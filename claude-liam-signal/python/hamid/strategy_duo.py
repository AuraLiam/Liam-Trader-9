"""دو استراتژی جدای حمید روی دستگاه بک‌تست ۳ ساله (دستور ۲۶ اوت صبح).

«استراتژی‌های من یکی از ۴ساعته شروع می‌شد و بر اساس شکست سقف و کف بود و
یک استراتژی اردر بلاک — دو استراتژی جداست. فقط روند تحلیل کلی از ۴ساعته
تا ۱۵دقیقه ثابت است. ضریب را ۱۵ در نظر بگیر و پوزیشن‌هایی با ریوارد ۳
پیدا کن و کامل از هر دو جداگانه بک‌تست بگیر.»

بستر مشترک (ثابت، هر دو استراتژی): جهت از ۴س (EMA21/55) و ۱س باید
هم‌قصه باشند — تایم پایین حق نقض بالادست را ندارد (قانون ۲).

**break4h — شکست سقف/کف ۴ساعته**: سوینگ‌های تأییدشدهٔ ۴س (پیوت ۲کندله؛
تأیید فقط بعد از بسته‌شدن ۲ کندل بعدی — بی‌آینده). لانگ: کلوز ۱۵د از
آخرین سقف سوینگ ۴س عبور کند (کراس، نه ادامهٔ رد‌شده). استاپ پشت سطح
شکسته با حاشیهٔ ۱.۲×ATR۱۵د (ابطال ساختاری، قانون ۱۰). شورت قرینه.

**ob3 — اردر بلاک**: زون از liam9_strategy.order_block_zone روی پنجرهٔ
۱س، فقط زون تازه (مصرف‌نشده). ورود: کندل ۱۵د به زون نفوذ کند و در جهت
معامله بسته شود (ری‌تست + پس‌زدن). استاپ پشت لبهٔ دور زون + ۰.۵×ATR۱۵د.

هر دو: تارگت = ۳×ریسک · سقف نگهداری ۱۹۲ کندل (درس rr3) · **محافظ
لیکویید اهرم ۱۵**: استاپ٪ ≤ ۵۰÷۱۵ = ۳.۳۳٪ · **دام کارمزد**: سهم کارمزد
> ۰.۳R = رد (درس اسکلپ) · بدترین حالت درون‌کندلی · ضدهم‌پوشانی · R خالص
از کارمزد ۰.۱۵٪. اهرم در R اثر ندارد (درس ۲۴ اوت) — فقط قید استاپ و
مارجین است.

اجرا:  python3 -m hamid.strategy_duo --src <dir> --strategy break4h \
         --shard 0 --shards 8 --out /tmp/s0.json
ادغام همان hamid.history_backtest --merge است (اسکیمای تکه یکی است).
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
from hamid.dash_backtest import _cut                   # noqa: E402
from hamid.history_backtest import (                   # noqa: E402
    MIN_15M, WARMUP, ok_symbols, resample)

FEE_PCT = ST.PARAMS["fee_round_trip_pct"]
RR = 3.0
LEV = 15.0
LIQ_GUARD = 50.0
MAX_STOP_PCT = LIQ_GUARD / LEV                 # 3.333٪
MAX_FEE_R = 0.30
HOLD = 192
WHTF = 400
W15 = 600
PIVOT_K = 2


def trend_dir(w4, w1):
    """بستر ثابت ۴س→۱س: هر دو هم‌قصه → LONG/SHORT؛ غیر آن None."""
    if len(w4) < 60 or len(w1) < 60:
        return None
    c4 = [k["c"] for k in w4]
    c1 = [k["c"] for k in w1]
    e4a, e4b = ST.ema(c4, 21), ST.ema(c4, 55)
    e1a, e1b = ST.ema(c1, 21), ST.ema(c1, 55)
    if None in (e4a, e4b, e1a, e1b):
        return None
    if e4a > e4b and e1a > e1b:
        return "LONG"
    if e4a < e4b and e1a < e1b:
        return "SHORT"
    return None


def confirmed_swings(w4, k=PIVOT_K):
    """آخرین سقف و کف سوینگ تأییدشدهٔ ۴س — پیوت i فقط وقتی که k کندل
    بعدش هم بسته شده باشند (یعنی تا انتهای پنجره موجودند: بی‌آینده)."""
    hi = lo = None
    for i in range(k, len(w4) - k):
        win = w4[i - k:i + k + 1]
        oth_h = max(x["h"] for j, x in enumerate(win) if j != k)
        oth_l = min(x["l"] for j, x in enumerate(win) if j != k)
        # اکیداً بالاتر/پایین‌تر — سقف‌های مساویِ رنج، سوینگ نیستند
        if w4[i]["h"] > oth_h:
            hi = w4[i]["h"]
        if w4[i]["l"] < oth_l:
            lo = w4[i]["l"]
    return hi, lo


def sig_break4h(direction, w4, ls, a15):
    """شکست سقف/کف ۴س با کلوز ۱۵د — کراس، نه ادامهٔ ردشده."""
    hi, lo = confirmed_swings(w4)
    c_now, c_prev = ls[-1]["c"], ls[-2]["c"]
    if direction == "LONG" and hi is not None \
            and c_now > hi and c_prev <= hi:
        return {"entry": c_now, "sl": hi - 1.2 * a15, "level": hi}
    if direction == "SHORT" and lo is not None \
            and c_now < lo and c_prev >= lo:
        return {"entry": c_now, "sl": lo + 1.2 * a15, "level": lo}
    return None


def sig_ob3(direction, w1, ls, a15):
    """ری‌تست اردر بلاک تازهٔ ۱س + کلوز هم‌جهت ۱۵د."""
    zone = ST.order_block_zone(w1, direction)
    if not zone or not zone.get("fresh"):
        return None
    k = ls[-1]
    if direction == "LONG":
        if k["l"] <= zone["hi"] and k["c"] > zone["hi"] \
                and k["c"] > k["o"]:
            return {"entry": k["c"], "sl": zone["lo"] - 0.5 * a15,
                    "level": zone["hi"]}
    else:
        if k["h"] >= zone["lo"] and k["c"] < zone["lo"] \
                and k["c"] < k["o"]:
            return {"entry": k["c"], "sl": zone["hi"] + 0.5 * a15,
                    "level": zone["lo"]}
    return None


STRATEGIES = {"break4h": sig_break4h, "ob3": sig_ob3}


def replay(strategy, sym, c15, c1h, c4h, step=1):
    """حلقهٔ ریپلی مشترک — پنجرهٔ لغزان، بی‌آینده، بدترین حالت درون‌کندلی."""
    fn = STRATEGIES[strategy]
    trades, reasons = [], {}

    def rej(key):
        reasons[key] = reasons.get(key, 0) + 1

    p1 = p4 = 0
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
        ls = c15[max(0, i + 1 - W15):i + 1]
        d = trend_dir(w4, w1)
        if d is None:
            rej("بستر ۴س/۱س هم‌قصه نیست")
            i += step
            continue
        a15 = ST.atr(ls[-120:]) or 0
        if a15 <= 0:
            rej("ATR نامعتبر")
            i += step
            continue
        sig = fn(d, w4 if strategy == "break4h" else w1, ls, a15)
        if not sig:
            rej("ماشهٔ ورود نیست")
            i += step
            continue
        entry, sl = sig["entry"], sig["sl"]
        risk = (entry - sl) if d == "LONG" else (sl - entry)
        if risk <= 0:
            rej("ریسک نامعتبر")
            i += step
            continue
        stop_pct = risk / entry * 100
        if stop_pct > MAX_STOP_PCT:
            rej(f"محافظ لیکویید اهرم {LEV:g} (استاپ >{MAX_STOP_PCT:.2f}٪)")
            i += step
            continue
        fee_r = (FEE_PCT / 100) * entry / risk
        if fee_r > MAX_FEE_R:
            rej("دام کارمزد (سهم کارمزد >0.3R)")
            i += step
            continue
        tp = entry + RR * risk if d == "LONG" else entry - RR * risk
        res = exit_px = None
        bars = 0
        for j in range(i + 1, min(i + 1 + HOLD, len(c15))):
            k = c15[j]
            bars = j - i
            if d == "LONG":
                if k["l"] <= sl:
                    res, exit_px = "stop", sl
                    break
                if k["h"] >= tp:
                    res, exit_px = "target", tp
                    break
            else:
                if k["h"] >= sl:
                    res, exit_px = "stop", sl
                    break
                if k["l"] <= tp:
                    res, exit_px = "target", tp
                    break
        if res is None:
            res = "timeout"
            exit_px = c15[min(i + HOLD, len(c15) - 1)]["c"]
        r = ((exit_px - entry) if d == "LONG" else (entry - exit_px)) / risk
        trades.append({"sym": sym, "dir": d, "outcome": res,
                       "R": round(r, 3), "R_net": round(r - fee_r, 3),
                       "quality": None, "stop_pct": round(stop_pct, 3),
                       "bars": bars, "opened": c15[i]["t"]})
        i += bars + 1
    return trades, reasons


def run(src, strategy, shard=0, shards=1, out=None, step=1, quiet=False):
    if strategy not in STRATEGIES:
        raise SystemExit(f"استراتژی ناشناخته: {strategy}")
    out = Path(out) if out else \
        ROOT / "brain" / "research" / "history" / f"duo_{strategy}_{shard}.json"
    inv_path = out.parent / f"inventory_{strategy}_{shard}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    inv = history_ingest.ingest(src, out_path=inv_path, quiet=True)
    syms = ok_symbols(inv)
    if not syms:
        raise SystemExit(f"هیچ فایل ۱۵د سالمی در {src} نیست")
    mine = syms[shard::shards]
    all_trades, all_reasons, drops = [], {}, {}
    done, t0 = 0, time.time()
    for s in mine:
        c15 = history_ingest.load_klines(s, "15m", inv_path)
        if not c15 or len(c15) < MIN_15M:
            drops["سری کوتاه"] = drops.get("سری کوتاه", 0) + 1
            continue
        c1, c4 = resample(c15, 60), resample(c15, 240)
        if len(c1) < 260 or len(c4) < 260:
            drops["تایم بالا کوتاه"] = drops.get("تایم بالا کوتاه", 0) + 1
            continue
        tr, rs = replay(strategy, s, c15, c1, c4, step=step)
        all_trades += tr
        for k, v in rs.items():
            all_reasons[k] = all_reasons.get(k, 0) + v
        done += 1
        if not quiet:
            print(f"  [{strategy}/{shard}] {done}/{len(mine)} {s} — "
                  f"{len(all_trades)} معامله — {int(time.time() - t0)}s",
                  flush=True)
    res = {"generated": int(time.time() * 1000),
           "engine": f"duo-{strategy}-v1", "shard": shard, "shards": shards,
           "step": step, "w15": W15, "whtf": WHTF,
           "overrides": {"strategy": strategy, "rr": RR, "lev": LEV,
                         "max_stop_pct": round(MAX_STOP_PCT, 3)},
           "hold": HOLD, "symbols": done, "skipped": sum(drops.values()),
           "drop_reasons": drops, "trades": all_trades,
           "rejections": all_reasons}
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    if not quiet:
        print(f"تکهٔ {strategy}/{shard}: {done} نماد، "
              f"{len(all_trades)} معامله → {out}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--strategy", required=True, choices=sorted(STRATEGIES))
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(a.src, a.strategy, shard=a.shard, shards=a.shards, out=a.out,
        step=a.step)
