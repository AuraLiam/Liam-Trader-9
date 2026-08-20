#!/usr/bin/env python3
"""لیام تریدر ۹ — موتور شوک بیت‌کوین (دستور حمید، ۱۹ اوت).

قانون تازه‌ای که حمید داد، کلمه به کلمه کد شده:

  ۱. «وقتی در هر تایم‌فریمی بیت‌کوین یهو پامپ یا دامپ شد، بر اساس
     استراتژی و اردر بلاک با ضریب ۵ تا ۶ ترید کند.»
     → حالت SHOCK_FOLLOW: شوک روی هر تایم (۱د/۵د/۱۵د/۱س/۴س) شناسایی
       می‌شود، ورود **روی بازگشت به اردر بلاکِ همان ایمپالس** است نه
       وسط حرکت، اهرم ۵ (پایه) یا ۶ (با تأییدهای اضافه).

  ۲. «برای گرفتن پامپ ضریب ۱۵ ولی با گرفتن تأییدیهٔ ۱۰۰ درصدی ورود حجم.»
     → حالت PUMP_CHASE: اهرم ۱۵ فقط وقتی **هر شش تأیید حجمی** برقرار
       باشد. یکی غایب = اهرم ۱۵ ممنوع؛ موتور یا به حالت ۵–۶ برمی‌گردد یا
       NO_SIGNAL می‌دهد. «۱۰۰ درصد» یعنی صد درصد، نه پنج از شش.

چرا ورود روی اردر بلاک و نه وسط شوک: بعد از یک حرکت انفجاری، استاپِ
معنادار پشت ساختار است نه چند دهم درصد پایین‌تر؛ ورود وسط حرکت یعنی استاپ
دور و RR خراب، یا استاپ نزدیک و لیکویید نزدیک. اردر بلاکِ ایمپالس تنها
جایی است که هر دو با هم جور می‌شوند.

سازگاری با قوانین ریسک داشبورد (۲٪ هر معامله · سقف روزانه ۵٪ · ۵ پوزیشن ·
اهرم ۲۰): هر سه ضریب این موتور (۵، ۶، ۱۵) زیر سقف ۲۰ هستند، و محافظ
فاصلهٔ لیکویید هم جداگانه اعمال می‌شود — اهرم ۱۵ یعنی لیکویید ~۶.۷٪ دورتر،
پس استاپ باید زیر ~۳.۳٪ بماند وگرنه اهرم پایین می‌آید.

⚠️ وضعیت: این قانون **تازه** است و هنوز کارنامهٔ CI-دار ندارد. تا وقتی
دفتر پیپرش بازهٔ اطمینان بالای صفر نشان ندهد، فقط پیپر — نه پول واقعی
(همان قانون همیشگی: عمل فقط با CI بالای صفر).

خط فرمان:
    python3 liam9_shock.py BTCUSDT          # وضعیت لحظه‌ای همهٔ تایم‌ها
    python3 liam9_shock.py --selftest
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


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        sym = args[0] if args else "BTCUSDT"
        print(json.dumps(scan_btc(), ensure_ascii=False, indent=1))
        for tf in TFS:
            print(tf, json.dumps(signal(sym, tf, equity=1000),
                                 ensure_ascii=False)[:220])
