#!/usr/bin/env python3
"""لیام تریدر ۹ — موتور شوک + خط زندهٔ امن، آمادهٔ داشبورد (دستور حمید، ۱۹ اوت).

⚠️ این فایل **تولیدشده** است: `python3 scripts/build_dash_shock.py`
   منبع حقیقت `liam9_shock.py` و `liam9_link.py` است. دستی ویرایشش نکن.

همین فایل را کامل در اسلات «استراتژی» داشبورد بگذار. تک است (فقط
کتابخانهٔ استاندارد پایتون) و دو کلاس با `meta` دارد:

    Liam9ShockStrategy   — موتور شوک بیت‌کوین
    (کلاس اصلی؛ داشبورد همین را پیدا و بارگذاری می‌کند)

قانون کدشده:
  · شوک روی هر تایم (۱د/۵د/۱۵د/۱س/۴س) = بدنه ≥۲.۵×ATR + کف مطلق آن تایم
    + حجم ≥۲× میانه.
  · ورود روی **بازگشت به اردر بلاک ایمپالس** با اهرم ۵–۶ — نه وسط حرکت.
  · شکار پامپ با اهرم ۱۵ **فقط** با هر شش تأیید حجمی. یکی غایب = ممنوع.
  · اهرم ≤ min(خواسته، ۵۰÷استاپ٪، سقف داشبورد ۲۰). سایز از ریسک ۲٪
    می‌آید نه از اهرم.
  · خط زندهٔ امن: هر تصمیم و هر ردشدن با دلیل گزارش می‌شود؛ فرمان‌های
    امضاشده (HMAC) با seq و انقضا پذیرفته می‌شوند. بدون کلید = رد همه.

راه‌اندازی در داشبورد:
    ۱. فایل را در اسلات استراتژی بگذار.
    ۲. (اختیاری ولی توصیه‌شده) متغیر محیطی `LIAM9_LINK_SECRET` را همان
       چیزی بگذار که در گیت‌هاب گذاشتی، تا فرمان‌های زنده هم کار کنند.
    ۳. تمام. داشبورد کلاس را می‌سازد و `generate_signal(symbol)` صدا می‌زند.

خط فرمان (برای تست بیرون داشبورد):
    python3 liam9_shock_strategy.py BTCUSDT
    python3 liam9_shock_strategy.py --selftest
"""

import json
import time
import urllib.request

TFS = ["1m", "5m", "15m", "1h", "4h"]
TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
         "1h": 3_600_000, "4h": 14_400_000}

P = {
    "version": "liam9-shock-1.0",
    # ── شوک: چه چیزی «یهو» حساب می‌شود ─────────────────────────────────
    "shock_atr_mult": 2.5,       # بدنهٔ ایمپالس ≥ ۲.۵ برابر ATR همان تایم
    "shock_min_pct": {"1m": 0.35, "5m": 0.60, "15m": 0.90,
                      "1h": 1.50, "4h": 2.50},   # کف مطلق هر تایم
    "shock_vol_mult": 2.0,       # حجم ایمپالس ≥ ۲ برابر میانهٔ ۵۰ کندل
    "shock_lookback": 3,         # ایمپالس می‌تواند تا ۳ کندل طول بکشد
    "shock_fresh_bars": 12,      # شوک کهنه‌تر از این دیگر شوک نیست
    # ── اردر بلاک ──────────────────────────────────────────────────────
    "ob_max_age_bars": 40,       # OB قدیمی‌تر از این، بی‌اعتبار
    "ob_touch_pct": 0.15,        # «رسیدن به OB» یعنی این‌قدر نزدیکی
    # ── اهرم (دستور حمید) ──────────────────────────────────────────────
    "lev_follow_base": 5,
    "lev_follow_max": 6,
    "lev_pump_chase": 15,
    "liq_guard_ratio": 0.5,      # استاپ حداکثر نصف راه تا لیکویید
    "max_leverage_cap": 20,      # سقف داشبورد حمید
    # ── هندسه و کارمزد ─────────────────────────────────────────────────
    "rr_target": 2.0,
    "min_net_rr": 1.5,
    "fee_round_trip_pct": 0.15,
    "min_stop_pct": 0.35,
    "max_stop_pct": 3.0,
    "risk_per_trade_pct": 2.0,
    "max_hold_bars": 24,
}

VENUES = [
    ("https://api.mexc.com/api/v3/klines?symbol={s}&interval={i}&limit={n}", "mexc"),
    ("https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={g}&interval={i}&limit={n}", "gate"),
    ("https://fapi.binance.com/fapi/v1/klines?symbol={s}&interval={i}&limit={n}", "binance"),
]


# ── داده ────────────────────────────────────────────────────────────────────
def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "liam9-shock"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_klines(symbol, interval="5m", n=200):
    """کندل با حجم — حجم این‌جا اختیاری نیست، قانون رویش بنا شده."""
    for tmpl, venue in VENUES:
        url = tmpl.format(s=symbol, n=n, i=interval,
                          g=symbol.replace("USDT", "_USDT"))
        try:
            rows = _get(url)
            out = []
            for k in rows:
                if venue == "gate":       # [t,quoteVol,c,h,l,o,baseVol]
                    out.append({"t": int(k[0]) * 1000, "o": float(k[5]),
                                "h": float(k[3]), "l": float(k[4]),
                                "c": float(k[2]),
                                "v": float(k[6] if len(k) > 6 else k[1])})
                else:                      # [t,o,h,l,c,v,...]
                    out.append({"t": int(k[0]), "o": float(k[1]),
                                "h": float(k[2]), "l": float(k[3]),
                                "c": float(k[4]), "v": float(k[5])})
            if len(out) >= 60:
                return out
        except Exception:                                # noqa: BLE001
            continue
    return None


# ── ابزار قطعی ──────────────────────────────────────────────────────────────
def atr(cd, n=14):
    if len(cd) < n + 1:
        return None
    trs = [max(cd[i]["h"] - cd[i]["l"], abs(cd[i]["h"] - cd[i - 1]["c"]),
               abs(cd[i]["l"] - cd[i - 1]["c"])) for i in range(1, len(cd))]
    a = sum(trs[:n]) / n
    for t in trs[n:]:
        a = (a * (n - 1) + t) / n
    return a


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def ema(vals, n):
    if len(vals) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(vals[:n]) / n
    for v in vals[n:]:
        e = v * k + e * (1 - k)
    return e


# ── ۱) شناسایی شوک روی هر تایم‌فریم ────────────────────────────────────────
def detect_shock(cd, tf, now_ms=None):
    """«یهو پامپ یا دامپ شد» — با عدد، نه با چشم.

    شوک = حرکت جهت‌دار طی ۱ تا ۳ کندل که هر سه شرط را دارد:
      · بدنهٔ خالص ≥ shock_atr_mult × ATR همان تایم
      · بزرگی حرکت ≥ کف مطلق آن تایم (تا نویز تایم پایین شوک حساب نشود)
      · حجم ایمپالس ≥ shock_vol_mult × میانهٔ ۵۰ کندل اخیر
    و تازه باشد (زیر shock_fresh_bars کندل از پایانش)."""
    if not cd or len(cd) < 60:
        return None
    a = atr(cd[-60:])
    if not a:
        return None
    med_v = median([k["v"] for k in cd[-50:]]) or 0.0
    best = None
    for span in range(1, P["shock_lookback"] + 1):
        for end in range(len(cd) - 1, max(len(cd) - 1 - P["shock_fresh_bars"],
                                          span), -1):
            seg = cd[end - span + 1: end + 1]
            move = seg[-1]["c"] - seg[0]["o"]
            move_pct = abs(move) / seg[0]["o"] * 100
            body_atr = abs(move) / a if a else 0
            vol = sum(k["v"] for k in seg)
            vol_mult = (vol / (med_v * span)) if med_v > 0 else 0
            if (body_atr >= P["shock_atr_mult"]
                    and move_pct >= P["shock_min_pct"].get(tf, 1.0)
                    and vol_mult >= P["shock_vol_mult"]):
                cand = {"tf": tf, "dir": "PUMP" if move > 0 else "DUMP",
                        "move_pct": round(move_pct, 3),
                        "atr_mult": round(body_atr, 2),
                        "vol_mult": round(vol_mult, 2),
                        "bars": span, "start_i": end - span + 1, "end_i": end,
                        "age_bars": len(cd) - 1 - end,
                        "t": seg[-1]["t"]}
                if best is None or cand["atr_mult"] > best["atr_mult"]:
                    best = cand
        if best:
            break                      # کوتاه‌ترین ایمپالسِ معتبر کافی است
    return best


# ── ۲) اردر بلاکِ ایمپالس ──────────────────────────────────────────────────
def impulse_order_block(cd, shock):
    """آخرین کندل مخالف پیش از ایمپالس — با شرط جابه‌جایی (displacement).

    فقط «آخرین کندل مخالف» نیست (قانون شخصی‌سازی حمید): باید ایمپالس از
    آن OB بیرون زده باشد و OB هنوز مصرف نشده باشد."""
    if not shock:
        return None
    i0 = shock["start_i"]
    up = shock["dir"] == "PUMP"
    ob = None
    for j in range(i0 - 1, max(i0 - 12, 0) - 1, -1):
        k = cd[j]
        if (up and k["c"] < k["o"]) or (not up and k["c"] > k["o"]):
            ob = {"i": j, "hi": k["h"], "lo": k["l"], "t": k["t"]}
            break
    if ob is None:
        return None
    # جابه‌جایی: ایمپالس باید از سقف/کف OB عبور کرده باشد
    imp = cd[shock["start_i"]: shock["end_i"] + 1]
    if up and max(k["h"] for k in imp) <= ob["hi"]:
        return None
    if not up and min(k["l"] for k in imp) >= ob["lo"]:
        return None
    # مصرف‌شدگی: بعد از ایمپالس، قیمت داخل OB برنگشته باشد
    after = cd[shock["end_i"] + 1:]
    for k in after:
        if up and k["l"] <= ob["lo"]:
            return None                      # کامل مصرف شد
        if not up and k["h"] >= ob["hi"]:
            return None
    ob["age_bars"] = len(cd) - 1 - ob["i"]
    ob["fresh"] = ob["age_bars"] <= P["ob_max_age_bars"]
    return ob if ob["fresh"] else None


# ── ۳) تأییدیهٔ حجم — «۱۰۰ درصدی» یعنی هر شش تا ────────────────────────────
def volume_confirmation(cd, shock):
    """شش تأیید حجمی برای مجوز اهرم ۱۵. یکی غایب = مجوز باطل.

    عمداً همه‌شان از حجم و رفتار خودِ کندل می‌آیند و هیچ‌کدام حدسی نیست:
      ۱. حجم ایمپالس ≥ ۳ برابر میانهٔ ۵۰ کندل
      ۲. حجم صعودی داخل ایمپالس (هر کندل از قبلی بیشتر) — تک‌کندلی معاف
      ۳. کلوز در ۲۰٪ بالای دامنهٔ ایمپالس (پامپ) یا ۲۰٪ پایین (دامپ)
      ۴. ویکِ مخالف کمتر از ۳۰٪ دامنه — یعنی رد نشده
      ۵. کندلِ بعدِ ایمپالس حجمش نریخته (≥ نصف میانه) — نه پامپ توخالی
      ۶. حجم ۵ کندل اخیر روی‌هم از حجم ۵ کندل قبلِ ایمپالس بیشتر
    """
    out = {"checks": {}, "full": False, "score": 0}
    if not shock or len(cd) < 60:
        return out
    med_v = median([k["v"] for k in cd[-50:]]) or 0.0
    imp = cd[shock["start_i"]: shock["end_i"] + 1]
    up = shock["dir"] == "PUMP"
    hi = max(k["h"] for k in imp)
    lo = min(k["l"] for k in imp)
    rng = hi - lo
    close = imp[-1]["c"]
    vols = [k["v"] for k in imp]

    c = out["checks"]
    c["حجم ≥ ۳× میانه"] = med_v > 0 and sum(vols) / len(vols) >= 3 * med_v
    c["حجم صعودی در ایمپالس"] = len(vols) == 1 or all(
        vols[i] >= vols[i - 1] for i in range(1, len(vols)))
    c["کلوز در ۲۰٪ انتهای دامنه"] = rng > 0 and (
        (close - lo) / rng >= 0.80 if up else (hi - close) / rng >= 0.80)
    body_top = max(imp[-1]["c"], imp[-1]["o"])
    body_bot = min(imp[-1]["c"], imp[-1]["o"])
    k_rng = imp[-1]["h"] - imp[-1]["l"]
    opp_wick = (imp[-1]["h"] - body_top) if up else (body_bot - imp[-1]["l"])
    c["ویک مخالف < ۳۰٪"] = k_rng > 0 and opp_wick / k_rng < 0.30
    nxt = cd[shock["end_i"] + 1] if shock["end_i"] + 1 < len(cd) else None
    c["حجم بعدی نریخته"] = nxt is None or (med_v > 0 and nxt["v"] >= med_v * 0.5)
    pre = cd[max(shock["start_i"] - 5, 0): shock["start_i"]]
    c["جریان حجم رو به بالا"] = (
        sum(k["v"] for k in cd[-5:]) > sum(k["v"] for k in pre) if pre else False)

    out["score"] = sum(1 for v in c.values() if v)
    out["full"] = out["score"] == len(c)          # ۱۰۰٪ یعنی همه
    out["missing"] = [k for k, v in c.items() if not v]
    return out


# ── ۴) اهرم: دستور حمید، با محافظ لیکویید ──────────────────────────────────
def leverage_for(mode, stop_pct, extra_confirms=0):
    """اهرم مجاز. هرگز از سقف داشبورد (۲۰) و از محافظ لیکویید رد نمی‌شود.

    محافظ: استاپ باید حداکثر نصف فاصلهٔ لیکویید باشد →
    اهرم ≤ ۱۰۰×liq_guard_ratio / استاپ٪ (اهرم ۱۵ ⇒ استاپ زیر ~۳.۳٪)."""
    if stop_pct <= 0:
        return None
    guard = int(100.0 * P["liq_guard_ratio"] / stop_pct)
    want = (P["lev_pump_chase"] if mode == "PUMP_CHASE"
            else min(P["lev_follow_base"] + (1 if extra_confirms >= 2 else 0),
                     P["lev_follow_max"]))
    lev = min(want, guard, P["max_leverage_cap"])
    floor = 3 if mode != "PUMP_CHASE" else 8
    return lev if lev >= floor else None


def size_for(equity, stop_pct, lev):
    """سایز از قانون ریسک ۲٪ داشبورد — نه از اهرم. اهرم فقط مارجین را
    تعیین می‌کند؛ ضررِ استاپ همان ۲٪ می‌ماند."""
    if not equity or stop_pct <= 0 or not lev:
        return None
    risk_usd = equity * P["risk_per_trade_pct"] / 100.0
    notional = risk_usd / (stop_pct / 100.0)
    return {"risk_usd": round(risk_usd, 2),
            "notional_usd": round(notional, 2),
            "margin_usd": round(notional / lev, 2), "leverage": lev}


# ── ۵) تصمیم ────────────────────────────────────────────────────────────────
def decide(symbol, cd, tf, equity=None, btc_shock=None, now_ms=None):
    """تصمیم موتور شوک روی یک نماد و یک تایم.

    btc_shock: شوکِ خودِ بیت‌کوین (از scan_btc). قانون حمید شوکِ **بیت‌کوین**
    را ماشه می‌داند؛ برای خود BTCUSDT همان شوک خودش است."""
    def no(why, extra=None):
        d = {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf, "why": why,
             "version": P["version"], "panel": "لیام تریدر ۹"}
        if extra:
            d.update(extra)
        return d

    if not cd or len(cd) < 60:
        return no("کندل ناکافی — قانون ۱: حدس ممنوع")
    shock = btc_shock or detect_shock(cd, tf, now_ms)
    if not shock:
        return no("شوکی روی این تایم نیست")

    own = detect_shock(cd, tf, now_ms)
    if symbol != "BTCUSDT" and not own:
        return no("بیت‌کوین شوک دارد ولی این نماد همراهی نکرده",
                  {"btc_shock": shock})
    local = own or shock
    direction = "LONG" if local["dir"] == "PUMP" else "SHORT"
    ob = impulse_order_block(cd, local)
    vc = volume_confirmation(cd, local)
    px = cd[-1]["c"]

    # ── مسیر ۲: شکار پامپ با اهرم ۱۵ — فقط با تأیید ۱۰۰٪ ────────────────
    if vc["full"] and local["age_bars"] <= 2:
        # ورود دنباله‌رو: استاپ پشت کف/سقف ایمپالس، نه پشت ساختار دور
        imp = cd[local["start_i"]: local["end_i"] + 1]
        sl = min(k["l"] for k in imp) if direction == "LONG" \
            else max(k["h"] for k in imp)
        risk = abs(px - sl)
        stop_pct = risk / px * 100 if px else 0
        if not (P["min_stop_pct"] <= stop_pct <= P["max_stop_pct"]):
            return no(f"شکار پامپ رد شد: استاپ {stop_pct:.2f}٪ بیرون بازهٔ مجاز",
                      {"volume": vc})
        lev = leverage_for("PUMP_CHASE", stop_pct)
        if lev is None:
            return no(f"شکار پامپ رد شد: استاپ {stop_pct:.2f}٪ با اهرم ۱۵ "
                      "به لیکویید نزدیک می‌شود", {"volume": vc})
        return _build(symbol, tf, "PUMP_CHASE", direction, px, sl, stop_pct,
                      lev, local, ob, vc, equity,
                      ["تأیید حجمی ۱۰۰٪ (هر شش شرط)",
                       f"ایمپالس {local['move_pct']}٪ = {local['atr_mult']}×ATR",
                       f"حجم {local['vol_mult']}× میانه",
                       f"اهرم {lev}× (دستور حمید برای شکار پامپ)"])

    # ── مسیر ۱: دنبال‌کردن شوک روی اردر بلاک با اهرم ۵–۶ ────────────────
    if ob is None:
        return no("اردر بلاک معتبری از ایمپالس نمانده (مصرف‌شده یا بی‌جابه‌جایی)",
                  {"volume": vc, "shock": local})
    near = (abs(px - ob["hi"]) / px * 100 <= P["ob_touch_pct"] * 10
            if direction == "LONG"
            else abs(px - ob["lo"]) / px * 100 <= P["ob_touch_pct"] * 10)
    inside = ob["lo"] <= px <= ob["hi"]
    if not (inside or near):
        return no("قیمت هنوز به اردر بلاک ایمپالس برنگشته — منتظر بازگشت",
                  {"ob": ob, "shock": local, "volume": vc,
                   "state": "WAITING_OB"})
    sl = ob["lo"] * 0.999 if direction == "LONG" else ob["hi"] * 1.001
    risk = abs(px - sl)
    stop_pct = risk / px * 100 if px else 0
    if not (P["min_stop_pct"] <= stop_pct <= P["max_stop_pct"]):
        return no(f"استاپ {stop_pct:.2f}٪ بیرون بازهٔ مجاز", {"ob": ob})
    extra = sum([vc["score"] >= 4, local["atr_mult"] >= 3.5,
                 local["vol_mult"] >= 3.0])
    lev = leverage_for("SHOCK_FOLLOW", stop_pct, extra)
    if lev is None:
        return no(f"استاپ {stop_pct:.2f}٪ با اهرم شوک جا نمی‌شود")
    return _build(symbol, tf, "SHOCK_FOLLOW", direction, px, sl, stop_pct,
                  lev, local, ob, vc, equity,
                  [f"شوک {local['dir']} روی {tf}: {local['move_pct']}٪ "
                   f"({local['atr_mult']}×ATR، حجم {local['vol_mult']}×)",
                   "ورود روی بازگشت به اردر بلاک ایمپالس (نه وسط حرکت)",
                   f"تأیید حجمی {vc['score']}/۶",
                   f"اهرم {lev}× (دستور حمید: ۵ تا ۶)"])


def _build(symbol, tf, mode, direction, entry, sl, stop_pct, lev, shock, ob,
           vc, equity, why):
    risk = abs(entry - sl)
    tp1 = (entry + P["rr_target"] * risk if direction == "LONG"
           else entry - P["rr_target"] * risk)
    fee_r = (P["fee_round_trip_pct"] / 100) * entry / risk if risk else 99
    net_rr = P["rr_target"] - fee_r
    if net_rr < P["min_net_rr"]:
        return {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf,
                "why": f"RR خالص {net_rr:.2f} زیر کف {P['min_net_rr']} — "
                       "دام کارمزد", "version": P["version"],
                "panel": "لیام تریدر ۹"}
    out = {"action": direction, "mode": mode, "symbol": symbol, "tf": tf,
           # قرارداد اجرا (دستور حمید، ۲۰ اوت): ایزوله + استاپ/تارگت اجباری
           "product": "futures", "margin_mode": "isolated",
           "sl_tp_mandatory": True,
           "entry": round(entry, 8), "sl": round(sl, 8), "tp1": round(tp1, 8),
           "stop_pct": round(stop_pct, 3), "rr_net": round(net_rr, 2),
           "fee_r": round(fee_r, 3), "leverage": lev,
           "shock": shock, "ob": ob,
           "volume_score": f"{vc['score']}/6", "volume_full": vc["full"],
           "volume_missing": vc.get("missing", []),
           "trail": {"step1_at": round(entry + (tp1 - entry) / 3, 8),
                     "rule": "🪜 ⅓ مسیر → استاپ سربه‌سرِ کارمزددار"},
           "max_hold_bars": P["max_hold_bars"],
           "panel": "لیام تریدر ۹", "version": P["version"],
           "t": int(time.time() * 1000), "why": why}
    out["stop_loss"], out["take_profit"] = out["sl"], out["tp1"]
    if equity:
        s = size_for(equity, stop_pct, lev)
        if s:
            out.update({"size_usd": s["notional_usd"],
                        "margin_usd": s["margin_usd"],
                        "risk_usd": s["risk_usd"]})
    return out


# ── ۶) پویش: بیت‌کوین روی همهٔ تایم‌ها ─────────────────────────────────────
def scan_btc(now_ms=None, fetch=None):
    """شوک بیت‌کوین روی هر پنج تایم — خروجی برای رادار و خط زنده."""
    f = fetch or fetch_klines
    found = {}
    for tf in TFS:
        cd = f("BTCUSDT", tf, 200)
        if not cd:
            continue
        s = detect_shock(cd, tf, now_ms)
        if s:
            s["volume"] = volume_confirmation(cd, s)
            found[tf] = s
    return found


def signal(symbol, tf="5m", equity=None):
    cd = fetch_klines(symbol, tf, 200)
    if not cd:
        return {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf,
                "why": "کندل نرسید — قانون ۱"}
    return decide(symbol, cd, tf, equity=equity)


# ── خودآزمایی ───────────────────────────────────────────────────────────────
def _mk(path, tf_ms=300_000, t0=0, vol=100.0):
    return [{"t": t0 + i * tf_ms, "o": p, "h": p * 1.002, "l": p * 0.998,
             "c": p, "v": vol} for i, p in enumerate(path)]


def _selftest():
    # بستر آرام + یک ایمپالس انفجاری با حجم
    base = [100.0 + (i % 3) * 0.02 for i in range(80)]
    cd = _mk(base)
    # کندل مخالف (اردر بلاک) بعد آرامش
    cd.append({"t": 80 * 300000, "o": 100.05, "h": 100.08, "l": 99.90,
               "c": 99.92, "v": 90})
    # ایمپالس: بدنهٔ بزرگ، حجم ۵ برابر، کلوز نزدیک سقف
    # ایمپالس ~۱.۶٪: هم شوک است، هم استاپش داخل بازهٔ مجاز می‌ماند
    cd.append({"t": 81 * 300000, "o": 99.92, "h": 101.60, "l": 99.90,
               "c": 101.50, "v": 700})
    s = detect_shock(cd, "5m")
    assert s and s["dir"] == "PUMP", s
    assert s["atr_mult"] >= P["shock_atr_mult"], s
    vc = volume_confirmation(cd, s)
    assert vc["full"], vc                      # همهٔ شش تأیید

    # حالت شکار پامپ: اهرم ۱۵ و استاپ پشت کف ایمپالس
    r = decide("BTCUSDT", cd, "5m", equity=1000)
    assert r["action"] == "LONG" and r["mode"] == "PUMP_CHASE", r
    assert r["leverage"] == P["lev_pump_chase"], r
    assert r["sl"] < r["entry"] < r["tp1"]
    assert r["margin_usd"] > 0 and r["risk_usd"] == 20.0, r

    # یک تأیید حجمی که برداشته شود → اهرم ۱۵ ممنوع
    cd2 = [dict(k) for k in cd]
    cd2[-1]["h"] = 103.0                       # ویک مخالف بزرگ، کلوز پایین دامنه
    vc2 = volume_confirmation(cd2, detect_shock(cd2, "5m"))
    assert not vc2["full"] and vc2["missing"], vc2
    r2 = decide("BTCUSDT", cd2, "5m", equity=1000)
    assert r2.get("mode") != "PUMP_CHASE", r2
    assert r2.get("leverage") in (None, 5, 6) or r2["action"] == "NO_SIGNAL", r2

    # بازگشت به اردر بلاک → حالت ۵–۶
    cd3 = [dict(k) for k in cd]
    for i in range(1, 6):                      # پولبک به سمت OB
        cd3.append({"t": (81 + i) * 300000, "o": 101.5 - i * 0.22,
                    "h": 101.6 - i * 0.22, "l": 101.3 - i * 0.22,
                    "c": 101.4 - i * 0.22, "v": 120})
    r3 = decide("BTCUSDT", cd3, "5m", equity=1000)
    assert r3["action"] == "LONG" and r3["mode"] == "SHOCK_FOLLOW", r3
    assert P["lev_follow_base"] <= r3["leverage"] <= P["lev_follow_max"], r3
    assert r3["sl"] < cd3[-1]["c"], r3

    # محافظ لیکویید: اهرم هرگز از ۱۰۰×۰.۵/استاپ رد نمی‌شود
    for st in (0.5, 1.0, 2.0, 3.0):
        for mode in ("SHOCK_FOLLOW", "PUMP_CHASE"):
            lv = leverage_for(mode, st)
            assert lv is None or lv <= int(50.0 / st), (mode, st, lv)
            assert lv is None or lv <= P["max_leverage_cap"]

    # بازار آرام = هیچ شوکی
    assert detect_shock(_mk([100.0 + (i % 2) * 0.01 for i in range(120)]),
                        "5m") is None
    assert decide("BTCUSDT", _mk([100.0] * 120), "5m")["action"] == "NO_SIGNAL"
    print("✓ خودآزمایی موتور شوک گذشت — شوک، اردر بلاک، تأیید ۱۰۰٪، اهرم")


import hashlib
import hmac
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not (ROOT / "signals").exists():
    ROOT = Path(".").resolve()
UP = ROOT / "signals" / "live-link.json"          # استراتژی → ما
DOWN = ROOT / "signals" / "link-commands.json"    # ما → استراتژی
REPO_RAW = "https://raw.githubusercontent.com/Auraliam/Liam-Trader-9/main"
PAGES = "https://auraliam.github.io/Liam-Trader-9"

MAX_EVENTS = 200            # حلقهٔ رویداد؛ فایل بی‌انتها نمی‌شود
MAX_CMDS = 50
MAX_BYTES = 64 * 1024
CMD_TTL_S = 3600

# فهرست سفید — هر چیز بیرون این، رد.
ALLOWED = {
    "set_param":  "یک پارامتر عددی موتور را عوض کن",
    "set_risk":   "ریسک هر معامله / سقف روزانه را عوض کن",
    "pause":      "موقتاً هیچ سیگنالی صادر نکن",
    "resume":     "دوباره فعال شو",
    "hint":       "دیتای تازه از حمید (متن + برچسب نماد)",
    "watch":      "این نمادها را ویژه زیر نظر بگیر",
    # دستور حمید ۲۴ اوت: «با موتور ۱ دقیقه در ارتباط باشی که بتوانی
    # آپدیت‌های تحلیل‌ها را بهش بدی.»
    #
    # عمداً **یک‌طرفه**: این فرمان فقط می‌تواند موتور را سخت‌گیرتر کند
    # (`avoid` یا `confidence_delta` منفی). هیچ میدانی برای بازکردن
    # دروازه، ساختن سیگنال، یا بالا بردن اطمینان ندارد — چون خروجی یک
    # ایجنت هرگز واقعیت تلقی نمی‌شود (قانون ۰۱ بند ۱۱). اگر روزی کسی
    # چنین میدانی اضافه کند، `hamid/test_scalp1m.py` چرخه را سرخ می‌کند.
    "analysis":   "آپدیت تحلیلِ مشورتی برای موتور ۱ دقیقه (فقط محدودکننده)",
    # دستور حمید ۱۹ اوت: «اگر سیگنالی دیدی برای اسکلپ مناسب است، سریع
    # دستور بده به داشبورد که آن پوزیشن فیوچرز را اجرا کند.»
    #
    # این تنها فرمانی است که به سفارش می‌رسد، و عمداً سخت‌گیرترین است:
    #   · فقط فیوچرز (product همیشه "futures"؛ اسپات پذیرفته نمی‌شود)
    #   · اهرم ≤ سقف داشبورد و ≤ محافظ لیکویید
    #   · نوشنال ≤ سقف سخت
    #   · mode پیش‌فرض "demo"؛ «live» فقط وقتی اجرا می‌شود که خودِ حمید
    #     روی ماشین داشبورد LIAM9_ALLOW_LIVE=1 گذاشته باشد. کانال به‌
    #     تنهایی هرگز پول واقعی را روشن نمی‌کند.
    "open_position": "اجرای پوزیشن فیوچرز روی داشبورد (اسکلپ سریع)",
}
# فرمان‌هایی که حتی با امضای درست هم رد می‌شوند (مرز ایمنی، نه سلیقه).
FORBIDDEN = {"enable_live", "live_execution", "set_secret", "exec", "eval",
             "shell", "disable_guard", "set_leverage_cap"}

# پارامترهایی که فرمان حق تغییرشان را دارد و بازهٔ مجازشان.
# بیرون این جدول = رد. بازه‌ها از محافظ‌های خودِ موتور می‌آیند.
PARAM_BOUNDS = {
    "shock_atr_mult": (1.5, 6.0),
    "shock_vol_mult": (1.2, 8.0),
    "shock_fresh_bars": (2, 40),
    "ob_max_age_bars": (5, 120),
    "rr_target": (1.0, 5.0),
    "min_net_rr": (0.8, 4.0),
    "min_stop_pct": (0.1, 2.0),
    "max_stop_pct": (0.5, 5.0),
    "risk_per_trade_pct": (0.25, 5.0),
    "min_quality": (0, 100),
}


# ── مرزهای سخت سفارش (تغییرشان از راه دور ممکن نیست) ──────────────────────
EXEC_MAX_NOTIONAL_USD = 200.0     # سقف سخت هر سفارش، حتی در دمو
EXEC_MAX_LEVERAGE = 20            # سقف داشبورد حمید
EXEC_LIQ_GUARD = 50.0             # اهرم ≤ ۵۰÷استاپ٪ (استاپ ≤ نصف لیکویید)
EXEC_TTL_S = 300                  # سفارش کهنه اجرا نمی‌شود؛ ۵ دقیقه


def validate_exec(order):
    """اعتبارسنجی سفارش فیوچرز. خروجی: لیست ایرادها (خالی = سالم).

    هرچه این‌جا رد شود، هیچ‌جای دیگری قابل دور زدن نیست — نه با امضا،
    نه با فرمان، نه با پارامتر."""
    errs = []
    if order.get("product") != "futures":
        errs.append("فقط فیوچرز؛ product باید futures باشد")
    sym = str(order.get("symbol") or "")
    if not sym.endswith("USDT") or len(sym) < 5:
        errs.append("نماد فیوچرز USDT نیست")
    if order.get("side") not in ("LONG", "SHORT"):
        errs.append("جهت نامعتبر")
    # دستور حمید (۲۰ اوت): پوزیشن بی‌استاپ/بی‌تارگت ممنوع؛ tp1 هم اجباری شد.
    for k in ("entry", "sl", "tp1", "stop_pct", "leverage", "notional_usd"):
        v = order.get(k)
        if not isinstance(v, (int, float)) or v <= 0:
            errs.append(f"«{k}» عددی مثبت نیست — استاپ و تارگت اجباری‌اند")
    if order.get("margin_mode") != "isolated":
        errs.append("مارجین باید isolated باشد — کراس ممنوع (دستور ۲۰ اوت)")
    if errs:
        return errs
    if order["leverage"] > EXEC_MAX_LEVERAGE:
        errs.append(f"اهرم {order['leverage']} بالاتر از سقف {EXEC_MAX_LEVERAGE}")
    if order["leverage"] > int(EXEC_LIQ_GUARD / order["stop_pct"]):
        errs.append("اهرم از محافظ فاصلهٔ لیکویید رد می‌کند")
    if order["notional_usd"] > EXEC_MAX_NOTIONAL_USD:
        errs.append(f"نوشنال {order['notional_usd']} بالاتر از سقف "
                    f"{EXEC_MAX_NOTIONAL_USD}")
    if order.get("mode") not in ("demo", "live"):
        errs.append("mode باید demo یا live باشد")
    d = order["side"]
    if (d == "LONG" and order["sl"] >= order["entry"]) or \
       (d == "SHORT" and order["sl"] <= order["entry"]):
        errs.append("استاپ سمت اشتباه ورود است")
    return errs


def make_exec_command(seq, symbol, side, entry, sl, tp1, stop_pct, leverage,
                      notional_usd, mode="demo", ttl_s=EXEC_TTL_S, **extra):
    """سفارش فیوچرز امضاشده. mode پیش‌فرض demo — «live» فقط با تأیید
    جداگانهٔ حمید روی ماشین داشبورد اجرا می‌شود."""
    order = {"product": "futures", "symbol": symbol, "side": side,
             "entry": float(entry), "sl": float(sl),
             "tp1": (float(tp1) if tp1 else None),
             "stop_pct": float(stop_pct), "leverage": int(leverage),
             "notional_usd": round(float(notional_usd), 2),
             "margin_mode": "isolated", "mode": mode, **extra}
    errs = validate_exec(order)
    if errs:
        raise ValueError("سفارش رد شد: " + "؛ ".join(errs))
    return make_command("open_position", seq, ttl_s=ttl_s, order=order)


def _secret():
    """کلید فقط از محیط. نبودش خطا نیست — یعنی حالت فقط-خواندن."""
    return (os.environ.get("LIAM9_LINK_SECRET") or "").encode() or None


def sign(payload, secret=None):
    """امضای قطعی روی JSON مرتب‌شده. کلید هرگز برنمی‌گردد."""
    s = secret if secret is not None else _secret()
    if not s:
        return None
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()
    return hmac.new(s, body, hashlib.sha256).hexdigest()


def verify(payload, signature, secret=None):
    """مقایسهٔ ثابت-زمان. بدون کلید = رد (نه قبول)."""
    if not signature:
        return False
    expect = sign(payload, secret)
    if not expect:
        return False
    return hmac.compare_digest(expect, signature)


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:                                    # noqa: BLE001
        return default


def _fetch_remote(rel):
    for base in (REPO_RAW, PAGES):
        try:
            req = urllib.request.Request(base + rel,
                                         headers={"User-Agent": "liam9-link"})
            with urllib.request.urlopen(req, timeout=12) as r:
                return json.load(r)
        except Exception:                                # noqa: BLE001
            continue
    return None


class Link:
    """خط زنده. `role` فقط برچسب است تا در گزارش معلوم باشد چه کسی نوشته."""

    def __init__(self, role="strategy", up=None, down=None, remote=True):
        self.role = role
        self.up = Path(up) if up else UP
        self.down = Path(down) if down else DOWN
        self.remote = remote
        self.paused = False
        self.last_seq = 0
        self.applied = []
        self.orders = []          # سفارش‌های تحویل‌شده به داشبورد

    # ── بالا-رو ───────────────────────────────────────────────────────
    def _append(self, kind, data):
        doc = _read_json(self.up, {"panel": "لیام تریدر ۹", "events": []})
        ev = {"t": int(time.time() * 1000), "kind": kind, "role": self.role,
              "data": data}
        sig = sign(ev)
        if sig:
            ev["sig"] = sig                # قابل راستی‌آزمایی، نه محرمانه
        doc.setdefault("events", []).append(ev)
        doc["events"] = doc["events"][-MAX_EVENTS:]
        doc["updated"] = ev["t"]
        doc["signed"] = bool(sig)
        self.up.parent.mkdir(parents=True, exist_ok=True)
        self.up.write_text(json.dumps(doc, ensure_ascii=False))
        return ev

    def heartbeat(self, state):
        """ضربان: زنده‌ام، این را می‌بینم، این وضعیتم است."""
        return self._append("HEARTBEAT", state)

    def event(self, kind, data):
        """رویداد معنادار: تصمیم، رد شدن با دلیل، شوک، خطا."""
        return self._append(kind, data)

    # ── پایین-رو ──────────────────────────────────────────────────────
    def pull(self):
        """فرمان‌های تازه: فقط امضادار، تازه، و با seq بزرگ‌تر از آخرین."""
        doc = None
        if self.remote:
            doc = _fetch_remote("/signals/link-commands.json")
        if doc is None:
            doc = _read_json(self.down, {"commands": []})
        out, now = [], time.time()
        for c in (doc.get("commands") or [])[-MAX_CMDS:]:
            body = {k: v for k, v in c.items() if k != "sig"}
            if not verify(body, c.get("sig")):
                continue                              # امضا غلط یا بی‌کلید
            if body.get("type") in FORBIDDEN or body.get("type") not in ALLOWED:
                continue
            seq = body.get("seq")
            if not isinstance(seq, int) or seq <= self.last_seq:
                continue                              # بازپخش یا قدیمی
            if float(body.get("expires", 0)) < now:
                continue                              # منقضی
            out.append(body)
        for c in out:
            self.last_seq = max(self.last_seq, c["seq"])
        return out

    def apply(self, commands, params=None, risk=None):
        """اعمال امن. هر فرمان اثرش را روی خط بالا-رو هم گزارش می‌دهد."""
        done = []
        for c in commands:
            t = c["type"]
            res = {"seq": c["seq"], "type": t, "ok": False, "why": ""}
            if t == "pause":
                self.paused, res["ok"] = True, True
            elif t == "resume":
                self.paused, res["ok"] = False, True
            elif t == "hint":
                txt = str(c.get("text", ""))[:500]
                res["ok"], res["hint"] = bool(txt), txt
            elif t == "watch":
                syms = [str(s)[:20] for s in (c.get("symbols") or [])][:50]
                res["ok"], res["symbols"] = bool(syms), syms
            elif t == "analysis":
                # سقف‌خورده در همین لایه، نه فقط در مصرف‌کننده: فرمانی که
                # اطمینان را **بالا** ببرد این‌جا به صفر بریده می‌شود.
                sym = str(c.get("sym") or "")[:20].upper()
                delta = c.get("confidence_delta", 0)
                delta = (max(-40.0, min(0.0, float(delta)))
                         if isinstance(delta, (int, float)) else 0.0)
                res.update(ok=bool(sym), sym=sym,
                           note=str(c.get("note", ""))[:400],
                           avoid=bool(c.get("avoid")),
                           confidence_delta=delta)
                if not sym:
                    res["why"] = "بدون نماد — آپدیت تحلیل بی‌هدف پذیرفته نیست"
            elif t == "set_param":
                k, v = c.get("key"), c.get("value")
                lo_hi = PARAM_BOUNDS.get(k)
                if params is None:
                    res["why"] = "موتوری برای تنظیم داده نشده"
                elif not lo_hi:
                    res["why"] = f"پارامتر «{k}» قابل تنظیم از راه دور نیست"
                elif not isinstance(v, (int, float)):
                    res["why"] = "مقدار عددی نیست"
                elif not (lo_hi[0] <= v <= lo_hi[1]):
                    res["why"] = f"مقدار بیرون بازهٔ مجاز {lo_hi}"
                else:
                    params[k] = v
                    res["ok"] = True
            elif t == "open_position":
                # کانال فقط سفارش را **تحویل** می‌دهد؛ اجرا کار داشبورد است.
                # مرز پول واقعی این‌جاست: mode="live" فقط وقتی عبور می‌کند
                # که خودِ حمید روی ماشین داشبورد LIAM9_ALLOW_LIVE=1 گذاشته
                # باشد. نبودش = تبدیل به دمو، نه رد کامل (تا اسکلپ نخوابد).
                order = c.get("order") or {}
                errs = validate_exec(order)
                if errs:
                    res["why"] = "؛ ".join(errs)
                elif self.paused:
                    res["why"] = "موتور متوقف است"
                else:
                    if order.get("mode") == "live" and \
                            os.environ.get("LIAM9_ALLOW_LIVE") != "1":
                        order = dict(order, mode="demo",
                                     downgraded="LIAM9_ALLOW_LIVE تنظیم نیست")
                    res["ok"], res["order"] = True, order
                    self.orders.append(order)
            elif t == "set_risk":
                k, v = c.get("key"), c.get("value")
                if risk is None:
                    res["why"] = "دفتر ریسکی داده نشده"
                elif k not in ("risk_per_trade_pct", "daily_loss_cap_pct"):
                    res["why"] = "این کلید ریسک قابل تنظیم نیست"
                elif not isinstance(v, (int, float)) or not (0.1 <= v <= 10):
                    res["why"] = "مقدار بیرون بازهٔ امن (۰.۱ تا ۱۰)"
                else:
                    risk[k] = v
                    res["ok"] = True
            done.append(res)
            self.applied.append(res)
        if done:
            self.event("COMMANDS_APPLIED", done)
        return done


# ── سمت ما: ساخت فرمان امضاشده ─────────────────────────────────────────────
def make_command(cmd_type, seq, ttl_s=CMD_TTL_S, **fields):
    """فرمان امضاشده می‌سازد. بدون کلید، امضا None است و گیرنده ردش می‌کند."""
    if cmd_type in FORBIDDEN or cmd_type not in ALLOWED:
        raise ValueError(f"فرمان «{cmd_type}» مجاز نیست")
    body = {"type": cmd_type, "seq": int(seq),
            "expires": time.time() + ttl_s, **fields}
    s = sign(body)
    if s:
        body["sig"] = s
    return body


def push_command(cmd, path=None):
    """فرمان را در دفتر پایین-رو می‌گذارد (سقف تعداد و اندازه رعایت می‌شود)."""
    p = Path(path) if path else DOWN
    doc = _read_json(p, {"panel": "لیام تریدر ۹", "commands": []})
    doc.setdefault("commands", []).append(cmd)
    doc["commands"] = doc["commands"][-MAX_CMDS:]
    doc["updated"] = int(time.time() * 1000)
    blob = json.dumps(doc, ensure_ascii=False)
    if len(blob.encode()) > MAX_BYTES:
        doc["commands"] = doc["commands"][-10:]
        blob = json.dumps(doc, ensure_ascii=False)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(blob)
    return doc


def next_seq(path=None):
    doc = _read_json(Path(path) if path else DOWN, {"commands": []})
    seqs = [c.get("seq", 0) for c in (doc.get("commands") or [])
            if isinstance(c.get("seq"), int)]
    return (max(seqs) + 1) if seqs else 1


# ── خودآزمایی ───────────────────────────────────────────────────────────────
def _link_selftest():
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    up, down = tmp / "live-link.json", tmp / "link-commands.json"
    os.environ["LIAM9_LINK_SECRET"] = "test-secret-not-a-real-key"

    link = Link(role="test", up=up, down=down, remote=False)
    link.heartbeat({"state": "WATCHING", "px": 100})
    doc = json.loads(up.read_text())
    assert doc["events"][-1]["kind"] == "HEARTBEAT" and doc["signed"]
    assert "LIAM9_LINK_SECRET" not in up.read_text()      # کلید هرگز نوشته نشود
    assert "test-secret" not in up.read_text()

    # امضا: دستکاری محتوا = رد
    ev = doc["events"][-1]
    body = {k: v for k, v in ev.items() if k != "sig"}
    assert verify(body, ev["sig"])
    body["data"]["px"] = 999
    assert not verify(body, ev["sig"])

    # فرمان مجاز، امضادار، تازه → اعمال می‌شود
    params = {"shock_vol_mult": 2.0}
    push_command(make_command("set_param", next_seq(down),
                              key="shock_vol_mult", value=2.5), down)
    cmds = link.pull()
    assert len(cmds) == 1, cmds
    res = link.apply(cmds, params=params)
    assert res[0]["ok"] and params["shock_vol_mult"] == 2.5

    # بازپخش همان فرمان = رد
    assert link.pull() == []

    # مقدار بیرون بازه = رد
    push_command(make_command("set_param", next_seq(down),
                              key="shock_vol_mult", value=99), down)
    res2 = link.apply(link.pull(), params=params)
    assert not res2[0]["ok"] and params["shock_vol_mult"] == 2.5

    # پارامتر خارج از فهرست = رد
    push_command(make_command("set_param", next_seq(down),
                              key="lev_pump_chase", value=50), down)
    res3 = link.apply(link.pull(), params={"lev_pump_chase": 15})
    assert not res3[0]["ok"], res3

    # فرمان ممنوع اصلاً ساخته نمی‌شود
    for bad in ("enable_live", "shell", "set_secret"):
        try:
            make_command(bad, 99)
            raise AssertionError(f"فرمان ممنوع ساخته شد: {bad}")
        except ValueError:
            pass
    # و اگر دستی هم در فایل کاشته شود، رد می‌شود
    forged = {"type": "enable_live", "seq": 500,
              "expires": time.time() + 60}
    forged["sig"] = sign(forged)
    push_command(forged, down)
    assert all(c["type"] != "enable_live" for c in link.pull())

    # امضای غلط = رد
    bad = {"type": "pause", "seq": 600, "expires": time.time() + 60,
           "sig": "00" * 32}
    push_command(bad, down)
    assert all(c["seq"] != 600 for c in link.pull())

    # منقضی = رد
    old = {"type": "pause", "seq": 700, "expires": time.time() - 1}
    old["sig"] = sign(old)
    push_command(old, down)
    assert all(c["seq"] != 700 for c in link.pull())

    # بدون کلید: هیچ فرمانی پذیرفته نمی‌شود (رد امن، نه قبول)
    ok_cmd = make_command("pause", 800)
    push_command(ok_cmd, down)
    del os.environ["LIAM9_LINK_SECRET"]
    link2 = Link(role="test2", up=up, down=down, remote=False)
    assert link2.pull() == []
    link2.heartbeat({"state": "بدون کلید"})              # ضربان باز هم می‌نویسد
    assert json.loads(up.read_text())["events"][-1]["kind"] == "HEARTBEAT"

    # حلقهٔ رویداد: فایل بی‌انتها نمی‌شود
    os.environ["LIAM9_LINK_SECRET"] = "test-secret-not-a-real-key"
    l3 = Link(role="t3", up=up, down=down, remote=False)
    for i in range(MAX_EVENTS + 30):
        l3.heartbeat({"i": i})
    assert len(json.loads(up.read_text())["events"]) == MAX_EVENTS

    # pause/resume
    l3.apply([{"type": "pause", "seq": 1}])
    assert l3.paused
    l3.apply([{"type": "resume", "seq": 2}])
    assert not l3.paused
    del os.environ["LIAM9_LINK_SECRET"]
    print("✓ خودآزمایی خط زنده گذشت — امضا، ضدبازپخش، فهرست سفید، مرز لایو")


# ══════════════════════════════════════════════════════════════════════════
#  پوستهٔ کلاسی برای داشبورد
# ══════════════════════════════════════════════════════════════════════════
try:
    from strategy_base import BaseStrategy            # قالب رایج داشبوردها
except Exception:                                     # noqa: BLE001
    try:
        from base_strategy import BaseStrategy
    except Exception:                                 # noqa: BLE001
        class BaseStrategy:                           # پایهٔ خنثی
            pass


class RiskBook:
    """قوانین ریسک داشبورد حمید، کد شده — قبل از هر ورود جواب می‌دهد
    «چقدر، یا اصلاً نه»: ریسک ۲٪ · سقف روزانه ۵٪ · ۵ پوزیشن · اهرم ۲۰."""

    def __init__(self, equity=None, cfg=None):
        self.equity = float(equity) if equity else None
        self.cfg = {"risk_per_trade_pct": P["risk_per_trade_pct"],
                    "daily_loss_cap_pct": 5.0, "max_open_positions": 5,
                    "max_leverage": P["max_leverage_cap"]}
        self.cfg.update(cfg or {})
        self.day_loss_pct, self.open_positions = 0.0, 0

    def approve(self, stop_pct, lev):
        c = self.cfg
        if self.open_positions >= c["max_open_positions"]:
            return False, {"reason": f"سقف {c['max_open_positions']} پوزیشن پر است"}
        if self.day_loss_pct >= c["daily_loss_cap_pct"]:
            return False, {"reason": f"سقف ضرر روزانه {c['daily_loss_cap_pct']}٪ "
                                     "خورده — توقف خودکار"}
        lev = min(lev or 0, c["max_leverage"])
        if lev < 2:
            return False, {"reason": "اهرم مجاز کمتر از حداقل عملی"}
        info = {"leverage": lev}
        if self.equity:
            s = size_for(self.equity, stop_pct, lev)
            if s:
                info.update(s)
        left = c["daily_loss_cap_pct"] - self.day_loss_pct
        if left < c["risk_per_trade_pct"] * 2:
            info["warn"] = (f"فقط {left:.1f}٪ تا سقف روزانه مانده — جا برای "
                            f"{left / c['risk_per_trade_pct']:.1f} باخت کامل")
        return True, info

    def on_open(self):
        self.open_positions += 1

    def on_close(self, r_multiple):
        self.open_positions = max(0, self.open_positions - 1)
        if r_multiple < 0:
            self.day_loss_pct += abs(r_multiple) * self.cfg["risk_per_trade_pct"]

    def new_day(self):
        self.day_loss_pct = 0.0


class Liam9ShockStrategy(BaseStrategy):
    """شوک بیت‌کوین → اردر بلاک (اهرم ۵–۶) یا شکار پامپ (اهرم ۱۵ با تأیید ۱۰۰٪).

    هر فراخوانی: فرمان‌های امضاشده را می‌گیرد، تصمیم می‌سازد، و تصمیم یا
    دلیل ردش را روی خط زنده گزارش می‌دهد — پس حمید لحظه‌ای می‌بیند موتور
    چه دید و چرا نرفت."""

    meta = {
        "name": "لیام تریدر ۹ — شوک بیت‌کوین",
        "id": "liam9-shock",
        "version": P["version"],
        "author": "لیام تریدر ۹",
        "timeframes": TFS,
        "market": "crypto-futures",
        "risk_profile": {"risk_per_trade_pct": P["risk_per_trade_pct"],
                         "leverage_follow": [P["lev_follow_base"],
                                             P["lev_follow_max"]],
                         "leverage_pump_chase": P["lev_pump_chase"],
                         "max_leverage": P["max_leverage_cap"],
                         "stop_pct_range": [P["min_stop_pct"],
                                            P["max_stop_pct"]]},
        "description": ("شوک روی هر تایم (بدنه ≥۲.۵×ATR + کف تایم + حجم "
                        "≥۲× میانه) → ورود روی بازگشت به اردر بلاک ایمپالس "
                        "با اهرم ۵–۶؛ شکار پامپ با اهرم ۱۵ فقط با هر شش "
                        "تأیید حجمی. NO_SIGNAL تصمیم معتبر است."),
    }

    def __init__(self, *a, **kw):
        try:
            super().__init__(*a, **kw)
        except Exception:                             # noqa: BLE001
            pass
        self.equity = kw.get("equity")
        self.book = RiskBook(self.equity)
        self.link = Link(role="dashboard-shock", remote=True)
        self.tf = kw.get("timeframe") or "5m"
        self.btc_shocks = {}

    # ── ورودی‌های رایج داشبورد ───────────────────────────────────────
    def generate_signal(self, symbol, candles=None, timeframe=None, **kw):
        tf = timeframe or self.tf
        cmds = self.link.pull()
        if cmds:
            self.link.apply(cmds, params=P, risk=self.book.cfg)
        if self.link.paused:
            return {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf,
                    "why": "با فرمان امضاشده متوقف شده", "panel": "لیام تریدر ۹"}
        cd = candles if candles and len(candles) >= 60 else \
            fetch_klines(symbol, tf, 200)
        if not cd:
            return {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf,
                    "why": "کندل نرسید — قانون ۱: حدس ممنوع"}
        sig = decide(symbol, cd, tf, equity=kw.get("equity") or self.equity,
                     btc_shock=self.btc_shocks.get(tf))
        if sig["action"] != "NO_SIGNAL":
            ok, info = self.book.approve(sig["stop_pct"], sig["leverage"])
            sig["risk"] = info
            if not ok:
                sig = {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf,
                       "why": "ریسک اجازه نداد: " + info["reason"],
                       "panel": "لیام تریدر ۹"}
            else:
                sig["leverage"] = info["leverage"]
                if info.get("notional_usd"):
                    sig["size_usd"] = info["notional_usd"]
                    sig["margin_usd"] = info["margin_usd"]
                if info.get("warn"):
                    sig.setdefault("why", []).append("⚠️ " + info["warn"])
        self.link.event("SIGNAL" if sig["action"] != "NO_SIGNAL" else "SKIP",
                        {k: sig.get(k) for k in
                         ("symbol", "tf", "action", "mode", "entry", "sl",
                          "tp1", "leverage", "stop_pct", "volume_score", "why")})
        return sig

    def on_bar(self, symbol, candles=None, **kw):
        return self.generate_signal(symbol, candles=candles, **kw)

    def run(self, symbol, **kw):
        return self.generate_signal(symbol, **kw)

    # ── بستر: شوک خود بیت‌کوین، برای همهٔ نمادها ─────────────────────
    def refresh_btc(self):
        """یک بار در هر چرخه صدا بزن؛ بعدش همهٔ نمادها بسترشان را دارند."""
        self.btc_shocks = scan_btc()
        self.link.heartbeat({"btc_shocks": {tf: {"dir": s["dir"],
                                                 "pct": s["move_pct"],
                                                 "vol": s["vol_mult"]}
                                            for tf, s in self.btc_shocks.items()}})
        return self.btc_shocks

    # ── مدیریت معامله: نردبان تریل حمید ──────────────────────────────
    def manage_position(self, position, candle):
        long = position["action"] == "LONG"
        sl = position.get("sl_current", position["sl"])
        hi, lo = candle["h"], candle["l"]
        if (long and lo <= sl) or (not long and hi >= sl):
            return {"event": "STOP", "price": sl}
        if (long and hi >= position["tp1"]) or (not long and lo <= position["tp1"]):
            return {"event": "TARGET", "price": position["tp1"]}
        t1 = position["trail"]["step1_at"]
        if (long and hi >= t1) or (not long and lo <= t1):
            be = position["entry"] * (1.0015 if long else 0.9985)
            if (long and sl < be) or (not long and sl > be):
                return {"event": "TRAIL", "sl": be}
        return {"event": "HOLD"}

    # ── ممیزی: موتور ریسک داشبورد با این استراتژی تداخل دارد؟ ────────
    def audit(self, risk=None):
        out = {"contract": self.meta["risk_profile"], "conflicts": [],
               "notes": []}
        if risk is None:
            out["notes"].append("آبجکت ریسک داده نشد — بررسی دستی لازم است")
            return out
        def dig(*names):
            for n in names:
                if isinstance(risk, dict) and n in risk:
                    return risk[n]
                if hasattr(risk, n):
                    return getattr(risk, n)
            return None
        lev = dig("leverage_cap", "max_leverage", "maxLeverage")
        if lev is not None and lev < P["lev_pump_chase"]:
            out["notes"].append(
                f"سقف اهرم داشبورد {lev}× زیر ۱۵× است — شکار پامپ با همان "
                "سقف اجرا می‌شود (سایز کوچک‌تر، لبه دست‌نخورده)")
        ms = dig("min_stop_pct", "min_stop_distance_pct")
        if ms is not None and ms > P["max_stop_pct"]:
            out["conflicts"].append(
                f"کف استاپ داشبورد {ms}٪ بالاتر از سقف {P['max_stop_pct']}٪ "
                "این موتور — همهٔ ستاپ‌ها در سکوت رد می‌شوند")
        fee = dig("fee_pct", "taker_fee", "commission")
        if fee is not None and float(fee) < P["fee_round_trip_pct"] / 3:
            out["conflicts"].append(
                f"کارمزد داشبورد {fee}٪ خیلی پایین‌تر از واقعیت "
                f"({P['fee_round_trip_pct']}٪) — RR خوش‌بین می‌شود")
        return out


def _dash_selftest():
    _selftest()                                        # موتور شوک
    _link_selftest()                                   # خط زنده
    s = Liam9ShockStrategy(equity=1000)
    assert isinstance(s.meta, dict) and s.meta.get("id") == "liam9-shock"
    for ep in ("generate_signal", "on_bar", "run", "manage_position", "audit"):
        assert callable(getattr(s, ep)), ep
    # تصمیم روی کندل تزریقی، بدون شبکه
    base = [100.0 + (i % 3) * 0.02 for i in range(80)]
    cd = [{"t": i * 300000, "o": p, "h": p * 1.002, "l": p * 0.998, "c": p,
           "v": 100.0} for i, p in enumerate(base)]
    cd.append({"t": 80 * 300000, "o": 100.05, "h": 100.08, "l": 99.90,
               "c": 99.92, "v": 90})
    cd.append({"t": 81 * 300000, "o": 99.92, "h": 101.60, "l": 99.90,
               "c": 101.50, "v": 700})
    r = s.generate_signal("BTCUSDT", candles=cd, timeframe="5m")
    assert r["action"] == "LONG" and r["mode"] == "PUMP_CHASE", r
    assert r["leverage"] <= P["max_leverage_cap"] and r.get("size_usd"), r
    # سقف پوزیشن داشبورد واقعاً جلو می‌گیرد
    for _ in range(5):
        s.book.on_open()
    r2 = s.generate_signal("BTCUSDT", candles=cd, timeframe="5m")
    assert r2["action"] == "NO_SIGNAL" and "پوزیشن" in r2["why"], r2
    # ممیزی تداخل
    a = s.audit({"min_stop_pct": 5.0, "max_leverage": 20})
    assert a["conflicts"], a
    print("✓ خودآزمایی فایل داشبورد گذشت — کلاس، meta، ریسک، خط زنده")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _dash_selftest()
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        sym = args[0] if args else "BTCUSDT"
        st = Liam9ShockStrategy(equity=1000)
        print("شوک بیت‌کوین:", json.dumps(st.refresh_btc(), ensure_ascii=False)[:400])
        for tf in TFS:
            out = st.generate_signal(sym, timeframe=tf)
            print(tf, json.dumps(out, ensure_ascii=False)[:220])
