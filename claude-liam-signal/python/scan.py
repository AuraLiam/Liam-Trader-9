#!/usr/bin/env python3
"""What the engine says about the market right now, on real candles.

The panel normally does this itself in the browser. Where Binance is
unreachable — which is most of Iran, and this project's own container — the
panel has nothing to chart and correctly says so instead of inventing a signal.
This script does the same work somewhere the network reaches, and writes the
result to signals/latest.json for the panel to display.

Nothing here decides anything the engine would not have decided. Same engine,
same gates, same thresholds, lifted out of index.html. The only judgement added
is the ordering, which follows what the real-candle backtest measured:

    5m   n=1860  win 27.6%  E=+0.141R  [+0.062, +0.220]   edge, interval clear
    15m  n=2071  win 18.3%  E=+0.005R  [-0.052, +0.063]   no measurable edge

So a 5m setup outranks a 15m one of the same stage. That is a ranking, not a
gate — 15m spanning zero means no evidence of an edge, not evidence of none, and
switching it off is a bigger claim than one 52-day window supports.

    python3 scan.py --symbols 100 --telegram
"""
import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
# سرویس سایهٔ محلی (۲ سپتامبر، قانون ۰۲) خروجی‌اش را کنار دفتر تولید می‌نویسد
# نه روی آن: LIAM9_SIGNALS_DIR=signals/shadow. پیش‌فرض همان signals/ است.
OUT = Path(os.environ.get("LIAM9_SIGNALS_DIR") or (ROOT / "signals"))
if not OUT.is_absolute():
    OUT = ROOT / OUT
sys.path.insert(0, str(HERE))
from backtest import get, top_symbols, MS          # same fetching, same retries
import sources                                      # the venue that actually served
import brain                                        # permanent memory

BARS = 420                                          # engine sees 400 after the open one goes
STAGE_RANK = {"SIGNAL": 3, "ARMED": 2, "PULLBACK_1": 1, "WATCH": 0}
TF_RANK = {"5m": 1, "15m": 0}                       # measured, see the docstring
STRATS = {"smc": "کانال + اردر بلاک", "ibs": "IBS + پولبک"}

# ── ترجیح استراتژی، زمان‌دار و از فایل (دستور صریح حمید، ۳۰ اوت شب) ────────
# «ارز یونی با smc|5m|LONG صادر شده بود — تا فردا همان مدل اولویت بگیرد.»
#
# سه قید که این را از «شل‌کردن دروازه» جدا می‌کند:
#   ۱. فقط **ترتیبِ** نامزدها عوض می‌شود. هیچ آستانه‌ای جابه‌جا نمی‌شود و
#      هیچ استراتژی‌ای خاموش نمی‌شود — ibs سرِ جایش است.
#   ۲. جایش در کلیدِ مرتب‌سازی **بعد از** مرحله و تایم‌فریم است. تایم‌فریم
#      یک سنجهٔ اثبات‌شده است (۵د روی کندل واقعی CI بالای صفر داشت، ۱۵د نه)
#      و ترجیحِ بی‌سنجش حق ندارد سنجهٔ اثبات‌شده را کنار بزند.
#   ۳. سررسید دارد. پشت این ترجیح CI نیست (smc −۰.۰۴۴R با n=۷۲ در برابر
#      ibs −۰.۱۱۷R با n=۱۵۰ — بازه‌ها روی هم می‌افتند)، پس بعد از سررسید
#      خودبه‌خود خنثی می‌شود، نه این‌که بی‌صدا ابدی بماند.
PRIORITY_CFG = ROOT / "config" / "strategy_priority.json"


def strategy_priority(now_ms=None):
    """(استراتژیِ مرجَح یا None، بستهٔ توضیح) — از فایل، نه کدِ سخت."""
    now = now_ms or int(time.time() * 1000)
    try:
        c = json.loads(PRIORITY_CFG.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return None, {"active": False, "why": "فایل ترجیح نیست — حالت خنثی"}
    pref, until = c.get("prefer"), c.get("until")
    if pref not in STRATS:
        return None, {"active": False, "why": f"استراتژی ناشناخته: {pref!r}"}
    if not isinstance(until, (int, float)):
        return None, {"active": False, "why": "ترجیحِ بی‌سررسید پذیرفته نمی‌شود"}
    if now >= until:
        return None, {"active": False, "prefer": pref, "expired": True,
                      "why": f"سررسید ترجیح {pref} گذشته — حالت خنثی"}
    return pref, {"active": True, "prefer": pref, "until": until,
                  "until_text": c.get("until_text"),
                  "set_by": c.get("set_by"), "scope": c.get("scope")}


def klines_now(sym, tf, bars=BARS):
    # ترجیح منبع (۲ سپتامبر، دستور حمید): LIAM9_CANDLES=perp → اول بیت‌یونیکس
    # پرپچوال و بعد بقیهٔ پرپ‌ها؛ اسپاتِ تاریخی پشتیبان می‌ماند تا هیچ اسکنی
    # بی‌کندل نشود («گزینهٔ جایگزین همیشه باید وجود داشته باشد»).
    if sources.CANDLE_SOURCE == "perp":
        try:
            # از sources.klines، نه مستقیم perp_klines: همان‌جا پشتیبان اسپات و
            # بررسی هویت قرارداد (PUMPUSDT ۱۷۱٪ دور از اسپات، کاوش ۹) نشسته است.
            rows = sources.klines(sym, tf, bars)
            return [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
                     "c": float(k[4]), "v": float(k[5])} for k in rows]
        except Exception:                            # noqa: BLE001 - پشتیبان اسپات
            pass
    rows = get(f"/api/v3/klines?symbol={sym}&interval={tf}&limit={bars}")
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
             "c": float(k[4]), "v": float(k[5])} for k in rows]


def _source_label():
    """Say which venue the numbers came from, not which one was asked first.

    This line is printed on the panel. It read "real Binance candles" whether or
    not Binance had served them, which is the kind of caption that is true until
    the day it silently is not."""
    # اثبات سوییچ پرپ (۲ سپتامبر): «آخرین صرافی» گمراه می‌کرد — اسکنِ اولِ
    # بعد از سوییچ ۱۰۰+ نماد از بیت‌یونیکس گرفت ولی چون آخرین نماد به اسپات
    # بایننس افتاد، برچسب «Binance» شد. حالا شمارشِ هر صرافی چاپ می‌شود.
    counts = sources.used_counts()
    if not counts:
        where = sources.used().get("klines")
        if where is None:
            return "کندل واقعی بایننس، اسکن‌شده روی رانر گیت‌هاب"
        return f"کندل واقعی {sources.venue_label(where)}، اسکن‌شده روی رانر گیت‌هاب"
    parts = " · ".join(f"{sources.venue_label(k)} {n}" for k, n in
                       sorted(counts.items(), key=lambda kv: -kv[1])[:4])
    return f"کندل واقعی — {parts} (شمار سری‌ها)، اسکن‌شده روی رانر گیت‌هاب"


def top_by_48h(n):
    """The most-traded pairs over the last 48 hours, not the last 24.

    Binance's ticker endpoint only reports a rolling 24h window, so using it
    would quietly answer a different question from the one asked. Summing 48
    hourly candles per pair costs one extra request each and answers the actual
    one. The 24h ranking is used only to decide which pairs are worth measuring
    properly — a coin outside the top 250 by day is not going to enter the top
    100 by two days.
    """
    shortlist = top_symbols(250)
    vols = {}

    def vol48(sym):
        rows = get(f"/api/v3/klines?symbol={sym}&interval=1h&limit=48")
        return sym, sum(float(r[7]) for r in rows)      # index 7 is quote volume

    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(vol48, s) for s in shortlist]:
            try:
                sym, v = f.result()
                vols[sym] = v
            except Exception:                            # noqa: BLE001 - drop what will not answer
                continue
    ranked = sorted(vols.items(), key=lambda kv: -kv[1])
    return [s for s, _ in ranked[:n]]


# ── پهنای دید: هسته + دُمِ چرخان (اصلاح ۱ سپتامبر) ──────────────────────
#
# سند می‌گوید «پایش ۲۰۰ ارز»، ولی اندازه‌گیری روی ۳ روز گذشته: از ۳۳۲
# اسکنِ ثبت‌شده، **۳۲۵ تا ۶۰ نمادی** بودند و فقط **۵ تا ۲۰۰ نمادی** —
# یعنی اسکنِ پهن ۱.۷ بار در روز اجرا شده، نه هر ۱۵ دقیقه. علتش همان
# چیزی است که خودِ `live-scan.yml` در سرآیندش نوشته: کرونِ `*/N` روی
# حساب رایگان انداخته می‌شود (همان کلاسِ گزارش ساعتیِ دامیننس).
#
# و چون زنجیره همیشه **همان ۶۰ نمادِ اولِ حجم** را می‌گیرد، رتبه‌های ۶۱
# تا ۲۰۰ عملاً هرگز دیده نمی‌شوند. اثرش روی محصول در ممیزی ۳۰ اوت
# شمرده شده بود: ۳۱ نمادِ یکتا از ۶۸ ارسال در ۷ روز، در حالی که سقف
# روزانه هرگز پر نمی‌شد.
#
# درمان، بالا بردن هزینهٔ هر اجرا نیست (زمانِ زنجیره محدود است) بلکه
# **چرخاندن** است: هستهٔ پرنقدینگی هر بار اسکن می‌شود — بی‌آن، بیت‌کوین
# دو-سومِ اوقات دیده نمی‌شد و بسترِ اجباریِ قانون ۳ می‌شکست — و بقیهٔ
# ظرفیت روی دُم می‌چرخد تا در چند اجرا کلِ میدان پوشیده شود.
#
# هیچ دروازهٔ تحلیلی عوض نمی‌شود؛ فقط میدانِ دید به اندازهٔ سندش برمی‌گردد.
def rotating_field(n, universe=200, core=30, slot=None):
    """`n` نماد: `core` تای اول همیشه + بقیه از دُم، با چرخشِ قطعی.

    `slot` از زمان می‌آید تا اجراهای پیاپیِ زنجیره برشِ متفاوتی بگیرند؛
    قطعی است (نه تصادفی) تا بازتولیدپذیر بماند.
    """
    if universe <= n:                                # چرخش بی‌معنا
        return top_by_48h(n)
    ranked = top_by_48h(universe)
    core = max(0, min(core, n, len(ranked)))
    head, tail = ranked[:core], ranked[core:]
    want = n - core
    if want <= 0 or not tail:
        return head[:n]
    if slot is None:
        slot = int(time.time() // 300)               # هر ۵ دقیقه یک برش
    start = (slot * want) % len(tail)
    picked = [tail[(start + i) % len(tail)] for i in range(min(want, len(tail)))]
    return head + picked


def ctx_dir(setup):
    """The market direction the mined history was keyed on. The live scan has no
    per-setup dominance series, so this stays '?' and the lookup falls back to
    the symbol record — which is the honest degradation, not a guess."""
    return setup.get("dom_dir", "?")


def usdt_dominance():
    """Context only — it never decides, it can only conflict with a direction."""
    try:
        rows = get("/api/v3/ticker/24hr")
        by = {r["symbol"]: r for r in rows}
        btc = by.get("BTCUSDT")
        if not btc:
            return None
        return {"btcChange": float(btc["priceChangePercent"])}
    except Exception:                                # noqa: BLE001 - context is optional
        return None


def _btc_dir_by_tf(jobs):
    """Same definition the miner stored: close now against 8 bars ago on the
    same grid, with a ±0.25% dead zone. A different definition here would make
    the mined rule and the live test mean different things."""
    out = {}
    for j in jobs:
        if j["sym"] != "BTCUSDT":
            continue
        cd = j["candles"]
        if len(cd) > 8:
            chg = (cd[-1]["c"] - cd[-9]["c"]) / cd[-9]["c"] * 100
            out[j["tf"]] = "UP" if chg > 0.25 else "DOWN" if chg < -0.25 else "FLAT"
    return out


def _room_r(s):
    r = s.get("room")
    return r["r"] if isinstance(r, dict) else (r or 0)


# Mirrors mine.py's CONDITIONS over the live setup's fields. A condition the
# live setup cannot express exactly (the channel family) is absent on purpose:
# skipped is honest, approximated is a different rule wearing the same name.
RULE_TESTS = {
    "FVG هم‌جهت دارد": lambda s, b: bool(s.get("fvg")),
    "روی سطح کلیدی": lambda s, b: bool(s.get("level")),
    "ADX بالای ۲۵": lambda s, b: (s.get("adx") or 0) >= 25,
    "ADX زیر ۲۰": lambda s, b: (s.get("adx") or 99) < 20,
    "پولبک دوم یا بیشتر": lambda s, b: (s.get("visits") or 0) >= 2,
    "نقدینگی جمع شده": lambda s, b: bool(s.get("swept")),
    "جای حرکت بیش از ۱.۵ برابر": lambda s, b: _room_r(s) >= 1.5,
    "جای حرکت کمتر از ۱ برابر": lambda s, b: 0 < _room_r(s) < 1,
    "R:R بالای ۲.۵": lambda s, b: (s.get("rr") or 0) >= 2.5,
    "CHOCH دارد": lambda s, b: s.get("choch") == 1,
    "داخل اردر بلاک": lambda s, b: s.get("inOB") == 1 or s.get("inside") is True,
    "بیت‌کوین صعودی": lambda s, b: b == "UP",
    "بیت‌کوین نزولی": lambda s, b: b == "DOWN",
    "لانگ همسو با بیت‌کوین": lambda s, b: s.get("dir") == "LONG" and b == "UP",
    "شورت همسو با بیت‌کوین": lambda s, b: s.get("dir") == "SHORT" and b == "DOWN",
    "لانگ خلاف بیت‌کوین": lambda s, b: s.get("dir") == "LONG" and b == "DOWN",
    "شورت خلاف بیت‌کوین": lambda s, b: s.get("dir") == "SHORT" and b == "UP",
}


def confirmed_rules():
    """قانون‌هایی که بازهٔ بوت‌استرپشان صفر را رد کرده — تنها یادگیریِ مجاز به عمل.

    brain/backtests/latest.json is remeasured every morning on real candles, so
    a condition the tape stopped rewarding loses its seat at the next morning's
    remeasure without anyone editing this file."""
    try:
        j = json.loads((ROOT / "brain" / "backtests" / "latest.json").read_text())
    except Exception:                                # noqa: BLE001 - no backtest yet is a valid state
        return {}
    rules = {}
    for strat, rs in (j.get("reasons") or {}).items():
        keep = [r for r in rs if r.get("ci") and (r["ci"][0] > 0 or r["ci"][1] < 0)]
        if keep:
            rules[strat] = keep
    return rules


def apply_learned_rules(setups, jobs, rules):
    """The nightly backtest's confirmed lessons, applied instead of just stored.

    Only conditions whose bootstrap interval cleared zero act here, and each
    acts with its measured delta as a signed weight. The measurement decides;
    this code only obeys it. A setup that matches at least one confirmed
    positive rule and no confirmed negative one is tagged `elite` — the
    competition tier the panel shows separately, so its record can be judged
    on its own."""
    if not rules:
        return 0
    btc = _btc_dir_by_tf(jobs)
    n = 0
    for s in setups:
        hits, total = [], 0.0
        for r in rules.get(s.get("strategy"), []):
            test = RULE_TESTS.get(r["condition"])
            if not test:
                continue
            try:
                if test(s, btc.get(s["tf"])):
                    total += r["delta"]
                    hits.append({"rule": r["condition"], "delta": r["delta"]})
            except Exception:                        # noqa: BLE001 - one odd field must not kill the scan
                continue
        if hits:
            s["learned"] = {"boost": round(total, 3), "rules": hits}
            s["elite"] = all(h["delta"] > 0 for h in hits)
            n += 1
        else:
            s["elite"] = False
    return n


def funnel_report(setups, sent, demoted, held, series, failed,
                  pre_gate=None, demoted_dirs=None):
    """قیف سلامت سیگنال — قانون ۰۷ (E23). سکوت باید با شواهد توضیح داده شود.

    تا امروز دلیل رد فقط در لاگ Actions چاپ می‌شد و بعد گم می‌شد؛ هر بار
    «چرا سیگنال کم است؟» یعنی کاوش دستی لاگ. حالا هر اسکن قیف را در
    signals/funnel.json می‌نویسد: ورودی هر دروازه، تعداد رد، دلایل اصلی و
    یک طبقه‌بندی صریح. هیچ آستانه‌ای این‌جا عوض نمی‌شود — فقط ثبت."""
    from collections import Counter
    stages = Counter(s.get("stage") for s in setups)
    reasons = Counter()
    for s in setups:
        why = s.get("skip") or s.get("waitReason")
        if why and s.get("stage") != "SIGNAL":
            reasons[str(why).split("—")[0].strip()[:60]] += 1
    n_sig = stages.get("SIGNAL", 0)
    if not series or (failed and not setups):
        cls = "PIPELINE_DEGRADED"
    elif sent:
        cls = "SIGNAL_READY"
    elif n_sig:
        cls = "SIGNAL_SUPPRESSED_BY_RISK"   # ساخته شد ولی دروازهٔ ارسال نگذاشت
    else:
        cls = "NO_VALID_SETUP_HEALTHY"      # سکوتِ سالم — عیب نیست
    return {
        "generated": int(time.time() * 1000),
        "panel": "لیام تریدر ۹",
        "classification": cls,
        "series_fetched": series, "series_failed": failed,
        "setups": len(setups), "stages": dict(stages),
        # ── جهت، و مهم‌تر: جهتِ **پیش از دروازه** (۶ سپتامبر) ──────────
        #
        # سؤال حمید: «علت اینکه سیگنال شورت پیدا نمیشود باید دقیق بررسی
        # شود.» با فیلدهای قبلی اصلاً قابل جواب نبود: قیف فقط شمارِ کلِ
        # ستاپ را داشت، نه جهتش — پس معلوم نمی‌شد موتور شورت **نمی‌سازد**
        # یا می‌سازد و دروازه **می‌کشدش**. بدتر، این تابع بعد از
        # `gate_stages` صدا زده می‌شود، یعنی وضعیتِ پیش-دروازه تا امروز
        # بازیابی‌ناپذیر بود. حالا عکسِ پیش-دروازه در `main` گرفته و
        # همین‌جا ثبت می‌شود. هیچ آستانه‌ای عوض نشد — فقط شمردنی شد.
        "dirs": dict(Counter((s.get("dir") or "?") for s in setups)),
        "stage_dir_post_gate": {f"{k[0]}|{k[1]}": v for k, v in
                                Counter((s.get("stage"), s.get("dir") or "?")
                                        for s in setups).items()},
        "stage_dir_pre_gate": ({f"{k[0]}|{k[1]}": v
                                for k, v in (pre_gate or {}).items()}
                               if pre_gate else None),
        "trend_gate_demoted_dirs": dict(demoted_dirs or {}) or None,
        "learning_held": held, "trend_gate_demoted": demoted,
        "telegram_sent": sent,
        "top_reasons": dict(reasons.most_common(10)),
        "note": ("سکوت طولانی لزوماً خرابی نیست؛ این فایل تفاوت «ستاپ نبود» "
                 "با «زنجیره خراب بود» را با عدد نشان می‌دهد (قانون ۰۷)"),
    }


# ── برشِ دومِ دفترِ ضدواقع: مرحلهٔ منتشرشونده (دستور حمید، ۶ سپتامبر) ──────
#
# «اون برش جدا رو هم بساز که سریع‌تر پر بشه.»
#
# دو جمعیتِ **جدا**، چون دو سؤال جدا هستند:
#   `gate-vetoed`  — ستاپی که تا گلوگاه ارسال رفت و فقط دروازهٔ روند
#                    نگذاشت. ضدواقعِ تمیز، ولی کم‌حجم.
#   `stage-vetoed` — ستاپی که در مرحلهٔ انتشار تنزل خورد. پرحجم‌تر، ولی
#                    از دروازه‌های پایین‌دست (ضدتکرار، بازجویی، سقف روزانه)
#                    رد نشده — پس نمونه‌اش «سیگنالی که می‌رفت» نیست.
#
# **هرگز با هم جمع نمی‌شوند.** پول‌کردنشان یعنی حکمی که معلوم نیست دربارهٔ
# چیست. `gate_verdict` هر کدام را جدا داوری می‌کند.
#
# سه مهارِ سیل — بدون این‌ها روزی ~۲۰٬۰۰۰ ردیف می‌شد (۲۰۵ تنزل × ۹۶ اسکن):
#   ۱. فقط ستاپی که **SIGNAL** بوده؛ ARMED/PULLBACK ضعیف‌ترند و قرار
#      نبود سیگنال شوند.
#   ۲. ضدتکرار روی دفترِ **باز**: تا ردیفِ قبلیِ همان (نماد، جهت) بسته
#      نشده، ردیف تازه باز نمی‌شود. حافظهٔ تازه‌ای لازم ندارد — از همان
#      وضعیتی می‌خواند که از قبل هست (قانون ۰۵: نویسندهٔ تازه نساز).
#   ۳. سقف سختِ هر اجرا.
STAGE_VETO_CAP = 12


def _stage_veto_open_keys():
    """(نماد، جهت)هایی که همین حالا ردیفِ بازِ برشِ مرحله دارند."""
    out = set()
    try:
        from hamid import paper as _p
        p = Path(_p.OPEN)
        if not p.exists():
            return out
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:                        # noqa: BLE001
                continue
            st = (r.get("why") or {}).get("stage") or r.get("stage_tag")
            if st == "stage-vetoed":
                out.add((r.get("sym"), (r.get("dir") or "").upper()))
    except Exception:                                # noqa: BLE001
        pass
    return out


def _stage_veto_ledger(s, a, was_stage, sv):
    """ردیفِ ضدواقعِ برشِ مرحله — بی‌صدا نمی‌افتد، ولی تنزل را هم نمی‌گیرد."""
    if was_stage != "SIGNAL" or sv["n"] >= STAGE_VETO_CAP:
        return
    key = (s.get("sym"), (s.get("dir") or "").upper())
    if key in sv["open"]:
        return
    if not (s.get("entry") and s.get("sl")):
        return
    try:
        from hamid import paper as _p
        n = _p.open_from(
            [{"symbol": s["sym"], "dir": s["dir"], "entry": s["entry"],
              "sl": s["sl"], "tp1": s.get("tp1") or s["entry"],
              "tp2": s.get("tp2"), "stage_tag": "stage-vetoed",
              "tf": s.get("tf")}],
            {"veto_why": "trend_gate_stage",
             "gate_reason": str(a.get("reason") or "")[:120],
             "trend_4h": a.get("t4"), "trend_1h": a.get("t1"),
             "trend_mode": a.get("mode"), "quality": s.get("quality"),
             "was_stage": was_stage})
        if n:
            sv["n"] += 1
            sv["open"].add(key)
        else:
            print(f"  ⚠️ برشِ مرحله {s.get('sym')}: ردیف ساخته نشد", flush=True)
    except Exception as e:                           # noqa: BLE001
        print(f"  ⚠️ برشِ مرحله {s.get('sym')}: {type(e).__name__}: {e}",
              flush=True)


def gate_stages(setups, kget=None):
    """دروازهٔ روند روی مراحل منتشرشونده — دستور حمید، ۲۰ اوت.

    ریشه: داشبورد latest.json را می‌خواند و روی ARMED هم عمل می‌کند؛ یک
    شورت ARMEDِ ARB در بازار صعودی همین‌طور اجرا شد. از این پس هر ستاپ
    SIGNAL/ARMED/PULLBACK_1 قبل از انتشار از همان دروازهٔ روند گلوگاه
    ارسال رد می‌شود: هر دو تایم بالا خلاف یا تأیید ناقص خلاف روند یا
    دادهٔ روند ناموجود → تنزل به WATCH با دلیل (قانون ۱ و ۲).
    خروجی: تعداد تنزل‌یافته‌ها."""
    from hamid import trend_gate
    if kget is None:
        import sources as _src

        def kget(sym, tf, n):
            return [{"t": k[0], "o": float(k[1]), "h": float(k[2]),
                     "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                    for k in _src.klines(sym, tf, n)]
    cache = {}

    def cached(sym, tf, n):
        if (sym, tf) not in cache:
            cache[(sym, tf)] = kget(sym, tf, n)
        return cache[(sym, tf)]

    demoted = 0
    # تفکیک جهت (۶ سپتامبر): بدون این، «۶۴ تنزل» نمی‌گوید چند شورت
    # کشته شد و چند لانگ — و همان عدد است که سؤال حمید را جواب می‌دهد.
    from collections import Counter as _C
    dmt_dirs = _C()
    _sv = {"n": 0, "open": _stage_veto_open_keys()}
    for s in setups:
        if s.get("stage") not in ("SIGNAL", "ARMED", "PULLBACK_1"):
            continue
        try:
            a = trend_gate.assess(s["sym"], s["dir"], cached, evidence=s)
        except Exception as e:                       # noqa: BLE001
            a = {"ok": False, "t4": None, "t1": None, "mode": "no-data",
                 "reason": f"دروازهٔ روند اجرا نشد ({type(e).__name__}) — "
                           "دادهٔ ناقص = انتشار ممنوع (قانون ۱)"}
        s["trend4"], s["trend1"] = a.get("t4"), a.get("t1")
        s["trend_mode"] = a.get("mode")
        if not a["ok"]:
            was = s.get("stage")
            s["stage"] = "WATCH"
            s["skip"] = a["reason"]
            demoted += 1
            dmt_dirs[s.get('dir') or '?'] += 1
            _stage_veto_ledger(s, a, was, _sv)
            continue
        # نقشهٔ نقدینگی اجباری (دستور حمید، ۲۳ اوت: «نقشهٔ نقدینگی ارزها
        # حتماً بررسی بشه»). از کندل‌هایی که همین ستاپ از قبل دارد ساخته
        # می‌شود — صفر فچ اضافه، صفر تأخیر. نبودِ نقشه = دادهٔ ناقص در
        # فیلدِ حالا-اجباری = انتشار ممنوع (قانون ۱)، همان الگوی دروازهٔ
        # روند بالا.
        try:
            from hamid import liqmap
            lm = liqmap.build(s.get("candles") or [])
        except Exception:                            # noqa: BLE001
            lm = None
        if not lm:
            s["stage"] = "WATCH"
            s["skip"] = "نقشهٔ نقدینگی ساخته نشد — بررسی نقدینگی اجباری است"
            demoted += 1
            dmt_dirs[s.get('dir') or '?'] += 1
            continue
        s["liq_map"] = {"magnet": lm["magnet"], "above": lm["above"][:2],
                        "below": lm["below"][:2]}
        ln = liqmap.note(lm, s.get("dir"))
        if ln:
            s["liqmap_note"] = ln
    return demoted, dict(dmt_dirs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=100)
    ap.add_argument("--tf", default="5m,15m")
    ap.add_argument("--cores", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--rotate", type=int, default=0,
                    help="میدانِ کامل (مثلاً ۲۰۰) — هر اجرا برشی از آن، "
                         "با هستهٔ ثابت. صفر = رفتار قدیمی")
    ap.add_argument("--core", type=int, default=30,
                    help="چند نمادِ پرحجم همیشه اسکن شوند (بسترِ اجباری)")
    ap.add_argument("--telegram", action="store_true",
                    help="deliver new signals as charts (needs TELEGRAM_BOT_TOKEN/CHAT_ID)")
    args = ap.parse_args()
    tfs = [t.strip() for t in args.tf.split(",") if t.strip()]

    t0 = time.time()
    if args.rotate and args.rotate > args.symbols:
        syms = rotating_field(args.symbols, universe=args.rotate,
                              core=args.core)
        print(f"scanning {len(syms)} pairs — {args.core} core + "
              f"{len(syms) - args.core} rotating out of the top {args.rotate} "
              f"× {len(tfs)} timeframes", flush=True)
    else:
        syms = top_by_48h(args.symbols)
        print(f"scanning the {len(syms)} most-traded pairs of the last 48h "
              f"× {len(tfs)} timeframes", flush=True)
    # دفترِ پوششِ غلتان — با چرخش، «پهنای دید» دیگر عددِ یک اجرا نیست.
    # هر اجرا ۶۰ نماد می‌بیند ولی برشِ متفاوتی؛ چیزی که واقعاً اهمیت
    # دارد این است که در یک پنجرهٔ معنادار چند نمادِ **یکتا** دیده شده.
    # بدون این دفتر، متر E01 هر بار ۶۰ می‌دید و چرخش را نمی‌فهمید.
    try:
        _cov_p = OUT / "scan-coverage.json"          # سایه دفتر پوشش خودش را دارد
        _now_ms = int(time.time() * 1000)
        try:
            _cov = json.loads(_cov_p.read_text(encoding="utf-8"))
        except Exception:                                # noqa: BLE001
            _cov = {}
        _seen = {k: v for k, v in (_cov.get("seen") or {}).items()
                 if isinstance(v, int) and _now_ms - v <= 3 * 3600_000}
        for _s in syms:
            _seen[_s] = _now_ms
        _cov_p.parent.mkdir(parents=True, exist_ok=True)
        _cov_p.write_text(json.dumps(
            {"generated": _now_ms, "window_h": 3, "seen": _seen,
             "unique_1h": sum(1 for v in _seen.values()
                              if _now_ms - v <= 3600_000),
             "unique_3h": len(_seen), "last_run": len(syms),
             "field": args.rotate or len(syms)},
            ensure_ascii=False), encoding="utf-8")
    except Exception as _e:                              # noqa: BLE001
        print(f"  دفتر پوشش نوشته نشد: {type(_e).__name__}", flush=True)

    pairs = [(s, tf) for tf in tfs for s in syms]

    jobs, failed = [], 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(klines_now, s, tf): (s, tf) for s, tf in pairs}
        for f, (s, tf) in futs.items():
            try:
                cd = f.result()
                if len(cd) >= 360:
                    jobs.append({"sym": s, "tf": tf, "candles": cd})
            except Exception:                        # noqa: BLE001 - one bad series is not fatal
                failed += 1
    print(f"  {len(jobs)} series fetched, {failed} failed", flush=True)
    if not jobs:
        sys.exit("no candles — every venue refused, not just Binance")

    tmp = HERE / ".scan-tmp"
    tmp.mkdir(exist_ok=True)
    procs = []
    for i in range(args.cores):
        shard = jobs[i::args.cores]
        if not shard:
            continue
        p = tmp / f"scan-{i}.json"
        p.write_text(json.dumps(shard))
        procs.append(subprocess.Popen(["node", str(HERE / "scan_worker.js"), str(p)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    setups = []
    for p in procs:
        so, se = p.communicate()
        if p.returncode != 0:
            sys.exit(f"scan worker failed: {se.decode()[:600]}")
        setups += json.loads(so.decode() or "[]")

    rules = confirmed_rules()
    applied = apply_learned_rules(setups, jobs, rules)
    print(f"confirmed backtest rules applied to {applied} setups", flush=True)

    pref, pref_note = strategy_priority()
    if pref:
        print(f"ترجیح استراتژی فعال: {pref} تا {pref_note.get('until_text')} "
              f"— فقط ترتیب، بدون بستن هیچ استراتژی", flush=True)
    setups.sort(key=lambda s: (STAGE_RANK.get(s["stage"], 0), TF_RANK.get(s["tf"], 0),
                               1 if (pref and s.get("strategy") == pref) else 0,
                               (s.get("learned") or {}).get("boost", 0.0),
                               s["conf"] or 0, s["ev"] or 0), reverse=True)

    # ── the learning room is asked before anything is called a signal ─────────
    # Storing experience is not learning; using it is. Every setup is looked up
    # against what this coin, this strategy and this direction have actually done
    # before, and against setups of the same coarse shape. Where the record is
    # clearly bad on a real sample the setup is held back rather than sent — and
    # where the record is thin it says so and changes nothing, because a verdict
    # built on four trades is not evidence.
    idx = brain.build_index()
    consulted = held = 0
    for s in setups:
        shape = brain.shape_key({
            "strategy": s.get("strategy"), "dir": s.get("dir"), "tf": s.get("tf"),
            "rr": s.get("rr"), "adx": s.get("adx"),
            "dom_dir": (ctx_dir(s)),
        })
        rec = brain.recall(sym=s["sym"], strategy=s.get("strategy"),
                           direction=s.get("dir"), shape=shape, idx=idx)
        best = rec.get("symbol") or rec.get("shape")
        s["learning"] = {
            "verdict": rec["verdict"],
            "n": best["n"] if best else 0,
            "hit": best["hit"] if best else None,
            "ev": best["ev"] if best else None,
        }
        consulted += 1
        if s["stage"] == "SIGNAL" and rec["verdict"] == "bad":
            s["stage"] = "ARMED"
            s["skip"] = (f"اتاق یادگیری مخالف است — {best['n']} مورد مشابه، "
                         f"برد {best['hit']}٪، انتظار {best['ev']:+.2f}R")
            held += 1
    print(f"learning room consulted on {consulted} setups, held back {held}", flush=True)

    # عکسِ جهت **پیش از** دروازه (۶ سپتامبر). باید این‌جا گرفته شود، چون
    # `gate_stages` خودِ `stage` را عوض می‌کند و بعدش دیگر بازیابی‌پذیر
    # نیست — تا امروز همین باعث شده بود سؤال «موتور شورت نمی‌سازد یا
    # دروازه می‌کشدش؟» اصلاً جواب نداشته باشد.
    from collections import Counter as _PC
    _pre_gate = _PC((s.get("stage"), s.get("dir") or "?") for s in setups)

    # دروازهٔ روند روی هرچه منتشر می‌شود، نه فقط سیگنال (دستور ۲۰ اوت)
    demoted, _dmt_dirs = gate_stages(setups)
    print(f"trend gate demoted {demoted} published-stage setups", flush=True)

    # نمونه‌گیر شورت (دستور حمید ۳۰ اوت: «اون ۱۳۰ و ۱۵۰ شورت رو تو
    # پیپرمود بگیر») — فقط دفترِ آزمایش می‌نویسد؛ به stage هیچ ستاپی دست
    # نمی‌زند، پس چیزی وارد مسیر ارسال/پنل نمی‌شود. بودجه که پر شد، خودش
    # می‌ایستد. جزئیات و مرزها: hamid/short_sampler.py.
    try:
        from hamid import short_sampler
        _ss = short_sampler.sample(setups)
        print(f"short sampler: opened={_ss.get('opened', 0)} "
              f"left={_ss.get('left')} "
              + (_ss.get("why") or ""), flush=True)
    except Exception as _e:                          # noqa: BLE001
        print(f"short sampler failed: {type(_e).__name__} — "
              "نمونه‌گیری اختیاری است، اسکن ادامه دارد", flush=True)

    counts = {k: sum(1 for s in setups if s["stage"] == k) for k in STAGE_RANK}
    signals = [s for s in setups if s["stage"] == "SIGNAL"]

    # Each strategy is counted on its own. Blurring them together would hide the
    # thing worth knowing, which is whether one of them is carrying the other.
    per_strategy = {
        k: {"name": v,
            "signals": sum(1 for s in signals if s.get("strategy") == k),
            "armed": sum(1 for s in setups if s.get("strategy") == k and s["stage"] == "ARMED"),
            "watching": sum(1 for s in setups if s.get("strategy") == k and s["stage"] == "WATCH")}
        for k, v in STRATS.items()}

    # A setup that has not fired yet is worth an alarm at the price that would
    # make it fire, so it gets looked at the moment price arrives rather than
    # whenever the next scan happens to run.
    alarms = [{"sym": s["sym"], "tf": s["tf"], "dir": s["dir"],
               "strategy": s.get("strategy"), "strategyName": s.get("strategyName"),
               "price": s["entry"], "now": s.get("price"),
               "distancePct": (abs((s.get("price") or s["entry"]) - s["entry"]) / s["entry"] * 100)
               if s["entry"] else None,
               "why": s.get("waitReason") or s.get("skip") or "منتظر تأییدیه",
               "stage": s["stage"]}
              for s in setups if s["stage"] in ("ARMED", "PULLBACK_1")]
    alarms.sort(key=lambda a: a["distancePct"] if a["distancePct"] is not None else 999)

    # The events room: what was true at this moment, written down now so the
    # learning room can ask later which conditions went with which outcome.
    ctx = usdt_dominance()
    brain.event("scan", symbols=len(syms), series=len(jobs),
                counts=counts, per_strategy=per_strategy, context=ctx,
                signals=[{"sym": s["sym"], "tf": s["tf"], "dir": s["dir"],
                          "strategy": s.get("strategy"), "entry": s["entry"],
                          "sl": s["sl"], "tp1": s["tp1"], "rr": s["rr"]}
                         for s in signals])
    brain.room_save("scan", {"lastScan": int(time.time() * 1000),
                             "counts": counts, "per_strategy": per_strategy})
    # ادغام، نه بازنویسی. این خط قبلاً کل فایل رادار را عوض می‌کرد و هر
    # نیم‌ساعت آلارم‌های پامپ‌رادار و آلارم‌های فعال‌شدهٔ چرخه را می‌شست —
    # مسیر آلارم→بازبینی→سیگنال بی‌صدا خالی می‌ماند (یافتهٔ بازبینی معماری).
    _old = brain.room_load("radar", {}) or {}
    _keep = [a for a in (_old.get("alarms") or [])
             if a.get("strategy") not in ("ibs", "smc")]
    brain.room_save("radar", {**_old, "alarms": (alarms + _keep)[:80]})
    for s in signals:
        brain.room_log("watch", f"{s['sym']} {s['tf']} {s['dir']} — {s.get('strategyName','')}", "sig")

    report = {
        "generated": int(time.time() * 1000),
        "generatedText": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "source": _source_label(),
        "symbols": len(syms), "series": len(jobs), "timeframes": tfs,
        "counts": counts,
        "per_strategy": per_strategy,
        "strategy_priority": pref_note,   # ترجیح فعال — دیده شود، نه بی‌صدا
        "alarms": alarms[:40],
        "learning": {
            "experiences": len(brain.read(brain.LEARNING / "experiences.jsonl")),
            "heldBack": held,
            "note": "قبل از هر سیگنال، سابقهٔ همان ارز با همان استراتژی و همان جهت "
                    "پرسیده می‌شود. اگر سابقه بد و نمونه کافی باشد، سیگنال نگه داشته "
                    "می‌شود. اگر سابقه کم باشد چیزی تغییر نمی‌کند.",
        },
        "context": ctx,
        "note": "۵ دقیقه بالاتر از ۱۵ دقیقه رتبه می‌گیرد، چون بک‌تست روی کندل واقعی "
                "روی ۵ دقیقه لبه اندازه گرفت (+۰.۱۴۱R با بازهٔ کاملاً بالای صفر) و روی "
                "۱۵ دقیقه نه (+۰.۰۰۵R، بازه صفر را در بر می‌گیرد). این فقط رتبه‌بندی است — "
                "هیچ ارزی به‌خاطر تایم‌فریمش حذف نمی‌شود.",
        "signals": signals,
        "watch": [s for s in setups if s["stage"] != "SIGNAL"][:60],
        # یادگیریِ تأییدشده — فقط همین‌ها اجازهٔ عمل دارند؛ پنل عین همین را نشان می‌دهد
        "learned_rules": [{"strategy": st, "condition": r["condition"], "n": r["n"],
                           "delta": r["delta"], "ci": r["ci"], "verdict": r["verdict"]}
                          for st, rs in rules.items() for r in rs],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    # Telegram gets the candles so it can draw the setup; the published file does
    # not, or 236 setups × 120 bars would make it megabytes for no reader.
    if args.telegram:
        from telegram import send_signals

        def draw(s, path):
            if not s.get("candles"):
                return None
            from chart import render
            return render(s["candles"], s, path)

        _sent_n = send_signals(signals, draw) or 0
    else:
        _sent_n = 0

    # قیف سلامت (قانون ۰۷) — پاسخ «چرا سیگنال نیامد» با شواهد، نه حدس
    _fn = funnel_report(setups, sent=_sent_n, demoted=demoted, held=held,
                        series=len(jobs), failed=failed,
                        pre_gate=_pre_gate, demoted_dirs=_dmt_dirs)
    (OUT / "funnel.json").write_text(json.dumps(_fn, ensure_ascii=False, indent=1))
    print(f"funnel: {_fn['classification']} · {_fn['setups']} setups · "
          f"{_fn['telegram_sent']} sent", flush=True)

    def strip(s):
        return {k: v for k, v in s.items() if k != "candles"}

    report["signals"] = [strip(s) for s in report["signals"]]
    report["watch"] = [strip(s) for s in report["watch"]]
    (OUT / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

    print(f"\n{counts['SIGNAL']} signals · {counts['ARMED']} armed · "
          f"{counts['PULLBACK_1']} first pullback · {counts['WATCH']} watching")
    for k, v in per_strategy.items():
        print(f"  {v['name']:<22} {v['signals']:>3} signal · {v['armed']:>3} armed · {v['watching']:>4} watching")
    if alarms:
        print(f"\nalarms set on {len(alarms)} setups waiting for confirmation — nearest:")
        for a in alarms[:6]:
            d = f"{a['distancePct']:.2f}%" if a["distancePct"] is not None else "—"
            print(f"  {a['sym']:<12} {a['tf']:<4} {a['dir']:<5} at {a['price']:<12.6g} ({d} away) — {a['why']}")
    for s in signals[:20]:
        room = f"{s['room']['r']}×" if s.get("room") else "—"
        # عیب‌یابی ۱۴ اوت: ev=None این print را می‌کشت و کل main هر دور
        # با TypeError تمام می‌شد — گزارش لاگ ناقص و کد خروج غلط. هیچ
        # فیلدی اینجا حق کشتن اسکن را ندارد؛ None صادقانه «—» می‌شود.
        ev = f"{s['ev']:.2f}R" if s.get("ev") is not None else "—"
        conf = f"{s['conf']}%" if s.get("conf") is not None else "—"
        print(f"  🚨 {s['sym']:<12} {s['tf']:<4} {s['dir']:<5} "
              f"entry {s['entry']:<12.6g} sl {s['sl']:<12.6g} tp1 {s['tp1']:<12.6g} "
              f"rr {s.get('rr', '—')}  conf {conf}  ev {ev}  room {room}")
    if not signals:
        print("  no setup passed every gate this pass — that is a normal result, not a fault")
    print(f"\nwritten to signals/latest.json in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
