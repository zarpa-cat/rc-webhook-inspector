"""Tests for WebhookStore."""

from pathlib import Path

import pytest

from rc_webhook_inspector.events import EventSynthesizer
from rc_webhook_inspector.store import WebhookStore


@pytest.fixture
def store(tmp_path: Path) -> WebhookStore:
    db_path = tmp_path / "test.db"
    s = WebhookStore(db_path)
    yield s
    s.close()


@pytest.fixture
def sample_event() -> dict:
    return EventSynthesizer.generate("INITIAL_PURCHASE")


class TestWebhookStore:
    def test_record_returns_id(self, store: WebhookStore, sample_event: dict) -> None:
        event_id = store.record(sample_event)
        assert isinstance(event_id, str)
        assert len(event_id) > 0

    def test_get_returns_recorded_event(self, store: WebhookStore, sample_event: dict) -> None:
        event_id = store.record(sample_event)
        result = store.get(event_id)
        assert result is not None
        assert result["event_id"] == event_id
        assert result["payload"] == sample_event

    def test_get_nonexistent_returns_none(self, store: WebhookStore) -> None:
        assert store.get("nonexistent-id") is None

    def test_list_empty(self, store: WebhookStore) -> None:
        events = store.list()
        assert events == []

    def test_list_returns_recorded_events(self, store: WebhookStore) -> None:
        e1 = EventSynthesizer.generate("INITIAL_PURCHASE")
        e2 = EventSynthesizer.generate("RENEWAL")
        store.record(e1)
        store.record(e2)
        events = store.list()
        assert len(events) == 2

    def test_list_filter_by_type(self, store: WebhookStore) -> None:
        store.record(EventSynthesizer.generate("INITIAL_PURCHASE"))
        store.record(EventSynthesizer.generate("RENEWAL"))
        store.record(EventSynthesizer.generate("RENEWAL"))
        events = store.list(event_type="RENEWAL")
        assert len(events) == 2

    def test_list_limit(self, store: WebhookStore) -> None:
        for _ in range(5):
            store.record(EventSynthesizer.generate("INITIAL_PURCHASE"))
        events = store.list(limit=3)
        assert len(events) == 3

    def test_list_filter_by_source(self, store: WebhookStore) -> None:
        store.record(EventSynthesizer.generate("INITIAL_PURCHASE"), source="synthetic")
        store.record(EventSynthesizer.generate("RENEWAL"), source="webhook")
        events = store.list(source="webhook")
        assert len(events) == 1
        assert events[0]["source"] == "webhook"

    def test_clear_returns_count(self, store: WebhookStore) -> None:
        store.record(EventSynthesizer.generate("INITIAL_PURCHASE"))
        store.record(EventSynthesizer.generate("RENEWAL"))
        count = store.clear()
        assert count == 2

    def test_clear_empties_store(self, store: WebhookStore) -> None:
        store.record(EventSynthesizer.generate("INITIAL_PURCHASE"))
        store.clear()
        assert store.list() == []

    def test_record_preserves_event_type(self, store: WebhookStore) -> None:
        event = EventSynthesizer.generate("CANCELLATION")
        event_id = store.record(event)
        result = store.get(event_id)
        assert result is not None
        assert result["event_type"] == "CANCELLATION"
