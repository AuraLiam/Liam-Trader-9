"""بک‌تست موتور داشبورد ۲.۰ (liam9_strategy.analyze) روی کندل واقعی.

دستور حمید (۲۰ اوت): «بک‌تست بگیر از سیستم جدید که به پنل اضافه کردیم» —
یعنی همین موتور سوینگ ۴س/۱س/۱۵د با دروازهٔ جدید جهت بازار (بستر BTC).
محاسبهٔ سنگین روی Actions اجرا می‌شود (dash-backtest.yml)، نه در نشست.

اصول همان h1_backtest است:
- بدون نگاه به آینده: هر تصمیم فقط با کندل‌های ≤ همان لحظه (۴س، ۱س، ۱۵د
  و بستر BTC همه بریده به t_now).
- لایهٔ تجربه خاموش (EXPERIENCE خالی) — استفاده‌اش در گذشته نگاه به آینده است.
- بدترین حالت درون‌کندلی: اگر در یک کندل هم استاپ هم تارگت لمس شد، استاپ.
- ضدهم‌پوشانی: بعد از هر معامله، از کندل بعدِ خروج ادامه می‌دهیم.
- R خالص از کارمزد ۰.۱۵٪ گزارش می‌شود؛ CI بوت‌استرپ ۹۵٪ تنها حکم است.
- ردشدن در سکوت ممنوع: علت هر NO_SIGNAL شمرده و در خروجی می‌آید (قیف).

خروجی: signals/dash-backtest.json

اجرا:  python3 -m hamid.dash_backtest --symbols 60 --bars 1000
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

import liam9_strategy as ST                            # noqa: E402

OUT = ROOT / "signals" / "dash-backtest.json"
FEE_PCT = ST.PARAMS["fee_round_trip_pct"]
MAX_HOLD = 96                     # ۹۶ کندل ۱۵د = ۲۴ ساعت؛ بعدش ستاپ مرده است
WARMUP = 300                      # ۱۵د لازم برای پولبک/ATR + شروع منصفانه


def _cd(rows):
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
             "l": float(k[3]), "c": float(k[4])} for k in rows]


def _cut(cd, t_now, lo=0):
    """اندیس اولین کندل بعد از t_now — برش بدون نگاه به آینده، خطی نه مربعی."""
    i = lo
    while i < len(cd) and cd[i]["t"] <= t_now:
        i += 1
    return i


def replay_symbol(sym, c15, c1h, c4h, btc1h=None, btc4h=None, step=1):
    """هر کندل ۱۵د جلو می‌رود؛ خروجی: (معامله‌ها، شمارش علت‌های رد)."""
    trades, reasons = [], {}
    p1 = p4 = pb1 = pb4 = 0
    i = WARMUP
    while i < len(c15) - 2:
        t_now = c15[i]["t"]
        p1 = _cut(c1h, t_now, p1)
        p4 = _cut(c4h, t_now, p4)
        w1, w4 = c1h[:p1], c4h[:p4]
        if len(w4) < 220 or len(w1) < 220:
            i += step
            continue
        wb1 = wb4 = None
        if btc1h and btc4h:
            pb1 = _cut(btc1h, t_now, pb1)
            pb4 = _cut(btc4h, t_now, pb4)
            wb1, wb4 = btc1h[:pb1], btc4h[:pb4]
        sig = ST.analyze(sym, w4, w1, c15[:i + 1], btc4h=wb4, btc1h=wb1)
        if sig["action"] == "NO_SIGNAL":
            key = str(sig.get("why", "?")).split("—")[0].strip()[:48]
            reasons[key] = reasons.get(key, 0) + 1
            i += step
            continue
        res = exit_px = None
        bars = 0
        for j in range(i + 1, min(i + 1 + MAX_HOLD, len(c15))):
            k = c15[j]
            bars = j - i
            if sig["action"] == "LONG":
                if k["l"] <= sig["sl"]:
                    res, exit_px = "stop", sig["sl"]
                    break
                if k["h"] >= sig["tp1"]:
                    res, exit_px = "target", sig["tp1"]
                    break
            else:
                if k["h"] >= sig["sl"]:
                    res, exit_px = "stop", sig["sl"]
                    break
                if k["l"] <= sig["tp1"]:
                    res, exit_px = "target", sig["tp1"]
                    break
        if res is None:
            res = "timeout"
            exit_px = c15[min(i + MAX_HOLD, len(c15) - 1)]["c"]
        risk = abs(sig["entry"] - sig["sl"])
        if risk <= 0:
            i += step
            continue
        r = ((exit_px - sig["entry"]) if sig["action"] == "LONG"
             else (sig["entry"] - exit_px)) / risk
        fee_r = (FEE_PCT / 100) * sig["entry"] / risk
        trades.append({"sym": sym, "dir": sig["action"], "outcome": res,
                       "R": round(r, 3), "R_net": round(r - fee_r, 3),
                       "quality": sig["quality"], "stop_pct": sig["stop_pct"],
                       "bars": bars, "opened": c15[i]["t"]})
        i += bars + 1                                  # ضدهم‌پوشانی
    return trades, reasons


def boot_ci(rs, n_boot=3000, seed=7):
    """CI ۹۵٪ بوت‌استرپ میانگین R — تنها حکم پذیرش (قانون CI)."""
    if len(rs) < 30:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(rs, k=len(rs))) / len(rs)
                   for _ in range(n_boot))
    return [round(means[int(n_boot * 0.025)], 3),
            round(means[int(n_boot * 0.975)], 3)]


def _agg(trades):
    if not trades:
        return {"n": 0}
    rs = [t["R_net"] for t in trades]
    wins = sum(1 for t in trades if t["outcome"] == "target")
    return {"n": len(trades), "win_pct": round(100 * wins / len(trades), 1),
            "mean_r_net": round(sum(rs) / len(rs), 3), "ci95": boot_ci(rs),
            "outcomes": {o: sum(1 for t in trades if t["outcome"] == o)
                         for o in ("target", "stop", "timeout")}}


def run(symbols=60, bars=1000, quiet=False):
    import sources
    ST.EXPERIENCE.clear()                              # ضد نگاه به آینده
    ST.ENV["margin_mode"] = None
    getattr(ST, "_LAST", {}).clear()                   # ضدتکرار از صفر (قطعیت)
    # sources.top_symbols همه‌جا نیست (رانر ۲۰ اوت با AttributeError مرد؛
    # تست محلی چون خودش این تابع را شبیه‌سازی می‌کرد عیب را نمی‌دید).
    # همان مسیر جایگزین اثبات‌شدهٔ h1_backtest:
    try:
        syms = sources.top_symbols(symbols)
    except Exception:                                  # noqa: BLE001
        from hamid.trainer import top_symbols
        syms = top_symbols(symbols)
    # بک‌تست باید همچنان رتبهٔ ۶۱+ را هم بسازد تا per_liquidity_tier قابل
    # پایش بماند — دروازهٔ نقدشوندگی (۲۱ اوت) فقط مسیر زندهٔ داشبورد را
    # می‌بندد، نه اندازه‌گیری خودمان را کور می‌کند.
    ST.TOP_LIQUIDITY.clear()
    ST.TOP_LIQUIDITY.update(s.upper() for s in syms)
    ST._TOP_LIQ_OK = True
    try:
        btc1 = _cd(sources.klines("BTCUSDT", "1h", 400))
        btc4 = _cd(sources.klines("BTCUSDT", "4h", 400))
    except Exception:                                  # noqa: BLE001
        btc1 = btc4 = None
    if not btc1 or not btc4:
        print("⚠️ بستر BTC نرسید — دروازهٔ بازار همهٔ آلت‌ها را رد می‌کند")
    all_trades, all_reasons, drops = [], {}, {}
    done = 0
    for rank, s in enumerate(syms, 1):
        try:
            c15 = _cd(sources.klines(s, "15m", bars))
            c1 = _cd(sources.klines(s, "1h", 400))
            c4 = _cd(sources.klines(s, "4h", 400))
        except Exception as e:                         # noqa: BLE001
            drops[type(e).__name__] = drops.get(type(e).__name__, 0) + 1
            continue
        if not c15 or not c1 or not c4 or len(c15) < WARMUP + 50 \
                or len(c1) < 260 or len(c4) < 260:
            drops["سری کوتاه"] = drops.get("سری کوتاه", 0) + 1
            continue
        tr, rs = replay_symbol(s, c15, c1, c4, btc1h=btc1, btc4h=btc4)
        for t in tr:
            t["rank"] = rank            # ردهٔ حجم ۴۸س — برای تفکیک نقدشوندگی
        all_trades += tr
        for k, v in rs.items():
            all_reasons[k] = all_reasons.get(k, 0) + v
        done += 1
        if not quiet and done % 10 == 0:
            print(f"  {done}/{len(syms)} نماد — {len(all_trades)} معامله",
                  flush=True)
    per_dir = {d: _agg([t for t in all_trades if t["dir"] == d])
               for d in ("LONG", "SHORT")}
    # تفکیک نقدشوندگی (پروتکل بک‌تست): مقایسهٔ ۶۰نمادی و ۱۲۰نمادیِ ۲۰ اوت
    # نشان داد گسترش دامنه میانگین را رقیق کرد — این تفکیک همان فرضیه را
    # با CI جدا می‌سنجد؛ محدود کردن دامنهٔ زنده فقط بعد از CI روشن.
    per_tier = {"top60": _agg([t for t in all_trades if t.get("rank", 999) <= 60]),
                "rank61plus": _agg([t for t in all_trades if t.get("rank", 0) > 60])}
    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "engine": ST.PARAMS["version"], "tf": "15m",
           "market_gate": "on", "experience_layer": "off (ضد نگاه به آینده)",
           "symbols": done, "skipped": sum(drops.values()),
           "drop_reasons": drops, "bars_15m": bars,
           "overall": _agg(all_trades), "per_direction": per_dir,
           "per_liquidity_tier": per_tier,
           "rejection_funnel": dict(sorted(all_reasons.items(),
                                           key=lambda x: -x[1])[:12]),
           "note": ("کندل واقعی، بدون نگاه به آینده، R خالص از کارمزد "
                    f"{FEE_PCT}٪؛ حکم فقط با CI ۹۵٪ بالای صفر (قانون CI)")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        o = res["overall"]
        print(f"\nنمادها: {done} · معامله: {o.get('n', 0)}")
        if o.get("n"):
            print(f"برد: {o['win_pct']}٪ · میانگین R خالص: {o['mean_r_net']:+.3f}"
                  f" · CI95: {o['ci95']}")
        print(f"نوشته شد: {OUT}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=60)
    ap.add_argument("--bars", type=int, default=1000)
    args = ap.parse_args()
    run(symbols=args.symbols, bars=args.bars)
