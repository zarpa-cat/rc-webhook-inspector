"""Tests for WebhookInspector."""

from rc_webhook_inspector.events import EventSynthesizer
from rc_webhook_inspector.inspector import WebhookInspector


class TestWebhookInspector:
    def test_validate_valid_event(self) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        result = WebhookInspector.validate(event)
        assert result.valid is True
        assert result.errors == []

    def test_validate_missing_event_field(self) -> None:
        result = WebhookInspector.validate({"api_version": "1.0"})
        assert result.valid is False
        assert any("event" in e for e in result.errors)

    def test_validate_missing_type(self) -> None:
        payload = {"api_version": "1.0", "event": {"product_id": "x"}}
        result = WebhookInspector.validate(payload)
        assert result.valid is False
        assert any("type" in e for e in result.errors)

    def test_validate_missing_api_version(self) -> None:
        payload = {"event": {"type": "INITIAL_PURCHASE"}}
        result = WebhookInspector.validate(payload)
        assert result.valid is False
        assert any("api_version" in e for e in result.errors)

    def test_validate_unrecognized_type_warns(self) -> None:
        payload = {"api_version": "1.0", "event": {"type": "CUSTOM_EVENT"}}
        result = WebhookInspector.validate(payload)
        assert result.valid is True
        assert any("Unrecognized" in w for w in result.warnings)

    def test_validate_invalid_timestamp(self) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        event["event"]["event_timestamp_ms"] = -1
        result = WebhookInspector.validate(event)
        assert result.valid is False

    def test_validate_warns_missing_product_id(self) -> None:
        payload = {"api_version": "1.0", "event": {"type": "INITIAL_PURCHASE"}}
        result = WebhookInspector.validate(payload)
        assert any("product_id" in w for w in result.warnings)

    def test_validate_warns_missing_app_user_id(self) -> None:
        payload = {"api_version": "1.0", "event": {"type": "INITIAL_PURCHASE"}}
        result = WebhookInspector.validate(payload)
        assert any("app_user_id" in w for w in result.warnings)

    def test_summarize_extracts_fields(self) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE", subscriber_id="user_42")
        summary = WebhookInspector.summarize(event)
        assert summary["type"] == "INITIAL_PURCHASE"
        assert summary["subscriber_id"] == "user_42"
        assert summary["product_id"] is not None
        assert summary["timestamp_ms"] is not None

    def test_summarize_empty_payload(self) -> None:
        summary = WebhookInspector.summarize({})
        assert summary["type"] is None
        assert summary["subscriber_id"] is None

    def test_validate_all_generated_types_valid(self) -> None:
        for et in EventSynthesizer.all_types():
            event = EventSynthesizer.generate(et)
            result = WebhookInspector.validate(event)
            assert result.valid is True, f"Validation failed for {et}: {result.errors}"
