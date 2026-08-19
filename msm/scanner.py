from __future__ import annotations

import threading
from typing import Any

from .alerts import notify_all
from .config import all_tickers, load_config
from .data import fetch_market
from .state import load_state, save_state
from .structure import Alert, analyze, now_et

_LOCK = threading.Lock()


def run_scan(
    force_notify: bool = False,
    send_briefing: bool = False,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with _LOCK:
        return _run_scan_locked(force_notify=force_notify, send_briefing=send_briefing, cfg=cfg)


def _run_scan_locked(
    force_notify: bool,
    send_briefing: bool,
    cfg: dict[str, Any] | None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    state = load_state()
    market = fetch_market(all_tickers(cfg), force=True)
    snapshot = analyze(cfg, market)
    candidates: list[Alert] = snapshot.pop("alerts_candidate", [])
    briefing = snapshot.get("briefing") or ""

    active = set(state.get("active_ids") or [])
    new_ids = {a.id for a in candidates}
    fresh = [a for a in candidates if a.id not in active]
    seeded = bool(state.get("seeded"))
    today = now_et().strftime("%Y-%m-%d")
    want_briefing = bool(send_briefing) or (seeded and state.get("briefing_date") != today)
    if not seeded:
        want_briefing = bool(send_briefing)

    notify_alerts: list[Alert] = []
    if not seeded and not force_notify:
        pass
    else:
        notify_alerts = list(candidates) if force_notify else fresh

    delivered: list[str] = []
    if notify_alerts or (want_briefing and briefing):
        delivered = notify_all(
            cfg,
            notify_alerts,
            briefing=briefing if want_briefing else None,
        )

    history = list(state.get("alerts") or [])
    for a in (notify_alerts if seeded or force_notify else []):
        history.append(a.to_dict())
    history = history[-200:]

    state.update(
        {
            "seeded": True,
            "active_ids": sorted(new_ids),
            "alerts": history,
            "snapshot": snapshot,
            "last_scan": snapshot.get("ts"),
            "briefing_date": today if (want_briefing or not seeded) else state.get("briefing_date"),
        }
    )
    save_state(state)

    snapshot["new_alerts"] = [a.to_dict() for a in (fresh if seeded else [])]
    snapshot["delivered"] = delivered
    snapshot["alert_history"] = history
    snapshot["ntfy_topic"] = (cfg.get("alerts") or {}).get("ntfy_topic")
    snapshot["ntfy_server"] = (cfg.get("alerts") or {}).get("ntfy_server") or "https://ntfy.sh"
    snapshot["seeded"] = True
    return snapshot


def current_view(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    state = load_state()
    snap = state.get("snapshot") or {}
    if not snap:
        return run_scan(cfg=cfg)
    snap = dict(snap)
    snap["new_alerts"] = []
    snap["delivered"] = []
    snap["alert_history"] = state.get("alerts") or []
    snap["ntfy_topic"] = (cfg.get("alerts") or {}).get("ntfy_topic")
    snap["ntfy_server"] = (cfg.get("alerts") or {}).get("ntfy_server") or "https://ntfy.sh"
    snap["last_scan"] = state.get("last_scan")
    snap["seeded"] = state.get("seeded")
    return snap
