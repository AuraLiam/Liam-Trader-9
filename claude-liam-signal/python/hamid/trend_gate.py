"""دروازهٔ هم‌راستایی با روند — دستور حمید (۱۷ اوت).

مشاهدهٔ او، عین جمله: «بارها دیدم چارت کاملاً صعودی است ولی سیگنال شورت
صادر شده، و برعکس.» ریشه: سلسله‌مراتب ۴س/۱س فقط در امتیاز اثر داشت، نه
به‌صورت وتو در گلوگاه ارسال — سیگنال خلاف روند با امتیازِ جمعیِ خوب رد
می‌شد و می‌رفت.

قانون (مکمل قانون ۲ و ۸ غیرقابل‌مذاکره‌ها):
  هر دو تایم بالا (۴س و ۱س) خلاف جهت سیگنال → وتوی مطلق. هیچ استثنایی.
  یک تایم بالا خلاف جهت → «خلاف روند»: فقط با تمام تأییدیه‌ها می‌گذرد و
  روی پیام برچسب می‌خورد؛ حتی یک تأییدیهٔ غایب → NO_SIGNAL.
  هم‌راستا یا رنج → عبور عادی (بقیهٔ دروازه‌ها سر جایشان‌اند).

تأییدیه‌های کامل خلاف روند (همه لازم‌اند — «تمام تاییدیه‌ها»):
  inOB      قیمت داخل ناحیهٔ معتبر OB
  swept     سوییپ نقدینگی رخ داده (شکار استاپ‌ها پیش از برگشت)
  choch     تغییر کاراکتر ثبت‌شده
  fvg       FVG معتبر در جهت سیگنال
  quality   کیفیت ستاپ ≥ ۷۰

روند هر تایم از structure.trend (سوینگ‌محور، قطعی) با ۲۴۰ کندل.
"""
from hamid.structure import trend

COUNTER_NEEDS = ("inOB", "swept", "choch", "fvg", "quality>=70")
_TF_N = 240

# ── قرارداد شواهد با ورکر (رفع ۳۰ اوت شب) ────────────────────────────────
#
# عیبی که ممیزی پیدا کرد: این دروازه تأییدیه‌ها را با نامِ **آرزویی**
# می‌خواند، نه با نامی که `scan_worker.js` واقعاً می‌نویسد. نتیجه‌اش این
# بود که مسیر «خلاف روند با تأیید کامل» **ساختاراً دست‌نیافتنی** شد:
#
#   · smc کلیدِ `inOB` ندارد؛ اسمش `inside` است (scan_worker.js:83)
#   · smc اصلاً `choch` تولید نمی‌کند
#   · ibs مقدارِ `fvg` و `swept` را **هاردکد** می‌گذارد (scan_worker.js:61)
#
# شاهد: در تمام آرشیو ارسال و دفتر بسته، صفر مورد `counter-confirmed`.
# یعنی عملاً «یک تایم مخالف = وتو» اجرا می‌شد، نه قاعده‌ای که سند
# ۱۷ اوت نوشته. و آزمونِ قبلی نگرفت چون شواهد را **دستی** با همان
# نام‌های آرزویی می‌ساخت — تستِ فیکسچرِ خیالی.
#
# رفع، عمداً **بدون شل‌کردن هیچ چیز**: سه حالت از هم جدا می‌شود —
# حاضر / غایب / **محاسبه‌نشده** — و «محاسبه‌نشده» مثل غایب می‌بندد
# (قانون ۱: دادهٔ ناموجود = NO_SIGNAL). تنها چیزی که عوض می‌شود این
# است که قیف **راستش را می‌گوید**: تا امروز «شاهد غایب» گزارش می‌شد،
# در حالی که شاهد اصلاً حساب نشده بود. باز کردن این مسیر یعنی محاسبهٔ
# واقعی fvg/swept/choch در موتور — کارِ قانون ۰۳، نه این وصله.
COMPUTED = {
    # استراتژی → تأییدیه‌هایی که موتورش واقعاً حساب می‌کند
    "ibs": {"inOB", "choch", "quality>=70"},
    "smc": {"inOB", "swept", "fvg", "quality>=70"},
}
# نام‌های هم‌معنا روی خروجی ورکر (scan.py:176-177 از قبل همین را می‌داند)
ALIASES = {"inOB": ("inOB", "inside")}


def _opposes(t, direction):
    return (direction == "LONG" and t == "down") or \
           (direction == "SHORT" and t == "up")


def confirm(ev, need):
    """حالت یک تأییدیه: True حاضر · False غایب · None محاسبه‌نشده.

    «محاسبه‌نشده» با «غایب» یکی نیست — اولی یعنی نمی‌دانیم، دومی یعنی
    می‌دانیم که نیست. هر دو می‌بندند، ولی دلیلشان در قیف فرق می‌کند و
    فقط اولی «شکافِ موتور» است."""
    strat = ev.get("strategy")
    known = COMPUTED.get(strat)
    if known is not None and need not in known:
        return None
    if need == "quality>=70":
        q = ev.get("quality")
        return None if q is None else q >= 70
    for k in ALIASES.get(need, (need,)):
        if k in ev and ev[k] is not None:
            return bool(ev[k])
    return None if known is None else False


def counter_path_open(strategy):
    """آیا مسیر «خلاف روند با تأیید کامل» برای این استراتژی اصلاً باز است؟

    اگر موتور حتی یکی از تأییدیه‌های لازم را حساب نکند، مسیر بسته است و
    هر سیگنالِ خلاف روندِ آن استراتژی وتو می‌شود — فارغ از بازار. این
    را صریح برمی‌گردانیم تا در گزارش دیده شود، نه این‌که سال‌ها بی‌صدا
    بماند."""
    known = COMPUTED.get(strategy)
    if known is None:
        return True, []
    gap = [n for n in COUNTER_NEEDS if n not in known]
    return (not gap), gap


def assess(sym, direction, kget, evidence=None):
    """kget(sym, tf, n) -> کندل‌ها. خروجی همیشه دلیل نوشته دارد.

    ok=False یعنی ارسال ممنوع — بی‌استثنا (دستور: عدم تأیید = بدون سیگنال).
    """
    ev = evidence or {}
    out = dict(sym=sym, dir=direction, t4=None, t1=None,
               mode="with-trend", ok=True, missing=[], reason="")
    try:
        c4 = kget(sym, "4h", _TF_N)
        c1 = kget(sym, "1h", _TF_N)
    except Exception as e:                           # noqa: BLE001
        out.update(ok=False, mode="no-data",
                   reason=f"روند ۴س/۱س خواندنی نیست ({type(e).__name__}) — "
                          "دادهٔ ناقص = NO_SIGNAL (قانون ۱)")
        return out
    if len(c4) < 60 or len(c1) < 60:
        out.update(ok=False, mode="no-data",
                   reason="کندل کافی برای حکم روند نیست — NO_SIGNAL")
        return out
    t4, t1 = trend(c4), trend(c1)
    out.update(t4=t4, t1=t1)

    opp4, opp1 = _opposes(t4, direction), _opposes(t1, direction)
    if opp4 and opp1:
        out.update(ok=False, mode="hard-veto",
                   reason=f"هر دو تایم بالا خلاف {direction} است "
                          f"(۴س={t4}، ۱س={t1}) — وتوی مطلق؛ تایم پایین حق "
                          "نقض ساختار بالا را ندارد (قانون ۲)")
        return out
    if opp4 or opp1:
        have, absent, uncomputed = [], [], []
        for need in COUNTER_NEEDS:
            st = confirm(ev, need)
            (have if st is True else absent if st is False
             else uncomputed).append(need)
        missing = absent + uncomputed
        if missing:
            why = []
            if absent:
                why.append("غایب: " + ", ".join(absent))
            if uncomputed:
                # این نیمه، شکافِ موتور است نه حکمِ بازار — و تا امروز
                # به‌دروغ «غایب» گزارش می‌شد.
                why.append("محاسبه‌نشده: " + ", ".join(uncomputed))
            out.update(ok=False, mode="counter-blocked", missing=missing,
                       absent=absent, uncomputed=uncomputed,
                       reason=f"خلاف روند {'۴س' if opp4 else '۱س'} "
                              f"({t4 if opp4 else t1}) و تأییدیه ناقص است — "
                              f"{' · '.join(why)} → NO_SIGNAL "
                              "(قانون: خلاف روند فقط با تمام تأییدیه‌ها؛ "
                              "شاهدِ محاسبه‌نشده = دادهٔ ناموجود، قانون ۱)")
        else:
            out.update(mode="counter-confirmed",
                       reason=f"خلاف روند {'۴س' if opp4 else '۱س'} ولی هر "
                              f"{len(COUNTER_NEEDS)} تأییدیه کامل است — عبور "
                              "با برچسب خلاف روند")
        return out
    out["reason"] = f"هم‌راستا (۴س={t4}، ۱س={t1})"
    return out


def caption_line(a):
    """خط کپشن — فقط برای عبورِ خلاف روند؛ قانون ۲ حمید: بدون توضیح ناقص است."""
    if a.get("mode") != "counter-confirmed":
        return None
    return (f"⚠️ خلاف روند (۴س={a['t4']}، ۱س={a['t1']}) — مجاز چون تمام "
            f"تأییدیه‌ها کامل بود: {'، '.join(COUNTER_NEEDS)}")
