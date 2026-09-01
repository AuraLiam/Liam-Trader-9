"""پاسبان رادار گینر — دو راهِ خراب‌شدن، هر دو قفل.

۱. **اسپم**: ارزی که سه روز در گینرهاست هر ۱۵ دقیقه پیام بدهد. دستور
   صریح حمید: «همان گزارش اولیه کافی است». اگر این بشکند، حمید ۹۶ پیام
   در روز می‌گیرد و بعد کلاً پیام‌ها را نادیده می‌گیرد — همان چیزی که
   قانون ۰۷ از ۲۳ اوت می‌جنگد.
۲. **حدس‌زدن**: بدون OI نمی‌شود پول‌تازه را از شورت‌اسکوئیز جدا کرد. اگر
   ماژول در نبودِ OI حدس بزند، همان لحظه قانون ۰۱ بند ۱ را شکسته و
   حمید روی عددی تصمیم می‌گیرد که هیچ‌کس اندازه‌اش نگرفته.

روی دادهٔ **ساختگی** سنجیده می‌شود تا با عوض‌شدن بازار بی‌معنا نشود.

اجرا: `python3 -m hamid.test_gainer_radar`
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import gainer_radar as G                             # noqa: E402

OK = 0
FAIL = []
H = 3_600_000


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


def run():
    # ── ۱) تفکیکِ چهارگانه — همان کاری که حمید روی ARB دستی کرد ────────
    check("قیمت ↑ و OI ↑ → پول تازه",
          G.classify(18.0, 18.6)[0] == "NEW_MONEY")
    check("قیمت ↑ و OI ↓ → شورت‌اسکوئیز",
          G.classify(18.0, -5.0)[0] == "SHORT_SQUEEZE")
    check("قیمت ↓ و OI ↑ → توزیع",
          G.classify(-3.0, 12.0)[0] == "DISTRIBUTION")
    check("قیمت ↓ و OI ↓ → بستنِ لانگ",
          G.classify(-3.0, -12.0)[0] == "LONG_UNWIND")

    # ── ۲) حدس ممنوع (قانون ۰۱ بند ۱) ─────────────────────────────────
    st, why = G.classify(18.0, None)
    check("بدون OI حدس زده نمی‌شود", st == "UNKNOWN_OI")
    check("و دلیلِ نامعلومی صریح نوشته می‌شود", "نامعلوم" in why)
    check("بدون تغییر قیمت هم حدس زده نمی‌شود",
          G.classify(None, 5.0)[0] == "UNKNOWN")

    # ── ۳) ضداسپم — قلبِ دستور حمید ────────────────────────────────────
    seen = {"ARBUSDT": {"at": 1000, "state": "NEW_MONEY", "chg": 18.0}}
    now = 1000 + 3 * H
    check("همان ارز با همان حالت دوباره گزارش نمی‌شود",
          G.should_report("ARBUSDT", "NEW_MONEY", 18.4, seen, now)[0] is False)
    check("حتی با تغییرِ کمی بیشتر هم ساکت می‌ماند",
          G.should_report("ARBUSDT", "NEW_MONEY", 22.0, seen, now)[0] is False,
          "۲۲ از ۱.۵×۱۸=۲۷ کمتر است")
    check("ولی عوض‌شدنِ حالت خبرِ واقعی است",
          G.should_report("ARBUSDT", "SHORT_SQUEEZE", 18.4, seen, now)[0])
    check("و جهشِ ≥۱.۵ برابر هم خبر است",
          G.should_report("ARBUSDT", "NEW_MONEY", 28.0, seen, now)[0])
    check("ارزِ تازه همیشه گزارش می‌شود",
          G.should_report("GMXUSDT", "NEW_MONEY", 9.0, seen, now)[0])
    check(f"بعد از {G.SEEN_TTL_H} ساعت سکوت، دوباره تازه است",
          G.should_report("ARBUSDT", "NEW_MONEY", 18.4, seen,
                          1000 + (G.SEEN_TTL_H + 1) * H)[0])

    # ── ۴) دفترِ دیده‌ها مرجعش را نمی‌لغزاند ────────────────────────────
    #
    # اگر `chg` مرجع در هر دیدن به‌روز می‌شد، شرطِ «جهش ۱.۵×» هرگز فعال
    # نمی‌شد: هر بار کمی بالاتر، و مرجع هم با آن بالا می‌رفت. مرجع باید
    # آخرینِ **گزارش‌شده** بماند.
    tmp = Path(tempfile.mkdtemp()) / "seen.json"
    old_seen = G.SEEN
    G.SEEN = tmp
    try:
        res = {"generated": 5000, "candidates": [
            {"sym": "AAAUSDT", "state": "NEW_MONEY", "chg_pct": 20.0,
             "oi": 100.0, "report": True},
            {"sym": "BBBUSDT", "state": "NEW_MONEY", "chg_pct": 9.0,
             "oi": 50.0, "report": False},
        ]}
        s1 = G.remember(res)
        check("ارزِ گزارش‌شده مرجعش ثبت می‌شود",
              s1["AAAUSDT"]["chg"] == 20.0 and s1["AAAUSDT"]["at"] == 5000)
        check("ارزِ ساکت مرجعِ گزارش نمی‌گیرد (وگرنه ضداسپم خبر را هم می‌بلعد)",
              "chg" not in s1["BBBUSDT"] and "at" not in s1["BBBUSDT"],
              str(s1["BBBUSDT"]))
        check("ولی OI ارزِ ساکت تازه می‌شود (مبنای دلتای بعدی)",
              s1["BBBUSDT"]["oi"] == 50.0)
        res2 = {"generated": 6000, "candidates": [
            {"sym": "AAAUSDT", "state": "NEW_MONEY", "chg_pct": 24.0,
             "oi": 110.0, "report": False}]}
        s2 = G.remember(res2)
        check("دیدنِ بی‌گزارش، مرجعِ ۲۰٪ را نمی‌لغزاند",
              s2["AAAUSDT"]["chg"] == 20.0, str(s2["AAAUSDT"]))
    finally:
        G.SEEN = old_seen

    # ── ۵) پارس مقاوم: شکلِ ناشناس عدد نمی‌سازد ────────────────────────
    check("بدنهٔ ناشناس ردیف نمی‌سازد", G._rows({"data": "چیزی"}) == []
          and G._rows(None) == [])
    check("data.list هم پذیرفته می‌شود",
          G._rows({"data": {"list": [{"symbol": "X"}]}}) == [{"symbol": "X"}])
    check("نسبت به درصد تبدیل می‌شود",
          abs(G._chg({"change": 0.186}) - 18.6) < 1e-6)
    check("و درصدِ خام دوباره ضرب نمی‌شود",
          abs(G._chg({"change": 18.6}) - 18.6) < 1e-6)
    check("میدانِ ناموجود None می‌دهد نه صفر", G._chg({"x": 1}) is None)

    # ── ۶) مرزها ───────────────────────────────────────────────────────
    src = (PY / "hamid" / "gainer_radar.py").read_text(encoding="utf-8")
    check("از دروازهٔ آلارم رد می‌شود، نه مستقیم به تلگرام (قانون ۰۷)",
          "alert_gate.send" in src and "tg.send_text" not in src)
    check("پیام امضای پنل دارد (دستور ۱۶ اوت)", "PANEL_NAME" in src)
    check("پیام صریح می‌گوید آلارم است نه سیگنال",
          "آلارم است نه سیگنال" in src)
    check("عددِ سنجیده‌شدهٔ چسبندگی در پیام هست (ادعای بی‌عدد ممنوع)",
          "۱.۰۴" in src)
    check("ماژول سیگنال صادر نمی‌کند",
          "send_signals" not in src and "paper.open_from" not in src)
    check("فقط خروجی خودش را می‌نویسد (قانون ۰۵)",
          src.count("write_text") == 2, "gainer-radar.json + gainer-seen.json")

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
