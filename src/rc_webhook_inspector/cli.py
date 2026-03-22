"""CLI tool for rc-webhook-inspector."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from rc_webhook_inspector.events import EventSynthesizer
from rc_webhook_inspector.inspector import WebhookInspector
from rc_webhook_inspector.store import WebhookStore

app = typer.Typer(name="rcwi", help="RevenueCat Webhook Inspector")
store_app = typer.Typer(name="store", help="Webhook event store commands")
app.add_typer(store_app, name="store")

console = Console()

DEFAULT_DB = "webhooks.db"


def _read_payload(source: str | None = None) -> dict:  # noqa: UP007
    """Read a JSON payload from a file path or stdin."""
    if source is None or source == "-":
        data = sys.stdin.read()
    else:
        data = Path(source).read_text()
    return json.loads(data)


@app.command()
def generate(
    event_type: Annotated[
        str | None, typer.Argument(help="Event type to generate")  # noqa: UP007
    ] = None,
    all_types: Annotated[bool, typer.Option("--all", help="Generate all event types")] = False,
    subscriber_id: Annotated[
        str | None, typer.Option("--subscriber-id", help="Subscriber ID")  # noqa: UP007
    ] = None,
) -> None:
    """Generate synthetic RevenueCat webhook events."""
    if all_types:
        for et in EventSynthesizer.all_types():
            event = EventSynthesizer.generate(et, subscriber_id=subscriber_id)
            console.print_json(json.dumps(event))
    elif event_type is not None:
        event = EventSynthesizer.generate(event_type, subscriber_id=subscriber_id)
        console.print_json(json.dumps(event))
    else:
        console.print("[red]Error:[/red] Provide an event type or use --all")
        raise typer.Exit(code=1)


@store_app.command("record")
def store_record(
    source: Annotated[
        str | None, typer.Argument(help="JSON file path or - for stdin")  # noqa: UP007
    ] = None,
    db: Annotated[str, typer.Option("--db", help="Database path")] = DEFAULT_DB,
) -> None:
    """Record a webhook event to the store."""
    payload = _read_payload(source)
    store = WebhookStore(db)
    event_id = store.record(payload)
    console.print(f"[green]Recorded[/green] event_id={event_id}")
    store.close()


@store_app.command("list")
def store_list(
    event_type: Annotated[
        str | None, typer.Option("--type", help="Filter by event type")  # noqa: UP007
    ] = None,
    limit: Annotated[int, typer.Option("--limit", help="Max events to list")] = 50,
    db: Annotated[str, typer.Option("--db", help="Database path")] = DEFAULT_DB,
) -> None:
    """List stored events."""
    store = WebhookStore(db)
    events = store.list(limit=limit, event_type=event_type)
    store.close()

    if not events:
        console.print("[dim]No events found.[/dim]")
        return

    table = Table(title="Stored Events")
    table.add_column("Event ID", style="cyan", max_width=36)
    table.add_column("Type", style="green")
    table.add_column("Source", style="yellow")

    for ev in events:
        table.add_row(ev["event_id"], ev["event_type"], ev["source"])

    console.print(table)


@store_app.command("get")
def store_get(
    event_id: Annotated[str, typer.Argument(help="Event ID to retrieve")],
    db: Annotated[str, typer.Option("--db", help="Database path")] = DEFAULT_DB,
) -> None:
    """Get a stored event as JSON."""
    store = WebhookStore(db)
    event = store.get(event_id)
    store.close()

    if event is None:
        console.print(f"[red]Error:[/red] Event {event_id} not found")
        raise typer.Exit(code=1)

    console.print_json(json.dumps(event["payload"]))


@store_app.command("clear")
def store_clear(
    db: Annotated[str, typer.Option("--db", help="Database path")] = DEFAULT_DB,
) -> None:
    """Purge all stored events."""
    store = WebhookStore(db)
    count = store.clear()
    store.close()
    console.print(f"[yellow]Cleared[/yellow] {count} event(s)")


@app.command()
def validate(
    source: Annotated[
        str | None, typer.Argument(help="JSON file path or - for stdin")  # noqa: UP007
    ] = None,
) -> None:
    """Validate a webhook payload."""
    payload = _read_payload(source)
    result = WebhookInspector.validate(payload)

    if result.valid:
        console.print("[green]✓ Valid[/green]")
    else:
        console.print("[red]✗ Invalid[/red]")

    for error in result.errors:
        console.print(f"  [red]ERROR:[/red] {error}")
    for warning in result.warnings:
        console.print(f"  [yellow]WARN:[/yellow] {warning}")

    if not result.valid:
        raise typer.Exit(code=1)


@app.command()
def inspect(
    source: Annotated[
        str | None, typer.Argument(help="JSON file path or - for stdin")  # noqa: UP007
    ] = None,
) -> None:
    """Summarize key fields from a webhook payload."""
    payload = _read_payload(source)
    summary = WebhookInspector.summarize(payload)
    console.print_json(json.dumps(summary))


@app.command()
def serve(
    port: Annotated[int, typer.Option("--port", help="Port to listen on")] = 8080,
    auth_key: Annotated[
        str | None,  # noqa: UP007
        typer.Option("--auth-key", help="HMAC auth key for signature verification"),
    ] = None,
    db: Annotated[str, typer.Option("--db", help="Database path")] = DEFAULT_DB,
) -> None:
    """Start the webhook receiver server."""
    import uvicorn

    from rc_webhook_inspector.receiver import configure

    configure(db_path=db, auth_key=auth_key)
    console.print(f"[green]Starting server on port {port}[/green]")
    uvicorn.run("rc_webhook_inspector.receiver:app", host="0.0.0.0", port=port)
