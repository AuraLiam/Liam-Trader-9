"""بلوک سفارشِ آماده‌کپی — از همان سیگنالی که به تلگرام می‌رود.

دستور حمید (۲۴ اوت): «از همین پوزیشن‌هایی که از تلگرام می‌فرستی برای
لیمیت گذاشتن هم می‌توانی استفاده کنی.» یعنی پیام تلگرام باید بدون هیچ
حساب‌کردنِ دستی قابل تبدیل به سفارش باشد: قیمت لیمیت، استاپ، تارگت،
اهرم، حالت مارجین و سهم مارجین.

سه قید که این فایل را از یک «قالب چاپ» جدا می‌کند:

۱. **هیچ عددی این‌جا دوباره تعریف نمی‌شود.** اهرم و سهم مارجین از
   `liam9_strategy` (همان فایلی که حمید در داشبورد می‌گذارد) وارد
   می‌شوند. دلیلش درسِ ۲۳ اوت است: عددی که در دو جا نوشته شود، یکی‌اش
   کهنه می‌ماند. اگر آن فایل قابل import نبود، بلوک **چاپ نمی‌شود** —
   عددِ حدسی بدتر از نبودِ بلوک است (قانون ۱).
۲. **ورودیِ ناسالم = بلوکِ نرفته، نه بلوکِ غلط.** استاپ سمت اشتباه،
   تارگت سمت اشتباه، استاپ صفر، اهرمِ ردشده از محافظ لیکویید، یا دام
   کارمزد → `None`.
۳. **این اجرای زنده نیست.** خروجی فقط متن است؛ هیچ سفارشی جایی ثبت
   نمی‌شود. `LIVE_EXECUTION=false` دست‌نخورده می‌ماند
   (`.claude/rules/05-security-live-execution-disabled.md`).

موجودی حساب: فقط از `LIAM9_BALANCE_USDT` خوانده می‌شود. نبودش یعنی
درصدها چاپ می‌شوند و عدد دلاری چاپ نمی‌شود — موجودیِ فرضی، عددِ ساختگی
است.
"""
import os
import sys
from pathlib import Path

_PY = Path(__file__).resolve().parent.parent
if str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

try:                                    # noqa: SIM105
    import liam9_strategy as ST
except Exception:                       # pragma: no cover - محیط ناقص
    ST = None

# سقف هم‌زمانی از همان فایل می‌آید؛ این‌جا فقط برای پیام یادآوری می‌شود.
MARGIN_MODE = "isolated"                # کراس ممنوع — قرارداد اجرای ۲۰ اوت
ENTRY_ZONE_MULT = 0.35                  # قانون ۱۰: ورود ± ۰.۳۵×ریسک


def balance_usdt():
    """موجودی مارجین فیوچرز از محیط، یا None. هرگز مقدار پیش‌فرض ندارد."""
    raw = os.getenv("LIAM9_BALANCE_USDT", "").strip()
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if v > 0 else None


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def ticket(s, balance=None):
    """سیگنال → دیکشنری سفارش، یا None وقتی چیزی سرِ جایش نیست.

    `s` همان دیکشنری سیگنالِ مسیر ارسال است: sym/dir/entry/sl/tp1 اجباری،
    tp2 و quality/conf اختیاری.
    """
    if ST is None:
        return None
    d = str(s.get("dir") or "").upper()
    if d not in ("LONG", "SHORT"):
        return None
    entry, sl = _num(s.get("entry")), _num(s.get("sl"))
    tp1, tp2 = _num(s.get("tp1")), _num(s.get("tp2"))
    if entry is None or sl is None or tp1 is None or entry <= 0:
        return None

    long_ = d == "LONG"
    risk = entry - sl if long_ else sl - entry
    if risk <= 0:                       # استاپ سمت اشتباه یا روی ورود
        return None
    if (tp1 <= entry) if long_ else (tp1 >= entry):
        return None                     # تارگت سمت اشتباه
    if tp2 is not None and ((tp2 <= tp1) if long_ else (tp2 >= tp1)):
        tp2 = None                      # تارگت۲ بی‌معنا → حذف، نه چاپِ غلط

    stop_pct = risk / entry * 100
    fee_rt = ST.SCALP["fee_round_trip_pct"]
    fee_r = (fee_rt / 100) * entry / risk
    if fee_r >= ST.SCALP["max_fee_r"]:  # دام کارمزد — همان دروازهٔ استراتژی
        return None

    quality = s.get("quality")
    if quality is None:
        quality = s.get("conf")
    q = _num(quality)
    if q is None:
        return None                     # بدون کیفیت، اهرم قابل تعیین نیست
    lev = ST.suggest_leverage(stop_pct, q)
    if not lev:
        return None                     # محافظ لیکویید عبور نداد
    margin_pct = ST.margin_pct_for(q)

    zone = ENTRY_ZONE_MULT * risk
    t = {
        "sym": s.get("sym"),
        "side": "خرید/LONG" if long_ else "فروش/SHORT",
        "dir": d,
        "order_type": "limit",
        "margin_mode": MARGIN_MODE,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "leverage": lev,
        "liq_guard_max": int(ST.SCALP["liq_guard"] / stop_pct),
        "margin_pct": margin_pct,
        "stop_pct": round(stop_pct, 3),
        "fee_r": round(fee_r, 3),
        "entry_zone": [round(entry - zone, 10), round(entry + zone, 10)],
        "max_concurrent": ST.MAX_CONCURRENT,
        # ضررِ استاپ نسبت به مارجینِ همین پوزیشن — عددِ صادقانه‌ای که
        # حمید باید قبل از زدن دکمه ببیند، نه بعدش.
        "stop_loss_pct_of_margin": round(lev * stop_pct, 1),
    }
    bal = balance if balance is not None else balance_usdt()
    if bal:
        margin = bal * margin_pct / 100
        t["balance"] = bal
        t["margin_usdt"] = round(margin, 2)
        t["notional_usdt"] = round(margin * lev, 2)
        t["qty"] = round(margin * lev / entry, 8)
        t["risk_usdt"] = round(margin * lev * stop_pct / 100, 2)
    return t


def lines(t):
    """بلوک فارسیِ آماده‌کپی. ورودی خروجیِ ticket() است."""
    if not t:
        return []
    g = f"{t['entry']:.10g}"
    L = ["", "📋 <b>سفارش آماده (لیمیت)</b>",
         f"<code>{t['side']} · لیمیت {g} · اهرم {t['leverage']}x · "
         f"مارجین ایزوله</code>",
         f"<code>SL {t['sl']:.10g}</code>"
         + (f"  <code>TP1 {t['tp1']:.10g}</code>")
         + (f"  <code>TP2 {t['tp2']:.10g}</code>" if t.get("tp2") else "")]
    if t.get("margin_usdt") is not None:
        L.append(f"<code>مارجین {t['margin_usdt']:.10g}$ "
                 f"({t['margin_pct']}٪) · حجم {t['qty']:.10g} "
                 f"· ارزش {t['notional_usdt']:.10g}$</code>")
    else:
        L.append(f"<code>مارجین {t['margin_pct']}٪ از موجودی فیوچرز "
                 f"· سقف {t['max_concurrent']} پوزیشن هم‌زمان</code>")
    L.append(f"<i>استاپ {t['stop_pct']}٪ ⇒ خوردنش {t['stop_loss_pct_of_margin']}٪ "
             f"از مارجینِ همین پوزیشن · سقف اهرمِ محافظ لیکویید "
             f"{t['liq_guard_max']}x · کارمزد {t['fee_r']}R</i>")
    L.append(f"<i>فقط داخل ناحیهٔ <code>{t['entry_zone'][0]:.10g}</code>–"
             f"<code>{t['entry_zone'][1]:.10g}</code> معتبر است؛ بیرونش "
             f"EXPIRED — قیمت را تعقیب نکن.</i>")
    return L
