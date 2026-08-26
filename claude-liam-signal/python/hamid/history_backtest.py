"""بک‌تست ۳ ساله: موتور داشبورد روی دادهٔ تاریخی درایو (دستور حمید، ۲۶ اوت).

حمید ۵۴۵ مگابایت کندل ۱۵دقیقهٔ ۲۹۸ ارز (اوت ۲۰۲۳ تا اوت ۲۰۲۶) را از
لپ‌تاپ به درایو داد؛ history-ingest آن را بایگانی کرد (artifact
aura-history). این ماژول همان موتور داشبورد (liam9_strategy.analyze،
عین dash_backtest) را روی کل آن سه سال می‌راند — تا حکم لبه از نمونهٔ
چندهفته‌ای به نمونهٔ سه‌ساله با رژیم‌های مختلف برسد.

فرق با dash_backtest فقط منبع داده است، نه منطق:
- ۱۵د مستقیم از فایل‌های باینری (history_ingest.load_klines).
- ۱س و ۴س از خودِ ۱۵د ساخته می‌شوند (resample) — درایو تایم بالا ندارد.
- برچسب زمانی هر کندل ساخته‌شده = زمانِ بازشدنِ آخرین کندل ۱۵د سازنده‌اش؛
  با همین قرارداد، کندل تایم بالا دقیقاً همان لحظه‌ای وارد پنجره می‌شود
  که همهٔ سازنده‌هایش دیده شده‌اند — نگاه به آینده ساختاراً ناممکن.
- پنجرهٔ لغزان (۶۰۰ کندل ۱۵د، ۴۰۰ کندل تایم بالا) عین شرایط زندهٔ
  داشبورد؛ بدون آن هر فراخوان analyze سه سال کندل می‌گرفت و هم کند می‌شد
  هم با شرایط زنده ناهمسنجه.

بقیه عین dash_backtest: تجربه خاموش، بدترین حالت درون‌کندلی، ضدهم‌پوشانی،
R خالص از کارمزد، حکم فقط CI ۹۵٪.

اجرا (رانر، تکه‌ای):  python3 -m hamid.history_backtest --src <dir> \
                        --shard 0 --shards 8 --out /tmp/shard0.json
ادغام:                python3 -m hamid.history_backtest --merge <dir> \
                        --out brain/research/history/backtest3y.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

import liam9_strategy as ST                            # noqa: E402
from hamid import history_ingest                       # noqa: E402
from hamid.dash_backtest import (                      # noqa: E402
    FEE_PCT, MAX_HOLD, WARMUP, _agg, _cut, boot_ci)

OUT = ROOT / "brain" / "research" / "history" / "backtest3y.json"
W15 = 600                     # پنجرهٔ ۱۵د مثل bars زندهٔ dash-backtest
WHTF = 400                    # پنجرهٔ ۱س/۴س مثل ۴۰۰ کندل زندهٔ داشبورد
MIN_15M = WARMUP + 50


def resample(c15, minutes):
    """کندل تایم بالا از ۱۵د — برچسب = بازشدنِ آخرین سازنده (بی‌آینده).

    هر سطل فقط از کندل‌هایی ساخته می‌شود که t آن‌ها ≤ برچسب خودش است؛
    پس وقتی _cut با t_now آن را وارد پنجره می‌کند، همهٔ داده‌اش از قبل
    دیده شده بوده. شکاف داده سطل را ناقص می‌کند ولی آینده وارد نمی‌کند."""
    ms = minutes * 60_000
    out, cur = [], None
    for k in c15:
        b = k["t"] // ms
        if cur is None or b != cur["b"]:
            if cur is not None:
                out.append({"t": cur["last"], "o": cur["o"], "h": cur["h"],
                            "l": cur["l"], "c": cur["c"], "v": cur["v"]})
            cur = {"b": b, "o": k["o"], "h": k["h"], "l": k["l"],
                   "c": k["c"], "v": 0.0, "last": k["t"]}
        cur["h"] = max(cur["h"], k["h"])
        cur["l"] = min(cur["l"], k["l"])
        cur["c"] = k["c"]
        cur["v"] += k.get("v") or 0.0
        cur["last"] = k["t"]
    if cur is not None:
        out.append({"t": cur["last"], "o": cur["o"], "h": cur["h"],
                    "l": cur["l"], "c": cur["c"], "v": cur["v"]})
    return out


def replay_windowed(sym, c15, c1h, c4h, btc1h=None, btc4h=None, step=1):
    """عین dash_backtest.replay_symbol با پنجرهٔ لغزان روی سری چندساله."""
    trades, reasons = [], {}
    p1 = p4 = pb1 = pb4 = 0
    i = WARMUP
    while i < len(c15) - 2:
        t_now = c15[i]["t"]
        p1 = _cut(c1h, t_now, p1)
        p4 = _cut(c4h, t_now, p4)
        w1 = c1h[max(0, p1 - WHTF):p1]
        w4 = c4h[max(0, p4 - WHTF):p4]
        if len(w4) < 220 or len(w1) < 220:
            i += step
            continue
        wb1 = wb4 = None
        if btc1h and btc4h:
            pb1 = _cut(btc1h, t_now, pb1)
            pb4 = _cut(btc4h, t_now, pb4)
            wb1 = btc1h[max(0, pb1 - WHTF):pb1]
            wb4 = btc4h[max(0, pb4 - WHTF):pb4]
        sig = ST.analyze(sym, w4, w1, c15[max(0, i + 1 - W15):i + 1],
                         btc4h=wb4, btc1h=wb1)
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


def _prep_engine(all_syms):
    ST.EXPERIENCE.clear()                              # ضد نگاه به آینده
    ST.ENV["margin_mode"] = None
    getattr(ST, "_LAST", {}).clear()
    ST.TOP_LIQUIDITY.clear()
    ST.TOP_LIQUIDITY.update(s.upper() for s in all_syms)
    ST._TOP_LIQ_OK = True


def ok_symbols(inv):
    """نمادهای ۱۵دِ سالم از شناسنامه — مرتب تا تکه‌بندی قطعی باشد."""
    out = []
    for key, e in inv["klines"].items():
        if e.get("status") == "OK" and key.endswith("_15m"):
            out.append(key.rsplit("_", 1)[0])
    return sorted(out)


def run(src, shard=0, shards=1, out=None, step=1, max_symbols=None,
        quiet=False):
    out = Path(out) if out else OUT
    inv_path = out.parent / f"inventory_shard{shard}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    inv = history_ingest.ingest(src, out_path=inv_path, quiet=True)
    syms = ok_symbols(inv)
    if not syms:
        raise SystemExit(f"هیچ فایل ۱۵د سالمی در {src} نیست")
    mine = syms[shard::shards]
    if max_symbols:
        mine = mine[:max_symbols]
    _prep_engine(syms)
    btc15 = history_ingest.load_klines("BTCUSDT", "15m", inv_path)
    btc1 = resample(btc15, 60) if btc15 else None
    btc4 = resample(btc15, 240) if btc15 else None
    if not btc1 or not btc4:
        print("⚠️ BTCUSDT در داده نیست — دروازهٔ بازار همهٔ آلت‌ها را رد می‌کند")
    all_trades, all_reasons, drops = [], {}, {}
    done, t_start = 0, time.time()
    for s in mine:
        c15 = history_ingest.load_klines(s, "15m", inv_path)
        if not c15 or len(c15) < MIN_15M:
            drops["سری کوتاه"] = drops.get("سری کوتاه", 0) + 1
            continue
        c1, c4 = resample(c15, 60), resample(c15, 240)
        if len(c1) < 260 or len(c4) < 260:
            drops["تایم بالا کوتاه"] = drops.get("تایم بالا کوتاه", 0) + 1
            continue
        tr, rs = replay_windowed(s, c15, c1, c4, btc1h=btc1, btc4h=btc4,
                                 step=step)
        all_trades += tr
        for k, v in rs.items():
            all_reasons[k] = all_reasons.get(k, 0) + v
        done += 1
        if not quiet:
            print(f"  [{shard}] {done}/{len(mine)} {s} — "
                  f"{len(all_trades)} معامله — "
                  f"{int(time.time() - t_start)}s", flush=True)
    res = {"generated": int(time.time() * 1000),
           "engine": ST.PARAMS["version"], "shard": shard, "shards": shards,
           "step": step, "w15": W15, "whtf": WHTF,
           "symbols": done, "skipped": sum(drops.values()),
           "drop_reasons": drops, "trades": all_trades,
           "rejections": all_reasons}
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    if not quiet:
        print(f"تکهٔ {shard}: {done} نماد، {len(all_trades)} معامله → {out}")
    return res


def _year(ms):
    return time.gmtime(ms / 1000).tm_year


def merge(shards_dir, out=None):
    """ادغام تکه‌ها → گزارش نهایی با CI کل/جهت/سال. حکم فقط با CI."""
    out = Path(out) if out else OUT
    trades, reasons = [], {}
    n_sym = n_skip = 0
    engines, files = set(), 0
    for p in sorted(Path(shards_dir).rglob("*.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                              # noqa: BLE001
            continue
        if "trades" not in j or "shard" not in j:
            continue
        files += 1
        trades += j["trades"]
        n_sym += j.get("symbols", 0)
        n_skip += j.get("skipped", 0)
        engines.add(j.get("engine"))
        for k, v in j.get("rejections", {}).items():
            reasons[k] = reasons.get(k, 0) + v
    if not files:
        raise SystemExit(f"هیچ تکه‌ای در {shards_dir} نیست")
    years = sorted({_year(t["opened"]) for t in trades})
    span = None
    if trades:
        ts = [t["opened"] for t in trades]
        span = [time.strftime("%Y-%m-%d", time.gmtime(min(ts) / 1000)),
                time.strftime("%Y-%m-%d", time.gmtime(max(ts) / 1000))]
    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "engine": sorted(e for e in engines if e), "tf": "15m",
           "source": "دادهٔ ۳ سالهٔ درایو (aura-history)",
           "market_gate": "on", "experience_layer": "off (ضد نگاه به آینده)",
           "shards": files, "symbols": n_sym, "skipped": n_skip,
           "trade_span": span,
           "overall": _agg(trades),
           "per_direction": {d: _agg([t for t in trades if t["dir"] == d])
                             for d in ("LONG", "SHORT")},
           "per_year": {str(y): _agg([t for t in trades
                                      if _year(t["opened"]) == y])
                        for y in years},
           "rejection_funnel": dict(sorted(reasons.items(),
                                           key=lambda x: -x[1])[:12]),
           "note": ("کندل واقعی ۳ ساله، ۱س/۴س بازسازی‌شده از ۱۵د با برچسبِ "
                    "بی‌آینده، پنجرهٔ لغزان عین شرایط زنده، R خالص از کارمزد "
                    f"{FEE_PCT}٪؛ حکم فقط با CI ۹۵٪ (قانون CI)")}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    o = res["overall"]
    print(f"ادغام {files} تکه: {o.get('n', 0)} معامله از {n_sym} نماد")
    if o.get("n"):
        print(f"برد {o['win_pct']}٪ · میانگین R خالص {o['mean_r_net']:+.3f}"
              f" · CI95 {o['ci95']}")
    print(f"نوشته شد: {out}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="ریشهٔ دادهٔ درایو (شامل klines/)")
    ap.add_argument("--merge", help="پوشهٔ تکه‌ها برای ادغام")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--max-symbols", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.merge:
        merge(a.merge, out=a.out)
    elif a.src:
        run(a.src, shard=a.shard, shards=a.shards, out=a.out, step=a.step,
            max_symbols=a.max_symbols)
    else:
        ap.error("--src یا --merge لازم است")
