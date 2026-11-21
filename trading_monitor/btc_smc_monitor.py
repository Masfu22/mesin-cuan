#!/usr/bin/env python3
"""Read-only BTC/USD SMC alert monitor. Uses public Kraken OHLC data; never places orders."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API = "https://api.kraken.com/0/public/OHLC"
STATE_FILE = Path(".monitor_state/btcusd_smc.json")
WIB = ZoneInfo("Asia/Jakarta")


def get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "BTCUSD-SMC-Monitor/1.0"})
    with urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def candles(interval: int) -> list[dict]:
    query = urlencode({"pair": "XBTUSD", "interval": interval})
    payload = get_json(f"{API}?{query}")
    if payload.get("error"):
        raise RuntimeError("Kraken API: " + "; ".join(payload["error"]))
    result = payload.get("result", {})
    pair_key = next((key for key in result if key != "last"), None)
    if not pair_key:
        raise RuntimeError("Data OHLC Kraken kosong.")
    rows = result[pair_key]
    # Kraken's final row is the still-forming candle. Exclude it.
    rows = rows[:-1]
    parsed = []
    for row in rows:
        parsed.append({
            "time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[6]),
        })
    if len(parsed) < 60:
        raise RuntimeError(f"Data interval {interval} menit tidak cukup: {len(parsed)} candle.")
    return parsed


def ema(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"EMA{period} membutuhkan minimal {period} candle.")
    alpha = 2.0 / (period + 1)
    value = sum(values[:period]) / period
    for item in values[period:]:
        value = alpha * item + (1 - alpha) * value
    return value


def bias(data: list[dict]) -> str:
    closes = [c["close"] for c in data]
    fast, slow = ema(closes, 20), ema(closes, 50)
    if fast > slow and closes[-1] > fast:
        return "BULLISH"
    if fast < slow and closes[-1] < fast:
        return "BEARISH"
    return "NEUTRAL"


def latest_smc_signal(m5: list[dict], direction: str):
    # Look for a recent sweep of the previous 12-candle liquidity pool,
    # followed by a close through the pre-sweep internal structure (CHoCH).
    start = max(12, len(m5) - 10)
    for i in range(len(m5) - 2, start - 1, -1):
        prior = m5[i - 12:i]
        after = m5[i + 1:]
        if len(after) == 0:
            continue
        if direction == "BULLISH":
            liquidity = min(c["low"] for c in prior)
            swept = m5[i]["low"] < liquidity and m5[i]["close"] > liquidity
            internal_high = max(c["high"] for c in m5[max(0, i - 5):i])
            confirmation = next((c for c in after if c["close"] > internal_high), None)
            if swept and confirmation:
                return {
                    "side": "BUY", "sweep": m5[i], "confirm": confirmation,
                    "liquidity": liquidity, "extreme": m5[i]["low"],
                }
        elif direction == "BEARISH":
            liquidity = max(c["high"] for c in prior)
            swept = m5[i]["high"] > liquidity and m5[i]["close"] < liquidity
            internal_low = min(c["low"] for c in m5[max(0, i - 5):i])
            confirmation = next((c for c in after if c["close"] < internal_low), None)
            if swept and confirmation:
                return {
                    "side": "SELL", "sweep": m5[i], "confirm": confirmation,
                    "liquidity": liquidity, "extreme": m5[i]["high"],
                }
    return None


def telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("GitHub Secrets TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID harus diisi.")
    body = urlencode({"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}).encode()
    req = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "BTCUSD-SMC-Monitor/1.0"},
        method="POST",
    )
    with urlopen(req, timeout=25) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError("Telegram menolak pengiriman notifikasi.")


def main() -> int:
    print("Mengambil OHLC Kraken BTC/USD (read-only)...")
    h4, h1, m15, m5 = candles(240), candles(60), candles(15), candles(5)
    b4, b1, b15 = bias(h4), bias(h1), bias(m15)
    last = m5[-1]
    print(f"H4={b4} H1={b1} M15={b15} | M5 close={last['close']:.2f}")

    if not (b4 == b1 == b15 and b4 in ("BULLISH", "BEARISH")):
        print("NO SIGNAL: arah H4/H1/M15 belum sejalan.")
        return 0

    setup = latest_smc_signal(m5, b4)
    if not setup:
        print("NO SIGNAL: belum ada rangkaian liquidity sweep + CHoCH M5.")
        return 0

    entry = setup["confirm"]["close"]
    if setup["side"] == "BUY":
        sl = setup["extreme"] - max(entry * 0.001, 1.0)
        risk = entry - sl
        tp1, tp2 = entry + 1.5 * risk, entry + 2.0 * risk
    else:
        sl = setup["extreme"] + max(entry * 0.001, 1.0)
        risk = sl - entry
        tp1, tp2 = entry - 1.5 * risk, entry - 2.0 * risk

    fingerprint_raw = f"{setup['side']}|{setup['sweep']['time']}|{setup['confirm']['time']}"
    fingerprint = hashlib.sha256(fingerprint_raw.encode()).hexdigest()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
    if state.get("last_alert") == fingerprint:
        print("Sinyal yang sama sudah dikirim; notifikasi duplikat dilewati.")
        return 0

    stamp = datetime.fromtimestamp(setup["confirm"]["time"], timezone.utc).astimezone(WIB)
    message = (
        f"🔔 BTC/USD — SMC SETUP {setup['side']}\n"
        f"Konfirmasi: {stamp:%d-%m-%Y %H:%M} WIB\n"
        f"Struktur: H4 {b4} | H1 {b1} | M15 {b15}\n"
        f"M5: liquidity sweep + CHoCH terdeteksi\n\n"
        f"Entry referensi: {entry:,.2f}\n"
        f"Stop Loss: {sl:,.2f}\n"
        f"TP1 (1.5R): {tp1:,.2f}\n"
        f"TP2 (2R): {tp2:,.2f}\n\n"
        f"Sumber harga: Kraken BTC/USD spot, bukan kuotasi broker Exness. "
        f"Cek spread dan harga Exness sebelum mengambil keputusan. "
        f"Ini notifikasi analisis, bukan perintah transaksi; tidak ada order yang dikirim."
    )
    telegram(message)
    state["last_alert"] = fingerprint
    state["last_alert_at_utc"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("Sinyal baru dikirim ke Telegram.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"MONITOR ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
