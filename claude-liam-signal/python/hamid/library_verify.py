"""راستی‌آزمایی صف کتابخانه — کار ایجنت اصلی، نه حلقهٔ خودکار.

## چرا این فایل وجود دارد

۲۲ اوت اندازه‌گیری شد: صف ۴۳ مدخل QUEUED داشت و قفسه ۱۲ مدخل VERIFIED
که همه در یک نوبت دستی وارد شده بودند. یعنی حلقهٔ مطالعه **کار می‌کرد**
(هر انجین سطر reading دارد) ولی هیچ‌چیز از صف به قفسه نمی‌رفت، چون
راستی‌آزمایی طبق README و قانون ۰۳ کارِ ایجنت اصلی است و کسی انجامش
نداده بود. از بیرون سالم به نظر می‌رسید: حلقه سبز، فایل‌ها پر، خروجی صفر.

## راستی‌آزمایی یعنی چه — و یعنی چه نه

**یعنی**: منبع واقعی و معتبر است؛ توصیفِ روشش در مدخل درست است؛ با
قوانین هسته تناقض ندارد.

**یعنی نه**: «ادعایش درست است» و قطعاً نه «وارد Production می‌شود».
ورود به قفسه فقط اجازهٔ **خواندن** است. هر قاعده‌ای که از این منابع
دربیاید باز هم باید مسیر کامل قانون ۰۳ را برود
(BACKTEST → WALK_FORWARD → PAPER → ... با CI از صفر رد شده).

## پیش‌فرض امن

هر مدخلی که در جدول تصمیم نباشد **QUEUED می‌ماند**. سکوت هرگز به معنای
تأیید نیست — وگرنه همان خرابیِ بی‌صدایی می‌شود که این فایل برای رفعش
نوشته شد.

## تعارض حذف نمی‌شود

بعضی از این منابع نتیجه‌های متناقض دارند (نمونهٔ روشن: شواهد کندل‌شناسی).
قانون ۰۳ می‌گوید تعارض versioned و قابل‌مشاهده می‌ماند، پس هر دو طرف
VERIFIED می‌شوند و تعارض در `notes` صریح نوشته می‌شود.

اجرا:  python3 -m hamid.library_verify --apply
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LIB = ROOT / "brain" / "library"
QUEUE = LIB / "queue.jsonl"
SHELF = LIB / "index.jsonl"

# ── جدول تصمیم ──────────────────────────────────────────────────────────
# کلید = عنوان نرمال‌شده. مقدار = (status, یادداشت راستی‌آزمایی).
# یادداشت باید بگوید **چرا معتبر است** و **برای چه کاری**، نه تعریف کلی.
V = "VERIFIED"
DECISIONS = {
    # E10 — ریزساختار و جریان سفارش. مرجعِ همان چیزی که الان نداریمش.
    "trading and exchanges market microstructure for practitioners": (
        V, "مرجع استاندارد ریزساختار (Harris, OUP 2002). تعریف‌های صف، "
           "اسپرد، انواع سفارش و نقش بازارگردان از این‌جا می‌آید — پایهٔ "
           "لازم برای اینکه فیلدهای عمق درست تفسیر شوند."),
    "empirical market microstructure": (
        V, "Hasbrouck (OUP 2007) — روش‌شناسی تجربی: VAR روی جریان سفارش، "
           "تجزیهٔ اثر دائمی/موقت. همان ابزاری که برای سنجش d_* لازم است."),
    "trades quotes and prices financial markets under the microscope": (
        V, "Bouchaud, Bonart, Donier, Gould (CUP 2018) — کتاب مرجعِ کمیِ "
           "دفتر سفارش: اثر قیمت، عدم‌تعادل صف، آمار لغو. مستقیماً همان "
           "پرسشی که depth_bos می‌سنجد."),
    "algorithmic and high frequency trading": (
        V, "Cartea, Jaimungal, Penalva (CUP 2015) — چارچوب ریاضی اجرا و "
           "اثر بازار. برای E19 (مدیریت معامله) و E10 هر دو."),
    "measuring the information content of stock trades": (
        V, "Hasbrouck, Journal of Finance 1991 — مقالهٔ پایه‌ای که «محتوای "
           "اطلاعاتی معامله» را قابل اندازه‌گیری کرد."),
    "the price impact of order book events": (
        V, "Cont, Kukanov, Stoikov, J. Financial Econometrics 2014 — منشأ "
           "OFI به شکلی که امروز استفاده می‌شود. **مرز مهم**: OFI واقعی "
           "به رویدادِ دفتر نیاز دارد؛ دادهٔ REST ما تقریب درشت است و "
           "فیلدها به همین دلیل d_ نام دارند نه ofi."),
    "flow toxicity and liquidity in a high frequency world": (
        V, "Easley, López de Prado, O'Hara, RFS 2012 — VPIN. **تعارض ثبت "
           "شود**: خودِ VPIN بعداً نقد جدی شد (Andersen & Bondarenko). "
           "پس ادعایش با احتیاط و فقط با بک‌تست خودمان."),
    "deep order flow imbalance extracting alpha at multiple horizons": (
        V, "Kolm, Turiel, Westray — OFI چندسطحی و افق‌های مختلف. مستقیماً "
           "مرتبط با اینکه ما عدم‌تعادل را در ۳ سطح ثبت می‌کنیم."),
    "limit order books": (
        V, "دو مدخل هم‌نام: مرور Gould و همکاران (Quantitative Finance "
           "2013) و کتاب Abergel و همکاران (CUP 2016). هر دو مرور "
           "ساختاریِ معتبرِ دفتر سفارش‌اند."),
    "market microstructure in practice": (
        V, "Lehalle & Laruelle — نگاه عملیِ اجرا و نقدشوندگی؛ مکمل کتاب "
           "نظری Bouchaud."),
    "the financial mathematics of market liquidity": (
        V, "Guéant 2016 — ریاضیات اجرا/نقدشوندگی. برای سایز و اثر بازار."),
    "high frequency trading": (
        V, "Aldridge, 2nd ed 2013 — مروری عملی. **درجهٔ اعتبار پایین‌تر** "
           "از منابع دانشگاهی بالا؛ به‌عنوان زمینه، نه مرجع عددی."),
    "queue imbalance as a one tick ahead price predictor in a limit order book": (
        V, "Gould & Bonart — دقیقاً همان فرضیه‌ای که depth_bos می‌سنجد: "
           "آیا عدم‌تعادل صف قدم بعدی قیمت را می‌گوید. نتیجه‌شان مثبت "
           "ولی روی داده و بازارِ خودشان — برای ما فرضیه است نه نتیجه."),
    "enhancing trading strategies with order book signals": (
        V, "Cartea, Donnelly, Jaimungal — استفادهٔ عملی از سیگنال دفتر در "
           "استراتژی. الگوی همان کاری که اگر depth_bos جواب مثبت داد "
           "باید بکنیم."),
    "detecting layering and spoofing in markets": (
        V, "Bao & Putniņš — روش‌شناسی تشخیص لایه‌چینی. **مرز صریح**: با "
           "دادهٔ عکس‌برداریِ ما لغو از اجرا تفکیک نمی‌شود، پس این منبع "
           "فقط برای فهمِ SPOOF_LIKE_RISK است، نه ادعای اثبات (قانون ۰۸)."),


    # ── افزودهٔ ۲۳ اوت: نامِ علمیِ کاری که حمید توصیف کرد ──────────────
    # حمید: «استاپ را زیر آخرین کف/سقف یا اردر بلاک یا محل هانت نقدینگی
    # می‌گذارند.» ادبیات SMC برای این‌ها شواهد داوری‌شده ندارد، ولی خودِ
    # پدیده‌ها در ادبیات دانشگاهی با نام دیگر مطالعه شده‌اند. این پنج
    # منبع همان پل‌اند.
    "currency orders and exchange rate dynamics an explanation for the "
    "predictive success of technical analysis": (
        V, "Osler, Journal of Finance 2003 — از دفتر سفارش واقعی یک بانک "
           "بزرگ. نشان می‌دهد تیک‌پرافیت‌ها روی اعداد رُند خوشه می‌شوند و "
           "استاپ‌ها درست آن‌سویشان. این **مدرکِ داده‌محورِ** چرایی واکنش "
           "حمایت/مقاومت است — نه ادعای یوتیوبی."),
    "stop loss orders and price cascades in currency markets": (
        V, "Osler، JIMF 2005 — سازوکار آبشار استاپ با داده. نسخهٔ مستندِ "
           "همان چیزی که «هانت نقدینگی» می‌نامیم. **مرز**: بازارش FX است؛ "
           "انتقال به کریپتو باید روی دفتر خودمان سنجیده شود."),
    "the volume clock insights into the high frequency paradigm": (
        V, "Easley, López de Prado, O'Hara — در فرکانس بالا اطلاعات با "
           "**حجم** می‌آید نه با ساعت، پس کندلِ زمانی نمونه‌برداری بدی "
           "است. مستقیماً مربوط به هدف ۳۰ثانیه: شاید مسئله خودِ کندلِ "
           "زمانی باشد نه دورهٔ آن."),
    "trading price action trading ranges": (
        V, "Al Brooks، جلد سوم — رفتار داخل رنج، شکست کاذب، تلهٔ لبهٔ "
           "رنج. جلد گمشدهٔ قفسه و دقیقاً همان جایی که اسکلپ ۱ دقیقه "
           "بیشترین ضرر را می‌دهد."),
    "anomalous price impact and the critical nature of liquidity in "
    "financial markets": (
        V, "Toth و همکاران با Bouchaud، Physical Review X 2011 — قانون "
           "جذرِ اثر بازار. نقدینگی واقعی بسیار کمتر از چیزی است که دفتر "
           "نشان می‌دهد؛ سفارش بزرگ تکه‌تکه اجرا می‌شود و ردپایش همان "
           "چیزی است که «اردر بلاک» نامیده می‌شود — با ریاضیِ سنجیدنی."),

    # E09 — کندل‌شناسی. شواهدش عمداً هر دو طرف دارد.
    "japanese candlestick charting techniques": (
        V, "Nison — منبع تاریخیِ تعریف الگوها. تعریف را از این‌جا "
           "می‌گیریم؛ **اعتبار آماری را نه** (قانون ۰۹)."),
    "candlestick charting explained": (
        V, "Morris — تعریف‌های کمی‌شده‌تر از Nison؛ برای تبدیل الگو به "
           "نسبت (بدنه/گستره، ویک/گستره)."),
    "encyclopedia of candlestick charts": (
        V, "Bulkowski — آمار برخورد/شکست روی نمونهٔ بزرگ. عدد می‌دهد، که "
           "برای گریدینگ لازم است؛ ولی بازارِ سهام و تایمِ روزانه است، "
           "پس مستقیماً به کریپتوی ۱ دقیقه منتقل نمی‌شود."),
    "the art and science of technical analysis": (
        V, "Grimes 2012 — همان قانون CI ما به زبان تحلیل تکنیکال: هر "
           "قاعده باید ثابت کند از تصادف بهتر است. سنگ‌بنای روش‌شناسی."),
    "the predictive power of price patterns": (
        V, "Caginalp & Laurent 1998 — شواهد **له** الگوهای کندلی. "
           "تعارض با Marshall و همکاران عمداً حفظ می‌شود (قانون ۰۳)."),
    "performance of candlestick analysis on intraday futures data": (
        V, "Fock, Klein, Zwergel — روی دادهٔ درون‌روزیِ فیوچرز؛ نزدیک‌ترین "
           "بستر به ما. نتیجه‌شان محتاطانه/منفی."),
    "candlestick technical trading strategies can they create value": (
        V, "Marshall, Young, Rose — شواهد **علیه** ارزش کندل روی سهام "
           "امریکا. طرف دیگرِ تعارضِ ثبت‌شده."),
    "the intra day performance of market timing strategies and trading": (
        V, "Duvinage, Mazza, Petitjean — درون‌روزی، بعد از کسر هزینه. "
           "دقیقاً همان سؤالی که برای اسکلپ ۱-۳ دقیقه مهم است."),

    # E07 — ساختار و پرایس اکشن
    "trading price action trends": (
        V, "Al Brooks — خوانش کندل‌به‌کندل در روند. روشش انضباطی است "
           "(کلوزِ قاطع، نه ویک) و با trendlines-canon می‌خواند."),
    "trading price action reversals": (
        V, "Al Brooks — تشخیص برگشت؛ مستقیماً مرتبط با تفکیک CHoCH "
           "واقعی از تلهٔ داخل پولبک، که قانون هستهٔ ماست."),
    "reading price charts bar by bar": (
        V, "Al Brooks (Wiley 2009) — نسخهٔ یک‌جلدی و فشرده‌ترِ همان روش "
           "سه‌جلدی. برای شروع مناسب‌تر است چون تعریف‌ها را بدون تکرار "
           "می‌دهد؛ ولی جزئیات برگشت در جلد Reversals کامل‌تر است."),

    # E18 — روش‌شناسی سنجش. بالاترین اولویت عملی.
    "advances in financial machine learning": (
        V, "López de Prado 2018 — نمونه‌گیری، برچسب‌گذاری سه‌مانعی، "
           "purged CV. مستقیماً همان چیزی که بک‌تست‌های ما لازم دارند."),
    "the deflated sharpe ratio": (
        V, "Bailey & López de Prado 2014 — تصحیح چندآزمونی. **همین منبع "
           "۲۲ اوت یک عیب واقعی را رو کرد**: آستانهٔ sqrt(2·ln n) که "
           "استفاده می‌کردم امیدِ بیشینه است نه آستانهٔ کنترل خطا؛ به "
           "Šidák اصلاح شد."),
    "pseudo mathematics and financial charlatanism": (
        V, "Bailey, Borwein, López de Prado, Zhu — چرا بک‌تستِ "
           "بهینه‌سازی‌شده تقریباً همیشه دروغ می‌گوید. همان درسی که "
           "تأیید خارج از نمونهٔ ۲۲ اوت عملاً به ما داد."),

    # E08 — نواحی عرضه/تقاضا با ریشهٔ مستند
    "trades about to happen": (
        V, "Weis — وایکاف مدرن: effort vs result، spring/upthrust. ریشهٔ "
           "مستندِ همان چیزی که SMC اسمش را OB گذاشته."),
    "mind over markets": (
        V, "Dalton — Auction Market Theory، ناحیهٔ ارزش و POC. چارچوب "
           "**مستقل** برای همان نواحی؛ ارزشش در همین استقلال است."),

    # E26 — ناظر کل: مدیریت/روانشناسی/اقتصاد (کتابخانه‌اش در منشور)
    "thinking fast and slow": (
        V, "Kahneman — خطاهای سیستم تصمیم. **هشدار**: بخش پرایمینگش در "
           "بحران بازتولید زیر سؤال رفت؛ بخش‌های تصمیم تحت ریسک محکم‌اند."),
    "the psychology of money": (
        V, "Housel — رفتار و ریسک. کتاب روایی است نه پژوهشی؛ برای E26 "
           "به‌عنوان زمینه، نه منبع عدد."),
    "basic economics": (
        V, "Sowell — اقتصاد پایه. **دیدگاه‌دار** است؛ به‌عنوان یک نگاه "
           "ثبت می‌شود نه اجماع."),

    # اسکلپ — بستر مستقیم ۱-۵ دقیقه
    "forex price action scalping": (
        V, "Volman — یکی از معدود منابع جدی با تعریف دقیق ستاپ روی تایم "
           "بسیار پایین. بازارش فارکس است؛ انتقال به کریپتو باید "
           "بک‌تست شود."),
    "understanding price action": (
        V, "Volman — تایم ۵ دقیقه، همان روش با تعریف‌های صریح‌تر."),
}


def norm_key(title, source=""):
    """کلید نرمال: عنوان انگلیسی پیش از خط تیرهٔ فارسی، بدون نشانه و شماره.

    عنوان‌ها از دو بستهٔ مختلف آمده‌اند و شکلشان یکی نیست ("... , 2nd
    Edition" در یکی، زیرعنوان فارسی در دیگری). بدون نرمال‌سازی، یک کتاب
    دو بار وارد قفسه می‌شود.

    **زیرعنوان بریده نمی‌شود.** نسخهٔ اول این تابع همه‌چیز را بعد از
    «:» یا «,» می‌انداخت و دو خرابیِ متقابل ساخت: «Trading Price Action:
    Trends» و «... : Reversals» یکی شدند (دو کتاب متفاوت، یکی گم می‌شد)،
    و «Thinking, Fast and Slow» به «thinking» تبدیل شد که با هیچ کلیدی
    نمی‌خورد. زیرعنوان دقیقاً همان چیزی است که این‌ها را از هم جدا
    می‌کند، پس می‌ماند و فقط نشانه‌گذاری و شمارهٔ ویرایش پاک می‌شود."""
    t = (title or "").split("—")[0].split("|")[0]
    t = re.sub(r"\b\d+(st|nd|rd|th)\s+edition\b", " ", t, flags=re.I)
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def author_hint(source):
    """نام‌خانوادگی نویسندهٔ اول از فیلد source، در هر دو قالبِ موجود.

    دو بسته دو قالب دارند: «book | Larry Harris | 2002 | url» و
    «David H. Weis — Trades About to Happen (Wiley)». هر دو پوشش داده
    می‌شوند."""
    s = source or ""
    chunk = s.split("|")[1] if "|" in s else s.split("—")[0]
    first = re.split(r"[;,]", chunk)[0].strip()
    words = re.sub(r"[^A-Za-zÀ-ÿ ]+", " ", first).split()
    return words[-1].lower() if words else ""


def dupe_key(entry):
    """کلید یکتاییِ اثر = عنوان + نویسندهٔ اول.

    عنوان به‌تنهایی کافی نیست: «Limit Order Books» هم نام مرورِ Gould
    است هم کتاب Abergel — دو اثر متفاوت. با عنوانِ تنها یکی بی‌دلیل
    DUPLICATE می‌شد و از قفسه بیرون می‌ماند."""
    return f"{norm_key(entry.get('title', ''))}::{author_hint(entry.get('source', ''))}"


def decide(entry):
    """→ (status, note). کلیدِ ناموجود = QUEUED می‌ماند (پیش‌فرض امن)."""
    k = norm_key(entry.get("title", ""), entry.get("source", ""))
    if k in DECISIONS:
        return DECISIONS[k]
    for dk, val in DECISIONS.items():
        if k and (k.startswith(dk) or dk.startswith(k)) and \
                min(len(k), len(dk)) >= 12:
            return val
    return "QUEUED", ""


def load(p):
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def run(apply=False, quiet=False, queue_path=None, shelf_path=None):
    QUEUE_P = Path(queue_path) if queue_path else QUEUE
    SHELF_P = Path(shelf_path) if shelf_path else SHELF
    queue, shelf = load(QUEUE_P), load(SHELF_P)
    on_shelf = {dupe_key(e) for e in shelf}
    now = int(time.time() * 1000)
    new, updated, dupes, left = [], [], [], []
    seen = set()
    for e in queue:
        if e.get("status") != "QUEUED":
            updated.append(e)
            continue
        k = dupe_key(e)
        status, note = decide(e)
        if status == "QUEUED":
            left.append(e)
            updated.append(e)
            continue
        if k in on_shelf or k in seen:
            # تکراری حذف نمی‌شود (قانون ۲ README) — status عوض می‌شود.
            e = dict(e, status="DUPLICATE",
                     notes=(e.get("notes") or "") +
                           " | تکراری؛ همین منبع از پیش در قفسه است.")
            dupes.append(e)
            updated.append(e)
            continue
        seen.add(k)
        ver = dict(e, status=status, verified_by="lead", verified_at=now,
                   notes=note)
        new.append(ver)
        updated.append(ver)
    if not quiet:
        print(f"صف: {len(queue)} · تأیید تازه: {len(new)} · تکراری: "
              f"{len(dupes)} · هنوز QUEUED: {len(left)}")
        for e in new:
            print(f"  ✓ [{e.get('engine','?'):4}] {e['title'][:60]}")
        for e in dupes:
            print(f"  ⧉ {e['title'][:60]}")
        for e in left:
            print(f"  … بدون تصمیم، QUEUED می‌ماند: {e['title'][:52]}")
    if apply:
        QUEUE_P.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                                   for e in updated))
        with SHELF_P.open("a") as fh:
            for e in new:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        if not quiet:
            print(f"\nقفسه: {len(shelf)} → {len(shelf) + len(new)}")
    elif not quiet:
        print("\n(اجرای خشک — برای نوشتن --apply بده)")
    return {"verified": len(new), "duplicates": len(dupes),
            "still_queued": len(left), "shelf_before": len(shelf)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(0 if run(apply=ap.parse_args().apply) else 0)
