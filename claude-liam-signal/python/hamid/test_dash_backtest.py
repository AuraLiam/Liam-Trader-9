"""پاسبان بک‌تست موتور داشبورد — همراه اجباری dash_backtest (قانون رفع قطعی).

درس‌های تکرارنشدنی: (۱) تصمیم فقط با کندل‌های گذشته؛ (۲) run() خودش هم
باید در تست اجرا شود (KeyError دفتر H1 دو بار به تولید رفت چون هیچ تستی
run را صدا نمی‌زد)؛ (۳) فیکسچر باید معامله بسازد وگرنه تست روی لیست خالی
«الکی سبز» می‌شود.
"""
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import liam9_strategy as ST            # noqa: E402
from hamid import dash_backtest as BT  # noqa: E402

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


def mk(path, tf_ms, t0=0):
    return [{"t": t0 + i * tf_ms, "o": p, "h": p * 1.004, "l": p * 0.996,
             "c": p} for i, p in enumerate(path)]


# فیکسچر: روند صعودی زیگزاگی (سوینگ واقعی می‌سازد؛ پلهٔ صاف «رنج» می‌شود)
M15, H1, H4 = 900000, 3600000, 14400000
up = [100 + i * 0.5 + 6 * math.sin(i / 3.0) for i in range(320)]
# ۴س و ۱س هر دو دقیقاً تا لحظهٔ شروع پنجرهٔ ۱۵د تاریخ کامل دارند (۳۲۰ ≥ ۲۲۰)
t15 = 320 * H4
c4 = mk(up, H4, t0=t15 - 320 * H4)
c1 = mk(up, H1, t0=t15 - 320 * H1)
base = [up[-1] + i * 0.15 + 1.5 * math.sin(i / 3.0) for i in range(310)]
pull = base + [base[-1] - i * 0.45 for i in range(1, 12)]
fwd = [pull[-1] * (1 + 0.004 * i) for i in range(1, 60)]
c15 = mk(pull + fwd, M15, t0=t15)
sig_i = len(pull) - 1
c15[sig_i]["l"] = c15[sig_i]["c"] * 0.988
c15[sig_i]["c"] = c15[sig_i]["c"] * 0.9895

ST.EXPERIENCE.clear()
ST.ENV["margin_mode"] = None
ST.TOP_LIQUIDITY.clear()
ST.TOP_LIQUIDITY.add("TESTUSDT")
ST._TOP_LIQ_OK = True
trades, reasons = BT.replay_symbol("TESTUSDT", c15, c1, c4,
                                   btc1h=c1, btc4h=c4)
check("بک‌تست معاملهٔ واقعی ساخت (نه لیست خالی)", len(trades) >= 1,
      f"trades={len(trades)} reasons={dict(list(reasons.items())[:3])}")
check("هر معامله R خالص دارد و از R ناخالص بیشتر نیست",
      all("R_net" in t and t["R_net"] <= t["R"] for t in trades))
opens = [t["opened"] for t in trades]
check("معامله‌ها هم‌پوشانی ندارند", len(opens) == len(set(opens)))
check("قیف علت رد خالی نیست (ردشدن در سکوت ممنوع)", len(reasons) >= 1)

# بدون بستر BTC هیچ معامله‌ای نباید ساخته شود (دروازهٔ بازار)
tr2, rs2 = BT.replay_symbol("TESTUSDT", c15, c1, c4)
check("بدون بستر BTC صفر معامله (دروازهٔ بازار در بک‌تست هم فعال است)",
      len(tr2) == 0 and any("بازار" in k or "BTC" in k for k in rs2),
      str(list(rs2)[:3]))

# تصمیم فقط با کندل‌های گذشته
seen = {}
old = ST.analyze


def spy(sym, w4, w1, w15, **kw):
    seen["ok"] = seen.get("ok", True) and \
        w15[-1]["t"] == max(k["t"] for k in w15) and \
        (not w1 or w1[-1]["t"] <= w15[-1]["t"]) and \
        (not w4 or w4[-1]["t"] <= w15[-1]["t"])
    return old(sym, w4, w1, w15, **kw)


ST.analyze = spy
try:
    BT.replay_symbol("TESTUSDT", c15, c1, c4, btc1h=c1, btc4h=c4)
finally:
    ST.analyze = old
check("تصمیم فقط با کندل‌های گذشته گرفته می‌شود", seen.get("ok") is True)

# CI: نمونهٔ کم None، نمونهٔ کافی بازه
check("CI با نمونهٔ کم None است", BT.boot_ci([0.1] * 10) is None)
ci = BT.boot_ci([0.5, -1.0, 2.0] * 20)
check("CI با نمونهٔ کافی بازه می‌دهد", ci and ci[0] < ci[1], str(ci))

# run() خودش هم اجرا می‌شود — با منبع دادهٔ ساختگی
import sources                          # noqa: E402
old_k, old_top = sources.klines, getattr(sources, "top_symbols", None)
old_out = BT.OUT
tmp = Path(BT.OUT.parent) / "dash-backtest-test.json"


def fake_klines(sym, tf, n, **kw):
    cd = {"15m": c15, "1h": c1, "4h": c4}[tf]
    return [[k["t"], k["o"], k["h"], k["l"], k["c"], 1.0] for k in cd]


# عمداً sources.top_symbols تزریق نمی‌شود: رانر ۲۰ اوت دقیقاً چون این تابع
# در sources نبود مرد و تستِ قبلی با تزریقش عیب را پوشانده بود. حالا run()
# باید از مسیر جایگزین (hamid.trainer.top_symbols) رد شود — همان مسیر واقعی.
from hamid import trainer               # noqa: E402
old_trainer_top = trainer.top_symbols
sources.klines = fake_klines
trainer.top_symbols = lambda n: ["TESTUSDT"]
BT.OUT = tmp
try:
    res = BT.run(symbols=1, bars=400, quiet=True)
    check("run() بدون sources.top_symbols هم تا آخر می‌رود (مسیر جایگزین)",
          not hasattr(sources, "top_symbols")
          and res["overall"].get("n", 0) >= 1 and "rejection_funnel" in res
          and res["market_gate"] == "on", str(res.get("overall")))
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
print(f"پاسبان بک‌تست داشبورد: هر {OK} بررسی سبز")
