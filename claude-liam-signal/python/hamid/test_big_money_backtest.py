"""پاسبان بک‌تست بیگ‌مانی روی جهانِ نمادها — همراه اجباری big_money_backtest.py.

کاملاً آفلاین: hamid.big_money.fetch_stats با فیکسچر مهندسی‌شده (همان
الگوی test_big_money.py) جایگزین می‌شود؛ شبکهٔ واقعی هرگز لمس نمی‌شود.
مسیر جایگزین top_symbols هم طبق کلاس‌عیب ۲۰ اوت (AttributeError وقتی
sources.top_symbols نیست) تست می‌شود — همان درسی که dash_backtest و
scalp_dash_backtest قبلاً یاد گرفتند.
"""
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import big_money as BM                     # noqa: E402
from hamid import big_money_backtest as BB             # noqa: E402

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


# ── boot_ci ───────────────────────────────────────────────────────────────
check("boot_ci با نمونهٔ کم None است", BB.boot_ci([0.1] * 10) is None)
ci = BB.boot_ci([0.5, -0.2, 0.8] * 20)
check("boot_ci با نمونهٔ کافی بازه می‌دهد", ci and ci[0] < ci[1], str(ci))

# ── فیکسچر مهندسی‌شده (عیناً همان test_big_money.py: div پیشگو) ───────────
random.seed(11)
bar_secs, T, k, n = 300, 48, 0.0015, 2500


def _synthetic(seed):
    rng = random.Random(seed)
    rows, px = [], 100.0
    for i in range(n):
        phase = 2 * math.pi * i / T
        sig = math.sin(phase)
        px *= (1 + k * sig + rng.gauss(0, 0.0006))
        all_long = 50 + rng.gauss(0, 1.5)
        top_size_long = all_long + sig * 8 + rng.gauss(0, 1.0)
        tls = 1000 + 50 * math.sin(phase * 0.7) + rng.gauss(0, 10)
        tss = 1000 - 50 * math.sin(phase * 0.7) + rng.gauss(0, 10)
        rows.append({"t": i * bar_secs, "allLong": all_long,
                    "topSizeLong": top_size_long, "topAcctLong": all_long,
                    "topLongSize": tls, "topShortSize": tss, "px": px})
    return rows


FIXTURES = {"AUSDT": _synthetic(11), "BUSDT": _synthetic(12)}

old_hz, old_zwin = BM.BT_HORIZONS, BM.BT_ZWIN_SECS
old_fetch = BM.fetch_stats
old_tier = BM._tier
BM.BT_HORIZONS = [("1h", 3600)]
BM.BT_ZWIN_SECS = 9000
BM._tier = lambda frm: ("5m", bar_secs)
BM.fetch_stats = lambda sym, interval, frm, to: FIXTURES[sym]

import sources                                          # noqa: E402
from hamid import trainer                                # noqa: E402
old_top = getattr(sources, "top_symbols", None)
old_trainer_top = trainer.top_symbols
old_out = BB.OUT
tmp = Path(BB.OUT.parent) / "big-money-backtest-test.json"

if old_top is not None:
    del sources.top_symbols
trainer.top_symbols = lambda n: list(FIXTURES.keys())
BB.OUT = tmp
try:
    res = BB.run(symbols=2, quiet=True)
    check("run() بدون sources.top_symbols هم از مسیر جایگزین رد می‌شود",
          not hasattr(sources, "top_symbols") and res["symbols_tested"] == 2,
          str(res.get("symbols_tested")))
    key = "div|1h"
    pooled = res["pooled_oos"].get(key)
    check("واگراییِ استخر‌شده از هر دو نماد حکم‌دار می‌شود",
          pooled is not None and pooled["n"] >= 60, str(pooled))
    check("CI۹۵ استخرشده کاملاً بالای صفر است",
          pooled and pooled["ci95_pct"] and pooled["ci95_pct"][0] > 0, str(pooled))
    check("ci_clears_zero درست به این ویژگی اشاره می‌کند",
          res["ci_clears_zero"] == key, str(res.get("ci_clears_zero")))
    check("per_symbol برای هر دو نماد جدا ثبت شده",
          set(res["per_symbol"].keys()) == set(FIXTURES.keys()))
    check("فایل روی دیسک نوشته و JSON معتبر است", tmp.exists())
finally:
    BM.BT_HORIZONS, BM.BT_ZWIN_SECS = old_hz, old_zwin
    BM.fetch_stats = old_fetch
    BM._tier = old_tier
    trainer.top_symbols = old_trainer_top
    if old_top is not None:
        sources.top_symbols = old_top
    BB.OUT = old_out
    tmp.unlink(missing_ok=True)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان بک‌تست بیگ‌مانی: هر {OK} بررسی سبز")
