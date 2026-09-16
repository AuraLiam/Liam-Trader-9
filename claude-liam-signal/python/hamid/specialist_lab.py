#!/usr/bin/env python3
"""میز مستقل ۱۲ متخصص — هر کدام با استراتژی نام‌دار خودش (دستور حمید، ۱۶ سپتامبر شب).

═══════════════════════════════════════════════════════════════════════
  دستور، و عیبی که این فایل برای رفعش ساخته شد
═══════════════════════════════════════════════════════════════════════

حمید: «هر متخصص با توجه به استراتژی خودش روی ۲۰۰ ارز ۱۰۰۰ ترید در
پیپرمود انجام می‌دهد و اجازهٔ تغییر و آپدیت استراتژی با استفاده از خلاقیت
خودش را دارد… هر ارز ۵ ترید… فقط در تایم‌فریم ۱۵ دقیقه… می‌تواند در گذشتهٔ
ارزها بدون اطلاع از آیندهٔ ارز ترید کند… اسم متخصصین و نوع استراتژی و اسم
استراتژی هر کدام را جلوی اسمشان بنویس.»

**عیبِ ریشه‌ای که قبل از این کار پیدا شد**: میز قبلی (`guardian_desk`) به
هر ۱۲ مراقب **یک جهانِ ستاپِ مشترک** می‌داد و آن‌ها فقط رأی می‌دادند که
واردش شوند یا نه. نتیجه‌اش روی دادهٔ واقعی (اجرای ۱۲ سپتامبر) این شد:

  · ثور، حمل، میزان، سنبله → **دقیقاً یک عدد**: n=۳۰۵۳، خالص +۰.۰۱۰۸R،
    برد ۵۹.۱٪. یعنی هیچ‌کدام چیزی غربال نمی‌کردند.
  · عقرب، جوزا، جدی، قوس، دلو → **n=۰** از ۱۲٬۷۸۴ ستاپ (۱۰۰٪ امتناع).

پس «استراتژی متخصص» وجود نداشت؛ فقط یک فیلتر روی ستاپِ کسِ دیگر بود.
این‌جا هر متخصص **ستاپ خودش را کشف می‌کند**: ورود، استاپ و تارگتش را از
منطقِ تخصصِ خودش می‌سازد. دوازده استراتژیِ واقعاً متفاوت، نه دوازده فیلتر.

═══════════════════════════════════════════════════════════════════════
  قواعد سختِ آزمایش (نقض هر کدام = نتیجهٔ بی‌اعتبار)
═══════════════════════════════════════════════════════════════════════

۱. **بدون نگاه به آینده.** هر تصمیم فقط از `c15[:i+1]` ساخته می‌شود و
   نتیجه از کندل i+1 به بعد خوانده می‌شود (`trainer.resolve`). همان
   موتوری که میز تمرین یک ماه است با آن می‌سنجد.
۲. **فقط ۱۵ دقیقه** (دستور صریح). `tf="15m"` در همه‌جا ثابت است.
۳. **۵ ترید بر ارز، ۲۰۰ ارز، ۱۰۰۰ ترید بر متخصص** — سقفِ هر ارز در خودِ
   حلقه است تا یک ارزِ پرنوسان نمونه را نبلعد.
۴. **کندل واقعی** از همان `sources.klines` تولید؛ هیچ سری‌ای ساخته
   نمی‌شود.
۵. **خالص از کارمزد** با همان `hamid/fees.py`ِ تولید. هیچ عددی ناخالص
   گزارش نمی‌شود بی‌آنکه خالصش کنارش باشد.
۶. **ارزِ بلاک‌شده** (TRX، دستور ۱۶ سپتامبر) در جهان نیست.
۷. دفترها `stage="sp-<id>"` دارند و در `paper._NOT_SIGNAL` می‌نشینند —
   ترازوی سیگنالِ ارسالی آلوده نمی‌شود.

═══════════════════════════════════════════════════════════════════════
  «خلاقیت» چطور کدنویسی شد — و چرا این‌طور
═══════════════════════════════════════════════════════════════════════

حمید خواست متخصص «مثل یک تریدر بنشیند چارت و اطلاعات را ببیند و تغییرات
را ایجاد کند و باز ترید کند». ترجمهٔ صادقانه‌اش با قانون ۰۶ (هیچ LLMی روی
کندل) این است:

هر متخصص یک **فضای ایدهٔ خودش** دارد (`ideas`): چند تغییرِ مشخص در قاعدهٔ
خودش که فقط برای تخصص او معنا دارند — مثلاً «اردر بلاک باید ≥۲ بار واکنش
گرفته باشد» برای اسد، یا «فقط سوییپی که در ۳ کندل پس گرفته شود» برای
سرطان. چرخهٔ بهبود:

    اجرای پایه (نیمهٔ اولِ تاریخ)  →  هر ایده روی همان نیمه سنجیده می‌شود
    →  بهترین ایده انتخاب می‌شود  →  **روی نیمهٔ دومِ دیده‌نشده آزموده
    می‌شود**  →  فقط اگر آن‌جا هم بهتر بود، پذیرفته می‌شود

نیمهٔ دوم خارج-از-نمونه است. بی‌آن، هر ایده‌ای که روی همان داده انتخاب
شود «بهتر» به نظر می‌رسد — این دقیقاً همان data-snooping است که قانون ۰۳
منعش کرده. پذیرش نهایی هم شرط دارد: اختلاف خالص باید مثبت بماند و CI
شیداک‌شدهٔ اختلاف نباید کاملاً زیر صفر باشد.

**متخصص واقعاً می‌خواهد نتیجهٔ بهتر بگیرد**: تابع هدفش خالصِ R است، نه
تعداد معامله و نه نرخ برد. ایده‌ای که تعداد را زیاد کند ولی خالص را پایین
بیاورد، رد می‌شود — همان چیزی که میز ۱ دقیقه را زمین زد.

اجرا:  python3 -m hamid.specialist_lab --symbols 200 --per-symbol 5 [--only leo]
       python3 -m hamid.specialist_lab --report        (فقط گزارش از فایل)
       python3 -m hamid.specialist_lab --selftest
"""
import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "specialist-lab.json"
LEDGER = ROOT / "brain" / "specialists"

TF = "15m"
PER_SYMBOL = 5
TARGET_TRADES = 1000
WARMUP = 160
MAX_HOLD = 96                  # ۲۴ ساعت روی ۱۵ دقیقه
FEE_FALLBACK = 0.15            # ٪ رفت‌وبرگشت، اگر fees جواب نداد


# ══════════════════════════════════════════════════════════════════════
#  دوازده متخصص: نام · نوع استراتژی · نام استراتژی · قاعده · فضای ایده
# ══════════════════════════════════════════════════════════════════════
#
# هر ردیف یک استراتژیِ کامل است: `entry` از پنجرهٔ کندل تا همین لحظه یک
# ستاپ می‌سازد یا None. `params` مقدارهای پایه، `ideas` تغییرهایی که خودِ
# متخصص می‌تواند امتحان کند.

SPECIALISTS = [
    {"id": "scorpio", "sign": "♏", "fa": "عقرب", "en": "Scorpio",
     "family": "بستر و رژیم (Regime)", "strategy_fa": "جزر و مد تتر",
     "strategy_en": "USDT Tide",
     "idea": "وقتی کل بازار یک‌صدا حرکت می‌کند، ضعیف‌ترین ضدجریان می‌شکند: "
             "در کندل‌های پرفشار هم‌جهت پشت‌سرهم وارد ادامه شو.",
     "params": {"press_bars": 3, "press_atr": 0.8, "rr": 2.0, "stop_atr": 1.2},
     "ideas": [{"press_bars": 4}, {"press_atr": 1.1}, {"rr": 3.0}, {"stop_atr": 1.8}]},

    {"id": "gemini", "sign": "♊", "fa": "جوزا", "en": "Gemini",
     "family": "همبستگی و لید-لگ (Lead-Lag)", "strategy_fa": "دنباله‌روِ پیشرو",
     "strategy_en": "Lagging Follower",
     "idea": "نماد بعد از یک شکافِ حرکتی نسبت به میانگین خودش، فاصله را "
             "جبران می‌کند: بازگشت به میانگین بعد از کشش بیش از حد.",
     "params": {"stretch_atr": 2.2, "ema": 34, "rr": 2.0, "stop_atr": 1.3},
     "ideas": [{"stretch_atr": 3.0}, {"ema": 55}, {"rr": 1.5}, {"stop_atr": 1.8}]},

    {"id": "taurus", "sign": "♉", "fa": "ثور", "en": "Taurus",
     "family": "دنبال‌کنندهٔ روند (Trend Following)", "strategy_fa": "گاوِ روند",
     "strategy_en": "Trend Bull",
     "idea": "دو میانگین هم‌جهت + کندلِ بسته بالای هر دو = ادامهٔ روند؛ "
             "استاپ زیر میانگین کند.",
     "params": {"fast": 21, "slow": 55, "rr": 2.5, "stop_atr": 1.5},
     "ideas": [{"fast": 13}, {"slow": 89}, {"rr": 3.5}, {"stop_atr": 2.2}]},

    {"id": "aries", "sign": "♈", "fa": "حمل", "en": "Aries",
     "family": "شکست و ایمپالس (Breakout)", "strategy_fa": "قوچِ شکست",
     "strategy_en": "Ram Breakout",
     "idea": "شکستِ سقف/کف N کندل با بدنهٔ قاطع = ایمپالس؛ ورود روی همان "
             "شکست، نه روی پولبک.",
     "params": {"lookback": 20, "body_frac": 0.6, "rr": 2.0, "stop_atr": 1.4},
     "ideas": [{"lookback": 40}, {"body_frac": 0.75}, {"rr": 3.0}, {"stop_atr": 2.0}]},

    {"id": "leo", "sign": "♌", "fa": "اسد", "en": "Leo",
     "family": "اسمارت مانی (SMC / Order Block)", "strategy_fa": "اردر بلاکِ حمید",
     "strategy_en": "Hamid Order Block",
     "idea": "تعریف خودِ حمید: اولین کندلِ رنگ مخالف که بدنه‌اش از مجموع کل "
             "شدوهایش بزرگ‌تر است، پس از جهش؛ معتبر وقتی گذشته واکنش نشان "
             "داده باشد. ورود روی بازگشت به زون.",
     "params": {"disp_atr": 1.8, "min_reactions": 1, "rr": 2.0, "stop_atr": 1.0},
     "ideas": [{"min_reactions": 2}, {"disp_atr": 2.5}, {"rr": 3.0}, {"stop_atr": 1.5}]},

    {"id": "cancer", "sign": "♋", "fa": "سرطان", "en": "Cancer",
     "family": "نقدینگی و سوییپ (Liquidity)", "strategy_fa": "شکارِ استاپ",
     "strategy_en": "Stop Hunt",
     "idea": "ویکی که کفِ/سقفِ N کندل را می‌زند و همان کندل پس می‌گیرد = "
             "استاپ‌ها جمع شدند؛ ورود در جهت بازگشت.",
     "params": {"lookback": 20, "wick_frac": 0.5, "reclaim_bars": 1,
                "rr": 2.0, "stop_atr": 1.2},
     "ideas": [{"wick_frac": 0.65}, {"lookback": 40}, {"reclaim_bars": 3}, {"rr": 3.0}]},

    {"id": "pisces", "sign": "♓", "fa": "حوت", "en": "Pisces",
     "family": "هندسهٔ کندل (Candlestick)", "strategy_fa": "ماهیِ بلعنده",
     "strategy_en": "Engulfing Fish",
     "idea": "الگوی برگشتیِ داخلِ دامنه (بلعنده یا پین‌بار با ویکِ ردکننده) در سمتِ درستِ میانگین — نه شکست، که میدانِ حمل است.",
     "params": {"ibs_edge": 0.35, "ema": 21, "wick_mult": 1.5, "rr": 2.0, "stop_atr": 1.2},
     "ideas": [{"ibs_edge": 0.25}, {"ema": 34}, {"rr": 3.0}, {"wick_mult": 2.2}]},

    {"id": "libra", "sign": "♎", "fa": "میزان", "en": "Libra",
     "family": "هندسهٔ ریسک (Risk Geometry)", "strategy_fa": "ترازوی کارمزد",
     "strategy_en": "Fee Scale",
     "idea": "فقط ستاپی که استاپش به‌قدر کافی گشاد است تا سهم کارمزد از R "
             "کوچک بماند؛ لبه از هندسه می‌آید نه از پیش‌بینی.",
     "params": {"min_stop_pct": 1.0, "ema": 34, "touch_atr": 0.6, "rr": 2.5, "stop_atr": 2.0},
     "ideas": [{"min_stop_pct": 1.5}, {"rr": 3.5}, {"stop_atr": 2.8}, {"touch_atr": 1.0}]},

    {"id": "capricorn", "sign": "♑", "fa": "جدی", "en": "Capricorn",
     "family": "بازگشت به میانگین (Mean Reversion)", "strategy_fa": "بزِ صبور",
     "strategy_en": "Patient Goat",
     "idea": "کشش بیش از حد از میانگین بلند + کندلِ برگشتی = بازگشت؛ "
             "صبر تا لبهٔ آماری، نه تا احساس.",
     "params": {"ema": 89, "stretch_atr": 2.5, "rr": 1.8, "stop_atr": 1.5},
     "ideas": [{"stretch_atr": 3.2}, {"ema": 144}, {"rr": 2.5}, {"stop_atr": 2.2}]},

    {"id": "virgo", "sign": "♍", "fa": "سنبله", "en": "Virgo",
     "family": "نوسان و فشردگی (Volatility)", "strategy_fa": "فشردگیِ سنبله",
     "strategy_en": "Virgo Squeeze",
     "idea": "دامنهٔ فشرده‌شده نسبت به ATR بلند = انبساط در راه؛ ورود روی "
             "اولین شکستِ همان فشردگی.",
     "params": {"squeeze_bars": 12, "squeeze_ratio": 0.6, "rr": 2.5, "stop_atr": 1.3},
     "ideas": [{"squeeze_ratio": 0.45}, {"squeeze_bars": 20}, {"rr": 3.5}, {"stop_atr": 1.8}]},

    {"id": "sagittarius", "sign": "♐", "fa": "قوس", "en": "Sagittarius",
     "family": "شتاب و مومنتوم (Momentum)", "strategy_fa": "کمانِ شتاب",
     "strategy_en": "Momentum Bow",
     "idea": "نرخِ تغییرِ N کندل در صدکِ بالا + حجمِ بالاتر از میانه = "
             "شتابِ واقعی، نه نوسانِ تصادفی.",
     "params": {"roc_bars": 10, "roc_min_pct": 1.5, "vol_mult": 1.3,
                "rr": 2.5, "stop_atr": 1.5},
     "ideas": [{"roc_min_pct": 2.5}, {"vol_mult": 1.8}, {"roc_bars": 20}, {"rr": 3.5}]},

    {"id": "aquarius", "sign": "♒", "fa": "دلو", "en": "Aquarius",
     "family": "ضدجمعیت (Contrarian)", "strategy_fa": "دلوِ خلافِ جمع",
     "strategy_en": "Contrarian Jar",
     "idea": "سه کندلِ پشت‌سرهمِ هم‌جهت با حجمِ رو به کاهش = خستگیِ جمعیت؛ "
             "ورود خلافِ همان حرکت.",
     "params": {"run_bars": 3, "vol_fade": 0.9, "rr": 1.8, "stop_atr": 1.3},
     "ideas": [{"run_bars": 4}, {"vol_fade": 0.75}, {"rr": 2.5}, {"stop_atr": 1.9}]},
]
BY_ID = {s["id"]: s for s in SPECIALISTS}


# ══════════════════════════════════════════════════════════════════════
#  ابزار کندل — همه از پنجرهٔ بسته، هیچ‌کدام از آینده
# ══════════════════════════════════════════════════════════════════════
def _ema(vals, n):
    if len(vals) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(vals[:n]) / n
    for v in vals[n:]:
        e = v * k + e * (1 - k)
    return e


def _atr(cd, n=14):
    if len(cd) < n + 1:
        return None
    tr = []
    for i in range(len(cd) - n, len(cd)):
        h, l, pc = cd[i]["h"], cd[i]["l"], cd[i - 1]["c"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(tr) / len(tr) if tr else None


def _body(c):
    return abs(c["c"] - c["o"])


def _shadows(c):
    return (c["h"] - max(c["o"], c["c"])) + (min(c["o"], c["c"]) - c["l"])


def _ibs(c):
    rng = c["h"] - c["l"]
    return (c["c"] - c["l"]) / rng if rng > 0 else 0.5


def _mk(direction, entry, stop_dist, rr):
    """ستاپ استاندارد: ورود، استاپ، تارگت — RR ثابتِ خودِ متخصص."""
    if stop_dist <= 0 or entry <= 0:
        return None
    if direction == "LONG":
        return {"dir": "LONG", "entry": entry, "sl": entry - stop_dist,
                "tp1": entry + stop_dist * rr}
    return {"dir": "SHORT", "entry": entry, "sl": entry + stop_dist,
            "tp1": entry - stop_dist * rr}


# ══════════════════════════════════════════════════════════════════════
#  دوازده قاعدهٔ ورود — هر کدام فقط میدانِ تخصصِ خودش را می‌خواند
# ══════════════════════════════════════════════════════════════════════
def e_scorpio(cd, p):
    n = int(p["press_bars"])
    if len(cd) < n + 20:
        return None
    a = _atr(cd)
    if not a:
        return None
    last = cd[-n:]
    up = all(k["c"] > k["o"] for k in last)
    dn = all(k["c"] < k["o"] for k in last)
    if not (up or dn):
        return None
    if sum(_body(k) for k in last) < p["press_atr"] * a * n:
        return None
    return _mk("LONG" if up else "SHORT", cd[-1]["c"], a * p["stop_atr"], p["rr"])


def e_gemini(cd, p):
    n = int(p["ema"])
    if len(cd) < n + 20:
        return None
    a = _atr(cd)
    e = _ema([k["c"] for k in cd], n)
    if not a or not e:
        return None
    px = cd[-1]["c"]
    gap = (px - e) / a
    if gap >= p["stretch_atr"]:
        return _mk("SHORT", px, a * p["stop_atr"], p["rr"])
    if gap <= -p["stretch_atr"]:
        return _mk("LONG", px, a * p["stop_atr"], p["rr"])
    return None


def e_taurus(cd, p):
    f, s = int(p["fast"]), int(p["slow"])
    if len(cd) < s + 20:
        return None
    cl = [k["c"] for k in cd]
    a, ef, es = _atr(cd), _ema(cl, f), _ema(cl, s)
    if not (a and ef and es):
        return None
    px = cd[-1]["c"]
    if ef > es and px > ef:
        return _mk("LONG", px, a * p["stop_atr"], p["rr"])
    if ef < es and px < ef:
        return _mk("SHORT", px, a * p["stop_atr"], p["rr"])
    return None


def e_aries(cd, p):
    n = int(p["lookback"])
    if len(cd) < n + 20:
        return None
    a = _atr(cd)
    if not a:
        return None
    c = cd[-1]
    rng = c["h"] - c["l"]
    if rng <= 0 or _body(c) / rng < p["body_frac"]:
        return None
    prev = cd[-n - 1:-1]
    hi, lo = max(k["h"] for k in prev), min(k["l"] for k in prev)
    if c["c"] > hi and c["c"] > c["o"]:
        return _mk("LONG", c["c"], a * p["stop_atr"], p["rr"])
    if c["c"] < lo and c["c"] < c["o"]:
        return _mk("SHORT", c["c"], a * p["stop_atr"], p["rr"])
    return None


def e_leo(cd, p):
    """اردر بلاک، دقیقاً به تعریف حمید — بدنه > مجموع شدوها + واکنشِ گذشته."""
    if len(cd) < 60:
        return None
    a = _atr(cd)
    if not a:
        return None
    px = cd[-1]["c"]
    win = cd[-120:] if len(cd) >= 120 else cd
    best = None
    for i in range(3, len(win) - 1):
        body = win[i]["c"] - win[i]["o"]
        for role in ("demand", "supply"):
            if role == "demand" and body <= p["disp_atr"] * a:
                continue
            if role == "supply" and -body <= p["disp_atr"] * a:
                continue
            j = i - 1
            if role == "demand" and win[j]["c"] >= win[j]["o"]:
                continue
            if role == "supply" and win[j]["c"] <= win[j]["o"]:
                continue
            if _body(win[j]) <= _shadows(win[j]):        # قاعدهٔ حمید
                continue
            lo = min(win[j]["o"], win[j]["c"])
            hi = max(win[j]["o"], win[j]["c"])
            if hi <= lo:
                continue
            mitigated, reactions = False, 0
            for k in win[i + 1:]:
                if role == "demand" and k["c"] < lo:
                    mitigated = True
                elif role == "supply" and k["c"] > hi:
                    mitigated = True
                elif lo <= k["h"] and k["l"] <= hi:
                    reactions += 1
            if mitigated or reactions < p["min_reactions"]:
                continue
            dist = abs(px - (hi if role == "demand" else lo)) / px
            if dist < 0.004 and (best is None or dist < best[0]):
                best = (dist, role, lo, hi)
    if not best:
        return None
    _, role, lo, hi = best
    if role == "demand":
        return _mk("LONG", px, max(px - lo, a * p["stop_atr"] * 0.5), p["rr"])
    return _mk("SHORT", px, max(hi - px, a * p["stop_atr"] * 0.5), p["rr"])


def e_cancer(cd, p):
    n = int(p["lookback"])
    rb = int(p["reclaim_bars"])
    if len(cd) < n + 20:
        return None
    a = _atr(cd)
    if not a:
        return None
    c = cd[-1]
    rng = c["h"] - c["l"]
    if rng <= 0:
        return None
    prev = cd[-n - 1:-1]
    hi, lo = max(k["h"] for k in prev), min(k["l"] for k in prev)
    low_wick = (min(c["o"], c["c"]) - c["l"]) / rng
    up_wick = (c["h"] - max(c["o"], c["c"])) / rng
    if c["l"] < lo and c["c"] > lo and low_wick >= p["wick_frac"]:
        if all(cd[-1 - k]["c"] > lo for k in range(min(rb, len(cd) - 1))):
            return _mk("LONG", c["c"], a * p["stop_atr"], p["rr"])
    if c["h"] > hi and c["c"] < hi and up_wick >= p["wick_frac"]:
        if all(cd[-1 - k]["c"] < hi for k in range(min(rb, len(cd) - 1))):
            return _mk("SHORT", c["c"], a * p["stop_atr"], p["rr"])
    return None


def e_pisces(cd, p):
    """هندسهٔ کندلِ برگشتی **داخل دامنه** — نه شکست.

    دو اصلاح که آزمون تحمیل کرد: نسخهٔ اول فقط «بلعنده» بود و کور ماند؛
    نسخهٔ دوم بدنهٔ قاطع را گرفت و ۹۰٪ با حملِ شکست هم‌پوشان شد. مرزِ
    تخصص باید در خودِ قاعده باشد: کندلی که سقف/کف دامنه را می‌شکند
    میدانِ حمل است؛ حوت الگوی برگشتیِ **داخل** دامنه را می‌خواند —
    بلعنده یا پین‌بار با ویکِ ردکننده. الگو تأیید است نه ماشهٔ مستقل
    (قانون ۰۹)، پس سمتِ میانگین هم شرط است.
    """
    n = int(p["ema"])
    if len(cd) < n + 30:
        return None
    a, e = _atr(cd), _ema([k["c"] for k in cd], n)
    if not (a and e):
        return None
    c, q = cd[-1], cd[-2]
    rng = c["h"] - c["l"]
    body = _body(c)
    if rng <= 0 or body <= 0:
        return None
    prev = cd[-21:-1]
    hi, lo = max(k["h"] for k in prev), min(k["l"] for k in prev)
    if c["c"] > hi or c["c"] < lo:
        return None                                  # شکست، میدانِ حمل است
    up_wick = c["h"] - max(c["o"], c["c"])
    dn_wick = min(c["o"], c["c"]) - c["l"]
    bull_eng = c["c"] > c["o"] and q["c"] < q["o"] and c["c"] > q["o"] and c["o"] < q["c"]
    bear_eng = c["c"] < c["o"] and q["c"] > q["o"] and c["c"] < q["o"] and c["o"] > q["c"]
    pin_bull = dn_wick >= p["wick_mult"] * body and c["c"] > c["o"]
    pin_bear = up_wick >= p["wick_mult"] * body and c["c"] < c["o"]
    ibs = _ibs(c)
    if c["c"] > e and (bull_eng or pin_bull) and ibs >= 1 - p["ibs_edge"]:
        return _mk("LONG", c["c"], a * p["stop_atr"], p["rr"])
    if c["c"] < e and (bear_eng or pin_bear) and ibs <= p["ibs_edge"]:
        return _mk("SHORT", c["c"], a * p["stop_atr"], p["rr"])
    return None


def e_libra(cd, p):
    """هندسهٔ ریسک: فقط ستاپی که کارمزد سهم کوچکی از R بگیرد.

    نسخهٔ اول «هر کندلی که بالای میانگین بسته شود» را می‌گرفت و عملاً
    همیشه در بازار بود — آزمونِ هم‌پوشانی نشان داد ورودهایش ابرمجموعهٔ
    سه متخصص دیگر است. ترازو باید **انتخاب‌گر** باشد نه همیشه‌حاضر: حالا
    علاوه بر کفِ استاپ، پولبک به میانگین و بازگشت از آن لازم است — یعنی
    ورود در جایی که فاصله تا استاپ منطقی است، نه وسط حرکت.
    """
    n = int(p["ema"])
    if len(cd) < n + 20:
        return None
    a, e = _atr(cd), _ema([k["c"] for k in cd], n)
    if not (a and e):
        return None
    c, q = cd[-1], cd[-2]
    px = c["c"]
    stop = a * p["stop_atr"]
    if stop / px * 100 < p["min_stop_pct"]:          # کارمزد سهمش بزرگ می‌شود
        return None
    near = abs(q["l"] - e) <= a * p["touch_atr"] or abs(q["h"] - e) <= a * p["touch_atr"]
    if not near:
        return None                                  # پولبکی به میانگین نبوده
    if px > e and c["c"] > c["o"] and c["c"] > q["h"]:
        return _mk("LONG", px, stop, p["rr"])
    if px < e and c["c"] < c["o"] and c["c"] < q["l"]:
        return _mk("SHORT", px, stop, p["rr"])
    return None


def e_capricorn(cd, p):
    n = int(p["ema"])
    if len(cd) < n + 20:
        return None
    a, e = _atr(cd), _ema([k["c"] for k in cd], n)
    if not (a and e):
        return None
    c = cd[-1]
    gap = (c["c"] - e) / a
    if gap <= -p["stretch_atr"] and c["c"] > c["o"]:
        return _mk("LONG", c["c"], a * p["stop_atr"], p["rr"])
    if gap >= p["stretch_atr"] and c["c"] < c["o"]:
        return _mk("SHORT", c["c"], a * p["stop_atr"], p["rr"])
    return None


def e_virgo(cd, p):
    n = int(p["squeeze_bars"])
    if len(cd) < n + 40:
        return None
    a = _atr(cd)
    if not a:
        return None
    win = cd[-n - 1:-1]
    rng = max(k["h"] for k in win) - min(k["l"] for k in win)
    if rng > p["squeeze_ratio"] * a * n ** 0.5:
        return None
    c = cd[-1]
    hi, lo = max(k["h"] for k in win), min(k["l"] for k in win)
    if c["c"] > hi:
        return _mk("LONG", c["c"], a * p["stop_atr"], p["rr"])
    if c["c"] < lo:
        return _mk("SHORT", c["c"], a * p["stop_atr"], p["rr"])
    return None


def e_sagittarius(cd, p):
    n = int(p["roc_bars"])
    if len(cd) < n + 60:
        return None
    a = _atr(cd)
    if not a:
        return None
    c = cd[-1]
    base = cd[-n - 1]["c"]
    if base <= 0:
        return None
    roc = (c["c"] / base - 1) * 100
    vols = [k.get("v") or 0 for k in cd[-50:]]
    med = statistics.median(vols) if vols else 0
    if med <= 0 or (c.get("v") or 0) < p["vol_mult"] * med:
        return None
    if roc >= p["roc_min_pct"]:
        return _mk("LONG", c["c"], a * p["stop_atr"], p["rr"])
    if roc <= -p["roc_min_pct"]:
        return _mk("SHORT", c["c"], a * p["stop_atr"], p["rr"])
    return None


def e_aquarius(cd, p):
    n = int(p["run_bars"])
    if len(cd) < n + 30:
        return None
    a = _atr(cd)
    if not a:
        return None
    last = cd[-n:]
    up = all(k["c"] > k["o"] for k in last)
    dn = all(k["c"] < k["o"] for k in last)
    if not (up or dn):
        return None
    vs = [k.get("v") or 0 for k in last]
    if len(vs) < 2 or vs[0] <= 0 or vs[-1] > p["vol_fade"] * vs[0]:
        return None                                   # حجم نریخته = خستگی نیست
    return _mk("SHORT" if up else "LONG", cd[-1]["c"], a * p["stop_atr"], p["rr"])


ENTRY = {"scorpio": e_scorpio, "gemini": e_gemini, "taurus": e_taurus,
         "aries": e_aries, "leo": e_leo, "cancer": e_cancer, "pisces": e_pisces,
         "libra": e_libra, "capricorn": e_capricorn, "virgo": e_virgo,
         "sagittarius": e_sagittarius, "aquarius": e_aquarius}


# ══════════════════════════════════════════════════════════════════════
#  بازپخش — بدون نگاه به آینده
# ══════════════════════════════════════════════════════════════════════
def _fee_r(sym, entry, sl):
    try:
        from hamid import fees
        v = fees.cost_in_r(entry, sl, sym)
        if v is not None:
            return v
    except Exception:                                # noqa: BLE001
        pass
    stop_pct = abs(entry - sl) / entry * 100 if entry else 0
    return FEE_FALLBACK / stop_pct if stop_pct > 0 else None


def replay(sym, cd, spec, params, lo=0, hi=None, cap=PER_SYMBOL):
    """ستاپ‌های همین متخصص روی همین ارز؛ فقط پنجرهٔ [lo, hi) از تاریخ.

    هر تصمیم از `cd[:i+1]` ساخته می‌شود و نتیجه از i+1 به بعد خوانده
    می‌شود — هیچ کندلی از آینده به تصمیم نمی‌رسد."""
    from hamid.trainer import resolve
    fn = ENTRY[spec["id"]]
    hi = len(cd) if hi is None else hi
    out = []
    i = max(lo, WARMUP)
    while i < hi - 2 and len(out) < cap:
        try:
            s = fn(cd[:i + 1], params)
        except Exception:                            # noqa: BLE001 - یک ستاپ خراب، کل اجرا را نمی‌کشد
            s = None
        if not s:
            i += 1
            continue
        stop_pct = abs(s["entry"] - s["sl"]) / s["entry"] * 100
        if not (0.15 <= stop_pct <= 8.0):            # هندسهٔ بی‌معنا وارد نمی‌شود
            i += 1
            continue
        j, outcome, r, exc = resolve(cd, i, s, max_hold=MAX_HOLD)
        if outcome == "timeout" and j >= len(cd) - 1 and (j - i) < MAX_HOLD:
            break                                    # به تهِ داده خورد — نتیجه معلوم نیست
        fee = _fee_r(sym, s["entry"], s["sl"])
        out.append({"sym": sym, "spec": spec["id"], "dir": s["dir"],
                    "entry": s["entry"], "sl": s["sl"], "tp1": s["tp1"],
                    "opened": cd[i]["t"], "closed": cd[j]["t"], "tf": TF,
                    "outcome": outcome, "R": r, "fee_r": None if fee is None else round(fee, 4),
                    "net_r": None if (r is None or fee is None) else round(r - fee, 4),
                    "stop_pct": round(stop_pct, 3), "hold_bars": j - i, **exc})
        i = j + 1
    return out


def summarize(trades):
    nets = [t["net_r"] for t in trades if t.get("net_r") is not None]
    gross = [t["R"] for t in trades if t.get("R") is not None]
    if not nets:
        return {"n": len(trades), "net": None, "ci": [None, None], "verdict": "بی‌حکم — نمونه کم"}
    m = statistics.fmean(nets)
    sd = statistics.pstdev(nets) if len(nets) > 1 else 0.0
    h = 1.96 * sd / math.sqrt(len(nets))
    outs = {}
    for t in trades:
        outs[t["outcome"]] = outs.get(t["outcome"], 0) + 1
    return {"n": len(nets), "net": round(m, 4), "gross": round(statistics.fmean(gross), 4) if gross else None,
            "ci": [round(m - h, 4), round(m + h, 4)],
            "win_pct": round(sum(x > 0 for x in nets) / len(nets) * 100, 1),
            "sd": round(sd, 4), "sum_net": round(sum(nets), 2),
            "median_stop_pct": round(statistics.median(t["stop_pct"] for t in trades), 3),
            "median_fee_r": round(statistics.median(t["fee_r"] for t in trades if t.get("fee_r") is not None), 3)
            if any(t.get("fee_r") is not None for t in trades) else None,
            "outcomes": outs,
            "verdict": ("مثبت با CI بالای صفر" if m - h > 0 else
                        "منفی با CI زیر صفر" if m + h < 0 else "بی‌حکم — CI شامل صفر")}


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=200)
    ap.add_argument("--per-symbol", type=int, default=PER_SYMBOL)
    ap.add_argument("--only", default=None, help="فقط این متخصص")
    ap.add_argument("--improve", action="store_true", help="چرخهٔ بهبود را هم بدو")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(list(argv))
    if a.selftest:
        return selftest()
    from hamid.specialist_run import run_all
    doc = run_all(n_symbols=a.symbols, per_symbol=a.per_symbol,
                  only=a.only, improve=a.improve)
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc.get("summary") or {}, ensure_ascii=False, indent=1))
    return 0


def selftest():
    from hamid.test_specialist_lab import run as t
    return t()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
