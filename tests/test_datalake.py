"""
tests/test_datalake.py
Unit tests for src/datalake.py — verifies the data lake path structure
and read/write helpers, without touching the real data/ directory.
"""

import json

import pytest

from src import datalake


@pytest.fixture(autouse=True)
def isolate_data_root(tmp_path, monkeypatch):
    """
    Redirect datalake's root paths to a temp directory for every test,
    so tests never read/write the project's real data/ folder.
    """
    fake_messages_root = tmp_path / "raw" / "telegram_messages"
    fake_images_root = tmp_path / "raw" / "images"
    monkeypatch.setattr(datalake, "MESSAGES_ROOT", fake_messages_root)
    monkeypatch.setattr(datalake, "IMAGES_ROOT", fake_images_root)
    return tmp_path


def test_get_messages_path_creates_partitioned_folder():
    path = datalake.get_messages_path("CheMed123", "2026-06-24")

    assert path.parent.exists()
    assert path.name == "CheMed123.json"
    assert path.parent.name == "2026-06-24"


def test_get_image_path_creates_channel_subdirectory():
    path = datalake.get_image_path("lobelia4cosmetics", 98765)

    assert path.parent.exists()
    assert path.name == "98765.jpg"
    assert path.parent.name == "lobelia4cosmetics"


def test_save_and_load_messages_json_round_trip():
    messages = [
        {"message_id": 1, "text": "Paracetamol available", "views": 10, "forwards": 2},
        {"message_id": 2, "text": "New stock of bandages", "views": 5, "forwards": 0},
    ]

    saved_path = datalake.save_messages_json("tikvahpharma", "2026-06-24", messages)
    assert saved_path.exists()

    loaded = datalake.load_messages_json(saved_path)
    assert loaded == messages


def test_save_messages_json_is_valid_json_on_disk():
    messages = [{"message_id": 1, "text": "hello"}]
    saved_path = datalake.save_messages_json("CheMed123", "2026-06-24", messages)

    with open(saved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data == messages


def test_iter_message_files_yields_channel_date_and_path():
    datalake.save_messages_json("CheMed123", "2026-06-24", [{"message_id": 1}])
    datalake.save_messages_json("tikvahpharma", "2026-06-25", [{"message_id": 2}])

    results = list(datalake.iter_message_files())
    channels = {r[0] for r in results}
    dates = {r[1] for r in results}

    assert channels == {"CheMed123", "tikvahpharma"}
    assert dates == {"2026-06-24", "2026-06-25"}
    assert all(path.exists() for _, _, path in results)


def test_iter_message_files_empty_when_no_data():
    results = list(datalake.iter_message_files())
    assert results == []