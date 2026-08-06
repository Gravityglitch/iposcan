"""Tracks which IPOs have already triggered an alert, to avoid re-alerting."""
from __future__ import annotations

import json
from pathlib import Path


def load_alerted(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text())
    return set(data.get("alerted", []))


def save_alerted(path: Path, alerted: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"alerted": sorted(alerted)}, indent=2) + "\n")
