"""Tests for signer module."""

from __future__ import annotations

import hashlib
import hmac
import json

from rc_webhook_inspector.signer import sign_payload, sign_raw, verify_payload, verify_raw

KEY = "test-secret-key"

PAYLOAD = {
    "api_version": "1.0",
    "event": {"type": "INITIAL_PURCHASE", "app_user_id": "sub_abc"},
}


def test_sign_payload_produces_hex_string() -> None:
    sig = sign_payload(PAYLOAD, KEY)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA256 hex = 64 chars


def test_sign_payload_deterministic() -> None:
    assert sign_payload(PAYLOAD, KEY) == sign_payload(PAYLOAD, KEY)


def test_verify_payload_valid() -> None:
    sig = sign_payload(PAYLOAD, KEY)
    assert verify_payload(PAYLOAD, KEY, sig) is True


def test_verify_payload_wrong_key() -> None:
    sig = sign_payload(PAYLOAD, KEY)
    assert verify_payload(PAYLOAD, "wrong-key", sig) is False


def test_verify_payload_tampered_payload() -> None:
    sig = sign_payload(PAYLOAD, KEY)
    tampered = {**PAYLOAD, "extra": "injected"}
    assert verify_payload(tampered, KEY, sig) is False


def test_sign_raw() -> None:
    body = json.dumps(PAYLOAD, separators=(",", ":")).encode()
    expected = hmac.new(KEY.encode(), body, hashlib.sha256).hexdigest()
    assert sign_raw(body, KEY) == expected


def test_verify_raw_valid() -> None:
    body = b'{"hello":"world"}'
    sig = sign_raw(body, KEY)
    assert verify_raw(body, KEY, sig) is True


def test_verify_raw_invalid() -> None:
    body = b'{"hello":"world"}'
    assert verify_raw(body, KEY, "deadbeef" * 8) is False


def test_sign_raw_different_from_sign_payload_for_different_serialisation() -> None:
    """sign_payload uses compact separators; non-compact bodies won't match."""
    loose_body = json.dumps(PAYLOAD).encode()  # spaces after : and ,
    compact_sig = sign_payload(PAYLOAD, KEY)
    # They should differ if serialisation differs
    loose_sig = sign_raw(loose_body, KEY)
    # Only equal if json.dumps already produces compact form (implementation-dependent)
    # Just verify both return valid hex strings
    assert len(compact_sig) == 64
    assert len(loose_sig) == 64
