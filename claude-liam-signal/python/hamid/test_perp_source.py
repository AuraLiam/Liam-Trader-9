"""پاسبان منبع قرارداد دائمی — دستور حمید ۳۱ اوت («ارز را پرپچوال انتخاب کن»).

عیبی که ممیزی یافت: کل تحلیل زنده روی کندل **اسپات** بود در حالی که
اجرا روی فیوچرز است. نامرئی مانده بود چون شکل کندل فیوچرز بایننس با
اسپات مو‌به‌مو یکی است.

سه چیزی که قفل می‌شود:
۱. مسیر پرپ واقعاً به میزبان قرارداد دائمی می‌رود (نه v3 اسپات).
۲. پارسرها بدون شبکه، روی پاسخِ ضبط‌شده، شکل بایننسی درست می‌دهند.
۳. مرزِ «سوییچ تصمیم حمید است» در کد نوشته می‌ماند — و مقایسه هرگز
   دو منبع را با هم قاطی نمی‌کند (تطبیق فقط بر مهر زمان).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
import sources                                                # noqa: E402
from hamid import perp_vs_spot as P                           # noqa: E402

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
    ids = [v["id"] for v in sources.PERP_VENUES]
    check("دست‌کم دو صرافی پرپ ثبت شده", len(ids) >= 2, str(ids))
    urls = [v["url"]("BTCUSDT", "15m", 100) for v in sources.PERP_VENUES]
    check("هیچ‌کدام به مسیر اسپات (api/v3/klines) نمی‌روند",
          not any("/api/v3/klines" in u for u in urls), str(urls))
    check("بایننس‌پرپ به میزبان فیوچرز می‌رود",
          any("fapi.binance.com" in u for u in urls), str(urls))
    check("MEXC پرپ به میزبان قرارداد می‌رود و نماد را _USDT می‌کند",
          any("contract.mexc.com" in u and "BTC_USDT" in u for u in urls), str(urls))

    rows = sources._binance_perp([[1788000000000, "10", "11.5", "9.5", "11", "100", 0]])
    check("پارسر بایننس‌پرپ شکل بایننسی می‌دهد",
          rows[0][:6] == [1788000000000, 10.0, 11.5, 9.5, 11.0, 100.0], str(rows))
    m = sources._mexc_perp({"data": {"time": [1788000000], "open": [10],
                                     "close": [11], "high": [11.5],
                                     "low": [9.5], "vol": [100]}})
    check("پارسر MEXC پرپ ثانیه را به میلی‌ثانیه می‌برد",
          m[0][0] == 1788000000000, str(m))
    check("و ترتیب o/h/l/c را جابه‌جا نمی‌کند",
          m[0][1:5] == [10.0, 11.5, 9.5, 11.0], str(m))
    check("MEXC پرپ بدون حجم هم می‌شکند نه دروغ می‌گوید",
          sources._mexc_perp({"data": {"time": [1], "open": [1], "close": [1],
                                       "high": [1], "low": [1]}})[0][5] == 0.0)

    def spot(s, tf, n):
        return [[1788000000000 + i * 900000, 100 + i, 101 + i, 99 + i,
                 100.5 + i, 10, 0] for i in range(60)]

    def perp(s, tf, n):
        return [[1788000000000 + i * 900000, 100.2 + i, 101.4 + i, 98.9 + i,
                 100.7 + i, 10, 0] for i in range(60)]

    c = P.compare("BTCUSDT", "15m", 60, spot_fn=spot, perp_fn=perp)
    check("مقایسه روی کندل‌های هم‌زمان اجرا می‌شود", c["ok"] and c["bars"] == 60)
    check("basis اندازه گرفته می‌شود", c["basis_med_pct"] > 0)
    check("نسبت دامنه اندازه گرفته می‌شود", c["range_ratio"] > 1)
    check("جابه‌جایی سقف/کف اندازه گرفته می‌شود",
          c["swing_high_gap_pct"] > 0 and c["swing_low_gap_pct"] > 0)

    # مهر زمانِ ناهم‌راستا: باید رد شود، نه اینکه ردیف‌ها را کورکورانه جفت کند
    def shifted(s, tf, n):
        return [[1788000000000 + 7 * 60000 + i * 900000, 100, 101, 99, 100.5,
                 10, 0] for i in range(60)]
    c2 = P.compare("BTCUSDT", "15m", 60, spot_fn=spot, perp_fn=shifted)
    check("کندلِ ناهم‌زمان جفت نمی‌شود (تطبیق بر مهر زمان)",
          c2["ok"] is False and "هم‌زمان" in c2["why"], str(c2))
    c3 = P.compare("XUSDT", "15m", 60, spot_fn=spot,
                   perp_fn=lambda *a: (_ for _ in ()).throw(RuntimeError()))
    check("نمادِ بدونِ پرپ صریح اعلام می‌شود نه بی‌صدا حذف",
          c3["ok"] is False and "پرپ" in c3["why"], str(c3))

    v = P.verdict(P.summarize([c]))
    check("حکم به مقیاسِ استاپِ خودمان گره خورده", "استاپِ میانه" in v, v)
    check("بی‌داده حکم نمی‌سازد", "حکمی نیست" in P.verdict({"n": 0}))

    src = (PY / "sources.py").read_text(encoding="utf-8")
    check("مرزِ «سوییچ تصمیم حمید است» در کد نوشته شده",
          "تصمیم صریح حمید است (قانون ۰۳)" in src)
    check("مسیر اسپات صریح برچسب خورده",
          "این مسیر **اسپات** است" in src)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
