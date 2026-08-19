from __future__ import annotations

import argparse
import json

from .config import load_config
from .scanner import run_scan
from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="msm",
        description="Detect US equity market-structure changes and push them to desktop and phone.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve_p = sub.add_parser("serve", help="Open the live dashboard and scan in the background")
    serve_p.add_argument("--port", type=int, default=None)
    serve_p.add_argument("--bind", default=None)

    scan_p = sub.add_parser("scan", help="Run one scan (Task Scheduler / GitHub Actions)")
    scan_p.add_argument("--briefing", action="store_true", help="Force the daily briefing notification")
    scan_p.add_argument("--force-notify", action="store_true", help="Push every current signal, not only changes")
    scan_p.add_argument("--json", action="store_true", help="Print the snapshot as JSON")

    args = parser.parse_args()
    if args.cmd == "serve":
        serve(host=args.bind, port=args.port)
        return

    cfg = load_config()
    snap = run_scan(force_notify=args.force_notify, send_briefing=args.briefing, cfg=cfg)
    if args.json:
        print(json.dumps(snap, indent=2, default=str))
        return
    print(snap.get("briefing") or "")
    delivered = snap.get("delivered") or []
    fresh = snap.get("new_alerts") or []
    print()
    print(f"New structure changes: {len(fresh)}")
    for a in fresh:
        print(f"  [{a.get('severity')}] {a.get('title')}")
    if delivered:
        print(f"Notifications sent: {len(delivered)}")


if __name__ == "__main__":
    main()
