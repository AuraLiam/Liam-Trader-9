"""بک‌تست میز اسکلپ ۱ دقیقهٔ داشبورد (liam9_strategy.scalp_decide) با E08/E09.

دستور حمید (۲۰ اوت): اسکلپ ۱ دقیقه به داشبورد اضافه شد؛ الان با تأیید
اردر بلاک (E08، خودکفا) و هندسهٔ کندل نسخه‌دار (E09) — هر دو باید اثرشان
با عدد سنجیده شود، نه فقط اضافه شده باشند. محاسبهٔ سنگین روی Actions.

اصول همان dash_backtest است:
- بدون نگاه به آینده: تصمیم فقط با c1m[:i+1].
- لایهٔ تجربه و ضدتکرار از صفر شروع می‌شوند (قطعیت، ضد نگاه به آینده).
- بدترین حالت درون‌کندلی، ضدهم‌پوشانی، R خالص از کارمزد، CI بوت‌استرپ.
- هر معامله برچسب می‌گیرد: ob_bonus (اردر بلاک هم‌جهت تازه نزدیک ورود بود؟)
  و candle_align (کندل قبلی هم‌جهت/مخالف/خنثی بود؟) — تا اثر واقعیِ این دو
  انجین با CI جدا سنجیده شود، نه فقط ادعا شود که «اضافه شدند».

محدودیت دادهٔ صادقانه: صرافی‌ها کندل ۱ دقیقه را فقط چند صد تا عقب می‌دهند
(این‌جا حداکثر `--bars`، پیش‌فرض ۱۰۰۰ ≈ ۱۶.۷ ساعت اخیر). نمونهٔ ۱ دقیقه‌ای
همیشه از سوینگ کوچک‌تر خواهد بود — این محدودیت دیتاست است، نه دروازه.

خروجی: signals/scalp-dash-backtest.json

اجرا:  python3 -m hamid.scalp_dash_backtest --symbols 60 --bars 1000
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

OUT = ROOT / "signals" / "scalp-dash-backtest.json"
FEE_PCT = ST.SCALP["fee_round_trip_pct"]
MAX_HOLD = ST.SCALP["hold_bars"]          # ~۴۵ دقیقه؛ بعدش ستاپ مرده است
WARMUP = 145                              # ۹۰ (خود اسکلپ) + ۲۰ حاشیه بر لوک‌بک OB (۱۲۰)


def _cd(rows):
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
             "l": float(k[3]), "c": float(k[4])} for k in rows]


def replay_symbol(sym, c1m, step=1):
    """هر کندل ۱ دقیقه جلو می‌رود؛ خروجی: (معامله‌ها، شمارش علت‌های رد)."""
    trades, reasons = [], {}
    i = WARMUP
    while i < len(c1m) - 2:
        sig = ST.scalp_decide(c1m[:i + 1], sym)
        if sig["action"] == "NO_SIGNAL":
            key = str(sig.get("why", "?")).split("—")[0].strip()[:48]
            reasons[key] = reasons.get(key, 0) + 1
            i += step
            continue
        res = exit_px = None
        bars = 0
        for j in range(i + 1, min(i + 1 + MAX_HOLD, len(c1m))):
            k = c1m[j]
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
            exit_px = c1m[min(i + MAX_HOLD, len(c1m) - 1)]["c"]
        risk = abs(sig["entry"] - sig["sl"])
        if risk <= 0:
            i += step
            continue
        r = ((exit_px - sig["entry"]) if sig["action"] == "LONG"
             else (sig["entry"] - exit_px)) / risk
        fee_r = (FEE_PCT / 100) * sig["entry"] / risk
        ob = sig.get("order_block")
        trades.append({"sym": sym, "dir": sig["action"], "outcome": res,
                       "R": round(r, 3), "R_net": round(r - fee_r, 3),
                       "quality": sig["quality"], "stop_pct": sig["stop_pct"],
                       "bars": bars, "opened": c1m[i]["t"],
                       "session": sig.get("session"),
                       "candle_align": sig.get("pattern_align"),
                       "ob_bonus": bool(ob and ob.get("fresh")
                                       and ob.get("dist_pct", 99) <= 0.6)})
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
    ST._LAST.clear()                                    # ضدتکرار از صفر (قطعیت)
    try:
        syms = sources.top_symbols(symbols)
    except Exception:                                  # noqa: BLE001
        from hamid.trainer import top_symbols
        syms = top_symbols(symbols)

    all_trades, all_reasons, drops = [], {}, {}
    done = 0
    for s in syms:
        try:
            c1m = _cd(sources.klines(s, "1m", bars))
        except Exception as e:                         # noqa: BLE001
            drops[type(e).__name__] = drops.get(type(e).__name__, 0) + 1
            continue
        if not c1m or len(c1m) < WARMUP + 50:
            drops["سری کوتاه"] = drops.get("سری کوتاه", 0) + 1
            continue
        tr, rs = replay_symbol(s, c1m)
        all_trades += tr
        for k, v in rs.items():
            all_reasons[k] = all_reasons.get(k, 0) + v
        done += 1
        if not quiet and done % 10 == 0:
            print(f"  {done}/{len(syms)} نماد — {len(all_trades)} معامله",
                  flush=True)

    per_dir = {d: _agg([t for t in all_trades if t["dir"] == d])
               for d in ("LONG", "SHORT")}
    # اثر واقعیِ E08 (اردر بلاک) و E09 (هندسهٔ کندل) — نه فقط «اضافه شدند»
    per_ob = {"with_ob": _agg([t for t in all_trades if t["ob_bonus"]]),
              "without_ob": _agg([t for t in all_trades if not t["ob_bonus"]])}
    per_candle = {a: _agg([t for t in all_trades if t["candle_align"] == a])
                 for a in ("with", "against", None)}
    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "engine": ST.PARAMS["version"], "tf": "1m",
           "experience_layer": "off (ضد نگاه به آینده)",
           "symbols": done, "skipped": sum(drops.values()),
           "drop_reasons": drops, "bars_1m": bars,
           "data_note": (f"کندل ۱ دقیقهٔ صرافی حداکثر ~{bars} تا عقب می‌رود "
                         f"(~{bars / 60:.1f} ساعت)؛ نمونه ذاتاً کوچک‌تر از "
                         "سوینگ است — محدودیت دیتاست، نه دروازه"),
           "overall": _agg(all_trades), "per_direction": per_dir,
           "order_block_effect": per_ob,
           "candle_evidence_effect": {str(k): v for k, v in per_candle.items()},
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
