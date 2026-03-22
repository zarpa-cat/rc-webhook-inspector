"""FastAPI webhook receiver server."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from rc_webhook_inspector.inspector import WebhookInspector
from rc_webhook_inspector.store import WebhookStore

app = FastAPI(title="RC Webhook Inspector")

_store: WebhookStore | None = None
_auth_key: str | None = None


def get_store() -> WebhookStore:
    """Get the global webhook store instance."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = WebhookStore()
    return _store


def configure(db_path: str = "webhooks.db", auth_key: str | None = None) -> None:
    """Configure the receiver with a store and optional auth key."""
    global _store, _auth_key  # noqa: PLW0603
    _store = WebhookStore(db_path)
    _auth_key = auth_key


def _verify_signature(body: bytes, signature: str, key: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    rc_webhook_signature: str | None = Header(None, alias="RC-Webhook-Signature"),
) -> JSONResponse:
    """Receive and store a webhook event."""
    body = await request.body()

    if _auth_key is not None:
        if rc_webhook_signature is None:
            raise HTTPException(status_code=401, detail="Missing RC-Webhook-Signature header")
        if not _verify_signature(body, rc_webhook_signature, _auth_key):
            raise HTTPException(status_code=401, detail="Invalid signature")

    import json

    try:
        payload: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    store = get_store()
    event_id = store.record(payload, source="webhook")
    validation = WebhookInspector.validate(payload)

    return JSONResponse(
        status_code=200,
        content={
            "event_id": event_id,
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
        },
    )


@app.get("/events")
async def list_events(
    limit: int = 50,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    """List recent stored events."""
    store = get_store()
    return store.list(limit=limit, event_type=event_type)


@app.get("/events/{event_id}")
async def get_event(event_id: str) -> dict[str, Any]:
    """Get a specific stored event."""
    store = get_store()
    event = store.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
