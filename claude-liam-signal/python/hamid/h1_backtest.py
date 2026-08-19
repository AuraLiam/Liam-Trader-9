#!/usr/bin/env python3
"""بک‌تست موتور یک‌ساعته روی کندل واقعی — با قوانین ریسک داشبورد حمید.

هیچ ادعای عملکردی بدون این فایل گفته نمی‌شود. شبیه‌ساز نیست: کندل واقعی
از همان منبع تولید، بدون نگاه به آینده (تصمیم فقط با کندل‌های تا لحظهٔ
همان کندل)، با نردبان تریل و بدترین‌حالتِ درون‌کندلی (اگر یک کندل هم استاپ
و هم تارگت را لمس کرد، استاپ فرض می‌شود).

    python3 -m hamid.h1_backtest --symbols 60 --bars 1500

خروجی: تعداد، برد٪، میانگین R خالص، بازهٔ اطمینان ۹۵٪ بوت‌استرپ، تفکیک
به‌ازای جهت/کیفیت/تجربه، و شبیه‌سازی منحنی سرمایه با ریسک ۲٪ و ۱٪ در
برابر سقف روزانهٔ ۵٪ — همان سوالی که تنظیمات داشبورد ایجاد می‌کند.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import liam9_h1_strategy as H1                                # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "signals" / "h1-backtest.json"
FEE_PCT = 0.15


def boot_ci(vals, n=2000, seed=7):
    """بازهٔ ۹۵٪ حول میانگین با بازنمونه‌گیری — قانون: عمل فقط با CI بالای صفر."""
    if len(vals) < 8:
        return (None, None)
    rnd = random.Random(seed)
    means = []
    for _ in range(n):
        s = [vals[rnd.randrange(len(vals))] for _ in range(len(vals))]
        means.append(sum(s) / len(s))
    means.sort()
    return (round(means[int(0.025 * n)], 3), round(means[int(0.975 * n)], 3))


# ── واریانت‌های مدیریت معامله ──────────────────────────────────────────────
#
# چرا واریانت: اندازه‌گیری ۱۹ اوت روی همین موتور نشان داد نرخ برد ۵۸.۴٪ ولی
# میانگین ‎−۰.۲۱۱R — چون ۳۶ معامله با تریل نزدیک صفر بسته شد و فقط ۸ تا به
# تارگت رسید، در حالی که بازنده‌ها R کامل دادند. همان الگو در دفتر اسکلپ ۱د
# هم دیده شد. پس نردبان تریل باید *سنجیده* شود، نه حدس زده.
#
# قانون تریل دستور صریح حمید است و تا نتیجهٔ CI-دار عوض نمی‌شود؛ این‌جا فقط
# اندازه می‌گیریم و گزارش می‌دهیم — تولید دست‌نخورده می‌ماند.
VARIANTS = [
    {"key": "base", "rr": None, "trail": (1 / 3, 2 / 3),
     "label": "تولید فعلی: تریل ⅓→سربه‌سر، ⅔→⅓"},
    {"key": "trail_half", "rr": None, "trail": (0.5, 0.75),
     "label": "تریل دیرتر: ½→سربه‌سر، ¾→½"},
    {"key": "no_trail", "rr": None, "trail": None,
     "label": "بدون تریل: فقط استاپ و تارگت"},
    {"key": "tp15", "rr": 1.5, "trail": (1 / 3, 2 / 3),
     "label": "تارگت نزدیک‌تر ۱.۵R با تریل فعلی"},
    {"key": "tp15_no_trail", "rr": 1.5, "trail": None,
     "label": "تارگت ۱.۵R بدون تریل"},
]


# ── فیلترهای ورود ──────────────────────────────────────────────────────────
#
# اندازه‌گیری ۱۹ اوت (۸۰۴ معامله، ۶۳ نماد، کندل واقعی): پایه ‎−۰.۱۰۶R با
# CI کاملاً زیر صفر، و هر پنج واریانت مدیریت خروج هم منفی. یعنی مشکل خروج
# نیست، *ورود* است. فرق ساختاری با موتور پنل (که sig-ibs با ۶۷٪ برد و
# ‎+۰.۰۸۴R دارد) این است: پنل بعد از پولبک منتظر تریگر می‌ماند
# (ریکلیم/میکرو-BOS) و چند دروازهٔ دیگر هم دارد؛ این نسخه همان‌جا وارد
# می‌شود. پس فیلترها را روی همان ورودها می‌سنجیم، نه با حدس.
ENTRY_FILTERS = [
    {"key": "all", "label": "بدون فیلتر (پایه)"},
    {"key": "confirm", "label": "فقط با کندل تأیید هم‌جهت"},
    {"key": "q70", "label": "فقط کیفیت ≥۷۰"},
    {"key": "reclaim", "label": "فقط با ریکلیم: کلوز بالای سقف کندل قبل"},
    {"key": "confirm_reclaim", "label": "کندل تأیید + ریکلیم"},
    {"key": "short_only", "label": "فقط شورت (جهتِ کم‌ضررتر در نمونه)"},
]


def _entry_passes(key, sig, c1h_upto):
    if key == "all":
        return True
    if key == "confirm":
        return sig.get("pattern_align") == "with"
    if key == "q70":
        return sig.get("quality", 0) >= 70
    if key == "short_only":
        return sig["action"] == "SHORT"
    reclaim = _has_reclaim(sig["action"], c1h_upto)
    if key == "reclaim":
        return reclaim
    if key == "confirm_reclaim":
        return reclaim and sig.get("pattern_align") == "with"
    return True


def _has_reclaim(direction, cd):
    """تریگر ورود: کندل آخر سقف/کف کندل قبلی را پس گرفته است.

    همان چیزی که موتور پنل روی ۵د می‌خواهد (reclaim/micro-BOS) — این‌جا
    روی ۱س، چون تایم اجرا همان است."""
    if len(cd) < 2:
        return False
    k, p = cd[-1], cd[-2]
    return k["c"] > p["h"] if direction == "LONG" else k["c"] < p["l"]


def _shape(sig, variant):
    """سیگنال واحد را به هندسهٔ یک واریانت درمی‌آورد (ورود و استاپ ثابت)."""
    pos = dict(sig)
    entry, sl0 = sig["entry"], sig["sl"]
    risk = abs(entry - sl0)
    rr = variant["rr"] or H1.P["rr_target"]
    pos["tp1"] = entry + rr * risk if sig["action"] == "LONG" \
        else entry - rr * risk
    if variant["trail"] is None:
        far = 10.0                            # پله‌ای که هرگز لمس نمی‌شود
        pos["trail"] = {"step1_at": entry + far * risk * (1 if sig["action"] == "LONG" else -1),
                        "step1_sl": sl0,
                        "step2_at": entry + far * risk * (1 if sig["action"] == "LONG" else -1),
                        "step2_sl": sl0, "rule": "بدون تریل"}
        return pos
    f1, f2 = variant["trail"]
    span = pos["tp1"] - entry
    pad = H1.P["breakeven_pad_pct"] / 100
    pos["trail"] = {
        "step1_at": entry + span * f1,
        "step1_sl": entry * (1 + pad) if sig["action"] == "LONG"
        else entry * (1 - pad),
        "step2_at": entry + span * f2,
        "step2_sl": entry + span * f1,
        "rule": variant["label"]}
    return pos


def _run_one(pos, c1h, i, sig):
    """یک پوزیشن را تا نتیجه جلو می‌برد. بدترین حالت درون‌کندلی: استاپ اول."""
    sl, res, bars, exit_px = pos["sl"], None, 0, None
    for k in c1h[i + 1: i + 1 + H1.P["max_hold_bars"]]:
        bars += 1
        pos["sl"] = sl
        ev = H1.manage(pos, k)
        if ev["event"] == "STOP":
            moved = abs(sl - sig["sl"]) > 1e-12
            res, exit_px = ("trail" if moved else "stop"), sl
            break
        if ev["event"] == "TARGET":
            res, exit_px = "target", pos["tp1"]
            break
        if ev["event"] == "TRAIL":
            sl = ev["sl"]
    if res is None:
        res = "timeout"
        exit_px = c1h[min(i + H1.P["max_hold_bars"], len(c1h) - 1)]["c"]
    risk = abs(sig["entry"] - sig["sl"])
    r = ((exit_px - sig["entry"]) if sig["action"] == "LONG"
         else (sig["entry"] - exit_px)) / risk
    fee_r = (FEE_PCT / 100) * sig["entry"] / risk
    return res, round(r, 3), round(r - fee_r, 3), bars


def replay_symbol(sym, c1h, c4h, step=1, variants=None):
    """هر کندل ۱س را جلو می‌برد؛ هر ستاپ با همهٔ واریانت‌ها سنجیده می‌شود.

    ورودها برای همهٔ واریانت‌ها یکی است، پس مقایسه منصفانه است. جلو رفتن
    ضدهم‌پوشانی با طول معاملهٔ واریانت پایه انجام می‌شود."""
    vs = variants or VARIANTS
    out = {v["key"]: [] for v in vs}
    out.update({"entry:" + f["key"]: [] for f in ENTRY_FILTERS})
    i = 260                                   # به‌اندازهٔ EMA200 تاریخ لازم است
    while i < len(c1h) - 2:
        t_now = c1h[i]["t"]                   # میدان ۴س فقط تا همان لحظه
        c4 = [k for k in c4h if k["t"] <= t_now]
        if len(c4) < 220:
            i += step
            continue
        window = c1h[:i + 1]
        sig = H1.analyze(sym, c4, window)
        if sig["action"] == "NO_SIGNAL":
            i += step
            continue
        base_bars, base_row = 1, None
        for v in vs:
            res, r, r_net, bars = _run_one(_shape(sig, v), c1h, i, sig)
            row = {"sym": sym, "dir": sig["action"], "outcome": res,
                   "R": r, "R_net": r_net, "quality": sig["quality"],
                   "stop_pct": sig["stop_pct"], "exp_used": sig["exp_used"],
                   "bars": bars, "opened": c1h[i]["t"]}
            if v["key"] == "base":
                base_bars, base_row = bars, row
            out[v["key"]].append(row)
        # فیلترهای ورود روی همان معاملهٔ پایه سنجیده می‌شوند — تفاوت فقط
        # «وارد می‌شدیم یا نه»، نه نحوهٔ خروج.
        for f in ENTRY_FILTERS:
            if _entry_passes(f["key"], sig, window):
                out["entry:" + f["key"]].append(base_row)
        i += base_bars + 1                     # ضدهم‌پوشانی
    return out


def equity_curve(trades, risk_pct, daily_cap_pct=5.0, start=1000.0):
    """منحنی سرمایه با قوانین داشبورد — سقف روزانه واقعاً اعمال می‌شود."""
    eq, day, day_loss, blocked = start, None, 0.0, 0
    peak, max_dd = start, 0.0
    for t in sorted(trades, key=lambda x: x["opened"]):
        d = time.strftime("%Y-%m-%d", time.gmtime(t["opened"] / 1000))
        if d != day:
            day, day_loss = d, 0.0
        if day_loss >= daily_cap_pct:
            blocked += 1
            continue
        pnl_pct = t["R_net"] * risk_pct
        eq *= (1 + pnl_pct / 100)
        if pnl_pct < 0:
            day_loss += abs(pnl_pct)
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak * 100)
    return {"risk_pct": risk_pct, "final": round(eq, 2),
            "return_pct": round((eq / start - 1) * 100, 2),
            "max_drawdown_pct": round(max_dd, 2), "blocked_by_daily_cap": blocked}


def describe(name, trades):
    if not trades:
        return {"name": name, "n": 0}
    rs = [t["R_net"] for t in trades]
    w = sum(1 for t in trades if t["R"] > 0)
    lo, hi = boot_ci(rs)
    return {"name": name, "n": len(trades),
            "win_pct": round(100 * w / len(trades), 1),
            "mean_r_net": round(sum(rs) / len(rs), 3),
            "ci95": [lo, hi], "positive": bool(lo is not None and lo > 0)}


def run(symbols=60, bars=1000, quiet=False):
    """bars پیش‌فرض ۱۰۰۰ است، نه ۱۵۰۰: sources.sane هر سری کوتاه‌تر از ۹۰٪
    درخواست را رد می‌کند و بیشتر صرافی‌ها سقف ۱۰۰۰ کندل دارند — با ۱۵۰۰،
    ۵۲ نماد از ۶۰ در سکوت افتادند و نمونه به ۷۷ معامله رسید (۱۹ اوت)."""
    import sources
    try:
        syms = sources.top_symbols(symbols)
    except Exception:                                    # noqa: BLE001
        from hamid.trainer import top_symbols
        syms = top_symbols(symbols)
    books, done = {v["key"]: [] for v in VARIANTS}, 0
    # ردشدن در سکوت ممنوع: ۱۹ اوت یک بک‌تست ۱۲۰ نمادی با ۸ نماد اجرا شد
    # چون «4h» در هیچ نگاشت صرافی نبود و ۱۱۲ استثنا بی‌صدا بلعیده شد.
    drops = {}
    for s in syms:
        try:
            k1 = sources.klines(s, "1h", bars)
            k4 = sources.klines(s, "4h", 400)
        except Exception as e:                           # noqa: BLE001
            drops[type(e).__name__] = drops.get(type(e).__name__, 0) + 1
            continue
        if not k1 or not k4 or len(k1) < 400 or len(k4) < 260:
            drops["سری کوتاه"] = drops.get("سری کوتاه", 0) + 1
            continue
        c1 = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4]} for k in k1]
        c4 = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4]} for k in k4]
        part = replay_symbol(s, c1, c4)
        for k, v in part.items():
            books[k] += v
        done += 1
        if not quiet and done % 10 == 0:
            print(f"  {done}/{len(syms)} نماد — {len(books['base'])} معامله")
    skipped = sum(drops.values())
    if not quiet and skipped:
        print(f"  {skipped} نماد رد شد: {drops}")

    all_tr = books["base"]
    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "engine": H1.P["version"], "symbols": done, "skipped": skipped, "drop_reasons": drops,
           "bars": bars,
           "source": "کندل واقعی ۱ ساعته (نه شبیه‌ساز)",
           "variants": [dict(describe(v["label"], books[v["key"]]),
                             key=v["key"],
                             equity2=equity_curve(books[v["key"]], 2.0),
                             equity1=equity_curve(books[v["key"]], 1.0),
                             outcomes={o: sum(1 for t in books[v["key"]]
                                              if t["outcome"] == o)
                                       for o in ("target", "trail", "stop",
                                                 "timeout")})
                        for v in VARIANTS],
           "entry_filters": [dict(describe(f["label"], books["entry:" + f["key"]]),
                                  key=f["key"],
                                  equity1=equity_curve(books["entry:" + f["key"]], 1.0),
                                  outcomes={o: sum(1 for t in books["entry:" + f["key"]]
                                                   if t["outcome"] == o)
                                            for o in ("target", "trail", "stop",
                                                      "timeout")})
                             for f in ENTRY_FILTERS],
           "overall": describe("کل", all_tr),
           "by_dir": [describe(d, [t for t in all_tr if t["dir"] == d])
                      for d in ("LONG", "SHORT")],
           "by_quality": [
               describe("کیفیت ≥۷۵", [t for t in all_tr if t["quality"] >= 75]),
               describe("کیفیت ۶۰–۷۴", [t for t in all_tr
                                        if 60 <= t["quality"] < 75]),
               describe("کیفیت <۶۰", [t for t in all_tr if t["quality"] < 60])],
           "by_experience": [
               describe("با تجربه", [t for t in all_tr if t["exp_used"]]),
               describe("بدون تجربه", [t for t in all_tr if not t["exp_used"]])],
           "outcomes": {o: sum(1 for t in all_tr if t["outcome"] == o)
                        for o in ("target", "trail", "stop", "timeout")},
           "equity": [equity_curve(all_tr, 2.0), equity_curve(all_tr, 1.0)]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        o = res["overall"]
        print(f"\n== موتور ۱ ساعته روی کندل واقعی ==")
        print(f"معامله {o['n']} · برد {o.get('win_pct')}٪ · "
              f"میانگین {o.get('mean_r_net')}R خالص · CI95 {o.get('ci95')}")
        print("نتایج:", res["outcomes"])
        for e in res["equity"]:
            print(f"ریسک {e['risk_pct']}٪ → بازده {e['return_pct']}٪ · "
                  f"افت حداکثر {e['max_drawdown_pct']}٪ · "
                  f"{e['blocked_by_daily_cap']} معامله قربانی سقف روزانه")
        print("\n== فیلترهای ورود (خروج یکی، ورود فرق دارد) ==")
        for f in res["entry_filters"]:
            flag = "✅ CI بالای صفر" if f.get("positive") else ""
            print(f"  {f['name']}: n={f['n']} برد={f.get('win_pct')}٪ "
                  f"R={f.get('mean_r_net')} CI={f.get('ci95')} {flag}")
        print("\n== واریانت‌های مدیریت معامله (ورودها یکی، خروج فرق دارد) ==")
        for v in res["variants"]:
            flag = "✅ CI بالای صفر" if v.get("positive") else ""
            print(f"  {v['name']}: n={v['n']} برد={v.get('win_pct')}٪ "
                  f"میانگین={v.get('mean_r_net')}R CI={v.get('ci95')} {flag}")
            print(f"     نتایج {v['outcomes']} · ریسک۱٪ بازده "
                  f"{v['equity1']['return_pct']}٪ افت {v['equity1']['max_drawdown_pct']}٪")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=60)
    ap.add_argument("--bars", type=int, default=1000)
    a = ap.parse_args()
    run(symbols=a.symbols, bars=a.bars)
