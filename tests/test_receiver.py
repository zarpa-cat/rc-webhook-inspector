"""Tests for WebhookReceiver FastAPI app."""

import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rc_webhook_inspector.events import EventSynthesizer
from rc_webhook_inspector.receiver import app, configure


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test_receiver.db"
    configure(db_path=str(db_path), auth_key=None)
    return TestClient(app)


@pytest.fixture
def auth_client(tmp_path: Path) -> tuple[TestClient, str]:
    db_path = tmp_path / "test_receiver_auth.db"
    key = "test-secret-key"
    configure(db_path=str(db_path), auth_key=key)
    return TestClient(app), key


class TestReceiver:
    def test_health(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_post_webhook(self, client: TestClient) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        resp = client.post("/webhook", json=event)
        assert resp.status_code == 200
        data = resp.json()
        assert "event_id" in data
        assert data["valid"] is True

    def test_post_invalid_json(self, client: TestClient) -> None:
        resp = client.post(
            "/webhook", content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_list_events(self, client: TestClient) -> None:
        event = EventSynthesizer.generate("RENEWAL")
        client.post("/webhook", json=event)
        resp = client.get("/events")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_event(self, client: TestClient) -> None:
        event = EventSynthesizer.generate("CANCELLATION")
        post_resp = client.post("/webhook", json=event)
        event_id = post_resp.json()["event_id"]
        resp = client.get(f"/events/{event_id}")
        assert resp.status_code == 200
        assert resp.json()["event_id"] == event_id

    def test_get_event_not_found(self, client: TestClient) -> None:
        resp = client.get("/events/nonexistent")
        assert resp.status_code == 404

    def test_webhook_with_valid_signature(self, auth_client: tuple[TestClient, str]) -> None:
        client, key = auth_client
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        body = json.dumps(event).encode()
        sig = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
        resp = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "RC-Webhook-Signature": sig},
        )
        assert resp.status_code == 200

    def test_webhook_missing_signature(self, auth_client: tuple[TestClient, str]) -> None:
        client, _ = auth_client
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        resp = client.post("/webhook", json=event)
        assert resp.status_code == 401

    def test_webhook_invalid_signature(self, auth_client: tuple[TestClient, str]) -> None:
        client, _ = auth_client
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        resp = client.post(
            "/webhook",
            json=event,
            headers={"RC-Webhook-Signature": "invalid"},
        )
        assert resp.status_code == 401

    def test_list_events_with_type_filter(self, client: TestClient) -> None:
        client.post("/webhook", json=EventSynthesizer.generate("INITIAL_PURCHASE"))
        client.post("/webhook", json=EventSynthesizer.generate("RENEWAL"))
        resp = client.get("/events", params={"event_type": "RENEWAL"})
        assert resp.status_code == 200
        events = resp.json()
        assert all(e["event_type"] == "RENEWAL" for e in events)
