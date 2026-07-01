# Medical Telegram Warehouse

An end-to-end data pipeline for Ethiopian medical and pharmaceutical Telegram
channels from raw scraping through a dimensional data warehouse, computer-vision
enrichment, an analytical REST API, and full pipeline orchestration.

Built for the **10 Academy Week 8 Challenge**: *Shipping a Data Product: From Raw
Telegram Data to an Analytical API*.


## Business Context

Kara Solutions needs actionable insight into Ethiopian medical businesses operating
on Telegram. Most-mentioned products, posting trends, channel activity patterns,
and visual content analysis (promotional images vs. product displays) are all
business questions this pipeline answers.

The architecture follows a modern **ELT** approach:

```
Telegram (Telethon)
    └── Raw Data Lake (JSON + images)
            └── PostgreSQL raw schema
                    └── dbt staging models
                            └── dbt star schema marts
                                    └── YOLOv8 image enrichment
                                            └── FastAPI analytical endpoints
                                                    └── Dagster orchestration
```


## Project Structure

```
medicall-telegram-warehouse/
├── .github/
│   └── workflows/
│       └── unittests.yml           # CI: runs pytest on every push and PR
├── .env                            # secrets — NEVER committed
├── .env.example                    # template for required env vars
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md
├── pipeline.py                     # Dagster orchestration (Task 5)
│
├── data/
│   └── raw/
│       ├── telegram_messages/      # partitioned by date: {YYYY-MM-DD}/{channel}.json
│       └── images/                 # by channel: {channel_name}/{message_id}.jpg
│
├── logs/                           # scrape activity and error logs
│
├── medical_warehouse/              # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml                # env-var based, safe to commit
│   ├── seeds/
│   │   └── yolo_results.csv        # YOLO detection results loaded via dbt seed
│   ├── models/
│   │   ├── staging/
│   │   │   ├── sources.yml
│   │   │   ├── schema.yml
│   │   │   └── stg_telegram_messages.sql
│   │   └── marts/
│   │       ├── schema.yml
│   │       ├── dim_channels.sql
│   │       ├── dim_dates.sql
│   │       ├── fct_messages.sql
│   │       └── fct_image_detections.sql
│   └── tests/
│       ├── assert_no_future_messages.sql
│       └── assert_positive_views.sql
│
├── src/
│   ├── __init__.py
│   ├── scraper.py                  # Telethon scraping pipeline (Task 1)
│   ├── datalake.py                 # data lake read/write helpers (Task 1)
│   ├── load_to_postgres.py         # raw JSON → Postgres loader (Task 2)
│   └── yolo_detect.py              # YOLOv8 image enrichment (Task 3)
│
├── api/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application (Task 4)
│   ├── database.py                 # SQLAlchemy connection (Task 4)
│   └── schemas.py                  # Pydantic request/response models (Task 4)
│
├── tests/
│   ├── __init__.py
│   ├── test_datalake.py            # unit tests for datalake helpers
│   └── test_scraper.py             # unit tests for scraper serialization

```


## Setup

### Prerequisites
- Python 3.11+
- Docker Desktop (for PostgreSQL)
- Git
- A Telegram account with API credentials from https://my.telegram.org

### 1. Clone and create a virtual environment

```powershell
git clone <your-repo-url> medicall-telegram-warehouse
cd medicall-telegram-warehouse
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in real values. **Never commit `.env`.**

TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
TELEGRAM_SESSION_NAME=telegram_scraper_session

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medical_warehouse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=


Telegram credentials: register an app at https://my.telegram.org → API Development Tools.

### 3. Start PostgreSQL via Docker

```powershell
docker run -d --name medical_pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=medical_warehouse postgres:16
```

### 4. Load environment variables and set dbt profile path

Run this in every new terminal session before using dbt or Dagster:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}
$env:DBT_PROFILES_DIR = "$PWD\medical_warehouse"
```


## Running the Pipeline

### Individual steps

| Step | Command | Output |
|---|---|---|
| **Task 1** Scrape Telegram | `python -m src.scraper --limit 500` | `data/raw/telegram_messages/`, `data/raw/images/`, `logs/` |
| **Task 2** Load raw to Postgres | `python -m src.load_to_postgres` | `raw.telegram_messages` table populated |
| **Task 2** Run dbt models | `cd medical_warehouse && dbt run` | staging view + star schema marts built |
| **Task 2** Run dbt tests | `cd medical_warehouse && dbt test` | 21 tests, 0 failures |
| **Task 2** Generate dbt docs | `cd medical_warehouse && dbt docs generate && dbt docs serve` | browsable data dictionary at localhost:8080 |
| **Task 3** Run YOLO detection | `python -m src.yolo_detect` | `data/yolo_results.csv` with 446 detection rows |
| **Task 3** Seed YOLO to dbt | `cd medical_warehouse && dbt seed` | `yolo_results` table seeded |
| **Task 4** Start the API | `uvicorn api.main:app --reload` | `http://localhost:8000/docs` |
| **Task 5** Run full pipeline | `dagster dev -f pipeline.py` | Dagster UI at `http://localhost:3000` |

### Automated pipeline (Task 5 — Dagster)

```powershell
dagster dev -f pipeline.py
```

Open `http://localhost:3000` → Jobs → `medical_warehouse_pipeline` → Launchpad → Launch Run.

The pipeline executes all four stages in order:
```
scrape_telegram_data → load_raw_to_postgres → run_dbt_transformations → run_yolo_enrichment
```

A daily schedule (`0 6 * * *`) is configured under Automation → Schedules.


## Data Warehouse Star Schema

Built with dbt, materialized in PostgreSQL under the `public_marts` schema.

```
dim_channels ──┐
               ├── fct_messages ──── fct_image_detections
dim_dates    ──┘
```

| Model | Type | Description |
|---|---|---|
| `stg_telegram_messages` | View | Cleaned, typed, filtered staging layer over raw messages |
| `dim_channels` | Table | One row per channel: name, type (Pharmaceutical/Cosmetics/Medical), posting stats |
| `dim_dates` | Table | Date spine generated from scrape date range with day/week/month/quarter fields |
| `fct_messages` | Table | One row per message with FK to both dimensions, view/forward counts, has_image flag |
| `fct_image_detections` | Table | One row per YOLO detection joined to fct_messages on message_id |

### dbt test coverage
- `unique` + `not_null` on all primary keys
- `relationships` tests on all foreign keys (`fct_messages → dim_channels`, `fct_messages → dim_dates`)
- Custom test: `assert_no_future_messages` no message dated after today
- Custom test: `assert_positive_views` no negative view counts


## Image Classification (Task 3 YOLOv8)

YOLOv8 nano (`yolov8n.pt`) runs detection on all downloaded channel images.
Each image is classified into one of four business categories:

| Category | Rule |
|---|---|
| `promotional` | Person + product-like object detected |
| `product_display` | Product-like object only, no person |
| `lifestyle` | Person only, no product-like object |
| `other` | Neither detected above confidence threshold |

Results: **310 images processed**, **446 detection rows**, across all three channels.


## Analytical API (Task 4 FastAPI)

Base URL: `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

| Endpoint | Description |
|---|---|
| `GET /health` | API and database connectivity status |
| `GET /api/reports/top-products?limit=10` | Most frequently mentioned terms across all channels |
| `GET /api/channels/{channel_name}/activity` | Daily post counts and view trends for a channel |
| `GET /api/search/messages?query=paracetamol&limit=20` | ILIKE keyword search over message content |
| `GET /api/reports/visual-content` | YOLO image category counts and confidence scores by channel |

All endpoints return typed Pydantic responses with explicit HTTP status codes:
`400` invalid params, `404` not found, `500` database errors.


## Channels Scraped

| Channel | Type | Username |
|---|---|---|
| CheMed | Pharmaceutical | `CheMed123` |
| Lobelia Cosmetics | Cosmetics | `lobelia4cosmetics` |
| Tikvah Pharma | Pharmaceutical | `tikvahpharma` |


## Testing

```powershell
python -m pytest tests/ -v
```

CI runs automatically on every push and pull request via
`.github/workflows/unittests.yml`.

Unit tests cover:
- `test_datalake.py` path generation, JSON round-tripping, `iter_message_files()`
- `test_scraper.py`  message serialization, null handling, channel list validation


## Branching Strategy

Each task developed on its own branch, merged into `main` via Pull Request:

| Branch | Task |
|---|---|
| `task-1` | Data scraping and collection (Telethon + data lake) |
| `task-2` | Data modeling and transformation (Postgres loader + dbt) |
| `task-3` | YOLOv8 image enrichment and warehouse integration |
| `task-4` | FastAPI analytical endpoints |
| `task-5` | Dagster pipeline orchestration and scheduling |


## Pipeline Status

- [x] Task 1 Data Scraping and Collection
- [x] Task 2 Data Modeling and Transformation
- [x] Task 3 Data Enrichment with YOLOv8
- [x] Task 4 Analytical API with FastAPI
- [x] Task 5 Pipeline Orchestration with Dagster