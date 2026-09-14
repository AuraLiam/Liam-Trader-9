"""آزمون آفلاین فاز ۲ دامیننس — ساختار مستقل USDT.D/BTC.D و دروازهٔ صداقت.

سری‌ها مصنوعی و بذردار (seed) هستند: روند نزولی/صعودی با پولبک، تا موتور
سوینگ چیزی برای شمردن داشته باشد. هیچ شبکه‌ای صدا زده نمی‌شود.

    python3 -m hamid.test_dominance
"""
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import dominance, premortem                        # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAIL += 1


T0 = (1_754_000_000_000 // 3_600_000) * 3_600_000     # هم‌تراز با سرِ ساعت


def mk_points(hours, slope, base=8.0, amp=0.08, per=5.0, b_slope=0.0, b_base=56.0):
    """نقطهٔ ۵دقیقه‌ای: روند خطی + موج سینوسی (پولبک‌ساز) — بدون تصادف."""
    pts = []
    for i in range(int(hours * 12)):
        h = i / 12.0
        u = base + slope * h + amp * math.sin(h / per)
        b = b_base + b_slope * h + amp * math.sin(h / per + 1.0)
        pts.append({"t": T0 + i * 300_000, "u": round(u, 4), "b": round(b, 4)})
    return pts


# ── کندل‌سازی از نقاط ───────────────────────────────────────────────────────
pts = mk_points(10, slope=-0.01)
bars = dominance._bars(pts, "u")
check("سطل آخرِ باز حذف می‌شود", len(bars) == 9)
check("o/h/l/c از خودِ نقاط سطل", bars[0]["o"] == pts[0]["u"]
      and bars[0]["c"] == pts[11]["u"]
      and bars[0]["h"] == max(p["u"] for p in pts[:12])
      and bars[0]["l"] == min(p["u"] for p in pts[:12]))
b4 = dominance._bars(pts, "u", 4 * 3_600_000)
check("کندل ۴س هم از همان نقاط ساخته می‌شود", 1 <= len(b4) <= 3)

# ── دروازهٔ صداقت: دادهٔ کم = INSUFFICIENT، نه حدس ─────────────────────────
st = dominance.structural(mk_points(30, slope=-0.01))
check("زیر ۶۰ کندل ۱س حکم ساختاری صادر نمی‌شود",
      st["regime"] == "INSUFFICIENT" and st["bars_1h"] < 60, str(st))
check("شمارش صریح در جواب هست", "کندل ۱س" in (st.get("note") or ""))

# ── رژیم‌ها ─────────────────────────────────────────────────────────────────
st_bull = dominance.structural(mk_points(300, slope=-0.01))
check("USDT.D ساختاراً نزولی → BULLISH",
      st_bull["regime"] == "BULLISH", str(st_bull.get("usdt")))
check("چرایی با روند ۱س", "۱س down" in (st_bull.get("why") or ""), st_bull.get("why"))

st_bear = dominance.structural(mk_points(300, slope=+0.01))
check("USDT.D ساختاراً صعودی → BEARISH",
      st_bear["regime"] == "BEARISH", str(st_bear.get("usdt")))

st_rng = dominance.structural(mk_points(300, slope=0.0, amp=0.05))
check("بدون جهت → RANGE (اعتراف، نه حدس)",
      st_rng["regime"] == "RANGE", str(st_rng.get("usdt")))

# خط روند در مختصاتِ پنجرهٔ برازش (ممیزی E03، ۸ سپتامبر): روی سری بلندتر
# از ۱۲۰ کندل، برون‌یابی با ایندکسِ کل آرایه حمایت را ۰.۲۵ واحد بالای قیمت
# می‌برد. خاصیت: حمایتِ نشکسته باید زیر/نزدیک قیمت باشد، نه ۳٪ بالاتر.
_long = dominance._bars(mk_points(300, slope=+0.01, amp=0.02), "u")
_ts = dominance._tf_struct(_long, dominance.MIN_BARS_1H)
if _ts.get("trendline"):
    _tl = __import__("hamid.structure", fromlist=["trendline"]).trendline(_long)
    _n = min(len(_long), dominance.TL_LOOKBACK)
    check("value_now = مقدار خط در آخرین کندلِ پنجرهٔ برازش، نه کل آرایه",
          abs(_ts["trendline"]["value_now"] - round(_tl.at(_n - 1), 3)) < 1e-9,
          str(_ts["trendline"]))
    check("(اثبات منفی) مختصاتِ کل آرایه عددِ دیگری می‌داد",
          len(_long) > dominance.TL_LOOKBACK
          and abs(_tl.at(len(_long) - 1) - _tl.at(_n - 1)) > 1e-6)
    if _ts["trendline"]["kind"] == "support" and not _ts["trendline"]["broken"]:
        check("حمایتِ نشکسته بالای قیمت نمی‌نشیند",
              _ts["trendline"]["value_now"] <= _ts["px"] * 1.01,
              f"{_ts['trendline']['value_now']} vs px {_ts['px']}")
else:
    check("(سری ساختگی خط نساخت — بررسی مختصات رد شد، نه شکست)", True)

st_uns = dominance.structural(mk_points(300, slope=-0.01),
                              macro=[{"title": "CPI", "in_hours": 1.5}])
check("رویداد کلان تا ۲ ساعت → UNSAFE با دلیل",
      st_uns["regime"] == "UNSAFE" and "CPI" in st_uns.get("unsafe_reason", ""))
st_far = dominance.structural(mk_points(300, slope=-0.01),
                              macro=[{"title": "CPI", "in_hours": 8}])
check("رویداد دور، رژیم را معلق نمی‌کند", st_far["regime"] == "BULLISH")

check("bars_4h گزارش می‌شود", st_bull.get("bars_4h", 0) >= 60
      or "INSUFFICIENT" in str(st_bull.get("usdt", {}).get("trend_4h")))

# ── دروازهٔ ۷ پیش‌مورتم: رژیم ساختاری با وزن ۲، دلتا فقط وقتی داده کم است ──
tmp = Path(tempfile.mkdtemp())
premortem.DOM = tmp / "dominance.json"


def quiet_c15(n=60, px=100.0):
    """کندل ۱۵د آرام و خنثی — تا فقط بند دامیننس فرق دو حالت را بسازد."""
    out = []
    for i in range(n):
        p = px + 0.03 * math.sin(i / 7.0)
        out.append({"t": T0 + i * 900_000, "o": p, "h": p + 0.05,
                    "l": p - 0.05, "c": p, "v": 10.0})
    return out


SIG = {"sym": "AUSDT", "dir": "LONG", "entry": 100.0, "sl": 99.0, "tp1": 102.0}

premortem.DOM.write_text(json.dumps(
    {"structure": {"regime": "BULLISH", "why": "USDT.D ساختار ۱س down"},
     "chg_1h": {"usdt": +0.5}}))          # دلتا عمداً مخالف است — نباید خوانده شود
rv = premortem.review(dict(SIG), quiet_c15())
check("رژیم ساختاری BULLISH → دلیل تارگتِ لانگ",
      any("رژیم ساختاری" in x for x in rv["pro"]), str(rv["pro"]))
check("با رژیم ساختاری، دلتای عددی دیگر شمرده نمی‌شود",
      not any("USDT.D در حال" in x for x in rv["con"]), str(rv["con"]))

premortem.DOM.write_text(json.dumps(
    {"structure": {"regime": "BEARISH", "why": "USDT.D ساختار ۱س up"}}))
rv2 = premortem.review(dict(SIG), quiet_c15())
check("رژیم BEARISH → دلیل استاپِ لانگ با وزن ۲",
      any("رژیم ساختاری" in x for x in rv2["con"])
      and rv2["con_w"] >= rv["con_w"] + 2, f"{rv2['con']} / con_w={rv2['con_w']}")

premortem.DOM.write_text(json.dumps(
    {"structure": {"regime": "INSUFFICIENT", "bars_1h": 12},
     "chg_1h": {"usdt": +0.5}}))
rv3 = premortem.review(dict(SIG), quiet_c15())
check("INSUFFICIENT → برگشت به دلتای عددی (وزن ۱)",
      any("USDT.D در حال رشد" in x for x in rv3["con"]), str(rv3["con"]))

# ── ممیزی ۱۴ سپتامبر: «تقویم در دسترس نبود» ≠ «تقویم خالی» ─────────────
from hamid import intel as _intel                               # noqa: E402
_saved_cal = _intel.calendar
try:
    class _E(Exception):
        code = 429
    def _boom():
        raise _E("rate")
    _intel.calendar = _boom
    _ev, _ok, _why = dominance.macro_events_status()
    check("شکست تقویم صریح برمی‌گردد: ok=False با علت و کد HTTP", _ev == [] and _ok is False and _why == "_E:429", str((_ev, _ok, _why)))
    check("سازگاری: macro_events() هنوز فهرست خالی می‌دهد", dominance.macro_events() == [])
    _intel.calendar = lambda: {"next_48h": [], "high_this_week": 0}
    _ev2, _ok2, _ = dominance.macro_events_status()
    check("تقویم خالیِ سالم: ok=True و فهرست خالی", _ev2 == [] and _ok2 is True)
    _intel.calendar = lambda: {"next_48h": [{"title": "CPI", "in_hours": 1.5, "country": "USD"},
                                            {"title": "Tea party", "in_hours": 1.0}]}
    _ev3, _ok3, _ = dominance.macro_events_status()
    check("فیلتر کلان همان است: فقط عنوانِ کلان می‌ماند", [e["title"] for e in _ev3] == ["CPI"], str(_ev3))
    _intel.calendar = lambda: {"next_48h": [{"title": "CPI", "in_hours": 1.5}], "cached": True,
                               "cache_age_min": 40, "source_error": "HTTPError:403 / HTTPError:403"}
    _ev4, _ok4, _why4 = dominance.macro_events_status()
    check("پاسخِ حافظه‌ای: رویدادها می‌مانند، ok=CACHED با سن و علتِ منبع",
          _ev4 and _ok4 == "CACHED" and "40" in _why4 and "403" in _why4, str((_ev4, _ok4, _why4)))
finally:
    _intel.calendar = _saved_cal

# حافظهٔ ۶ساعتهٔ خودِ intel.calendar — هر دو منبع ۴۰۳، حافظه تازه → پاسخِ برچسب‌دار
import time as _time                                            # noqa: E402
_sv = (_intel._json, _intel._tv_calendar, _intel.CAL_CACHE)
try:
    class _H(Exception):
        code = 403
    def _no(*a, **k):
        raise _H("blocked")
    _intel._json = _no; _intel._tv_calendar = _no
    with tempfile.TemporaryDirectory() as _td:
        _intel.CAL_CACHE = Path(_td) / "calendar-last.json"
        try:
            _intel.calendar(); _raised = False
        except Exception:
            _raised = True
        check("بی‌حافظه و بی‌منبع → استثنا (حدس نمی‌زند)", _raised)
        _fut = (_time.time() + 3600)
        import datetime as _dt
        _iso = _dt.datetime.fromtimestamp(_fut, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        _intel.CAL_CACHE.write_text(json.dumps({"generated": int(_time.time() * 1000) - 30 * 60000,
                                                "high": [{"title": "FOMC", "country": "USD", "date": _iso, "impact": "High"}]}), encoding="utf-8")
        _c = _intel.calendar()
        check("حافظهٔ ۳۰دقیقه‌ای: رویداد برمی‌گردد با cached/سن/علت", _c.get("cached") is True and _c.get("cache_age_min") == 30
              and "403" in _c.get("source_error", "") and _c["next_48h"][0]["title"] == "FOMC", str(_c))
        _intel.CAL_CACHE.write_text(json.dumps({"generated": int(_time.time() * 1000) - 7 * 3600 * 1000, "high": []}), encoding="utf-8")
        try:
            _intel.calendar(); _raised2 = False
        except Exception:
            _raised2 = True
        check("حافظهٔ ۷ساعته مرده است → استثنا", _raised2)
finally:
    _intel._json, _intel._tv_calendar, _intel.CAL_CACHE = _sv
_dsrc = Path(dominance.__file__).read_text(encoding="utf-8")
check("حکم دامیننس شکست تقویم را چاپ می‌کند و روی خروجی calendar_ok می‌نشیند",
      "calendar_ok" in _dsrc and "محافظ رویداد ≤۲س این نوبت کور است" in _dsrc)

print()
if FAIL:
    print(f"✗ {FAIL} آزمون شکست")
    sys.exit(1)
print("✓ همهٔ آزمون‌های دامیننس گذشت")
