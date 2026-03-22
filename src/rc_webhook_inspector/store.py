"""SQLite-backed store for recording and replaying webhook events."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


class WebhookStore:
    """Persist and query webhook events in SQLite."""

    def __init__(self, db_path: str | Path = "webhooks.db") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'synthetic',
                payload TEXT NOT NULL,
                created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        """)
        self._conn.commit()

    def record(self, event: dict[str, Any], source: str = "synthetic") -> str:
        """Save an event and return its event_id."""
        event_id = str(uuid.uuid4())
        event_type = event.get("event", {}).get("type", "UNKNOWN")
        self._conn.execute(
            "INSERT INTO events (event_id, event_type, source, payload) VALUES (?, ?, ?, ?)",
            (event_id, event_type, source, json.dumps(event)),
        )
        self._conn.commit()
        return event_id

    def get(self, event_id: str) -> dict[str, Any] | None:
        """Retrieve a single event by ID."""
        row = self._conn.execute(
            "SELECT * FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "source": row["source"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        }

    def list(
        self,
        limit: int = 50,
        event_type: str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """List stored events with optional filters."""
        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)
        if source is not None:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [
            {
                "event_id": r["event_id"],
                "event_type": r["event_type"],
                "source": r["source"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def clear(self) -> int:
        """Purge all events, return count deleted."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        self._conn.execute("DELETE FROM events")
        self._conn.commit()
        return count

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
