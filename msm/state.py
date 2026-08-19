from __future__ import annotations

import json
from typing import Any

from .config import STATE_PATH


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {
            "seeded": False,
            "active_ids": [],
            "alerts": [],
            "snapshot": None,
            "briefing_date": None,
            "last_scan": None,
        }
    with STATE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)
    tmp.replace(STATE_PATH)
