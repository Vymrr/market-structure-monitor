from __future__ import annotations

import json
import os
from typing import Any

from .config import WEB_DIR

DROP = {"ntfy_topic", "ntfy_server", "delivered", "new_alerts", "access"}


def public_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in snap.items() if k not in DROP}
    out["hosted"] = True
    out["source"] = "github-actions" if os.environ.get("GITHUB_ACTIONS") else "local"
    return out


def write_public_snapshot(snap: dict[str, Any]) -> None:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    path = WEB_DIR / "snapshot.json"
    payload = public_snapshot(snap)
    path.write_text(json.dumps(payload, default=str), encoding="utf-8")
