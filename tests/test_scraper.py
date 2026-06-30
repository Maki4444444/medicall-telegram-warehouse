"""
tests/test_scraper.py
Unit tests for the pure/serialization logic in src/scraper.py.
Does not connect to Telegram — uses a lightweight fake message object
to exercise serialize_message() in isolation.
"""

from datetime import datetime, timezone

import pytest

from src import scraper


class FakeMedia:
    """Stand-in for a Telethon media object."""
    pass


class FakeMessage:
    """Minimal stand-in for a Telethon Message, only the attributes
    serialize_message() actually reads."""

    def __init__(self, id, date, message, views, forwards, photo=False, media=None):
        self.id = id
        self.date = date
        self.message = message
        self.views = views
        self.forwards = forwards
        self.photo = photo
        self.media = media


@pytest.fixture(autouse=True)
def isolate_image_root(tmp_path, monkeypatch):
    """Avoid writing into the real data/raw/images during tests."""
    from src import datalake
    monkeypatch.setattr(datalake, "IMAGES_ROOT", tmp_path / "raw" / "images")
    yield


def test_serialize_message_basic_fields():
    msg = FakeMessage(
        id=101,
        date=datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc),
        message="Paracetamol 500mg in stock",
        views=42,
        forwards=3,
        photo=False,
        media=None,
    )

    result = scraper.serialize_message(msg, "CheMed123")

    assert result["message_id"] == 101
    assert result["channel"] == "CheMed123"
    assert result["text"] == "Paracetamol 500mg in stock"
    assert result["views"] == 42
    assert result["forwards"] == 3
    assert result["media"] is None
    assert result["image_path"] is None


def test_serialize_message_handles_missing_text():
    msg = FakeMessage(
        id=102,
        date=datetime(2026, 6, 24, tzinfo=timezone.utc),
        message=None,
        views=None,
        forwards=None,
        photo=False,
    )

    result = scraper.serialize_message(msg, "tikvahpharma")

    assert result["text"] == ""
    assert result["views"] == 0
    assert result["forwards"] == 0


def test_serialize_message_with_photo_sets_image_path():
    msg = FakeMessage(
        id=103,
        date=datetime(2026, 6, 24, tzinfo=timezone.utc),
        message="Product photo attached",
        views=10,
        forwards=1,
        photo=True,
        media=FakeMedia(),
    )

    result = scraper.serialize_message(msg, "lobelia4cosmetics")

    assert result["image_path"] is not None
    assert result["image_path"].endswith("103.jpg")
    assert result["media"]["has_photo"] is True


def test_serialize_message_no_date_returns_none():
    msg = FakeMessage(id=104, date=None, message="no date", views=0, forwards=0)

    result = scraper.serialize_message(msg, "CheMed123")

    assert result["date"] is None


def test_channels_list_contains_required_channels():
    """Sanity check the three rubric-required channels are configured."""
    lowered = [c.lower() for c in scraper.CHANNELS]
    assert any("chemed" in c for c in lowered)
    assert any("lobelia" in c for c in lowered)
    assert any("tikvah" in c for c in lowered)