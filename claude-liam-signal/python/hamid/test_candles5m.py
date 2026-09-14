"""آزمون آفلاین جمع‌آوری ۵د — بدون هیچ شبکه‌ای.

چیزهایی که باید نگه داشته شوند:
  ۱. راستی‌آزمایی: سری سالم قبول؛ تکرار/OHLC خراب/شکاف بزرگ رد با دلیل.
  ۲. دادهٔ گمشده شمرده و اعلام می‌شود، هرگز پر نمی‌شود.
  ۳. مانیفست: لنگر زمانی بعد از ساخت عوض نمی‌شود (پیشرفت سنجش‌پذیر).
  ۴. ادامه از وسط: DONE دوباره کشیده نمی‌شود؛ FAILED دوباره تلاش می‌شود.
  ۵. منبعِ ناموفق نماد را FAILED می‌کند، نه DONE — و دلیلش ثبت است.

    python3 -m hamid.test_candles5m
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import candles5m as c5                    # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="c5m-"))
c5.MANIFEST = TMP / "5m-manifest.json"               # دور از brain/ تولید
c5.INVENTORY = TMP / "inventory.json"
c5.INVENTORY.write_text(json.dumps(
    {"klines": {"AAAUSDT_15m.bin": {}, "BBBUSDT_15m.bin": {},
                "CCCUSDT_15m.bin": {}}}))
c5.PAUSE_S = 0

FAIL = 0


def check(n, ok, txt):
    global FAIL
    print(f"{n} {'✅' if ok else '❌'} {txt}")
    if not ok:
        FAIL += 1


T0 = 1_700_000_000_000 - 1_700_000_000_000 % c5.TF_MS


def series(n, start=T0, gap_at=None, dup_at=None, bad_at=None):
    rows, t = [], start
    for i in range(n):
        if gap_at is not None and i == gap_at:
            t += 40 * c5.TF_MS                       # شکاف بزرگ
        r = [t, 100.0, 101.0, 99.0, 100.5, 5.0]
        if bad_at is not None and i == bad_at:
            r = [t, 100.0, 99.0, 99.5, 100.5, 5.0]   # high < open
        rows.append(r)
        if dup_at is not None and i == dup_at:
            rows.append(list(r))                     # زمان تکراری
        t += c5.TF_MS
    return rows


# ۱) سری سالم قبول می‌شود
ok, rep = c5.verify(series(500), T0, T0 + 500 * c5.TF_MS)
check("۱", ok and rep["rows"] == 500 and rep["missing_rows"] == 0
      and rep["coverage_pct"] == 100.0, "سری سالم → قبول، پوشش ۱۰۰٪")

# ۲) شکاف شمرده و اعلام می‌شود؛ شکاف بزرگ = رد با دلیل
ok2, rep2 = c5.verify(series(500, gap_at=100), T0, 0)
check("۲", not ok2 and rep2["gaps"] == 1 and rep2["missing_rows"] == 40
      and "پوشش" in rep2["why"],
      "شکاف ۴۰ردیفی → شمرده شد و رد؛ هیچ ردیفی جعل نشد")

# ۳) تکرار و OHLC خراب رد می‌شوند
ok3, r3 = c5.verify(series(50, dup_at=10), T0, 0)
ok4, r4 = c5.verify(series(50, bad_at=10), T0, 0)
check("۳", not ok3 and r3["why"] == "تکراری"
      and not ok4 and r4["why"] == "OHLC خراب",
      "تکراری و OHLC خراب → رد با دلیل درست")

# ۴) لنگر مانیفست بعد از ساخت ثابت می‌ماند
m1 = c5.init_manifest(now_ms=T0 + 1000 * c5.TF_MS)
c5.MANIFEST.write_text(json.dumps(m1))
m2 = c5.init_manifest(now_ms=T0 + 9000 * c5.TF_MS)  # خیلی بعدتر
check("۴", m2["start_ms"] == m1["start_ms"] and m2["end_ms"] == m1["end_ms"]
      and len(m2["symbols"]) == 3,
      "لنگر زمانی با اجراهای بعدی جابه‌جا نشد")

# ۵) اجرا با منبع قلابی: DONE می‌سازد، FAILED دلیل دارد، ادامه از وسط
calls = []


def fake_fetch(sym, s, e):
    calls.append(sym)
    if sym == "BBBUSDT":
        return None, "بلاک"
    return "fake_src", series(300, start=s)


ups = c5.run(budget_min=5, out_dir=TMP / "out", fetch=fake_fetch)
m = json.loads(c5.MANIFEST.read_text())
sy = m["symbols"]
check("۵", sy["AAAUSDT"]["status"] == "DONE" and sy["AAAUSDT"]["sha256"]
      and sy["BBBUSDT"]["status"] == "FAILED" and sy["BBBUSDT"]["why"] == "بلاک"
      and sy["CCCUSDT"]["status"] == "DONE" and len(ups) == 2,
      "اجرا: ۲ DONE با sha256 · ۱ FAILED با دلیل")

calls.clear()
c5.run(budget_min=5, out_dir=TMP / "out", fetch=fake_fetch)
check("۶", calls == ["BBBUSDT"],
      "اجرای دوم فقط سراغ FAILED رفت — DONE دوباره کشیده نشد")

print()
if FAIL:
    print(f"{FAIL} آزمون شکست")
    sys.exit(1)
print("همهٔ ۶ آزمون جمع‌آوری ۵د گذشت")
