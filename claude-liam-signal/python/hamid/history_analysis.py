"""تحلیل عمیق دفتر بک‌تست ۳ ساله (دستور حمید، شب ۲۶ اوت: «زیر و رو کن»).

ورودی: تکه‌های خام history_backtest (artifact bt3y-shard-*).
خروجی:
- brain/research/history/backtest3y_trades.json.gz — کل دفتر معامله‌ها،
  فشرده، تا هر تحلیل بعدی محلی و بدون رانر باشد.
- brain/research/history/backtest3y_analysis.json — برش‌هایی که حکمِ
  «کجا می‌بازیم و کجا نه» را می‌دهند: ناخالص در برابر خالص (آیا لبهٔ
  ناخالص هست و کارمزد می‌خوردش؟ — همان بیماری شوک/اسکلپ)، سطل کیفیت،
  سطل پهنای استاپ (سهم کارمزد)، ردهٔ نقدشوندگی (رتبهٔ universe لپ‌تاپ)،
  سال×جهت، و ماهانه.

حکم فقط با CI ۹۵٪ (قانون CI)؛ سطل زیر ۳۰ معامله CI ندارد و ادعا نمی‌کند.

اجرا:  python3 -m hamid.history_analysis --shards <dir> [--universe <json>]
"""
import argparse
import gzip
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid.dash_backtest import boot_ci                # noqa: E402

HDIR = ROOT / "brain" / "research" / "history"
OUT_TRADES = HDIR / "backtest3y_trades.json.gz"
OUT_ANALYSIS = HDIR / "backtest3y_analysis.json"
UNIVERSE = HDIR / "meta" / "universe.json"

QUALITY_BINS = [(0, 60), (60, 70), (70, 80), (80, 101)]
STOP_BINS = [(0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 99.0)]


def load_shards(shards_dir):
    trades = []
    for p in sorted(Path(shards_dir).rglob("*.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                              # noqa: BLE001
            continue
        if "trades" in j and "shard" in j:
            trades += j["trades"]
    return trades


def agg2(trades):
    """میانگین ناخالص و خالص با CI هر دو — تا «کارمزد می‌خورَدش» قابل
    دیدن باشد، نه فقط نتیجهٔ نهایی."""
    if not trades:
        return {"n": 0}
    rs_g = [t["R"] for t in trades]
    rs_n = [t["R_net"] for t in trades]
    wins = sum(1 for t in trades if t["outcome"] == "target")
    return {"n": len(trades), "win_pct": round(100 * wins / len(trades), 1),
            "mean_r_gross": round(sum(rs_g) / len(rs_g), 3),
            "ci95_gross": boot_ci(rs_g),
            "mean_r_net": round(sum(rs_n) / len(rs_n), 3),
            "ci95_net": boot_ci(rs_n),
            "mean_fee_r": round(sum(g - n for g, n in zip(rs_g, rs_n))
                                / len(rs_g), 3)}


def _ym(ms):
    return time.strftime("%Y-%m", time.gmtime(ms / 1000))


def _year(ms):
    return time.gmtime(ms / 1000).tm_year


def analyze(trades, universe_path=None):
    res = {"generated": int(time.time() * 1000),
           "overall": agg2(trades),
           "per_direction": {d: agg2([t for t in trades if t["dir"] == d])
                             for d in ("LONG", "SHORT")}}
    res["per_quality"] = {
        f"{lo}-{hi - 1}": agg2([t for t in trades
                                if lo <= (t.get("quality") or 0) < hi])
        for lo, hi in QUALITY_BINS}
    res["per_stop_pct"] = {
        f"{lo}-{hi}%": agg2([t for t in trades
                             if lo <= (t.get("stop_pct") or 0) < hi])
        for lo, hi in STOP_BINS}
    years = sorted({_year(t["opened"]) for t in trades})
    res["per_year_direction"] = {
        f"{y}_{d}": agg2([t for t in trades
                          if _year(t["opened"]) == y and t["dir"] == d])
        for y in years for d in ("LONG", "SHORT")}
    res["monthly"] = {}
    for t in trades:
        res["monthly"].setdefault(_ym(t["opened"]), []).append(t)
    res["monthly"] = {m: {"n": len(v),
                          "mean_r_net": round(sum(x["R_net"] for x in v)
                                              / len(v), 3)}
                      for m, v in sorted(res["monthly"].items())}
    # ردهٔ نقدشوندگی از universe لپ‌تاپ (رتبهٔ حجم در لحظهٔ ضبط)
    upath = Path(universe_path) if universe_path else UNIVERSE
    if upath.is_file():
        uni = json.loads(upath.read_text(encoding="utf-8"))
        rank = {s["symbol"]: s.get("rank") for s in uni.get("symbols", [])
                if isinstance(s, dict)}
        res["per_liquidity"] = {
            "rank1_60": agg2([t for t in trades
                              if (rank.get(t["sym"]) or 999) <= 60]),
            "rank61plus": agg2([t for t in trades
                                if (rank.get(t["sym"]) or 999) > 60]),
            "note": "رتبهٔ universe.json لپ‌تاپ — لحظهٔ ضبط، نه تاریخی"}
    # پراکندگی نمادها: بهترین/بدترین با نمونهٔ کافی
    per_sym = {}
    for t in trades:
        per_sym.setdefault(t["sym"], []).append(t["R_net"])
    scored = [{"sym": s, "n": len(v),
               "mean_r_net": round(sum(v) / len(v), 3), "ci95": boot_ci(v)}
              for s, v in per_sym.items() if len(v) >= 100]
    scored.sort(key=lambda x: -x["mean_r_net"])
    res["symbols_best"] = scored[:10]
    res["symbols_worst"] = scored[-10:][::-1]
    res["symbols_net_positive_ci"] = [
        x for x in scored if x["ci95"] and x["ci95"][0] > 0]
    res["note"] = ("برش‌های دفتر ۳ ساله؛ حکم فقط با CI ۹۵٪. سطل n<30 "
                   "CI ندارد و ادعا نمی‌کند (قانون CI).")
    return res


def run(shards_dir, out_analysis=None, out_trades=None, universe_path=None):
    trades = load_shards(shards_dir)
    if not trades:
        raise SystemExit(f"هیچ معامله‌ای در {shards_dir} نیست")
    out_trades = Path(out_trades) if out_trades else OUT_TRADES
    out_analysis = Path(out_analysis) if out_analysis else OUT_ANALYSIS
    out_trades.parent.mkdir(parents=True, exist_ok=True)
    out_trades.write_bytes(gzip.compress(
        json.dumps(trades, ensure_ascii=False).encode("utf-8"), 9))
    res = analyze(trades, universe_path)
    res["trades_file"] = str(out_trades.relative_to(ROOT)) \
        if str(out_trades).startswith(str(ROOT)) else str(out_trades)
    out_analysis.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    o = res["overall"]
    print(f"{o['n']} معامله · ناخالص {o['mean_r_gross']:+.3f} {o['ci95_gross']}"
          f" · خالص {o['mean_r_net']:+.3f} {o['ci95_net']}"
          f" · کارمزد {o['mean_fee_r']:.3f}R/معامله")
    print(f"نوشته شد: {out_analysis} + {out_trades}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--trades-out", default=None)
    ap.add_argument("--universe", default=None)
    a = ap.parse_args()
    run(a.shards, out_analysis=a.out, out_trades=a.trades_out,
        universe_path=a.universe)
