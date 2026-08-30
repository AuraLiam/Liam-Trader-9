"""پاسبان آزمایشگاه شورت.

سه چیزی که قفل می‌شود — هر سه، درسِ همین شب:

۱. **نمونه از همهٔ دفترها جمع شود.** دفتر ارسالی فقط ۸۳ شورت دارد؛ با
   انحراف معیار ~۱.۰R برای نیم‌پهنای ۰.۱R حدود ۴۲۰ نمونه لازم است. اگر
   کسی دوباره فقط دفتر ارسالی را نگاه کند، حکمی می‌سازد که نمونه‌اش
   کفاف نمی‌دهد.
۲. **همه‌چیز بر حسب فاصلهٔ استاپ تفکیک شود.** چون سهم کارمزد از R برابر
   `کارمزد٪ ÷ استاپ٪` است، مقایسهٔ بدونِ تفکیکِ هندسه بی‌معناست — همان
   پارادوکس سیمپسونی که گزارش دیشب را باطل کرد.
۳. **گزارش هر دو جهت را بدهد.** ادعای «شورت بد است» فقط با دیدنِ لانگ
   در همان باند معنا دارد. اندازه‌گیری ۳۰ اوت: در هر چهار باند، اختلافِ
   جهت صفر را در بر می‌گیرد — و در سه باند از چهار، شورت **بهتر** است.
"""
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import short_lab as L                              # noqa: E402

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


def run():
    # ── ۱) برآورد اندازهٔ نمونه ────────────────────────────────────────
    xs = [1.0, -1.0] * 50                       # انحراف معیار ~۱.۰
    n = L.need_n(xs, 0.10)
    check("برآورد n با فرمول (۱.۹۶σ/نیم‌پهنا)² است",
          abs(n - round((1.96 * statistics.stdev(xs) / 0.10) ** 2)) <= 1, str(n))
    check("نیم‌پهنای کوچک‌تر، n بزرگ‌تر می‌خواهد",
          L.need_n(xs, 0.05) > L.need_n(xs, 0.10))
    check("نمونهٔ کم، برآورد نمی‌دهد (حدس نمی‌زند)",
          L.need_n([1.0]) is None)

    # ── ۲) استخر باید از همهٔ دفترها باشد ─────────────────────────────
    sh = L.pool()
    lo = L.pool(("LONG",))
    check("استخر شورت ساخته شد", len(sh) > 0, str(len(sh)))
    check("و از دفتر ارسالی بزرگ‌تر است (کلِ حرفِ این فایل)",
          len(sh) > 300, str(len(sh)))
    names = {r["_ledger"] for r in sh}
    check("همهٔ دفترهای فهرست، در استخر هستند",
          names >= {n for _, n in L.LEDGERS if n != "پولبک ۲"}, str(names))
    check("هر ردیف برچسب دفترش را دارد",
          all(r.get("_ledger") for r in sh))
    check("استخر جهت را رعایت می‌کند",
          all(r["dir"] == "SHORT" for r in sh)
          and all(r["dir"] == "LONG" for r in lo))
    check("لانگ هم استخر دارد (مقایسه بدون طرف مقابل بی‌معناست)",
          len(lo) > 0, str(len(lo)))

    # ── ۳) کارمزد بازمحاسبه شده، نه از عددِ ذخیره‌شده ──────────────────
    with_fee = [r for r in sh if r.get("_fee_r") is not None]
    check("کارمزد روی هر ردیف بازمحاسبه شده",
          len(with_fee) > len(sh) * 0.9, f"{len(with_fee)}/{len(sh)}")
    moved = [r for r in with_fee
             if r.get("_R_net_stored") is not None
             and abs(r["R_net"] - r["_R_net_stored"]) > 1e-9]
    check("و با عددِ ذخیره‌شده فرق دارد (عیبِ دو ثابت کارمزد)",
          len(moved) > len(with_fee) * 0.5, f"{len(moved)}/{len(with_fee)}")
    check("جابه‌جایی در جهتِ بدتر است (کارمزدِ بیشتر، نه کمتر)",
          statistics.median([r["R_net"] - r["_R_net_stored"]
                             for r in moved]) < 0)

    # ── ۴) تفکیک هندسه اجباری است ─────────────────────────────────────
    banded = [r for r in sh if L.band(r) is not None]
    check("اکثر ردیف‌ها باند استاپ می‌گیرند",
          len(banded) > len(sh) * 0.9, f"{len(banded)}/{len(sh)}")
    fees_by_band = {}
    for b_lo, b_hi in L.STOP_BANDS:
        g = [r["_fee_r"] for r in sh
             if r["_stop_pct"] is not None and b_lo <= r["_stop_pct"] < b_hi
             and r.get("_fee_r") is not None]
        if len(g) >= 5:
            fees_by_band[(b_lo, b_hi)] = statistics.mean(g)
    check("کارمزد با گشادشدنِ استاپ یکنواخت کم می‌شود "
          "(کارمزد٪÷استاپ٪ — نه سهمی ثابت)",
          list(fees_by_band.values()) == sorted(fees_by_band.values(),
                                                reverse=True),
          str({f"{a}-{b}": round(v, 3) for (a, b), v in fees_by_band.items()}))

    # ── ۵) گزارش باید هر دو جهت و هر دو معیار را چاپ کند ──────────────
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        L.main([])
    out = buf.getvalue()
    for must, why in (
            ("همان تفکیک برای لانگ", "طرف مقابل"),
            ("اختلاف جهت، داخل هر باند استاپ", "آزمون دونمونه‌ای"),
            ("ناخالص در برابر خالص", "جای لبه در برابر جای کارمزد"),
            ("چقدر نمونه لازم است", "کفایت نمونه"),
            ("مرز صادقانه", "قانون ۱۲")):
        check(f"گزارش «{must}» را دارد ({why})", must in out, out[:120])
    check("گزارش می‌گوید خالص بازمحاسبه شده",
          "بازمحاسبه" in out)
    check("گزارش نمادهای سازندهٔ نمونه را نام می‌برد",
          "نمادهایی که سطلِ شورت را می‌سازند" in out)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
