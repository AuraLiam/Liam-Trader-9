"""پاسبان موتور بیگ‌مانی (E10) — همراه اجباری hamid/big_money.py.

کاملاً آفلاین: پروکسی این سندباکس api.gateio.ws را می‌بندد (۴۰۳ سیاستی)،
پس fetch_stats با پاسخ‌های ساختگی تست می‌شود، نه شبکهٔ واقعی. اجرای واقعی
فقط از GitHub Actions معنی دارد.

درس‌های تکرارنشدنی این پروژه که این‌جا هم رعایت شدند: (۱) فیکسچر باید
واقعاً یک نتیجهٔ حکم‌دار بسازد (n≥30، thin=False) وگرنه تست الکی سبز
می‌شود؛ (۲) z-score باید اثبات‌شده بدون نگاه به آینده باشد، نه فقط ادعا.
"""
import math
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import big_money as BM               # noqa: E402

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


# ── long_pct ──────────────────────────────────────────────────────────────
check("نسبت ۱ = ۵۰٪ لانگ", abs(BM.long_pct(1.0) - 50.0) < 1e-9)
check("نسبت ۳ = ۷۵٪ لانگ", abs(BM.long_pct(3.0) - 75.0) < 1e-9)
check("نسبت ۰ = ۰٪ لانگ", abs(BM.long_pct(0.0) - 0.0) < 1e-9)

# ── _tier ─────────────────────────────────────────────────────────────────
now = time.time()
check("تازه = ۵ دقیقه", BM._tier(now - 3600)[0] == "5m")
check("خیلی قدیمی = ۱ ساعته", BM._tier(now - 200 * 86400)[0] == "1h")

# ── _raw_features ─────────────────────────────────────────────────────────
rows_rf = [
    {"t": 0, "allLong": 40.0, "topSizeLong": 55.0, "topLongSize": 100.0, "topShortSize": 50.0},
    {"t": 3600, "allLong": 45.0, "topSizeLong": 60.0, "topLongSize": 150.0, "topShortSize": 50.0},
]
raw = BM._raw_features(rows_rf, bar_secs=3600)
check("div = topSizeLong - allLong", abs(raw[0]["div"] - 15.0) < 1e-9, str(raw[0]))
check("skew = (لانگ-شورت)/کل × ۱۰۰", abs(raw[0]["skew"] - (50 / 150 * 100)) < 1e-6)
check("dsize یک‌ساعت قبل ندارد = ۰", raw[0]["dsize"] == 0.0)
check("dsize با یک‌ساعت قبل: (۱۵۰/۱۰۰-۱)×۱۰۰=۵۰",
      abs(raw[1]["dsize"] - 50.0) < 1e-6, str(raw[1]))
check("crowd/size عیناً پاس می‌شوند",
      raw[1]["crowd"] == 45.0 and raw[1]["size"] == 60.0)

# ── _zscores: بدون نگاه به آینده ─────────────────────────────────────────
random.seed(3)
vals = [random.gauss(0, 1) for _ in range(300)]
z_full = BM._zscores(vals, win=20)
z_prefix = BM._zscores(vals[:150], win=20)
check("z-score فقط از گذشته می‌آید (بریدن دنباله، سر دست‌نخورده می‌ماند)",
      z_full[:150] == z_prefix)
check("گرمایش کم = None (نیمهٔ اول پنجره)", z_full[5] is None)
check("بعد از گرمایش، عدد واقعی می‌دهد", z_full[25] is not None)
const = BM._zscores([5.0] * 50, win=20)
check("سری ثابت: انحراف صفر → z=0 نه تقسیم‌برصفر", const[30] == 0.0)

# ── _tstat ────────────────────────────────────────────────────────────────
check("t-stat با نمونهٔ کم = ۰", BM._tstat([1.0, 2.0]) == 0.0)
check("t-stat سری با میانگین صفر ≈ صفر", abs(BM._tstat([-1, 0, 1, -1, 1, 0])) < 1e-6)

# ── fetch_stats: پارس صفحه‌بندی‌شده، بدون شبکه ─────────────────────────────
pages = {
    0: [{"time": 0, "lsr_account": "1.0", "top_lsr_size": "3.0", "top_lsr_account": "2.0",
         "top_long_size": "300", "top_short_size": "100", "mark_price": "100.0"},
        {"time": 300, "lsr_account": "1.2", "top_lsr_size": "2.5", "top_lsr_account": "1.8",
         "top_long_size": "310", "top_short_size": "110", "mark_price": "101.0"}],
    300: [],
}
old_get = BM._get_json
BM._get_json = lambda url, tries=3: pages.get(
    int(url.split("from=")[1].split("&")[0]), [])
try:
    got = BM.fetch_stats("BTC", "5m", 0, 600)
finally:
    BM._get_json = old_get
check("fetch_stats دو ردیف صعودی برمی‌گرداند", len(got) == 2 and got[0]["t"] < got[1]["t"],
      str(got))
check("fetch_stats نسبت‌ها را به درصد لانگ تبدیل می‌کند",
      abs(got[0]["allLong"] - 50.0) < 1e-6 and abs(got[0]["topSizeLong"] - 75.0) < 1e-6,
      str(got[0]))

# ── run_backtest: فیکسچر مهندسی‌شده با واگرایی پیشگو ──────────────────────
# div بالا (پول درشت لانگ‌تر از جمعیت) → قیمت طی افق بعدی بالا می‌رود.
# ماکروی سینوسی با پریود ۴۸ کندل، z-score روی پنجرهٔ ۳۰ کندلی این نوسان را
# می‌گیرد؛ n=۲۵۰۰ برای رسیدن oosN به کف ۳۰ (زیر آن نتیجه thin=True می‌شود
# و در «بهترین» انتخاب نمی‌گردد — دقیقاً محافظ CI پروژه).
old_hz, old_zwin = BM.BT_HORIZONS, BM.BT_ZWIN_SECS
BM.BT_HORIZONS = [("1h", 3600)]
BM.BT_ZWIN_SECS = 9000                          # ۳۰ کندل در ۵ دقیقه
try:
    random.seed(11)
    bar_secs, T, k, n = 300, 48, 0.0015, 2500
    rows_bt, px = [], 100.0
    for i in range(n):
        phase = 2 * math.pi * i / T
        sig = math.sin(phase)
        px *= (1 + k * sig + random.gauss(0, 0.0006))
        all_long = 50 + random.gauss(0, 1.5)
        top_size_long = all_long + sig * 8 + random.gauss(0, 1.0)
        tls = 1000 + 50 * math.sin(phase * 0.7) + random.gauss(0, 10)
        tss = 1000 - 50 * math.sin(phase * 0.7) + random.gauss(0, 10)
        rows_bt.append({"t": i * bar_secs, "allLong": all_long,
                        "topSizeLong": top_size_long, "topAcctLong": all_long,
                        "topLongSize": tls, "topShortSize": tss, "px": px})
    out = BM.run_backtest(rows_bt, cost_bps=0.0, bar_secs=bar_secs)
finally:
    BM.BT_HORIZONS, BM.BT_ZWIN_SECS = old_hz, old_zwin

div_r = next((r for r in out["results"] if r["feature"] == "div"), None)
check("واگراییِ مهندسی‌شده حکم‌دار می‌شود (n≥۳۰، thin=False)",
      div_r is not None and not div_r["thin"] and div_r["oosN"] >= 30, str(div_r))
check("جهت درست تشخیص داده می‌شود (div بالا → سیگنال لانگ)",
      div_r is not None and div_r["sign"] == 1, str(div_r))
check("میانگین اوت‌آف‌سمپل واقعاً مثبت است (نه فقط جهت)",
      div_r is not None and div_r["oosMean"] > 0.3, str(div_r))
check("بهترین نتیجه همین واگرایی است",
      out["best"] is not None and out["best"]["feature"] == "div", str(out["best"]))
check("هر نتیجه ردپای معامله‌های اوت‌آف‌سمپل دارد (برای پول‌بندی cross-symbol)",
      all("oos_trades" in r and len(r["oos_trades"]) == r["oosN"] for r in out["results"]))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان موتور بیگ‌مانی: هر {OK} بررسی سبز")
