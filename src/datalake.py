"""
datalake.py
Helper functions for writing scraped Telegram data into the project's
partitioned raw data lake structure.

Layout produced:
    data/raw/telegram_messages/{YYYY-MM-DD}/{channel_name}.json
    data/raw/images/{channel_name}/{message_id}.jpg
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("datalake")

DATA_ROOT = Path(os.getenv("DATA_ROOT", "data"))
MESSAGES_ROOT = DATA_ROOT / "raw" / "telegram_messages"
IMAGES_ROOT = DATA_ROOT / "raw" / "images"


def get_messages_path(channel_name: str, date_str: str) -> Path:
    """Return (and create) the path for a channel's messages on a given date."""
    day_dir = MESSAGES_ROOT / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir / f"{channel_name}.json"


def get_image_path(channel_name: str, message_id: int) -> Path:
    """Return (and create) the path for a downloaded image."""
    channel_dir = IMAGES_ROOT / channel_name
    channel_dir.mkdir(parents=True, exist_ok=True)
    return channel_dir / f"{message_id}.jpg"


def save_messages_json(channel_name: str, date_str: str, messages: list) -> Path:
    """
    Write a list of message dicts to the partitioned JSON path.
    Preserves whatever structure is passed in (no field stripping).
    """
    path = get_messages_path(channel_name, date_str)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2, default=str)
        logger.info(
            "Saved %d messages for channel=%s date=%s -> %s",
            len(messages), channel_name, date_str, path,
        )
    except OSError as e:
        logger.error("Failed writing messages for %s/%s: %s", channel_name, date_str, e)
        raise
    return path


def load_messages_json(path: Path) -> list:
    """Read a previously saved messages JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_message_files():
    """
    Generator yielding (channel_name, date_str, file_path) for every
    JSON file currently in the data lake. Used by the Postgres loader.
    """
    if not MESSAGES_ROOT.exists():
        return
    for date_dir in sorted(MESSAGES_ROOT.iterdir()):
        if not date_dir.is_dir():
            continue
        for file_path in sorted(date_dir.glob("*.json")):
            channel_name = file_path.stem
            yield channel_name, date_dir.name, file_path