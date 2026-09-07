#!/usr/bin/env python3
"""لیام تریدر ۹ — موتور اختصاصی **شورت** برای داشبورد (دستور حمید، ۷ سپتامبر)

«توی کد پایتون برای داشبورد هم برای شورت بهترین استراتژی رو بنویس و
تحویل داشبورد بده که بدون خطا.»

═══════════════════════════════════════════════════════════════════════
  حکمِ فعلی: PAPER_ONLY — این فایل هنوز مجوز تولید ندارد
═══════════════════════════════════════════════════════════════════════

قانون ۰۱ بند ۸ می‌گوید معاملهٔ خلاف روند فقط با «Strategy Counter-trend
مستقل و **تست‌شده**» مجاز است. این فایل مستقل هست؛ تست‌شده هنوز نیست.
پس تا وقتی بازهٔ اطمینانش از صفر رد نکند و حمید صریح تأیید نکند،
خروجی‌اش برچسب `PAPER_ONLY` دارد و به سیگنالِ واقعی نمی‌رود
(قانون ۰۳/۱۲).

──────────────────── چرا شورت‌های فعلی می‌بازند ────────────────────

اندازه‌گیری ۷ سپتامبر روی دفترِ بستهٔ پیپر، **یکتاشده** بر
(نماد، ورود، زمانِ باز شدن) — چون CI روی ردیفِ تکراری دروغ می‌گوید
(تصحیح ۲۴ اوت):

    همهٔ شورت‌های یکتا: n=۲۰٬۳۰۷ · خالص از کارمزد **−۰.۳۱۲R**
                        CI۹۵ [−۰.۳۳۹, −۰.۲۸۵]
    شورت‌های سیگنال‌گرید: n=۱۲۹ · **−۰.۳۵۱R** · CI [−۰.۵۰۴, −۰.۱۹۹]
    (لانگ سیگنال‌گرید برای مقایسه: n=۲۳۱ · −۰.۲۲۸R)

یعنی مشکل «شورت پیدا نمی‌شود» نبود؛ شورت‌هایی که پیدا می‌شدند
**بدتر از لانگ** می‌باختند. پس اضافه‌کردن شورتِ بیشتر با همان قواعد،
ضرر را زیاد می‌کرد نه کم.

──────────── چهار فیلتری که با شمارش انتخاب شدند، نه با سلیقه ────────────

دوازده شرط **پیش از دیدن نتیجه** ثبت شد (هر کدام از یک سند: منشور،
قانون ۱۰، قانون ۱۱، درس کارمزد) و همه با تصحیح چندآزمونیِ Šidák
سنجیده شدند (m=۱۲، آستانهٔ |t| ≥ ۲.۸۵۸):

| شرط | n | خالصِ با-شرط | اختلاف با بی-شرط | \|t\| |
|---|---|---|---|---|
| **استاپ ≥ ۱٪** | ۸٬۸۸۱ | −۰.۱۷۳R | **+۰.۲۴۸** | ۱۰.۰۳ |
| **OB هم‌جهت** | ۳٬۴۲۹ | −۰.۱۷۰R | **+۰.۱۷۱** | ۸.۰۳ |
| **بالای کانال (>۰.۷۰)** | ۱٬۵۵۶ | −۰.۱۴۲R | **+۰.۱۸۵** | ۶.۸۲ |
| OB تازه | ۱٬۲۷۲ | −۰.۱۳۹R | +۰.۱۸۵ | ۶.۷۷ |
| ۴س نزولی | ۱۰٬۴۳۳ | −۰.۲۲۶R | +۰.۱۷۸ | ۶.۴۰ |
| ایمپالس ≥۴ | ۵۷۵ | −۰.۱۰۴R | +۰.۲۱۴ | ۴.۸۳ |
| **استاپ < ۰.۵٪** | ۱٬۷۱۳ | −۰.۴۸۵R | **−۰.۱۸۹** | ۶.۳۸ |

قوی‌ترین اهرم **هندسه** است، نه تشخیص جهت — و مکانیکش معلوم است:
سهم کارمزد از هر معامله برابر `کارمزد٪ ÷ استاپ٪` است، پس استاپِ تنگ
سهمِ کارمزد را چند برابر می‌کند. همان بیماریِ اسکلپ ۱ دقیقه (قانون ۱۰)
و همان چیزی که میز شوک را خواباند.

──────────── ترکیب، با آزمونِ خارج از نمونه ────────────

دفتر به دو نیمهٔ زمانی بریده شد (نیمهٔ اول ساخت، نیمهٔ دوم دیده‌نشده):

| ترکیب | نیمهٔ اول | نیمهٔ دوم (خارج از نمونه) |
|---|---|---|
| استاپ گشاد | n=۵۰۵۱ −۰.۱۸۱ | n=۳۸۳۰ −۰.۱۶۱ |
| + OB هم‌جهت | n=۱۱۶۵ −۰.۰۸۹ | n=۹۸۸ −۰.۱۱۷ |
| **+ بالای کانال** | **n=۳۱۵ −۰.۰۲۰ [−۰.۱۰۳,+۰.۰۶۴]** | **n=۲۷۹ −۰.۰۳۶ [−۰.۱۲۴,+۰.۰۵۱]** |

دو نیمه با هم می‌خوانند — یعنی اثر پایدار است، نه تصادفِ یک دوره.
ولی **CI هر دو شاملِ صفر است**: از −۰.۳۱R به ~صفر، نه به سود.

**پس ادعای درست این است: این چهار فیلتر ضررِ شورت را از بین می‌برند؛
سود اثبات‌شده نمی‌سازند.** هر ادعای بیشتر، ادعای بی‌سند است.

──────────── چه چیزی هنوز سنجیده نشده ────────────

هندسهٔ تارگت. هر ۵۹۴ ردیفِ فیلترشده RR بین ۲.۰ و ۲.۵ داشتند — یعنی
دفتر اصلاً تنوعِ RR ندارد و از رویش نمی‌شود فهمید تارگتِ بزرگ‌تر جواب
می‌دهد یا نه. این را فقط بک‌تستِ کندلِ واقعی روی رانر جواب می‌دهد
(`short-backtest.yml`)، نه این دفتر.

باطل‌کننده: اگر بک‌تستِ کندلِ واقعی روی این چهار فیلتر خالصِ منفی با
CI زیر صفر بدهد، این استراتژی رد می‌شود — نه اینکه فیلتر اضافه شود.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]

STRATEGY_ID = "liam9_short"
STRATEGY_VERSION = "v1.0"
PANEL_NAME = "لیام تریدر ۹"

# وضعیت ادعا (قانون ۰۳). دست‌نخورده می‌ماند تا بک‌تستِ کندلِ واقعی
# حکم بدهد و حمید صریح تأیید کند.
VALIDATION_STATUS = "PAPER_VALIDATED_PENDING"
PRODUCTION_APPROVED = False

P = {
    # ── هندسه: قوی‌ترین اهرمِ اندازه‌گیری‌شده (+۰.۲۴۸R، |t|=۱۰.۰) ──
    "min_stop_pct": 1.00,      # استاپِ تنگ‌تر از این = دامِ کارمزد
    "max_stop_pct": 3.30,      # بالاتر از این، محافظ لیکویید اهرم را زیر ۱۵ می‌برد
    "rr_target": 2.20,         # میانهٔ همان ۵۹۴ ردیفِ سنجیده‌شده
    "min_net_rr": 1.60,        # بعد از کارمزد؛ کف از hamid/fees
    # ── مکان: بالای کانال، جایی که شورت معنا دارد (قانون ۱۱) ──
    "min_chan_pos": 0.70,
    # ── سقف‌ها: قرارداد اجرا (۲۰ اوت) ──
    "max_leverage": 20,
    "liq_guard": 50.0,         # اهرم ≤ ۵۰ ÷ استاپ٪
    "risk_pct": 2.0,
    "max_hold_bars": 120,
    "stale_max_s": 300,        # کندل کهنه‌تر از این = NO_SIGNAL (قانون ۰۱ بند ۱)
    "min_bars": 60,
}


# ═══════════════════ ابزارهای کوچکِ قطعی ═══════════════════

def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _ohlc(c):
    """یک کندل → (o, h, l, close, v). شکل‌های رایج صرافی را می‌پذیرد."""
    if isinstance(c, dict):
        vals = [c.get(k) for k in ("o", "h", "l", "c", "v")]
        if vals[0] is None:
            vals = [c.get(k) for k in ("open", "high", "low", "close", "volume")]
        return tuple(_f(v) for v in vals)
    if isinstance(c, (list, tuple)) and len(c) >= 6:
        return (_f(c[1]), _f(c[2]), _f(c[3]), _f(c[4]), _f(c[5]))
    return (None,) * 5


def _ts(c):
    if isinstance(c, dict):
        return _f(c.get("t") or c.get("openTime") or c.get("time"))
    if isinstance(c, (list, tuple)) and c:
        return _f(c[0])
    return None


def atr(cd, n=14):
    if len(cd) < n + 1:
        return None
    tr = []
    for i in range(len(cd) - n, len(cd)):
        _, h, lo, _, _ = _ohlc(cd[i])
        pc = _ohlc(cd[i - 1])[3]
        if None in (h, lo, pc):
            return None
        tr.append(max(h - lo, abs(h - pc), abs(lo - pc)))
    return sum(tr) / len(tr) if tr else None


def channel_pos(cd, look=96):
    """جای قیمت در دامنهٔ اخیر: ۰ = کف، ۱ = سقف.

    نسخهٔ سادهٔ «کانال» قانون ۱۱ است، نه جایگزینش: دامنهٔ سقف/کف. کانالِ
    موازیِ واقعی کارِ `hamid/base_map.py` است و این‌جا فقط **مکان** لازم
    است، نه شیب.
    """
    seg = cd[-look:] if len(cd) > look else cd
    if len(seg) < 20:
        return None
    highs = [_ohlc(c)[1] for c in seg]
    lows = [_ohlc(c)[2] for c in seg]
    if any(x is None for x in highs + lows):
        return None
    hi, lo = max(highs), min(lows)
    last = _ohlc(seg[-1])[3]
    if last is None or hi <= lo:
        return None
    return (last - lo) / (hi - lo)


def trend(cd, n=50):
    """روند از شیبِ میانگینِ دو نیمه — بی‌اندیکاتور، قطعی.

    خروجی: "up" / "down" / "flat". **flat واقعی است، نه گِرد‌شده به
    up**: همان عیبی که ۶ سپتامبر پیدا شد — تثبیتِ بعد از رالی هنوز
    «up» خوانده می‌شد و هر شورتی را وتو می‌کرد. آستانهٔ بزرگی این‌جا
    صریح است.
    """
    seg = cd[-n:] if len(cd) > n else cd
    if len(seg) < 20:
        return None
    cl = [_ohlc(c)[3] for c in seg]
    if any(x is None for x in cl):
        return None
    h = len(cl) // 2
    a, b = sum(cl[:h]) / h, sum(cl[h:]) / (len(cl) - h)
    if not a:
        return None
    ch = (b - a) / a * 100
    # آستانه: کمتر از ۰.۵٪ جابه‌جایی بین دو نیمه یعنی «بی‌جهت».
    if ch > 0.5:
        return "up"
    if ch < -0.5:
        return "down"
    return "flat"


def bearish_ob(cd, look=60):
    """اردر بلاکِ نزولی به تعریف خودِ حمید (قانون ۱۱).

    «بعد از رشد، کندل‌ها را به عقب برمی‌گردیم تا اولین کندلِ **قرمزِ
    قوی** که بدنه‌اش از مجموع شدوهایش بزرگ‌تر است.» تازگی هم شمرده
    می‌شود: کندلی که قیمت بعداً از سقفش رد شده، مصرف‌شده است.
    """
    seg = cd[-look:] if len(cd) > look else cd
    if len(seg) < 10:
        return None
    for i in range(len(seg) - 3, 0, -1):
        o, h, lo, c, _ = _ohlc(seg[i])
        if None in (o, h, lo, c) or c >= o:
            continue
        body = o - c
        wicks = (h - o) + (c - lo)
        if body <= wicks:
            continue
        after = seg[i + 1:]
        consumed = any((_ohlc(x)[3] or 0) > h for x in after)
        return {"top": h, "bottom": o, "idx": i,
                "age_bars": len(seg) - 1 - i,
                "fresh": not consumed, "body_ratio": round(body / (wicks or 1e-9), 2)}
    return None


def swept_high(cd, look=40):
    """سوییپِ نقدینگیِ بالا: سقفی که شکسته شد و کلوز برنگشت بالای آن."""
    seg = cd[-look:] if len(cd) > look else cd
    if len(seg) < 12:
        return False
    highs = [_ohlc(c)[1] for c in seg[:-3]]
    if not highs or any(h is None for h in highs):
        return False
    prior = max(highs)
    tail = seg[-3:]
    pierced = any((_ohlc(c)[1] or 0) > prior for c in tail)
    closed_back = (_ohlc(tail[-1])[3] or 0) < prior
    return bool(pierced and closed_back)


def leverage_for(stop_pct):
    """محافظ لیکویید حاکم مطلق (قانون ۱۰): اهرم ≤ ۵۰ ÷ استاپ٪، سقف ۲۰."""
    if not stop_pct or stop_pct <= 0:
        return None
    return max(1, min(P["max_leverage"], int(P["liq_guard"] / stop_pct)))


def size_for(equity, stop_pct, lev):
    """سایز از **قانون ریسک**، نه از اهرم: ضررِ استاپ همیشه ۲٪ می‌ماند."""
    if not equity or not stop_pct or not lev:
        return None
    risk_usd = equity * P["risk_pct"] / 100.0
    notional = risk_usd / (stop_pct / 100.0)
    return {"risk_usd": round(risk_usd, 2),
            "notional_usd": round(notional, 2),
            "margin_usd": round(notional / lev, 2)}


# ═══════════════════ تصمیم ═══════════════════

def _no(symbol, tf, why, **extra):
    return {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf, "why": why,
            "strategy": STRATEGY_ID, "version": STRATEGY_VERSION,
            "validation_status": VALIDATION_STATUS,
            "production_approved": PRODUCTION_APPROVED,
            "panel": PANEL_NAME, "t": int(time.time() * 1000), **extra}


def decide(symbol, cd, tf="15m", cd_4h=None, btc_4h=None, btc_1h=None,
           equity=None, now_ms=None):
    """تصمیمِ شورت. → dict با `action` ∈ {SHORT, NO_SIGNAL}.

    ترتیب دروازه‌ها همان ترتیب قانون ۰۰ است: داده → بسترِ BTC → ساختار
    ۴س → مکان → OB → نقدینگی → هندسه/کارمزد → اهرم/سایز. هیچ دروازه‌ای
    جابه‌جا نمی‌شود بی‌دستور صریح حمید.
    """
    now = now_ms or int(time.time() * 1000)
    funnel = []

    def step(name, ok, detail=""):
        funnel.append({"gate": name, "pass": bool(ok), "detail": detail})
        return bool(ok)

    # ── ۱) داده: ناقص/کهنه = NO_SIGNAL (قانون ۰۱ بند ۱) ──
    if not cd or len(cd) < P["min_bars"]:
        return _no(symbol, tf, f"کندل کم: {len(cd or [])} < {P['min_bars']}",
                   funnel=funnel)
    last_t = _ts(cd[-1])
    if last_t is None:
        return _no(symbol, tf, "مهرِ زمانِ کندل خوانده نشد", funnel=funnel)
    age_s = (now - last_t) / 1000.0
    if age_s > P["stale_max_s"] * 4:
        # ×۴ چون مهرِ کندل زمانِ **باز شدن** آن است؛ روی ۱۵د یک کندلِ
        # تازه هم می‌تواند ۹۰۰ ثانیه سن داشته باشد و کهنه نباشد.
        return _no(symbol, tf, f"کندل کهنه: {age_s:.0f} ثانیه", funnel=funnel)
    step("داده", True, f"{len(cd)} کندل · سن {age_s:.0f}s")

    price = _ohlc(cd[-1])[3]
    if not price:
        return _no(symbol, tf, "قیمتِ کلوز خوانده نشد", funnel=funnel)

    # ── ۲) بسترِ بیت‌کوین (قانون ۰۱ بند ۳ · قرارداد اجرا بند ۳) ──
    #
    # برای آلت، نبودِ بسترِ BTC یعنی NO_SIGNAL — نه عبورِ کور. برای خودِ
    # BTC این دروازه بی‌معناست و رد می‌شود.
    is_btc = symbol.upper().startswith("BTC")
    if not is_btc:
        if btc_4h is None or btc_1h is None:
            return _no(symbol, tf, "بسترِ بیت‌کوین در دسترس نیست (قانون ۳)",
                       funnel=funnel)
        if btc_4h == "up" and btc_1h == "up":
            step("بسترِ BTC", False, "هر دو تایمِ BTC صعودی — وتوی مطلق")
            return _no(symbol, tf, "هر دو تایمِ بیت‌کوین صعودی — شورت وتو",
                       funnel=funnel)
        step("بسترِ BTC", True, f"۴س={btc_4h} · ۱س={btc_1h}")

    # ── ۳) ساختار ۴س (اندازه‌گیری: +۰.۱۷۸R) ──
    t4 = trend(cd_4h) if cd_4h else None
    if cd_4h and t4 is None:
        return _no(symbol, tf, "روند ۴س محاسبه نشد", funnel=funnel)
    if t4 == "up":
        step("ساختار ۴س", False, "۴س صعودی")
        return _no(symbol, tf, "ساختار ۴س صعودی — شورت خلاف روند بالادست",
                   funnel=funnel)
    step("ساختار ۴س", True, t4 or "بدون کندل ۴س (شاهد نیست، وتو هم نیست)")

    # ── ۴) مکان: بالای کانال (اندازه‌گیری: +۰.۱۸۵R) ──
    cp = channel_pos(cd)
    if cp is None:
        return _no(symbol, tf, "مکانِ کانال محاسبه نشد", funnel=funnel)
    if cp <= P["min_chan_pos"]:
        step("مکان", False, f"chan_pos={cp:.2f} ≤ {P['min_chan_pos']}")
        return _no(symbol, tf,
                   f"قیمت در {cp:.0%} دامنه — شورت از وسط/کف، تعقیبِ ریزش",
                   funnel=funnel)
    step("مکان", True, f"chan_pos={cp:.2f}")

    # ── ۵) اردر بلاکِ نزولی و تازه (اندازه‌گیری: +۰.۱۷۱ / +۰.۱۸۵R) ──
    ob = bearish_ob(cd)
    if not ob:
        step("اردر بلاک", False, "OB نزولیِ معتبر پیدا نشد")
        return _no(symbol, tf, "اردر بلاک نزولیِ معتبر نیست", funnel=funnel)
    if not ob["fresh"]:
        step("اردر بلاک", False, f"مصرف‌شده (سن {ob['age_bars']} کندل)")
        return _no(symbol, tf, "اردر بلاک مصرف شده", funnel=funnel)
    step("اردر بلاک", True,
         f"سقف {ob['top']:.8g} · سن {ob['age_bars']} · بدنه/شدو {ob['body_ratio']}")

    # ── ۶) نقدینگی: سوییپِ سقف (روش حمید؛ شاهد، نه وتو) ──
    sweep = swept_high(cd)
    step("نقدینگی", True, "سوییپِ سقف دیده شد" if sweep else "بدون سوییپ")

    # ── ۷) هندسه: استاپ پشتِ سقفِ OB + حاشیهٔ نوسان ──
    a = atr(cd)
    if not a:
        return _no(symbol, tf, "ATR محاسبه نشد", funnel=funnel)
    entry = price
    sl = ob["top"] + 0.25 * a
    if sl <= entry:
        return _no(symbol, tf, "استاپ زیر ورود — هندسهٔ نامعتبر", funnel=funnel)
    stop_pct = (sl - entry) / entry * 100.0
    if stop_pct < P["min_stop_pct"]:
        step("هندسه", False, f"استاپ {stop_pct:.2f}٪ < {P['min_stop_pct']}٪")
        return _no(symbol, tf,
                   f"استاپ {stop_pct:.2f}٪ تنگ‌تر از کف — دامِ کارمزد "
                   f"(اندازه‌گیری: استاپِ تنگ ۰.۱۹R بدتر است)",
                   stop_pct=round(stop_pct, 3), funnel=funnel)
    if stop_pct > P["max_stop_pct"]:
        step("هندسه", False, f"استاپ {stop_pct:.2f}٪ > {P['max_stop_pct']}٪")
        return _no(symbol, tf,
                   f"استاپ {stop_pct:.2f}٪ گشادتر از سقف — محافظ لیکویید",
                   stop_pct=round(stop_pct, 3), funnel=funnel)
    step("هندسه", True, f"استاپ {stop_pct:.2f}٪")

    risk = sl - entry
    tp1 = entry - P["rr_target"] * risk
    if tp1 <= 0:
        return _no(symbol, tf, "تارگت زیر صفر — هندسهٔ نامعتبر", funnel=funnel)
    tp2 = entry - 2 * P["rr_target"] * risk

    # ── ۸) دروازهٔ کارمزد (hamid/fees — منبع واحد، نه عددِ محلی) ──
    try:
        from hamid import fees
        fee_r = fees.cost_in_r(entry, sl, symbol=symbol)
    except Exception:                                # noqa: BLE001
        # نبودِ ماژول نباید عددِ ساختگی بسازد: کارمزدِ محافظه‌کارانهٔ
        # مستندِ ۱۶ اوت (تیکر دو سر + لغزش ≈ ۰.۱۵٪).
        fee_r = (0.15 / 100.0) * entry / risk
    net_rr = P["rr_target"] - fee_r
    if net_rr < P["min_net_rr"]:
        step("کارمزد", False, f"RR خالص {net_rr:.2f}")
        return _no(symbol, tf,
                   f"RR خالص {net_rr:.2f} زیر کف {P['min_net_rr']}",
                   fee_r=round(fee_r, 3), funnel=funnel)
    step("کارمزد", True, f"RR خالص {net_rr:.2f} · fee_r {fee_r:.3f}")

    # ── ۹) اهرم و سایز ──
    lev = leverage_for(stop_pct)
    if not lev:
        return _no(symbol, tf, "اهرم محاسبه نشد", funnel=funnel)
    step("اهرم", True, f"×{lev} (محافظ لیکویید)")

    out = {
        "action": "SHORT", "symbol": symbol, "tf": tf,
        "strategy": STRATEGY_ID, "version": STRATEGY_VERSION,
        # قرارداد اجرا (دستور حمید، ۲۰ اوت): ایزوله + استاپ/تارگت اجباری
        "product": "futures", "margin_mode": "isolated",
        "sl_tp_mandatory": True,
        "entry": round(entry, 8), "sl": round(sl, 8),
        "tp1": round(tp1, 8), "tp2": round(tp2, 8),
        "stop_pct": round(stop_pct, 3),
        "rr_target": P["rr_target"], "rr_net": round(net_rr, 2),
        "fee_r": round(fee_r, 3), "leverage": lev,
        "chan_pos": round(cp, 3), "trend_4h": t4,
        "btc_4h": btc_4h, "btc_1h": btc_1h,
        "ob": ob, "sweep": sweep,
        "max_hold_bars": P["max_hold_bars"],
        "trail": {"arm_at": round(entry - fee_r * risk, 8),
                  "frac": 0.80,
                  "rule": "🪜 تا سود از کارمزد نگذشته استاپ دست نمی‌خورد؛ "
                          "بعد از آن روی ۸۰٪ بهترین سود و فقط پایین‌تر "
                          "(قانون تریل نسخهٔ سه)"},
        # مرزِ صادقانه، روی خودِ خروجی — تا کسی آن را «سیگنالِ تأییدشده»
        # نخواند (قانون ۱۲).
        "validation_status": VALIDATION_STATUS,
        "production_approved": PRODUCTION_APPROVED,
        "boundary": ("PAPER_ONLY — چهار فیلترِ این موتور ضررِ شورت را از "
                     "−۰.۳۱R به ~صفر می‌آورند (n=۵۹۴، دو نیمهٔ هم‌خوان)، "
                     "ولی CI هنوز شاملِ صفر است. سودِ اثبات‌شده نیست."),
        "panel": PANEL_NAME, "t": now, "funnel": funnel,
    }
    out["stop_loss"], out["take_profit"] = out["sl"], out["tp1"]
    if equity:
        s = size_for(equity, stop_pct, lev)
        if s:
            out.update({"size_usd": s["notional_usd"],
                        "margin_usd": s["margin_usd"],
                        "risk_usd": s["risk_usd"]})
    return out


def signal(symbol, tf="15m", equity=None, fetch=None):
    """پوستهٔ شبکه‌دار. `fetch(sym, tf, n)` تزریق‌پذیر است تا آزمون
    آفلاین بماند (هیچ آزمونی به شبکه وصل نمی‌شود)."""
    if fetch is None:
        import sources
        fetch = lambda s, t, n: sources.klines(s, t, n)   # noqa: E731
    try:
        cd = fetch(symbol, tf, 200)
        cd4 = fetch(symbol, "4h", 200)
    except Exception as e:                           # noqa: BLE001
        return _no(symbol, tf, f"کندل گرفته نشد: {type(e).__name__}")
    b4 = b1 = None
    if not symbol.upper().startswith("BTC"):
        try:
            b4 = trend(fetch("BTCUSDT", "4h", 200))
            b1 = trend(fetch("BTCUSDT", "1h", 200))
        except Exception:                            # noqa: BLE001
            b4 = b1 = None
    return decide(symbol, cd, tf=tf, cd_4h=cd4, btc_4h=b4, btc_1h=b1,
                  equity=equity)


# ═══════════════════ خودآزمایی (بدون شبکه) ═══════════════════

def _mk(path, t0=0, tf_ms=900_000, base=100.0, end=None):
    """کندلِ ساختگی از یک مسیرِ ضریبی. شکل: [t, o, h, l, c, v].

    `end` یعنی «آخرین کندل دقیقاً این‌جا بسته شود» — t0 از طولِ خودِ
    مسیر حساب می‌شود. بدون آن، هر بار که طولِ سناریو عوض شود سنِ کندل
    هم بی‌سروصدا عوض می‌شد و آزمون به دلیلِ اشتباه می‌افتاد.
    """
    if end is not None:
        t0 = end - (len(path) - 1) * tf_ms
    out, p = [], base
    for i, m in enumerate(path):
        o = p
        c = o * m
        h, lo = max(o, c) * 1.001, min(o, c) * 0.999
        out.append([t0 + i * tf_ms, o, h, lo, c, 1000.0])
        p = c
    return out


def _selftest():
    ok, fail = 0, []

    def chk(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fail.append(name)
            print(f"  ✗ {name}" + (f"  ↳ {extra}" if extra else ""))

    now = 1788800000000
    tf_ms = 900_000

    # مسیرِ واقعیِ ستاپِ شورت: رالیِ بلند → ایمپالسِ نزولیِ کوتاه (که
    # اردر بلاک را می‌سازد) → پولبکِ کم‌عمق به زیرِ همان OB.
    # قیمتِ آخر باید **بالای دامنه** بماند، وگرنه شورت یعنی تعقیبِ ریزش.
    cd = _mk([1.003] * 150 + [0.985] * 3 + [1.002] * 3,
             end=now, tf_ms=tf_ms)
    cd4 = _mk([0.997] * 120, end=now, tf_ms=14_400_000)

    d = decide("AAAUSDT", cd, cd_4h=cd4, btc_4h="down", btc_1h="down",
               equity=1000, now_ms=now)
    chk("خروجی dict معتبر است", isinstance(d, dict) and "action" in d, str(d)[:120])
    chk("هرگز LONG نمی‌دهد", d["action"] in ("SHORT", "NO_SIGNAL"), d["action"])
    chk("قیفِ دروازه‌ها روی خروجی هست", isinstance(d.get("funnel"), list))
    chk("وضعیت اعتبارسنجی روی خروجی هست",
        d.get("validation_status") == VALIDATION_STATUS)
    chk("تولید تأیید نشده است", d.get("production_approved") is False)

    # وتوی مطلقِ بسترِ BTC (قرارداد اجرا بند ۳)
    v = decide("AAAUSDT", cd, cd_4h=cd4, btc_4h="up", btc_1h="up", now_ms=now)
    chk("هر دو تایمِ BTC صعودی = وتو", v["action"] == "NO_SIGNAL", v.get("why"))
    m = decide("AAAUSDT", cd, cd_4h=cd4, now_ms=now)
    chk("بسترِ BTC ناموجود = NO_SIGNAL نه عبورِ کور",
        m["action"] == "NO_SIGNAL" and "بیت‌کوین" in m["why"], m.get("why"))
    b = decide("BTCUSDT", cd, cd_4h=cd4, now_ms=now)
    chk("ولی خودِ BTC از دروازهٔ بستر رد نمی‌شود",
        not any(g["gate"] == "بسترِ BTC" for g in b.get("funnel", [])))

    # ۴س صعودی = رد
    u4 = _mk([1.004] * 120, end=now, tf_ms=14_400_000)
    r = decide("AAAUSDT", cd, cd_4h=u4, btc_4h="down", btc_1h="down",
               now_ms=now)
    chk("۴س صعودی = رد", r["action"] == "NO_SIGNAL" and "۴س" in r["why"],
        r.get("why"))

    # مکان: کفِ دامنه = رد
    low = _mk([0.997] * 199, end=now, tf_ms=tf_ms)
    r = decide("AAAUSDT", low, cd_4h=cd4, btc_4h="down", btc_1h="down",
               now_ms=now)
    chk("شورت از کفِ دامنه رد می‌شود",
        r["action"] == "NO_SIGNAL", r.get("why"))

    # دادهٔ کم و کهنه
    chk("کندل کم = NO_SIGNAL",
        decide("AAAUSDT", cd[:10], now_ms=now)["action"] == "NO_SIGNAL")
    stale = _mk([1.003] * 150 + [0.985] * 3 + [1.002] * 3,
                end=now - 10 * 86400_000, tf_ms=tf_ms)
    chk("کندل کهنه = NO_SIGNAL",
        decide("AAAUSDT", stale, cd_4h=cd4, btc_4h="down", btc_1h="down",
               now_ms=now)["action"] == "NO_SIGNAL")

    # روندِ بی‌جهت واقعاً flat است — نه گِردشده به up (عیب ۶ سپتامبر)
    chk("روندِ بی‌جهت flat است", trend(_mk([1.0] * 60)) == "flat",
        str(trend(_mk([1.0] * 60))))
    chk("روندِ نزولی down است", trend(_mk([0.99] * 60)) == "down")
    chk("روندِ صعودی up است", trend(_mk([1.01] * 60)) == "up")

    # قرارداد اجرا روی خروجیِ سیگنال‌دار
    if d["action"] == "SHORT":
        chk("مارجین ایزوله", d["margin_mode"] == "isolated")
        chk("استاپ و تارگت روی خروجی",
            d.get("stop_loss") and d.get("take_profit"))
        chk("تارگت زیر ورود (شورت)", d["tp1"] < d["entry"])
        chk("استاپ بالای ورود (شورت)", d["sl"] > d["entry"])
        chk("اهرم از محافظ لیکویید رد نمی‌شود",
            d["leverage"] <= min(P["max_leverage"],
                                 int(P["liq_guard"] / d["stop_pct"])),
            f"lev={d['leverage']} stop={d['stop_pct']}")
        chk("استاپ از کفِ هندسه گشادتر است",
            d["stop_pct"] >= P["min_stop_pct"], str(d["stop_pct"]))
        chk("RR خالص از کف بالاتر است", d["rr_net"] >= P["min_net_rr"])
        chk("ضررِ استاپ ۲٪ سرمایه می‌ماند",
            abs(d["risk_usd"] - 20.0) < 0.01, str(d.get("risk_usd")))
        chk("مرزِ صادقانه روی خروجی هست", "PAPER_ONLY" in d["boundary"])
        chk("امضای پنل هست", d["panel"] == PANEL_NAME)
        chk("شناسه و نسخهٔ استراتژی هست",
            d["strategy"] == STRATEGY_ID and d["version"] == STRATEGY_VERSION)
    else:
        fail.append("مسیرِ سیگنال‌دار اصلاً فعال نشد")
        print(f"  ✗ سناریوی شورت به SHORT نرسید: {d.get('why')}")

    # اهرم و سایز، مستقل
    chk("محافظ لیکویید: استاپ ۵٪ → اهرم ۱۰", leverage_for(5.0) == 10)
    chk("سقف اهرم ۲۰ رعایت می‌شود", leverage_for(0.1) == P["max_leverage"])
    s = size_for(1000, 2.0, 10)
    chk("سایز از ریسکِ ۲٪ می‌آید، نه از اهرم",
        abs(s["risk_usd"] - 20) < 1e-6 and abs(s["notional_usd"] - 1000) < 1e-6,
        str(s))

    print(f"{ok} بررسی گذشت" + (f"، {len(fail)} افتاد: {fail}" if fail else ""))
    return not fail


def main(argv):
    if "--selftest" in argv:
        return 0 if _selftest() else 1
    sym = next((a for a in argv[1:] if not a.startswith("-")), "BTCUSDT")
    tf = "15m"
    if "--tf" in argv:
        tf = argv[argv.index("--tf") + 1]
    print(json.dumps(signal(sym, tf=tf), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
