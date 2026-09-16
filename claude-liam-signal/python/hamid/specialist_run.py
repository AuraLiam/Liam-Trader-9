#!/usr/bin/env python3
"""اجرای میز متخصصین: ۱۰۰۰ ترید بر متخصص، و چرخهٔ بهبودِ خارج-از-نمونه.

جدا از `specialist_lab.py` عمداً: آن‌جا **تعریفِ** دوازده استراتژی است
(قاعده‌ها، پارامترها، ایده‌ها) و این‌جا **اجرای** سنگین. تعریف را باید
بتوان بی‌اجرا خواند و آزمود.

## چرخهٔ بهبود — «خلاقیت»ی که قابل اثبات است

    تاریخِ هر ارز به دو نیمه بریده می‌شود:
      · نیمهٔ اول  (in-sample)      → این‌جا ایده‌ها امتحان می‌شوند
      · نیمهٔ دوم  (out-of-sample)  → فقط یک بار، برای داوریِ نهایی

    ۱. پایه روی نیمهٔ اول → خالصِ پایه
    ۲. هر ایدهٔ همان متخصص روی همان نیمهٔ اول → بهترین ایده انتخاب می‌شود
    ۳. پایه و ایدهٔ برنده، هر دو روی نیمهٔ دوم اجرا می‌شوند
    ۴. **پذیرش فقط اگر روی نیمهٔ دوم هم بهتر باشد** و CI اختلاف کاملاً
       زیر صفر نباشد

بند ۳ و ۴ همان چیزی‌اند که این را از «بهینه‌سازیِ روی نمودار» جدا می‌کنند.
بی آن‌ها هر ایده‌ای که روی همان داده انتخاب شود بهتر به نظر می‌رسد.

عددِ نهاییِ گزارش‌شده برای هر متخصص **از نیمهٔ دوم** است — دادهٔ
دیده‌نشده. عددِ نیمهٔ اول فقط برای انتخاب ایده بود و جداگانه گزارش
می‌شود تا فاصله‌شان دیده شود.
"""
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent

from hamid.specialist_lab import (SPECIALISTS, BY_ID, TF, PER_SYMBOL,   # noqa: E402
                                  WARMUP, replay, summarize, OUT, LEDGER)

BARS = 2000                    # ~۲۱ روز روی ۱۵ دقیقه
MIN_BARS = 600
Z_SIDAK = 2.58                 # ~۱۲ آزمون هم‌زمان (۱۲ متخصص)، دوطرفه ۰.۰۵


def _klines(sym, bars=BARS):
    try:
        import sources
        rows = sources.klines(sym, TF, bars)
    except Exception:                                # noqa: BLE001
        return []
    out = []
    for k in rows or []:
        try:
            out.append({"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
                        "l": float(k[3]), "c": float(k[4]), "v": float(k[5])})
        except Exception:                            # noqa: BLE001
            continue
    return out


def _universe(n):
    from backtest import top_symbols
    try:
        syms = top_symbols(max(n, 400))
    except Exception:                                # noqa: BLE001
        syms = []
    try:
        from hamid.universe import is_blocked, STABLES, WRAPPED
    except Exception:                                # noqa: BLE001
        return syms[:n]
    keep = []
    for s in syms:
        base = s[:-4] if s.endswith("USDT") else s
        if is_blocked(s) or base in STABLES or base in WRAPPED:
            continue
        keep.append(s)
        if len(keep) >= n:
            break
    return keep


def _diff_ci(a, b, z=Z_SIDAK):
    """اختلافِ میانگینِ دو گروهِ مستقل با CI شیداک‌شده."""
    if len(a) < 2 or len(b) < 2:
        return None, (None, None)
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    se = math.sqrt(statistics.pvariance(a) / len(a) + statistics.pvariance(b) / len(b))
    d = ma - mb
    return round(d, 4), (round(d - z * se, 4), round(d + z * se, 4))


def _run_variant(spec, params, series, half, per_symbol, budget):
    """اجرای یک نسخهٔ پارامتری روی نیمهٔ خواسته‌شده از تاریخِ همهٔ ارزها."""
    trades = []
    for sym, cd in series:
        if len(trades) >= budget:
            break
        n = len(cd)
        mid = n // 2
        lo, hi = (WARMUP, mid) if half == "in" else (max(mid, WARMUP), n)
        if hi - lo < 120:
            continue
        trades += replay(sym, cd, spec, params, lo=lo, hi=hi, cap=per_symbol)
    return trades[:budget]


def improve_spec(spec, series, per_symbol, budget):
    """ایده‌های خودِ متخصص را امتحان کن؛ فقط با تأییدِ خارج-از-نمونه بپذیر."""
    base_p = dict(spec["params"])
    base_in = _run_variant(spec, base_p, series, "in", per_symbol, budget)
    base_in_net = [t["net_r"] for t in base_in if t.get("net_r") is not None]
    tried = []
    best = None
    for idea in spec.get("ideas") or []:
        p = dict(base_p, **idea)
        tr = _run_variant(spec, p, series, "in", per_symbol, budget)
        nets = [t["net_r"] for t in tr if t.get("net_r") is not None]
        m = statistics.fmean(nets) if len(nets) >= 30 else None
        tried.append({"change": idea, "n": len(nets),
                      "net_in": None if m is None else round(m, 4)})
        if m is not None and (best is None or m > best[0]):
            best = (m, idea, p)
    base_m = statistics.fmean(base_in_net) if base_in_net else None
    if best is None or base_m is None or best[0] <= base_m:
        return {"adopted": False, "why": "هیچ ایده‌ای روی نیمهٔ اول از پایه بهتر نشد",
                "tried": tried, "base_net_in": None if base_m is None else round(base_m, 4),
                "params": base_p}
    # داوریِ خارج-از-نمونه
    cand_p = best[2]
    base_out = _run_variant(spec, base_p, series, "out", per_symbol, budget)
    cand_out = _run_variant(spec, cand_p, series, "out", per_symbol, budget)
    bn = [t["net_r"] for t in base_out if t.get("net_r") is not None]
    cn = [t["net_r"] for t in cand_out if t.get("net_r") is not None]
    d, (lo, hi) = _diff_ci(cn, bn)
    ok = (d is not None and d > 0 and not (hi is not None and hi < 0)
          and len(cn) >= 30)
    return {"adopted": bool(ok), "change": best[1], "tried": tried,
            "base_net_in": round(base_m, 4),
            "cand_net_in": round(best[0], 4),
            "base_net_out": round(statistics.fmean(bn), 4) if bn else None,
            "cand_net_out": round(statistics.fmean(cn), 4) if cn else None,
            "diff_out": d, "diff_ci": [lo, hi],
            "why": ("ایده روی دادهٔ دیده‌نشده هم بهتر بود" if ok else
                    "روی نیمهٔ اول بهتر بود ولی خارج-از-نمونه تأیید نشد — رد شد"),
            "params": cand_p if ok else base_p}


def run_all(n_symbols=200, per_symbol=PER_SYMBOL, only=None, improve=True,
            budget=None, log=print):
    improve_on = bool(improve)
    budget = budget or (n_symbols * per_symbol)
    t0 = time.time()
    syms = _universe(n_symbols * 3)
    log(f"نامزد: {len(syms)} ارز (بلاک‌شده‌ها حذف)", flush=True)
    series, skipped = [], []
    for s in syms:
        if len(series) >= n_symbols:
            break
        cd = _klines(s)
        if len(cd) < MIN_BARS:
            skipped.append(s)
            continue
        series.append((s, cd))
    log(f"کندل گرفته شد: {len(series)} ارز · {len(skipped)} ارزِ بی‌تاریخچهٔ کافی رد شد",
        flush=True)
    if len(series) < n_symbols:
        log(f"هشدار: فقط {len(series)} ارز تاریخچهٔ ≥{MIN_BARS} کندل داشت — "
            f"هدف {n_symbols} بود. عدد همان‌طور که هست گزارش می‌شود.", flush=True)
    specs = [BY_ID[only]] if only else SPECIALISTS
    LEDGER.mkdir(parents=True, exist_ok=True)
    desks = {}
    for spec in specs:
        st = time.time()
        imp = (improve_spec(spec, series, per_symbol, budget) if improve_on
               else {"adopted": False, "params": dict(spec["params"]),
                     "why": "چرخهٔ بهبود اجرا نشد"})
        params = imp["params"]
        trades = _run_variant(spec, params, series, "out", per_symbol, budget)
        s_out = summarize(trades)
        base_tr = (_run_variant(spec, dict(spec["params"]), series, "out", per_symbol, budget)
                   if imp.get("adopted") else trades)
        desks[spec["id"]] = {
            "sign": spec["sign"], "fa": spec["fa"], "en": spec["en"],
            "family": spec["family"],
            "strategy_fa": spec["strategy_fa"], "strategy_en": spec["strategy_en"],
            "idea": spec["idea"],
            "params_base": spec["params"], "params_used": params,
            "improvement": imp,
            "result_out_of_sample": s_out,
            "result_base_out": summarize(base_tr) if imp.get("adopted") else s_out,
            "seconds": round(time.time() - st, 1)}
        try:
            with (LEDGER / f"{spec['id']}.jsonl").open("a", encoding="utf-8") as f:
                for t in trades:
                    f.write(json.dumps(t, ensure_ascii=False) + "\n")
        except Exception:                            # noqa: BLE001
            pass
        r = s_out
        log(f"  {spec['sign']} {spec['fa']} [{spec['strategy_fa']}] "
            f"n={r.get('n')} خالص={r.get('net')} CI={r.get('ci')} "
            f"{'· ایده پذیرفته' if imp.get('adopted') else ''}", flush=True)
    total = sum((d["result_out_of_sample"].get("n") or 0) for d in desks.values())
    return {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
            "owner": "E18", "tf": TF, "per_symbol": per_symbol,
            "n_symbols": len(series), "n_symbols_target": n_symbols,
            "n_skipped_no_history": len(skipped),
            "trades_total": total,
            "seconds": round(time.time() - t0, 1),
            "desks": desks,
            "summary": {k: {"fa": v["fa"], "strategy": v["strategy_fa"],
                            "n": v["result_out_of_sample"].get("n"),
                            "net": v["result_out_of_sample"].get("net"),
                            "ci": v["result_out_of_sample"].get("ci"),
                            "adopted": v["improvement"].get("adopted")}
                        for k, v in desks.items()},
            "method": ("هر متخصص ستاپ خودش را کشف می‌کند (نه فیلترِ ستاپِ مشترک). "
                       "بازپخش بدون نگاه به آینده روی کندل واقعی ۱۵ دقیقه؛ "
                       "تاریخ دو نیمه: نیمهٔ اول برای انتخاب ایده، نیمهٔ دوم فقط "
                       "برای داوری. عددِ گزارش‌شده از نیمهٔ دوم است."),
            "boundary": ("دفتر پیپر است: فیل کامل و بی‌لغزش فرض می‌شود، پس سقفِ "
                         "خوش‌بینانه است نه انتظارِ لایو. هیچ‌کدام از این "
                         "استراتژی‌ها وارد تولید نمی‌شود مگر از مسیر قانون ۰۳ "
                         "(CI بالای صفر + تأیید حمید). برچسب دفترها sp-<id> و "
                         "بیرون از کارنامهٔ سیگنالِ ارسالی.")}
