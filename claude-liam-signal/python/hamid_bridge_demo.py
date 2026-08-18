#!/usr/bin/env python3
"""پل داشبورد ↔ لیام تریدر ۹ — اجرای دموی بیت‌یونیکس (دستور حمید، ۱۸ اوت).

این فایل تک و مستقل است (فقط کتابخانهٔ استاندارد) — روی داشبورد/لپ‌تاپ
اجرایش کن:

    python3 hamid_bridge_demo.py                # حالت خشک: فقط نمایش
    BITUNIX_DEMO_API_KEY=... BITUNIX_DEMO_API_SECRET=... \
    python3 hamid_bridge_demo.py --live-demo    # سفارش واقعی روی حساب دمو

چه می‌کند (هر POLL_S ثانیه):
  ۱. قصدهای اجرا را از ریپوی لیام تریدر ۹ می‌کشد (signals/exec-outbox.json)
     — همان دفتری که چرخه/رادار بعد از عبور از همهٔ دروازه‌ها پر می‌کنند.
     «اتصال به کلود» همین است: ایجنت و چرخه‌ها آن‌جا می‌نویسند، این پل
     می‌خواند؛ تازگی داده در حد چند دقیقه است (کادنس Actions)، پول ۱۵ثانیه
     فقط برای برداشتن سریعِ قصد تازه است.
  ۲. کیل‌سوییچ مرکزی را چک می‌کند (brain/killswitch.json) — tripped = هیچ
     سفارشی؛ قرارداد execution_gate.
  ۳. قصد تازه (id تکراری نه) را روی بیت‌یونیکس **دمو** سفارش می‌گذارد —
     یا در حالت خشک فقط چاپ/ثبت می‌کند.
  ۴. هر اقدام در shadow-book.jsonl محلی ثبت می‌شود تا بعداً با پیپر
     مقایسه شود (فیل/لغزش دمو در برابر فرض پیپر — دادهٔ طلایی قبل از لایو).

قواعد سخت (تغییرناپذیر):
  · فقط حساب دمو. LIVE_EXECUTION=false — این فایل عمداً هیچ سویچی برای
    پول واقعی ندارد.
  · کلیدها فقط از متغیر محیطی؛ هرگز در فایل/گیت/چت.
  · دادهٔ غایب/کهنه = سفارش نه (قانون ۱ — حدس ممنوع).
  · امضای بیت‌یونیکس طبق سند رسمی است و باید در اولین اجرا راستی‌آزمایی
    شود: https://www.bitunix.com/api-docs/futures/common/sign.html
    (double SHA-256: sha256(nonce+timestamp+apiKey+queryParams+body)
    سپس sha256(digest+secretKey)؛ هدرها: api-key, sign, nonce, timestamp)
    اگر ساختار پاسخ خطا داد، متن کاملش چاپ می‌شود — همان را برای کلود
    بفرست تا endpoint/امضا را با سند رسمی تطبیق بدهد.
"""
import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# ── پیکربندی ────────────────────────────────────────────────────────────────
REPO_RAW = "https://raw.githubusercontent.com/Auraliam/Liam-Trader-9/main"
PAGES = "https://auraliam.github.io/Liam-Trader-9"     # آینهٔ دوم (gh-pages)
OUTBOX_PATHS = ["/signals/exec-outbox.json"]
KILL_PATHS = ["/brain/killswitch.json"]
POLL_S = 15
FRESH_MAX_H = 12          # قصد کهنه‌تر از این هرگز اجرا نمی‌شود
DEMO_BASE = "https://fapi.bitunix.com"                 # فیوچرز
ORDER_PATH = "/api/v1/futures/trade/place_order"       # طبق سند رسمی چک شود
STATE_FILE = Path.home() / ".liam9-bridge-state.json"
SHADOW_BOOK = Path.home() / ".liam9-shadow-book.jsonl"
MAX_NOTIONAL_USD = 100.0  # سقف سخت هر سفارش دمو — حتی دمو بی‌سقف نمی‌شود


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "liam9-bridge"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_first(paths):
    """از raw گیت‌هاب، و اگر نشد از Pages — دو آینهٔ همان ریپو."""
    last_err = None
    for base in (REPO_RAW, PAGES):
        for p in paths:
            try:
                return _get(base + p)
            except Exception as e:                    # noqa: BLE001
                last_err = e
    print(f"⚠️ دیتا نرسید: {type(last_err).__name__} — این نوبت هیچ اقدامی نمی‌شود")
    return None


def _state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:                                # noqa: BLE001
        return {"done": []}


def _save_state(st):
    st["done"] = st["done"][-500:]
    STATE_FILE.write_text(json.dumps(st))


def _log_shadow(row):
    with SHADOW_BOOK.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ── امضای بیت‌یونیکس (سند رسمی: api-docs/futures/common/sign.html) ─────────
def bitunix_sign(api_key, secret, params_qs, body_str, nonce, ts_ms):
    digest = hashlib.sha256(
        (nonce + str(ts_ms) + api_key + params_qs + body_str).encode()
    ).hexdigest()
    return hashlib.sha256((digest + secret).encode()).hexdigest()


def bitunix_order(api_key, secret, intent, qty):
    body = {
        "symbol": intent["symbol"],
        "side": "BUY" if intent["direction"] == "LONG" else "SELL",
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "price": str(intent["entry"]),
        "qty": str(qty),
        "effect": "GTC",
        "clientId": intent["id"][:36],
    }
    if intent.get("tp1"):
        body["tpPrice"] = str(intent["tp1"])
    if intent.get("sl"):
        body["slPrice"] = str(intent["sl"])
    body_str = json.dumps(body, separators=(",", ":"))
    nonce = uuid.uuid4().hex
    ts = int(time.time() * 1000)
    sign = bitunix_sign(api_key, secret, "", body_str, nonce, ts)
    req = urllib.request.Request(
        DEMO_BASE + ORDER_PATH, data=body_str.encode(), method="POST",
        headers={"api-key": api_key, "sign": sign, "nonce": nonce,
                 "timestamp": str(ts), "Content-Type": "application/json",
                 "language": "en-US"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return True, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read())
        except Exception:                            # noqa: BLE001
            return False, {"error": f"HTTP {e.code}"}
    except Exception as e:                           # noqa: BLE001
        return False, {"error": type(e).__name__}


def qty_for(intent, equity_usd=1000.0, risk_pct=1.0):
    """سایز از ریسک ۱٪ و فاصلهٔ استاپ؛ سقف سخت MAX_NOTIONAL_USD."""
    entry, sl = float(intent["entry"]), float(intent.get("sl") or 0)
    if not sl or entry <= 0 or abs(entry - sl) <= 0:
        return None
    risk_usd = equity_usd * risk_pct / 100.0
    qty = risk_usd / abs(entry - sl)
    if qty * entry > MAX_NOTIONAL_USD:
        qty = MAX_NOTIONAL_USD / entry
    return round(qty, 6)


def run(live_demo=False):
    api_key = os.environ.get("BITUNIX_DEMO_API_KEY", "").strip()
    secret = os.environ.get("BITUNIX_DEMO_API_SECRET", "").strip()
    if live_demo and not (api_key and secret):
        print("⛔ --live-demo بدون BITUNIX_DEMO_API_KEY/SECRET ممکن نیست — "
              "به حالت خشک برمی‌گردم")
        live_demo = False
    mode = "🟠 دموی واقعی بیت‌یونیکس" if live_demo else "⚪️ حالت خشک (نمایش)"
    print(f"پل لیام تریدر ۹ ⇄ داشبورد | {mode} | هر {POLL_S} ثانیه\n")

    st = _state()
    while True:
        try:
            kill = fetch_first(KILL_PATHS)
            if kill and kill.get("tripped"):
                print(f"⛔ کیل‌سوییچ فعال است ({kill['tripped'].get('reason')}) "
                      "— هیچ سفارشی گذاشته نمی‌شود")
                time.sleep(POLL_S)
                continue
            box = fetch_first(OUTBOX_PATHS) or []
            now = time.time() * 1000
            fresh = [i for i in box
                     if i.get("status") == "PENDING"
                     and i.get("id") not in st["done"]
                     and now - (i.get("created_at") or 0) < FRESH_MAX_H * 3600_000]
            for it in fresh:
                qty = qty_for(it)
                line = (f"{it['symbol']} {it['direction']} @ {it['entry']} "
                        f"SL {it.get('sl')} TP {it.get('tp1')} | qty={qty} "
                        f"| {it.get('strategy','?')}")
                if qty is None:
                    print(f"⏭ {line} — بدون استاپ معتبر، رد شد (قانون ۱)")
                    st["done"].append(it["id"])
                    continue
                if live_demo:
                    ok, resp = bitunix_order(api_key, secret, it, qty)
                    tag = "✅ سفارش دمو ثبت شد" if ok else f"❌ رد شد: {resp}"
                    print(f"{tag} → {line}")
                    _log_shadow({"t": int(now), "intent": it["id"],
                                 "sym": it["symbol"], "dir": it["direction"],
                                 "qty": qty, "ok": ok, "resp": resp,
                                 "mode": "demo"})
                else:
                    print(f"👁 قصد تازه (خشک): {line}")
                    _log_shadow({"t": int(now), "intent": it["id"],
                                 "sym": it["symbol"], "dir": it["direction"],
                                 "qty": qty, "ok": None, "mode": "dry"})
                st["done"].append(it["id"])
            if not fresh:
                print(time.strftime("%H:%M:%S"),
                      "— قصد تازه‌ای نیست (دفتر خوانده شد، کیل‌سوییچ سبز)")
            _save_state(st)
        except KeyboardInterrupt:
            print("\nخداحافظ — دفتر سایه:", SHADOW_BOOK)
            return
        except Exception as e:                       # noqa: BLE001
            print(f"⚠️ خطای حلقه: {type(e).__name__}: {e} — ادامه می‌دهم")
        time.sleep(POLL_S)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-demo", action="store_true",
                    help="سفارش واقعی روی حساب دمو (کلید از env)")
    args = ap.parse_args()
    run(live_demo=args.live_demo)
