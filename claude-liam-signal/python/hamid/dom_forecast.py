"""ناظر پیش‌بینی دامیننس — دستور حمید، ۱۷ اوت.

هر نوبتِ اتاق دامیننس (زنجیرهٔ رادار، گام مؤثر ~۳-۵ دقیقه) دو کار می‌کند:

۱. **صدور پیش‌بینی با دلیل** — تحلیلگر (کد قطعی، قانون ۰۶) برای USDT.D و
   BTC.D مسیر احتمالی ۳۰ و ۱۲۰ دقیقهٔ بعد را می‌گوید (UP/DOWN/FLAT) و
   موظف است دلایلش را بنویسد. «ایجنت» تأییدکننده همین‌جاست: پیش‌بینی
   جهت‌دار فقط با ≥۲ شاهد هم‌جهت و دادهٔ تازه (≤۱۰ دقیقه) ثبت می‌شود؛
   دادهٔ کهنه یا شواهد متضاد = NO_FORECAST (قانون ۱ — حدس ممنوع).

۲. **نمره‌دهی پیش‌بینی‌های سررسیدشده** — پیش‌بینی قبلی با حرکت واقعی
   سنجیده و در کارنامه ثبت می‌شود: تعداد، اصابت، درصد اصابت به تفکیک
   متریک و افق. خطا پنهان نمی‌شود — کارنامه روی signals/dominance.json
   می‌نشیند و پنل همان را نشان می‌دهد.

آستانه‌ها: حرکت واقعی = |Δ| ≥ NOISE واحد دامیننس؛ زیر آن FLAT است.
دفتر: brain/dom-forecasts.json (open + دنبالهٔ graded + score تجمیعی).
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
LEDGER = ROOT / "brain" / "dom-forecasts.json"

HORIZONS_MIN = (30, 120)
NOISE = 0.02          # واحد دامیننس؛ زیر این، حرکت نیست — لرزش است
FRESH_MS = 10 * 60000  # دادهٔ کهنه‌تر از ۱۰ دقیقه = پیش‌بینی ممنوع
KEEP_GRADED = 400      # دنبالهٔ کارنامه، برای عیب‌یابی


def _load():
    try:
        d = json.loads(LEDGER.read_text())
        return {"open": d.get("open") or [], "graded": d.get("graded") or [],
                "score": d.get("score") or {}}
    except Exception:                                # noqa: BLE001
        return {"open": [], "graded": [], "score": {}}


def _save(st):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    st["graded"] = st["graded"][-KEEP_GRADED:]
    LEDGER.write_text(json.dumps(st, ensure_ascii=False))


def _evidence(metric, chg1, chg4, trend1, trend4):
    """شواهد جهت‌دار؛ هر شاهد یک (جهت، دلیل فارسی)."""
    ev = []
    if chg1 is not None and abs(chg1) >= 0.05:
        ev.append(("UP" if chg1 > 0 else "DOWN",
                   f"دلتای ۱س {metric} = {chg1:+.3f}"))
    if chg4 is not None and abs(chg4) >= 0.15:
        ev.append(("UP" if chg4 > 0 else "DOWN",
                   f"دلتای ۴س {metric} = {chg4:+.3f}"))
    if trend1 in ("up", "down"):
        ev.append(("UP" if trend1 == "up" else "DOWN",
                   f"ساختار ۱س {metric}: {trend1}"))
    if trend4 in ("up", "down"):
        ev.append(("UP" if trend4 == "up" else "DOWN",
                   f"ساختار ۴س {metric}: {trend4}"))
    return ev


def make_forecast(points, struct, now_ms=None):
    """پیش‌بینی این نوبت؛ دلیل اجباری است. برمی‌گرداند لیست (شاید خالی)."""
    if not points:
        return []
    now = now_ms or int(time.time() * 1000)
    if now - points[-1]["t"] > FRESH_MS:
        return []                       # دادهٔ کهنه — قانون ۱
    su = (struct or {}).get("usdt") or {}
    sb = (struct or {}).get("btc_d") or {}

    def _chg(key, minutes):
        t0 = points[-1]["t"] - minutes * 60000
        past = min(points, key=lambda p: abs(p["t"] - t0))
        if abs(past["t"] - t0) > minutes * 60000:
            return None
        return round(points[-1][key] - past[key], 3)

    out = []
    for metric, key, s in (("USDT.D", "u", su), ("BTC.D", "b", sb)):
        t4 = s.get("trend_4h")
        t4 = t4 if t4 in ("up", "down", "range") else None
        ev = _evidence(metric, _chg(key, 60), _chg(key, 240),
                       s.get("trend_1h"), t4)
        ups = [r for d, r in ev if d == "UP"]
        downs = [r for d, r in ev if d == "DOWN"]
        if len(ups) >= 2 and not downs:
            path, reasons = "UP", ups
        elif len(downs) >= 2 and not ups:
            path, reasons = "DOWN", downs
        elif ev:
            path = "FLAT"
            reasons = [f"شواهد ناهم‌جهت یا ناکافی ({len(ups)}↑/{len(downs)}↓)"]
        else:
            path, reasons = "FLAT", ["هیچ شاهد جهت‌داری نیست"]
        for h in HORIZONS_MIN:
            out.append({"made": now, "due": now + h * 60000, "metric": metric,
                        "key": key, "horizon_min": h, "path": path,
                        "base": points[-1][key], "reasons": reasons})
    return out


def grade_due(st, points, now_ms=None):
    """پیش‌بینی‌های سررسیدشده را با واقعیت می‌سنجد و کارنامه را به‌روز می‌کند."""
    now = now_ms or int(time.time() * 1000)
    still, graded_now = [], 0
    for f in st["open"]:
        if f["due"] > now:
            still.append(f)
            continue
        actual = min(points, key=lambda p: abs(p["t"] - f["due"])) if points else None
        if actual is None or abs(actual["t"] - f["due"]) > 15 * 60000:
            f["result"] = "UNGRADABLE"   # دادهٔ آن لحظه را نداریم — جعل نمی‌کنیم
            st["graded"].append(f)
            continue
        delta = round(actual[f["key"]] - f["base"], 3)
        real = "FLAT" if abs(delta) < NOISE else ("UP" if delta > 0 else "DOWN")
        f["actual_delta"], f["real_path"] = delta, real
        f["result"] = "HIT" if real == f["path"] else "MISS"
        st["graded"].append(f)
        k = f"{f['metric']}|{f['horizon_min']}m"
        sc = st["score"].setdefault(k, {"n": 0, "hit": 0})
        sc["n"] += 1
        sc["hit"] += 1 if f["result"] == "HIT" else 0
        graded_now += 1
    st["open"] = still
    return graded_now


def scoreboard(st):
    out = {}
    for k, v in sorted(st["score"].items()):
        out[k] = {"n": v["n"], "hit": v["hit"],
                  "hit_pct": round(100 * v["hit"] / v["n"], 1) if v["n"] else None}
    return out


def update(points, struct, now_ms=None):
    """یک نوبت کامل: نمره‌دهی سررسیدها + صدور پیش‌بینی تازه. خروجی برای پنل."""
    st = _load()
    graded_now = grade_due(st, points, now_ms)
    # ضدتکرار درست (درس ۱۸ اوت): پیش‌بینی باز تا سررسیدش **دست‌نخورده می‌ماند**.
    # نسخهٔ اول تازه را جایگزین می‌کرد و چون زنجیره هر ~۳ دقیقه می‌چرخد،
    # هیچ پیش‌بینی‌ای به سررسید نمی‌رسید و کارنامه ابدی خالی می‌ماند.
    open_slots = {(f["metric"], f["horizon_min"]) for f in st["open"]}
    fresh = [f for f in make_forecast(points, struct, now_ms)
             if (f["metric"], f["horizon_min"]) not in open_slots]
    st["open"] += fresh
    _save(st)
    return {"made_now": [{k: f[k] for k in
                          ("metric", "horizon_min", "path", "reasons")}
                         for f in fresh],
            "graded_now": graded_now,
            "scoreboard": scoreboard(st),
            "open": len(st["open"])}
