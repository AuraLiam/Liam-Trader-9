#!/usr/bin/env python3
"""آزمایشگاه مراقبان — ۱۲ استراتژی، سه تایم‌فریم، بدون خبر از فردا.

دستور حمید (۳ سپتامبر): «حالا پیپرمود وارد مرحلهٔ جدیدی می‌شود؛ ۱۲
متخصص ۱۲ استراتژی جدید اضافه می‌کنند و هر کدام ستاپ پیشنهادی خودش را
می‌دهد، و پیپر تریدینگ روی ۱س و ۱۵د و ۵د روی همان ارزها **جداگانه**
اجرا می‌شود… برای جمع‌آوری دادهٔ تاریخی بیشتر، ۲ تا ۳ سال عقب برویم و
**بدون اطلاع از یک روز جلوتر** طبق استراتژی خودم ترید کنیم. برای هر
ترید، ۱۲ ایجنت نتیجه را پیش‌بینی کنند: درست +۱، غلط −۱… و در آخر
بررسی شود ۱س چه نتیجه‌ای داد، ۱۵د چه، و کدام متخصص‌ها امتیاز بیشتری
گرفتند.»

## چهار قاعده‌ای که این آزمایشگاه را از یک بک‌تستِ معمولی جدا می‌کند

**۱. هیچ تابعی کندلِ بعد از `i` را نمی‌بیند.** ورودی هر استراتژی
`cd[:i+1]` است — برشِ واقعی، نه شاخصِ نگاه‌نکردنی. پس نشتِ آینده
غیرممکن است نه «بعید»؛ و آزمون با اثبات منفی همین را قفل می‌کند.

**۲. سه تایم‌فریم، سه دفترِ جدا.** حمید گفت «جداگانه». اختلاطشان یعنی
نتیجهٔ ۵د پشتِ نتیجهٔ ۱س پنهان شود، در حالی که سؤال دقیقاً همین است که
کدام تایم بهتر جواب می‌دهد.

**۳. پیش‌بینی جدا از پیشنهاد است.** هر مراقب روی **هر** معامله رأی
می‌دهد — چه خودش پیشنهادش داده باشد چه نه. ممتنع مجاز است و صفر امتیاز
می‌گیرد؛ «چیزی نمی‌گویم» جوابِ معتبر است و نباید با حدسِ تصادفی جایگزین
شود.

**۴. دلیلِ استاپ و دلیلِ تارگت ثبت می‌شود** (بند H7.6): هر معامله با
`exit_reason` بسته می‌شود — تارگت، استاپ، سقفِ نگهداری، یا پایانِ داده.

## مرز

خروجی این آزمایشگاه **دفتر آزمایش** است، جدا از دفتر پیپر تولید. هیچ
استراتژی‌ای از این‌جا وارد سیگنال واقعی نمی‌شود مگر از مسیر قانون ۰۳:
CI بالای صفر روی دادهٔ خارج-از-نمونه و تأیید صریح حمید.

    python3 -m hamid.guardian_lab --demo
"""
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import phoenix as PHX                     # noqa: E402

ROOT = HERE.parents[2]
BRAIN = ROOT / "brain" / "guardian-lab"
TRADES = BRAIN / "trades.jsonl"                      # append-only
OUT = ROOT / "signals" / "guardian-lab.json"

ENGINE = "E18"
PANEL = "لیام تریدر ۹"

TFS = ("1h", "15m", "5m")                            # دستور حمید — جداگانه
WARMUP = 60                  # کندل لازم پیش از اولین تصمیم
MAX_HOLD = {"1h": 24, "15m": 32, "5m": 48}           # سقف نگهداری، به کندل
RR = 2.0                     # تارگت = این‌قدر برابرِ استاپ
STOP_ATR = 1.5               # استاپ = این‌قدر ATR
FEE_ROUND_TRIP_PCT = 0.15    # کارمزد دو سر + لغزش (راستی‌آزمایی‌شدهٔ ۱۶ اوت)
MIN_TRADES_VERDICT = 100     # زیر این، حکمِ تایم‌فریم اعلام نمی‌شود
# پنجرهٔ دیدِ استراتژی‌ها. عمیق‌ترین نگاهِ واقعیِ آن‌ها ۱۲۰ کندل است (ثور)
# و فقط حمل با `_swings(cd)` بی‌کران بود — یعنی هر بار کلِ گذشته را
# می‌گشت و هزینه درجه‌دو می‌شد. اندازه‌گیری روی همین ماشین: ۱۰۰۰ کندل
# ۲.۴ ثانیه، ۲۰۰۰ کندل ۹.۲، ۴۰۰۰ کندل ۳۷.۶ — یعنی دو برابر داده، چهار
# برابر زمان. با همین شیب، یک سریِ ۱۰۵٬۱۲۰تایی ~۷ ساعت می‌شد و اجرای
# واقعیِ ۴ سپتامبر بعد از ۸۰ دقیقه لغو شد.
#
# ۴۰۰ سه برابرِ عمیق‌ترین نگاهِ واقعی است، پس هیچ استراتژی‌ای چیزی را که
# لازم دارد از دست نمی‌دهد؛ فقط «آخرین سوینگِ دو سال پیش» از دستِ حمل
# می‌رود، که ساختارِ قابل‌معامله نیست. نرخ یکسانیِ تصمیم‌ها اندازه‌گیری و
# در آزمون قفل شده — ادعا نمی‌شود.
WINDOW = 400


# ── کمکی‌های قطعی (فقط از گذشته) ────────────────────────────────────────
def _atr(cd, n=14):
    if len(cd) < 2:
        return 0.0
    tr = [max(cd[i]["h"] - cd[i]["l"], abs(cd[i]["h"] - cd[i - 1]["c"]),
              abs(cd[i]["l"] - cd[i - 1]["c"])) for i in range(1, len(cd))]
    tr = tr[-n:]
    return sum(tr) / len(tr) if tr else 0.0


def _ema(vals, n):
    if not vals:
        return None
    k = 2.0 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def _ibs(c):
    rng = c["h"] - c["l"]
    return (c["c"] - c["l"]) / rng if rng > 0 else 0.5


def _swings(cd, left=2, right=2):
    hi, lo = [], []
    for i in range(left, len(cd) - right):
        w = cd[i - left:i + right + 1]
        if cd[i]["h"] >= max(x["h"] for x in w):
            hi.append(i)
        if cd[i]["l"] <= min(x["l"] for x in w):
            lo.append(i)
    return hi, lo


def to_candles(rows):
    """ردیفِ خامِ منبع → دیکشنریِ کندل.

    `sources.klines` شکل بایننسی برمی‌گرداند: `[open_ms, o, h, l, c, v,
    close_ms]` — **لیست**، نه دیکشنری. هر ماژول دیگرِ این مخزن همین
    تبدیل را دارد؛ اجرای واقعیِ ۴ سپتامبر آن را نداشت و نتیجه‌اش این شد
    که هر استراتژی روی `c["h"]` خطا داد، خطا بلعیده شد، و ۹ سریِ واقعی
    با ~۴۹۰٬۰۰۰ کندل **صفر معامله** ساختند بی‌آنکه چیزی گزارش شود.
    """
    out = []
    for k in rows or []:
        if isinstance(k, dict):
            out.append(k)
            continue
        out.append({"t": k[0], "o": float(k[1]), "h": float(k[2]),
                    "l": float(k[3]), "c": float(k[4]),
                    "v": float(k[5]) if len(k) > 5 else 0.0})
    return out


# ── دوازده استراتژی، هر کدام از میدانِ تخصص خودِ همان مراقب ─────────────
# قرارداد: `f(cd)` که `cd` برشِ **بسته‌شدهٔ** تا همین لحظه است. خروجی
# "long" / "short" / None. هیچ‌کدام حق دیدن کندل بعدی را ندارد.

def _s_taurus(cd, ctx=None):
    """ثور — روند تایم بالا: EMA۲۱ بالای EMA۵۵ و پولبک به EMA۲۱."""
    cl = [c["c"] for c in cd]
    e21, e55 = _ema(cl[-80:], 21), _ema(cl[-120:], 55)
    if e21 is None or e55 is None:
        return None
    last = cd[-1]
    if e21 > e55 and last["l"] <= e21 <= last["c"]:
        return "long"
    if e21 < e55 and last["h"] >= e21 >= last["c"]:
        return "short"
    return None


def _s_aries(cd, ctx=None):
    """حمل — ایمپالس، BOS، و **پولبک دوم** (روش حمید، نه پولبک اول)."""
    hi, lo = _swings(cd)
    if len(hi) < 2 or len(lo) < 2:
        return None
    a = _atr(cd)
    if a <= 0:
        return None
    last = cd[-1]
    # شکست سقف قبلی (BOS)، بعد دو بار برگشت به همان ناحیه
    top = cd[hi[-2]]["h"]
    bot = cd[lo[-2]]["l"]
    broke_up = any(c["c"] > top for c in cd[hi[-2] + 1:])
    broke_dn = any(c["c"] < bot for c in cd[lo[-2] + 1:])
    if broke_up:
        backs = sum(1 for c in cd[hi[-2] + 1:] if c["l"] <= top + 0.2 * a)
        if backs >= 2 and last["l"] <= top + 0.5 * a <= last["c"]:
            return "long"
    if broke_dn:
        backs = sum(1 for c in cd[lo[-2] + 1:] if c["h"] >= bot - 0.2 * a)
        if backs >= 2 and last["h"] >= bot - 0.5 * a >= last["c"]:
            return "short"
    return None


def _s_leo(cd, ctx=None):
    """اسد — اردر بلاک به تعریف حمید: اولین کندلِ قویِ مخالف پیش از حرکت."""
    a = _atr(cd)
    if a <= 0 or len(cd) < 30:
        return None
    last = cd[-1]
    for j in range(len(cd) - 25, len(cd) - 3):
        c = cd[j]
        body = abs(c["c"] - c["o"])
        wick = (c["h"] - max(c["o"], c["c"])) + (min(c["o"], c["c"]) - c["l"])
        if body <= wick or body < 0.8 * a:
            continue
        moved = cd[j + 1]["c"] - c["c"]
        if c["c"] > c["o"] and moved > a and last["l"] <= c["h"] and last["c"] >= c["l"]:
            return "long"
        if c["c"] < c["o"] and moved < -a and last["h"] >= c["l"] and last["c"] <= c["h"]:
            return "short"
    return None


def _s_cancer(cd, ctx=None):
    """سرطان — سوییپ نقدینگی: ویک زیر کف اخیر، بستنِ بالای آن."""
    a = _atr(cd)
    if a <= 0 or len(cd) < 25:
        return None
    prev = cd[-21:-1]
    lo = min(c["l"] for c in prev)
    hi = max(c["h"] for c in prev)
    last = cd[-1]
    if last["l"] < lo - 0.1 * a and last["c"] > lo:
        return "long"
    if last["h"] > hi + 0.1 * a and last["c"] < hi:
        return "short"
    return None


def _s_pisces(cd, ctx=None):
    """حوت — هندسهٔ کندل: IBS در انتهای دامنه + بدنهٔ بزرگ‌تر از میانه."""
    if len(cd) < 25:
        return None
    last = cd[-1]
    bodies = [abs(c["c"] - c["o"]) for c in cd[-21:-1]]
    med = statistics.median(bodies) if bodies else 0
    if abs(last["c"] - last["o"]) < med * 1.2:
        return None
    v = _ibs(last)
    if v <= 0.25:
        return "long"
    if v >= 0.75:
        return "short"
    return None


def _s_libra(cd, ctx=None):
    """میزان — فقط جایی که هندسه کارمزد را می‌خرد: استاپ به‌قدر کافی گشاد."""
    a = _atr(cd)
    last = cd[-1]
    if a <= 0 or last["c"] <= 0:
        return None
    stop_pct = STOP_ATR * a / last["c"] * 100
    if stop_pct < FEE_ROUND_TRIP_PCT / 0.15:         # کارمزد ≤ ۰.۱۵R
        return None
    return _s_taurus(cd, ctx)                        # جهت از روند، دروازه از هندسه


# مراقبی که «نسخهٔ تنگ‌ترِ» مراقب دیگری است — با دلیل، نه بی‌صدا.
#
# اندازه‌گیری بک‌تست ۲ ساله (۴ سپتامبر): جدی روی ثور سوار است و فقط
# فیلترِ دریفت اضافه می‌کند. روی دادهٔ واقعی واقعاً جدا شد (۱۳۴٬۰۱۴ رأی
# در برابر ۱۴۷٬۰۳۲ — یعنی ۱۳٬۰۱۸ بار بیشتر ممتنع)، پس دوقلوی حوت/سنبله
# نیست. ولی چون هرگز **خلافِ** ثور رأی نمی‌دهد، رأیش مستقل هم نیست و
# در میانگین وزنی سهمِ ثور را سنگین‌تر می‌کند.
#
# قانون ۱۶ تخصص جدی را «حافظه و کارنامه» تعریف کرده: n≥۱۲ با انتظار
# مثبت = تأیید، <−۰.۳R = مخالف. یعنی باید از **دفتر بسته** بخواند نه
# از دریفتِ ۵۰ کندل. بازنویسی‌اش تغییر استراتژی است و طبق قانون ۰۳
# تأیید صریح حمید می‌خواهد؛ تا آن روز این‌جا ثبت است تا فراموش نشود.
NARROWER = {
    ("capricorn", "taurus"):
        "جدی = ثور + فیلتر دریفت؛ هرگز خلافش رأی نمی‌دهد. طبق قانون ۱۶ "
        "باید از دفتر بسته بخواند — بازنویسی منتظر تأیید حمید (قانون ۰۳)",
}


def _data_clean(cd):
    """دادهٔ ۲۰ کندل اخیر سالم است؟ (شکاف بزرگ یا کندلِ مرده ندارد)"""
    if len(cd) < 25:
        return None                                  # نمی‌دانم ≠ سالم
    for i in range(len(cd) - 20, len(cd)):
        if cd[i]["h"] <= cd[i]["l"]:
            return False
        if abs(cd[i]["o"] - cd[i - 1]["c"]) / max(cd[i - 1]["c"], 1e-12) > 0.03:
            return False
    return True


def _s_virgo(cd, ctx=None):
    """سنبله — کیفیت داده. **هیچ‌وقت جهت پیشنهاد نمی‌دهد.**

    عیبِ اندازه‌گیری‌شده (بک‌تست ۲ ساله، ۴ سپتامبر): نسخهٔ قبلی وقتی
    داده سالم بود `_s_pisces` را برمی‌گرداند. روی کندلِ پرپِ
    BTC/ETH/SOL داده **همیشه** سالم است، پس سنبله در هر ۲۶۸٬۵۶۱ رأی
    دقیقاً حوت شد — کارنامه‌شان بیت‌به‌بیت یکی درآمد
    (−۴۹٬۰۰۳ امتیاز، ۱۰۱٬۲۴۸ پیشنهاد، ۴۰.۹٪ دقت برای هر دو).

    چرا این فقط یک تکرارِ بی‌ضرر نیست: شورا رأی وزنی می‌گیرد، پس نظرِ
    حوت **دو بار** شمرده می‌شد و شورای دوازده‌نفره عملاً یازده صدا
    داشت با یکی از آن‌ها دو برابر. یعنی وزنی که قانون ۱۶ به کارنامهٔ
    هر مراقب گره زده بود، بی‌سروصدا شکسته بود.

    قانون ۱۶ تخصص سنبله را «کیفیت داده، هم‌زمانی» تعریف کرده — نه
    جهت. پس این‌جا هیچ ستاپی پیشنهاد نمی‌کند؛ حرفش فقط در رأی است
    (`predict`): دادهٔ خراب = مخالف، دادهٔ سالم = ممتنع.
    """
    return None


def _s_capricorn(cd, ctx=None):
    """جدی — حافظه: همان جهتی که در ۵۰ کندل اخیر بازده مثبت داده."""
    if len(cd) < 60:
        return None
    d = _s_taurus(cd, ctx)
    if d is None:
        return None
    rets = [cd[i]["c"] / cd[i - 1]["c"] - 1 for i in range(len(cd) - 50, len(cd))]
    drift = sum(rets)
    if d == "long" and drift <= 0:
        return None
    if d == "short" and drift >= 0:
        return None
    return d


def _s_scorpio(cd, ctx=None):
    """عقرب — دامیننس: بی‌سری دامیننس، رأی نمی‌دهد (قانون ۱)."""
    dom = (ctx or {}).get("dominance")
    if not dom or len(dom) < 3:
        return None
    d = _s_taurus(cd, ctx)
    if d is None:
        return None
    rising = dom[-1] > dom[-3]
    if d == "long" and rising:                       # USDT.D صعودی = بازار نزولی
        return None
    if d == "short" and not rising:
        return None
    return d


def _s_gemini(cd, ctx=None):
    """جوزا — بستر بیت‌کوین: بی‌سری BTC، رأی نمی‌دهد."""
    btc = (ctx or {}).get("btc")
    if not btc or len(btc) < 5:
        return None
    d = _s_taurus(cd, ctx)
    if d is None:
        return None
    up = btc[-1] > btc[-5]
    return d if ((d == "long") == up) else None


def _s_sagittarius(cd, ctx=None):
    """قوس — خبر: در بک‌تست تاریخی خبرِ هم‌ترازِ زمان نداریم، پس ممتنع."""
    return None


def _s_aquarius(cd, ctx=None):
    """دلو — جمعیت: فاندینگ/ترند تاریخی هم‌تراز نداریم، پس ممتنع."""
    return None


STRATEGIES = {"taurus": _s_taurus, "aries": _s_aries, "leo": _s_leo,
              "cancer": _s_cancer, "pisces": _s_pisces, "libra": _s_libra,
              "virgo": _s_virgo, "capricorn": _s_capricorn,
              "scorpio": _s_scorpio, "gemini": _s_gemini,
              "sagittarius": _s_sagittarius, "aquarius": _s_aquarius}

# دو مراقبِ عمداً ساکت — نبودِ دادهٔ هم‌ترازِ زمان، نه نبودِ تخصص.
SILENT = {"sagittarius": "خبرِ هم‌ترازِ زمانِ گذشته در دفتر نیست — عدد جعل نمی‌شود",
          "aquarius": "فاندینگ/ترند تاریخیِ هم‌تراز نداریم — ممتنع"}


# ── پیش‌بینی: هر مراقب روی هر معامله ────────────────────────────────────
def predict(gid, cd, direction, ctx=None):
    """رأی این مراقب دربارهٔ نتیجهٔ همین معامله: +۱ / −۱ / ممتنع.

    قاعده‌اش ساده و قطعی است: اگر استراتژی خودش همین جهت را می‌دید،
    می‌گوید «می‌رسد»؛ اگر جهت مخالف را می‌دید، می‌گوید «نمی‌رسد»؛ اگر
    چیزی نمی‌دید، **ممتنع** — و ممتنع صفر امتیاز می‌گیرد، نه حدسِ سکه.
    """
    # سنبله جهت پیشنهاد نمی‌دهد، ولی حق رأی دارد: حرفش دربارهٔ **داده**
    # است نه بازار. معامله‌ای که روی دادهٔ خراب بسته شده، مخالف دارد؛
    # روی دادهٔ سالم، سنبله حرفی برای گفتن ندارد و ممتنع است (قانون ۱).
    if gid == "virgo":
        clean = _data_clean(cd)
        return None if clean else -1
    f = STRATEGIES.get(gid)
    if f is None:
        return None
    try:
        own = f(cd, ctx)
    except Exception:                                # noqa: BLE001
        return None
    if own is None:
        return None
    return 1 if own == direction else -1


# ── شبیه‌سازی یک معامله، فقط با کندل‌های بعدی ──────────────────────────
def simulate(cd, i, direction, tf, rr=RR, stop_atr=STOP_ATR,
             fee_pct=FEE_ROUND_TRIP_PCT):
    """ورود روی بستِ کندل i؛ خروج با اولین برخورد. دلیل خروج ثبت می‌شود."""
    a = _atr(cd[:i + 1])
    entry = cd[i]["c"]
    if a <= 0 or entry <= 0:
        return None
    risk = stop_atr * a
    if direction == "long":
        sl, tp = entry - risk, entry + rr * risk
    else:
        sl, tp = entry + risk, entry - rr * risk
    hold = MAX_HOLD.get(tf, 24)
    fee_r = (fee_pct / 100.0) * entry / risk
    for j in range(i + 1, min(len(cd), i + 1 + hold)):
        c = cd[j]
        hit_sl = (c["l"] <= sl) if direction == "long" else (c["h"] >= sl)
        hit_tp = (c["h"] >= tp) if direction == "long" else (c["l"] <= tp)
        if hit_sl and hit_tp:
            # هر دو در یک کندل: بدبینانه استاپ. خوش‌بینیِ درون‌کندلی
            # همان چیزی است که بک‌تست را دروغ‌گو می‌کند.
            return {"R": -1.0, "R_net": round(-1.0 - fee_r, 4), "bars": j - i,
                    "exit_reason": "استاپ (هر دو در یک کندل — فرضِ بدبینانه)",
                    "entry": entry, "sl": sl, "tp": tp, "fee_r": round(fee_r, 4)}
        if hit_sl:
            return {"R": -1.0, "R_net": round(-1.0 - fee_r, 4), "bars": j - i,
                    "exit_reason": "استاپ — قیمت به نقطهٔ ابطال رسید",
                    "entry": entry, "sl": sl, "tp": tp, "fee_r": round(fee_r, 4)}
        if hit_tp:
            return {"R": float(rr), "R_net": round(rr - fee_r, 4), "bars": j - i,
                    "exit_reason": f"تارگت — {rr}R پیش از استاپ خورد",
                    "entry": entry, "sl": sl, "tp": tp, "fee_r": round(fee_r, 4)}
    j = min(len(cd) - 1, i + hold)
    if j <= i:
        return None
    out = cd[j]["c"]
    r = ((out - entry) if direction == "long" else (entry - out)) / risk
    ended = j >= len(cd) - 1 and j < i + hold
    return {"R": round(r, 4), "R_net": round(r - fee_r, 4), "bars": j - i,
            "exit_reason": ("پایان داده — معامله باز بود" if ended
                            else f"سقف نگهداری ({hold} کندل) — نه تارگت، نه استاپ"),
            "entry": entry, "sl": sl, "tp": tp, "fee_r": round(fee_r, 4)}


# ── اجرای رو-به-جلو روی یک تایم‌فریم ────────────────────────────────────
def run_tf(sym, tf, cd, ctx=None, warmup=WARMUP, step=1, now_ms=None, deadline=None):
    """هر کندل، هر مراقب پیشنهاد می‌دهد؛ همه پیش‌بینی می‌کنند.

    برشِ `cd[:i+1]` تنها چیزی است که به استراتژی می‌رسد — پس نشتِ آینده
    ساختاراً ناممکن است، نه «مراقبیم که نشود».

    `deadline` (ثانیهٔ مطلقِ `time.time()`) بازپخش را **وسطِ سری** قطع
    می‌کند و می‌گوید تا کجا رفت. بدون این، بودجه فقط بین سری‌ها سنجیده
    می‌شد: سریِ آخر که شروع می‌شد تا آخر می‌رفت، از سقف job رد می‌شد،
    job کشته می‌شد و **هیچ نتیجه‌ای ذخیره نمی‌شد** — ۸۰ دقیقه محاسبه با
    خروجیِ صفر. نتیجهٔ ناقصِ اعلام‌شده از نتیجهٔ نداشته بهتر است.
    """
    ctx = ctx or {}
    trades = []
    errors, first_error = {}, {}
    run_tf.last_cut = None
    bars = range(warmup, len(cd) - 2, step)
    total = len(bars)
    for done, i in enumerate(bars):
        if deadline is not None and time.time() > deadline:
            run_tf.last_cut = {"at_bar": i, "of_bars": len(cd), "replayed": done,
                               "covered_pct": round(100 * done / max(1, total), 1)}
            break
        lo = max(0, i + 1 - WINDOW)                  # پنجرهٔ ثابت — بالا را ببین
        past = cd[lo:i + 1]
        sub = {"dominance": (ctx.get("dominance") or [])[lo:i + 1] or None,
               "btc": (ctx.get("btc") or [])[lo:i + 1] or None}
        for gid, f in STRATEGIES.items():
            try:
                d = f(past, sub)
            except Exception as e:                   # noqa: BLE001
                # خطا ≠ «بی‌نظر». بلعیدنش همان چیزی بود که نیم‌میلیون کندل
                # را به صفر معامله تبدیل کرد و هیچ‌کس نفهمید. شمرده و
                # گزارش می‌شود؛ اجرا نمی‌ایستد ولی ساکت هم نمی‌ماند.
                errors[gid] = errors.get(gid, 0) + 1
                if gid not in first_error:
                    first_error[gid] = f"{type(e).__name__}: {e}"
                d = None
            if d not in ("long", "short"):
                continue
            res = simulate(cd, i, d, tf)
            if res is None:
                continue
            votes = {}
            for other in STRATEGIES:
                v = predict(other, past, d, sub)
                if v is not None:
                    votes[other] = v
            trades.append({"sym": sym, "tf": tf, "i": i, "t": cd[i]["t"],
                           "by": gid, "dir": d, **res, "votes": votes})
    if errors:
        tot = sum(errors.values())
        worst = max(errors, key=errors.get)
        print(f"  ⚠ {sym} {tf}: {tot} خطای استراتژی روی {len(errors)} مراقب — "
              f"نمونه [{worst}] {first_error.get(worst)}", flush=True)
    run_tf.last_errors = dict(errors)
    return trades


# ── نمره‌دهی: به تفکیک تایم‌فریم و به تفکیک متخصص ──────────────────────
def score(trades):
    """درست +۱، غلط −۱ (دستور حمید). ممتنع اصلاً در دفتر نیست."""
    by_tf, by_g, by_g_tf = {}, {}, {}
    for t in trades:
        good = t["R_net"] > 0
        tf = t["tf"]
        s = by_tf.setdefault(tf, {"n": 0, "wins": 0, "sum_R": 0.0, "sum_net": 0.0,
                                  "by_reason": {}})
        s["n"] += 1
        s["wins"] += 1 if good else 0
        s["sum_R"] += t["R"]
        s["sum_net"] += t["R_net"]
        rk = (t.get("exit_reason") or "?").split("—")[0].strip()
        s["by_reason"][rk] = s["by_reason"].get(rk, 0) + 1
        # پیشنهاددهنده
        p = by_g.setdefault(t["by"], {"proposed": 0, "points": 0, "votes": 0,
                                      "sum_net": 0.0})
        p["proposed"] += 1
        p["sum_net"] += t["R_net"]
        # پیش‌بینی‌کننده‌ها
        for gid, v in (t.get("votes") or {}).items():
            g = by_g.setdefault(gid, {"proposed": 0, "points": 0, "votes": 0,
                                      "sum_net": 0.0})
            g["votes"] += 1
            g["points"] += 1 if (v > 0) == good else -1
            gt = by_g_tf.setdefault(gid, {}).setdefault(tf, {"votes": 0, "points": 0})
            gt["votes"] += 1
            gt["points"] += 1 if (v > 0) == good else -1
    for s in by_tf.values():
        s["win_pct"] = round(100 * s["wins"] / s["n"], 1) if s["n"] else None
        s["mean_R"] = round(s["sum_R"] / s["n"], 4) if s["n"] else None
        s["mean_net"] = round(s["sum_net"] / s["n"], 4) if s["n"] else None
        s["ci95_net"] = _ci([t for t in trades], None) if False else None
    for tf, s in by_tf.items():
        xs = [t["R_net"] for t in trades if t["tf"] == tf]
        s["ci95_net"] = _ci(xs)
        s["verdict"] = _verdict(s["n"], s["ci95_net"])
    for gid, g in by_g.items():
        g["accuracy"] = (round(100 * (g["points"] + g["votes"]) / (2 * g["votes"]), 1)
                         if g["votes"] else None)
        g["mean_net"] = round(g["sum_net"] / g["proposed"], 4) if g["proposed"] else None
        g["silent_why"] = SILENT.get(gid)
    return {"by_tf": by_tf, "by_guardian": by_g, "by_guardian_tf": by_g_tf,
            "trades": len(trades)}


def _ci(xs, _=None):
    n = len(xs)
    if n < 2:
        return None
    m = statistics.mean(xs)
    sd = statistics.stdev(xs)
    h = 1.96 * sd / math.sqrt(n)
    return [round(m - h, 4), round(m + h, 4)]


def _verdict(n, ci):
    if n < MIN_TRADES_VERDICT:
        return f"UNDECIDED — n={n} کمتر از {MIN_TRADES_VERDICT}، حکم اعلام نمی‌شود"
    if ci and ci[0] > 0:
        return "لبهٔ خالص بالای صفر — نامزد قانون ۰۳ (نه ورود خودکار)"
    if ci and ci[1] < 0:
        return "لبهٔ خالص زیر صفر — این هندسه اجرا نشود"
    return "CI شامل صفر — از نویز جدا نشده"


def snapshot(res, syms=None, span=None, now_ms=None):
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    return {"generated": now, "engine": ENGINE, "panel": PANEL,
            "symbols": list(syms or []), "span": span,
            "timeframes": list(TFS),
            "trades": res["trades"], "by_tf": res["by_tf"],
            "by_guardian": res["by_guardian"],
            "by_guardian_tf": res["by_guardian_tf"],
            "rules": {"rr": RR, "stop_atr": STOP_ATR, "max_hold": MAX_HOLD,
                      "fee_round_trip_pct": FEE_ROUND_TRIP_PCT,
                      "min_trades_verdict": MIN_TRADES_VERDICT},
            "boundary": "دفتر آزمایش است، جدا از پیپر تولید. هیچ استراتژی‌ای از "
                        "این‌جا وارد سیگنال واقعی نمی‌شود مگر با CI بالای صفر روی "
                        "دادهٔ خارج-از-نمونه و تأیید صریح حمید (قانون ۰۳)."}


def append_trades(trades, path=None):
    p = Path(path or TRADES)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for t in trades:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    return len(trades)


# ── نمایش ────────────────────────────────────────────────────────────────
def _demo_series(n=900, seed=11):
    """سری قطعیِ روندی-نوسانی — فقط برای نمایش و آزمون، نه ادعای عملکرد."""
    cd, p, s = [], 100.0, seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        u = s / 2147483648.0 - 0.5
        p *= 1 + 0.0016 * math.sin(i / 41.0) + 0.004 * u
        o = p
        c = p * (1 + 0.002 * u)
        cd.append({"t": 1_700_000_000_000 + i * 900_000, "o": o,
                   "h": max(o, c) * 1.0025, "l": min(o, c) * 0.9975, "c": c,
                   "v": 100.0 + 10 * abs(u)})
    return cd


def resample(cd, k):
    """k کندل را به یک کندل تبدیل می‌کند — ۵د → ۱۵د (k=3) و → ۱س (k=12).

    بدون این، «سه تایم‌فریم جداگانه» روی یک سریِ یکسان اجرا می‌شد و هر
    سه عددِ یکسان می‌دادند؛ یعنی دقیقاً همان سؤالی که حمید پرسید
    («۱س چه داد، ۱۵د چه داد») بی‌جواب می‌ماند.
    """
    out = []
    for i in range(0, len(cd) - k + 1, k):
        w = cd[i:i + k]
        out.append({"t": w[0]["t"], "o": w[0]["o"],
                    "h": max(x["h"] for x in w), "l": min(x["l"] for x in w),
                    "c": w[-1]["c"], "v": sum(x.get("v") or 0 for x in w)})
    return out


def deep_klines(sym, tf, want, quiet=True):
    """عمیق‌ترین سریِ **سالم** که منبع می‌دهد — نه «همه یا هیچ».

    دو واقعیتِ اندازه‌گیری‌شده (۴ سپتامبر) این تابع را لازم کرد:

    ۱. مسیر اسپات صفحه‌بندی ندارد (سقف ۱۰۰۰ کندل)، پس هیچ‌کدام از سه
       تایم‌فریمِ دو ساله را نمی‌تواند بدهد. فقط پرپِ صفحه‌بندی‌شده می‌تواند.
    ۲. `sources.sane` سریِ کوتاه‌تر از ۹۰٪ خواسته را رد می‌کند. یعنی اگر
       تاریخچهٔ صرافی به دو سال نرسد، نتیجه **هیچ** می‌شود نه «هرچه هست» —
       و ما حتی نمی‌فهمیم چقدر تاریخچه وجود داشت.

    پس عمق را نردبانی کم می‌کنیم تا اولین سریِ سالم بیاید، و همان‌جا صریح
    می‌گوییم واقعاً چند سال گیر آمد. عددِ نیامده جعل نمی‌شود.
    """
    import sources
    tried = []
    w = int(want)
    while w >= max(WARMUP + 50, 400):
        try:
            rows = sources.perp_klines(sym, tf, w, quiet=quiet)
            if rows and len(rows) >= WARMUP + 50:
                return to_candles(rows), {"asked": int(want), "got": len(rows),
                                          "ladder": tried}
        except Exception as e:                       # noqa: BLE001
            tried.append(f"{w}:{type(e).__name__}")
        else:
            tried.append(f"{w}:کوتاه")
        w //= 2
    return None, {"asked": int(want), "got": 0, "ladder": tried}


def run_real(syms, years=2.0, step=1, quiet=True, budget_s=None, tfs=None):
    """اجرای واقعی روی کندل بازار — «۲ تا ۳ سال عقب» (بند H7.3).

    هر تایم‌فریم سریِ خودش را از منبع می‌گیرد (نه بازنمونه‌گیریِ ۵د)، چون
    عمقِ تاریخیِ در دسترس برای هر تایم فرق می‌کند و بازنمونه‌گیری از سریِ
    کوتاه، «۲ سال ۱ساعته» نمی‌سازد.

    ترتیب از ارزان به گران (۱س → ۱۵د → ۵د) و با بودجهٔ زمانی: دو سالِ ۵د
    یعنی ~۱۰۵۲ صفحهٔ ۲۰۰تایی برای هر نماد، و اگر اول اجرا شود ممکن است کلِ
    job را بخورد و هیچ نتیجه‌ای نماند. این‌طوری تایم‌های بالا همیشه تمام
    می‌شوند و ۵د هرچه وقت ماند برمی‌دارد — با ثبتِ صریحِ آن‌چه نرسید.
    """
    per_day = {"1h": 24, "15m": 96, "5m": 288}
    order = tuple(t for t in ("1h", "15m", "5m")     # ارزان‌ترین اول
                  if tfs is None or t in tfs)
    t0 = time.time()
    deadline = (t0 + budget_s) if budget_s is not None else None
    trades, got, skipped = [], {}, []
    for tf in order:
        want = int(years * 365 * per_day[tf])
        for sym in syms:
            if budget_s is not None and time.time() - t0 > budget_s:
                skipped.append({"sym": sym, "tf": tf,
                                "why": f"بودجهٔ {budget_s}s تمام شد پیش از رسیدن به این سری"})
                continue
            cd, info = deep_klines(sym, tf, want, quiet=quiet)
            if not cd:
                print(f"  {sym} {tf}: کندل نیامد (نردبان {info['ladder'][:3]}) — کنار گذاشته شد",
                      flush=True)
                skipped.append({"sym": sym, "tf": tf, "why": "سری سالم نیامد",
                                "ladder": info["ladder"][:4]})
                continue
            yrs = round(len(cd) / (365 * per_day[tf]), 2)
            print(f"  {sym} {tf}: {len(cd):,} کندل ≈ {yrs} سال "
                  f"(خواسته {info['asked']:,}) · {int(time.time() - t0)}s", flush=True)
            got.setdefault(tf, []).append(len(cd))
            trades += run_tf(sym, tf, cd, step=step, deadline=deadline)
            cut = getattr(run_tf, "last_cut", None)
            if cut:
                why = (f"بودجه وسطِ بازپخش تمام شد — {cut['covered_pct']}٪ سری "
                       f"({cut['replayed']:,} کندل) بازپخش شد")
                skipped.append({"sym": sym, "tf": tf, "why": why, "cut": cut})
                print(f"  ⏹ {sym} {tf}: {why}", flush=True)
    span = {tf: {"series": len(v), "bars_median": int(statistics.median(v)),
                 "years_median": round(statistics.median(v) / (365 * per_day[tf]), 2)}
            for tf, v in got.items()}
    return trades, {"per_tf": span, "skipped": skipped,
                    "asked_years": years, "elapsed_s": int(time.time() - t0)}


def _arg(argv, name, cast=str, default=None):
    for a in argv:
        if a.startswith(name):
            return cast(a.split("=", 1)[1])
    return default


# ── تکه‌ها: سه تایم‌فریم موازی، ولی یک نویسنده ─────────────────────────
#
# سریِ ۵دِ دو ساله ~۲۱۰ هزار کندل است و کنارِ دو تایمِ دیگر در یک job
# نمی‌گنجد (اندازه‌گیری ۴ سپتامبر: اجرای یک‌جا از سقف ۸۰ دقیقه رد شد).
# راهش موازی‌کردن است — ولی سه job که همه روی `signals/guardian-lab.json`
# بنویسند، همان بی‌نظمی‌ای است که قانون ۰۵ («یک نویسنده برای هر دامنهٔ
# وضعیت») و قانون ضد-merge منع می‌کنند.
#
# پس هر job فقط یک **تکهٔ حمل‌ونقلی** می‌سازد (نه دفتر، نه تابلو) و یک
# job پایانی همه را کنار هم می‌گذارد، یک بار نمره می‌دهد و یک بار
# می‌نویسد. یکتاسازی روی **هویتِ معامله** است نه متنِ خط — همان درسِ
# ۲۴ اوت که CI را با ردیفِ تکراری ساختگی تنگ کرده بود.
def write_shard(path, trades, span):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"trades": trades, "span": span},
                            ensure_ascii=False), encoding="utf-8")
    return p


def trade_key(t):
    return (t.get("sym"), t.get("tf"), t.get("by"), t.get("t"), t.get("i"))


def read_shards(paths):
    trades, per_tf, skipped, elapsed, asked = [], {}, [], 0, None
    seen = set()
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for t in d.get("trades") or []:
            k = trade_key(t)
            if k in seen:
                continue
            seen.add(k)
            trades.append(t)
        sp = d.get("span") or {}
        per_tf.update(sp.get("per_tf") or {})
        skipped += sp.get("skipped") or []
        elapsed = max(elapsed, int(sp.get("elapsed_s") or 0))
        asked = sp.get("asked_years", asked)
    return trades, {"per_tf": per_tf, "skipped": skipped,
                    "asked_years": asked, "elapsed_s": elapsed,
                    "shards": [str(p) for p in paths]}


def _report(res, span, syms, yrs):
    print(f"آزمایشگاه (واقعی) — {res['trades']} معامله روی {len(syms)} نماد، {yrs} سال")
    for tf, s in res["by_tf"].items():
        cov = (span.get("per_tf") or {}).get(tf) or {}
        print(f"  {tf}: n={s['n']} · برد {s['win_pct']}٪ · خالص {s['mean_net']}R "
              f"· CI {s['ci95_net']} · پوشش {cov.get('years_median', '?')} سال "
              f"· {s['verdict']}")
    for sk in span.get("skipped") or []:
        print(f"  ⚠ {sk['sym']} {sk['tf']}: {sk['why']}")
    print(f"  زمان: {span.get('elapsed_s')}s · خواسته {span.get('asked_years')} سال")


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--from-shards" in argv:
        paths = argv[argv.index("--from-shards") + 1:]
        trades, span = read_shards(paths)
        syms = sorted({t.get("sym") for t in trades if t.get("sym")})
        res = score(trades)
        append_trades(trades)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(snapshot(res, syms, span), ensure_ascii=False,
                                  indent=1) + "\n", encoding="utf-8")
        _report(res, span, syms, span.get("asked_years"))
        return 0
    if "--real" in argv:
        syms = [a for a in argv if a.endswith("USDT")] or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        yrs = 2.0
        for a in argv:
            if a.startswith("--years="):
                yrs = float(a.split("=", 1)[1])
        budget = _arg(argv, "--budget-min=", float)
        budget = budget * 60 if budget is not None else None
        tf_only = _arg(argv, "--tf=")
        tfs = [tf_only] if tf_only else None
        shard = _arg(argv, "--shard-out=")
        trades, span = run_real(syms, yrs, step=1, budget_s=budget, tfs=tfs)
        if shard:
            # تکه فقط حمل‌ونقل است: نه دفتر می‌نویسد نه تابلو. نوشتنِ
            # وضعیت کارِ job پایانی است (قانون ۰۵).
            p = write_shard(shard, trades, span)
            print(f"تکه نوشته شد: {p} — {len(trades)} معامله")
            _report(score(trades), span, syms, yrs)
            return 0
        res = score(trades)
        append_trades(trades)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(snapshot(res, syms, span), ensure_ascii=False,
                                  indent=1) + "\n", encoding="utf-8")
        _report(res, span, syms, yrs)
        return 0
    base = _demo_series(n=3600)
    series = {"5m": base, "15m": resample(base, 3), "1h": resample(base, 12)}
    trades = []
    for tf in TFS:
        trades += run_tf("DEMOUSDT", tf, series[tf], step=3)
    res = score(trades)
    snap = snapshot(res, ["DEMOUSDT"], "سری نمایشی")
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"تابلوی آزمایشگاه نوشته شد: {OUT.relative_to(ROOT)}")
    print(f"آزمایشگاه مراقبان — {res['trades']} معاملهٔ آزمایشی")
    for tf, s in res["by_tf"].items():
        print(f"  {tf}: n={s['n']} · برد {s['win_pct']}٪ · خالص {s['mean_net']}R "
              f"· CI {s['ci95_net']} · {s['verdict']}")
    top = sorted(res["by_guardian"].items(), key=lambda x: -(x[1]["points"] or 0))
    for gid, g in top[:6]:
        name = PHX.BY_ID[gid]["name"]
        print(f"  {name}: {g['points']:+d} امتیاز از {g['votes']} رأی "
              f"(دقت {g['accuracy']}٪) · {g['proposed']} پیشنهاد")
    for gid, why in SILENT.items():
        print(f"  {PHX.BY_ID[gid]['name']}: ممتنع — {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
