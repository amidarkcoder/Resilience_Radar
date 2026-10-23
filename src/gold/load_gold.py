import logging

from src.gold.decision_engine import (
    safety_stock,
    dual_sourcing_mc,
    nearshoring_milp,
)

from src.gold.dimensions import (
    build_dimensions
)

from src.gold.facts import (
    build_facts
)

from src.gold.kpi_marts import (
    inventory_kpi_mart,
    otif_mart,
    perfect_order_mart
)
logger = logging.getLogger(__name__)

PIPELINE_STEPS = [
    # (step_name, module, blocking)
    ("build_dimensions", build_dimensions, True),
    ("build_facts", build_facts, True),
    ("otif_mart", otif_mart, False),
    ("perfect_order_mart", perfect_order_mart, False),
    ("inventory_kpi_mart", inventory_kpi_mart, False),
    ("safety_stock", safety_stock, False),
    ("dual_sourcing_mc", dual_sourcing_mc, False),
    ("nearshoring_milp", nearshoring_milp, False),
]


def run(conn_str: str, **context) -> dict:
    results = {}
    for step_name, module, blocking in PIPELINE_STEPS:
        logger.info("Starting gold step: %s", step_name)
        try:
            result = module.run(conn_str)
            results[step_name] = {"status": "SUCCESS", "summary": result}
            logger.info("Completed gold step: %s -> %s", step_name, result)
        except Exception as exc:
            results[step_name] = {"status": "FAILED", "error": str(exc)}
            logger.exception("Gold step failed: %s", step_name)
            if blocking:
                logger.error(
                    "Step %s is blocking -- aborting remaining gold steps.", step_name
                )
                raise
            logger.warning(
                "Step %s failed but is non-blocking -- continuing to next step.", step_name
            )

    failed_steps = [name for name, r in results.items() if r["status"] == "FAILED"]
    if failed_steps:
        logger.warning(
            "Gold stage completed with %d non-blocking failure(s): %s",
            len(failed_steps), failed_steps,
        )
    logger.info("Gold stage complete. Summary: %s", results)
    return results


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    run(conn_str)