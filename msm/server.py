from __future__ import annotations

import copy
import json
import shutil
import socket
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .alerts import notify_all
from .config import WEB_DIR, load_config
from .scanner import current_view, run_scan
from .structure import Alert, is_rth, now_et

TAILSCALE_EXE_CANDIDATES = (
    Path(r"C:\Program Files\Tailscale\tailscale.exe"),
    Path(r"C:\Program Files (x86)\Tailscale\tailscale.exe"),
)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, cfg=None, **kwargs):
        self.cfg = cfg or load_config()
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            self._json(attach_access(current_view(self.cfg), self.cfg))
            return
        if path == "/api/health":
            self._json(
                {
                    "ok": True,
                    "rth": is_rth(),
                    "ts": now_et().isoformat(timespec="seconds"),
                    "access": access_urls(self.cfg),
                }
            )
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/scan":
            snap = run_scan(cfg=self.cfg)
            self._json({"ok": True, "ts": snap.get("ts"), "delivered": snap.get("delivered")})
            return
        if path == "/api/test-notify":
            topic = (self.cfg.get("alerts") or {}).get("ntfy_topic")
            alert = Alert(
                id="test",
                ts=now_et().isoformat(timespec="seconds"),
                severity="medium",
                title="Market Structure Monitor connected",
                body=f"Push alerts are working. Topic: {topic}",
                symbol="SYS",
                kind="test",
            )
            notify_all(self.cfg, [alert])
            self._json({"ok": True, "topic": topic})
            return
        self.send_error(404)

    def _json(self, payload) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def tailscale_exe() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    for path in TAILSCALE_EXE_CANDIDATES:
        if path.exists():
            return str(path)
    return None


def tailscale_status() -> dict:
    exe = tailscale_exe()
    if not exe:
        return {"installed": False, "state": "not_installed", "ip": None, "dns": None}
    try:
        raw = subprocess.check_output(
            [exe, "status", "--json"],
            timeout=8,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(raw)
    except Exception:
        return {"installed": True, "state": "offline", "ip": None, "dns": None}

    backend = str(data.get("BackendState") or "unknown")
    self_info = data.get("Self") or {}
    ips = self_info.get("TailscaleIPs") or data.get("TailscaleIPs") or []
    ip4 = next((i for i in ips if ":" not in i), None)
    dns = (self_info.get("DNSName") or "").rstrip(".")
    return {
        "installed": True,
        "state": backend.lower(),
        "ip": ip4,
        "dns": dns or None,
        "online": backend == "Running" and bool(ip4),
    }


def access_urls(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    port = int(cfg.get("port") or 8765)
    ts = tailscale_status()
    out = {
        "local": f"http://127.0.0.1:{port}",
        "lan": f"http://{lan_ip()}:{port}",
        "tailscale": f"http://{ts['ip']}:{port}" if ts.get("ip") else None,
        "tailscale_dns": f"http://{ts['dns']}:{port}" if ts.get("dns") else None,
        "tailscale_state": ts.get("state"),
        "tailscale_installed": bool(ts.get("installed")),
        "tailscale_online": bool(ts.get("online")),
    }
    return out


def attach_access(snap: dict, cfg: dict | None = None) -> dict:
    view = dict(snap)
    view["access"] = access_urls(cfg)
    return view


def desktop_alert_cfg(cfg: dict) -> dict:
    """Local dashboard: silent Windows toasts only. GitHub Actions owns ntfy."""
    out = copy.deepcopy(cfg)
    alerts = out.setdefault("alerts", {})
    alerts["ntfy"] = False
    alerts["telegram_bot_token"] = ""
    alerts["discord_webhook"] = ""
    alerts["windows_toast"] = True
    return out


def _loop(cfg: dict, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            run_scan(cfg=cfg)
        except Exception as exc:
            print(f"[scan] {exc}", flush=True)
        seconds = int(cfg.get("scan_seconds_rth" if is_rth() else "scan_seconds_off", 180))
        stop.wait(max(30, seconds))


def serve(host: str | None = None, port: int | None = None) -> None:
    cfg = load_config()
    host = host or cfg.get("bind") or "0.0.0.0"
    port = int(port or cfg.get("port") or 8765)
    WEB_DIR.mkdir(parents=True, exist_ok=True)

    desktop_cfg = desktop_alert_cfg(cfg)
    print("Seeding market structure snapshot…", flush=True)
    try:
        snap = run_scan(cfg=desktop_cfg)
        print(f"Seeded at {snap.get('ts_label')}", flush=True)
    except Exception as exc:
        print(f"Initial scan failed: {exc}", flush=True)

    stop = threading.Event()
    worker = threading.Thread(target=_loop, args=(desktop_cfg, stop), daemon=True)
    worker.start()

    httpd = ThreadingHTTPServer((host, port), partial(Handler, cfg=desktop_cfg))
    access = access_urls(cfg)
    topic = (cfg.get("alerts") or {}).get("ntfy_topic")
    ntfy = (cfg.get("alerts") or {}).get("ntfy_server") or "https://ntfy.sh"
    print("", flush=True)
    print("  Market Structure Monitor", flush=True)
    print(f"  Desktop:     {access['local']}", flush=True)
    print(f"  Same Wi-Fi:  {access['lan']}", flush=True)
    if access.get("tailscale"):
        print(f"  Phone/away:  {access['tailscale']}   (Tailscale)", flush=True)
        if access.get("tailscale_dns"):
            print(f"               {access['tailscale_dns']}", flush=True)
    elif access.get("tailscale_installed"):
        print("  Phone/away:  Tailscale installed but not logged in. Run: tailscale login", flush=True)
    else:
        print("  Phone/away:  Tailscale not installed", flush=True)
    print(f"  Phone push:  GitHub Actions → {ntfy}/{topic}", flush=True)
    print("  Desktop:     silent Windows toast on structure changes (this window)", flush=True)
    print("  Ctrl+C to stop.", flush=True)
    print("", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping…", flush=True)
    finally:
        stop.set()
        httpd.server_close()
