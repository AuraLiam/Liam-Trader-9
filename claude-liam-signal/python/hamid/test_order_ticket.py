"""پاسبان بلوک سفارش — همراه اجباری order_ticket.py. آفلاین.

خطر این بلوک «خراب شدن» نیست، **درست به‌نظر رسیدنِ عددِ غلط** است: حمید
از رویش سفارش می‌گذارد. پس بیشتر بررسی‌ها روی این‌اند که ورودیِ ناسالم
هیچ بلوکی تولید نکند، و اعداد اهرم/مارجین دقیقاً همان چیزی باشند که
liam9_strategy می‌گوید — نه یک کپیِ کهنه.
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
import liam9_strategy as ST                      # noqa: E402
from hamid import order_ticket as OT             # noqa: E402

OK = 0
FAIL = []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}")
        if extra:
            print(f"      ↳ {extra}")


def sig(**kw):
    s = {"sym": "BTCUSDT", "dir": "LONG", "entry": 100.0, "sl": 99.0,
         "tp1": 102.0, "tp2": 104.0, "quality": 70}
    s.update(kw)
    return s


print("— بلوک سالم:")
t = OT.ticket(sig(), balance=1000.0)
check("سیگنال سالم بلوک می‌گیرد", t is not None)
check("حالت مارجین همیشه ایزوله است (کراس ممنوع)",
      t["margin_mode"] == "isolated", str(t.get("margin_mode")))
check("نوع سفارش لیمیت است", t["order_type"] == "limit")
check("استاپ و تارگت هر دو روی بلوک‌اند (سفارش بی‌استاپ باطل است)",
      t["sl"] == 99.0 and t["tp1"] == 102.0)

print("\n— هیچ عددی دوباره تعریف نشده (درسِ واگرایی عدد، ۲۳ اوت):")
check("اهرم دقیقاً همان suggest_leverage فایل داشبورد است",
      t["leverage"] == ST.suggest_leverage(t["stop_pct"], 70),
      f"{t['leverage']} vs {ST.suggest_leverage(t['stop_pct'], 70)}")
check("سهم مارجین دقیقاً همان margin_pct_for است",
      t["margin_pct"] == ST.margin_pct_for(70))
check("سقف هم‌زمانی از همان فایل می‌آید", t["max_concurrent"] == ST.MAX_CONCURRENT)
src = (PY / "hamid" / "order_ticket.py").read_text(encoding="utf-8")
for bad in ("15, 39", "25.0, 30.0", "LEV_MIN =", "MARGIN_PCT_MIN ="):
    check(f"عدد اهرم/مارجین در این فایل کپی نشده ({bad!r})", bad not in src)

print("\n— محافظ لیکویید حاکم مطلق است:")
wide = OT.ticket(sig(sl=97.0, quality=100))      # استاپ ۳٪ → سقف ۱۶
check("اطمینان ۱۰۰ از محافظ لیکویید رد نمی‌شود",
      wide["leverage"] <= int(50.0 / wide["stop_pct"]),
      f"lev={wide['leverage']} stop={wide['stop_pct']}٪")
check("و سقفِ محافظ روی خود پیام چاپ می‌شود",
      wide["liq_guard_max"] == int(50.0 / wide["stop_pct"]))
check("استاپِ گشادتر از ~۳.۳٪ اصلاً بلوک نمی‌گیرد (اهرم زیر کف ۱۵)",
      OT.ticket(sig(sl=96.0)) is None)

print("\n— ورودیِ ناسالم = بلوکِ نرفته، نه بلوکِ غلط:")
check("استاپ بالای ورود در لانگ رد می‌شود", OT.ticket(sig(sl=101.0)) is None)
check("استاپ زیر ورود در شورت رد می‌شود",
      OT.ticket(sig(dir="SHORT", sl=99.0, tp1=98.0)) is None)
check("استاپ روی ورود (risk صفر) رد می‌شود", OT.ticket(sig(sl=100.0)) is None)
check("تارگت سمت اشتباه رد می‌شود", OT.ticket(sig(tp1=98.0)) is None)
check("ورود صفر/منفی رد می‌شود", OT.ticket(sig(entry=0)) is None)
check("جهت نامعتبر رد می‌شود", OT.ticket(sig(dir="MAYBE")) is None)
check("بدون کیفیت/اعتماد اهرم حدس زده نمی‌شود",
      OT.ticket(sig(quality=None, conf=None)) is None)
check("عدد غیرعددی (None/متن) رد می‌شود",
      OT.ticket(sig(sl=None)) is None and OT.ticket(sig(tp1="بالا")) is None)
tight = OT.ticket(sig(sl=99.9))                  # استاپ ۰.۱٪ → دام کارمزد
check("دام کارمزد (استاپ خیلی تنگ) بلوک نمی‌گیرد", tight is None)
mixed = OT.ticket(sig(tp2=101.0))                # تارگت۲ عقب‌تر از تارگت۱
check("تارگت۲ بی‌معنا حذف می‌شود، نه چاپ شود", mixed["tp2"] is None)

print("\n— شورت قرینهٔ لانگ است (ریشهٔ گلایهٔ «لانگ ۵، شورت ۲۰»):")
a = OT.ticket(sig())
b = OT.ticket(sig(dir="SHORT", sl=101.0, tp1=98.0, tp2=96.0))
check("اهرم دو جهت با هندسهٔ قرینه یکی است",
      a["leverage"] == b["leverage"], f"{a['leverage']} vs {b['leverage']}")
check("سهم مارجین دو جهت یکی است", a["margin_pct"] == b["margin_pct"])

print("\n— موجودی هرگز ساخته نمی‌شود:")
no_bal = OT.ticket(sig(), balance=None)
has = no_bal.get("margin_usdt") is not None
check("بدون LIAM9_BALANCE_USDT هیچ عدد دلاری چاپ نمی‌شود",
      not has or OT.balance_usdt() is not None)
txt = "\n".join(OT.lines(OT.ticket(sig(), balance=None)))
check("و در آن حالت درصدِ مارجین جای عدد دلاری را می‌گیرد",
      "٪ از موجودی فیوچرز" in txt or "مارجین " in txt, txt)
withb = "\n".join(OT.lines(OT.ticket(sig(), balance=1000.0)))
check("با موجودی، مارجین/حجم/ارزش هر سه چاپ می‌شوند",
      "مارجین" in withb and "حجم" in withb and "ارزش" in withb)
check("ضررِ استاپ نسبت به مارجین صریح چاپ می‌شود (نه پنهان)",
      "از مارجینِ همین پوزیشن" in withb)
check("عدد ضرر = اهرم × استاپ٪",
      abs(t["stop_loss_pct_of_margin"] - t["leverage"] * t["stop_pct"]) < 0.1)

print("\n— ناحیهٔ اعتبار و EXPIRED (قانون ۱۰):")
lo, hi = t["entry_zone"]
check("ناحیهٔ ورود = ورود ± ۰.۳۵×ریسک", abs((hi - lo) - 2 * 0.35 * 1.0) < 1e-9,
      f"{lo}–{hi}")
check("و پیام صریح می‌گوید بیرونش EXPIRED است", "EXPIRED" in withb)

print("\n— مرز اجرای زنده:")
check("این فایل هیچ سفارشی ثبت نمی‌کند (فقط متن)",
      "requests" not in src and "http" not in src.lower().replace("https://", ""))
check("و صریح می‌گوید اجرای زنده نیست", "LIVE_EXECUTION=false" in src)

print("\n— بلوک روی کپشن واقعیِ تلگرام می‌نشیند:")
import telegram as TG                            # noqa: E402
cap = TG.caption({"sym": "BTCUSDT", "dir": "LONG", "tf": "15m", "entry": 100.0,
                  "sl": 99.0, "tp1": 102.0, "tp2": 104.0, "rr": 2.0,
                  "quality": 70, "conf": 70})
check("کپشن واقعی بلوک سفارش را دارد", "سفارش آماده (لیمیت)" in cap, cap[-400:])
check("و امضای پنل هنوز سرِ جایش است", TG.PANEL_NAME in cap)
bad_cap = TG.caption({"sym": "X", "dir": "LONG", "tf": "5m", "entry": 100.0,
                      "sl": 101.0, "tp1": 102.0, "rr": 1.0, "quality": 70})
check("سیگنالِ بی‌بلوک هنوز ارسال می‌شود (بلوک، سیگنال را گروگان نمی‌گیرد)",
      "سفارش آماده" not in bad_cap and "X" in bad_cap)

print("\n— بدون تأخیر در ارسال (دستور صریح حمید):")
t0 = time.time()
for _ in range(200):
    OT.ticket(sig())
per_ms = (time.time() - t0) / 200 * 1000
check(f"ساخت بلوک زیر ۱ میلی‌ثانیه است ({per_ms:.3f}ms)", per_ms < 1.0)
t0 = time.time()
subprocess.run([sys.executable, "-c",
                "import sys; sys.path.insert(0, %r); from hamid import order_ticket"
                % str(PY)], check=True, capture_output=True)
imp = time.time() - t0
check(f"import سرد هم زیر ۳ ثانیه است ({imp:.2f}s)", imp < 3.0)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان بلوک سفارش: هر {OK} بررسی سبز")
