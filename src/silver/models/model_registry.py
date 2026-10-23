import logging
import os
from contextlib import contextmanager
from pathlib import Path

import mlflow

logger = logging.getLogger(__name__)


DEFAULT_TRACKING_URI = f"file://{Path('/opt/airflow/mlruns').resolve()}"
TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI)


def _configure_mlflow(experiment_name: str) -> None:
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(experiment_name)


@contextmanager
def log_model_run(experiment_name: str, run_name: str, params: dict, tags: dict | None = None):

    _configure_mlflow(experiment_name)

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(params)
        if tags:
            mlflow.set_tags(tags)

        ctx = _RunContext(run)
        try:
            yield ctx
        except Exception:
            mlflow.set_tag("status", "FAILED")
            logger.exception(
                "Model run '%s' in experiment '%s' failed -- logged as FAILED in MLflow.",
                run_name, experiment_name,
            )
            raise
        else:
            mlflow.set_tag("status", "SUCCESS")
            logger.info(
                "Model run '%s' in experiment '%s' completed and logged to MLflow (run_id=%s).",
                run_name, experiment_name, run.info.run_id,
            )


class _RunContext:


    def __init__(self, run):
        self.run_id = run.info.run_id

    def log_metrics(self, metrics: dict) -> None:
        mlflow.log_metrics(metrics)

    def log_model(self, model, artifact_name: str, flavor: str = "lightgbm") -> None:
        """Logs the fitted model as an MLflow artifact. flavor must match
        the library the model was trained with -- 'lightgbm', 'sklearn', etc.
        """
        if flavor == "lightgbm":
            mlflow.lightgbm.log_model(model, artifact_name)
        elif flavor == "sklearn":
            mlflow.sklearn.log_model(model, artifact_name)
        else:
            raise ValueError(f"Unsupported model flavor: {flavor!r}")

    def log_dataframe_artifact(self, df, artifact_file_name: str) -> None:
        """Logs a small DataFrame (e.g. feature importance, validation
        predictions sample) as a CSV artifact attached to this run.
        """
        tmp_path = f"/tmp/{artifact_file_name}"
        df.to_csv(tmp_path, index=False)
        mlflow.log_artifact(tmp_path)


def get_latest_run(experiment_name: str) -> dict | None:

    _configure_mlflow(experiment_name)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        return None

    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="tags.status = 'SUCCESS'",
        order_by=["start_time DESC"],
        max_results=1,
    )
    if runs.empty:
        return None

    row = runs.iloc[0]
    return {
        "run_id": row["run_id"],
        "start_time": row["start_time"],
        "metrics": {c.replace("metrics.", ""): row[c] for c in runs.columns if c.startswith("metrics.")},
        "params": {c.replace("params.", ""): row[c] for c in runs.columns if c.startswith("params.")},
    }