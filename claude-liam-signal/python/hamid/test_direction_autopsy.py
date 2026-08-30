"""پاسبان کالبدشکافی جهت — و قفلِ کلاسِ خطای «تک‌نمونه به‌جای دونمونه».

خطایی که ۳۰ اوت شب رخ داد: گزارش گفت «شورت تنها سطلی است که CI‌اش زیر
صفر است» و از آن نتیجه گرفت شورت بدتر از لانگ است. آزمونِ درست (اختلاف
دو گروه) هرگز اجرا نشده بود؛ وقتی اجرا شد، CI اختلاف **صفر را در بر
می‌گرفت**.

این آزمون سه چیز را قفل می‌کند:

۱. موتور **همیشه** آزمون دونمونه‌ای را کنار ادعای تک‌نمونه‌ای چاپ کند.
۲. مخدوش‌کننده کنترل شود (طبقه‌بندی بر استراتژی و بر باند استاپ).
۳. روی دادهٔ ساختگیِ سیمپسون — که در آن هیچ تفاوت جهتی وجود ندارد و
   تفاوتِ ظاهری فقط از ترکیب می‌آید — موتور باید **همان** را بگوید:
   اختلاف خام بزرگ، اختلاف طبقه‌بندی‌شده تقریباً صفر.

بند ۳ مهم‌ترین است: آزمونی که فقط روی دادهٔ واقعی سبز باشد، فردا با
عوض‌شدن دفتر بی‌معنا می‌شود. دادهٔ ساختگی، خودِ **روش** را می‌سنجد.
"""
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import direction_autopsy as A                     # noqa: E402

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


def simpson_rows():
    """دادهٔ ساختگی که در آن جهت هیچ اثری ندارد و ترکیب همه‌کاره است.

    دو استراتژی: `sig-tight` (زیانده، چون کارمزدش زیاد است) و `sig-wide`
    (سربه‌سر). داخل هر استراتژی، شورت و لانگ **دقیقاً یک توزیع** دارند.
    ولی شورت ۹۰٪ از استراتژی زیانده می‌آید و لانگ فقط ۱۰٪ — پس تجمعی،
    شورت بدتر به نظر می‌رسد بی‌آن‌که جهت هیچ نقشی داشته باشد."""
    rows = []

    def add(stage, d, n, mean, stop, seed):
        for i in range(n):
            # مقدارِ قطعی و پراکنده (بی‌تصادف، تا آزمون تکرارپذیر بماند)
            v = mean + ((i * 37 + seed) % 21 - 10) * 0.10
            rows.append({"sym": f"S{i%9}USDT", "dir": d, "R_net": v,
                         "R": v + 0.25, "fee_r": 0.25, "outcome": "trail",
                         "opened": 1_700_000_000_000 + i * 60_000,
                         "entry": 100.0, "sl": 100.0 + stop * (1 if d == "SHORT" else -1),
                         "_stage": stage, "_stop_pct": stop})
    # داخل هر استراتژی: میانگین دو جهت یکی است
    add("sig-tight", "SHORT", 90, -0.30, 0.35, 1)
    add("sig-tight", "LONG", 20, -0.30, 0.35, 2)
    add("sig-wide", "SHORT", 10, +0.10, 1.10, 3)
    add("sig-wide", "LONG", 90, +0.10, 1.10, 4)
    return rows


def run():
    # ── ۱) خودِ ابزارِ آماری ────────────────────────────────────────────
    a = [1.0, 2.0, 3.0, 4.0]
    b = [1.0, 2.0, 3.0, 4.0]
    ts = A.two_sample(a, b)
    check("اختلاف دو گروهِ یکسان صفر است", abs(ts["diff"]) < 1e-9, str(ts))
    check("و CI‌اش صفر را در بر می‌گیرد", ts["lo"] <= 0 <= ts["hi"])
    ts2 = A.two_sample([5.0, 6.0, 7.0, 8.0], b)
    check("اختلاف دو گروهِ جدا مثبت است", ts2["diff"] > 0, str(ts2["diff"]))
    check("نمونهٔ کم اختلاف نمی‌سازد", A.two_sample([1.0], b) is None)
    m, lo, hi, n = A.ci95([0.0, 0.0, 0.0, 0.0])
    check("واریانس صفر، بازهٔ صفر می‌دهد نه خطا", lo == hi == 0.0)
    check("حکم بازه درست خوانده می‌شود",
          A.verdict(0.1, 0.2) == "بالای صفر"
          and A.verdict(-0.2, -0.1) == "زیر صفر"
          and A.verdict(-0.1, 0.2) == "شامل صفر")

    # ── ۲) پارادوکس سیمپسون روی دادهٔ ساختگی ───────────────────────────
    rows = simpson_rows()
    sh = [r["R_net"] for r in rows if r["dir"] == "SHORT"]
    lo_ = [r["R_net"] for r in rows if r["dir"] == "LONG"]
    raw = A.two_sample(sh, lo_)
    check("دادهٔ ساختگی واقعاً شکافِ خام می‌سازد", raw["diff"] < -0.15,
          f"{raw['diff']:+.4f}")
    check("و شکافِ خام از نویز جدا به نظر می‌رسد (تلهٔ همین‌جاست)",
          raw["hi"] < 0, f"CI[{raw['lo']:+.3f},{raw['hi']:+.3f}]")

    strat = A.stratified_diff(rows, lambda r: r["_stage"])
    check("با کنترلِ استراتژی، اختلاف تقریباً صفر می‌شود",
          abs(strat["diff"]) < 0.02, f"{strat['diff']:+.4f}")
    check("و CI طبقه‌بندی‌شده صفر را در بر می‌گیرد",
          strat["lo"] <= 0 <= strat["hi"],
          f"CI[{strat['lo']:+.3f},{strat['hi']:+.3f}]")
    check("طبقه‌های استفاده‌شده گزارش می‌شوند", len(strat["used"]) == 2,
          str(strat["used"]))

    std, cov = A.standardize(rows, lambda r: r["_stage"])
    check("استانداردسازی، لانگ را به سطح شورت می‌آورد",
          std is not None and abs(std - statistics.mean(sh)) < 0.02,
          f"{std} در برابر {statistics.mean(sh)}")
    check("پوشش استانداردسازی گزارش می‌شود", cov > 0.95, str(cov))

    # طبقهٔ تک‌نمونه‌ای باید کنار برود و صریح اعلام شود
    thin = rows + [{"dir": "SHORT", "R_net": 9.9, "_stage": "sig-solo",
                    "_stop_pct": 1.0}]
    s2 = A.stratified_diff(thin, lambda r: r["_stage"])
    check("طبقهٔ تک‌نمونه‌ای کنار می‌رود و اعلام می‌شود",
          any(k == "sig-solo" for k, _, _ in s2["skipped"]), str(s2["skipped"]))
    check("و پرتِ همان طبقه، اختلاف را آلوده نمی‌کند",
          abs(s2["diff"] - strat["diff"]) < 1e-9,
          f"{s2['diff']} در برابر {strat['diff']}")

    # ── ۳) باند استاپ ──────────────────────────────────────────────────
    check("باند استاپ درست دسته‌بندی می‌شود",
          A.band({"_stop_pct": 0.3}) == "0–0.5٪"
          and A.band({"_stop_pct": 1.0}) == "0.8–1.5٪"
          and A.band({"_stop_pct": 9.0}) == "1.5–99٪")
    check("استاپ ناموجود، باند نمی‌گیرد (حدس زده نمی‌شود)",
          A.band({"_stop_pct": None}) is None)

    # ── ۴) یکتاسازی، پیش از هر آماری ───────────────────────────────────
    src = (PY / "hamid" / "direction_autopsy.py").read_text(encoding="utf-8")
    check("دفتر پیش از آمار یکتا می‌شود (درس ۲۴ اوت)",
          "seen.add(k)" in src and "if k in seen" in src)
    check("یکتاسازی بر هویتِ معامله است نه متنِ خط",
          '(r.get("sym"), r.get("dir"), r.get("opened"), r.get("entry"))' in src)

    # ── ۵) کلاسِ خطا: ادعای دونمونه‌ای باید همیشه چاپ شود ───────────────
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        A.main([])
    out = buf.getvalue()
    check("خروجی، اختلافِ دو گروه را صریح چاپ می‌کند",
          "اختلاف خام (شورت − لانگ)" in out, out[:200])
    check("خروجی، کنترلِ مخدوش‌کننده را چاپ می‌کند",
          "کنترل بر استراتژی" in out and "کنترل بر باند فاصلهٔ استاپ" in out)
    check("خروجی، تفاوتِ ادعای تک‌نمونه و دونمونه را توضیح می‌دهد",
          "در برابر **صفر**" in out)
    check("خروجی، ترکیبِ استراتژی هر جهت را نشان می‌دهد",
          "ترکیبِ شورت" in out or "با ترکیبِ شورت" in out)
    check("خروجی، مرز صادقانه دارد (قانون ۱۲)", "مرز صادقانه" in out)
    check("خروجی، جدولِ کارمزد در برابر فاصلهٔ استاپ دارد",
          "کارمزد=" in out and "استاپ 0–0.5٪" in out)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
