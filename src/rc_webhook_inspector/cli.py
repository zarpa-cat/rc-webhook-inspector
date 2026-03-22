"""CLI tool for rc-webhook-inspector."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from rc_webhook_inspector.differ import PayloadDiffer
from rc_webhook_inspector.events import EventSynthesizer
from rc_webhook_inspector.inspector import WebhookInspector
from rc_webhook_inspector.replayer import WebhookReplayer
from rc_webhook_inspector.signer import sign_payload, verify_payload
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
def replay(
    event_id: Annotated[str, typer.Argument(help="Event ID to replay")],
    endpoint: Annotated[str, typer.Argument(help="Target URL to POST to")],
    auth_key: Annotated[
        str | None,  # noqa: UP007
        typer.Option("--auth-key", help="Sign with HMAC key (attaches RC-Webhook-Signature)"),
    ] = None,
    db: Annotated[str, typer.Option("--db", help="Database path")] = DEFAULT_DB,
) -> None:
    """Replay a stored event to any HTTP endpoint."""
    store = WebhookStore(db)
    event = store.get(event_id)
    store.close()

    if event is None:
        console.print(f"[red]Error:[/red] Event {event_id!r} not found")
        raise typer.Exit(code=1)

    replayer = WebhookReplayer()
    result = replayer.replay(
        event_id=event_id,
        payload=event["payload"],
        endpoint=endpoint,
        auth_key=auth_key,
    )

    status_style = "green" if result.success else "red"
    console.print(
        f"[{status_style}]HTTP {result.status_code}[/{status_style}] "
        f"→ {endpoint} ({result.elapsed_ms}ms)"
    )

    if result.error:
        console.print(f"[red]Error:[/red] {result.error}")

    if result.response_body:
        console.print("[dim]Response:[/dim]")
        try:
            console.print_json(result.response_body)
        except Exception:  # noqa: BLE001
            console.print(result.response_body)

    if not result.success:
        raise typer.Exit(code=1)


@app.command()
def diff(
    left_source: Annotated[str, typer.Argument(help="Left payload: file path or - for stdin")],
    right_source: Annotated[str, typer.Argument(help="Right payload: file path")],
) -> None:
    """Compare two webhook payloads and show field differences."""
    left = _read_payload(left_source)
    right = _read_payload(right_source)

    result = PayloadDiffer.diff(left, right)

    if not result.same_type:
        console.print(
            f"[yellow]⚠ Type mismatch:[/yellow] {result.left_type!r} vs {result.right_type!r}"
        )
    else:
        console.print(f"[dim]Comparing two [{result.left_type}] payloads[/dim]")

    if not result.has_diffs:
        console.print("[green]✓ Identical[/green]")
        return

    table = Table(title="Payload Diff")
    table.add_column("Field", style="cyan")
    table.add_column("Kind", style="yellow")
    table.add_column("Left", style="red")
    table.add_column("Right", style="green")

    for d in result.diffs:
        table.add_row(d.path, d.kind, repr(d.left), repr(d.right))

    console.print(table)
    nc, na, nr = len(result.changed), len(result.added), len(result.removed)
    console.print(f"[dim]{nc} changed · {na} added · {nr} removed[/dim]")


@app.command()
def sign(
    key: Annotated[str, typer.Argument(help="HMAC key to sign with")],
    source: Annotated[
        str | None, typer.Argument(help="JSON file path or - for stdin")  # noqa: UP007
    ] = None,
    verify: Annotated[
        str | None,  # noqa: UP007
        typer.Option("--verify", help="Verify this signature instead of printing a new one"),
    ] = None,
) -> None:
    """Compute or verify the HMAC-SHA256 signature for a webhook payload."""
    payload = _read_payload(source)

    if verify is not None:
        ok = verify_payload(payload, key, verify)
        if ok:
            console.print("[green]✓ Signature valid[/green]")
        else:
            console.print("[red]✗ Signature invalid[/red]")
            raise typer.Exit(code=1)
    else:
        sig = sign_payload(payload, key)
        console.print(sig)


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
