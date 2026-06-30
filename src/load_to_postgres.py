"""
src/load_to_postgres.py
Reads JSON files from the raw data lake (data/raw/telegram_messages/)
and loads them into the `raw.telegram_messages` table in PostgreSQL.

Usage:
    python -m src.load_to_postgres
"""

import logging
import os

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

from src.datalake import iter_message_files, load_messages_json

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("load_to_postgres")

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "medical_warehouse"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS raw;"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw.telegram_messages (
    message_id      BIGINT,
    channel         TEXT,
    date            TIMESTAMPTZ,
    text            TEXT,
    views            INTEGER,
    forwards         INTEGER,
    media           JSONB,
    image_path      TEXT,
    loaded_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (message_id, channel)
);
"""

UPSERT_SQL = """
INSERT INTO raw.telegram_messages
    (message_id, channel, date, text, views, forwards, media, image_path)
VALUES %s
ON CONFLICT (message_id, channel) DO NOTHING;
"""


def get_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        logger.error("Could not connect to PostgreSQL with config host=%s db=%s: %s",
                     DB_CONFIG["host"], DB_CONFIG["dbname"], e)
        raise


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_SCHEMA_SQL)
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()


def load_all(conn):
    import json as _json

    total_rows = 0
    total_files = 0

    with conn.cursor() as cur:
        for channel_name, date_str, file_path in iter_message_files():
            try:
                messages = load_messages_json(file_path)
            except (OSError, ValueError) as e:
                logger.error("Skipping unreadable file %s: %s", file_path, e)
                continue

            if not messages:
                continue

            rows = [
                (
                    m.get("message_id"),
                    m.get("channel", channel_name),
                    m.get("date"),
                    m.get("text"),
                    m.get("views", 0),
                    m.get("forwards", 0),
                    _json.dumps(m.get("media")) if m.get("media") is not None else None,
                    m.get("image_path"),
                )
                for m in messages
            ]

            try:
                execute_values(cur, UPSERT_SQL, rows)
                conn.commit()
                total_rows += len(rows)
                total_files += 1
                logger.info("Loaded %d rows from %s", len(rows), file_path)
            except psycopg2.Error as e:
                conn.rollback()
                logger.error("Failed loading %s: %s", file_path, e)

    logger.info("Done. Loaded %d rows from %d files.", total_rows, total_files)


def main():
    conn = get_connection()
    try:
        ensure_schema(conn)
        load_all(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()