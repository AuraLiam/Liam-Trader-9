"""پاسبانِ هزینهٔ تسویه — قطعی ۵۶ساعتهٔ چرخهٔ حمید (۲۴–۲۶ سپتامبر).

## چه اتفاقی افتاد

`paper.mark` برای **هر ردیف** دفتر باز یک بار کندل می‌گرفت. دفتر به ۴٬۸۵۴
ردیف روی فقط ۲۹۸ نماد رسید (~۱۶ برابر فچ تکراری). چرخه ۳۳ دقیقه بی‌هیچ خطی
ماند و در سقف ۴۰ دقیقهٔ job کشته شد — **پیش از** نوشتنِ دفتر باز و پیش از
انتشار. ردیف‌ها تسویه نمی‌شدند، دفتر بزرگ‌تر می‌شد، اجرای بعد کندتر: مارپیچ.
۲۷ فایل وضعیت ۵۶ ساعت کهنه ماندند.

## کلاسِ عیب

حلقهٔ شبکه‌ایِ بی‌سقف به‌ازای هر ردیف، داخل jobی که سقف سخت دارد. این آزمون
**خاصیت** را می‌سنجد نه شکلِ کد را:

1. تعداد فچِ شبکه در یک `mark` ≤ تعداد نمادهای یکتا (نه تعداد ردیف‌ها).
2. نمادِ خراب در یک دور بیش از یک بار فچ نمی‌شود.
3. وقتی سقف زمان خورد، **هیچ ردیفی گم نمی‌شود** — مانده‌ها دست‌نخورده باز می‌مانند.
4. قدیمی‌ترین ردیف‌ها اول تسویه می‌شوند؛ آن‌که برای دور بعد می‌ماند جدیدترین است.
5. کش بعد از `mark` پاک می‌شود — حتی اگر وسطش خطا شود.

    python3 -m hamid.test_mark_budget
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import paper as P                                  # noqa: E402

OK, FAIL = 0, []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


def _row(sym, age_h, now):
    # ورودِ دور از قیمت: پر نمی‌شود، پس ردیف باز می‌ماند و تسویه چیزی را نمی‌بندد.
    return {"sym": sym, "dir": "LONG", "entry": 1.0, "sl": 0.99, "tp1": 1.02,
            "tp2": None, "opened": int(now - age_h * 3600e3), "filled": None,
            "why": {"stage": "practice"}}


def _candles(now, n):
    return [[int(now - (n - i) * 900_000), 2.0, 2.1, 1.9, 2.0, 1.0] for i in range(n)]


def _setup():
    d = Path(tempfile.mkdtemp(prefix="markb-"))
    saved = (P.CLOSED, P.OPEN, P.EQUITY, P.MARK_BUDGET_S, P.sources.klines)
    P.CLOSED, P.OPEN, P.EQUITY = d / "c.jsonl", d / "o.jsonl", d / "e.json"
    return saved


def _restore(saved):
    P.CLOSED, P.OPEN, P.EQUITY, P.MARK_BUDGET_S, P.sources.klines = saved


print("── هزینهٔ تسویهٔ دفتر باز ──")
now = time.time() * 1000

# ── ۱) فچ به‌ازای نماد، نه ردیف ─────────────────────────────────────────
saved = _setup()
try:
    calls = []

    def fake(sym, tf, n):
        calls.append((sym, n))
        return _candles(now, n)

    P.sources.klines = fake
    syms = [f"S{i}USDT" for i in range(12)]
    rows = [_row(s, 0.5 + j * 0.33 + k * 0.01, now) for j in range(30) for k, s in enumerate(syms)]  # ۳۶۰ ردیف، همه زیر اعتبار ۱۲س لیمیت
    for r in rows:
        P._append(P.OPEN, r)
    still, closed = P.mark()
    check(f"۳۶۰ ردیف روی ۱۲ نماد ⇒ حداکثر ۱۲ فچ (دیده‌شده: {len(calls)})",
          len(calls) <= len(syms), str(calls[:5]))
    check("همهٔ ردیف‌ها باز ماندند (هیچ‌کدام پر نشد، هیچ‌کدام گم نشد)",
          still == len(rows) and closed == 0, f"still={still} closed={closed}")
    check("کش بعد از mark پاک شد", P._KCACHE is None)
finally:
    _restore(saved)

# ── ۲) نمادِ خراب یک بار، نه هر ردیف ────────────────────────────────────
saved = _setup()
try:
    calls = []

    def broken(sym, tf, n):
        calls.append(sym)
        if sym == "DEADUSDT":
            raise TimeoutError("venue chain exhausted")
        return _candles(now, n)

    P.sources.klines = broken
    for j in range(25):
        P._append(P.OPEN, _row("DEADUSDT", 0.5 + j * 0.4, now))
    P._append(P.OPEN, _row("LIVEUSDT", 2, now))
    P.mark()
    check(f"نمادِ خراب در یک دور یک بار فچ شد (دیده‌شده: {calls.count('DEADUSDT')})",
          calls.count("DEADUSDT") == 1, str(calls))
finally:
    _restore(saved)

# ── ۳ و ۴) سقف زمان: هیچ ردیفی گم نمی‌شود، قدیمی‌ترین اول ─────────────────
saved = _setup()
try:
    seen = []

    def slow(sym, tf, n):
        seen.append(sym)
        time.sleep(0.05)
        return _candles(now, n)

    P.sources.klines = slow
    P.MARK_BUDGET_S = 0.12      # ~دو فچ و بعد سقف
    ages = {f"A{i}USDT": 11 - i * 0.5 for i in range(20)}   # A0 قدیمی‌ترین؛ همه زیر اعتبار ۱۲س
    order = list(ages)
    import random
    random.Random(3).shuffle(order)                     # نوشتن به ترتیب نامرتب
    for s in order:
        P._append(P.OPEN, _row(s, ages[s], now))
    still, closed = P.mark()
    left = {r["sym"] for r in P._read(P.OPEN)}
    check("سقف خورد و هیچ ردیفی گم نشد (۲۰ نوشته، ۲۰ باز)",
          still == 20 and len(left) == 20 and closed == 0,
          f"still={still} left={len(left)}")
    check("سقف واقعاً جلوی فچ را گرفت (نه همهٔ ۲۰ نماد)",
          0 < len(seen) < 20, f"fetched={len(seen)}")
    check("قدیمی‌ترین‌ها اول تسویه شدند",
          seen and seen[0] == "A0USDT", str(seen))
    check("کش حتی بعد از سقف پاک شد", P._KCACHE is None)
finally:
    _restore(saved)

# ── ۵) کش حتی با خطای وسطِ حلقه پاک می‌شود ────────────────────────────────
saved = _setup()
try:
    P.sources.klines = lambda s, tf, n: _candles(now, n)
    real_settle = P._settle_one

    def boom(p, *a, **k):
        raise KeyboardInterrupt("simulated kill")

    P._settle_one = boom
    P._append(P.OPEN, _row("XUSDT", 1, now))
    try:
        P.mark()
    except KeyboardInterrupt:
        pass
    check("خطای وسط حلقه کش را جا نمی‌گذارد (finally)", P._KCACHE is None)
finally:
    P._settle_one = real_settle
    _restore(saved)

# ── ۶) سیم‌کشی: سقف با سقفِ job هم‌خوان است ────────────────────────────────
wf = (HERE.parents[2] / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
import re
m = re.search(r"timeout-minutes:\s*(\d+)", wf)
job_min = int(m.group(1)) if m else 0
check(f"سقف تسویه ({P.MARK_BUDGET_S}ث) کمتر از نیمِ سقف job ({job_min} دقیقه) است",
      job_min and P.MARK_BUDGET_S < job_min * 60 / 2,
      f"budget={P.MARK_BUDGET_S} job={job_min}m")
check("پاسبان در دروازهٔ چرخه اجرا می‌شود", "hamid.test_mark_budget" in wf)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}: {FAIL}")
    sys.exit(1)
print(f"پاسبان هزینهٔ تسویه: هر {OK} بررسی سبز")
