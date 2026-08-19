from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")

SECTOR_NAMES = {
    "XLK": "Tech",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Health",
    "XLY": "Discretionary",
    "XLP": "Staples",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Comm Svcs",
}


@dataclass
class Alert:
    id: str
    ts: str
    severity: str
    title: str
    body: str
    symbol: str
    kind: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def now_et() -> datetime:
    return datetime.now(ET)


def is_rth(dt: datetime | None = None) -> bool:
    dt = dt or now_et()
    if dt.weekday() >= 5:
        return False
    open_t = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = dt.replace(hour=16, minute=5, second=0, microsecond=0)
    return open_t <= dt <= close_t


def _sma(close: pd.Series, n: int) -> float | None:
    if len(close) < n:
        return None
    v = float(close.rolling(n).mean().iloc[-1])
    return None if np.isnan(v) else v


def _pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b * 100.0


def _last_change(close: pd.Series) -> tuple[float, float]:
    px = float(close.iloc[-1])
    if len(close) < 2:
        return px, 0.0
    prev = float(close.iloc[-2])
    return px, _pct(px, prev)


def classify_regime(close: pd.Series) -> str:
    s50 = _sma(close, 50)
    s200 = _sma(close, 200)
    if s50 is None or s200 is None:
        return "insufficient"
    c = float(close.iloc[-1])
    above50 = c > s50
    above200 = c > s200
    stacked_bull = s50 > s200
    stacked_bear = s50 < s200
    if above50 and above200 and stacked_bull:
        return "bull"
    if (not above50) and (not above200) and stacked_bear:
        return "bear"
    if (not above50) and above200:
        return "correction"
    if above50 and (not above200):
        return "recovery"
    return "range"


def _cross_today(a: pd.Series, b: pd.Series) -> str | None:
    if len(a) < 2 or len(b) < 2:
        return None
    prev = float(a.iloc[-2] - b.iloc[-2])
    cur = float(a.iloc[-1] - b.iloc[-1])
    if np.isnan(prev) or np.isnan(cur):
        return None
    if prev <= 0 < cur:
        return "bullish"
    if prev >= 0 > cur:
        return "bearish"
    return None


def find_swings(high: pd.Series, low: pd.Series, left: int = 5, right: int = 5) -> list[tuple[str, int, Any, float]]:
    h = high.to_numpy(dtype=float)
    l = low.to_numpy(dtype=float)
    idx = high.index
    n = len(h)
    raw: list[tuple[str, int, Any, float]] = []
    if n < left + right + 3:
        return []
    end = n - right
    for i in range(left, end):
        window_h = h[i - left : i + right + 1]
        window_l = l[i - left : i + right + 1]
        if h[i] >= np.nanmax(window_h):
            raw.append(("H", i, idx[i], float(h[i])))
        if l[i] <= np.nanmin(window_l):
            raw.append(("L", i, idx[i], float(l[i])))
    raw.sort(key=lambda x: x[1])
    cleaned: list[tuple[str, int, Any, float]] = []
    for e in raw:
        if not cleaned:
            cleaned.append(e)
            continue
        prev = cleaned[-1]
        if e[0] == prev[0]:
            if e[0] == "H" and e[3] >= prev[3]:
                cleaned[-1] = e
            elif e[0] == "L" and e[3] <= prev[3]:
                cleaned[-1] = e
        else:
            cleaned.append(e)
    return cleaned


def swing_bias(swings: list[tuple[str, int, Any, float]]) -> str:
    highs = [s for s in swings if s[0] == "H"]
    lows = [s for s in swings if s[0] == "L"]
    if len(highs) < 2 or len(lows) < 2:
        return "range"
    hh = highs[-1][3] > highs[-2][3]
    hl = lows[-1][3] > lows[-2][3]
    lh = highs[-1][3] < highs[-2][3]
    ll = lows[-1][3] < lows[-2][3]
    if hh and hl:
        return "uptrend"
    if lh and ll:
        return "downtrend"
    return "range"


def last_of(swings: list[tuple[str, int, Any, float]], kind: str) -> float | None:
    for s in reversed(swings):
        if s[0] == kind:
            return s[3]
    return None


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c: df[c] for c in ("Open", "High", "Low", "Close") if c in df.columns}
    frame = pd.DataFrame(cols)
    if "Volume" in df.columns:
        frame["Volume"] = df["Volume"]
    idx = frame.index
    if getattr(idx, "tz", None) is not None:
        frame = frame.copy()
        frame.index = idx.tz_localize(None) if idx.tz is None else idx.tz_convert("America/New_York").tz_localize(None)
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in frame.columns:
        agg["Volume"] = "sum"
    weekly = frame.resample("W-FRI").agg(agg).dropna(subset=["Close"])
    return weekly


def vix_bucket(level: float) -> str:
    if level < 12:
        return "very_low"
    if level < 16:
        return "calm"
    if level < 20:
        return "normal"
    if level < 25:
        return "elevated"
    if level < 32:
        return "high"
    return "crisis"


def breadth_bucket(n_above: int, n_total: int) -> str:
    if n_total <= 0:
        return "unknown"
    pct = n_above / n_total
    if pct >= 0.73:
        return "risk_on"
    if pct <= 0.27:
        return "risk_off"
    return "mixed"


def opening_range(intraday: pd.DataFrame) -> dict[str, Any] | None:
    if intraday is None or intraday.empty:
        return None
    idx = intraday.index
    if getattr(idx, "tz", None) is None:
        try:
            localized = idx.tz_localize("America/New_York", ambiguous="infer", nonexistent="shift_forward")
            frame = intraday.copy()
            frame.index = localized
        except Exception:
            return None
    else:
        frame = intraday.copy()
        frame.index = idx.tz_convert("America/New_York")

    today = now_et().date()
    day = frame[frame.index.date == today]
    if day.empty:
        last_day = frame.index[-1].date()
        day = frame[frame.index.date == last_day]
        today = last_day
    if day.empty:
        return None
    or_window = day.between_time("09:30", "09:59")
    if or_window.empty:
        or_window = day.iloc[:2]
    if or_window.empty:
        return None
    orh = float(or_window["High"].max())
    orl = float(or_window["Low"].min())
    last = float(day["Close"].iloc[-1])
    status = "inside"
    if last > orh:
        status = "break_up"
    elif last < orl:
        status = "break_down"
    vwap_num = (day["Close"] * day.get("Volume", pd.Series(1, index=day.index))).sum()
    vwap_den = float(day["Volume"].sum()) if "Volume" in day.columns else float(len(day))
    vwap = float(vwap_num / vwap_den) if vwap_den else last
    vs_vwap = "above" if last >= vwap else "below"
    return {
        "date": str(today),
        "orh": orh,
        "orl": orl,
        "last": last,
        "status": status,
        "vwap": vwap,
        "vs_vwap": vs_vwap,
    }


def _instrument(symbol: str, df: pd.DataFrame, left: int, right: int) -> dict[str, Any]:
    close, high, low = df["Close"], df["High"], df["Low"]
    px, chg = _last_change(close)
    s20, s50, s200 = _sma(close, 20), _sma(close, 50), _sma(close, 200)
    sma50_s = close.rolling(50).mean()
    sma200_s = close.rolling(200).mean()
    regime = classify_regime(close)
    cross_50_200 = _cross_today(sma50_s, sma200_s)
    vs50 = _pct(px, s50) if s50 else None
    vs200 = _pct(px, s200) if s200 else None

    prev_close = float(close.iloc[-2]) if len(close) > 1 else px
    dma50_cross = None
    dma200_cross = None
    if s50 is not None and len(close) > 51:
        s50_prev = float(sma50_s.iloc[-2])
        if prev_close <= s50_prev < px or prev_close < s50 <= px:
            dma50_cross = "above"
        elif prev_close >= s50_prev > px or prev_close > s50 >= px:
            dma50_cross = "below"
    if s200 is not None and len(close) > 201:
        s200_prev = float(sma200_s.iloc[-2])
        if prev_close <= s200_prev < px or prev_close < s200 <= px:
            dma200_cross = "above"
        elif prev_close >= s200_prev > px or prev_close > s200 >= px:
            dma200_cross = "below"

    swings = find_swings(high, low, left=left, right=right)
    daily_struct = swing_bias(swings)
    lsh = last_of(swings, "H")
    lsl = last_of(swings, "L")

    weekly_struct = "insufficient"
    try:
        w = to_weekly(df)
        if len(w) >= 20:
            wsw = find_swings(w["High"], w["Low"], left=3, right=3)
            weekly_struct = swing_bias(wsw)
    except Exception:
        weekly_struct = "insufficient"

    high20 = float(high.tail(20).max())
    low20 = float(low.tail(20).min())
    spark = [round(float(x), 4) for x in close.tail(60).tolist()]

    ma_stack = "mixed"
    if s20 and s50 and s200:
        if px > s20 > s50 > s200:
            ma_stack = "bull_aligned"
        elif px < s20 < s50 < s200:
            ma_stack = "bear_aligned"

    atr = None
    if len(df) >= 15:
        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])

    return {
        "symbol": symbol,
        "price": round(px, 4),
        "change_pct": round(chg, 3),
        "sma20": round(s20, 4) if s20 else None,
        "sma50": round(s50, 4) if s50 else None,
        "sma200": round(s200, 4) if s200 else None,
        "vs50_pct": round(vs50, 3) if vs50 is not None else None,
        "vs200_pct": round(vs200, 3) if vs200 is not None else None,
        "regime": regime,
        "ma_stack": ma_stack,
        "cross_50_200": cross_50_200,
        "dma50_cross": dma50_cross,
        "dma200_cross": dma200_cross,
        "daily_structure": daily_struct,
        "weekly_structure": weekly_struct,
        "last_swing_high": round(lsh, 4) if lsh else None,
        "last_swing_low": round(lsl, 4) if lsl else None,
        "high20": round(high20, 4),
        "low20": round(low20, 4),
        "dist_20d_high_pct": round(_pct(px, high20), 3),
        "atr": round(atr, 4) if atr and not np.isnan(atr) else None,
        "spark": spark,
        "bars": int(len(df)),
    }


def analyze(cfg: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    daily: dict[str, pd.DataFrame] = market["daily"]
    intraday: dict[str, pd.DataFrame] = market.get("intraday") or {}
    left = int(cfg.get("swing_left", 5))
    right = int(cfg.get("swing_right", 5))

    instruments: dict[str, dict[str, Any]] = {}
    for sym, df in daily.items():
        try:
            instruments[sym] = _instrument(sym, df, left, right)
        except Exception as exc:
            instruments[sym] = {"symbol": sym, "error": str(exc), "regime": "error"}

    sectors = []
    above50 = 0
    for sym in cfg.get("sectors", []):
        inst = instruments.get(sym)
        if not inst or inst.get("sma50") is None:
            continue
        over = inst["price"] > inst["sma50"]
        if over:
            above50 += 1
        sectors.append(
            {
                "symbol": sym,
                "name": SECTOR_NAMES.get(sym, sym),
                "price": inst["price"],
                "change_pct": inst.get("change_pct"),
                "regime": inst.get("regime"),
                "above50": over,
                "vs50_pct": inst.get("vs50_pct"),
            }
        )

    vix = instruments.get("^VIX") or {}
    vix3m = instruments.get("^VIX3M") or {}
    vix_px = vix.get("price")
    vix3m_px = vix3m.get("price")
    term = None
    term_state = None
    if vix_px and vix3m_px and vix3m_px != 0:
        term = round(vix_px / vix3m_px, 4)
        term_state = "backwardation" if term >= 1.0 else "contango"

    def rel_20d(a: str, b: str) -> float | None:
        if a not in daily or b not in daily:
            return None
        ca, cb = daily[a]["Close"], daily[b]["Close"]
        joined = pd.concat([ca, cb], axis=1, join="inner").dropna()
        if len(joined) < 21:
            return None
        ra = float(joined.iloc[-1, 0] / joined.iloc[-21, 0] - 1) * 100
        rb = float(joined.iloc[-1, 1] / joined.iloc[-21, 1] - 1) * 100
        return round(ra - rb, 3)

    internals = {
        "sectors_above_50": above50,
        "sectors_total": len(sectors),
        "breadth_bucket": breadth_bucket(above50, len(sectors) or 0),
        "rsp_vs_spy_20d": rel_20d("RSP", "SPY"),
        "iwm_vs_spy_20d": rel_20d("IWM", "SPY"),
        "qqq_vs_spy_20d": rel_20d("QQQ", "SPY"),
        "hyg_vs_tlt_20d": rel_20d("HYG", "TLT"),
    }

    score = _structure_score(instruments, internals, vix_px)
    opening = {sym: opening_range(df) for sym, df in intraday.items()}
    opening = {k: v for k, v in opening.items() if v}

    ts = now_et()
    snapshot = {
        "ts": ts.isoformat(timespec="seconds"),
        "ts_label": ts.strftime("%a %b %d %H:%M ET"),
        "rth": is_rth(ts),
        "indices": [instruments[s] for s in cfg.get("indices", []) if s in instruments],
        "instruments": instruments,
        "sectors": sectors,
        "internals": internals,
        "volatility": {
            "vix": vix_px,
            "vix_change_pct": vix.get("change_pct"),
            "vix_bucket": vix_bucket(vix_px) if vix_px else None,
            "vix3m": vix3m_px,
            "term_ratio": term,
            "term_state": term_state,
        },
        "cross_asset": [instruments[s] for s in cfg.get("cross_asset", []) if s in instruments],
        "rates": instruments.get("^TNX"),
        "opening": opening,
        "score": score,
    }
    snapshot["alerts_candidate"] = build_alerts(snapshot)
    snapshot["briefing"] = build_briefing(snapshot)
    return snapshot


def _structure_score(instruments: dict, internals: dict, vix_px: float | None) -> dict[str, Any]:
    pts = 0.0
    max_pts = 0.0

    def add(ok: bool | None, weight: float) -> None:
        nonlocal pts, max_pts
        max_pts += weight
        if ok:
            pts += weight

    spy = instruments.get("SPY") or {}
    add(spy.get("regime") == "bull", 18)
    add(spy.get("regime") in ("bull", "recovery"), 8)
    add(bool(spy.get("sma50") and spy.get("price", 0) > spy["sma50"]), 12)
    add(bool(spy.get("sma200") and spy.get("price", 0) > spy["sma200"]), 14)
    add(spy.get("daily_structure") == "uptrend", 10)
    add(spy.get("weekly_structure") == "uptrend", 8)

    b = internals.get("breadth_bucket")
    add(b == "risk_on", 12)
    add(b == "mixed", 4)

    iwm = internals.get("iwm_vs_spy_20d")
    add(iwm is not None and iwm > 0, 6)
    rsp = internals.get("rsp_vs_spy_20d")
    add(rsp is not None and rsp > 0, 6)

    hyg = instruments.get("HYG") or {}
    add(bool(hyg.get("sma50") and hyg.get("price", 0) > hyg["sma50"]), 8)

    if vix_px is not None:
        add(vix_px < 20, 8)
        add(vix_px < 16, 4)

    score = round(100 * pts / max_pts, 1) if max_pts else None
    if score is None:
        label = "n/a"
    elif score >= 70:
        label = "constructive"
    elif score >= 45:
        label = "neutral"
    else:
        label = "defensive"
    return {"value": score, "label": label}


def build_alerts(snap: dict[str, Any]) -> list[Alert]:
    ts = snap["ts"]
    alerts: list[Alert] = []

    def emit(severity: str, symbol: str, kind: str, title: str, body: str, key: str | None = None) -> None:
        aid = key or f"{symbol}:{kind}"
        alerts.append(Alert(id=aid, ts=ts, severity=severity, title=title, body=body, symbol=symbol, kind=kind))

    for inst in snap.get("indices", []):
        sym = inst["symbol"]
        emit(
            "high",
            sym,
            "regime",
            f"{sym} regime → {inst['regime'].replace('_', ' ').upper()}",
            f"{sym} is in a {inst['regime']} regime at {inst['price']:.2f} "
            f"({inst['change_pct']:+.2f}%). Daily swing structure: {inst['daily_structure']}; "
            f"weekly: {inst['weekly_structure']}.",
            key=f"{sym}:regime:{inst['regime']}",
        )
        emit(
            "medium",
            sym,
            "daily_structure",
            f"{sym} daily structure → {inst['daily_structure']}",
            f"Swing sequence on {sym} is now {inst['daily_structure']}. "
            f"Last swing high {inst.get('last_swing_high')}, last swing low {inst.get('last_swing_low')}.",
            key=f"{sym}:daily_structure:{inst['daily_structure']}",
        )
        emit(
            "high",
            sym,
            "weekly_structure",
            f"{sym} weekly structure → {inst['weekly_structure']}",
            f"Weekly market structure on {sym} flipped to {inst['weekly_structure']}.",
            key=f"{sym}:weekly_structure:{inst['weekly_structure']}",
        )
        if inst.get("cross_50_200") == "bullish":
            emit("critical", sym, "golden_cross", f"{sym} GOLDEN CROSS", f"50 DMA crossed above 200 DMA on {sym}.", key=f"{sym}:golden_cross")
        if inst.get("cross_50_200") == "bearish":
            emit("critical", sym, "death_cross", f"{sym} DEATH CROSS", f"50 DMA crossed below 200 DMA on {sym}.", key=f"{sym}:death_cross")
        if inst.get("dma50_cross"):
            side = inst["dma50_cross"]
            emit(
                "medium",
                sym,
                "dma50",
                f"{sym} {'reclaimed' if side == 'above' else 'lost'} 50 DMA",
                f"{sym} closed {side} its 50-day average ({inst.get('sma50')}).",
                key=f"{sym}:dma50:{side}",
            )
        if inst.get("dma200_cross"):
            side = inst["dma200_cross"]
            sev = "high" if side == "below" else "high"
            emit(
                sev,
                sym,
                "dma200",
                f"{sym} {'reclaimed' if side == 'above' else 'lost'} 200 DMA",
                f"{sym} closed {side} its 200-day average ({inst.get('sma200')}) — major trend line.",
                key=f"{sym}:dma200:{side}",
            )

        lsh, lsl, px = inst.get("last_swing_high"), inst.get("last_swing_low"), inst["price"]
        dstruct = inst.get("daily_structure")
        if lsh and px > lsh and dstruct == "downtrend":
            emit("high", sym, "choch", f"{sym} bullish CHoCH", f"{sym} broke last swing high {lsh} against a downtrend — change of character.", key=f"{sym}:choch:bullish")
        if lsl and px < lsl and dstruct == "uptrend":
            emit("high", sym, "choch", f"{sym} bearish CHoCH", f"{sym} broke last swing low {lsl} against an uptrend — change of character.", key=f"{sym}:choch:bearish")

    vol = snap.get("volatility") or {}
    if vol.get("vix_bucket"):
        emit(
            "high" if vol["vix_bucket"] in ("high", "crisis") else "medium",
            "VIX",
            "vol_regime",
            f"VIX regime → {vol['vix_bucket'].replace('_', ' ')} ({vol.get('vix')})",
            f"Implied vol is {vol.get('vix')} ({vol['vix_bucket']}). Term structure: {vol.get('term_state') or 'n/a'}.",
            key=f"VIX:bucket:{vol['vix_bucket']}",
        )
    if vol.get("term_state"):
        sev = "high" if vol["term_state"] == "backwardation" else "medium"
        emit(
            sev,
            "VIX",
            "term",
            f"VIX term structure → {vol['term_state']}",
            f"VIX/VIX3M = {vol.get('term_ratio')}. Backwardation often marks stress; contango is the normal carry regime.",
            key=f"VIX:term:{vol['term_state']}",
        )

    internals = snap.get("internals") or {}
    bb = internals.get("breadth_bucket")
    if bb:
        emit(
            "high" if bb == "risk_off" else "medium",
            "BREADTH",
            "breadth",
            f"Sector breadth → {bb.replace('_', ' ')} ({internals.get('sectors_above_50')}/{internals.get('sectors_total')} above 50 DMA)",
            "Participation across the 11 S&P sector ETFs shifted buckets. Narrow leadership is a structure warning even if SPY holds up.",
            key=f"BREADTH:{bb}",
        )

    def sign_label(v: float | None) -> str | None:
        if v is None:
            return None
        return "lead" if v > 0 else "lag"

    for key, label, rel in (
        ("iwm_vs_spy_20d", "IWM vs SPY", "IWM:rel"),
        ("rsp_vs_spy_20d", "RSP vs SPY (equal-weight breadth)", "RSP:rel"),
        ("qqq_vs_spy_20d", "QQQ vs SPY", "QQQ:rel"),
    ):
        v = internals.get(key)
        sl = sign_label(v)
        if sl:
            emit(
                "medium",
                label.split()[0],
                "relative",
                f"{label} 20d → {sl} ({v:+.2f}%)",
                f"20-day relative performance of {label} is {v:+.2f}%. Flips here often precede cap-weighted trend changes.",
                key=f"{rel}:{sl}",
            )

    hyg = (snap.get("instruments") or {}).get("HYG") or {}
    if hyg.get("dma50_cross"):
        side = hyg["dma50_cross"]
        emit(
            "high",
            "HYG",
            "credit",
            f"High-yield credit {'reclaimed' if side == 'above' else 'lost'} 50 DMA",
            "HYG is a clean risk-appetite proxy. Credit breaking down while SPY holds is a classic structure divergence.",
            key=f"HYG:dma50:{side}",
        )

    spy = next((i for i in snap.get("indices", []) if i["symbol"] == "SPY"), None)
    if spy and spy.get("dist_20d_high_pct") is not None and spy["dist_20d_high_pct"] > -0.15:
        if internals.get("sectors_above_50", 11) <= 4:
            emit(
                "high",
                "SPY",
                "divergence",
                "SPY near 20-day high on weak breadth",
                f"SPY is {spy['dist_20d_high_pct']:+.2f}% from its 20-day high but only "
                f"{internals.get('sectors_above_50')}/{internals.get('sectors_total')} sectors sit above the 50 DMA.",
                key="SPY:narrow_rally",
            )

    for sym, orb in (snap.get("opening") or {}).items():
        if orb.get("status") in ("break_up", "break_down") and snap.get("rth"):
            direction = "up" if orb["status"] == "break_up" else "down"
            emit(
                "medium",
                sym,
                "orb",
                f"{sym} opening-range break {direction}",
                f"{sym} last {orb['last']:.2f} vs ORH {orb['orh']:.2f} / ORL {orb['orl']:.2f}. VWAP: {orb['vs_vwap']}.",
                key=f"{sym}:orb:{orb.get('date')}:{direction}",
            )
        if snap.get("rth"):
            emit(
                "info",
                sym,
                "vwap",
                f"{sym} {orb.get('vs_vwap')} VWAP",
                f"{sym} is {orb.get('vs_vwap')} session VWAP ({orb.get('vwap'):.2f}).",
                key=f"{sym}:vwap:{orb.get('date')}:{orb.get('vs_vwap')}",
            )

    return alerts


def build_briefing(snap: dict[str, Any]) -> str:
    lines = [f"US Market Structure — {snap.get('ts_label')}", ""]
    for inst in snap.get("indices", []):
        vs50 = inst.get("vs50_pct")
        vs200 = inst.get("vs200_pct")
        lines.append(
            f"{inst['symbol']}  {inst['price']:.2f}  {inst['change_pct']:+.2f}%  "
            f"{inst['regime'].upper()}  daily:{inst['daily_structure']}  weekly:{inst['weekly_structure']}  "
            f"vs50:{vs50:+.1f}%" if vs50 is not None else f"{inst['symbol']} {inst['price']:.2f}"
        )
        if vs50 is not None and vs200 is not None:
            lines[-1] += f"  vs200:{vs200:+.1f}%"
    vol = snap.get("volatility") or {}
    lines += [
        "",
        f"VIX {vol.get('vix')} ({vol.get('vix_bucket')})  term:{vol.get('term_state')} ({vol.get('term_ratio')})",
        f"Breadth {snap.get('internals', {}).get('sectors_above_50')}/{snap.get('internals', {}).get('sectors_total')} sectors > 50 DMA  "
        f"[{snap.get('internals', {}).get('breadth_bucket')}]",
        f"IWM vs SPY 20d: {snap.get('internals', {}).get('iwm_vs_spy_20d')}%   "
        f"RSP vs SPY 20d: {snap.get('internals', {}).get('rsp_vs_spy_20d')}%",
        f"Structure score: {snap.get('score', {}).get('value')} {snap.get('score', {}).get('label')}",
    ]
    hyg = (snap.get("instruments") or {}).get("HYG")
    if hyg:
        lines.append(f"HYG {hyg.get('price')}  regime:{hyg.get('regime')}  vs50:{hyg.get('vs50_pct')}%")
    tnx = snap.get("rates") or {}
    if tnx.get("price"):
        lines.append(f"10Y yield (^TNX) {tnx['price']:.2f}%  {tnx.get('change_pct'):+.2f}%")
    orbs = snap.get("opening") or {}
    if orbs:
        lines.append("")
        for sym, o in orbs.items():
            lines.append(f"OR {sym}: {o['status']}  last {o['last']:.2f}  VWAP {o['vs_vwap']}")
    return "\n".join(lines)
