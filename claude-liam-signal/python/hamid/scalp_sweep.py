"""جستجوی هندسهٔ اسکلپ — با تفکیک اجباری جستجو از تأیید.

## مسئله‌ای که این فایل حل می‌کند

دفتر اسکلپ (n=۲۱۵۳): R ناخالص +۰.۰۳۰، کارمزد ۰.۲۱۸، خالص −۰.۱۸۸ با CI
کاملاً زیر صفر. حساسیت هزینه نشان داد حتی با کارمزد صفر هم CI صفر را در
بر می‌گیرد. پس دو راه بیشتر نیست:

**الف) لبهٔ ناخالص بزرگ‌تر** — همان چیزی که حمید می‌گوید: کیفیت ورود از
کندل‌شناسی و ساختار ۱ دقیقه. اندازه‌گیری روی همان دفتر:
IBS ≤۰.۱۵ در لانگ → +۰.۰۸۸R ناخالص، CI [+۰.۰۲۶, +۰.۱۵۳]، ولی t=۲.۷۸ در
برابر آستانهٔ Šidák ۲.۸۰ — **رد نشد**. سرنخ است، نه کشف.

**ب) هندسهٔ بزرگ‌تر** — کارمزد در واحد R برابر `کارمزد٪ ÷ استاپ٪` است.
اگر همان الگو با استاپ و تارگتِ **متناسباً بزرگ‌تر** معامله شود، R ثابت
می‌ماند ولی سهم کارمزد نصف می‌شود. این تنها اهرمی است که بدون بهبود
پیش‌بینی، ریاضی را عوض می‌کند.

**قیچیِ اهرم — صریح گفته شود:** `lev ≤ ۵۰ ÷ استاپ٪` (محافظ لیکویید).
استاپِ گشادتر یعنی سقف اهرمِ پایین‌تر. «اهرم بالا» و «کارمزدِ کم» روی
۱ دقیقه در تضاد ریاضی‌اند. اهرم هم R و نرخ برد را عوض نمی‌کند —
اندازه‌گیری‌شده روی همین دفتر: اهرم ۴۰–۵۰ → +۰.۰۳۳R، اهرم ۶۵–۹۵ →
+۰.۰۵۳R، هر دو با CI شامل صفر.

## چرا این فایل «جستجو» را از «تأیید» جدا می‌کند

۲۲ اوت یک جستجوی پارامتری R را از −۰.۲۰۹ به +۰.۱۲۶ رساند و تأیید خارج
از نمونه هر ۱۲ خانه را رد کرد. آن کشف، نویزِ جستجو بود. پس این‌جا از
اول دو نمونهٔ **مستقل** ساخته می‌شود: جستجو فقط روی A، و بهترین خانه
فقط یک بار روی B آزموده می‌شود. خانه‌ای که روی B نیفتد، وجود ندارد.

اجرا:  python3 -m hamid.scalp_sweep --bars 1500
"""
import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import microstructure as MS                 # noqa: E402
from hamid import scalp as SC                          # noqa: E402
from hamid.scenario_backtest import multiple_test_penalty   # noqa: E402

OUT = ROOT / "signals" / "scalp-sweep.json"
MIN_N = 30
WARMUP = 80

# شبکهٔ جستجو. هر بعد یک فرضیهٔ صریح دارد:
#   rr        — تارگت دورتر: R بزرگ‌تر به ازای همان کارمزد
#   max_fee_r — سقف سهم کارمزد از R؛ سخت‌گیرتر = هندسهٔ بزرگ‌تر اجباری
#   ibs_max   — کیفیت ورود (سرنخ IBS عمیق)
#   hold      — فرصت رسیدن به تارگت دورتر
GRID = {"rr": [1.5, 2.5, 4.0],
        "max_fee_r": [0.30, 0.15, 0.08],
        "ibs_max": [0.30, 0.15],
        # ۱۵ = درخواست صریح حمید («بعد از ۱۵ دقیقه با حداکثر سود خارج
        # شویم»). ۴۵ فعلیِ تولید، ۱۲۰ برای اینکه معلوم شود تارگتِ دورتر
        # اصلاً فرصت رسیدن پیدا می‌کند یا نه.
        "hold": [15, 45, 120]}


def cells():
    out = []
    for rr in GRID["rr"]:
        for mf in GRID["max_fee_r"]:
            for ib in GRID["ibs_max"]:
                for h in GRID["hold"]:
                    out.append({"rr": rr, "max_fee_r": mf,
                                "ibs_max": ib, "hold": h})
    return out


# ── دروازهٔ ساختار (فرضیهٔ حمید، ۲۳ اوت) ────────────────────────────────
# «اطمینان از نتیجهٔ معامله برمی‌گردد به تجربهٔ کندل‌شناسی و الگوهای
# BOS و CHoCH که در تایم ۱ دقیقه می‌بینیم.»
#
# موتور اسکلپ امروز ساختار را **اصلاً نگاه نمی‌کند** (EMA21/55 + IBS +
# پولبک). پس این فرضیه تا امروز نه رد شده نه تأیید — فقط آزموده نشده.
#
# عمداً بُعدِ شبکهٔ جستجو نشد: افزودنش شبکه را سه‌برابر و آستانهٔ
# چندآزمونی را سخت‌تر می‌کرد. به‌جایش آزمونِ جداگانه با **جهت
# پیش‌بینی‌شده**: ساختارِ هم‌جهت باید R ناخالص را بالا ببرد، نه پایین.
STRUCT_MODES = {
    "off":     "بدون دروازهٔ ساختار (پایه — همان چیزی که امروز اجرا می‌شود)",
    "aligned": "فقط وقتی سوگیری ساختار ۱ دقیقه هم‌جهت معامله است",
    "fresh":   "فقط تا ۱۰ کندل بعد از BOS/CHoCH هم‌جهت",
}
FRESH_BARS = 10


def struct_ok(win, direction, mode):
    """آیا ساختار ۱ دقیقه اجازه می‌دهد؟ → (بله/خیر، برچسب رویداد).

    ساختار از همان microstructure ای خوانده می‌شود که پیوت را با تأخیر
    تأیید می‌کند (confirmed_at_i = i+right) — یعنی هیچ نگاهی به آینده
    ندارد. اگر ساختار قابل‌محاسبه نبود، **رد** می‌شود نه عبورِ کور
    (قانون ۱: دادهٔ ناموجود = NO_SIGNAL)."""
    if mode == "off":
        return True, None
    st = MS.structure(win)
    if not st:
        return False, "ساختار محاسبه‌نشدنی"
    want = "up" if direction == "LONG" else "down"
    if mode == "aligned":
        return st["bias"] == want, st.get("last_event")
    if mode == "fresh":
        ev = st.get("last_event")
        if not ev or st.get("last_event_dir") != want:
            return False, ev
        age = (len(win) - 1) - (st.get("last_event_i") or 0)
        return age <= FRESH_BARS, f"{ev}+{age}"
    raise ValueError(f"حالت ناشناختهٔ ساختار: {mode}")


def decide(win, p, now_ms=None):
    """همان منطق scalp.decide ولی پارامترپذیر.

    عمداً بازنویسی شد نه monkeypatch: ثابت‌های ماژول در چند تابع خوانده
    می‌شوند و وصله‌زدنشان باعث می‌شود آزمون چیزی را بسنجد که تولید
    اجرا نمی‌کند."""
    if len(win) < WARMUP:
        return None
    closes = [k["c"] for k in win]
    e21 = sum(closes[-21:]) / 21
    e55 = sum(closes[-55:]) / 55
    px = closes[-1]
    if e21 > e55 and px > e55:
        d = "LONG"
    elif e21 < e55 and px < e55:
        d = "SHORT"
    else:
        return None
    i = SC._ibs(win[-1])
    if d == "LONG" and i > p["ibs_max"]:
        return None
    if d == "SHORT" and i < 1.0 - p["ibs_max"]:
        return None
    if d == "LONG":
        hi = max(k["h"] for k in win[-30:])
        lo = min(k["l"] for k in win[-8:])
        if hi <= lo or (hi - px) / (hi - lo + 1e-12) < 0.2:
            return None
        sl, risk = lo, px - lo
    else:
        lo = min(k["l"] for k in win[-30:])
        hi = max(k["h"] for k in win[-8:])
        if hi <= lo or (px - lo) / (hi - lo + 1e-12) < 0.2:
            return None
        sl, risk = hi, hi - px
    if risk <= 0:
        return None
    stop_pct = risk / px * 100
    fee_r = (SC.FEE_RT_PCT / 100) * px / risk
    if fee_r >= p["max_fee_r"]:
        return None
    lev = min(SC.LEV_MAX, int(50.0 / stop_pct) if stop_pct > 0 else SC.LEV_MAX)
    if lev < 1:
        return None
    ok, ev = struct_ok(win, d, p.get("struct", "off"))
    if not ok:
        return None
    tp = px + p["rr"] * risk if d == "LONG" else px - p["rr"] * risk
    return {"dir": d, "entry": px, "sl": sl, "tp1": tp, "risk": risk,
            "struct_event": ev,
            "stop_pct": stop_pct, "fee_r": fee_r, "lev": lev,
            "ibs": i, "session": SC.session_of(now_ms or win[-1]["t"])}


def simulate(cd, i, s, p):
    """بدترین‌حالت درون‌کندلی: استاپ بر تارگت مقدم است. تریل مثل تولید."""
    long = s["dir"] == "LONG"
    risk = s["risk"]
    sl = s["sl"]
    be = s["entry"] * (1 + 0.0015) if long else s["entry"] * (1 - 0.0015)
    third = s["entry"] + risk * p["rr"] / 3 * (1 if long else -1)
    trailed = False
    for k in cd[i + 1: i + 1 + p["hold"]]:
        if (long and k["l"] <= sl) or (not long and k["h"] >= sl):
            return ("trail", (sl - s["entry"]) / risk * (1 if long else -1)) \
                if trailed else ("stop", -1.0)
        if (long and k["h"] >= s["tp1"]) or (not long and k["l"] <= s["tp1"]):
            return ("target", p["rr"])
        if not trailed and ((long and k["h"] >= third)
                            or (not long and k["l"] <= third)):
            sl, trailed = be, True
    j = min(i + p["hold"], len(cd) - 1)
    return ("timeout", (cd[j]["c"] - s["entry"]) / risk * (1 if long else -1))


def replay(cd, p):
    """نقشه روی کندل i، نتیجه از کندل‌های بعد. بدون هم‌پوشانی."""
    out, i, n = [], WARMUP, len(cd)
    limit = n - p["hold"] - 2
    while i < limit:
        s = decide(cd[:i + 1], p)
        if not s:
            i += 2
            continue
        oc, r = simulate(cd, i, s, p)
        out.append({"R": r, "R_net": r - s["fee_r"], "outcome": oc,
                    "dir": s["dir"], "lev": s["lev"],
                    "stop_pct": s["stop_pct"], "fee_r": s["fee_r"]})
        i += p["hold"]
    return out


def boot(xs, seed=7, nb=3000):
    if len(xs) < 2:
        return None, None
    rnd = random.Random(seed)
    n = len(xs)
    m = sorted(sum(xs[rnd.randrange(n)] for _ in range(n)) / n
               for _ in range(nb))
    return m[int(0.025 * nb)], m[min(nb - 1, int(0.975 * nb))]


def t_stat(xs):
    if len(xs) < 3:
        return 0.0
    sd = statistics.stdev(xs)
    return statistics.mean(xs) / (sd / math.sqrt(len(xs))) if sd > 0 else 0.0


def score(trades, min_n=MIN_N):
    if len(trades) < min_n:
        return {"n": len(trades), "ci95": None,
                "note": f"نمونه کم ({len(trades)} < {min_n})"}
    net = [t["R_net"] for t in trades]
    lo, hi = boot(net)
    return {"n": len(trades),
            "R_gross": round(statistics.mean(t["R"] for t in trades), 4),
            "fee_R": round(statistics.mean(t["fee_r"] for t in trades), 4),
            "R_net": round(statistics.mean(net), 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "t": round(t_stat(net), 3),
            "win_rate": round(100 * sum(1 for x in net if x > 0) / len(net), 1),
            "median_stop_pct": round(
                statistics.median(t["stop_pct"] for t in trades), 3),
            "median_lev": int(statistics.median(t["lev"] for t in trades))}


def portfolio(r_net_mean, stop_pct, configs, r_net_sd=None):
    """ترجمهٔ R به دلار برای چیدمان‌های مختلف پوزیشن.

    پرسش حمید (۲۳ اوت): «به‌جای ۸ پوزیشن، ۳ پوزیشن ۳۰ دلاری با ضریب
    ۳۰ تا ۶۰ — ریسکمان منطقی‌تر نیست؟»

    ریاضیِ صریح، تا جای حدس نماند:
        ضرر یک استاپ  = مارجین × اهرم × استاپ٪
        سود/زیان انتظاری هر معامله = R خالص × همان ضرر یک استاپ
        بدترین حالتِ هم‌زمان = تعداد پوزیشن × ضرر یک استاپ

    **نکتهٔ اصلی:** تعداد و اندازهٔ پوزیشن، *امید ریاضی* را عوض
    نمی‌کنند — فقط مقیاس و پراکندگی را. اگر R خالص منفی باشد، بزرگ‌تر
    کردن پوزیشن فقط ضرر را بزرگ‌تر می‌کند. چیزی که واقعاً ریسک را کم
    می‌کند **اهرم** است، نه کم کردن تعداد پوزیشن: هر دو در فرمول بالا
    ضرب‌شونده‌اند، ولی اهرم روی *هر* پوزیشن اثر می‌گذارد.
    """
    out = []
    for c in configs:
        per_stop = c["margin"] * c["lev"] * (stop_pct / 100.0)
        row = {"label": c.get("label", ""), "n_positions": c["n"],
               "margin_each": c["margin"], "lev": c["lev"],
               "total_margin": round(c["n"] * c["margin"], 2),
               "loss_per_stop": round(per_stop, 2),
               "worst_case_all_stop": round(c["n"] * per_stop, 2),
               "expected_per_trade": round(r_net_mean * per_stop, 3)}
        row["expected_per_round"] = round(row["expected_per_trade"] * c["n"], 2)
        if r_net_sd:
            row["sd_per_trade"] = round(r_net_sd * per_stop, 2)
        out.append(row)
    return out


def compare_structure(A, B, geom, quiet=False):
    """آیا دروازهٔ ساختار ۱ دقیقه لبهٔ ناخالص را بالا می‌برد؟

    **پیش‌ثبت (پیش از دیدن نتیجه):** فرضیهٔ حمید می‌گوید بله — ساختارِ
    هم‌جهت باید R ناخالص را نسبت به پایه **بالا** ببرد. جهت پیش‌بینی
    مثبت است؛ اگر نتیجه منفی و معنادار درآمد، فرضیه **رد** می‌شود، نه
    اینکه «چیزی پیدا نشد».

    سه حالت = سه آزمون → آستانهٔ یک‌طرفهٔ Šidák روی m=۲ (دو حالتِ
    دروازه‌دار در برابر پایه؛ خودِ پایه فرضیه نیست).

    A برای اندازه‌گیری، B برای تأیید — همان تفکیک همیشگی.
    """
    from statistics import mean
    thr = multiple_test_penalty(2)
    base_trades = []
    for cd in A.values():
        base_trades += replay(cd, dict(geom, struct="off"))
    base = score(base_trades)
    rows = []
    for mode in ("aligned", "fresh"):
        tr = []
        for cd in A.values():
            tr += replay(cd, dict(geom, struct=mode))
        sc = score(tr)
        if not sc.get("ci95") or not base.get("ci95"):
            rows.append({"mode": mode, **sc, "verdict": "نمونه کم"})
            continue
        lift = sc["R_gross"] - base["R_gross"]
        # اختلاف دو نمونهٔ مستقل: بوت‌استرپ دو نمونه‌ای روی R ناخالص
        ga = [t["R"] for t in tr]
        gb = [t["R"] for t in base_trades]
        rnd = random.Random(11)
        ds = sorted((sum(ga[rnd.randrange(len(ga))] for _ in range(len(ga))) / len(ga)
                     - sum(gb[rnd.randrange(len(gb))] for _ in range(len(gb))) / len(gb))
                    for _ in range(3000))
        lo, hi = ds[75], ds[2925]
        t = t_stat([x - mean(gb) for x in ga])
        passed = lo > 0 and t >= thr
        refuted = hi < 0 and abs(t) >= thr
        rows.append({"mode": mode, **sc, "lift_gross": round(lift, 4),
                     "lift_ci95": [round(lo, 4), round(hi, 4)],
                     "t": round(t, 3), "confirms_hypothesis": passed,
                     "refutes_hypothesis": refuted,
                     "verdict": ("فرضیه تأیید شد" if passed else
                                 "فرضیه رد شد — ساختار **بدترش** کرد"
                                 if refuted else "بی‌نتیجه")})
    res = {"geometry": geom, "threshold_one_sided": thr,
           "baseline": base, "modes": rows}
    winner = next((r for r in rows if r.get("confirms_hypothesis")), None)
    if winner:
        tb = []
        for cd in B.values():
            tb += replay(cd, dict(geom, struct=winner["mode"]))
        res["confirm_b"] = score(tb)
        ok = res["confirm_b"].get("ci95") and res["confirm_b"]["ci95"][0] > 0
        res["verdict"] = (f"دروازهٔ «{winner['mode']}» روی A تأیید شد و روی B "
                          f"هم CI بالای صفر داد — نامزد واقعی" if ok else
                          f"دروازهٔ «{winner['mode']}» روی A تأیید شد ولی روی "
                          f"B نیفتاد — نویزِ جستجو")
    else:
        res["verdict"] = ("هیچ حالتی از دروازهٔ ساختار لبه را بالا نبرد؛ "
                          "تأیید خارج از نمونه اجرا نشد")
    if not quiet:
        print(f"\nدروازهٔ ساختار ۱ دقیقه (پایه: {base.get('R_gross')}R ناخالص، "
              f"n={base.get('n')})")
        for r in rows:
            print(f"  {r['mode']:<9} n={r.get('n',0):<5} "
                  f"ناخالص={r.get('R_gross',0):+.4f} "
                  f"تفاوت={r.get('lift_gross',0):+.4f} "
                  f"CI={r.get('lift_ci95')}  {r['verdict']}")
        print(f"  حکم: {res['verdict']}")
    return res


def run(bars=1500, n_symbols=60, quiet=False):
    import sources
    # `sources.top_symbols` وجود ندارد — این فراخوانی را از
    # scenario_backtest کپی کرده بودم بدون توجه به اینکه آن‌جا داخل
    # try/except با fallback است. جهانِ نمادها در hamid.trainer است.
    from hamid.trainer import top_symbols
    syms = top_symbols(n_symbols)
    if not syms:
        raise RuntimeError("جهان نماد خالی برگشت — بدون نماد جستجو معنا ندارد")
    # دو نمونهٔ **مستقل**: جستجو روی A، تأیید روی B. یک‌درمیان تا هر دو
    # نمونه ترکیب مشابهی از نقدشوندگی داشته باشند، نه اینکه B فقط
    # ته‌ماندهٔ کم‌حجم باشد.
    a_syms = [s for k, s in enumerate(syms) if k % 2 == 0]
    b_syms = [s for k, s in enumerate(syms) if k % 2 == 1]

    def load(names):
        out = {}
        for s in names:
            try:
                k = sources.klines(s, "1m", bars)
                if k and len(k) > WARMUP + 200:
                    out[s] = [{"t": x[0], "o": float(x[1]), "h": float(x[2]),
                               "l": float(x[3]), "c": float(x[4]),
                               "v": float(x[5])} for x in k]
            except Exception:                          # noqa: BLE001
                continue
        return out
    A, B = load(a_syms), load(b_syms)
    if not quiet:
        print(f"نمونهٔ A: {len(A)} نماد · نمونهٔ B: {len(B)} نماد "
              f"(هرکدام {bars} کندل ۱ دقیقه)\n")
    grid = cells()
    thr = multiple_test_penalty(len(grid))
    rows = []
    for p in grid:
        tr = []
        for cd in A.values():
            tr += replay(cd, p)
        rows.append({"params": p, **score(tr)})
    ranked = [r for r in rows if r.get("ci95")]
    ranked.sort(key=lambda r: -(r["t"] or 0))
    if not quiet:
        print(f"جستجو روی نمونهٔ A — {len(grid)} خانه، "
              f"آستانهٔ Šidák = {thr}\n")
        print(f"  {'rr':>4} {'feeR':>5} {'ibs':>5} {'hold':>5} "
              f"{'n':>5} {'خالص':>8} {'t':>6} {'استاپ٪':>7} {'اهرم':>5}  CI95")
        for r in ranked[:10]:
            p = r["params"]
            mk = "★" if (r["ci95"][0] > 0 and abs(r["t"]) >= thr) else " "
            print(f"{mk} {p['rr']:>4} {p['max_fee_r']:>5} {p['ibs_max']:>5} "
                  f"{p['hold']:>5} {r['n']:>5} {r['R_net']:>+8.4f} "
                  f"{r['t']:>6.2f} {r['median_stop_pct']:>7.3f} "
                  f"{r['median_lev']:>5}  {r['ci95']}")
    best = ranked[0] if ranked else None
    res = {"at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "bars": bars, "threshold": thr, "cells": rows,
           "sample_a_symbols": len(A), "sample_b_symbols": len(B)}
    if best and best["ci95"][0] > 0 and abs(best["t"]) >= thr:
        # تأیید: **یک** خانه، **یک** بار، روی نمونه‌ای که هرگز دیده نشده.
        tr_b = []
        for cd in B.values():
            tr_b += replay(cd, best["params"])
        conf = score(tr_b)
        res["best"] = best
        res["confirm_b"] = conf
        ok = conf.get("ci95") and conf["ci95"][0] > 0
        res["verdict"] = (
            f"خانهٔ برتر روی A رد شد و روی B هم CI بالای صفر داد "
            f"({conf.get('R_net')}R, CI {conf.get('ci95')}) — نامزد واقعی"
            if ok else
            f"خانهٔ برتر روی A رد شد ولی روی B نیفتاد "
            f"({conf.get('R_net')}R, CI {conf.get('ci95')}) — نویزِ جستجو بود")
    else:
        res["best"] = best
        res["verdict"] = ("هیچ خانه‌ای حتی روی نمونهٔ جستجو از آستانه رد "
                          "نشد — تأیید خارج از نمونه اجرا نشد، چون چیزی "
                          "برای تأیید نبود")
    if not quiet:
        print(f"\nحکم: {res['verdict']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=1500)
    ap.add_argument("--symbols", type=int, default=60)
    a = ap.parse_args()
    run(bars=a.bars, n_symbols=a.symbols)
