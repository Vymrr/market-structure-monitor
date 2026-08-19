from __future__ import annotations

import time
from typing import Any

import pandas as pd
import yfinance as yf

_CACHE: dict[str, Any] = {"daily": None, "intraday": None, "ts": 0.0}
_TTL = 50.0


def _extract(raw: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    if raw is None or raw.empty:
        return None
    cols = raw.columns
    df: pd.DataFrame | None = None
    if isinstance(cols, pd.MultiIndex):
        level0 = set(cols.get_level_values(0))
        level1 = set(cols.get_level_values(1))
        if ticker in level0:
            df = raw[ticker].copy()
        elif ticker in level1:
            df = raw.xs(ticker, axis=1, level=1).copy()
        else:
            return None
    else:
        df = raw.copy()

    df.columns = [str(c).title() for c in df.columns]
    rename = {"Adj Close": "Close"}
    df = df.rename(columns=rename)
    needed = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in needed):
        return None
    df = df.dropna(subset=["Close"])
    if df.empty:
        return None
    if getattr(df.index, "tz", None) is not None:
        try:
            df.index = df.index.tz_convert("America/New_York")
        except Exception:
            df.index = df.index.tz_localize(None)
    return df


def _download(tickers: list[str], period: str, interval: str) -> dict[str, pd.DataFrame]:
    if not tickers:
        return {}
    raw = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        df = _extract(raw, t)
        if df is not None and len(df) >= 5:
            out[t] = df
    return out


def fetch_market(tickers: list[str], force: bool = False) -> dict[str, Any]:
    now = time.time()
    if (
        not force
        and _CACHE["daily"] is not None
        and now - _CACHE["ts"] < _TTL
    ):
        return {"daily": _CACHE["daily"], "intraday": _CACHE["intraday"]}

    daily = _download(tickers, period="2y", interval="1d")
    intra_syms = [t for t in ("SPY", "QQQ", "IWM", "DIA") if t in tickers]
    try:
        intraday = _download(intra_syms, period="5d", interval="15m") if intra_syms else {}
    except Exception:
        intraday = {}

    _CACHE["daily"] = daily
    _CACHE["intraday"] = intraday
    _CACHE["ts"] = now
    return {"daily": daily, "intraday": intraday}
