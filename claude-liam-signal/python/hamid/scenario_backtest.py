"""بک‌تست دفتر سناریو روی ۱د/۳د — دستور حمید (۲۲ اوت).

«بک‌تست در گذشتهٔ ارزها به‌صورت واقعی که از آینده خبر ندارند به‌صورت ۵ایکس
گرفته شود، روی ۳۰ ارز ۳۰۰ بار پوزیشن باز شود برای یادگیری بیشتر.»

## ساختارِ ضدِ نگاه به آینده (نکتهٔ اصلی این فایل)

نقشه روی کندل i **بسته‌شده** ساخته می‌شود، و فقط کندل i+1 حق دارد ماشه‌اش
را بزند. یعنی جدول شاخه‌ها هرگز کلوزِ کندلی را که قرار است ماشه بزند
نمی‌بیند. این دقیقاً همان چیزی است که حمید خواست: «بلافاصله بعد از بسته
شدن کندل، تحلیل‌ها آماده باشند و سریع وارد شوند» — و همان چیزی است که
بک‌تست را صادق نگه می‌دارد.

خروج هم بدترین‌حالتِ درون‌کندلی است: اگر یک کندل هم استاپ و هم تارگت را
لمس کرد، **استاپ** حساب می‌شود (ترتیب واقعی درون کندل را نمی‌دانیم؛ فرض
خوش‌بینانه یعنی دروغ گفتن به خودمان).

## اهرم ۵ — مرز صادقانه

اهرم **R و نرخ برد را عوض نمی‌کند**؛ فقط مارجین و فاصلهٔ لیکویید را
جابه‌جا می‌کند. پس هر معامله هم به R گزارش می‌شود (سنجهٔ لبه) هم به درصد
حساب با اهرم ۵ و ریسک ثابت (سنجه‌ای که حمید می‌بیند). حکم پذیرش فقط از
CI بوت‌استرپ روی R می‌آید — قانون CI.

خروجی: signals/scenario-backtest.json
اجرا:  python3 -m hamid.scenario_backtest --symbols 30 --tf 1m --target-trades 300
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

from hamid import microstructure as MS               # noqa: E402
from hamid import scenarios as SC                    # noqa: E402

OUT = ROOT / "signals" / "scenario-backtest.json"
WARMUP = 60                    # پیوت + ATR + حاشیه
MAX_HOLD = 45                  # کندل؛ بعدش ستاپ اسکلپ مرده است
RISK_PCT = 2.0                 # ریسک هر معامله از حساب (قانون سایز)

# دستور صریح حمید (۲۲ اوت): «برای هر ترید ۱۰ دلار بذار».
# مهم و صریح: ۱۰ دلار **مارجین** است، نه ضرر. با اهرم L، نوشنال = ۱۰×L
# و ضررِ استاپ = نوشنال × استاپ٪. مثال: ۱۰$ با اهرم ۱۲ = ۱۲۰$ نوشنال؛
# استاپ ۰.۵٪ یعنی ضرر ۰.۶۰$ — نه ۱۰$. آنچه ۱۰$ را کامل می‌سوزاند،
# حرکت ۱/L برخلاف ماست (با اهرم ۱۲ ≈ ۸.۳٪) که محافظ لیکویید جلویش را
# می‌گیرد. هر دو عدد گزارش می‌شوند تا جای حدس نماند.
MARGIN_USD = 10.0


def _cd(rows):
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
             "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in rows]


def resample(c1m, minutes):
    """۱د → ۳د. مرزها روی مضارب واقعیِ زمان‌اند تا کندلِ ۳د همان چیزی باشد
    که صرافی می‌سازد، نه پنجرهٔ لغزانِ دلبخواه."""
    if minutes == 1:
        return c1m
    step = minutes * 60000
    out, cur = [], None
    for k in c1m:
        b = (k["t"] // step) * step
        if cur is None or cur["t"] != b:
            if cur:
                out.append(cur)
            cur = {"t": b, "o": k["o"], "h": k["h"], "l": k["l"],
                   "c": k["c"], "v": k["v"]}
        else:
            cur["h"] = max(cur["h"], k["h"])
            cur["l"] = min(cur["l"], k["l"])
            cur["c"] = k["c"]
            cur["v"] += k["v"]
    if cur:
        out.append(cur)
    return out


def maker_fill(cd, start_j, level, action, wait_bars, n):
    """آیا سفارش لیمیتِ میکر روی `level` پر می‌شود؟ → (اندیس فیل، یا None).

    مدل صادقانه: بعد از ماشه، قیمت باید **برگردد** و سطح را لمس کند تا
    لیمیت پر شود. اگر در پنجرهٔ انتظار برنگشت، معامله‌ای در کار نیست.
    این دقیقاً همان هزینهٔ واقعی میکر است: روی حرکت‌های تندِ برنده لیمیت
    جا می‌ماند (انتخاب نامساعد) و فقط وقتی پر می‌شود که بازار برگردد."""
    for j in range(start_j, min(start_j + wait_bars, n)):
        if action == "LONG" and cd[j]["l"] <= level:
            return j
        if action == "SHORT" and cd[j]["h"] >= level:
            return j
    return None


def replay_symbol(sym, cd, params=None, max_hold=MAX_HOLD):
    """نقشه روی کندل i، ماشه فقط از کندل i+1. خروجی: (معامله‌ها، علت‌های رد)."""
    q = dict(SC.P, **(params or {}))
    model = q["fee_model"]
    trades, reasons = [], {}
    i = WARMUP
    n = len(cd)
    while i < n - 2:
        plan = SC.plan(cd[:i + 1], sym, params)      # فقط گذشته
        if not plan["branches"]:
            key = str(plan.get("why") or "?")[:48]
            reasons[key] = reasons.get(key, 0) + 1
            i += 1
            continue
        nxt = cd[i + 1]
        br = SC.check(plan["branches"], nxt)          # ماشه با کلوزِ i+1
        if br is None:
            reasons["هیچ شاخه‌ای ماشه نخورد"] = reasons.get("هیچ شاخه‌ای ماشه نخورد", 0) + 1
            i += 1
            continue
        # ورود: تیکر = کلوزِ کندلِ ماشه. میکر = لیمیت روی خودِ سطح، که فقط
        # اگر قیمت برگردد پر می‌شود — وگرنه معامله‌ای نیست (نه فیلِ فرضی).
        if model == "maker_entry":
            fj = maker_fill(cd, i + 2, br["level"], br["action"],
                            q["maker_wait_bars"], n)
            if fj is None:
                reasons["لیمیت میکر پر نشد (قیمت برنگشت)"] = \
                    reasons.get("لیمیت میکر پر نشد (قیمت برنگشت)", 0) + 1
                i += 1
                continue
            sig = SC.resolve(br, br["level"])
            first_exit_j = fj + 1
            open_t = cd[fj]["t"]
        else:
            sig = SC.resolve(br, nxt["c"])
            first_exit_j = i + 2
            open_t = nxt["t"]
        entry, sl, tp = sig["entry"], sig["sl"], sig["tp1"]
        risk = abs(entry - sl)
        if risk <= 0:
            i += 1
            continue
        res, exit_px, bars = None, None, 0
        for j in range(first_exit_j, min(first_exit_j + max_hold, n)):
            k = cd[j]
            bars = j - first_exit_j + 1
            if sig["action"] == "LONG":
                if k["l"] <= sl:                      # بدترین حالت: استاپ اول
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
            exit_px = cd[min(first_exit_j + max_hold, n - 1)]["c"]
            bars = max(bars, 1)
        r = ((exit_px - entry) if sig["action"] == "LONG"
             else (entry - exit_px)) / risk
        # کارمزد به **نتیجه** بستگی دارد: خروج با استاپ همیشه مارکت است،
        # خروج با تارگت می‌تواند لیمیت باشد. تایم‌اوت هم مارکت است.
        rt = SC.round_trip_pct(model, "target" if res == "target" else "stop")
        fee_r = (rt / 100) * entry / risk
        # از همان R خالصِ گردشده مشتق می‌شود تا گزارش با خودش ناخوان نباشد
        r_net = round(r - fee_r, 3)
        trades.append({
            "sym": sym, "dir": sig["action"], "kind": sig["kind"],
            "trigger": sig["trigger"], "outcome": res,
            "R": round(r, 3), "R_net": r_net,
            "fee_pct": round(rt, 4), "fee_r": round(fee_r, 3),
            # درصد حساب: ریسک ثابت ۲٪ ضرب در R خالص. اهرم اندازهٔ مارجین را
            # عوض می‌کند نه این عدد — به‌عمد این‌طور، تا توهم «اهرم بیشتر =
            # لبهٔ بیشتر» ساخته نشود.
            "acct_pct": round(r_net * RISK_PCT, 4),
            # پول واقعی با مارجین ثابت ۱۰$ (دستور حمید)
            "margin_usd": MARGIN_USD,
            "notional_usd": round(MARGIN_USD * sig["leverage"], 2),
            "risk_usd": round(MARGIN_USD * sig["leverage"]
                              * sig["stop_pct"] / 100, 4),
            "pnl_usd": round(r_net * MARGIN_USD * sig["leverage"]
                             * sig["stop_pct"] / 100, 4),
            "leverage": sig["leverage"], "stop_pct": sig["stop_pct"],
            "session": sig["session"], "bias_at_plan": sig["bias_at_plan"],
            "bars": bars, "opened": open_t,
        })
        i = first_exit_j + bars                       # ضدهم‌پوشانی
    return trades, reasons


def multiple_test_penalty(n_trials):
    """آستانهٔ z که یک نتیجه باید از آن رد شود، وقتی n_trials پیکربندی
    آزموده‌ایم (تصحیح چندآزمونی، خانوادهٔ Deflated Sharpe / Šidák).

    منطق: با n آزمونِ مستقل، بیشینهٔ z تصادفی حدوداً به اندازهٔ
    sqrt(2·ln n) بالا می‌رود. پس «بهترین خانه» باید از همین آستانه رد شود
    نه از ۱.۹۶ معمولی. با ۱۲ ترکیب آستانه ≈ ۲.۲۳ — یعنی نتیجه‌ای که فقط
    تازه از صفر رد شده، عملاً هیچ نگفته.

    منبع: Bailey & López de Prado, "The Deflated Sharpe Ratio" (JPM 2014)
    و Bailey et al., "Pseudo-Mathematics and Financial Charlatanism"
    (Notices of the AMS 2014) — هر دو در brain/library/queue.jsonl."""
    import math
    n = max(1, int(n_trials))
    if n == 1:
        return 1.96
    return round(max(1.96, math.sqrt(2.0 * math.log(n))), 3)


def t_stat(rs):
    """t میانگین R — پایهٔ مقایسه با آستانهٔ چندآزمونی."""
    n = len(rs)
    if n < 3:
        return 0.0
    m = sum(rs) / n
    var = sum((x - m) ** 2 for x in rs) / (n - 1)
    se = (var / n) ** 0.5
    return round(m / se, 3) if se > 1e-15 else 0.0


def boot_ci(rs, n_boot=3000, seed=7):
    if len(rs) < 30:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(rs, k=len(rs))) / len(rs) for _ in range(n_boot))
    return [round(means[int(n_boot * 0.025)], 3),
            round(means[int(n_boot * 0.975)], 3)]


def _agg(ts):
    if not ts:
        return {"n": 0}
    rs = [t["R_net"] for t in ts]
    wins = sum(1 for t in ts if t["outcome"] == "target")
    return {"n": len(ts), "win_pct": round(100 * wins / len(ts), 1),
            "mean_r_net": round(sum(rs) / len(rs), 3), "ci95": boot_ci(rs),
            "mean_acct_pct": round(sum(t["acct_pct"] for t in ts) / len(ts), 4),
            "total_acct_pct": round(sum(t["acct_pct"] for t in ts), 2),
            "total_pnl_usd": round(sum(t["pnl_usd"] for t in ts), 2),
            "mean_pnl_usd": round(sum(t["pnl_usd"] for t in ts) / len(ts), 4),
            "mean_risk_usd": round(sum(t["risk_usd"] for t in ts) / len(ts), 3),
            "outcomes": {o: sum(1 for t in ts if t["outcome"] == o)
                         for o in ("target", "stop", "timeout")}}


def _split(ts, key):
    vals = sorted({t[key] for t in ts})
    return {str(v): _agg([t for t in ts if t[key] == v]) for v in vals}


def sweep(symbols=30, tf="3m", bars=1000, rrs=(1.5, 2.0, 3.0, 5.0),
          holds=(45, 120, 300), fee_model="maker_entry", leverage=12,
          universe="volatile", quiet=False, offset=0):
    """یک بار داده می‌گیرد، همان داده را با چند RR و چند پنجرهٔ نگهداری
    بازپخش می‌کند. سؤال حمید («RR ۵ به بالا») با کندل واقعی جواب می‌گیرد،
    نه با شبیه‌سازی.

    چرا پنجرهٔ نگهداری هم در جدول است: اندازه‌گیری ۲۲ اوت نشان داد پنجرهٔ
    ثابت ۴۵ کندل، RRهای بلند را **خفه می‌کند** — RR=5 با ۴۵ کندل ۰٪ برد
    داد و با ۳۰۰ کندل ۱۷.۶٪. یعنی «RR ۵ جواب نمی‌دهد» و «به RR ۵ وقت
    نداده‌ایم» دو چیز کاملاً متفاوت‌اند و باید از هم جدا شوند.

    هشدار روش‌شناختی که در خروجی هم می‌آید: این یک **جست‌وجوی پارامتر**
    است. بهترین خانهٔ جدول لزوماً لبه نیست — با این تعداد ترکیب، بهترین
    عدد حتی روی دادهٔ تصادفی هم مثبت درمی‌آید. تأیید فقط با دادهٔ مستقل."""
    import sources
    if universe == "volatile":
        from hamid.volatility_universe import build as vbuild
        syms = vbuild(n=symbols, tf=tf, quiet=quiet, offset=offset)["symbols"]
    else:
        try:
            syms = sources.top_symbols(symbols)
        except Exception:                              # noqa: BLE001
            from hamid.trainer import top_symbols
            syms = top_symbols(symbols)
    mins = int(tf.replace("m", ""))
    series, drops = {}, {}
    for sname in syms:
        try:
            c1 = _cd(sources.klines(sname, "1m", bars))
        except Exception as e:                         # noqa: BLE001
            drops[type(e).__name__] = drops.get(type(e).__name__, 0) + 1
            continue
        cd = resample(c1, mins)
        if len(cd) >= WARMUP + 40:
            series[sname] = cd
    if not quiet:
        print(f"دادهٔ {len(series)} نماد گرفته شد؛ حالا {len(rrs)}×{len(holds)} ترکیب")

    grid = []
    for rr in rrs:
        for hold in holds:
            tr = []
            for sname, cd in series.items():
                t, _ = replay_symbol(sname, cd,
                                     {"fee_model": fee_model, "rr_target": rr,
                                      "leverage": leverage}, max_hold=hold)
                tr += t
            a = _agg(tr)
            a.update({"rr": rr, "max_hold": hold,
                      "t_stat": t_stat([t["R_net"] for t in tr]) if tr else None})
            grid.append(a)
            if not quiet and a.get("n"):
                print(f"  RR={rr} hold={hold}: n={a['n']} برد {a['win_pct']}٪ "
                      f"R {a['mean_r_net']:+.3f} CI {a['ci95']} "
                      f"سود ${a['total_pnl_usd']:+.2f}")
    # تصحیح چندآزمونی: هر خانه t خودش را دارد و باید از آستانهٔ خانوادگی
    # رد شود، نه از ۱.۹۶. این همان چیزی است که تا امروز فقط «هشدار» بود.
    thr = multiple_test_penalty(len(grid))
    for g in grid:
        g["t_stat"] = g.pop("_t", None) or g.get("t_stat")
    ok = [g for g in grid if g.get("ci95") and g["ci95"][0] > 0]
    survivors = [g for g in grid
                 if g.get("t_stat") is not None and g["t_stat"] > thr]
    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "mode": "sweep", "tf": tf, "symbols": len(series),
           "universe": universe, "offset": offset, "fee_model": fee_model,
           "leverage": leverage, "margin_usd": MARGIN_USD,
           "bars_1m": bars, "drop_reasons": drops,
           "grid": sorted(grid, key=lambda g: -(g.get("mean_r_net") or -9)),
           "trials": len(grid),
           "multiple_test_threshold_t": thr,
           "ci_clears_zero": [{"rr": g["rr"], "hold": g["max_hold"],
                               "n": g["n"], "ci95": g["ci95"]} for g in ok],
           "survives_multiple_testing": [
               {"rr": g["rr"], "hold": g["max_hold"], "n": g["n"],
                "t_stat": g["t_stat"], "ci95": g["ci95"]} for g in survivors],
           "warning": ("جست‌وجوی پارامتر است: با "
                       f"{len(grid)} ترکیب، بهترین خانه حتی روی دادهٔ تصادفی هم "
                       "مثبت درمی‌آید. هیچ خانه‌ای بدون تأیید روی دادهٔ مستقل "
                       "«یافته» نیست (قانون CI + تصحیح چندآزمونی).")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    (OUT.parent / "scenario-sweep.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        print(f"خانه‌های با CI بالای صفر: {len(ok)} از {len(grid)}")
        print(f"آستانهٔ t با {len(grid)} آزمون: {thr} · "
              f"از این آستانه رد شد: {len(survivors)}")
        print(f"نوشته شد: {OUT.parent / 'scenario-sweep.json'}")
    return res


def run(symbols=30, tf="1m", bars=1000, target_trades=300, quiet=False,
        params=None, fee_model=None):
    params = dict(params or {})
    if fee_model:
        params["fee_model"] = fee_model
    import sources
    if params.pop("_universe", None) == "volatile":
        from hamid.volatility_universe import build as vbuild
        syms = vbuild(n=symbols, tf=tf, quiet=quiet)["symbols"]
    else:
        try:
            syms = sources.top_symbols(symbols)
        except Exception:                              # noqa: BLE001
            from hamid.trainer import top_symbols
            syms = top_symbols(symbols)

    mins = int(tf.replace("m", ""))
    all_tr, all_rs, drops = [], {}, {}
    done = 0
    for s in syms:
        try:
            c1 = _cd(sources.klines(s, "1m", bars))
        except Exception as e:                         # noqa: BLE001
            drops[type(e).__name__] = drops.get(type(e).__name__, 0) + 1
            continue
        cd = resample(c1, mins)
        if len(cd) < WARMUP + 40:
            drops["سری کوتاه"] = drops.get("سری کوتاه", 0) + 1
            continue
        tr, rs = replay_symbol(s, cd, params)
        all_tr += tr
        for k, v in rs.items():
            all_rs[k] = all_rs.get(k, 0) + v
        done += 1
        if not quiet and done % 5 == 0:
            print(f"  {done}/{len(syms)} نماد — {len(all_tr)} معامله", flush=True)

    res = {
        "generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
        "engine": f"E07 {MS.STRUCT_VERSION} + {SC.PLAN_VERSION}",
        "tf": tf, "symbols": done, "skipped": sum(drops.values()),
        "drop_reasons": drops, "bars_1m": bars,
        "target_trades": target_trades,
        "leverage": params.get("leverage", SC.P["leverage"]),
        "risk_pct_per_trade": RISK_PCT, "margin_usd": MARGIN_USD,
        "rr_target": params.get("rr_target", SC.P["rr_target"]),
        "fee_model": params.get("fee_model", SC.P["fee_model"]),
        "fee_table_pct": SC.FEE_MODELS[params.get("fee_model", SC.P["fee_model"])],
        "params": dict(SC.P, min_leg_atr=MS.MIN_LEG_ATR, **(params or {})),
        "overall": _agg(all_tr),
        "per_kind": _split(all_tr, "kind"),          # BOS در برابر CHoCH
        "per_direction": _split(all_tr, "dir"),
        "per_session": _split(all_tr, "session"),    # دستور حمید
        "per_trigger": _split(all_tr, "trigger"),
        "rejection_funnel": dict(sorted(all_rs.items(), key=lambda x: -x[1])[:12]),
        "trade_target_note": (
            f"هدف {target_trades} معامله بود؛ {len(all_tr)} ساخته شد. کمبود = "
            "کمبودِ تاریخچهٔ ۱ دقیقه در صرافی‌ها، نه سخت‌گیری دروازه — با "
            "--bars بیشتر یا نمادهای بیشتر پر می‌شود."),
        "leverage_note": (
            "اهرم R و نرخ برد را عوض نمی‌کند؛ فقط مارجین و فاصلهٔ لیکویید. "
            "acct_pct = R خالص × ریسک ۲٪ حساب. حکم فقط از CI روی R."),
        "note": ("نقشه روی کندل i، ماشه فقط از کندل i+1 — بدون نگاه به آینده. "
                 "خروج بدترین‌حالت درون‌کندلی. R خالص از کارمزد "
                 f"{SC.P['fee_round_trip_pct']}٪."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        o = res["overall"]
        print(f"\nنمادها: {done} · معامله: {o.get('n', 0)} (هدف {target_trades})")
        if o.get("n"):
            print(f"برد: {o['win_pct']}٪ · R خالص: {o['mean_r_net']:+.3f} "
                  f"· CI95: {o['ci95']} · جمع حساب: {o['total_acct_pct']:+.2f}٪")
            for k, v in res["per_kind"].items():
                if v.get("n"):
                    print(f"  {k}: n={v['n']} برد {v['win_pct']}٪ "
                          f"R {v['mean_r_net']:+.3f} CI {v['ci95']}")
            for k, v in res["per_session"].items():
                if v.get("n"):
                    print(f"  سشن {k}: n={v['n']} R {v['mean_r_net']:+.3f} "
                          f"CI {v['ci95']}")
        print(f"نوشته شد: {OUT}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=30)
    ap.add_argument("--tf", default="1m", choices=["1m", "3m"])
    ap.add_argument("--bars", type=int, default=1000)
    ap.add_argument("--target-trades", type=int, default=300)
    ap.add_argument("--min-leg-atr", type=float, default=None)
    ap.add_argument("--fee-model", default="taker",
                    choices=list(__import__("hamid.scenarios", fromlist=["x"]).FEE_MODELS))
    ap.add_argument("--rr", type=float, default=None)
    ap.add_argument("--leverage", type=int, default=None)
    ap.add_argument("--universe", default="liquidity",
                    choices=["liquidity", "volatile"])
    ap.add_argument("--offset", type=int, default=0,
                    help="نمونهٔ نمادیِ مستقل: از رتبهٔ offset+1 شروع کن")
    ap.add_argument("--sweep", action="store_true",
                    help="جدول RR × پنجرهٔ نگهداری روی همان دادهٔ واقعی")
    a = ap.parse_args()
    if a.min_leg_atr is not None:
        MS.MIN_LEG_ATR = a.min_leg_atr
    pr = {}
    if a.rr is not None:
        pr["rr_target"] = a.rr
    if a.leverage is not None:
        pr["leverage"] = a.leverage
    if a.universe == "volatile":
        pr["_universe"] = "volatile"
    if a.sweep:
        sweep(symbols=a.symbols, tf=a.tf, bars=a.bars,
              fee_model=a.fee_model, leverage=a.leverage or 12,
              universe=a.universe, offset=a.offset)
        raise SystemExit(0)
    run(symbols=a.symbols, tf=a.tf, bars=a.bars, target_trades=a.target_trades,
        params=pr, fee_model=a.fee_model)
