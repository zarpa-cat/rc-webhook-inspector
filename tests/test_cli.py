"""Tests for CLI commands."""

import json
from pathlib import Path

from typer.testing import CliRunner

from rc_webhook_inspector.cli import app
from rc_webhook_inspector.events import EventSynthesizer

runner = CliRunner()


class TestCli:
    def test_generate_single(self) -> None:
        result = runner.invoke(app, ["generate", "INITIAL_PURCHASE"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["event"]["type"] == "INITIAL_PURCHASE"

    def test_generate_all(self) -> None:
        result = runner.invoke(app, ["generate", "--all"])
        assert result.exit_code == 0
        # Each line should be valid JSON (rich formatting adds newlines)
        assert "INITIAL_PURCHASE" in result.output
        assert "RENEWAL" in result.output

    def test_generate_no_args(self) -> None:
        result = runner.invoke(app, ["generate"])
        assert result.exit_code == 1

    def test_generate_with_subscriber_id(self) -> None:
        result = runner.invoke(app, ["generate", "RENEWAL", "--subscriber-id", "test_user"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["event"]["app_user_id"] == "test_user"

    def test_store_record_and_get(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(event))

        result = runner.invoke(app, ["store", "record", str(event_file), "--db", db])
        assert result.exit_code == 0
        assert "Recorded" in result.output

    def test_store_list_empty(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        result = runner.invoke(app, ["store", "list", "--db", db])
        assert result.exit_code == 0
        assert "No events" in result.output

    def test_store_list_with_events(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        event = EventSynthesizer.generate("RENEWAL")
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(event))

        runner.invoke(app, ["store", "record", str(event_file), "--db", db])
        result = runner.invoke(app, ["store", "list", "--db", db])
        assert result.exit_code == 0
        assert "RENEWAL" in result.output

    def test_store_clear(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(EventSynthesizer.generate("RENEWAL")))
        runner.invoke(app, ["store", "record", str(event_file), "--db", db])

        result = runner.invoke(app, ["store", "clear", "--db", db])
        assert result.exit_code == 0
        assert "Cleared" in result.output

    def test_validate_valid(self, tmp_path: Path) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE")
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(event))

        result = runner.invoke(app, ["validate", str(event_file)])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_validate_invalid(self, tmp_path: Path) -> None:
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps({"bad": "payload"}))

        result = runner.invoke(app, ["validate", str(event_file)])
        assert result.exit_code == 1
        assert "Invalid" in result.output

    def test_inspect(self, tmp_path: Path) -> None:
        event = EventSynthesizer.generate("INITIAL_PURCHASE", subscriber_id="user_99")
        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(event))

        result = runner.invoke(app, ["inspect", str(event_file)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "INITIAL_PURCHASE"
        assert data["subscriber_id"] == "user_99"
