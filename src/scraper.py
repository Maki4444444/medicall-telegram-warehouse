"""
src/scraper.py
Telethon-based scraper for public Telegram channels selling medical
and pharmaceutical products in Ethiopia.

Usage:
    python -m src.scraper                 # scrape all configured channels
    python -m src.scraper --limit 200      # cap messages per channel
"""

import argparse
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    UsernameNotOccupiedError,
)

from src.datalake import save_messages_json, get_image_path

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "telegram_scraper_session")

# Public channels in scope for this project (rubric-required + extras
# from https://et.tgstat.com/medicine can be appended here).
CHANNELS = [
    "CheMed123",          # CheMed Telegram Channel
    "lobelia4cosmetics",  # Lobelia Cosmetics
    "tikvahpharma",       # Tikvah Pharma
]

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logging() -> logging.Logger:
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"scrape_{today}.log"

    logger = logging.getLogger("scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = setup_logging()


def serialize_message(message, channel_name: str) -> dict:
    """Extract the fields required by the project rubric from a Telethon message."""
    media_info = None
    has_photo = bool(message.photo)

    if message.media is not None:
        media_info = {
            "type": type(message.media).__name__,
            "has_photo": has_photo,
        }

    return {
        "message_id": message.id,
        "channel": channel_name,
        "date": message.date.isoformat() if message.date else None,
        "text": message.message or "",
        "views": message.views or 0,
        "forwards": message.forwards or 0,
        "media": media_info,
        "image_path": (
            str(get_image_path(channel_name, message.id)) if has_photo else None
        ),
    }


async def download_image_if_present(client: TelegramClient, message, channel_name: str):
    if not message.photo:
        return
    target_path = get_image_path(channel_name, message.id)
    if target_path.exists():
        return  # already downloaded, skip
    try:
        await client.download_media(message, file=str(target_path))
        logger.info("Downloaded image for message_id=%s channel=%s", message.id, channel_name)
    except Exception as e:  # noqa: BLE001 - log and continue, don't kill the run
        logger.error(
            "Failed to download image for message_id=%s channel=%s: %s",
            message.id, channel_name, e,
        )


async def scrape_channel(client: TelegramClient, channel_name: str, limit: int):
    """Scrape a single channel and persist results, grouped by message date."""
    logger.info("Starting scrape for channel=%s (limit=%s)", channel_name, limit)
    messages_by_date: dict[str, list] = {}
    count = 0

    try:
        async for message in client.iter_messages(channel_name, limit=limit):
            if message.message is None and message.media is None:
                continue  # skip empty service messages

            date_str = message.date.strftime("%Y-%m-%d") if message.date else "unknown"
            messages_by_date.setdefault(date_str, []).append(
                serialize_message(message, channel_name)
            )
            await download_image_if_present(client, message, channel_name)
            count += 1

    except FloodWaitError as e:
        logger.error(
            "Rate limited on channel=%s, must wait %s seconds. Stopping this channel early.",
            channel_name, e.seconds,
        )
    except (ChannelPrivateError, UsernameNotOccupiedError) as e:
        logger.error("Cannot access channel=%s: %s", channel_name, e)
        return
    except Exception as e:  # noqa: BLE001 - network/unexpected errors
        logger.error("Unexpected error scraping channel=%s: %s", channel_name, e)

    for date_str, messages in messages_by_date.items():
        save_messages_json(channel_name, date_str, messages)

    logger.info("Finished channel=%s, scraped %d messages total", channel_name, count)


async def main(limit: int):
    if not API_ID or not API_HASH:
        logger.error("TELEGRAM_API_ID / TELEGRAM_API_HASH missing from environment (.env)")
        raise SystemExit(1)

    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=== Scrape run started at %s, channels=%s ===", started_at, CHANNELS)

    async with TelegramClient(SESSION_NAME, int(API_ID), API_HASH) as client:
        for channel_name in CHANNELS:
            await scrape_channel(client, channel_name, limit)

    logger.info("=== Scrape run complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Telegram channels into the raw data lake.")
    parser.add_argument(
        "--limit", type=int, default=500, help="Max messages to pull per channel"
    )
    args = parser.parse_args()
    asyncio.run(main(args.limit))