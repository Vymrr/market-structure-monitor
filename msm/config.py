from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
CONFIG_PATH = ROOT / "config.json"
STATE_PATH = DATA_DIR / "state.json"
LOCAL_PATH = DATA_DIR / "local.json"

SEVERITY_RANK = {"info": 1, "medium": 2, "high": 3, "critical": 4}

DEFAULTS: dict[str, Any] = {
    "port": 8765,
    "bind": "0.0.0.0",
    "scan_seconds_rth": 180,
    "scan_seconds_off": 1800,
    "indices": ["SPY", "QQQ", "IWM", "DIA"],
    "sectors": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC"],
    "cross_asset": ["RSP", "TLT", "HYG", "LQD", "GLD", "UUP"],
    "vol": ["^VIX", "^VIX3M"],
    "rates": ["^TNX"],
    "swing_left": 5,
    "swing_right": 5,
    "alerts": {
        "windows_toast": True,
        "ntfy": True,
        "ntfy_server": "https://ntfy.sh",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "discord_webhook": "",
        "min_severity": "medium",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = _deep_merge(cfg, json.load(f))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    local: dict[str, Any] = {}
    if LOCAL_PATH.exists():
        with LOCAL_PATH.open(encoding="utf-8") as f:
            local = json.load(f)
    if not local.get("ntfy_topic"):
        local["ntfy_topic"] = "msm-" + secrets.token_hex(6)
        with LOCAL_PATH.open("w", encoding="utf-8") as f:
            json.dump(local, f, indent=2)

    alerts = cfg.setdefault("alerts", {})
    alerts["ntfy_topic"] = (
        os.environ.get("MSM_NTFY_TOPIC")
        or os.environ.get("NTFY_TOPIC")
        or local["ntfy_topic"]
    )
    if os.environ.get("MSM_NTFY_SERVER") or os.environ.get("NTFY_SERVER"):
        alerts["ntfy_server"] = os.environ.get("MSM_NTFY_SERVER") or os.environ["NTFY_SERVER"]
    if os.environ.get("MSM_TELEGRAM_BOT_TOKEN"):
        alerts["telegram_bot_token"] = os.environ["MSM_TELEGRAM_BOT_TOKEN"]
    if os.environ.get("MSM_TELEGRAM_CHAT_ID"):
        alerts["telegram_chat_id"] = os.environ["MSM_TELEGRAM_CHAT_ID"]
    if os.environ.get("MSM_DISCORD_WEBHOOK"):
        alerts["discord_webhook"] = os.environ["MSM_DISCORD_WEBHOOK"]
    if os.environ.get("MSM_MIN_SEVERITY"):
        alerts["min_severity"] = os.environ["MSM_MIN_SEVERITY"].lower()
    if os.environ.get("MSM_PORT"):
        cfg["port"] = int(os.environ["MSM_PORT"])
    if os.environ.get("MSM_BIND"):
        cfg["bind"] = os.environ["MSM_BIND"]
    cfg["_local"] = local
    return cfg


def all_tickers(cfg: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for key in ("indices", "sectors", "cross_asset", "vol", "rates"):
        for t in cfg.get(key, []):
            if t not in seen:
                seen.append(t)
    return seen
