"""HMAC-SHA256 signing helper for RevenueCat webhook payloads."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def sign_payload(payload: dict[str, Any], key: str) -> str:
    """Compute the HMAC-SHA256 signature RC expects.

    RevenueCat signs the raw request body with HMAC-SHA256 using the
    webhook auth key and includes it in the RC-Webhook-Signature header.

    This helper computes that signature from a dict, using the same
    compact JSON serialisation as the replayer.

    Args:
        payload: The webhook payload dict.
        key: The webhook auth key (from RC dashboard).

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    body = json.dumps(payload, separators=(",", ":")).encode()
    return hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


def verify_payload(payload: dict[str, Any], key: str, signature: str) -> bool:
    """Verify a signature against a payload and key.

    Args:
        payload: The webhook payload dict.
        key: The webhook auth key.
        signature: The signature to verify (from RC-Webhook-Signature header).

    Returns:
        True if the signature matches, False otherwise.
    """
    expected = sign_payload(payload, key)
    return hmac.compare_digest(expected, signature)


def sign_raw(body: bytes, key: str) -> str:
    """Compute HMAC-SHA256 for a raw body (bytes).

    Use this when you have the raw request body (not a parsed dict).

    Args:
        body: Raw request body bytes.
        key: The webhook auth key.

    Returns:
        Hex-encoded HMAC-SHA256 digest.
    """
    return hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


def verify_raw(body: bytes, key: str, signature: str) -> bool:
    """Verify a signature against raw body bytes.

    Args:
        body: Raw request body bytes.
        key: The webhook auth key.
        signature: The signature to verify.

    Returns:
        True if the signature matches, False otherwise.
    """
    expected = sign_raw(body, key)
    return hmac.compare_digest(expected, signature)
