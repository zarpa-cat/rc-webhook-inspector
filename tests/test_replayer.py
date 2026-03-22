"""Tests for WebhookReplayer."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from rc_webhook_inspector.events import EventSynthesizer
from rc_webhook_inspector.replayer import WebhookReplayer

PAYLOAD = EventSynthesizer.generate("INITIAL_PURCHASE", subscriber_id="sub_test")
KEY = "replay-secret"


def _make_mock_response(status_code: int = 200, text: str = '{"ok": true}') -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def test_replay_success() -> None:
    replayer = WebhookReplayer()
    with patch("rc_webhook_inspector.replayer.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = _make_mock_response(200)
        result = replayer.replay("evt_1", PAYLOAD, "http://localhost:8080/webhook")

    assert result.success is True
    assert result.status_code == 200
    assert result.event_id == "evt_1"
    assert result.error is None


def test_replay_failure_status() -> None:
    replayer = WebhookReplayer()
    with patch("rc_webhook_inspector.replayer.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = _make_mock_response(400, "Bad Request")
        result = replayer.replay("evt_2", PAYLOAD, "http://localhost:8080/webhook")

    assert result.success is False
    assert result.status_code == 400


def test_replay_attaches_signature_header_when_auth_key_given() -> None:
    replayer = WebhookReplayer()
    captured_headers: dict = {}

    def fake_post(url: str, *, content: bytes, headers: dict) -> MagicMock:
        captured_headers.update(headers)
        return _make_mock_response(200)

    with patch("rc_webhook_inspector.replayer.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.side_effect = fake_post
        replayer.replay("evt_3", PAYLOAD, "http://localhost/hook", auth_key=KEY)

    assert "RC-Webhook-Signature" in captured_headers
    # Verify the signature is correct
    body = json.dumps(PAYLOAD, separators=(",", ":")).encode()
    expected = hmac.new(KEY.encode(), body, hashlib.sha256).hexdigest()
    assert captured_headers["RC-Webhook-Signature"] == expected


def test_replay_no_signature_without_auth_key() -> None:
    replayer = WebhookReplayer()
    captured_headers: dict = {}

    def fake_post(url: str, *, content: bytes, headers: dict) -> MagicMock:
        captured_headers.update(headers)
        return _make_mock_response(200)

    with patch("rc_webhook_inspector.replayer.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.side_effect = fake_post
        replayer.replay("evt_4", PAYLOAD, "http://localhost/hook")

    assert "RC-Webhook-Signature" not in captured_headers


def test_replay_timeout_returns_error_result() -> None:
    import httpx

    replayer = WebhookReplayer(timeout=0.001)
    with patch("rc_webhook_inspector.replayer.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        result = replayer.replay("evt_5", PAYLOAD, "http://slow.example/webhook")

    assert result.success is False
    assert result.status_code == 0
    assert result.error is not None
    assert "Timeout" in result.error


def test_replay_request_error_returns_error_result() -> None:
    import httpx

    replayer = WebhookReplayer()
    with patch("rc_webhook_inspector.replayer.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.side_effect = httpx.RequestError("connection refused")
        result = replayer.replay("evt_6", PAYLOAD, "http://dead.example/webhook")

    assert result.success is False
    assert result.error is not None
    assert "Request error" in result.error


def test_replay_sign_method() -> None:
    replayer = WebhookReplayer()
    sig = replayer.sign(PAYLOAD, KEY)
    assert len(sig) == 64


def test_replay_extra_headers_forwarded() -> None:
    replayer = WebhookReplayer()
    captured_headers: dict = {}

    def fake_post(url: str, *, content: bytes, headers: dict) -> MagicMock:
        captured_headers.update(headers)
        return _make_mock_response(200)

    with patch("rc_webhook_inspector.replayer.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.side_effect = fake_post
        replayer.replay(
            "evt_7", PAYLOAD, "http://localhost/hook",
            extra_headers={"X-Custom": "zarpa"}
        )

    assert captured_headers.get("X-Custom") == "zarpa"
