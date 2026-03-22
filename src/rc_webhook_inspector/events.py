"""Synthetic RevenueCat webhook event generation."""

from __future__ import annotations

import time
import uuid
from typing import Any

EVENT_TYPES = [
    "INITIAL_PURCHASE",
    "RENEWAL",
    "CANCELLATION",
    "UNCANCELLATION",
    "BILLING_ISSUE",
    "SUBSCRIPTION_PAUSED",
    "SUBSCRIPTION_RESUMED",
    "EXPIRATION",
    "NON_RENEWING_PURCHASE",
    "SUBSCRIBER_ALIAS",
    "TRANSFER",
    "PRODUCT_CHANGE",
]


class EventSynthesizer:
    """Generate synthetic RevenueCat webhook payloads."""

    @staticmethod
    def all_types() -> list[str]:
        """Return all supported event type strings."""
        return list(EVENT_TYPES)

    @staticmethod
    def generate(
        event_type: str,
        subscriber_id: str | None = None,
        **overrides: Any,
    ) -> dict[str, Any]:
        """Generate a synthetic webhook payload for the given event type.

        Args:
            event_type: One of the supported RC webhook event types.
            subscriber_id: Optional subscriber ID override.
            **overrides: Additional field overrides merged into the event body.

        Returns:
            A dict matching the RevenueCat webhook payload shape.
        """
        if event_type not in EVENT_TYPES:
            raise ValueError(
                f"Unknown event type: {event_type!r}. Must be one of {EVENT_TYPES}"
            )

        now_ms = int(time.time() * 1000)
        sub_id = subscriber_id or f"$RCAnonymousID:{uuid.uuid4().hex[:32]}"
        event_id = str(uuid.uuid4())
        product_id = "com.example.premium_monthly"
        txn_id = f"GPA.{uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:4]}"

        event_body: dict[str, Any] = {
            "id": event_id,
            "type": event_type,
            "app_id": f"app{uuid.uuid4().hex[:12]}",
            "event_timestamp_ms": now_ms,
            "product_id": product_id,
            "period_type": "NORMAL",
            "purchased_at_ms": now_ms - 86_400_000,
            "expiration_at_ms": now_ms + 30 * 86_400_000,
            "environment": "SANDBOX",
            "entitlement_ids": ["premium"],
            "presented_offering_id": "default_offering",
            "transaction_id": txn_id,
            "original_transaction_id": txn_id,
            "app_user_id": sub_id,
            "original_app_user_id": sub_id,
            "aliases": [sub_id],
            "country_code": "US",
            "currency": "USD",
            "price": 9.99,
            "price_in_purchased_currency": 9.99,
            "subscriber_attributes": {},
            "store": "PLAY_STORE",
        }

        # Add type-specific fields
        if event_type == "CANCELLATION":
            event_body["cancel_reason"] = "UNSUBSCRIBE"
        elif event_type == "BILLING_ISSUE":
            event_body["grace_period_expiration_at_ms"] = now_ms + 3 * 86_400_000
        elif event_type == "PRODUCT_CHANGE":
            event_body["new_product_id"] = "com.example.premium_annual"
        elif event_type == "TRANSFER":
            event_body["transferred_from"] = [f"$RCAnonymousID:{uuid.uuid4().hex[:32]}"]
            event_body["transferred_to"] = [sub_id]

        event_body.update(overrides)

        return {
            "api_version": "1.0",
            "event": event_body,
        }
