"""Tests for EventSynthesizer."""

import pytest

from rc_webhook_inspector.events import EVENT_TYPES, EventSynthesizer


class TestEventSynthesizer:
    def test_all_types_returns_list(self) -> None:
        types = EventSynthesizer.all_types()
        assert isinstance(types, list)
        assert len(types) == 12

    def test_all_types_contains_expected(self) -> None:
        types = EventSynthesizer.all_types()
        assert "INITIAL_PURCHASE" in types
        assert "RENEWAL" in types
        assert "CANCELLATION" in types
        assert "PRODUCT_CHANGE" in types

    def test_generate_returns_dict(self) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        assert isinstance(event, dict)

    def test_generate_has_api_version(self) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        assert event["api_version"] == "1.0"

    def test_generate_has_event_body(self) -> None:
        event = EventSynthesizer.generate("RENEWAL")
        assert "event" in event
        assert event["event"]["type"] == "RENEWAL"

    def test_generate_with_subscriber_id(self) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE", subscriber_id="user_123")
        assert event["event"]["app_user_id"] == "user_123"

    def test_generate_with_overrides(self) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE", price=19.99, currency="EUR")
        assert event["event"]["price"] == 19.99
        assert event["event"]["currency"] == "EUR"

    def test_generate_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown event type"):
            EventSynthesizer.generate("FAKE_EVENT")

    def test_generate_cancellation_has_cancel_reason(self) -> None:
        event = EventSynthesizer.generate("CANCELLATION")
        assert "cancel_reason" in event["event"]

    def test_generate_billing_issue_has_grace_period(self) -> None:
        event = EventSynthesizer.generate("BILLING_ISSUE")
        assert "grace_period_expiration_at_ms" in event["event"]

    def test_generate_product_change_has_new_product(self) -> None:
        event = EventSynthesizer.generate("PRODUCT_CHANGE")
        assert "new_product_id" in event["event"]

    def test_generate_transfer_has_transfer_fields(self) -> None:
        event = EventSynthesizer.generate("TRANSFER")
        assert "transferred_from" in event["event"]
        assert "transferred_to" in event["event"]

    def test_generate_all_types_succeed(self) -> None:
        for et in EVENT_TYPES:
            event = EventSynthesizer.generate(et)
            assert event["event"]["type"] == et

    def test_generate_has_required_fields(self) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        body = event["event"]
        assert "id" in body
        assert "product_id" in body
        assert "transaction_id" in body
        assert "app_user_id" in body
        assert "event_timestamp_ms" in body

    def test_generate_unique_ids(self) -> None:
        e1 = EventSynthesizer.generate("INITIAL_PURCHASE")
        e2 = EventSynthesizer.generate("INITIAL_PURCHASE")
        assert e1["event"]["id"] != e2["event"]["id"]
