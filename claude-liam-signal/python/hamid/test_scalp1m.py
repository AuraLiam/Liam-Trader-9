"""پاسبان موتور قطعیِ ۱ دقیقه و کانال آپدیت تحلیل. آفلاین.

دو خطرِ اصلیِ این ساختار، و همان‌ها بیشترِ بررسی‌های این‌جا هستند:

۱. **دورزدنِ دروازه‌ها** — کانالِ آپدیت اگر بتواند اطمینان را بالا ببرد
   یا سیگنالی بسازد، عملاً یک درِ پشتی است: هر ستاپی که موتور رد کرده
   با یک پیام قبول می‌شود. پس این‌جا اثبات می‌شود که کانال **فقط**
   محدودکننده است، در هر دو لایه (`analysis_push` و `liam9_link.apply`).

۲. **عددِ ساختگی** — «احتمال» باید از شمارش بیاید. نمونهٔ کم باید
   `p=None` بدهد، نه یک عددِ قانع‌کننده.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
from hamid import scalp1m as S1                      # noqa: E402
from hamid import analysis_push as AP                # noqa: E402
import liam9_link as LINK                            # noqa: E402

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


NOW = int(time.time() * 1000)


def candles(n, start=100.0, step=0.05, tf_ms=60_000, end_ms=None):
    """سری صعودی ساده — برای آزمونِ دروازه‌ها، نه برای ادعای عملکرد."""
    end = end_ms or NOW
    out = []
    for i in range(n):
        c = start + step * i
        out.append({"t": end - (n - 1 - i) * tf_ms, "o": c - step / 2,
                    "h": c + step, "l": c - step, "c": c, "v": 1000.0})
    return out


def kget(sym, tf, n):
    ms = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
          "1h": 3_600_000, "4h": 14_400_000}[tf]
    return candles(max(n, 200), tf_ms=ms)


print("— دروازهٔ ۱: دادهٔ ناقص یا بیات = NO_SIGNAL:")
d = S1.decide("XUSDT", candles(10), kget)
check("کندل کم → NO_SIGNAL با دلیل", d["decision"] == "NO_SIGNAL"
      and d["gate"] == "data", str(d)[:120])
stale = candles(300, end_ms=NOW - 900_000)
d = S1.decide("XUSDT", stale, kget, now_ms=NOW)
check("کندل بیات → دروازهٔ تازگی، نه عبورِ کور",
      d["gate"] == "freshness", d.get("gate"))
check("و دلیلش قانون ۱ را نام می‌برد", "قانون ۱" in d["why"])
check("دفتر خالیِ کندل → NO_SIGNAL نه crash",
      S1.decide("XUSDT", [], kget)["decision"] == "NO_SIGNAL")

print("\n— دروازهٔ دامیننس اجباری است (قانون ۳):")
ok, why, reg = S1.dominance_gate("LONG", dom={})
check("نبودِ رژیم → رد", not ok, why)
# ── شکلِ محصول، نه دیکشنری دست‌ساز (۶ سپتامبر) ────────────────────────
#
# تا امروز همهٔ فیکسچرهای این بخش کلید `structural` می‌ساختند، در حالی که
# تولیدکننده (`dominance.py:280`) `structure` می‌نویسد. آزمون سبز بود و
# دروازه روی فایل واقعی **همیشه** INSUFFICIENT می‌داد — یعنی میز اسکلپ
# ۱د صددرصد رد می‌کرد. کلاسِ «اسکریپت سبز ≠ محصول درست» (قانون ۶ سپتامبر):
# آزمون باید شکلِ خروجیِ واقعی را بخواند، نه شکلی که آرزو می‌کنیم.
_real = HERE.parents[2] / "signals" / "dominance.json"
if _real.exists():
    import json as _j
    _dom = _j.loads(_real.read_text(encoding="utf-8"))
    _reg = (_dom.get("structure") or {}).get("regime")
    check("فایل واقعی دامیننس رژیم را زیر کلید structure دارد",
          isinstance(_dom.get("structure"), dict) and _reg is not None, str(_reg))
    _ok, _why, _got = S1.dominance_gate("SHORT", _dom)
    check("دروازه روی فایلِ واقعی رژیم را می‌بیند، نه INSUFFICIENT",
          _got == _reg and _got not in ("INSUFFICIENT", "UNKNOWN"),
          f"{_got} · {_why}")
_src1m = (HERE / "scalp1m.py").read_text(encoding="utf-8")
check("و کد کلیدِ تولیدکننده را اول می‌خواند",
      'dom.get("structure") or dom.get("structural")' in _src1m)
ok, _, _ = S1.dominance_gate("LONG", {"structure": {"regime": "INSUFFICIENT"}})
check("رژیم INSUFFICIENT → رد، نه عبور", not ok)
ok, why, _ = S1.dominance_gate("LONG", {"structure": {"regime": "UNSAFE"}})
check("رویداد کلان UNSAFE → رد", not ok and "معلق" in why)
ok, _, _ = S1.dominance_gate("LONG", {"structure": {"regime": "BEARISH"}})
check("LONG در رژیم BEARISH → تعارض، رد", not ok)
ok, _, _ = S1.dominance_gate("SHORT", {"structure": {"regime": "BULLISH"}})
check("SHORT در رژیم BULLISH → تعارض، رد", not ok)
ok, _, _ = S1.dominance_gate("LONG", {"structure": {"regime": "BULLISH"}})
check("جهتِ هم‌سو با رژیم عبور می‌کند", ok)
d = S1.decide("XUSDT", candles(300), kget, dom={}, now_ms=NOW)
check("موتور بدون دادهٔ دامیننس سیگنال نمی‌سازد",
      d["decision"] == "NO_SIGNAL" and d["gate"] == "dominance", str(d.get("gate")))

print("\n— ترتیب سلسله‌مراتب رعایت شده (قانون ۰۰/۰۲):")
src = (PY / "hamid" / "scalp1m.py").read_text(encoding="utf-8")
order = [src.index(g) for g in ('_no("data"', '_no("dominance"',
                                '_no("trend"', '_no("htf"',
                                '_no("liquidity"', '_no("geometry"')]
check("دامیننس قبل از روند، روند قبل از ۱۵د، ۱۵د قبل از هندسه",
      order == sorted(order), str(order))
check("تایم پایین حق نقض بالادست را ندارد — صریح در کد",
      "قانون ۲" in src and "بالادست را نقض نمی‌کند" in src)
check("کندلِ باز حذف می‌شود (قانون ۱۰ بند ۱)",
      "c1m[:-1]" in src and "کندلِ باز" in src)
check("نقشهٔ نقدینگی اجباری است — نبودش رد",
      'return _no("liquidity"' in src)

print("\n— احتمال از شمارش می‌آید، نه از حدس:")
p = S1.probability(75, "LONG", ledger=[])
check("دفتر خالی → p=None", p["p"] is None, str(p))
check("و می‌گوید چرا (نمونهٔ کم)", "نمونهٔ سطل" in p["why"])
few = [{"R": 1.0, "why": {"stage": "scalp1m", "score": 75}}] * 10
check("نمونهٔ زیر کف → هنوز p=None حتی با ۱۰۰٪ برد",
      S1.probability(75, "LONG", ledger=few)["p"] is None)
many = ([{"R": 1.0, "why": {"stage": "scalp1m", "score": 75}}] * 30
        + [{"R": -1.0, "why": {"stage": "scalp1m", "score": 75}}] * 20)
got = S1.probability(75, "LONG", ledger=many)
check("نمونهٔ کافی → نرخ بردِ شمرده‌شده", got["p"] == 60.0, str(got))
check("و n گزارش می‌شود", got["n"] == 50)
other = S1.probability(45, "LONG", ledger=many)
check("سطلِ دیگر از نمونهٔ این سطل استفاده نمی‌کند", other["p"] is None,
      str(other))
check("سطل‌بندی یکنواخت است", S1._bucket(49) == "<50"
      and S1._bucket(95) == "90+" and S1._bucket(75) == "<80")

print("\n— کانال آپدیت: فقط محدودکننده (مهم‌ترین مرز):")
check("مثبت به صفر بریده می‌شود", AP.clamp(30) == 0.0)
check("منفیِ خیلی بزرگ سقف می‌خورد", AP.clamp(-999) == AP.MAX_DELTA)
check("غیرعدد → صفر، نه خطا", AP.clamp("بالا") == 0.0)
u = AP.build("btcusdt", note="x" * 900, avoid=True, confidence_delta=50)
check("ساختِ آپدیت: نماد بزرگ، یادداشت بریده، دلتا صفر",
      u["sym"] == "BTCUSDT" and len(u["note"]) == 400
      and u["confidence_delta"] == 0.0, str(u)[:150])

# لایهٔ دوم: خودِ liam9_link هم باید ببُرد
res = LINK.Link().apply([{"seq": 1, "type": "analysis", "sym": "BTCUSDT",
                              "confidence_delta": 99, "note": "n"}])
check("liam9_link هم مستقلاً مثبت را صفر می‌کند (دو لایه، نه یکی)",
      res[0]["confidence_delta"] == 0.0, str(res[0]))
res = LINK.Link().apply([{"seq": 2, "type": "analysis", "sym": "",
                              "note": "n"}])
check("آپدیت بی‌نماد پذیرفته نمی‌شود", not res[0]["ok"], str(res[0]))
check("analysis در فهرست سفید هست", "analysis" in LINK.ALLOWED)
check("و مرزهای ممنوعه دست‌نخورده‌اند",
      "enable_live" in LINK.FORBIDDEN and "set_leverage_cap" in LINK.FORBIDDEN)

lsrc = (PY / "liam9_link.py").read_text(encoding="utf-8")
check("سند خط امن می‌گوید این فرمان یک‌طرفه است", "یک‌طرفه" in lsrc)
asrc = (PY / "hamid" / "analysis_push.py").read_text(encoding="utf-8")
check("فرستنده هیچ میدانی برای بازکردن دروازه ندارد",
      "confidence_delta" in asrc and "avoid" in asrc
      and "allow" not in asrc.lower() and "force" not in asrc.lower())
check("موتور فقط دو اهرم را از آپدیت می‌خواند",
      src.count('upd["avoid"]') >= 1 and 'upd["confidence_delta"]' in src)
check("و اثرش روی امتیاز فقط کاهشی است (max با صفر)",
      'max(0.0, score + upd["confidence_delta"])' in src)

print("\n— آپدیت کهنه اثر ندارد:")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "a.json"
    AP.store(AP.build("XUSDT", "تازه", confidence_delta=-10,
                      now_ms=NOW), path=p)
    fresh = S1.analysis_for("XUSDT", now_ms=NOW, path=p)
    old = S1.analysis_for("XUSDT", now_ms=NOW + 2 * 3600_000, path=p)
    none = S1.analysis_for("YUSDT", now_ms=NOW, path=p)
check("آپدیت تازه خوانده می‌شود", fresh and fresh["confidence_delta"] == -10.0)
check("آپدیت کهنه‌تر از TTL نادیده می‌شود", old is None)
check("نمادِ دیگر آپدیت نمی‌گیرد", none is None)
check("فایل ناموجود → None، نه خطا",
      S1.analysis_for("X", path=Path("/nonexistent/a.json")) is None)

print("\n— مرز اجرای زنده:")
check("سند می‌گوید خروجی تصمیم است نه سفارش",
      "تصمیم است، نه سفارش" in src or "تصمیم است نه سفارش" in src)
check("LIVE_EXECUTION=false روی فایل نوشته شده", "LIVE_EXECUTION=false" in src)
check("موتور خودش هیچ سفارشی نمی‌فرستد",
      "requests" not in src and "urlopen" not in src)

print("\n— قیفِ رد قابل توضیح است:")
check("هر رد دلیلِ نوشته دارد",
      all(k in S1._no("g", "w") for k in ("gate", "why", "decision")))
check("و شمارشِ دلایل جمع می‌شود",
      S1._reasons([S1._no("a", "x"), S1._no("a", "y"), S1._no("b", "z")])
      == {"a": 2, "b": 1})

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان موتور ۱ دقیقه: هر {OK} بررسی سبز")
