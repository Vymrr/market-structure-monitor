from __future__ import annotations

import json
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .alerts import notify_all
from .config import WEB_DIR, load_config
from .scanner import current_view, run_scan
from .structure import Alert, is_rth, now_et


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, cfg=None, **kwargs):
        self.cfg = cfg or load_config()
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            self._json(current_view(self.cfg))
            return
        if path == "/api/health":
            self._json({"ok": True, "rth": is_rth(), "ts": now_et().isoformat(timespec="seconds")})
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

    print("Seeding market structure snapshot…", flush=True)
    try:
        snap = run_scan(cfg=cfg)
        print(f"Seeded at {snap.get('ts_label')}", flush=True)
    except Exception as exc:
        print(f"Initial scan failed: {exc}", flush=True)

    stop = threading.Event()
    worker = threading.Thread(target=_loop, args=(cfg, stop), daemon=True)
    worker.start()

    httpd = ThreadingHTTPServer((host, port), partial(Handler, cfg=cfg))
    ip = lan_ip()
    topic = (cfg.get("alerts") or {}).get("ntfy_topic")
    server = (cfg.get("alerts") or {}).get("ntfy_server") or "https://ntfy.sh"
    print("", flush=True)
    print("  Market Structure Monitor", flush=True)
    print(f"  Desktop:  http://127.0.0.1:{port}", flush=True)
    print(f"  Phone:    http://{ip}:{port}   (same Wi-Fi)", flush=True)
    print(f"  Push:     {server}/{topic}", flush=True)
    print("            Install the free ntfy app and subscribe to that topic.", flush=True)
    print("  Ctrl+C to stop.", flush=True)
    print("", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping…", flush=True)
    finally:
        stop.set()
        httpd.server_close()
