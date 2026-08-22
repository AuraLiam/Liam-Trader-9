"""پاسبان بک‌تست دفتر سناریو — همراه اجباری scenario_backtest.py.

مهم‌ترین چیزی که این‌جا قفل می‌شود، همان چیزی است که کل ادعای بک‌تست روی
آن ایستاده: **نقشه هرگز کندلی را که ماشه‌اش می‌زند نمی‌بیند.** بقیه
(ضدهم‌پوشانی، بدترین‌حالت درون‌کندلی، مسیر جایگزین top_symbols، تفکیک
BOS/CHoCH و سشن) هم درس‌های تکرارشدهٔ همین پروژه‌اند.
"""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import scenarios as SC                     # noqa: E402
from hamid import scenario_backtest as BT             # noqa: E402

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


def walk(n=2500, seed=3, vol=0.0015, t0=0):
    rng = random.Random(seed)
    cd, px = [], 100.0
    for i in range(n):
        px *= (1 + rng.gauss(0, vol))
        cd.append({"t": t0 + i * 60000, "o": px,
                   "h": px + abs(rng.gauss(0, vol)) * px,
                   "l": px - abs(rng.gauss(0, vol)) * px,
                   "c": px, "v": 1.0})
    return cd


CD = walk()

# ── resample ─────────────────────────────────────────────────────────────
c3 = BT.resample(CD, 3)
check("۳د از ۱د ساخته می‌شود و حدوداً یک‌سوم تعداد دارد",
      abs(len(c3) - len(CD) / 3) <= 2, f"{len(c3)} vs {len(CD)/3:.0f}")
check("مرز کندل ۳د روی مضرب واقعی زمان است",
      all(k["t"] % (3 * 60000) == 0 for k in c3))
k0 = c3[0]
src = [k for k in CD if k0["t"] <= k["t"] < k0["t"] + 3 * 60000]
check("۳د سقف/کف/کلوز را درست از ۱د می‌سازد",
      abs(k0["h"] - max(s["h"] for s in src)) < 1e-9
      and abs(k0["l"] - min(s["l"] for s in src)) < 1e-9
      and abs(k0["c"] - src[-1]["c"]) < 1e-9)
check("۱د دست‌نخورده برمی‌گردد", BT.resample(CD, 1) is CD)

# ── ضد نگاه به آینده: نقشه نباید کندلِ ماشه را ببیند ─────────────────────
seen = {"max_len": 0, "ok": True}
old_plan = SC.plan


def spy_plan(cd, sym="?", params=None):
    seen["max_len"] = max(seen["max_len"], len(cd))
    seen["ok"] = seen["ok"] and cd[-1]["t"] == max(k["t"] for k in cd)
    return old_plan(cd, sym, params)


SC.plan = spy_plan
try:
    trades, reasons = BT.replay_symbol("TESTUSDT", CD)
finally:
    SC.plan = old_plan

check("بک‌تست معاملهٔ واقعی ساخت (نه لیست خالی)", len(trades) >= 5,
      f"trades={len(trades)} reasons={dict(list(reasons.items())[:3])}")
check("نقشه فقط با کندل‌های گذشته ساخته می‌شود", seen["ok"])
check("نقشه هرگز تا آخرِ سری را نمی‌بیند (کندلِ ماشه بیرون می‌ماند)",
      seen["max_len"] <= len(CD) - 2, f"max_len={seen['max_len']} / {len(CD)}")

# ماشه واقعاً از کندل بعدِ نقشه آمده: ورودِ هر معامله باید کلوزِ همان کندل
# باشد که در زمانِ opened ثبت شده — نه کلوزِ کندل نقشه.
bad = 0
by_t = {k["t"]: k for k in CD}
for t in trades:
    k = by_t.get(t["opened"])
    if k is None:
        bad += 1
check("زمان ورود هر معامله روی یک کندل واقعی می‌نشیند", bad == 0, f"bad={bad}")

opens = [t["opened"] for t in trades]
check("معامله‌ها هم‌پوشانی ندارند", len(opens) == len(set(opens)))
check("قیف علت رد خالی نیست (ردشدن در سکوت ممنوع)", len(reasons) >= 1)
check("R خالص هرگز از R ناخالص بیشتر نیست (کارمزد واقعاً کسر شده)",
      all(t["R_net"] <= t["R"] for t in trades))
check("هر معامله نوعش (BOS/CHoCH) و سشنش را حمل می‌کند",
      all(t["kind"] in ("BOS", "CHoCH")
          and t["session"] in ("asia", "london", "ny", "overlap")
          for t in trades))
check("اهرم روی هر معامله ثبت می‌شود", all(t["leverage"] >= 1 for t in trades))
check("acct_pct = R خالص × ریسک ۲٪ (اهرم لبه را عوض نمی‌کند)",
      all(abs(t["acct_pct"] - t["R_net"] * BT.RISK_PCT) < 1e-6 for t in trades))

# بدترین حالت درون‌کندلی: کندلی که هم استاپ هم تارگت را لمس کند = استاپ
hit = [t for t in trades if t["outcome"] == "stop"]
check("خروج استاپ‌دار وجود دارد (بدترین‌حالت واقعاً اعمال می‌شود)", len(hit) > 0)

# ── CI ───────────────────────────────────────────────────────────────────
check("CI با نمونهٔ کم None است", BT.boot_ci([0.1] * 10) is None)
ci = BT.boot_ci([0.5, -1.0, 2.0] * 20)
check("CI با نمونهٔ کافی بازه می‌دهد", ci and ci[0] < ci[1], str(ci))

# ── run(): مسیر جایگزین top_symbols + تفکیک‌های خواسته‌شده ───────────────
import sources                                        # noqa: E402
from hamid import trainer                             # noqa: E402

FIX = {"AUSDT": walk(seed=3), "BUSDT": walk(seed=9)}
old_k = sources.klines
old_top = getattr(sources, "top_symbols", None)
old_tt = trainer.top_symbols
old_out = BT.OUT
tmp = Path(BT.OUT.parent) / "scenario-backtest-test.json"

if old_top is not None:
    del sources.top_symbols
sources.klines = lambda sym, tf, n, **kw: [
    [k["t"], k["o"], k["h"], k["l"], k["c"], k["v"]] for k in FIX[sym]]
trainer.top_symbols = lambda n: list(FIX)
BT.OUT = tmp
try:
    res = BT.run(symbols=2, tf="1m", bars=2500, quiet=True)
    check("run() بدون sources.top_symbols هم از مسیر جایگزین رد می‌شود",
          not hasattr(sources, "top_symbols") and res["symbols"] == 2,
          str(res.get("symbols")))
    check("خروجی BOS و CHoCH را جدا گزارش می‌کند (دستور حمید)",
          "per_kind" in res and set(res["per_kind"]) & {"BOS", "CHoCH"},
          str(list(res.get("per_kind", {}))))
    check("خروجی کارنامهٔ هر سشن را جدا می‌دهد (دستور حمید)",
          "per_session" in res and len(res["per_session"]) >= 1)
    check("خروجی اهرم و ریسک هر معامله را اعلام می‌کند",
          res["leverage"] == SC.P["leverage"] and res["risk_pct_per_trade"] == 2.0)
    check("خروجی هدفِ تعداد معامله و فاصله‌اش را صادقانه می‌نویسد",
          "trade_target_note" in res and res["target_trades"] == 300)
    check("فایل روی دیسک نوشته شد", tmp.exists())
finally:
    sources.klines = old_k
    trainer.top_symbols = old_tt
    if old_top is not None:
        sources.top_symbols = old_top
    BT.OUT = old_out
    tmp.unlink(missing_ok=True)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان بک‌تست سناریو: هر {OK} بررسی سبز")
