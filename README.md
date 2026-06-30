# Medical Telegram Warehouse

An end-to-end data pipeline for Ethiopian medical and pharmaceutical Telegram
channels from raw scraping to a dimensional data warehouse, computer-vision
enrichment, and an analytical API. Built for the 10 Academy Week 8 Challenge
("Shipping a Data Product: From Raw Telegram Data to an Analytical API").

## Business Context

Kara Solutions needs actionable insight into Ethiopian medical businesses
operating on Telegram, most-mentioned products, posting trends, channel
activity, and visual content patterns (e.g. promotional images vs. plain
product photos). This repo implements a modern **ELT** pipeline:

Telegram (Telethon) → Raw Data Lake (JSON/images) → PostgreSQL raw schema
→ dbt staging models → dbt star schema marts → YOLOv8 enrichment
→ FastAPI analytical endpoints → Dagster orchestration

## Project Structure

medicall-telegram-warehouse/
├── .vscode/settings.json
├── .github/workflows/unittests.yml   # CI: runs pytest on every push/PR
├── .env                               # secrets — never committed
├── .env.example                       # template for required env vars
├── .gitignore
├── docker-compose.yml                 # Postgres + app services
├── Dockerfile                         # Python environment
├── requirements.txt
├── data/                              # raw data lake (gitignored, sample committed)
│   └── raw/
│       ├── telegram_messages/{YYYY-MM-DD}/{channel}.json
│       └── images/{channel}/{message_id}.jpg
├── logs/                              # scrape activity + error logs
├── medical_warehouse/                 # dbt project (created via dbt init)
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── staging/                   # cleaned, typed, renamed source data
│   │   └── marts/                     # star schema: dim_channels, dim_dates, fct_messages
│   └── tests/                         # custom dbt data tests
├── src/
│   ├── scraper.py                     # Telethon scraping pipeline (Task 1)
│   ├── datalake.py                    # data lake read/write helpers (Task 1)
│   ├── load_to_postgres.py            # raw JSON -> Postgres loader (Task 2)
│   └── yolo_detect.py                 # YOLOv8 image enrichment (Task 3)
├── api/
│   ├── main.py                        # FastAPI application (Task 4)
│   ├── database.py                    # SQLAlchemy connection (Task 4)
│   └── schemas.py                     # Pydantic request/response models (Task 4)
├── pipeline.py                        # Dagster ops, job graph, schedule (Task 5)
├── notebooks/
├── tests/                             # pytest unit tests, run in CI
└── scripts/

## Setup

### 1. Clone and create a virtual environment

```powershell
git clone <your-repo-url> medical-telegram-warehouse
cd medical-telegram-warehouse
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in real values. **Never commit `.env`.**

Telegram credentials come from registering an app at https://my.telegram.org.

### 3. Start PostgreSQL

```powershell
docker run -d --name medical_pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=medical_warehouse postgres:16
```

(Or use `docker-compose up -d` once `docker-compose.yml` is finalized.)

## Running the Pipeline

| Step | Command | Output |
|---|---|---|
| Scrape Telegram | `python -m src.scraper --limit 200` | `data/raw/telegram_messages/`, `data/raw/images/`, `logs/` |
| Load raw data to Postgres | `python -m src.load_to_postgres` | `raw.telegram_messages` table |
| Run dbt transformations | `cd medical_warehouse; dbt run; dbt test` | staging views + star schema marts in Postgres |
| Generate dbt docs | `dbt docs generate; dbt docs serve` | browsable data dictionary |
| Run YOLO enrichment | `python -m src.yolo_detect` | `data/yolo_results.csv` |
| Start the API | `uvicorn api.main:app --reload` | `http://localhost:8000/docs` |
| Run the orchestrated pipeline | `dagster dev -f pipeline.py` | Dagster UI with full job graph |

## Testing

```powershell
pytest tests/ -v
```

CI runs this automatically on every push and pull request via
`.github/workflows/unittests.yml`.

## Star Schema Design

- **`dim_channels`** — one row per channel (surrogate `channel_key`, name, type, posting stats)
- **`dim_dates`** — generated date spine over the scraped date range
- **`fct_messages`** — one row per message, FKs into both dimensions, plus view/forward counts and `has_image`
- **`fct_image_detections`** *(Task 3)* — YOLO detection results joined to `fct_messages` on `message_id`

## Branching Strategy

Each task is developed on its own branch off `main` and merged via Pull Request:

main ← task-1 (scraping)
main ← task-2 (dbt modeling)
main ← task-3 (YOLO enrichment)
main ← task-4 (FastAPI)
main ← task-5 (Dagster orchestration)

## Status

- [x] Task 1 Data Scraping and Collection
- [x] Task 2 Data Modeling and Transformation
- [ ] Task 3 Data Enrichment with YOLOv8
- [ ] Task 4 Analytical API with FastAPI
- [ ] Task 5 Pipeline Orchestration with Dagster