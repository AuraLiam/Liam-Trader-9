#!/usr/bin/env python3
"""لیام تریدر ۹ — موتور تایم یک ساعته برای داشبورد (دستور حمید، ۱۹ اوت).

⚠️ وضعیت سنجیده (۱۹ اوت، کندل واقعی، ۶۳ نماد، ۸۱۵ معامله):
    برد ۵۸.۳٪ ولی میانگین ‎−۰.۱۱۱R خالص، CI ۹۵٪ = [−۰.۱۸۲، −۰.۰۳۶]
    یعنی **کاملاً زیر صفر** — این موتور هنوز لبه ندارد. هیچ فیلتر ورودی
    هم نجاتش نداد (تأیید کندلی و کیفیت ≥۷۰ فقط n=۱۵ داشتند، شورت‌تنها
    CI = [−۰.۱۷۳، +۰.۰۰۹]). پس: **فقط پیپر**، نه پول واقعی، تا وقتی
    اندازه‌گیری تازه‌ای CI بالای صفر بدهد.

    یک نکتهٔ مهم دربارهٔ همین عدد: در آن بک‌تست لایهٔ تجربه خاموش بود
    (exp_used صفر از ۸۱۵) — چون کارنامهٔ تجربه از دفتر همان بازهٔ زمانی
    ساخته می‌شود و استفاده از آن در گذشته «نگاه به آینده» است. اثر آن
    لایه فقط رو به جلو (پیپر) قابل اثبات است، نه در بک‌تست.

ساخته‌شده دقیقاً روی «قوانین سراسری مدیریت ریسک و سرمایه»ی داشبورد خودت:

    ریسک هر معامله ۲٪ · سقف ضرر روزانه ۵٪ · ۵ پوزیشن هم‌زمان · اهرم ۲۰

هر چهارتا این‌جا کد شده‌اند، نه توصیه‌شده — `RiskBook` قبل از هر ورود
جواب می‌دهد «چقدر، یا اصلاً نه».

سلسله‌مراتب (همان منشور، یک پله بالاتر چون تایم اجرا ۱ ساعته است):
    روزانه/۴ساعته = میدان نبرد  →  ۱ ساعته = ستاپ و ورود

چرا این تایم با اهرم ۲۰ سازگار است (برخلاف ۱ دقیقه):
    اهرم ۲۰ یعنی لیکویید حدود ۵٪ دورتر. استاپ یک‌ساعتهٔ ما ۰.۸–۲.۲٪ است،
    یعنی همیشه کمتر از نصف راه تا لیکویید — سقف ۲۰ داشبورد اصلاً به این
    استراتژی نمی‌خورد. کارمزد هم روی استاپ بزرگ‌تر سهم کوچکی از R دارد
    (استاپ ۱.۵٪ → کارمزد ۰.۱۰R)، پس دام کارمزدِ اسکلپ این‌جا نیست.

یک حساب که باید بدانی (از همان تنظیمات خودت):
    سقف روزانه ۵٪ ÷ ریسک ۲٪ = ۲.۵ ضرر کامل و بعد داشبورد می‌ایستد.
    با نرخ برد ۵۰٪، احتمال دو باخت پشت‌سرهم ۲۵٪ است — یعنی تقریباً یک روز
    از هر چهار روز، ربات پیش از ظهر خاموش می‌شود. اگر می‌خواهی موتور
    نفس بکشد، ریسک هر معامله را ۱٪ بگذار: همان سقف ۵٪ آن‌وقت جای ۵ باخت
    می‌دهد. تصمیمش با توست؛ کد با هر دو کار می‌کند و اگر ۲٪ بماند خودش
    در خروجی هشدار می‌دهد.

استفاده در داشبورد:
    کلاس `Liam9H1Strategy` (BaseStrategy + meta) — سه نقطهٔ ورود رایج دارد.
    یا مستقیم:  sig = liam9_h1_strategy.signal("BTCUSDT")

خط فرمان:
    python3 liam9_h1_strategy.py BTCUSDT
    python3 liam9_h1_strategy.py --selftest
"""
import json
import time
import urllib.request

REPO_RAW = "https://raw.githubusercontent.com/Auraliam/liam-trader-9/main"
PAGES = "https://auraliam.github.io/liam-trader-9"
PARAMS_PATH = "/signals/h1-params.json"
EXPERIENCE_PATH = "/signals/experience.json"

# ── پارامترهای موتور یک‌ساعته ───────────────────────────────────────────────
P = {
    "version": "liam9-h1-1.0",
    # ساختار
    "ema_fast": 50, "ema_slow": 200,
    "swing_win": 24,               # ۲۴ کندل ۱س = یک شبانه‌روز
    "pullback_min": 0.25,          # پولبک واقعی، نه لرزش
    "pullback_max": 0.85,          # پولبکِ بلعنده = ساختار مشکوک
    # تأیید
    "ibs_long_max": 0.35,          # روی ۱س کمی بازتر از ۱۵د (کندل بزرگ‌تر)
    "ibs_short_min": 0.65,
    # ریسک هندسی
    "atr_n": 14, "atr_mult": 1.1,  # استاپ بیرون نویز ۱س
    "min_stop_pct": 0.60,          # زیر این، کارمزد و لغزش R را می‌خورد
    "max_stop_pct": 2.20,          # با اهرم ۲۰، نصف راه تا لیکویید
    "rr_target": 2.2,              # تارگت اول
    "min_net_rr": 1.8,             # بعد از کارمزد
    "fee_round_trip_pct": 0.15,
    # تجربه و کیفیت
    "exp_min_n": 12, "exp_veto_mean_r": -0.25, "min_quality": 55,
    # مدیریت معامله (قانون تریل حمید)
    "trail_first": 1 / 3, "trail_second": 2 / 3,
    "breakeven_pad_pct": 0.15,     # سربه‌سرِ کارمزددار
    "max_hold_bars": 48,           # دو شبانه‌روز؛ بعدش ستاپ مرده است
}

# ── قوانین ریسک داشبورد حمید (عکس تنظیمات، ۱۹ اوت) ─────────────────────────
RISK = {
    "risk_per_trade_pct": 2.0,
    "daily_loss_cap_pct": 5.0,
    "max_open_positions": 5,
    "max_leverage": 20,
    "liq_guard_ratio": 0.5,        # استاپ حداکثر نصف راه تا لیکویید
}

EXPERIENCE = {}

VENUES = [
    ("https://api.mexc.com/api/v3/klines?symbol={s}&interval={i}&limit={n}", "mexc"),
    ("https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={g}&interval={i}&limit={n}", "gate"),
    ("https://fapi.binance.com/fapi/v1/klines?symbol={s}&interval={i}&limit={n}", "binance"),
]


# ── داده ────────────────────────────────────────────────────────────────────
def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "liam9-h1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def sync_params():
    for base in (REPO_RAW, PAGES):
        try:
            d = _get(base + PARAMS_PATH)
            if isinstance(d, dict) and d.get("version"):
                P.update(d)
                return P["version"]
        except Exception:                                # noqa: BLE001
            continue
    return None


def sync_experience():
    for base in (REPO_RAW, PAGES):
        try:
            d = _get(base + EXPERIENCE_PATH)
            if isinstance(d, dict) and isinstance(d.get("index"), dict):
                EXPERIENCE.clear()
                EXPERIENCE.update(d["index"])
                return len(EXPERIENCE)
        except Exception:                                # noqa: BLE001
            continue
    return 0


def sync_all():
    return {"params": sync_params(), "experience_pairs": sync_experience()}


def fetch_klines(symbol, interval="1h", n=400):
    for tmpl, venue in VENUES:
        url = tmpl.format(s=symbol, n=n, i=interval,
                          g=symbol.replace("USDT", "_USDT"))
        try:
            rows = _get(url)
            out = []
            for k in rows:
                if venue == "gate":
                    out.append({"t": int(k[0]) * 1000, "o": float(k[5]),
                                "h": float(k[3]), "l": float(k[4]),
                                "c": float(k[2])})
                else:
                    out.append({"t": int(k[0]), "o": float(k[1]),
                                "h": float(k[2]), "l": float(k[3]),
                                "c": float(k[4])})
            if len(out) >= 60:
                return out
        except Exception:                                # noqa: BLE001
            continue
    return None


# ── ابزار قطعی ──────────────────────────────────────────────────────────────
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


def ibs(k):
    rng = k["h"] - k["l"]
    return (k["c"] - k["l"]) / rng if rng > 0 else 0.5


def trend(cd, fast=None, slow=None, win=None):
    """جهت میدان: EMA سریع/کند + سوینگ‌های واقعی. کم‌داده = None (نه حدس)."""
    fast = fast or P["ema_fast"]
    slow = slow or P["ema_slow"]
    win = win or P["swing_win"]
    closes = [k["c"] for k in cd]
    ef, es = ema(closes, fast), ema(closes, slow)
    if ef is None or es is None or len(cd) < win * 2:
        return None
    px = closes[-1]
    hi_now = max(k["h"] for k in cd[-win:])
    hi_prev = max(k["h"] for k in cd[-2 * win:-win])
    lo_now = min(k["l"] for k in cd[-win:])
    lo_prev = min(k["l"] for k in cd[-2 * win:-win])
    if ef > es and px > es and hi_now >= hi_prev:
        return "up"
    if ef < es and px < es and lo_now <= lo_prev:
        return "down"
    return "range"


def candle_confirm(cd, direction):
    """کندل تأییدی ۱س — بدنهٔ قاطع، پین‌بار، بلعنده. امتیاز، نه دروازه."""
    if len(cd) < 3:
        return None, []
    k, p = cd[-1], cd[-2]
    rng = k["h"] - k["l"]
    if rng <= 0:
        return None, []
    body = abs(k["c"] - k["o"])
    up_w, dn_w = k["h"] - max(k["c"], k["o"]), min(k["c"], k["o"]) - k["l"]
    bull, names = k["c"] > k["o"], []
    if body / rng >= 0.60:
        names.append("بدنهٔ قاطع" + (" صعودی" if bull else " نزولی"))
    if dn_w >= 2 * body and dn_w > up_w:
        names.append("پین‌بار کف (رد فروش)")
    if up_w >= 2 * body and up_w > dn_w:
        names.append("پین‌بار سقف (رد خرید)")
    pb = abs(p["c"] - p["o"])
    if body > pb and ((bull and p["c"] < p["o"] and k["c"] >= p["o"])
                      or (not bull and p["c"] > p["o"] and k["c"] <= p["o"])):
        names.append("بلعنده")
    if not names:
        return None, []
    bullish = bull or "پین‌بار کف (رد فروش)" in names
    align = ("with" if (bullish and direction == "LONG")
             or (not bullish and direction == "SHORT") else "against")
    return align, names


def leg_and_pullback(c1h, direction, win_n=60, min_leg=6):
    """موج آخر و عمق پولبک روی ۱س؛ خروجی (نسبت، اکسترمم پولبک) یا None."""
    win = c1h[-win_n:]
    px = win[-1]["c"]
    if direction == "LONG":
        hi_i = max(range(len(win)), key=lambda i: win[i]["h"])
        if hi_i < min_leg or hi_i > len(win) - 2:
            return None
        lo_i = min(range(hi_i + 1), key=lambda i: win[i]["l"])
        hi, lo = win[hi_i]["h"], win[lo_i]["l"]
        if hi <= lo:
            return None
        return (hi - px) / (hi - lo), min(k["l"] for k in win[hi_i:])
    lo_i = min(range(len(win)), key=lambda i: win[i]["l"])
    if lo_i < min_leg or lo_i > len(win) - 2:
        return None
    hi_i = max(range(lo_i + 1), key=lambda i: win[i]["h"])
    hi, lo = win[hi_i]["h"], win[lo_i]["l"]
    if hi <= lo:
        return None
    return (px - lo) / (hi - lo), max(k["h"] for k in win[lo_i:])


def experience_of(symbol, direction):
    return EXPERIENCE.get(f"{symbol}|{direction}")


# ── دفتر ریسک: چهار قانون داشبورد، کد شده ──────────────────────────────────
class RiskBook:
    """قبل از هر ورود می‌گوید «چقدر، یا نه» — با قوانین خود داشبورد.

    داشبورد هم همین کارها را می‌کند؛ این‌جا تکرارشان می‌کنیم تا استراتژی
    سفارشی نسازد که موتور ریسک بعداً در سکوت ردش کند.
    """

    def __init__(self, equity, cfg=None):
        self.equity = float(equity)
        self.cfg = dict(RISK, **(cfg or {}))
        self.day_loss_pct = 0.0
        self.open_positions = 0

    def leverage_for(self, stop_pct):
        """اهرم مجاز: هم سقف داشبورد، هم محافظ فاصلهٔ لیکویید."""
        if stop_pct <= 0:
            return None
        guard = int(100.0 * self.cfg["liq_guard_ratio"] / stop_pct)
        lev = min(self.cfg["max_leverage"], guard)
        return lev if lev >= 2 else None

    def approve(self, stop_pct):
        """(ok, dict) — سایز و اهرم، یا دلیل رد به زبان آدمیزاد."""
        c = self.cfg
        if self.open_positions >= c["max_open_positions"]:
            return False, {"reason": f"سقف {c['max_open_positions']} پوزیشن "
                                     "هم‌زمان پر است"}
        if self.day_loss_pct >= c["daily_loss_cap_pct"]:
            return False, {"reason": f"سقف ضرر روزانه {c['daily_loss_cap_pct']}٪ "
                                     "خورده — توقف خودکار"}
        lev = self.leverage_for(stop_pct)
        if lev is None:
            return False, {"reason": f"استاپ {stop_pct:.2f}٪ با سقف اهرم "
                                     f"{c['max_leverage']}× جا نمی‌شود"}
        risk_usd = self.equity * c["risk_per_trade_pct"] / 100.0
        notional = risk_usd / (stop_pct / 100.0)
        margin = notional / lev
        left = c["daily_loss_cap_pct"] - self.day_loss_pct
        warn = None
        if left < c["risk_per_trade_pct"] * 2:
            warn = (f"فقط {left:.1f}٪ تا سقف روزانه مانده — "
                    f"جا برای {left / c['risk_per_trade_pct']:.1f} باخت کامل")
        return True, {"risk_usd": round(risk_usd, 2),
                      "notional_usd": round(notional, 2),
                      "margin_usd": round(margin, 2), "leverage": lev,
                      "slots_left": c["max_open_positions"] - self.open_positions,
                      "warn": warn}

    # داشبورد نتیجه را برمی‌گرداند تا دفتر روز به‌روز بماند.
    def on_open(self):
        self.open_positions += 1

    def on_close(self, r_multiple):
        self.open_positions = max(0, self.open_positions - 1)
        if r_multiple < 0:
            self.day_loss_pct += abs(r_multiple) * self.cfg["risk_per_trade_pct"]

    def new_day(self):
        self.day_loss_pct = 0.0


# ── تصمیم ───────────────────────────────────────────────────────────────────
def analyze(symbol, c4h, c1h, equity=None, risk=None, btc4h=None, btc1h=None):
    """تصمیم یک‌ساعته. c4h میدان، c1h ستاپ و ورود.

    دستور حمید (۲۰ اوت): آلت بدون بستر BTC سیگنال نمی‌گیرد (قانون ۳)؛
    هر دو تایم BTC خلاف جهت = وتوی مطلق. ریشه: شورت ARB در بازار مثبت."""
    def no(why):
        return {"action": "NO_SIGNAL", "symbol": symbol, "tf": "1h",
                "why": why, "version": P["version"], "panel": "لیام تریدر ۹"}

    if not c1h or len(c1h) < 60 or not c4h:
        return no("دادهٔ ناکافی — قانون ۱: حدس ممنوع")
    t4 = trend(c4h)
    t1 = trend(c1h, fast=21, slow=55, win=12)
    if t4 is None:
        return no("روند ۴ساعته قابل‌سنجش نیست (کندل کم)")
    if t4 == "up" and t1 != "down":
        direction = "LONG"
    elif t4 == "down" and t1 != "up":
        direction = "SHORT"
    else:
        return no(f"میدان ۴س ({t4}) و ساختار ۱س ({t1}) هم‌قصه نیستند — وتوی روند")

    is_btc = symbol.upper().replace("USDT", "").replace("USD", "") == "BTC"
    if not is_btc:
        if not btc4h or not btc1h:
            return no("بستر BTC نرسیده — قانون ۳: سیگنال آلت بدون بستر ممنوع")
        b4 = trend(btc4h)
        b1 = trend(btc1h, fast=21, slow=55, win=12)
        if b4 is None or b1 is None:
            return no("روند BTC قابل‌سنجش نیست — قانون ۱")
        opp = "down" if direction == "LONG" else "up"
        if b4 == opp and b1 == opp:
            return no(f"هر دو تایم BTC ({b4}/{b1}) خلاف جهت — وتوی مطلق بازار")
        mkt_counter = (b4 == opp) or (b1 == opp)
        mkt_note = f"بستر BTC: ۴س {b4} · ۱س {b1}"
    else:
        mkt_counter, mkt_note = False, "خود بازار (BTC)"

    pb = leg_and_pullback(c1h, direction)
    if pb is None:
        return no("موج/پولبک معتبری روی ۱س نیست")
    ratio, pull_ext = pb
    if not (P["pullback_min"] <= ratio <= P["pullback_max"]):
        return no(f"عمق پولبک {ratio:.2f} خارج از بازهٔ سالم")

    k = c1h[-1]
    i = ibs(k)
    if direction == "LONG" and i > P["ibs_long_max"]:
        return no(f"IBS={i:.2f} تأیید لانگ نیست (کف {P['ibs_long_max']})")
    if direction == "SHORT" and i < P["ibs_short_min"]:
        return no(f"IBS={i:.2f} تأیید شورت نیست (سقف {P['ibs_short_min']})")

    entry = k["c"]
    a = atr(c1h[-(P["atr_n"] * 4):], P["atr_n"]) or 0
    if direction == "LONG":
        sl = min(pull_ext, entry - P["atr_mult"] * a)
        risk_dist = entry - sl
        tp1 = entry + P["rr_target"] * risk_dist
    else:
        sl = max(pull_ext, entry + P["atr_mult"] * a)
        risk_dist = sl - entry
        tp1 = entry - P["rr_target"] * risk_dist
    if risk_dist <= 0:
        return no("هندسهٔ استاپ نامعتبر")
    stop_pct = risk_dist / entry * 100
    if stop_pct < P["min_stop_pct"]:
        return no(f"استاپ {stop_pct:.2f}٪ زیر کف {P['min_stop_pct']}٪ — "
                  "کارمزد و لغزش R را می‌خورند")
    if stop_pct > P["max_stop_pct"]:
        return no(f"استاپ {stop_pct:.2f}٪ بالای سقف {P['max_stop_pct']}٪ — "
                  f"با اهرم {RISK['max_leverage']}× به لیکویید نزدیک می‌شود")
    fee_r = (P["fee_round_trip_pct"] / 100) * entry / risk_dist
    net_rr = P["rr_target"] - fee_r
    if net_rr < P["min_net_rr"]:
        return no(f"RR خالص {net_rr:.2f} زیر کف {P['min_net_rr']}")

    exp = experience_of(symbol, direction)
    exp_used = bool(exp and not exp.get("thin"))
    if exp_used and exp["mean_r"] <= P["exp_veto_mean_r"]:
        return no(f"کارنامهٔ همین ارز/جهت: {exp['n']} معامله، میانگین "
                  f"{exp['mean_r']:+.2f}R — تجربه می‌گوید نرو")

    align, names = candle_confirm(c1h, direction)
    quality = 60
    why = [f"میدان ۴س {t4} · ساختار ۱س {t1}",
           f"پولبک {ratio:.2f} در جهت روند",
           f"IBS {i:.2f} تأیید ورود",
           f"استاپ {stop_pct:.2f}٪ بیرون نویز ({P['atr_mult']}×ATR۱س)",
           f"RR خالص از کارمزد {net_rr:.2f}"]
    if exp_used:
        quality += 20 if exp["mean_r"] > 0 else 5
        why.append(f"تجربه: {exp['n']} معامله، برد {exp['win_pct']}٪، "
                   f"میانگین {exp['mean_r']:+.2f}R")
    elif exp:
        why.append(f"تاریخچهٔ نازک ({exp['n']} معامله) — بدون وزن")
    if align == "with":
        quality += 10
        why.append("کندل ۱س هم‌جهت: " + "، ".join(names))
    elif align == "against":
        quality -= 5
        why.append("کندل ۱س مخالف: " + "، ".join(names))
    if 0.38 <= ratio <= 0.705:
        quality += 5
        why.append("عمق پولبک در ناحیهٔ طلایی فیبوناچی")
    quality = max(0, min(100, quality))
    if quality < P["min_quality"]:
        return no(f"امتیاز کیفیت {quality} زیر کف {P['min_quality']}")

    # یک تایم BTC خلاف جهت → فقط با تأیید کامل (کندل هم‌جهت + کیفیت ≥۷۰)
    if mkt_counter:
        if align != "with" or quality < 70:
            return no(f"خلاف بازار ({mkt_note}) بدون تأیید کامل — "
                      f"کندل {align}، کیفیت {quality}")
        why.append(f"⚠️ خلاف بازار — {mkt_note}؛ با تأیید کامل عبور کرد")
    else:
        why.append(mkt_note)

    out = {"action": direction, "symbol": symbol, "tf": "1h",
           "product": "futures", "margin_mode": "isolated",
           "sl_tp_mandatory": True,
           "entry": round(entry, 8), "sl": round(sl, 8), "tp1": round(tp1, 8),
           "tp2": round(entry + (tp1 - entry) * 1.8, 8),
           "stop_pct": round(stop_pct, 3), "rr_net": round(net_rr, 2),
           "fee_r": round(fee_r, 3), "ibs": round(i, 2),
           "pullback": round(ratio, 3), "trend_4h": t4, "trend_1h": t1,
           "quality": quality, "exp_used": exp_used, "experience": exp,
           "pattern_align": align, "patterns": names,
           "max_hold_bars": P["max_hold_bars"],
           "trail": {
               "step1_at": round(entry + (tp1 - entry) * P["trail_first"], 8),
               "step1_sl": round(entry * (1 + P["breakeven_pad_pct"] / 100)
                                 if direction == "LONG"
                                 else entry * (1 - P["breakeven_pad_pct"] / 100), 8),
               "step2_at": round(entry + (tp1 - entry) * P["trail_second"], 8),
               "step2_sl": round(entry + (tp1 - entry) * P["trail_first"], 8),
               "rule": "🪜 ⅓ مسیر → استاپ سربه‌سرِ کارمزددار؛ ⅔ → استاپ روی ⅓"},
           "panel": "لیام تریدر ۹", "version": P["version"],
           "t": int(time.time() * 1000), "why": why}
    out["stop_loss"], out["take_profit"] = out["sl"], out["tp1"]

    book = risk if isinstance(risk, RiskBook) else (
        RiskBook(equity) if equity else None)
    if book:
        ok, info = book.approve(stop_pct)
        out["risk"] = info
        if not ok:
            return no("ریسک اجازه نداد: " + info["reason"])
        out["leverage"] = info["leverage"]
        out["size_usd"] = info["notional_usd"]
        out["margin_usd"] = info["margin_usd"]
        if info.get("warn"):
            out["why"].append("⚠️ " + info["warn"])
    else:
        out["leverage"] = min(RISK["max_leverage"],
                              int(50.0 / stop_pct)) or None
    return out


def signal(symbol, equity=None, risk=None):
    c1h = fetch_klines(symbol, "1h", 400)
    c4h = fetch_klines(symbol, "4h", 300)
    if not (c1h and c4h):
        return {"action": "NO_SIGNAL", "symbol": symbol, "tf": "1h",
                "why": "کندل از هیچ منبعی نرسید — قانون ۱"}
    btc4h = btc1h = None
    if symbol.upper().replace("USDT", "").replace("USD", "") != "BTC":
        btc4h = fetch_klines("BTCUSDT", "4h", 300)
        btc1h = fetch_klines("BTCUSDT", "1h", 400)
    return analyze(symbol, c4h, c1h, equity=equity, risk=risk,
                   btc4h=btc4h, btc1h=btc1h)


# ── مدیریت معامله (همان قانون تریل حمید) ───────────────────────────────────
def manage(pos, candle):
    """هر کندل ۱س بسته‌شده را بده؛ استاپ جدید یا خروج را برمی‌گرداند.

    بدون خوش‌بینی درون‌کندلی: اگر کندل هم استاپ و هم تارگت را لمس کرد،
    استاپ اول فرض می‌شود (بدترین حالت)."""
    d, entry, sl, tp1 = pos["action"], pos["entry"], pos["sl"], pos["tp1"]
    tr = pos["trail"]
    hi, lo = candle["h"], candle["l"]
    if d == "LONG":
        if lo <= sl:
            return {"event": "STOP", "price": sl}
        if hi >= tp1:
            return {"event": "TARGET", "price": tp1}
        if hi >= tr["step2_at"] and sl < tr["step2_sl"]:
            return {"event": "TRAIL", "sl": tr["step2_sl"], "step": 2}
        if hi >= tr["step1_at"] and sl < tr["step1_sl"]:
            return {"event": "TRAIL", "sl": tr["step1_sl"], "step": 1}
    else:
        if hi >= sl:
            return {"event": "STOP", "price": sl}
        if lo <= tp1:
            return {"event": "TARGET", "price": tp1}
        if lo <= tr["step2_at"] and sl > tr["step2_sl"]:
            return {"event": "TRAIL", "sl": tr["step2_sl"], "step": 2}
        if lo <= tr["step1_at"] and sl > tr["step1_sl"]:
            return {"event": "TRAIL", "sl": tr["step1_sl"], "step": 1}
    return {"event": "HOLD"}


# ── خودآزمایی ───────────────────────────────────────────────────────────────
def _selftest():
    def mk(path, tf_ms=3600000, t0=0):
        return [{"t": t0 + i * tf_ms, "o": p, "h": p * 1.004, "l": p * 0.996,
                 "c": p} for i, p in enumerate(path)]
    EXPERIENCE.clear()
    up = [100 + i * 0.35 for i in range(260)]
    c4 = mk(up, tf_ms=14400000)
    pull = up + [up[-1] - i * 1.2 for i in range(1, 9)]
    c1 = mk(pull)
    c1[-1]["l"], c1[-1]["c"] = c1[-1]["c"] * 0.988, c1[-1]["c"] * 0.9895
    b4, b1h = c4, mk(up)                      # بستر BTC هم‌جهت (قانون ۳)
    r = analyze("TESTUSDT", c4, c1, btc4h=b4, btc1h=b1h)
    assert r["action"] == "LONG", r
    # قرارداد اجرا (۲۰ اوت): ایزوله + استاپ/تارگت روی خود خروجی
    assert r["margin_mode"] == "isolated" and r["sl_tp_mandatory"], r
    assert r["stop_loss"] == r["sl"] and r["take_profit"] == r["tp1"], r
    # آلت بدون بستر BTC ممنوع؛ هر دو تایم BTC خلاف = وتوی مطلق
    assert analyze("TESTUSDT", c4, c1)["action"] == "NO_SIGNAL"
    dn4 = mk([200 - i * 0.35 for i in range(260)], tf_ms=14400000)
    g2 = analyze("TESTUSDT", c4, c1, btc4h=dn4, btc1h=mk([200 - i * 0.35 for i in range(260)]))
    assert g2["action"] == "NO_SIGNAL" and "وتوی مطلق" in g2["why"], g2
    # خود BTC معاف است
    assert analyze("BTCUSDT", c4, c1)["action"] == "LONG"
    assert r["sl"] < r["entry"] < r["tp1"], r
    assert P["min_stop_pct"] <= r["stop_pct"] <= P["max_stop_pct"], r
    assert r["leverage"] <= RISK["max_leverage"], r
    assert r["trail"]["step1_at"] < r["trail"]["step2_at"] < r["tp1"], r

    # اهرم هرگز از سقف داشبورد و از محافظ لیکویید رد نمی‌شود
    b = RiskBook(1000)
    for s in (0.6, 1.0, 1.5, 2.2):
        lev = b.leverage_for(s)
        assert lev <= RISK["max_leverage"] and lev <= int(50.0 / s), (s, lev)
    ok, info = b.approve(1.0)
    assert ok and abs(info["risk_usd"] - 20.0) < 1e-6, info
    assert abs(info["notional_usd"] - 2000.0) < 1e-6, info   # ۲٪ ÷ ۱٪ استاپ
    assert info["margin_usd"] == round(2000.0 / info["leverage"], 2), info

    # سقف پوزیشن هم‌زمان
    for _ in range(RISK["max_open_positions"]):
        b.on_open()
    ok2, why2 = b.approve(1.0)
    assert not ok2 and "پوزیشن" in why2["reason"], why2

    # سقف ضرر روزانه: دو باخت کامل با ریسک ۲٪ = ۴٪، سومی رد می‌شود
    b2 = RiskBook(1000)
    b2.on_open(); b2.on_close(-1.0)
    b2.on_open(); b2.on_close(-1.0)
    ok3, info3 = b2.approve(1.0)
    assert ok3 and info3["warn"], info3          # هشدار نزدیکی به سقف
    b2.on_open(); b2.on_close(-1.0)
    ok4, why4 = b2.approve(1.0)
    assert not ok4 and "روزانه" in why4["reason"], why4
    b2.new_day()
    assert b2.approve(1.0)[0]

    # سیگنال با دفتر ریسک: سایز و مارجین می‌آید
    r2 = analyze("TESTUSDT", c4, c1, equity=5000, btc4h=b4, btc1h=b1h)
    assert r2["action"] == "LONG" and r2["size_usd"] > 0 and r2["margin_usd"] > 0

    # وتوی تجربهٔ منفی و بی‌اثری تاریخچهٔ نازک
    EXPERIENCE["TESTUSDT|LONG"] = {"n": 30, "win_pct": 20.0, "mean_r": -0.7,
                                   "thin": False}
    assert analyze("TESTUSDT", c4, c1, btc4h=b4, btc1h=b1h)["action"] == "NO_SIGNAL"
    EXPERIENCE["TESTUSDT|LONG"] = {"n": 4, "win_pct": 0.0, "mean_r": -0.9,
                                   "thin": True}
    assert analyze("TESTUSDT", c4, c1, btc4h=b4, btc1h=b1h)["action"] == "LONG"
    EXPERIENCE.clear()

    # وتوی روند و دادهٔ کم
    down4 = mk([200 - i * 0.35 for i in range(260)], tf_ms=14400000)
    assert analyze("TESTUSDT", down4, c1, btc4h=b4, btc1h=b1h)["action"] == "NO_SIGNAL"
    assert analyze("TESTUSDT", c4, mk([100.0] * 10), btc4h=b4, btc1h=b1h)["action"] == "NO_SIGNAL"

    # مدیریت: تریل قبل از تارگت، استاپ در بدترین حالت اول
    pos = analyze("TESTUSDT", c4, c1, btc4h=b4, btc1h=b1h)
    mid1 = pos["trail"]["step1_at"]
    ev = manage(pos, {"h": mid1 * 1.0001, "l": pos["entry"]})
    assert ev["event"] == "TRAIL" and ev["step"] == 1, ev
    ev2 = manage(pos, {"h": pos["tp1"] * 1.01, "l": pos["sl"] * 0.99})
    assert ev2["event"] == "STOP", ev2
    print("✓ خودآزمایی موتور ۱ ساعته گذشت — ساختار، ریسک داشبورد، تریل")


# ── قالب کلاسی داشبورد ──────────────────────────────────────────────────────
try:
    from strategy_base import BaseStrategy
except Exception:                                        # noqa: BLE001
    try:
        from base_strategy import BaseStrategy
    except Exception:                                    # noqa: BLE001
        class BaseStrategy:
            pass


class Liam9H1Strategy(BaseStrategy):
    """لیام تریدر ۹ — موتور یک‌ساعته، هم‌تراز با قوانین ریسک داشبورد."""

    meta = {
        "name": "لیام تریدر ۹ — پولبک یک‌ساعته",
        "id": "liam9-h1-pullback",
        "version": P["version"],
        "author": "لیام تریدر ۹",
        "timeframes": ["4h", "1h"],
        "market": "crypto-futures",
        "risk_profile": {"risk_per_trade_pct": RISK["risk_per_trade_pct"],
                         "max_leverage": RISK["max_leverage"],
                         "max_open_positions": RISK["max_open_positions"],
                         "daily_loss_cap_pct": RISK["daily_loss_cap_pct"],
                         "stop_pct_range": [P["min_stop_pct"],
                                            P["max_stop_pct"]]},
        "description": ("میدان ۴س → ستاپ پولبک ۱س → تأیید IBS و کندل → "
                        "استاپ بیرون نویز (۰.۶–۲.۲٪، سازگار با اهرم ۲۰) → "
                        "دروازهٔ کارمزد → لایهٔ تجربه → نردبان تریل ⅓/⅔"),
    }

    def __init__(self, *a, **kw):
        try:
            super().__init__(*a, **kw)
        except Exception:                                # noqa: BLE001
            pass
        self.equity = kw.get("equity")
        self.book = RiskBook(self.equity) if self.equity else None
        sync_all()
        self.meta["version"] = P["version"]

    @staticmethod
    def _btc_ctx(symbol, kw):
        """بستر BTC — اگر داشبورد نداد، خودمان می‌گیریم (قانون ۳)."""
        if symbol.upper().replace("USDT", "").replace("USD", "") == "BTC":
            return None, None
        b4 = kw.get("btc4h") or fetch_klines("BTCUSDT", "4h", 300)
        b1 = kw.get("btc1h") or fetch_klines("BTCUSDT", "1h", 400)
        return b4, b1

    def generate_signal(self, symbol, c4h=None, c1h=None, equity=None, **kw):
        eq = equity or self.equity
        if c4h and c1h:
            b4, b1 = self._btc_ctx(symbol, kw)
            return analyze(symbol, c4h, c1h, equity=eq, risk=self.book,
                           btc4h=b4, btc1h=b1)
        return signal(symbol, equity=eq, risk=self.book)

    def on_bar(self, symbol, candles=None, **kw):
        if candles and len(candles) >= 60:
            c4h = fetch_klines(symbol, "4h", 300)
            if c4h:
                b4, b1 = self._btc_ctx(symbol, kw)
                return analyze(symbol, c4h, candles,
                               equity=kw.get("equity") or self.equity,
                               risk=self.book, btc4h=b4, btc1h=b1)
        return self.generate_signal(symbol, **kw)

    def run(self, symbol, **kw):
        return self.generate_signal(symbol, **kw)

    def manage_position(self, position, candle):
        return manage(position, candle)


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        sym = args[0] if args else "BTCUSDT"
        eq = float(args[1]) if len(args) > 1 else 1000.0
        v = sync_all()
        print(f"پارامترها: {v['params'] or 'پیش‌فرض'} · "
              f"تجربه: {v['experience_pairs']} جفت")
        print(json.dumps(signal(sym, equity=eq), ensure_ascii=False, indent=1))
