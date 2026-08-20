from __future__ import annotations

import subprocess
import sys
from typing import Any

import requests

from .config import SEVERITY_RANK
from .structure import Alert

PRIORITY = {"info": "2", "medium": "3", "high": "4", "critical": "5"}


def _passes(alert: Alert, min_severity: str) -> bool:
    return SEVERITY_RANK.get(alert.severity, 0) >= SEVERITY_RANK.get(min_severity, 2)


def notify_all(cfg: dict[str, Any], alerts: list[Alert], briefing: str | None = None) -> list[str]:
    sent: list[str] = []
    min_sev = (cfg.get("alerts") or {}).get("min_severity", "medium")
    actionable = [a for a in alerts if _passes(a, min_sev)]
    if briefing:
        _dispatch(cfg, title="US market structure briefing", body=briefing, severity="info")
        sent.append("briefing")
    for a in actionable:
        _dispatch(cfg, title=a.title, body=a.body, severity=a.severity)
        sent.append(a.id)
    return sent


def _dispatch(cfg: dict[str, Any], title: str, body: str, severity: str) -> None:
    alerts_cfg = cfg.get("alerts") or {}
    if alerts_cfg.get("ntfy"):
        _ntfy(alerts_cfg, title, body, severity)
    if alerts_cfg.get("windows_toast") and sys.platform == "win32":
        _windows_toast(title, body)
    token = (alerts_cfg.get("telegram_bot_token") or "").strip()
    chat = (alerts_cfg.get("telegram_chat_id") or "").strip()
    if token and chat:
        _telegram(token, chat, title, body)
    hook = (alerts_cfg.get("discord_webhook") or "").strip()
    if hook:
        _discord(hook, title, body)


def _ntfy(alerts_cfg: dict[str, Any], title: str, body: str, severity: str) -> None:
    topic = (alerts_cfg.get("ntfy_topic") or "").strip()
    if not topic:
        return
    server = (alerts_cfg.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
    url = f"{server}/{topic}"
    try:
        requests.post(
            url,
            data=body.encode("utf-8"),
            headers={
                "Title": title[:120],
                "Priority": PRIORITY.get(severity, "3"),
                "Tags": "chart_with_upwards_trend",
            },
            timeout=12,
        )
    except Exception:
        pass


def _telegram(token: str, chat_id: str, title: str, body: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": f"{title}\n\n{body}"[:3900]},
            timeout=12,
        )
    except Exception:
        pass


def _discord(webhook: str, title: str, body: str) -> None:
    try:
        requests.post(webhook, json={"content": f"**{title}**\n{body}"[:1900]}, timeout=12)
    except Exception:
        pass


def _windows_toast(title: str, body: str) -> None:
    def esc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    xml = (
        '<toast duration="short">'
        "<visual><binding template='ToastGeneric'>"
        f"<text>{esc(title)[:80]}</text>"
        f"<text>{esc(body)[:140]}</text>"
        "</binding></visual>"
        '<audio silent="true"/>'
        "</toast>"
    )
    script = f"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml(@'
{xml}
'@)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
foreach ($appId in @('Market Structure Monitor', '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe')) {{
  try {{
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
    exit 0
  }} catch {{}}
}}
exit 1
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            timeout=8,
            capture_output=True,
            text=True,
        )
    except Exception:
        pass
