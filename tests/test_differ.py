"""Tests for PayloadDiffer."""

from __future__ import annotations

from rc_webhook_inspector.differ import PayloadDiffer
from rc_webhook_inspector.events import EventSynthesizer


def _purchase() -> dict:
    return EventSynthesizer.generate("INITIAL_PURCHASE", subscriber_id="sub_test")


def test_identical_payloads_no_diffs() -> None:
    payload = _purchase()
    result = PayloadDiffer.diff(payload, payload)
    assert not result.has_diffs
    assert result.same_type


def test_changed_field() -> None:
    left = _purchase()
    right = _purchase()
    right["event"]["price"] = 9999.0

    result = PayloadDiffer.diff(left, right)
    assert result.has_diffs
    changed_paths = [d.path for d in result.changed]
    assert any("price" in p for p in changed_paths)


def test_added_field() -> None:
    left = _purchase()
    right = _purchase()
    right["event"]["custom_field"] = "hello"

    result = PayloadDiffer.diff(left, right)
    assert result.has_diffs
    added_paths = [d.path for d in result.added]
    assert any("custom_field" in p for p in added_paths)


def test_removed_field() -> None:
    left = _purchase()
    right = _purchase()
    left["event"]["extra_key"] = "present_only_in_left"

    result = PayloadDiffer.diff(left, right)
    assert result.has_diffs
    removed_paths = [d.path for d in result.removed]
    assert any("extra_key" in p for p in removed_paths)


def test_type_mismatch_flagged() -> None:
    left = EventSynthesizer.generate("INITIAL_PURCHASE")
    right = EventSynthesizer.generate("CANCELLATION")

    result = PayloadDiffer.diff(left, right)
    assert not result.same_type
    assert result.left_type == "INITIAL_PURCHASE"
    assert result.right_type == "CANCELLATION"


def test_same_type_flag() -> None:
    left = _purchase()
    right = _purchase()
    result = PayloadDiffer.diff(left, right)
    assert result.same_type


def test_diff_result_counts() -> None:
    left = {"event": {"type": "RENEWAL", "price": 9.99, "old_field": "bye"}}
    right = {"event": {"type": "RENEWAL", "price": 4.99, "new_field": "hi"}}
    result = PayloadDiffer.diff(left, right)
    assert len(result.changed) == 1
    assert len(result.added) == 1
    assert len(result.removed) == 1


def test_nested_diff() -> None:
    left = {"event": {"type": "RENEWAL", "nested": {"a": 1, "b": 2}}}
    right = {"event": {"type": "RENEWAL", "nested": {"a": 1, "b": 99}}}
    result = PayloadDiffer.diff(left, right)
    assert any("nested.b" in d.path for d in result.changed)
