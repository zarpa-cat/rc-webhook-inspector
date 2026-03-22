"""Compare two RevenueCat webhook payloads and highlight field differences."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldDiff:
    """A single field difference between two payloads."""

    path: str
    left: Any
    right: Any
    kind: str  # "changed" | "added" | "removed"


@dataclass
class DiffResult:
    """Result of comparing two webhook payloads."""

    left_type: str | None
    right_type: str | None
    same_type: bool
    diffs: list[FieldDiff] = field(default_factory=list)

    @property
    def has_diffs(self) -> bool:
        return len(self.diffs) > 0

    @property
    def changed(self) -> list[FieldDiff]:
        return [d for d in self.diffs if d.kind == "changed"]

    @property
    def added(self) -> list[FieldDiff]:
        return [d for d in self.diffs if d.kind == "added"]

    @property
    def removed(self) -> list[FieldDiff]:
        return [d for d in self.diffs if d.kind == "removed"]


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict into dot-separated key paths."""
    items: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(_flatten(v, path))
            else:
                items[path] = v
    else:
        items[prefix] = obj
    return items


class PayloadDiffer:
    """Compare two webhook payloads."""

    @staticmethod
    def diff(left: dict[str, Any], right: dict[str, Any]) -> DiffResult:
        """Return a DiffResult comparing left and right payloads.

        - Fields in both but with different values → "changed"
        - Fields only in right → "added"
        - Fields only in left → "removed"
        """
        left_type = left.get("event", {}).get("type")
        right_type = right.get("event", {}).get("type")

        flat_left = _flatten(left)
        flat_right = _flatten(right)

        all_keys = set(flat_left) | set(flat_right)
        diffs: list[FieldDiff] = []

        for key in sorted(all_keys):
            in_left = key in flat_left
            in_right = key in flat_right

            if in_left and in_right:
                if flat_left[key] != flat_right[key]:
                    diffs.append(FieldDiff(
                        path=key, left=flat_left[key], right=flat_right[key], kind="changed"
                    ))
            elif in_right:
                diffs.append(FieldDiff(path=key, left=None, right=flat_right[key], kind="added"))
            else:
                diffs.append(FieldDiff(path=key, left=flat_left[key], right=None, kind="removed"))

        return DiffResult(
            left_type=left_type,
            right_type=right_type,
            same_type=left_type == right_type,
            diffs=diffs,
        )
