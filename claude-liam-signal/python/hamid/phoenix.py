#!/usr/bin/env python3
"""شورای ققنوس — ۱۲ مراقب زودیاک، هر کدام با دستور تخصصی؛ حکم وزنی ققنوس روی هر سیگنال.

دستور حمید (۲ سپتامبر، شب): «۱۲ مراقب ققنوس را نام‌گذاری کن به زودیاک…
دستورات لازم برای استراتژی تخصصی را در اختیارشان قرار بده؛ و بعد مشاهدهٔ
سیگنال و اعلام رأی ققنوس که تو هستی، بر اساس وزن رأی می‌دهی که سیگنال
چگونه باشد.»

## چطور کار می‌کند (قطعی، پایتون — قانون ۰۶: بدون فراخوانی LLM بر سیگنال)

۱. هر سیگنالِ در آستانهٔ ارسال را هر ۱۲ مراقب می‌بینند. هر مراقب فقط
   میدان تخصص خودش را می‌خواند و یک رأی می‌دهد: عددی در [−۱, +۱] (علامت
   = جهت، بزرگی = اطمینان) با دلیلِ یک‌خطی؛ یا **ممتنع** وقتی دادهٔ
   تخصصش نیست (قانون ۱: دادهٔ ناموجود رأی نمی‌سازد).
۲. ققنوس (ایجنت اصلی) رأی‌ها را با **وزن کارنامه‌ای** جمع می‌کند:
   وزن پایهٔ همه ۱؛ لایهٔ خبر/جمعیت (قوس، دلو) پایهٔ ۰.۳ و سقف مشترک ۵٪
   کل رأی (قانون ۱۱/۱۵). وزن فقط با کارنامهٔ خودِ همان مراقب روی دفتر
   بسته جابه‌جا می‌شود: باند ±۰.۱۵ تا وقتی CI از ۵۰٪ رد نکرده، ±۰.۴۰ بعد
   از آن؛ زیر ۱۲ نمونه وزن اصلاً حرکت نمی‌کند (همان منطق agent_scores).
۳. حکم ققنوس: امتیاز در [−۱, +۱] → «تأیید قوی / تأیید / بی‌نظر / مخالف»
   + **پیشنهاد اندازه** (سایز کامل / نصف / فقط پیپر / نرو). با کمتر از
   ۴ رأی‌دهنده حکم «بی‌نظر — شواهد کم» است.

## مرز (قانون ۰۳/۱۲ — تغییرناپذیر بی‌دستور صریح حمید)

حکم ققنوس **روی پیام و روی دفتر می‌نشیند و شبانه سنجیده می‌شود**؛ هیچ
سیگنالی را حذف نمی‌کند و هیچ عددی (ورود/استاپ/تارگت/اهرم) را عوض
نمی‌کند. «سیگنال چگونه باشد» یعنی پیشنهاد اندازه و برچسبِ اعتماد روی
همان سیگنال. ورود حکم به دروازه یا سایز خودکار فقط وقتی که ماشین شبانه
CI بالای صفر بدهد و حمید تأیید کند. هیچ مراقبی وتو ندارد.

## سنجش

هر معاملهٔ بسته با رأی‌های ثبت‌شده: مراقبی که رأی هم‌علامتِ R داده «درست»
است، خلافش «غلط»، ممتنع شمرده نمی‌شود. کارنامه با CI ویلسون در
`brain/phoenix/scores.json`، تابلو در `signals/phoenix.json`، حکم‌ها در
`brain/phoenix/verdicts.jsonl` (append-only).
"""
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

BRAIN = ROOT / "brain" / "phoenix"
SCORES = BRAIN / "scores.json"
VERDICTS = BRAIN / "verdicts.jsonl"
OUT = ROOT / "signals" / "phoenix.json"
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
DOMINANCE = ROOT / "signals" / "dominance.json"
BTC_SENS = ROOT / "signals" / "btc-sensitivity.json"

MIN_N = 12
BAND_EXPLORATORY = 0.15
BAND_CONFIRMED = 0.40
SOCIAL_CAP = 0.05                 # سهم مشترک قوس+دلو از کل وزن (قانون ۱۱/۱۵)
MIN_VOTERS = 4
DOM_MAX_AGE_MIN = 90

# ── ۱۲ مراقب — نام زودیاک، تخصص، دستور ──────────────────────────────────
# ترتیب همان ترتیب تحلیل حمید است: بستر (دامیننس/BTC) → ساختار → مکان →
# نقدینگی → کندل/اجرا → ریسک → حافظه → دیدگاه (خبر/جمعیت) → دادهٔ سالم.
GUARDIANS = [
    {"id": "scorpio", "name": "عقرب", "sign": "♏", "engine": "E03/E04", "base": 1.0,
     "specialty": "دامیننس تتر و بیت‌کوین",
     "order": "USDT.D و BTC.D را در ۴س و بعد ۱س ببین. USDT.D صعودی = بازار نزولی؛ لانگ در آن دلیل خیلی قوی می‌خواهد. "
              "شاهدِ هم‌ترازِ تایم‌فریم (dom_tf) حرف اول را می‌زند؛ دادهٔ کهنه‌تر از ۹۰ دقیقه = ممتنع."},
    {"id": "gemini", "name": "جوزا", "sign": "♊", "engine": "E06/E12", "base": 1.0,
     "specialty": "بستر بیت‌کوین و لید-لگ",
     "order": "بیت‌کوین جهت را تعیین می‌کند؛ نمادِ COUPLED بدون همراهی BTC حق ورود ندارد. برای نمادِ INDEPENDENT "
              "(کلاس حساسیت تاریخی) وزن رأیت را نصف کن. شاهد: دلایل بازجویی دربارهٔ BTC و لگ-کورولیشن."},
    {"id": "taurus", "name": "ثور", "sign": "♉", "engine": "E07", "base": 1.0,
     "specialty": "روند تایم بالا (۴س/۱س)",
     "order": "۴س میدان نبرد است و ۱س ساختار عملیاتی. هر دو هم‌جهت = تأیید قوی؛ یکی خلاف = تأیید ضعیف و برچسب «خلاف روند»؛ "
              "هر دو خلاف = مخالف. تایم پایین حق نقض ساختار بالا را ندارد (قانون ۲)."},
    {"id": "aries", "name": "حمل", "sign": "♈", "engine": "E07/E08", "base": 1.0,
     "specialty": "ایمپالس، BOS و پولبک سالم",
     "order": "توالی IBS+پولبک پلاس: شکست → BOS → پولبک ۱ → BOS دوم → پولبک ۲. ضربهٔ بلاک ≥۶ ایمپالس واقعی است. "
              "CHoCH داخل پولبک برگشت نیست، تله است (قانون ۵) — رأی مخالف. ورود در پولبک اول = رأی مخالف."},
    {"id": "leo", "name": "اسد", "sign": "♌", "engine": "E08", "base": 1.0,
     "specialty": "اردر بلاک و FVG (SMC)",
     "order": "اردر بلاک به تعریف حمید: بعد از ریزش، اولین کندل قویِ مخالف که بدنه‌اش از مجموع شدوها بزرگ‌تر است. "
              "تازه و مصرف‌نشده = تأیید؛ اردر بلاک مخالف جلوی راه یا OB سه بار برگشت‌خورده = مخالف. بدون OB = ممتنع."},
    {"id": "cancer", "name": "سرطان", "sign": "♋", "engine": "E10", "base": 1.0,
     "specialty": "نقدینگی و سوییپ",
     "order": "سقف/کف برابر، استخر استاپ‌ها، سوییپ اخیر. نقدینگیِ جمع‌شده پشت ورود = تأیید؛ آهن‌ربای نقشهٔ نقدینگی "
              "هم‌جهت تارگت = تأیید، خلافش = مخالف. حجم برای حمید مهم‌ترین تأیید است."},
    {"id": "pisces", "name": "حوت", "sign": "♓", "engine": "E09", "base": 1.0,
     "specialty": "کندل و کیفیت ورود ۵د/۱۵د",
     "order": "الگوی کندلی تأیید ثانویه است نه ماشه (قانون ۰۹/۱۰). کندل فقط بعد از بسته‌شدن. کیفیت ≥۷۰ و الگوی "
              "هم‌جهت = تأیید؛ الگوی مخالف = مخالف؛ کیفیت <۵۰ = مخالف ضعیف."},
    {"id": "libra", "name": "میزان", "sign": "♎", "engine": "E16", "base": 1.0,
     "specialty": "ریسک، کارمزد و هندسهٔ RR",
     "order": "RR خالص از کارمزد+لغزش باید از حد بگذرد. کارمزد ≥۰.۲۵R = دام اسکالپ، مخالف. RR ≥۱.۸ و کارمزد ≤۰.۱۵R = تأیید. "
              "استاپ روی نقطهٔ ابطال ساختار باشد، نه عدد دلخواه."},
    {"id": "capricorn", "name": "جدی", "sign": "♑", "engine": "E21", "base": 1.0,
     "specialty": "حافظه و کارنامهٔ تاریخی",
     "order": "کارنامهٔ همین ارز/جهت/تایم را از اتاق یادگیری بخوان. n≥۱۲ با انتظار مثبت = تأیید؛ انتظار <−۰.۳R = مخالف؛ "
              "نمونهٔ کم یا خنثی = ممتنع. یک روز خوب یا بد چیزی را ثابت نمی‌کند."},
    {"id": "virgo", "name": "سنبله", "sign": "♍", "engine": "E02", "base": 1.0,
     "specialty": "کیفیت داده و هم‌زمانی",
     "order": "منبع کندل باید همان بازارِ اجرا (پرپ بیت‌یونیکس) باشد؛ پشتیبان اسپات = تأیید ضعیف. قیمت لحظهٔ ارسال "
              "≤۰.۵٪ از ورود = تأیید؛ >۱.۵٪ = مخالف. کندل کهنه یا سیگنال بی‌هم‌زمانی = مخالف."},
    {"id": "sagittarius", "name": "قوس", "sign": "♐", "engine": "E05/E14", "base": 0.3,
     "specialty": "کلان و خبر (فقط دیدگاه)",
     "order": "خبر دیدگاه است نه تصمیم (قانون ۱۵). اجماع خبری وزن‌دار هم‌جهت = تأیید ضعیف؛ خلاف = مخالف ضعیف؛ "
              "بی‌اجماع = ممتنع. سهم تو با دلو روی هم هرگز از ۵٪ رأی بیشتر نمی‌شود."},
    {"id": "aquarius", "name": "دلو", "sign": "♒", "engine": "E15", "base": 0.3,
     "specialty": "جمعیت و فومو (فقط دیدگاه)",
     "order": "داغی جمعیت و شاهد اپ fomo را بخوان. شاهدِ فومو برای همین نماد = تأیید ضعیف؛ داغی ≥۸۰ در جهتِ جمعیت "
              "(لانگِ داغ) = مخالف ضعیف (خطر تلهٔ شلوغی). سقف مشترک با قوس ۵٪."},
]
CAPPED = ("sagittarius", "aquarius")
BY_ID = {g["id"]: g for g in GUARDIANS}


# ── رأی هر مراقب: (v ∈ [−۱,+۱] یا None=ممتنع، دلیل) ─────────────────────
def _sign(direction):
    return 1 if str(direction).upper() == "LONG" else -1


def _v_scorpio(s, ctx):
    pm = s.get("premortem") or {}
    dt = pm.get("dom_tf") or {}
    if dt.get("aligned") is True:
        return 0.8, f"دامیننس هم‌تراز {dt.get('tf_used') or ''} هم‌جهت ({dt.get('regime') or '—'})"
    if dt.get("aligned") is False:
        return -0.8, f"دامیننس هم‌تراز {dt.get('tf_used') or ''} خلاف ({dt.get('regime') or '—'})"
    dom = ctx.get("dominance") or {}
    gen = dom.get("generated") or 0
    if not gen or (ctx.get("now_ms", time.time() * 1000) - gen) > DOM_MAX_AGE_MIN * 60_000:
        return None, "دامیننس تازه در دسترس نیست"
    c1 = ((dom.get("chg_1h") or {}).get("usdt"))
    c4 = ((dom.get("chg_4h") or {}).get("usdt"))
    if c1 is None or c4 is None:
        return None, "تغییر USDT.D ثبت نشده"
    d = _sign(s.get("dir"))
    # USDT.D بالا = بازار پایین. لانگ با USDT.D نزولی موافق است.
    score = -(c1 + c4) * d
    if abs(c1) < 0.01 and abs(c4) < 0.02:
        return 0.0, "USDT.D خنثی"
    v = max(-1.0, min(1.0, score * 20))
    return v, f"USDT.D ۱س {c1:+.3f} · ۴س {c4:+.3f} → {'هم‌جهت' if v > 0 else 'خلاف'}"


def _v_gemini(s, ctx):
    pm = s.get("premortem") or {}
    hits = [t for t in (pm.get("pro") or []) if "BTC" in t or "بیت" in t]
    cons = [t for t in (pm.get("con") or []) if "BTC" in t or "بیت" in t]
    cls = ((ctx.get("btc_sens") or {}).get(s.get("sym")) or {}).get("class")
    damp = 0.5 if cls == "INDEPENDENT" else 1.0
    if hits and not cons:
        return 0.7 * damp, f"بستر BTC هم‌جهت: {hits[0][:60]}" + (" (نماد مستقل: نصف)" if damp < 1 else "")
    if cons and not hits:
        return -0.7 * damp, f"بستر BTC خلاف: {cons[0][:60]}" + (" (نماد مستقل: نصف)" if damp < 1 else "")
    if hits and cons:
        return 0.0, "شواهد BTC دو طرفه"
    return None, "شاهد BTC در بازجویی نبود"


def _v_taurus(s, ctx):
    d = "up" if _sign(s.get("dir")) > 0 else "down"
    t4, t1 = s.get("trend4"), s.get("trend1")
    if t4 is None and t1 is None:
        return None, "روند ۴س/۱س ثبت نشده"
    a4, a1 = (t4 == d), (t1 == d)
    if a4 and a1:
        return 0.9, "۴س و ۱س هم‌جهت"
    if (t4 and t4 != d and t4 != "flat") and (t1 and t1 != d and t1 != "flat"):
        return -1.0, "۴س و ۱س هر دو خلاف"
    if a4 or a1:
        return 0.35, f"فقط {'۴س' if a4 else '۱س'} هم‌جهت — خلاف روند در دیگری"
    return -0.3, f"روند ۴س {t4} · ۱س {t1} — هم‌جهتی روشن نیست"


def _v_aries(s, ctx):
    if s.get("goOnFirst") or s.get("stage") == "PULLBACK_1":
        return -0.6, "ورود روی پولبک اول — روش حمید: صبر برای پولبک دوم"
    if s.get("choch"):
        return -0.7, "CHoCH داخل پولبک — تله محتمل، نه برگشت (قانون ۵)"
    imp = (s.get("block") or {}).get("impulse") or s.get("impulse")
    if imp is not None:
        try:
            imp = float(imp)
        except (TypeError, ValueError):
            imp = None
    if imp is not None:
        if imp >= 10:
            return 0.9, f"ضربهٔ بلاک {imp:.0f} — ایمپالس قوی"
        if imp >= 6:
            return 0.6, f"ضربهٔ بلاک {imp:.0f}"
        return -0.4, f"ضربهٔ بلاک ضعیف {imp:.0f}"
    if s.get("trend_mode") == "with-trend":
        return 0.3, "پولبک هم‌جهت روند، ایمپالس اندازه‌گیری نشده"
    return None, "ایمپالس/توالی ثبت نشده"


def _v_leo(s, ctx):
    pm = s.get("premortem") or {}
    ob = pm.get("ob_ctx") or {}
    al = ob.get("align")
    if al == "with":
        return 0.8, f"اردر بلاک {ob.get('tf') or ''} هم‌جهت" + (f"، {ob.get('hunts')} هانت" if ob.get("hunts") else "")
    if al == "against":
        return -0.8, f"اردر بلاک {ob.get('tf') or ''} مخالف جلوی راه"
    ret = (s.get("block") or {}).get("returns")
    if ret is not None and ret >= 3:
        return -0.5, f"بلاک {ret} بار برگشت خورده — فرسوده"
    if s.get("inOB") or s.get("ob"):
        return 0.4, "ورود داخل/کنار اردر بلاک"
    return None, "اردر بلاکی ثبت نشده"


def _v_cancer(s, ctx):
    d = _sign(s.get("dir"))
    parts, v = [], 0.0
    sw = s.get("swept")
    if sw:
        n = sw.get("n") if isinstance(sw, dict) else sw
        v += 0.5
        parts.append(f"نقدینگی جمع شد ({n} برخورد)")
    lm = s.get("liq_map") or {}
    mag = lm.get("magnet")
    if mag in ("above", "below"):
        with_dir = (mag == "above" and d > 0) or (mag == "below" and d < 0)
        v += 0.5 if with_dir else -0.6
        parts.append(f"آهن‌ربای نقدینگی {'هم‌جهت' if with_dir else 'خلاف'} ({mag})")
    elif mag == "balanced":
        parts.append("نقشهٔ نقدینگی متعادل")
    if not parts:
        return None, "شاهد نقدینگی ثبت نشده"
    return max(-1.0, min(1.0, v)), " · ".join(parts)


def _v_pisces(s, ctx):
    pm = s.get("premortem") or {}
    pat = (pm.get("patterns") or {}).get("align")
    q = s.get("quality")
    v, parts = 0.0, []
    if pat == "with":
        v += 0.5
        parts.append("الگوی کندلی هم‌جهت")
    elif pat == "against":
        v -= 0.6
        parts.append("الگوی کندلی مخالف")
    if q is not None:
        try:
            q = float(q)
            if q >= 70:
                v += 0.4
                parts.append(f"کیفیت {q:.0f}")
            elif q < 50:
                v -= 0.3
                parts.append(f"کیفیت پایین {q:.0f}")
            else:
                parts.append(f"کیفیت {q:.0f}")
        except (TypeError, ValueError):
            pass
    if s.get("elite"):
        v += 0.2
        parts.append("ستاپ نخبه")
    if not parts:
        return None, "کندل/کیفیت ثبت نشده"
    return max(-1.0, min(1.0, v)), " · ".join(parts)


def _v_libra(s, ctx):
    rr = s.get("rr")
    fee = ctx.get("fee_r")
    if fee is None:
        try:
            from hamid import fees as _fees
            fee = _fees.cost_in_r(float(s["entry"]), float(s["sl"]), s["sym"])
        except Exception:                            # noqa: BLE001
            fee = None
    parts, v = [], 0.0
    if fee is not None:
        if fee >= 0.25:
            return -1.0, f"کارمزد {fee:.2f}R ≥ ۰.۲۵R — دام اسکالپ"
        v += 0.5 if fee <= 0.15 else 0.1
        parts.append(f"کارمزد {fee:.2f}R")
    if rr is not None:
        try:
            rr = float(rr)
            if rr >= 1.8:
                v += 0.5
            elif rr < 1.5:
                v -= 0.5
            parts.append(f"RR {rr:g}")
        except (TypeError, ValueError):
            pass
    if not parts:
        return None, "هندسه/کارمزد ثبت نشده"
    return max(-1.0, min(1.0, v)), " · ".join(parts)


def _v_capricorn(s, ctx):
    lr = s.get("learning") or {}
    n, ev, hit = lr.get("n"), lr.get("ev"), lr.get("hit")
    if not n or n < MIN_N or ev is None:
        return None, "کارنامهٔ همین ارز/جهت هنوز نمونهٔ کافی ندارد"
    if ev <= -0.30:
        return -0.9, f"کارنامه بد: {n} مورد، برد {hit}٪، انتظار {ev:+.2f}R"
    if ev >= 0.10:
        return 0.7, f"کارنامه خوب: {n} مورد، برد {hit}٪، انتظار {ev:+.2f}R"
    if ev < 0:
        return -0.3, f"کارنامه منفی ضعیف: {n} مورد، انتظار {ev:+.2f}R"
    return 0.0, f"کارنامه خنثی: {n} مورد، انتظار {ev:+.2f}R"


def _v_virgo(s, ctx):
    parts, v = [], 0.0
    src = s.get("candle_src") or ctx.get("candle_src")
    if src:
        if str(src).startswith("bitunix"):
            v += 0.5
            parts.append("کندل از بازار اجرا (بیت‌یونیکس پرپ)")
        else:
            v += 0.15
            parts.append(f"کندل پشتیبان {src}")
    sy = s.get("sync") or {}
    dp = sy.get("dist_pct")
    if dp is not None:
        if abs(dp) <= 0.5:
            v += 0.4
            parts.append(f"هم‌زمان ({dp:+.2f}٪)")
        elif abs(dp) > 1.5:
            v -= 0.8
            parts.append(f"دور از ورود ({dp:+.2f}٪)")
        else:
            parts.append(f"فاصله {dp:+.2f}٪")
    ba = s.get("barsAgo")
    if ba is not None and ba > 6:
        v -= 0.3
        parts.append(f"ستاپ {ba} کندل قدیمی")
    if not parts:
        return None, "کیفیت/هم‌زمانی ثبت نشده"
    return max(-1.0, min(1.0, v)), " · ".join(parts)


def _v_sagittarius(s, ctx):
    na = s.get("news_align") or ctx.get("news_align")
    if na == "with":
        return 0.5, "اجماع خبری هم‌جهت (دیدگاه)"
    if na == "against":
        return -0.5, "اجماع خبری خلاف (دیدگاه)"
    return None, "اجماع خبری ندارد"


def _v_aquarius(s, ctx):
    heat = s.get("fomo_heat") if s.get("fomo_heat") is not None else ctx.get("fomo_heat")
    wit = s.get("fomo_witness") if s.get("fomo_witness") is not None else ctx.get("fomo_witness")
    parts, v = [], 0.0
    if wit:
        v += 0.4
        parts.append("شاهد فومو برای همین نماد")
    if heat is not None:
        try:
            heat = float(heat)
            if heat >= 80 and _sign(s.get("dir")) > 0:
                v -= 0.5
                parts.append(f"جمعیت داغ {heat:.0f} در لانگ — خطر تله")
            else:
                parts.append(f"داغی {heat:.0f}")
        except (TypeError, ValueError):
            pass
    if not parts:
        return None, "شاهد جمعیت ندارد"
    return max(-1.0, min(1.0, v)), " · ".join(parts)


VOTERS = {"scorpio": _v_scorpio, "gemini": _v_gemini, "taurus": _v_taurus, "aries": _v_aries,
          "leo": _v_leo, "cancer": _v_cancer, "pisces": _v_pisces, "libra": _v_libra,
          "capricorn": _v_capricorn, "virgo": _v_virgo, "sagittarius": _v_sagittarius,
          "aquarius": _v_aquarius}
assert set(VOTERS) == set(BY_ID) and len(GUARDIANS) == 12


# ── وزن از کارنامه ────────────────────────────────────────────────────────
def _wilson(k, n, z=1.96):
    if n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(c - h, 3), round(c + h, 3)]


def load_scores(path=None):
    p = Path(path or SCORES)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return {"generated": None, "guardians": {}}


def weight_of(gid, scores, base_rate=None):
    """وزن = پایه × (۱ + باند از کارنامه). زیر MIN_N هیچ حرکتی.

    ── مبنا، نه ۵۰٪ (رفع ۶ سپتامبر) ──────────────────────────────────────
    تا امروز دقتِ هر مراقب با **۰.۵** سنجیده می‌شد، انگار سکه می‌اندازد.
    ولی نرخِ بردِ خودِ دفتر ۷۱.۷٪ است (دفترِ تریل-سنگین). یعنی مراقبی که
    **همیشه** «+» بگوید و هیچ تحلیلی نکند، دقت ~۷۲٪ می‌گیرد و بیشینهٔ
    وزن (۱.۴) را می‌بَرد — رأی‌دهنده‌ای که هیچ تمایزی نمی‌سازد، پاداشِ
    کامل می‌گیرد. این دقیقاً همان کلاسی است که حمید از پنل دیگر آورد:
    رأیی که همیشه یک عدد است و فقط سقفِ اعتماد را جابه‌جا می‌کند.

    اندازه‌گیریِ همان روز: از ۱۲ مراقب، **جوزا** (۱۴/۱۴ رأی = +۰.۷) و
    **جدی** (۳۶/۳۶ رأی یک‌مقدار) انحراف معیارِ صفر دارند — و هر دو
    وزن بالا گرفته بودند.

    درمان: مبنا نرخِ واقعیِ همان دفتر است، نه ۰.۵. مراقب فقط برای
    **بهترشدن از مبنا** پاداش می‌گیرد. مبنای ناموجود → همان ۰.۵ (رفتار
    قبلی، تا وقتی دفتر عددش را بدهد).
    """
    g = BY_ID[gid]
    rec = (scores.get("guardians") or {}).get(gid) or {}
    n, k = rec.get("n") or 0, rec.get("correct") or 0
    if n < MIN_N:
        return g["base"], f"n={n} < {MIN_N} — وزن پایه"
    if base_rate is None:
        base_rate = scores.get("base_rate")
    b = float(base_rate) if isinstance(base_rate, (int, float)) else 0.5
    b = min(max(b, 0.05), 0.95)                  # مبنای افراطی وزن را نترکاند
    acc = k / n
    ci = rec.get("ci95") or _wilson(k, n)
    confirmed = ci is not None and (ci[0] > b or ci[1] < b)
    band = BAND_CONFIRMED if confirmed else BAND_EXPLORATORY
    # تقسیم بر بیشینهٔ فاصلهٔ ممکن تا مقیاس مثل قبل در [−۱,+۱] بماند
    span = max(1 - b, b)
    adj = max(-band, min(band, (acc - b) / span))
    return round(g["base"] * (1 + adj), 4), (
        f"دقت {acc*100:.0f}٪ در برابر مبنای {b*100:.0f}٪ · n={n} CI {ci} — "
        + ("باند کامل" if confirmed else "باند اکتشافی"))


def weights(scores=None):
    scores = scores if scores is not None else load_scores()
    w = {gid: weight_of(gid, scores) for gid in BY_ID}
    total = sum(v for v, _ in w.values())
    capped = sum(w[g][0] for g in CAPPED)
    if total > 0 and capped / total > SOCIAL_CAP:
        k = (SOCIAL_CAP * (total - capped)) / ((1 - SOCIAL_CAP) * capped)
        for g in CAPPED:
            # گردکردن به پایین — سقف ۵٪ سقف است، نه «تقریباً ۵٪»
            w[g] = (math.floor(w[g][0] * k * 10000) / 10000, w[g][1] + " · سقف لایهٔ اجتماعی ۵٪")
    return w


# ── حکم ققنوس ────────────────────────────────────────────────────────────
def _label(score, n_voters):
    if n_voters < MIN_VOTERS:
        return "بی‌نظر", "فقط پیپر / نظارت", "شواهد کم"
    if score >= 0.45:
        return "تأیید قوی", "سایز کامل", ""
    if score >= 0.15:
        return "تأیید", "سایز نصف", ""
    if score > -0.15:
        return "بی‌نظر", "فقط پیپر / نظارت", ""
    return "مخالف", "نرو", ""


def _context(s, now_ms=None):
    ctx = {"now_ms": now_ms or time.time() * 1000}
    try:
        ctx["dominance"] = json.loads(DOMINANCE.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        ctx["dominance"] = {}
    try:
        ctx["btc_sens"] = json.loads(BTC_SENS.read_text(encoding="utf-8")).get("coins") or {}
    except Exception:                                # noqa: BLE001
        ctx["btc_sens"] = {}
    return ctx


def judge(s, ctx=None, scores=None, write=False, now_ms=None):
    """همهٔ ۱۲ مراقب سیگنال را می‌بینند؛ ققنوس حکم وزنی می‌دهد. هرگز استثنا نمی‌دهد."""
    ctx = {**_context(s, now_ms), **(ctx or {})}
    w = weights(scores)
    votes, num, den = {}, 0.0, 0.0
    n_for = n_against = n_abs = 0
    for g in GUARDIANS:
        gid = g["id"]
        try:
            v, why = VOTERS[gid](s, ctx)
        except Exception as e:                       # noqa: BLE001 - مراقبِ خراب = ممتنع با دلیل
            v, why = None, f"خطای مراقب: {type(e).__name__}"
        if v is None:
            n_abs += 1
        else:
            v = max(-1.0, min(1.0, float(v)))
            num += w[gid][0] * v
            den += w[gid][0]
            if v > 0.05:
                n_for += 1
            elif v < -0.05:
                n_against += 1
        votes[gid] = {"v": None if v is None else round(v, 3), "w": w[gid][0], "why": why}
    n_voters = n_for + n_against + (12 - n_for - n_against - n_abs)
    score = round(num / den, 4) if den else 0.0
    label, posture, note = _label(score, n_voters)
    strongest = sorted(((d["v"], gid) for gid, d in votes.items() if d["v"] is not None), key=lambda t: t[0])
    top_for = [f"{BY_ID[g]['name']}: {votes[g]['why']}" for v, g in reversed(strongest) if v > 0][:2]
    top_against = [f"{BY_ID[g]['name']}: {votes[g]['why']}" for v, g in strongest if v < 0][:2]
    verdict = {"score": score, "label": label, "posture": posture, "note": note,
               "for": n_for, "against": n_against, "abstain": n_abs, "voters": n_voters,
               "top_for": top_for, "top_against": top_against, "votes": votes,
               "at": int(ctx["now_ms"]), "sym": s.get("sym"), "tf": s.get("tf"), "dir": s.get("dir"),
               "advisory": True}
    if write:
        try:
            BRAIN.mkdir(parents=True, exist_ok=True)
            with VERDICTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(verdict, ensure_ascii=False) + "\n")
        except Exception:                            # noqa: BLE001
            pass
    return verdict


def caption_lines(v):
    """دو خط کپشن: حکم + قوی‌ترین دلیل هر طرف. حکم مشاوره‌ای است (قانون ۰۳)."""
    if not v:
        return []
    L = [f"🔥 <i>ققنوس: <b>{v['label']}</b> ({v['for']} موافق · {v['against']} مخالف · "
         f"{v['abstain']} ممتنع، امتیاز {v['score']:+.2f}) — پیشنهاد اندازه: {v['posture']}"
         + (f" — {v['note']}" if v.get("note") else "") + "</i>"]
    bits = []
    if v.get("top_for"):
        bits.append("✔ " + v["top_for"][0])
    if v.get("top_against"):
        bits.append("✘ " + v["top_against"][0])
    if bits:
        L.append("<i>" + " · ".join(bits) + "</i>")
    return L


def trace(v):
    """ردپای دفتر: امتیاز، برچسب و رأی خام هر مراقب — برای ماشین شبانه."""
    if not v:
        return {"phoenix_score": None, "phoenix_label": None, "phoenix_votes": None}
    return {"phoenix_score": v["score"], "phoenix_label": v["label"],
            "phoenix_votes": {g: d["v"] for g, d in v["votes"].items()}}


# ── سنجش شبانه ───────────────────────────────────────────────────────────
def score_outcomes(closed_path=None, now_ms=None):
    """هر مراقب چند بار درست گفت: رأی هم‌علامت با R = درست؛ ممتنع شمرده نمی‌شود."""
    p = Path(closed_path or CLOSED)
    acc = {gid: {"n": 0, "correct": 0} for gid in BY_ID}
    used = wins = 0
    # ── یکتاسازی بر هویت معامله (رفع ۶ سپتامبر) ──────────────────────────
    #
    # این تابع ردیف‌ها را می‌شمرد، نه معامله‌ها را — و بازوهای آزمایشِ تریل
    # (`exp-trail-g65`/`exp-trail-g80`) همان معامله را آینه می‌کنند. پس هر
    # معامله سه بار در کارنامه می‌آمد. اندازه‌گیریِ همان روز: **۱۷۸ ردیف =
    # ۶۰ معاملهٔ یکتا** (۵۹ تا ×۳ + یک تکی).
    #
    # این دقیقاً همان کلاسی است که ۲۴ اوت یک بار تصحیح شد («قبل از هر CI،
    # یکتاییِ ردیف‌ها باید اثبات‌شده باشد») و در ماژول تازه دوباره رویید.
    # تکرار، هم n را چند برابر می‌کند و هم بازهٔ اطمینان را ساختگی تنگ —
    # یعنی مراقبی زودتر از حقش «تأییدشده» می‌شود و وزن می‌گیرد.
    seen = set()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:                        # noqa: BLE001
                continue
            why = r.get("why") or {}
            pv = why.get("phoenix_votes")
            R = r.get("R")
            if not pv or R is None or r.get("outcome") in ("expired", "no_fill", None):
                continue
            try:
                R = float(R)
            except (TypeError, ValueError):
                continue
            if R == 0:
                continue
            try:
                ident = (r.get("sym"), r.get("dir"),
                         round(float(r.get("entry") or 0), 10), r.get("opened"))
            except (TypeError, ValueError):
                ident = (r.get("sym"), r.get("dir"), r.get("entry"), r.get("opened"))
            if ident in seen:
                continue
            seen.add(ident)
            used += 1
            wins += 1 if R > 0 else 0
            for gid, v in pv.items():
                if gid not in acc or v is None or abs(v) <= 0.05:
                    continue
                acc[gid]["n"] += 1
                if (v > 0) == (R > 0):
                    acc[gid]["correct"] += 1
    # نرخِ بردِ همین دفتر — مبنایی که وزن با آن سنجیده می‌شود، نه ۰.۵.
    # بدون این، رأی‌دهندهٔ «همیشه مثبت» بیشینهٔ وزن را مجانی می‌برد.
    out = {"generated": int(now_ms or time.time() * 1000), "trades_used": used, "min_n": MIN_N,
           "base_rate": round(wins / used, 4) if used else None,
           "guardians": {}}
    for gid, a in acc.items():
        n, k = a["n"], a["correct"]
        out["guardians"][gid] = {"n": n, "correct": k, "acc": round(k / n, 3) if n else None,
                                 "ci95": _wilson(k, n) if n else None}
    return out


def snapshot(scores=None, n_recent=12):
    scores = scores if scores is not None else load_scores()
    w = weights(scores)
    recent = []
    try:
        lines = VERDICTS.read_text(encoding="utf-8").splitlines()[-n_recent:]
        recent = [json.loads(l) for l in lines if l.strip()]
        for r in recent:
            r.pop("votes", None)
    except Exception:                                # noqa: BLE001
        recent = []
    table = []
    for g in GUARDIANS:
        rec = (scores.get("guardians") or {}).get(g["id"]) or {}
        table.append({"id": g["id"], "name": g["name"], "sign": g["sign"], "engine": g["engine"],
                      "specialty": g["specialty"], "order": g["order"], "base": g["base"],
                      "weight": w[g["id"]][0], "weight_why": w[g["id"]][1],
                      "n": rec.get("n") or 0, "correct": rec.get("correct") or 0,
                      "acc": rec.get("acc"), "ci95": rec.get("ci95")})
    return {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹", "owner": "E00 — ققنوس",
            "advisory": True, "social_cap": SOCIAL_CAP, "min_n": MIN_N, "min_voters": MIN_VOTERS,
            "labels": {"تأیید قوی": "≥ +0.45 → سایز کامل", "تأیید": "≥ +0.15 → سایز نصف",
                       "بی‌نظر": "(−0.15, +0.15) → فقط پیپر / نظارت", "مخالف": "≤ −0.15 → نرو"},
            "boundary": "حکم روی پیام و دفتر می‌نشیند و شبانه سنجیده می‌شود؛ هیچ سیگنالی را حذف و هیچ عددی را عوض نمی‌کند. "
                        "ورود به دروازه/سایز خودکار فقط با CI بالای صفر و تأیید حمید (قانون ۰۳/۱۲).",
            "trades_scored": scores.get("trades_used") or 0, "scores_generated": scores.get("generated"),
            "guardians": table, "recent": recent}


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--score" in argv:
        sc = score_outcomes()
        BRAIN.mkdir(parents=True, exist_ok=True)
        SCORES.write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"ققنوس: کارنامه از {sc['trades_used']} معاملهٔ بسته با رأی")
    snap = snapshot()
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"نوشته شد: {OUT.name}")
    for g in snap["guardians"]:
        print(f"  {g['sign']} {g['name']:<6} وزن {g['weight']:.2f}  n={g['n']}  {g['specialty']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
