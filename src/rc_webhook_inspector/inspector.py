"""Validate and introspect RevenueCat webhook payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rc_webhook_inspector.events import EVENT_TYPES


@dataclass
class ValidationResult:
    """Result of webhook payload validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class WebhookInspector:
    """Validates and summarizes webhook payloads."""

    @staticmethod
    def validate(payload: dict[str, Any]) -> ValidationResult:
        """Validate a webhook payload.

        Checks:
        - event field is present
        - type is recognized
        - api_version is present
        - timestamps are valid (positive integers)
        """
        errors: list[str] = []
        warnings: list[str] = []

        if "event" not in payload:
            errors.append("Missing 'event' field in payload")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        event = payload["event"]

        if "type" not in event:
            errors.append("Missing 'type' field in event")
        elif event["type"] not in EVENT_TYPES:
            warnings.append(f"Unrecognized event type: {event['type']!r}")

        if "api_version" not in payload:
            errors.append("Missing 'api_version' field in payload")

        # Validate timestamps
        for ts_field in ["event_timestamp_ms", "purchased_at_ms", "expiration_at_ms"]:
            if ts_field in event:
                val = event[ts_field]
                if not isinstance(val, int | float) or val < 0:
                    errors.append(f"Invalid timestamp for '{ts_field}': {val}")

        if not errors:
            # Additional warnings
            if "product_id" not in event:
                warnings.append("Missing 'product_id' field in event")
            if "app_user_id" not in event:
                warnings.append("Missing 'app_user_id' field in event")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def summarize(payload: dict[str, Any]) -> dict[str, Any]:
        """Extract key fields from a webhook payload."""
        event = payload.get("event", {})
        return {
            "type": event.get("type"),
            "subscriber_id": event.get("app_user_id"),
            "product_id": event.get("product_id"),
            "timestamp_ms": event.get("event_timestamp_ms"),
            "environment": event.get("environment"),
            "store": event.get("store"),
            "transaction_id": event.get("transaction_id"),
            "price": event.get("price"),
            "currency": event.get("currency"),
            "country_code": event.get("country_code"),
        }
