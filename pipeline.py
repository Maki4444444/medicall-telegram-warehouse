"""
pipeline.py
Dagster orchestration pipeline for the Medical Telegram Warehouse.

Defines four ops:
  - scrape_telegram_data
  - load_raw_to_postgres
  - run_dbt_transformations
  - run_yolo_enrichment

Chained into a single job with enforced execution order,
and scheduled for daily runs at 06:00 UTC.

Usage:
    dagster dev -f pipeline.py
    Then open http://localhost:3000
"""

import shutil
import subprocess
import sys
from pathlib import Path

from dagster import (
    Definitions,
    In,
    Nothing,
    OpExecutionContext,
    ScheduleDefinition,
    get_dagster_logger,
    job,
    op,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: str | None = None):
    logger = get_dagster_logger()
    logger.info("Running: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or str(Path(__file__).parent),
    )

    if result.stdout:
        logger.info(result.stdout)
    if result.stderr:
        logger.warning(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}:\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Op 1 — scrape_telegram_data
# ---------------------------------------------------------------------------

@op(
    description=(
        "Scrapes messages and images from CheMed, Lobelia Cosmetics, and "
        "Tikvah Pharma Telegram channels using Telethon, writing raw JSON "
        "and images into the partitioned data lake under data/raw/. "
        "Requires a valid Telegram session file to exist from a prior "
        "manual authentication run."
    )
)
def scrape_telegram_data(context: OpExecutionContext):
    logger = get_dagster_logger()
    from pathlib import Path

    session_file = Path("telegram_scraper_session.session")
    if not session_file.exists():
        raise RuntimeError(
            "Telegram session file not found. Please run "
            "'python -m src.scraper --limit 10' manually first "
            "to complete the interactive login, then re-run this pipeline."
        )

    logger.info("Starting Telegram scrape for all configured channels...")
    _run([sys.executable, "-m", "src.scraper", "--limit", "500"])
    logger.info("Telegram scrape complete.")


# ---------------------------------------------------------------------------
# Op 2 — load_raw_to_postgres
# ---------------------------------------------------------------------------

@op(
    ins={"scrape_telegram_data": In(Nothing)},
    description=(
        "Reads all JSON files from the raw data lake "
        "(data/raw/telegram_messages/) and upserts them into the "
        "raw.telegram_messages table in PostgreSQL. Idempotent — "
        "safe to re-run without creating duplicate rows."
    )
)
def load_raw_to_postgres(context: OpExecutionContext):
    logger = get_dagster_logger()
    logger.info("Loading raw JSON files into PostgreSQL raw schema...")

    _run([sys.executable, "-m", "src.load_to_postgres"])

    logger.info("Raw data load complete.")


# ---------------------------------------------------------------------------
# Op 3 — run_dbt_transformations
# ---------------------------------------------------------------------------

@op(
    ins={"load_raw_to_postgres": In(Nothing)},
    description=(
        "Runs the full dbt project: executes all staging and mart models "
        "(stg_telegram_messages, dim_channels, dim_dates, fct_messages, "
        "fct_image_detections) and then runs all dbt tests to validate "
        "the star schema. Fails the op if any model or test fails."
    )
)
def run_dbt_transformations(context: OpExecutionContext):
    logger = get_dagster_logger()
    dbt_project_dir = str(Path(__file__).parent / "medical_warehouse")

    logger.info("Running dbt models...")
    _run(["dbt", "run"], cwd=dbt_project_dir)

    logger.info("Running dbt tests...")
    _run(["dbt", "test"], cwd=dbt_project_dir)

    logger.info("dbt transformations and tests complete.")


# ---------------------------------------------------------------------------
# Op 4 — run_yolo_enrichment
# ---------------------------------------------------------------------------

@op(
    ins={"run_dbt_transformations": In(Nothing)},
    description=(
        "Runs YOLOv8 nano object detection on all images in data/raw/images/, "
        "classifies each image as promotional / product_display / lifestyle / other, "
        "writes results to data/yolo_results.csv, seeds the CSV into dbt, "
        "and rebuilds fct_image_detections in the warehouse."
    )
)
def run_yolo_enrichment(context: OpExecutionContext):
    logger = get_dagster_logger()
    dbt_project_dir = str(Path(__file__).parent / "medical_warehouse")
    repo_root = Path(__file__).parent

    logger.info("Running YOLOv8 detection on scraped images...")
    _run([sys.executable, "-m", "src.yolo_detect"])

    logger.info("Copying YOLO results into dbt seeds...")
    shutil.copy(
        str(repo_root / "data" / "yolo_results.csv"),
        str(repo_root / "medical_warehouse" / "seeds" / "yolo_results.csv"),
    )

    logger.info("Seeding YOLO results into warehouse...")
    _run(["dbt", "seed"], cwd=dbt_project_dir)

    logger.info("Rebuilding fct_image_detections model...")
    _run(
        ["dbt", "run", "--select", "fct_image_detections"],
        cwd=dbt_project_dir,
    )

    logger.info("YOLO enrichment complete.")


# ---------------------------------------------------------------------------
# Job graph — enforces execution order via op dependencies
# ---------------------------------------------------------------------------

@job(
    description=(
        "Full Medical Telegram Warehouse pipeline: "
        "scrape → load → dbt transform → YOLO enrich. "
        "Each op depends on the previous, enforcing correct execution order."
    )
)
def medical_warehouse_pipeline():
    """
    Dependency graph:
        scrape_telegram_data
            └── load_raw_to_postgres
                    └── run_dbt_transformations
                            └── run_yolo_enrichment
    """
    run_yolo_enrichment(
        run_dbt_transformations(
            load_raw_to_postgres(
                scrape_telegram_data()
            )
        )
    )


# ---------------------------------------------------------------------------
# Schedule — daily at 06:00 UTC
# ---------------------------------------------------------------------------

daily_schedule = ScheduleDefinition(
    name="daily_medical_warehouse_pipeline",
    job=medical_warehouse_pipeline,
    cron_schedule="0 6 * * *",
    description="Runs the full pipeline daily at 06:00 UTC.",
)


# ---------------------------------------------------------------------------
# Definitions — top-level object Dagster requires at module level
# ---------------------------------------------------------------------------

defs = Definitions(
    jobs=[medical_warehouse_pipeline],
    schedules=[daily_schedule],
)