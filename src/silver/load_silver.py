import logging

from src.silver.cleaning import clean_orders, clean_suppliers, clean_inventory
from src.silver.models import (
    leadtime_distribution,
    demand_forecast,
    late_delivery_classifier,
)

logger = logging.getLogger(__name__)

# Each entry: (human-readable name, module, whether a failure here should
# block downstream steps). Cleaning jobs are hard-blocking -- if orders
# can't be cleaned, nothing downstream should run on garbage data.
PIPELINE_STEPS = [
    ("clean_orders", clean_orders, True),
    ("clean_suppliers", clean_suppliers, True),
    ("clean_inventory", clean_inventory, True),
    ("leadtime_distribution", leadtime_distribution, True),
    ("demand_forecast", demand_forecast, True),
    ("late_delivery_classifier", late_delivery_classifier, True),
]


def run(conn_str: str, **context) -> dict:
    results = {}

    for step_name, module, blocking in PIPELINE_STEPS:
        logger.info("Starting silver step: %s", step_name)
        try:
            # Every module exposes run(conn_str, **context) -- calling that
            # directly avoids depending on each module's internal function
            # name matching its filename (it doesn't, for the 3 model files).
            result = module.run(conn_str)
            results[step_name] = {"status": "SUCCESS", "summary": result}
            logger.info("Completed silver step: %s -> %s", step_name, result)
        except Exception as exc:
            results[step_name] = {"status": "FAILED", "error": str(exc)}
            logger.exception("Silver step failed: %s", step_name)
            if blocking:
                raise
            logger.warning(
                "Step %s failed but is non-blocking -- continuing to next step.",
                step_name,
            )

    logger.info("Silver stage complete. Summary: %s", results)
    return results


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    run(conn_str)