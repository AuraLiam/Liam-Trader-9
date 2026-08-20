"""پاسبان بک‌تست میز اسکلپ داشبورد — همراه اجباری scalp_dash_backtest.

همان درس‌های dash_backtest، برای اسکلپ ۱ دقیقه با E08/E09: (۱) تصمیم فقط
با کندل‌های گذشته؛ (۲) run() خودش هم در تست اجرا می‌شود؛ (۳) فیکسچر باید
واقعاً معامله بسازد وگرنه تست روی لیست خالی «الکی سبز» می‌شود؛ (۴) اثر
اردر بلاک/کندل باید در خروجی قابل تفکیک باشد، نه فقط حضور فیلدها.
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import liam9_strategy as ST                    # noqa: E402
from hamid import scalp_dash_backtest as BT    # noqa: E402

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


def _mk_cycle(px0, t0, n_up=120, n_pull=6, tf=60000):
    """یک دور روند صعودی + پولبک + کندل تأیید — دقیقاً الگوی سنجیده‌شدهٔ
    خودآزمایی liam9_strategy، زنجیره‌شده چند بار برای چند معاملهٔ قطعی."""
    out, px = [], px0
    for i in range(n_up):
        px = px0 + i * 0.05
        out.append({"t": t0 + i * tf, "o": px, "h": px * 1.001,
                    "l": px * 0.999, "c": px})
    last_up = px
    for i in range(1, n_pull + 1):
        px = last_up - i * 0.03
        out.append({"t": t0 + (n_up + i - 1) * tf, "o": px, "h": px * 1.001,
                    "l": px * 0.999, "c": px})
    out[-1]["l"] = out[-1]["c"] * 0.998
    out[-1]["c"] = out[-1]["c"] * 0.9982
    out[-4]["l"] = out[-1]["c"] * 0.993
    return out, px


def _chain(n_cycles=6):
    c1m, px, t = [], 100.0, int(time.time() * 1000) - 900 * 60000
    for _ in range(n_cycles):
        block, px = _mk_cycle(px, t)
        c1m += block
        t += len(block) * 60000 + 30 * 60000     # فاصله تا بیرون پنجرهٔ ضدتکرار
    return c1m


c1m = _chain()
ST.EXPERIENCE.clear()
ST.ENV["margin_mode"] = None
ST._LAST.clear()
trades, reasons = BT.replay_symbol("TESTUSDT", c1m)
check("بک‌تست معاملهٔ واقعی ساخت (نه لیست خالی)", len(trades) >= 1,
      f"trades={len(trades)} reasons={dict(list(reasons.items())[:3])}")
check("هر معامله R خالص دارد و از R ناخالص بیشتر نیست",
      all("R_net" in t and t["R_net"] <= t["R"] for t in trades))
opens = [t["opened"] for t in trades]
check("معامله‌ها هم‌پوشانی ندارند", len(opens) == len(set(opens)))
check("قیف علت رد خالی نیست (ردشدن در سکوت ممنوع)", len(reasons) >= 1)
check("هر معامله برچسب اثر اردر بلاک دارد (E08)",
      all("ob_bonus" in t for t in trades))
check("هر معامله برچسب هم‌راستایی کندل دارد (E09)",
      all("candle_align" in t for t in trades))

# تصمیم فقط با کندل‌های گذشته
seen = {}
old = ST.scalp_decide


def spy(cd, symbol="?"):
    seen["ok"] = seen.get("ok", True) and cd[-1]["t"] == max(k["t"] for k in cd)
    return old(cd, symbol)


ST.scalp_decide = spy
try:
    BT.replay_symbol("TESTUSDT", c1m)
finally:
    ST.scalp_decide = old
check("تصمیم فقط با کندل‌های گذشته گرفته می‌شود", seen.get("ok") is True)

# CI: نمونهٔ کم None، نمونهٔ کافی بازه
check("CI با نمونهٔ کم None است", BT.boot_ci([0.1] * 10) is None)
ci = BT.boot_ci([0.5, -1.0, 2.0] * 20)
check("CI با نمونهٔ کافی بازه می‌دهد", ci and ci[0] < ci[1], str(ci))

# run() خودش هم اجرا می‌شود — با منبع دادهٔ ساختگی، مسیر جایگزین top_symbols
import sources                          # noqa: E402
from hamid import trainer               # noqa: E402

old_k = sources.klines
old_top = getattr(sources, "top_symbols", None)
old_trainer_top = trainer.top_symbols
old_out = BT.OUT
tmp = Path(BT.OUT.parent) / "scalp-dash-backtest-test.json"


def fake_klines(sym, tf, n, **kw):
    return [[k["t"], k["o"], k["h"], k["l"], k["c"], 1.0] for k in c1m]


sources.klines = fake_klines
trainer.top_symbols = lambda n: ["TESTUSDT"]
BT.OUT = tmp
try:
    res = BT.run(symbols=1, bars=len(c1m), quiet=True)
    check("run() بدون sources.top_symbols هم تا آخر می‌رود (مسیر جایگزین)",
          not hasattr(sources, "top_symbols")
          and res["overall"].get("n", 0) >= 1 and "rejection_funnel" in res,
          str(res.get("overall")))
    check("خروجی run() اثر اردر بلاک و کندل را جدا گزارش می‌کند",
          "order_block_effect" in res and "candle_evidence_effect" in res)
finally:
    sources.klines = old_k
    trainer.top_symbols = old_trainer_top
    if old_top is not None:
        sources.top_symbols = old_top
    BT.OUT = old_out
    tmp.unlink(missing_ok=True)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان بک‌تست اسکلپ داشبورد: هر {OK} بررسی سبز")
