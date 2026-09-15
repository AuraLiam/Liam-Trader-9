"""آزمون آفلاین موضع بازار — شرط‌ها و کف/سقف‌ها همان‌طور که اعلام شده‌اند.

  ۱. ۴س صعودی + USDT.D نزولی → LONG_BIAS؛ ۴س نزولی + USDT.D صعودی → SHORT_BIAS.
  ۲. ۱س به‌تنهایی برچسب نمی‌سازد (قانون ۲) — ۴س رنج + ۱س صعودی → NEUTRAL.
  ۳. کندل BTC نرسد → NO_STANCE، نه حدس.
  ۴. دامیننس کهنه‌تر از ۹۰د → ممتنعِ ثبت‌شده، ولی موضع از ۴س/۱س ساخته می‌شود.
  ۵. رویداد کلان ≤۲س → یخ‌زده: موضع قبلی نگه داشته می‌شود.
  ۶. کف نگهداری ۲۴س: عبور امتیازِ مخالف زودتر از ۲۴س → نگه‌داشته؛ تغییر
     ساختار ۴س → همان لحظه عوض می‌شود.
  ۷. کارنامه زیر n=۲۰ عدد ندارد؛ با ۲۵ ثبت داوری‌شده، اصابت و CI دارد.
  ۸. دفتر append-only: ردیف‌های قبلی دست نمی‌خورند.

    python3 -m hamid.test_market_stance
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import market_stance as ms                # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="stance-"))
ms.OUT = TMP / "market-stance.json"
ms.LEDGER = TMP / "history.jsonl"

FAIL = 0


def check(n, ok, txt):
    global FAIL
    print(f"{n} {'✅' if ok else '❌'} {txt}")
    if not ok:
        FAIL += 1


def candles(direction, n=220, start=100.0):
    """سری با سوینگ‌های واضح: up = سقف/کف بالاتر، down = پایین‌تر، range = مسطح."""
    out, px = [], start
    for i in range(n):
        step = {"up": 0.4, "down": -0.4, "range": 0.0}[direction]
        wob = 1.2 if (i // 5) % 2 == 0 else -1.2       # زیگزاگ برای ساخت سوینگ
        px = px + step
        c = px + wob
        out.append({"t": i, "o": c - 0.2, "h": c + 0.8, "l": c - 0.8, "c": c, "v": 10})
    return out


def kget_factory(t4, t1, fail=False):
    def kget(sym, tf, n):
        if fail:
            raise RuntimeError("451")
        return candles(t4 if tf == "4h" else t1)
    return kget


NOW = 1_800_000_000_000                                # سه‌شنبه (weekday=1)


def dom(usdt4, usdt1, age_min=10, macro=None):
    return {"generated": NOW - age_min * 60000,
            "structure": {"usdt": {"trend_4h": usdt4, "trend_1h": usdt1},
                          "btc_d": {"trend_1h": "down"}},
            "macro": macro or []}


# ۱) جهت‌های روشن
r = ms.build(kget_factory("up", "up"), dom("down", "down"), {}, NOW, rows=[])
check("۱", r["stance"] == "LONG_BIAS" and r["score"] > 0.25
      and r["trigger"] == "first",
      f"۴س up + USDT.D down → LONG_BIAS (امتیاز {r['score']})")
r2 = ms.build(kget_factory("down", "down"), dom("up", "up"), {}, NOW, rows=[])
check("۱ب", r2["stance"] == "SHORT_BIAS" and r2["score"] < -0.25,
      f"۴س down + USDT.D up → SHORT_BIAS (امتیاز {r2['score']})")

# ۲) ۱س به‌تنهایی نمی‌تواند برچسب بسازد
r3 = ms.build(kget_factory("range", "up"), dom("range", "range"), {}, NOW, rows=[])
check("۲", r3["stance"] == "NEUTRAL" and r3["votes"]["btc_1h"] == 1
      and r3["votes"]["btc_4h"] == 0,
      "۴س رنج + ۱س صعودی → NEUTRAL (تایم پایین حق نقض ندارد)")

# ۳) بی‌داده = بی‌موضع
r4 = ms.build(kget_factory("up", "up", fail=True), dom("down", "down"), {}, NOW, rows=[])
check("۳", r4["stance"] == "NO_STANCE" and "btc" in r4["abstain"],
      "کندل BTC نرسید → NO_STANCE با دلیل")

# ۴) دامیننس کهنه → ممتنع ولی موضع ساخته می‌شود
r5 = ms.build(kget_factory("up", "up"), dom("down", "down", age_min=200), {}, NOW, rows=[])
check("۴", r5["stance"] == "LONG_BIAS" and "usdt" in r5["abstain"]
      and "usdt_4h" not in r5["votes"],
      "دامیننس ۲۰۰د → ممتنع ثبت شد؛ موضع از روند BTC ساخته شد")

# ۵) رویداد کلان ≤۲س → یخ‌زده
last = {"ts": NOW - 3 * 86_400_000, "stance": "SHORT_BIAS", "score": -0.6,
        "t4": "up", "btc_px": 100.0}
r6 = ms.build(kget_factory("up", "up"),
              dom("down", "down", macro=[{"title": "FOMC", "in_hours": 1.5, "country": "USD"}]),
              {}, NOW, rows=[last])
check("۵", r6["stance"] == "SHORT_BIAS" and r6["trigger"] == "event-freeze"
      and r6["held"] and r6["raw_stance"] == "LONG_BIAS",
      "FOMC در ۱.۵س → موضع قبلی نگه داشته شد (یخ‌زده)")

# ۶) کف نگهداری ۲۴س در برابر تغییر ساختار
recent = {"ts": NOW - 5 * 3_600_000, "stance": "SHORT_BIAS", "score": -0.6,
          "t4": "up", "btc_px": 100.0}
r7 = ms.build(kget_factory("up", "up"), dom("down", "down"), {}, NOW, rows=[recent])
check("۶", r7["stance"] == "SHORT_BIAS" and r7["trigger"] == "min-hold" and r7["held"],
      "عبور مخالف ۵ ساعت بعد → نگه‌داشته (کف ۲۴س)")
recent_struct = dict(recent, t4="down")               # ساختار ۴س عوض شده
r8 = ms.build(kget_factory("up", "up"), dom("down", "down"), {}, NOW, rows=[recent_struct])
check("۶ب", r8["stance"] == "LONG_BIAS" and r8["trigger"] == "structure-change",
      "تغییر ساختار ۴س → همان لحظه عوض شد")

# ۷) کارنامه
few = [{"ts": NOW - 10 * 86_400_000, "stance": "LONG_BIAS", "btc_px": 90.0}] * 5
tr = ms.track_record(few, 100.0, NOW)
many = [{"ts": NOW - (8 + i) * 86_400_000,
         "stance": "LONG_BIAS" if i % 5 else "SHORT_BIAS", "btc_px": 90.0}
        for i in range(25)]
tr2 = ms.track_record(many, 100.0, NOW)
check("۷", tr["hit"] is None and "n=5" in tr["why"]
      and tr2["n"] == 25 and tr2["hit"] == 0.8 and tr2["ci"][0] < 0.8 < tr2["ci"][1],
      f"زیر ۲۰ بی‌عدد؛ با ۲۵ ثبت: اصابت {tr2['hit']} CI {tr2['ci']}")

# ۸) دفتر append-only
ms.write(r)                                            # first → ردیف
ms.write(ms.build(kget_factory("up", "up"), dom("down", "down"), {}, NOW + 60000,
                  rows=ms._ledger_rows()))            # unchanged → بدون ردیف
rows = ms._ledger_rows()
first_line = ms.LEDGER.read_text().splitlines()[0]
ms.write(ms.build(kget_factory("down", "down"), dom("up", "up"), {},
                  NOW + 2 * 86_400_000, rows=rows))  # structure-change → ردیف
check("۸", len(rows) == 1 and len(ms._ledger_rows()) == 2
      and ms.LEDGER.read_text().splitlines()[0] == first_line
      and json.loads(ms.OUT.read_text())["stance"] == "SHORT_BIAS",
      "دفتر: ۱ → ۲ ردیف، ردیف اول دست‌نخورده، خروجی به‌روز")

print()
if FAIL:
    print(f"{FAIL} آزمون شکست")
    sys.exit(1)
print("همهٔ ۱۰ آزمون موضع بازار گذشت")
