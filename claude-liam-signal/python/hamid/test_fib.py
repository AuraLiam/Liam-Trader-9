"""آزمون اندازه‌گیری فیبوناچی روی پولبک — فقط ثبت، بدون ورود به تصمیم."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import premortem as pm                             # noqa: E402
from hamid import paper as pp                                 # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def candles(path):
    """path: لیست قیمت کلوز؛ کندل ساده حولش می‌سازیم."""
    return [{"t": i * 900000, "o": p, "h": p * 1.001, "l": p * 0.999,
             "c": p, "v": 1.0} for i, p in enumerate(path)]


def run():
    # موج صعودی 100→110 سپس پولبک به 105 → نسبت ~0.5 (ناحیهٔ طلایی)
    up = [100 + i * 0.5 for i in range(21)]          # 100 → 110
    pull = [110 - i * 0.5 for i in range(11)]        # 110 → 105
    c = candles([100] * 10 + up + pull)
    r = pm.fib_ratio(c, "LONG")
    check("لانگ: پولبک نیمهٔ موج ≈ ۰.۵", r is not None and 0.45 <= r <= 0.56,
          str(r))

    # قرینهٔ شورت: ریزش 110→100 سپس پولبک به 106.18 → ~0.618
    dn = [110 - i * 0.5 for i in range(21)]
    pb = [100 + i * 0.618 for i in range(11)]
    c2 = candles([110] * 10 + dn + pb)
    r2 = pm.fib_ratio(c2, "SHORT")
    check("شورت: پولبک ~۰.۶ موج", r2 is not None and 0.55 <= r2 <= 0.68,
          str(r2))

    # دادهٔ کوتاه یا بی‌موج → None، نه عدد جعلی
    check("دادهٔ کوتاه = None", pm.fib_ratio(candles([100] * 10), "LONG") is None)
    flat = candles([100.0] * 60)
    check("بازار بی‌موج = None (سقف=کف)", pm.fib_ratio(flat, "LONG") is None)

    # خروجی review فیلد fib دارد (ثبت روی پرونده)
    rv = pm.review({"sym": "TUSDT", "dir": "LONG", "entry": 105.0,
                    "sl": 103.0, "tp1": 112.0}, c)
    check("review فیلد fib برمی‌گرداند", "fib" in rv, str(rv.keys()))

    # شرط‌های بونفرونی None-بردبارند (ردیف‌های قدیمی fib ندارند)
    conds = {n: fn for n, fn in pp.CONDITIONS}
    g = conds["پولبک در ناحیهٔ طلایی فیبو (۰.۵–۰.۷۰۵)"]
    s = conds["پولبک کم‌عمق فیبو (<۰.۳۸)"]
    check("شرط طلایی: ۰.۶ → بله، None → خیر",
          g({"fib_ratio": 0.6}) and not g({}) and not g({"fib_ratio": None}))
    check("شرط کم‌عمق: ۰.۲ → بله، ۰.۵ → خیر",
          s({"fib_ratio": 0.2}) and not s({"fib_ratio": 0.5}) and not s({}))

    print(f"\n✓ همهٔ {OK} آزمون فیبوناچی گذشت")


if __name__ == "__main__":
    run()
