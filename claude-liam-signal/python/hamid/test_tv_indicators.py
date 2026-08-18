"""آزمون اندیکاتورهای سنجشی — EMA200 / Supertrend / ICT، بدون حدس روی دادهٔ کم."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import tv_indicators as tv                         # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def candles(path):
    return [{"t": i * 900000, "o": p, "h": p * 1.002, "l": p * 0.998,
             "c": p, "v": 1.0} for i, p in enumerate(path)]


def run():
    up = candles([100 + i * 0.3 for i in range(260)])
    dn = candles([200 - i * 0.3 for i in range(260)])

    # EMA
    check("EMA با دادهٔ کم = None", tv.ema([1, 2, 3], 200) is None)
    e = tv.ema([k["c"] for k in up], 200)
    check("EMA200 روی روند صعودی زیر قیمت است",
          e is not None and e < up[-1]["c"])

    # Supertrend
    check("سوپرترند روند صعودی = up", tv.supertrend(up) == "up")
    check("سوپرترند روند نزولی = down", tv.supertrend(dn) == "down")
    check("سوپرترند دادهٔ کم = None", tv.supertrend(candles([1, 2, 3])) is None)

    # snapshot — هم‌جهتی‌ها
    s = tv.snapshot(up, "LONG")
    check("لانگ در روند صعودی: EMA200 و سوپرترند هم‌جهت",
          s["ema200_align"] == "with" and s["supertrend_align"] == "with",
          str(s))
    s2 = tv.snapshot(up, "SHORT")
    check("شورت در روند صعودی: هر دو خلاف",
          s2["ema200_align"] == "against" and s2["supertrend_align"] == "against")
    s3 = tv.snapshot(candles([100] * 50), "LONG")
    check("دادهٔ کم: EMA200 حدس نمی‌زند", s3["ema200_align"] is None)

    # ICT: سناریوی دستی — سوییپ کف + displacement صعودی + FVG صعودی
    base = [100.0] * 80
    path = base + [99.2, 99.0] + [101.5] + [102.6] + [103.0, 103.2, 103.4]
    cd = candles(path)
    # سوییپ: کندل 99.0 زیر کف‌ها ویک زده و بعدی بالای آن کلوز کرده؛
    # displacement: پرش 99→101.5 بدنهٔ بزرگ؛ FVG: گپ بین سقف 99.0 و کف 102.6
    cd[81]["l"], cd[81]["c"] = 98.5, 99.0
    cd[82]["o"], cd[82]["c"] = 99.0, 101.5
    a = tv.ict_align(cd, "LONG")
    check("سناریوی ICT صعودی → with", a == "with", str(tv._ict_parts(cd, "LONG")))
    check("همان سناریو برای شورت → against یا None",
          tv.ict_align(cd, "SHORT") in ("against", None))
    check("دادهٔ کم ICT = None", tv.ict_align(candles([1] * 10), "LONG") is None)

    print(f"\n✓ همهٔ {OK} آزمون اندیکاتورهای سنجشی گذشت")


if __name__ == "__main__":
    run()
