"""Replay stored webhook events to any HTTP endpoint."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ReplayResult:
    """Result of a replay attempt."""

    event_id: str
    endpoint: str
    status_code: int
    success: bool
    response_body: str
    elapsed_ms: float
    error: str | None = None


class WebhookReplayer:
    """Fire stored events at any HTTP endpoint."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def sign(self, payload: dict[str, Any], key: str) -> str:
        """Compute HMAC-SHA256 signature for a payload."""
        body = json.dumps(payload, separators=(",", ":")).encode()
        return hmac.new(key.encode(), body, hashlib.sha256).hexdigest()

    def replay(
        self,
        event_id: str,
        payload: dict[str, Any],
        endpoint: str,
        auth_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> ReplayResult:
        """POST a stored event to the given endpoint.

        Args:
            event_id: The event's ID (for reporting).
            payload: The event payload dict to POST.
            endpoint: Full URL to POST to.
            auth_key: If provided, sign the payload and attach RC-Webhook-Signature header.
            extra_headers: Additional HTTP headers to include.
        """
        body = json.dumps(payload, separators=(",", ":")).encode()
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if auth_key is not None:
            sig = hmac.new(auth_key.encode(), body, hashlib.sha256).hexdigest()
            headers["RC-Webhook-Signature"] = sig

        if extra_headers:
            headers.update(extra_headers)

        start = time.monotonic()
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(endpoint, content=body, headers=headers)
            elapsed_ms = (time.monotonic() - start) * 1000
            return ReplayResult(
                event_id=event_id,
                endpoint=endpoint,
                status_code=resp.status_code,
                success=200 <= resp.status_code < 300,
                response_body=resp.text[:2000],
                elapsed_ms=round(elapsed_ms, 2),
            )
        except httpx.TimeoutException as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            return ReplayResult(
                event_id=event_id,
                endpoint=endpoint,
                status_code=0,
                success=False,
                response_body="",
                elapsed_ms=round(elapsed_ms, 2),
                error=f"Timeout: {exc}",
            )
        except httpx.RequestError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            return ReplayResult(
                event_id=event_id,
                endpoint=endpoint,
                status_code=0,
                success=False,
                response_body="",
                elapsed_ms=round(elapsed_ms, 2),
                error=f"Request error: {exc}",
            )
