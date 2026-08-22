"""بک‌تست بیگ‌مانی روی جهانِ نمادهای لیام — دستور حمید (۲۲ اوت):
«به‌صورت داشبورد اجراش کن، ازش استفاده کن، نتایج رو به‌صورت بک‌تست بگو».

فایل حمید (hamid.big_money) یک بک‌تست تک‌نمادی داشت؛ این‌جا روی جهانِ
نمادهای لیام (همان hamid.trainer.top_symbols که بقیهٔ بک‌تست‌های پروژه
استفاده می‌کنند) تکرار و معامله‌های اوت‌آف‌سمپلِ هر (ویژگی، افق) از همهٔ
نمادها روی هم ریخته می‌شود — همان الگوی CI بوت‌استرپ کل پروژه
(dash_backtest.py، scalp_dash_backtest.py)، به‌جای t-stat تک‌نمادی که
نمونه‌اش همیشه کوچک است.

بدون نگاه به آینده: جهت هر ویژگی فقط از نیمهٔ این‌سمپل هر نماد تعیین
می‌شود. هزینه: کارمزد دوسر لیام (۰.۱۵٪). حکم فقط با CI۹۵ بالای صفر
(قانون CI).

منبع داده Gate.io contract_stats است — فقط از Actions قابل‌دسترسی
(پروکسی این سندباکس صریحاً api.gateio.ws را می‌بندد).

خروجی: signals/big-money-backtest.json
اجرا:  python3 -m hamid.big_money_backtest --symbols 30
"""
import argparse
import json
import random
import time
from pathlib import Path

from hamid import big_money as BM

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "signals" / "big-money-backtest.json"


def boot_ci(rs, n_boot=3000, seed=7):
    if len(rs) < 30:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(rs, k=len(rs))) / len(rs) for _ in range(n_boot))
    return [round(means[int(n_boot * 0.025)], 4),
            round(means[int(n_boot * 0.975)], 4)]


def run(symbols=30, days=BM.BT_DAYS, cost_bps=BM.BT_COST_BPS, quiet=False):
    try:
        import sources
        syms = sources.top_symbols(symbols)
    except Exception:                                  # noqa: BLE001
        from hamid.trainer import top_symbols
        syms = top_symbols(symbols)

    pooled = {}          # (feature, horizon) -> list of oos trade returns (fraction)
    per_symbol = {}
    drops = {}
    done = 0
    to = int(time.time())
    frm = to - days * 86400
    interval, bar_secs = BM._tier(frm)

    first_error = None
    for sym in syms:
        # hamid.big_money مثل فایل اصلی حمید نماد خام می‌خواهد ("BTC")؛
        # top_symbols به قرارداد بایننس («BTCUSDT») برمی‌گردد. اجرای اول
        # روی Actions با ۳ از ۳ نماد CONTRACT_NOT_FOUND رد شد چون
        # contract=BTCUSDT_USDT ساخته می‌شد — همان کلاس عیبِ نگاشت نماد
        # که sources._under() قبلاً برایش راه‌حل داشت.
        bare = sym[:-4] if sym.upper().endswith("USDT") else sym
        try:
            rows = BM.fetch_stats(bare, interval, frm, to)
        except Exception as e:                         # noqa: BLE001
            key = type(e).__name__
            drops[key] = drops.get(key, 0) + 1
            if first_error is None:
                first_error = f"{sym}: {e}"
            continue
        rows = [r for r in rows if r["px"] > 0]
        if len(rows) < 200:
            drops["سری کوتاه"] = drops.get("سری کوتاه", 0) + 1
            continue
        out = BM.run_backtest(rows, cost_bps, bar_secs)
        per_symbol[sym] = {
            "n_bars": out["bars"], "tests": out["tests"],
            "best": ({k: v for k, v in out["best"].items() if k != "oos_trades"}
                     if out["best"] else None),
        }
        for r in out["results"]:
            key = (r["feature"], r["horizon"])
            pooled.setdefault(key, []).extend(r["oos_trades"])
        done += 1
        if not quiet and done % 5 == 0:
            print(f"  {done}/{len(syms)} نماد — آخرین: {sym}", flush=True)

    pooled_report = {}
    for (feat, hz), trades in pooled.items():
        wins = sum(1 for t in trades if t > 0)
        pooled_report[f"{feat}|{hz}"] = {
            "n": len(trades), "win_pct": round(100 * wins / len(trades), 1),
            "mean_pct_net": round(sum(trades) / len(trades) * 100, 4),
            "ci95_pct": boot_ci([t * 100 for t in trades]),
        }
    best_key = None
    for k, v in pooled_report.items():
        if v["ci95_pct"] and v["ci95_pct"][0] > 0:
            if best_key is None or v["mean_pct_net"] > pooled_report[best_key]["mean_pct_net"]:
                best_key = k

    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "engine": "E10 big-money-divergence", "source": "gate.io contract_stats",
           "symbols_tested": done, "symbols_skipped": sum(drops.values()),
           "drop_reasons": drops, "first_error_example": first_error,
           "interval": interval, "days": days,
           "cost_bps": cost_bps,
           "feature_defs": {k: {"label": lbl, "desc": d} for k, lbl, d in BM.BT_FEATURES},
           "pooled_oos": pooled_report,
           "ci_clears_zero": best_key,
           "per_symbol": per_symbol,
           "note": ("معامله‌های اوت‌آف‌سمپل همهٔ نمادها روی هم ریخته شد؛ حکم فقط "
                    "برای (ویژگی، افق) که CI۹۵ کاملاً بالای صفر است — بقیه بدون حکم")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        print(f"\nنمادها: {done} (رد‌شده: {sum(drops.values())})")
        for k, v in pooled_report.items():
            flag = "✓" if (v["ci95_pct"] and v["ci95_pct"][0] > 0) else " "
            print(f"  {flag} {k}: n={v['n']} win={v['win_pct']}% "
                  f"mean={v['mean_pct_net']:+.3f}% CI={v['ci95_pct']}")
        print(f"نوشته شد: {OUT}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=30)
    ap.add_argument("--days", type=int, default=BM.BT_DAYS)
    ap.add_argument("--cost-bps", type=float, default=BM.BT_COST_BPS)
    args = ap.parse_args()
    run(symbols=args.symbols, days=args.days, cost_bps=args.cost_bps)
