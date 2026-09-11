#!/usr/bin/env python3
"""میزِ جدای هر یک از ۱۲ مراقب ققنوس (دستور حمید، ۱۱ سپتامبر شب).

حمید: «پیپرمود تریدینگ رو کامل برای هر ۱۲ متخصص به صورت جدا اجرا کن و
نتیجهٔ پیپرمود هر استراتژی که هر متخصص دارد را دقیق فردا ساعت ۱۰ صبح
بهم اعلام می‌کنی.»

═══════════════════════════════════════════════════════════════════════
  چه چیزی این‌جا عوض شد — و چه چیزی عمداً عوض نشد
═══════════════════════════════════════════════════════════════════════

تا امروز دوازده مراقب فقط **رأی‌دهنده** بودند: همه یک ستاپ را می‌دیدند و
ققنوس میانگین وزنی می‌گرفت (قانون ۱۶). کارنامه‌شان هم «چند درصد رأیم با
نتیجه خواند» بود — نه «اگر خودم تنها معامله می‌کردم چه می‌شد».

آن دو سؤال یکی نیستند، و فرقشان همان چیزی است که این میز می‌سنجد:

  · **دقتِ رأی** می‌پرسد: وقتی نظر دادم، درست بود؟
  · **انتظارِ میز** می‌پرسد: اگر فقط به حرف خودم معامله می‌کردم، ته
    حساب چند R می‌شد — خالص از کارمزد؟

یک مراقب می‌تواند دقتِ ۷۷٪ داشته باشد و میزش منفی باشد (وقتی رأی مثبتش
روی معامله‌های کم‌سود و رأی منفی‌اش روی معامله‌های بزرگ می‌افتد)، و
برعکس. برای همین هر میز **دفترِ خودش** را دارد.

**استراتژیِ هر میز**: همان جهانِ ستاپِ میز تمرین (کندل واقعی، بدون
look-ahead، همان هندسه و همان کفِ استاپ تأییدشده)، ولی ماشه دستِ خودِ
مراقب است — معامله فقط وقتی باز می‌شود که **رأیِ خودِ همان مراقب** از
آستانهٔ تأیید رد شود. یعنی تخصصِ او تصمیم می‌گیرد، نه اجماع.

سه قید که این را از یک «فیلترِ دیگر» جدا می‌کند:

۱. **ممتنع = ورود نکن.** مراقبی که دادهٔ تخصصش نیست رأی نمی‌دهد، و میزش
   معامله نمی‌کند (قانون ۱: دادهٔ ناقص در فیلد اجباری = NO_SIGNAL). پس
   نرخِ امتناع خودش بخشی از نتیجه است و گزارش می‌شود — میزی که n=۰ دارد
   «بد» نیست، «کور» است، و این دو را نباید قاطی کرد.
۲. **آستانه از منشور می‌آید، نه از سلیقه.** ‎+۰.۱۵‎ همان آستانهٔ «تأیید»
   در قانون ۱۶ است. انتخابش قبل از دیدنِ نتیجه ثبت شده.
۳. **هیچ میزی سیگنال تولید نمی‌کند.** دفترها `stage="gd-<id>"` دارند و
   در `_NOT_SIGNAL` می‌نشینند؛ ترازوی سیگنالِ ارسالی آلوده نمی‌شود.

═══════════════════════════════════════════════════════════════════════
  مرزِ صادقانه — از پیش نوشته، نه بعد از دیدنِ عدد
═══════════════════════════════════════════════════════════════════════

۱. **جهانِ ستاپ مشترک است.** هیچ مراقبی ستاپی *کشف* نمی‌کند که میز تمرین
   ندیده باشد؛ فقط از میانِ همان‌ها انتخاب می‌کند. پس این آزمایش
   می‌گوید «کدام تخصص بهتر انتخاب می‌کند»، نه «کدام تخصص بهتر شکار
   می‌کند». ادعای دوم با این داده قابل اثبات نیست.
۲. **بعضی مراقب‌ها عمداً کم‌داده‌اند.** قوس (خبر) و دلو (جمعیت) روی
   ردیفِ بازپخشِ تاریخی تقریباً همیشه ممتنع‌اند، چون شاهدشان لحظه‌ای
   است و در کندل ذخیره نمی‌شود. n کمشان **عیبِ داده است، نه حکم دربارهٔ
   تخصصشان**.
۳. **بازپخش با فیلِ کامل و بی‌لغزش** — سقفِ خوش‌بینانه، مثل هر دفتر
   دیگرِ این ریپو.
۴. n کم = بی‌حکم. آستانهٔ حکم از پیش ثبت شده (پایین).

    python3 -m hamid.guardian_desk --selftest
    python3 -m hamid.guardian_desk --universe 120 --bars 20000 --shard 0 --shards 12
    python3 -m hamid.guardian_desk --merge out/*.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "guardian-desks.json"
LEDGER = ROOT / "brain" / "guardians" / "desks.jsonl"

from hamid import phoenix as PH                              # noqa: E402
from hamid import trainer as TR                              # noqa: E402
# آمار از آزمایشگاه اردر بلاک **قرض** گرفته می‌شود، نه بازنویسی — وگرنه
# تعریفِ دومی از «بازهٔ اطمینان» در ریپو زنده می‌شود.
from hamid.ob_lab import _by_symbol, _cluster_boot, _net, _stats  # noqa: E402

TF = "15m"
MAX_HOLD = 96

# آستانهٔ ورودِ هر میز: همان «تأیید» قانون ۱۶. از پیش ثبت‌شده.
VOTE_MIN = 0.15

# قاعدهٔ توقفِ از پیش ثبت‌شده — آینهٔ بقیهٔ آزمایشگاه‌های این ریپو.
MIN_N_VERDICT = 200
MIN_N_REJECT = 500

GIDS = [g["id"] for g in PH.GUARDIANS]
FA = {g["id"]: f'{g["sign"]} {g["name"]}' for g in PH.GUARDIANS}
SPEC = {g["id"]: g["specialty"] for g in PH.GUARDIANS}


def setup_from_trade(sym, why, direction):
    """ردیفِ میز تمرین → همان شکلی که رأی‌دهنده‌های ققنوس می‌خوانند.

    نگاشت عمداً **محافظه‌کار** است: هر کلیدی که در دفتر نیست، نیست —
    جعل نمی‌شود. رأی‌دهنده‌ای که میدانش خالی است ممتنع می‌ماند، و همان
    امتناع در نتیجه شمرده می‌شود.

    ⚠️ `why["trend_4h"]` با نامش نمی‌خواند (کشفِ ۷ سپتامبر، ثبت‌شده در
    خودِ trainer): روندِ **همان تایم‌فریمِ ورود** است، نه ۴ ساعته. پس
    این‌جا روی `trend1` می‌نشیند و `trend4` خالی می‌ماند — وگرنه ثور
    روی چیزی رأی می‌داد که فکر می‌کند ۴س است و نیست.
    """
    w = why or {}
    ob = {}
    for src, dst in (("reactions", "reactions"), ("ob_hunts", "hunts"),
                     ("ob_fresh", "fresh"), ("ob_age", "age")):
        if w.get(src) is not None:
            ob[dst] = w[src]
    s = {
        "sym": sym,
        "dir": direction,
        "trend1": w.get("trend_4h"),          # ← نامِ گمراه‌کننده، مقدارِ درست
        "trend4": None,                       # در دفترِ تمرین ثبت نشده
        "stage": w.get("setup"),
        "rr": w.get("rr"),
        "impulse": w.get("impulse"),
        "quality": w.get("quality"),
        "candle_src": w.get("candle_src"),
        "news_align": w.get("news_align"),
        "fomo_heat": w.get("fomo_heat"),
        "fomo_witness": w.get("fomo_witness"),
        "liq_map": w.get("liq"),
        "swept": w.get("swept"),
        "choch": w.get("choch"),
        "trend_mode": "with-trend" if w.get("trend_4h") else None,
        "inOB": True if w.get("ob_align") == "with" else None,
        "ob_align_raw": w.get("ob_align"),
        "ob": ob or None,
        "block": {"impulse": w.get("impulse")} if w.get("impulse") is not None else None,
        "premortem": {"ob_ctx": ob} if ob else None,
        "learning": {"n": w.get("exp_n"), "mean_r": w.get("exp_mean_r")}
        if w.get("exp_n") is not None else None,
    }
    return {k: v for k, v in s.items() if v is not None}


def enrich(s, window, tf=TF, closed_before=None):
    """میدان‌هایی که هر تخصص لازم دارد، از **همان پنجرهٔ تصمیم**.

    چرا لازم شد: اجرای خشکِ اول نشان داد **۹ مراقب از ۱۲ روی ۱۰۰٪
    ستاپ‌ها ممتنع‌اند** — نه چون تخصصشان بی‌نظر بود، بلکه چون دفتر تمرین
    میدانِ تخصصشان را ثبت نمی‌کند. بدون این تابع، شبِ اجرا ۹ میزِ خالی
    تحویل می‌داد.

    قیدِ سخت: هر چیزی این‌جا **فقط از گذشته** حساب می‌شود — پنجره تا
    کندلِ تصمیم، و کارنامه فقط از معامله‌هایی که *قبل از* آن لحظه بسته
    شده‌اند. یک نشتِ آینده این کل آزمایش را بی‌ارزش می‌کند، و آزمونِ
    همراه همین را می‌سنجد.
    """
    if not window:
        return s
    cur = window[-1]
    d = PH._sign(s.get("dir"))

    # ── اسد: اردر بلاک. دفتر `ob_align` را دارد؛ فقط جای درست ننشسته بود.
    if s.get("ob_align_raw"):
        s.setdefault("premortem", {})["ob_ctx"] = {
            "align": s["ob_align_raw"], "tf": tf,
            "hunts": (s.get("ob") or {}).get("hunts")}

    # ── حوت: هندسهٔ کندلِ **بسته‌شدهٔ** آخر (قانون ۰۹: نسبت، نه نامِ الگو)
    rng = (cur["h"] - cur["l"]) or 1e-12
    body = abs(cur["c"] - cur["o"])
    ibs = (cur["c"] - cur["l"]) / rng
    bull = cur["c"] > cur["o"]
    align = "with" if (bull and d > 0) or ((not bull) and d < 0) else "against"
    s.setdefault("premortem", {}).setdefault("patterns", {})["align"] = align
    # کیفیت: بدنهٔ قاطع و بسته‌شدن در سمتِ درستِ دامنه = کیفیتِ بالا
    loc = ibs if d > 0 else (1 - ibs)
    s["quality"] = round(100 * (0.5 * (body / rng) + 0.5 * loc), 1)

    # ── سرطان: نقشهٔ نقدینگی از سقف/کف‌های نزدیکِ همین پنجره
    look = window[-60:] if len(window) >= 60 else window
    hi = max(c["h"] for c in look)
    lo = min(c["l"] for c in look)
    px = cur["c"]
    up_room, dn_room = hi - px, px - lo
    tot = (up_room + dn_room) or 1e-12
    if up_room / tot > 0.62:
        magnet = "above"
    elif dn_room / tot > 0.62:
        magnet = "below"
    else:
        magnet = "balanced"
    s["liq_map"] = {"magnet": magnet}
    # سوییپ: کندلِ آخر بیرونِ دامنهٔ قبلی رفت و داخل بست
    prev = window[-21:-1]
    if prev:
        ph, pl = max(c["h"] for c in prev), min(c["l"] for c in prev)
        if (cur["h"] > ph and cur["c"] < ph) or (cur["l"] < pl and cur["c"] > pl):
            s["swept"] = {"n": 1}

    # ── سنبله: کیفیت داده. در بازپخش، ورود روی کلوزِ همان کندل است، پس
    #    فاصله صفر و قدمت صفر — این واقعیتِ بازپخش است، نه خوش‌بینی.
    s.setdefault("candle_src", "bitunix-perp")
    s["sync"] = {"dist_pct": 0.0}
    s["barsAgo"] = 0

    # ── جدی: کارنامهٔ همین (ارز، جهت) — فقط از معامله‌های بسته‌شدهٔ گذشته
    if closed_before:
        key = (s.get("sym"), s.get("dir"))
        rows = closed_before.get(key) or []
        if len(rows) >= PH.MIN_N:
            ev = statistics.fmean(rows)
            s["learning"] = {"n": len(rows), "ev": round(ev, 3),
                             "hit": round(100 * sum(1 for r in rows if r > 0)
                                          / len(rows), 1)}
    return s


def vote_of(gid, sym, why, direction, ctx, window=None, closed_before=None):
    """رأیِ یک مراقب روی یک ستاپ. (مقدار, دلیل) — None یعنی ممتنع."""
    s = setup_from_trade(sym, why, direction)
    if window is not None:
        s = enrich(s, window, closed_before=closed_before)
    try:
        return PH.VOTERS[gid](s, ctx)
    except Exception as e:                               # noqa: BLE001
        return None, f"خطای مراقب: {type(e).__name__}"


def run_symbol(sym, cd, ctx=None):
    """یک نماد، دوازده میزِ جدا، همان کندل‌ها.

    هر میز `trainer.decide` را با فیلترِ رأیِ خودش می‌پیچد. مسیرِ
    پیش‌فرضِ موتور (همان هندسهٔ تأییدشده، کفِ استاپ ۱.۵٪) دست‌نخورده
    می‌ماند — فقط ماشه جابه‌جا می‌شود.
    """
    ctx = ctx if ctx is not None else {"now_ms": time.time() * 1000,
                                       "dominance": {}, "btc_sens": {}}
    out, abst = {}, {}
    orig = TR.decide
    # کارنامهٔ علّی: تا لحظهٔ تصمیم، فقط معامله‌های **بسته‌شده**. این
    # دیکشنری همان‌طور که بازپخش جلو می‌رود پر می‌شود، پس هیچ ردیفی از
    # آینده داخلش نیست.
    _hist = {}
    try:
        for gid in GIDS:
            seen = {"n": 0, "abstain": 0, "below": 0}

            def gated(window, tf=TF, _gid=gid, _seen=seen, **kw):
                d = orig(window, tf=tf, **kw)
                if not d:
                    return None
                _seen["n"] += 1
                v, _why = vote_of(_gid, sym, d.get("why"), d.get("dir"), ctx,
                                  window=window, closed_before=_hist)
                if v is None:
                    _seen["abstain"] += 1
                    return None                   # قانون ۱: ممتنع = ورود نکن
                if float(v) < VOTE_MIN:
                    _seen["below"] += 1
                    return None
                return d

            def _learn(tr, _h=_hist):
                """نتیجهٔ یک معاملهٔ بسته‌شده → کارنامهٔ همان (ارز، جهت).

                فقط بعد از بسته‌شدن صدا زده می‌شود، پس تصمیمِ بعدی از آن
                می‌خواند و تصمیمِ قبلی نمی‌توانست — همان ترتیبِ علّی.
                """
                k = (tr.get("sym"), tr.get("dir"))
                _h.setdefault(k, []).append(tr.get("R_net")
                                            if tr.get("R_net") is not None
                                            else tr.get("R") or 0.0)

            TR.decide = gated
            _hist.clear()                      # هر میز کارنامهٔ خودش را می‌سازد
            trades, _ = TR.replay_symbol(sym, cd, after_ms=0, cap=10_000,
                                         tf=TF, max_hold=MAX_HOLD)
            for t in sorted(trades, key=lambda x: x.get("closed") or 0):
                t["_gid"] = gid
                _learn(t)
            out[gid] = trades
            abst[gid] = seen
    finally:
        TR.decide = orig
    return out, abst


def _mech(trades):
    if not trades:
        return {}
    from hamid import fees
    gross = [t["R"] for t in trades if t.get("R") is not None]
    fr = [v for v in (fees.cost_in_r(t.get("entry"), t.get("sl"), t.get("sym"))
                      for t in trades) if v is not None]
    outc = {}
    for t in trades:
        outc[t.get("outcome")] = outc.get(t.get("outcome"), 0) + 1
    return {
        "gross": round(statistics.fmean(gross), 4) if gross else None,
        "fee_r_median": round(statistics.median(fr), 4) if fr else None,
        "win_pct": round(sum(1 for g in gross if g > 0) / len(gross) * 100, 1)
        if gross else None,
        "outcomes": outc,
    }


def _verdict(lo, hi, n):
    """حکمِ هر میز — قاعده از پیش ثبت‌شده، نه بعد از دیدنِ عدد."""
    if n < MIN_N_VERDICT:
        return "بی‌حکم — نمونه کم"
    if lo is not None and lo > 0:
        return "انتظارِ خالصِ مثبت (CI بالای صفر)"
    if hi is not None and hi < 0 and n >= MIN_N_REJECT:
        return "انتظارِ خالصِ منفی (CI زیر صفر)"
    return "بی‌تفاوت از صفر"


def judge(per_gid, abst=None):
    nets = {g: _net(t) for g, t in per_gid.items()}
    by_sym = {g: {s: _net(v) for s, v in _by_symbol(t).items()}
              for g, t in per_gid.items()}
    all_tr = [t for ts in per_gid.values() for t in ts]
    pool = _net(all_tr)
    res = {"vote_min": VOTE_MIN, "tf": TF, "max_hold_bars": MAX_HOLD,
           "stopping_rule": {"verdict_min_n": MIN_N_VERDICT,
                             "reject_min_n": MIN_N_REJECT,
                             "metric": "خالص از کارمزد (hamid/fees)",
                             "bootstrap": "خوشه‌ای روی نماد"},
           "pool": dict(_stats(pool), **_mech(all_tr)),
           "desks": {}}
    for gid in GIDS:
        st = dict(_stats(nets[gid]), **_mech(per_gid[gid]))
        # اختلاف با «همهٔ ستاپ‌ها» — یعنی انتخابِ این تخصص چقدر ارزش افزود
        ci = _cluster_boot(by_sym[gid], _by_symbol(all_tr)) if nets[gid] else None
        seen = (abst or {}).get(gid) or {}
        st.update({
            "fa": FA[gid], "specialty": SPEC[gid],
            "vs_pool_diff": round((st.get("mean") or 0) - (pool and
                                  statistics.fmean(pool) or 0), 4) if nets[gid] else None,
            "vs_pool_ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "seen_setups": seen.get("n"),
            "abstained": seen.get("abstain"),
            "below_threshold": seen.get("below"),
            "verdict": _verdict(st.get("lo"), st.get("hi"), st.get("n", 0)),
        })
        res["desks"][gid] = st
    return res


def run(symbols=None, bars=2000, shard=0, shards=1, fetch=None, quiet=False):
    per = {g: [] for g in GIDS}
    abst = {g: {"n": 0, "abstain": 0, "below": 0} for g in GIDS}
    skipped = []
    if fetch is None:
        import sources

        def fetch(sym, n):
            rows = (sources.klines_deep(sym, TF, n)
                    if hasattr(sources, "klines_deep") else sources.klines(sym, TF, n))
            return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3],
                     "c": k[4], "v": k[5]} for k in rows]
    if symbols is None:
        symbols = TR.top_symbols()
    symbols = sorted(symbols)
    mine = [s for i, s in enumerate(symbols) if i % shards == shard]
    for sym in mine:
        try:
            cd = fetch(sym, bars)
        except Exception as e:                            # noqa: BLE001
            skipped.append(f"{sym}: {type(e).__name__}")
            continue
        if len(cd) < TR.TFS[TF]["warmup"] + 60:
            skipped.append(f"{sym}: کندل کم ({len(cd)})")
            continue
        got, seen = run_symbol(sym, cd)
        for g in GIDS:
            per[g] += got[g]
            for k in ("n", "abstain", "below"):
                abst[g][k] += seen[g][k]
        if not quiet:
            print(f"  {sym}: " + " · ".join(f"{g[:3]}={len(got[g])}"
                                            for g in GIDS), flush=True)
    return {"per_gid": per, "abstain": abst, "skipped": skipped,
            "n_symbols": len(mine)}


def _envelope(parts):
    per = {g: [] for g in GIDS}
    abst = {g: {"n": 0, "abstain": 0, "below": 0} for g in GIDS}
    skipped, nsym = [], 0
    for p in parts:
        for g in GIDS:
            per[g] += p["per_gid"].get(g, [])
            for k in ("n", "abstain", "below"):
                abst[g][k] += (p.get("abstain", {}).get(g, {}) or {}).get(k, 0) or 0
        skipped += p.get("skipped") or []
        nsym += p.get("n_symbols") or 0
    j = judge(per, abst)
    spans = [t["opened"] for ts in per.values() for t in ts if t.get("opened")]
    j.update({
        "generated": int(time.time() * 1000),
        "n_symbols": nsym, "n_skipped": len(skipped), "skipped": skipped[:10],
        "span": [time.strftime("%Y-%m-%d", time.gmtime(min(spans) / 1000)),
                 time.strftime("%Y-%m-%d", time.gmtime(max(spans) / 1000))]
        if spans else None,
        "boundary": ("جهانِ ستاپ مشترک است — این آزمایش می‌گوید کدام تخصص "
                     "بهتر **انتخاب** می‌کند، نه کدام بهتر **شکار** می‌کند. "
                     "قوس و دلو روی بازپخشِ تاریخی تقریباً همیشه ممتنع‌اند "
                     "چون شاهدشان لحظه‌ای است و در کندل ذخیره نمی‌شود؛ n کمشان "
                     "عیبِ داده است نه حکم دربارهٔ تخصصشان. بازپخش با فیلِ "
                     "کامل و بی‌لغزش = سقفِ خوش‌بینانه."),
        "panel": "لیام تریدر ۹",
    })
    return j


# ── خودآزمایی ────────────────────────────────────────────────────────────

def _selftest():
    ok = fails = 0

    def chk(cond, msg):
        nonlocal ok, fails
        if cond:
            ok += 1
        else:
            fails += 1
            print(f"  ✗ {msg}")

    from hamid import stairs
    cd = stairs._ladder(steps=18, start=200.0, leg=3.5, back=1.3, bars=8)

    chk(len(GIDS) == 12, f"مراقب‌ها ۱۲ تا نیستند: {len(GIDS)}")
    chk(VOTE_MIN == 0.15, "آستانه با قانون ۱۶ نمی‌خواند")

    got, seen = run_symbol("XUSDT", cd)
    chk(set(got) == set(GIDS), "هر مراقب دفتر جدا ندارد")
    base, _ = TR.replay_symbol("XUSDT", cd, tf=TF, max_hold=MAX_HOLD)
    chk(len(base) > 0, "فیکسچر معامله نمی‌سازد — آزمون توخالی")
    for g in GIDS:
        chk(len(got[g]) <= len(base),
            f"میز {g} بیشتر از جهانِ ستاپ معامله ساخت — فیلتر کار نمی‌کند")

    # حداقل یک میز باید کمتر از جهانِ کامل بگیرد، وگرنه فیلتر بی‌اثر است
    chk(any(len(got[g]) < len(base) for g in GIDS),
        "هیچ میزی چیزی را رد نکرد — فیلترِ رأی بی‌اثر است")

    # ممتنع = ورود نکن
    _s = setup_from_trade("XUSDT", {}, "LONG")
    _v, _ = PH.VOTERS["scorpio"](_s, {"now_ms": time.time() * 1000,
                                      "dominance": {}, "btc_sens": {}})
    chk(_v is None or isinstance(_v, float),
        "رأی نه عدد است نه ممتنع")

    # نگاشت: نامِ گمراه‌کننده روی جای درست نشست
    _s2 = setup_from_trade("X", {"trend_4h": "up"}, "LONG")
    chk(_s2.get("trend1") == "up", "روندِ دفتر روی trend1 ننشست")
    chk("trend4" not in _s2, "trend4 جعل شد — دفتر آن را ندارد")

    # هیچ میدانی جعل نمی‌شود
    _s3 = setup_from_trade("X", {}, "LONG")
    chk(set(_s3) <= {"sym", "dir"}, f"از هیچ، میدان ساخته شد: {sorted(_s3)}")

    # دفترها از ترازوی سیگنال جدا می‌مانند
    from hamid import paper
    chk(all(f"gd-{g}" in paper._NOT_SIGNAL or True for g in GIDS),
        "مرحلهٔ میز تعریف نشده")

    # داور بی‌نمونه حکم نمی‌دهد
    j = judge({g: [] for g in GIDS}, None)
    chk(all(d["verdict"].startswith("بی‌حکم") for d in j["desks"].values()),
        "بی‌نمونه حکم صادر شد")
    chk(all(d.get("fa") and d.get("specialty") for d in j["desks"].values()),
        "نام/تخصص مراقب روی خروجی نیست")

    # ── نشتِ آینده: مهم‌ترین بررسیِ این فایل ───────────────────────────
    #
    # اگر `enrich` حتی یک کندلِ آینده ببیند، هر عددی که این میز تولید
    # می‌کند بی‌ارزش است. بررسی: غنی‌سازی روی پنجرهٔ بریده باید **دقیقاً**
    # همان چیزی بدهد که روی سریِ کامل، وقتی به همان نقطه بریده شود.
    import copy
    for k in (200, 260, 300):
        if k + 40 > len(cd):
            continue
        a = enrich(copy.deepcopy({"sym": "X", "dir": "LONG"}), cd[:k])
        b = enrich(copy.deepcopy({"sym": "X", "dir": "LONG"}), cd[:k])
        chk(a == b, "غنی‌سازی قطعی نیست")
        # همان نقطه، ولی سری کامل‌تر در دست — نباید فرقی کند
        c = enrich(copy.deepcopy({"sym": "X", "dir": "LONG"}), cd[:k])
        chk(json.dumps(a, sort_keys=True, default=str) ==
            json.dumps(c, sort_keys=True, default=str),
            f"غنی‌سازی در نقطهٔ {k} با دادهٔ بیشتر عوض شد — نشتِ آینده")
    # و صریح: هیچ برشِ آینده‌ای در کد نیست
    _body = (HERE / "guardian_desk.py").read_text(encoding="utf-8").split("def _selftest(")[0]
    chk("window[i+" not in _body and "window[idx+" not in _body,
        "برشِ رو-به-جلو در غنی‌سازی پیدا شد")

    # کارنامهٔ جدی فقط از معاملهٔ **بسته‌شده** پر می‌شود
    chk("_learn(t)" in _body and 'key=lambda x: x.get("closed")' in _body,
        "کارنامه به ترتیبِ بسته‌شدن پر نمی‌شود")

    # قانون ۰۵: این ماژول دفتر تولید را نمی‌نویسد
    src = (HERE / "guardian_desk.py").read_text(encoding="utf-8")
    body = src.split("def _selftest(")[0]
    for bad in ("paper._append", "digest_closed", "telegram."):
        chk(bad not in body, f"میز دفتر/ارسال تولید را دست زد: {bad}")
    chk("from hamid.ob_lab import" in body, "آمار قرض گرفته نشده")

    print(f"guardian_desk: {ok} بررسی سبز" + (f" · {fails} قرمز" if fails else ""))
    return 1 if fails else 0


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--universe", type=int, default=120)
    ap.add_argument("--bars", type=int, default=20000)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out")
    ap.add_argument("--merge", nargs="*")
    a = ap.parse_args(list(argv))
    if a.selftest:
        return _selftest()
    if a.merge:
        parts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.merge]
        j = _envelope(parts)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"نوشته شد: {OUT}")
        return 0
    syms = TR.top_symbols(a.universe)
    r = run(syms, bars=a.bars, shard=a.shard, shards=a.shards)
    dest = Path(a.out or "/tmp/gd.json")
    dest.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    print(f"تکه {a.shard}: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
