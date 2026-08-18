#!/usr/bin/env python3
"""استراتژی لیام تریدر ۹ — نسخهٔ داشبورد (دستور حمید، ۱۸ اوت).

این فایل را در قسمت «استراتژی» داشبوردت کپی کن. تک و مستقل است (فقط
کتابخانهٔ استاندارد پایتون) و سه راه استفاده دارد:

    import liam9_strategy as st
    st.sync_params()                       # اتصال: پارامترها از ریپو تازه شود
    sig = st.signal("BTCUSDT")             # خودش کندل می‌گیرد و تصمیم می‌دهد
    # یا اگر داشبورد خودش کندل دارد:
    sig = st.analyze("BTCUSDT", c4h, c1h, c15)

    python3 liam9_strategy.py BTCUSDT      # تست از خط فرمان
    python3 liam9_strategy.py --selftest   # خودآزمایی بدون شبکه

خروجی: dict با action=LONG/SHORT/NO_SIGNAL + ورود/استاپ/تارگت/RR خالص +
دلایل فارسی. NO_SIGNAL تصمیم معتبر است (قانون: سیگنال اجباری ممنوع).

قوانین هسته (از منشور لیام — این‌جا فشرده و وفادار):
  · سلسله‌مراتب: ۴س و ۱س بر ۱۵د حاکم‌اند. هر دو تایم بالا خلاف = وتوی مطلق.
  · ستاپ = پولبک در جهت روند (روش حمید: صبر برای پولبک، نه شکار شکست).
  · IBS تأیید است نه سیگنال: لانگ ≤۰.۳۰، شورت ≥۰.۷۰.
  · استاپ بیرون نویز (≥۱.۲×ATR پانزده‌دقیقه) و پشت کف/سقف پولبک.
  · RR خالص از کارمزد (~۰.۱۵٪ رفت‌وبرگشت) باید از کف بگذرد.
  · دادهٔ ناکافی = NO_SIGNAL، هرگز حدس.

اتصال آپدیت («بعدش یه اتصال برقرار می‌کنیم»): sync_params() فایل
signals/strategy-params.json را از ریپوی لیام تریدر ۹ می‌کشد — هر وقت
قانونی با CI اثبات و در ریپو منتشر شود، داشبوردت با همان یک خط
به‌روز می‌شود، بدون تغییر این فایل.

نسخهٔ تمام‌عیار (همهٔ اتاق‌ها: OB/FVG/نقدینگی/دامیننس/حافظه) همان موتور
مرکزی است که قصدهایش را hamid_bridge_demo.py به داشبورد می‌رساند —
این فایل هستهٔ همان روش برای اجرای درجا در خود داشبورد است.
"""
import json
import time
import urllib.request

REPO_RAW = "https://raw.githubusercontent.com/Auraliam/Liam-Trader-9/main"
PAGES = "https://auraliam.github.io/Liam-Trader-9"
PARAMS_PATH = "/signals/strategy-params.json"

# ── پارامترها (پیش‌فرض = تولید فعلی؛ sync_params تازه‌شان می‌کند) ──────────
PARAMS = {
    "version": "liam9-dash-1.0",
    "ibs_long_max": 0.30,
    "ibs_short_min": 0.70,
    "min_net_rr": 1.8,
    "fee_round_trip_pct": 0.15,     # تیکر دو سر + لغزش (بیت‌یونیکس VIP0)
    "atr_noise_mult": 1.2,          # استاپ داخل نویز ممنوع (درس ZAMA)
    "rr_target": 2.0,
    "max_stop_pct": 2.0,
    "pullback_min_ratio": 0.25,     # پولبک واقعی، نه لرزش
    "pullback_max_ratio": 0.90,     # پولبکِ بلعنده = ساختار مشکوک
}

VENUES_15M = [
    ("https://api.mexc.com/api/v3/klines?symbol={s}&interval=15m&limit={n}", "mexc"),
    ("https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={g}&interval=15m&limit={n}", "gate"),
    ("https://fapi.binance.com/fapi/v1/klines?symbol={s}&interval=15m&limit={n}", "binance"),
]
IV = {"4h": "4h", "1h": "1h", "15m": "15m"}


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "liam9-strategy"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def sync_params():
    """اتصال به ریپو: پارامترهای اثبات‌شده را می‌کشد؛ خطا = پیش‌فرض امن."""
    for base in (REPO_RAW, PAGES):
        try:
            d = _get(base + PARAMS_PATH)
            if isinstance(d, dict) and d.get("version"):
                PARAMS.update({k: v for k, v in d.items()})
                return PARAMS["version"]
        except Exception:                            # noqa: BLE001
            continue
    return None


def fetch_klines(symbol, interval="15m", n=300):
    """کندل از چند صرافی عمومی؛ همه رد شدند = None (نه حدس)."""
    for tmpl, venue in VENUES_15M:
        url = tmpl.replace("15m", IV.get(interval, interval))
        url = url.format(s=symbol, n=n,
                         g=symbol.replace("USDT", "_USDT"))
        try:
            rows = _get(url)
            out = []
            for k in rows:
                if venue == "gate":                   # [t,vol,c,h,l,o,...]
                    out.append({"t": int(k[0]) * 1000, "o": float(k[5]),
                                "h": float(k[3]), "l": float(k[4]),
                                "c": float(k[2])})
                else:                                 # [t,o,h,l,c,...]
                    out.append({"t": int(k[0]), "o": float(k[1]),
                                "h": float(k[2]), "l": float(k[3]),
                                "c": float(k[4])})
            if len(out) >= 50:
                return out
        except Exception:                            # noqa: BLE001
            continue
    return None


# ── ابزارهای قطعی ───────────────────────────────────────────────────────────
def ema(vals, n):
    if len(vals) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(vals[:n]) / n
    for v in vals[n:]:
        e = v * k + e * (1 - k)
    return e


def atr(cd, n=14):
    if len(cd) < n + 1:
        return None
    trs = [max(cd[i]["h"] - cd[i]["l"], abs(cd[i]["h"] - cd[i - 1]["c"]),
               abs(cd[i]["l"] - cd[i - 1]["c"])) for i in range(1, len(cd))]
    a = sum(trs[:n]) / n
    for t in trs[n:]:
        a = (a * (n - 1) + t) / n
    return a


def trend(cd):
    """روند تایم بالا: EMA50 در برابر EMA200 + جهت سوینگ‌ها. کم‌داده = None."""
    closes = [k["c"] for k in cd]
    e50, e200 = ema(closes, 50), ema(closes, 200)
    if e50 is None or e200 is None:
        return None
    px = closes[-1]
    hi_now = max(k["h"] for k in cd[-30:])
    hi_prev = max(k["h"] for k in cd[-60:-30])
    lo_now = min(k["l"] for k in cd[-30:])
    lo_prev = min(k["l"] for k in cd[-60:-30])
    if e50 > e200 and px > e200 and hi_now >= hi_prev:
        return "up"
    if e50 < e200 and px < e200 and lo_now <= lo_prev:
        return "down"
    return "range"


def ibs(k):
    rng = k["h"] - k["l"]
    return (k["c"] - k["l"]) / rng if rng > 0 else 0.5


def _pullback(c15, direction):
    """موج و پولبک اخیر ۱۵د؛ خروجی (نسبت پولبک، اکسترمم پولبک) یا None."""
    win = c15[-60:]
    px = win[-1]["c"]
    if direction == "LONG":
        hi_i = max(range(len(win)), key=lambda i: win[i]["h"])
        if hi_i < 8 or hi_i > len(win) - 2:
            return None
        lo_i = min(range(hi_i + 1), key=lambda i: win[i]["l"])
        hi, lo = win[hi_i]["h"], win[lo_i]["l"]
        pull_lo = min(k["l"] for k in win[hi_i:])
        if hi <= lo:
            return None
        return (hi - px) / (hi - lo), pull_lo
    lo_i = min(range(len(win)), key=lambda i: win[i]["l"])
    if lo_i < 8 or lo_i > len(win) - 2:
        return None
    hi_i = max(range(lo_i + 1), key=lambda i: win[i]["h"])
    hi, lo = win[hi_i]["h"], win[lo_i]["l"]
    pull_hi = max(k["h"] for k in win[lo_i:])
    if hi <= lo:
        return None
    return (px - lo) / (hi - lo), pull_hi


def analyze(symbol, c4h, c1h, c15):
    """تصمیم روش لیام تریدر ۹ روی کندل‌های داده‌شده."""
    P = PARAMS
    no = lambda why: {"action": "NO_SIGNAL", "symbol": symbol, "why": why,  # noqa: E731
                      "version": P["version"]}
    if not c4h or not c1h or not c15 or len(c15) < 60:
        return no("دادهٔ ناکافی — قانون ۱: حدس ممنوع")
    t4, t1 = trend(c4h), trend(c1h)
    if t4 is None or t1 is None:
        return no("روند تایم بالا قابل‌سنجش نیست (کندل کم)")
    if t4 == "up" and t1 != "down":
        direction = "LONG"
    elif t4 == "down" and t1 != "up":
        direction = "SHORT"
    else:
        return no(f"روند ۴س ({t4}) و ۱س ({t1}) هم‌قصه نیستند — وتوی روند")
    pb = _pullback(c15, direction)
    if pb is None:
        return no("موج/پولبک معتبری در ۱۵د نیست")
    ratio, pull_ext = pb
    if not (P["pullback_min_ratio"] <= ratio <= P["pullback_max_ratio"]):
        return no(f"عمق پولبک {ratio:.2f} خارج از بازهٔ سالم")
    k_last = c15[-1]
    i = ibs(k_last)
    if direction == "LONG" and i > P["ibs_long_max"]:
        return no(f"IBS={i:.2f} — تأیید لانگ نیست (کف {P['ibs_long_max']})")
    if direction == "SHORT" and i < P["ibs_short_min"]:
        return no(f"IBS={i:.2f} — تأیید شورت نیست (سقف {P['ibs_short_min']})")
    entry = k_last["c"]
    a15 = atr(c15[-80:]) or 0
    if direction == "LONG":
        sl = min(pull_ext, entry - P["atr_noise_mult"] * a15)
        risk = entry - sl
        tp1 = entry + P["rr_target"] * risk
    else:
        sl = max(pull_ext, entry + P["atr_noise_mult"] * a15)
        risk = sl - entry
        tp1 = entry - P["rr_target"] * risk
    if risk <= 0:
        return no("هندسهٔ استاپ نامعتبر")
    stop_pct = risk / entry * 100
    if stop_pct > P["max_stop_pct"]:
        return no(f"استاپ {stop_pct:.2f}٪ — بزرگ‌تر از سقف {P['max_stop_pct']}٪")
    fee_r = (P["fee_round_trip_pct"] / 100) * entry / risk
    net_rr = P["rr_target"] - fee_r
    if net_rr < P["min_net_rr"]:
        return no(f"RR خالص {net_rr:.2f} زیر کف {P['min_net_rr']} — دام کارمزد")
    return {"action": direction, "symbol": symbol,
            "entry": round(entry, 8), "sl": round(sl, 8),
            "tp1": round(tp1, 8), "rr_net": round(net_rr, 2),
            "stop_pct": round(stop_pct, 3), "ibs": round(i, 2),
            "pullback": round(ratio, 3), "trend_4h": t4, "trend_1h": t1,
            "panel": "لیام تریدر ۹", "version": P["version"],
            "t": int(time.time() * 1000),
            "why": [f"روند ۴س {t4} · ۱س {t1} هم‌جهت",
                    f"پولبک {ratio:.2f} در جهت روند",
                    f"IBS {i:.2f} تأیید ورود",
                    f"استاپ بیرون نویز ({P['atr_noise_mult']}×ATR)",
                    f"RR خالص از کارمزد {net_rr:.2f}"]}


def signal(symbol):
    """کندل می‌گیرد و تصمیم می‌دهد — برای داشبوردی که فقط نماد می‌دهد."""
    c15 = fetch_klines(symbol, "15m", 300)
    c1h = fetch_klines(symbol, "1h", 260)
    c4h = fetch_klines(symbol, "4h", 260)
    if not (c15 and c1h and c4h):
        return {"action": "NO_SIGNAL", "symbol": symbol,
                "why": "کندل از هیچ منبعی نرسید — قانون ۱"}
    return analyze(symbol, c4h, c1h, c15)


def _selftest():
    def mk(path):
        return [{"t": i * 900000, "o": p, "h": p * 1.004, "l": p * 0.996,
                 "c": p} for i, p in enumerate(path)]
    up = [100 + i * 0.4 for i in range(230)]
    c4 = mk(up)
    c1 = mk(up)
    pull = up + [up[-1] - i * 0.5 for i in range(1, 16)]
    c15 = mk(pull)
    c15[-1]["l"], c15[-1]["c"] = c15[-1]["c"] * 0.99, c15[-1]["c"] * 0.9905
    r = analyze("TESTUSDT", c4, c1, c15)
    assert r["action"] == "LONG", r
    assert r["sl"] < r["entry"] < r["tp1"]
    dn = mk([100.0] * 40)
    assert analyze("TESTUSDT", c4, c1, dn[:10])["action"] == "NO_SIGNAL"
    mixed = analyze("TESTUSDT", mk([200 - i * 0.4 for i in range(230)]), c1, c15)
    assert mixed["action"] == "NO_SIGNAL" and "وتو" in mixed["why"]
    print("✓ خودآزمایی استراتژی گذشت —", r["why"])


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
        v = sync_params()
        print(f"پارامترها: {v or 'پیش‌فرض (اتصال نشد)'}")
        print(json.dumps(signal(sym), ensure_ascii=False, indent=1))
