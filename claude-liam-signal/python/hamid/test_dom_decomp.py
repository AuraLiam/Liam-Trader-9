"""پاسبان تجزیهٔ دامیننس تتر — صورت در برابر مخرج (بند ۲، ۲۹ اوت).

چیزی که این آزمون نگه می‌دارد: **یک عدد، دو معنیِ متضاد.** اگر تجزیه
اشتباه کند، موتور «تترِ تازه mint شد» را «بازار ریخت» می‌خواند — و
تفسیرش دقیقاً برعکس واقعیت می‌شود.

سناریوها با عددِ دستی ساخته شده‌اند تا جوابِ درست از قبل معلوم باشد.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import dom_decomp as D                             # noqa: E402

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


def pts(pairs, step_min=5):
    """(دامیننس، کل بازار) → سری، آخرین نقطه = آخرین جفت."""
    n = len(pairs)
    return [{"t": (i - n + 1) * step_min * 60000 + 10**12,
             "u": u, "b": 56.0, "m": m} for i, (u, m) in enumerate(pairs)]


def run():
    T = 3.0e12                     # کل بازار پایه: ۳ تریلیون دلار

    # ── ۱) تترِ تازه: عرضه بالا، کل بازار ثابت ────────────────────────────
    # D از ۵٪ به ۵.۵٪ فقط چون S از ۱۵۰ به ۱۶۵ میلیارد رفته
    s = pts([(5.0, T)] * 48 + [(5.5, T * 1.005)])
    d = D.decompose(s, 240)
    check("تجزیه با دادهٔ کافی اجرا می‌شود", d["status"] == "OK", str(d)[:200])
    check("mint تازه = SUPPLY_DRIVEN (نه «بازار ریخت»)",
          d["label"] == "SUPPLY_DRIVEN", str(d)[:260])
    check("و تفسیرش صریح می‌گوید این ریزش نیست",
          "ریزش نیست" in d["story"], d["story"])
    check("سهم صورت غالب است", d["supply_share"] >= D.DOMINANT_SHARE,
          str(d["supply_share"]))

    # ── ۲) ریزش بازار: عرضه ثابت، کل بازار پایین ─────────────────────────
    # S ثابت ۱۵۰ میلیارد؛ T از ۳ به ۲.۷ تریلیون → D از ۵٪ به ۵.۵۵٪
    s2 = pts([(5.0, T)] * 48 + [(round(100 * 0.15e12 / (T * 0.9), 3), T * 0.9)])
    d2 = D.decompose(s2, 240)
    check("ریزش بازار = MARKET_DRIVEN", d2["label"] == "MARKET_DRIVEN",
          str(d2)[:260])
    check("و تفسیرش «ریزشِ واقعی» را نام می‌برد",
          "ریزشِ واقعی" in d2["story"], d2["story"])

    # ── ۳) دقتِ ریاضی: جمعِ دو اثر باید دقیقاً برابر تغییر نسبت باشد ──────
    for name, dd in (("mint", d), ("ریزش", d2)):
        gap = abs(dd["d_dom_pct"] - (dd["supply_effect_pct"]
                                     + dd["mcap_effect_pct"]))
        check(f"تجزیه در سناریوی «{name}» دقیق است (نه تقریبی)", gap < 0.01,
              f"اختلاف {gap}")

    # ── ۴) هر دو با هم = MIXED؛ تفسیر یک‌طرفه ممنوع ──────────────────────
    s3 = pts([(5.0, T)] * 48 + [(5.25, T * 0.98)])
    d3 = D.decompose(s3, 240)
    check("اثر هم‌زمانِ دو ریشه = MIXED", d3["label"] == "MIXED", str(d3)[:200])
    check("و صریح می‌گوید تفسیر یک‌طرفه ممنوع است",
          "یک‌طرفه" in d3["story"], d3["story"])

    # ── ۵) بی‌حرکت = FLAT، نه داستان‌سازی ────────────────────────────────
    s4 = pts([(5.0, T)] * 49)
    d4 = D.decompose(s4, 240)
    check("بازهٔ بی‌تکان = FLAT", d4["label"] == "FLAT", str(d4)[:200])
    check("و خطِ کپشن برای FLAT ساخته نمی‌شود", D.line(d4) is None)

    # ── ۶) دادهٔ ناقص = INSUFFICIENT، نه عددِ ساختگی (قانون ۱) ────────────
    old = [{"t": i * 300000, "u": 5.0, "b": 56.0} for i in range(60)]
    check("سری بدون کل بازار = INSUFFICIENT",
          D.decompose(old, 240)["status"] == "INSUFFICIENT")
    check("و دلیلِ نبودن نوشته می‌شود، نه حذفِ بی‌صدا",
          "why" in D.decompose(old, 240))
    short = pts([(5.0, T)] * 3)
    check("نقطهٔ بازهٔ گذشته نباشد = INSUFFICIENT",
          D.decompose(short, 1440)["status"] == "INSUFFICIENT")

    # ── ۷) خط کپشن و خلاصهٔ چندبازه‌ای ───────────────────────────────────
    ln = D.line(d)
    check("خط کپشن هر دو اثر را با عدد می‌گوید",
          ln and "عرضه" in ln and "کل بازار" in ln and "٪" in ln, str(ln))
    sm = D.summary(s)
    check("خلاصه روی سه بازه حساب می‌شود",
          set(sm) == {"60m", "240m", "1440m"}, str(list(sm)))

    # ── ۸) مرز صادقانه روی خودِ خروجی است (قانون ۱۲) ─────────────────────
    check("مرز صادقانه روی خروجی نوشته شده",
          "شاهد است نه دروازه" in d["limit"], d["limit"])

    # ── ۹) اتاق دامیننس واقعاً مخرج را ذخیره می‌کند ──────────────────────
    src = (HERE / "dominance.py").read_text(encoding="utf-8")
    check("سری، کل ارزش بازار را ذخیره می‌کند (وگرنه تجزیه ابدی خالی است)",
          '_pt["m"] = mcap' in src)
    check("تجزیه به خروجی اتاق وصل است", '"decomposition": decomp' in src)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
