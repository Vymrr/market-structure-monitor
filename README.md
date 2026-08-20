# Market Structure Monitor

A free US-market structure detector. It watches the major indexes, sector breadth, VIX term structure, credit, and swing highs/lows, then **alerts you only when the structure actually changes**.

You can run it three ways:

1. **Cloud dashboard** — [https://vymrr.github.io/market-structure-monitor/](https://vymrr.github.io/market-structure-monitor/) (GitHub Pages, PC can be off)
2. **Phone push** — free [ntfy](https://ntfy.sh) from GitHub Actions
3. **Windows dashboard** — `run.bat` on this PC if you want Scan now / Tailscale

No paid data feed. Prices come from Yahoo Finance.

This is a monitoring tool, not trading advice.

## What it detects

| Signal | Why it matters |
| --- | --- |
| **Regime** on SPY / QQQ / IWM / DIA | Price vs 50- and 200-day averages (bull, correction, recovery, bear) |
| **Daily & weekly swing structure** | Higher-highs / higher-lows vs lower-highs / lower-lows |
| **CHoCH** | Close through the last swing against the prevailing trend (change of character) |
| **50 / 200 DMA breaks, golden & death crosses** | Classic trend-structure events |
| **VIX level + VIX/VIX3M term structure** | Contango vs backwardation (stress) |
| **Sector breadth** | How many of the 11 S&P sector ETFs sit above their 50 DMA |
| **RSP vs SPY, IWM vs SPY** | Equal-weight and small-cap confirmation or divergence |
| **HYG 50 DMA** | High-yield credit as a risk-appetite proxy |
| **Opening-range break + VWAP** | Intraday structure during the cash session |

The first scan **seeds a baseline and stays quiet**. After that you only get a ping when something flips, plus one daily briefing.

## Cloud dashboard (no PC required)

The live page is **https://vymrr.github.io/market-structure-monitor/**

GitHub Actions refreshes it about every 15 minutes on weekday US hours and writes a public snapshot (the ntfy topic is not published). Anyone with the link can see the tape; that is the cost of a free host.

## Quick start (Windows)

```powershell
cd $env:USERPROFILE\market-structure-monitor
python -m msm serve
```

Or double-click `run.bat`.

Then open:

- Desktop: [http://127.0.0.1:8765](http://127.0.0.1:8765)
- Phone on the same Wi-Fi: `http://YOUR-PC-LAN-IP:8765` (printed in the terminal)

If the phone page does not load, allow TCP port **8765** inbound in Windows Firewall for private networks.

### Push alerts to your phone

1. Install [ntfy](https://ntfy.sh) (Android / iOS / Windows).
2. Start the dashboard once. The terminal and the web page show a topic like `msm-a1b2c3d4e5f6`.
3. In ntfy, subscribe to that topic.

Public ntfy topics are not secret. The random name is enough for personal use. For anything sensitive, run your own ntfy server or set Telegram / Discord in `config.json`.

### Keep scanning while the dashboard is closed

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows-task.ps1
```

That registers a per-user task named `MarketStructureMonitor` every 15 minutes.

One-shot scan:

```powershell
python -m msm scan
python -m msm scan --briefing
```

## Optional channels

Edit `config.json` or set environment variables:

| Config / env | Purpose |
| --- | --- |
| `alerts.telegram_bot_token` + `alerts.telegram_chat_id` | Telegram bot |
| `alerts.discord_webhook` | Discord channel |
| `alerts.min_severity` | `info`, `medium`, `high`, or `critical` (default `medium`) |
| `MSM_NTFY_TOPIC` | Override the local random topic |
| `MSM_PORT` / `MSM_BIND` | Dashboard bind address |

## Free cloud (GitHub Actions)

1. Create a GitHub repo and push this folder.
2. Settings → Secrets and variables → Actions, add `MSM_NTFY_TOPIC` (use the same topic you subscribed to).
3. Optional secrets: `MSM_TELEGRAM_BOT_TOKEN`, `MSM_TELEGRAM_CHAT_ID`, `MSM_DISCORD_WEBHOOK`.
4. The workflow `.github/workflows/scan.yml` runs every 15 minutes on weekday US hours. You can also hit **Run workflow**.

GitHub’s cache holds the last snapshot so the cloud job still alerts on *changes*, not every tick.

## How to read the score

The 0–100 **structure score** is a weighted blend of SPY trend alignment, daily/weekly swing bias, sector breadth, small-cap and equal-weight confirmation, HYG, and VIX. It is a dashboard gauge, not a trade signal.

- **Constructive** (~70+): trend and internals mostly agree
- **Neutral** (~45–70): mixed or transitioning
- **Defensive** (<45): broken trend, weak breadth, or stress vol

## Project layout

```
msm/            detector, alerts, local web server
web/            dashboard
data/           local state (not for git)
config.json     watchlist, scan interval, alert channels
run.bat         start dashboard
scan.bat        one scan
```
