"""آزمایشگاه هندسه — سنجشِ «تارگتِ بزرگ‌تر، استاپِ گشادتر» (دستور حمید، ۹ سپتامبر).

حمید: «بله برو سراغ هندسه.»

═══════════════════════════════════════════════════════════════════════
  چرا هندسه، و چرا **حالا**
═══════════════════════════════════════════════════════════════════════

سهمِ کارمزد از هر معامله برابر است با `کارمزد٪ ÷ استاپ٪`. این یک
اتحادِ حسابی است، نه فرضیه: استاپِ تنگ‌تر یعنی سهمِ بزرگ‌تر برای
کارمزد، مستقل از این‌که ورود چقدر خوب باشد.

سه میزِ این سامانه با همین بیماری خوابیدند و هر سه علتِ یکسان داشتند:

| میز | ناخالص | خالص | حکم |
|---|---|---|---|
| اسکلپ ۱د (قانون ۱۰) | +۰.۰۴۶R | **−۰.۱۶۹R** | REJECT — کارمزد ۰.۲۱۵R |
| میز شوک (۲۴ اوت) | +۰.۰۸۲R، CI بالای صفر | **−۰.۰۳۱R** | خاموش شد |
| موتور شورت (۸ سپتامبر) | +۰.۱۹۷R، CI بالای صفر | **+۰.۱۱۴R، CI شاملِ صفر** | UNDECIDED |

و آزمایشگاه اردر بلاک (۹ سپتامبر) نشان داد **انتخابِ باکس گلوگاه نیست**:
سه بازوی متفاوت، هر سه بی‌اثر (بزرگ‌ترین اختلاف −۰.۰۲۷R با CI شاملِ صفر)
در حالی که نرخِ تغییرِ تصمیم ۱۷.۸–۴۳.۲٪ بود. یعنی آزمون ضعیف نبود؛
اهرم آن‌جا نبود.

**پس این آزمایش سؤالِ بعدی است، نه ایدهٔ تازه.** و جهتش از قبل یک شاهد
دارد: sweep اسکلپ (۲۳ اوت) نشان داد rr ۱.۵→۲.۵→۴.۰ ناخالص را یک‌نواخت
بالا می‌برد (+۰.۱۱۷ → +۰.۱۹۹ → +۰.۲۲۰). ولی آن روی ۱ دقیقه بود و
**خالصش هرگز مثبت نشد**؛ این‌جا روی ۱۵ دقیقه سنجیده می‌شود.

═══════════════════════════════════════════════════════════════════════
  شبکهٔ از پیش ثبت‌شده — ۹ خانه
═══════════════════════════════════════════════════════════════════════

دو محور، هر کدام سه سطح. سطحِ اولِ هر محور **کنترل** است (رفتار امروز):

    rr        ∈ {2.0*, 3.0, 4.0}          تارگت بر حسب R
    min_stop  ∈ {0.15*, 1.0, 1.5}         کفِ فاصلهٔ استاپ (٪)

`*` = مقدار امروز. خانهٔ `rr2.0/stop0.15` همان موتورِ فعلی است و
کنترلِ همهٔ مقایسه‌هاست.

**۸ مقایسه در برابر کنترل → تصحیح Šidák: α = ۱−۰.۹۵^(۱/۸) ≈ ۰.۰۰۶۴.**

سقفِ نگه‌داری عمداً **ثابت** (۹۶ کندل = ۲۴ ساعت) نگه داشته شد. وسوسه‌اش
بود که آن را هم محور کنیم، ولی هر محورِ سوم شبکه را به ۱۸+ خانه می‌برد،
آستانهٔ Šidák را سخت‌تر می‌کند و وقتِ رانر را دو برابر. اگر تارگتِ
بزرگ‌تر برنده شد، سؤالِ «آیا زمان کم می‌آورد؟» **آزمایشِ بعدی** است —
و درسِ ۲۳ اوت (hold=۱۵ بدتر از hold=۱۲۰) می‌گوید جوابش احتمالاً «بله».

──────────────── چه چیزی گزارش می‌شود، و چرا ────────────────

هر خانه علاوه بر خالص، **مکانیزم** را هم گزارش می‌کند:

  · `fee_r`    میانهٔ سهمِ کارمزد بر حسب R — همان `کارمزد٪ ÷ استاپ٪`
  · `gross`    ناخالص، تا معلوم شود بهبود از لبه آمده یا از کارمزد
  · `win_pct`  نرخ برد — تارگتِ بزرگ‌تر باید پایینش بیاورد
  · `n`        تعداد؛ کفِ استاپ نمونه را کم می‌کند

بدون این چهار، «بهتر شد» یک عدد است بدون توضیح. با این چهار، می‌شود
گفت **چرا**: اگر خالص بالا رفت و `fee_r` پایین آمد ولی ناخالص ثابت
ماند، بهبود از کارمزد است — دقیقاً همان چیزی که پیش‌بینی می‌شود.

خالص از منبع واحد `hamid/fees.py` بازمحاسبه می‌شود.

──────────────── قاعدهٔ توقفِ از پیش ثبت‌شده ────────────────

| حکم | شرط |
|---|---|
| `PROMOTE_CANDIDATE` | CI اختلاف (α تصحیح‌شده) کاملاً بالای صفر **و** n خانه ≥ ۲۰۰ → فقط **پیشنهاد** |
| `REJECT` | CI اختلاف کاملاً زیر صفر **و** n ≥ ۵۰۰ |
| `UNDECIDED` | بقیه |

آینهٔ `ob_lab` و `short_backtest` — تا سه آزمایشگاه با سه کف قضاوت نکنند.

**هیچ پیش‌فرضی عوض نمی‌شود.** `trainer.RR` و باندِ استاپ دست‌نخورده
می‌مانند تا حمید صریح تأیید کند (قانون ۰۳/۱۲).

──────────────── مرزِ صادقانه، از قبل ────────────────

۱. **تارگتِ بزرگ‌تر با سقفِ نگه‌داریِ ثابت، تایم‌اوت بیشتر می‌سازد.**
   ردیفِ تایم‌اوت نه برد است نه باخت؛ اگر سهمش بالا رفت، میانگین به
   سمت صفر کشیده می‌شود و «بهتر» شدنِ ظاهری می‌تواند فقط رقیق‌شدن باشد.
   پس `timeout_pct` هر خانه گزارش می‌شود و در تفسیر لازم است.
۲. **کفِ استاپ نمونه را کم می‌کند** — و معامله‌هایی که حذف می‌شوند
   تصادفی نیستند (نمادهای کم‌نوسان). این سوگیریِ انتخاب است، نه فقط
   کاهشِ n.
۳. بازپخش با فیلِ کامل و بی‌لغزش = سقفِ خوش‌بینانه.

    python3 -m hamid.geom_lab --selftest
    python3 -m hamid.geom_lab --universe 100 --bars 20000 --shard 0 --shards 12
    python3 -m hamid.geom_lab --merge out/*.json
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
OUT = ROOT / "signals" / "geom-lab.json"

from hamid import trainer as TR                              # noqa: E402
# آمار از آزمایشگاه اردر بلاک **قرض** گرفته می‌شود، نه بازنویسی — وگرنه
# دو تعریف از «بازهٔ اطمینان» در ریپو زنده می‌شود، همان کلاسِ عیبی که
# موتور شورت نسخهٔ ۱.۰ را باطل کرد.
from hamid.ob_lab import (_by_symbol, _cluster_boot, _net,   # noqa: E402
                          _stats, _verdict)

RR_LEVELS = (2.0, 3.0, 4.0)
STOP_LEVELS = (0.15, 1.0, 1.5)
CONTROL = "rr2.0/stop0.15"
TF = "15m"
MAX_HOLD = 96                     # ثابت و عمدی — شرحش بالای فایل

# ۹ خانه، ۸ مقایسه در برابر کنترل.
ARMS = {f"rr{r}/stop{s}": {"rr": r, "min_stop": s}
        for r in RR_LEVELS for s in STOP_LEVELS}
COMPARISONS = [a for a in ARMS if a != CONTROL]
ALPHA_SIDAK = 1 - (1 - 0.05) ** (1 / len(COMPARISONS))

# ── بازوی «پیش‌فرض» — اثباتِ محصول، بیرون از تحلیلِ از-پیش-ثبت‌شده ─────────
#
# ۹ سپتامبر کفِ استاپِ تولید از ۰.۱۵ به ۱.۵ رفت (تأیید حمید). ادعای
# «اعمال شد» بی‌اثبات، همان درسِ ۶ سپتامبر است: اسکریپتِ سبز ≠ محصولِ
# درست. پس این بازو موتور را **بی هیچ آرگومانی** صدا می‌زند و باید مو به
# مو با خانهٔ `rr2.0/stop1.5` یکی دربیاید.
#
# عمداً در `ARMS` نیست: ورودش به شبکه یعنی ۹ مقایسه به‌جای ۸ و آستانهٔ
# Šidák جابه‌جا می‌شد — یعنی تحلیلِ از-پیش-ثبت‌شده بعد از دیدنِ نتیجه عوض
# می‌شد. اثبات باید کنارِ تحلیل بنشیند، نه داخلش.
PROOF_ARM = "defaults"
PROOF_EQUALS = f"rr{TR.RR}/stop{TR.MIN_STOP_PCT}"
LEDGERS = list(ARMS) + [PROOF_ARM]

MIN_N_PROMOTE = 200
MIN_N_REJECT = 500


def run_symbol(sym, cd):
    """یک نماد، ۹ خانه + بازوی اثباتِ پیش‌فرض، همان کندل‌ها."""
    out = {}
    for arm, kw in ARMS.items():
        trades, _ = TR.replay_symbol(sym, cd, after_ms=0, cap=10_000, tf=TF,
                                     max_hold=MAX_HOLD, **kw)
        for t in trades:
            t["_arm"] = arm
        out[arm] = trades
    # بی هیچ آرگومانِ هندسه‌ای — دقیقاً همان چیزی که تولید صدا می‌زند.
    dflt, _ = TR.replay_symbol(sym, cd, after_ms=0, cap=10_000, tf=TF,
                               max_hold=MAX_HOLD)
    for t in dflt:
        t["_arm"] = PROOF_ARM
    out[PROOF_ARM] = dflt
    return out


def _fee_r(trades):
    """سهمِ کارمزد بر حسب R — از منبع واحد، نه فرمولِ محلی."""
    from hamid import fees
    out = []
    for t in trades:
        v = fees.cost_in_r(t.get("entry"), t.get("sl"), t.get("sym"))
        if v is not None:
            out.append(v)
    return out


def _mech(trades):
    """مکانیزم: ناخالص، کارمزد، نرخ برد، سهمِ تایم‌اوت."""
    if not trades:
        return {}
    gross = [t["R"] for t in trades if t.get("R") is not None]
    fr = _fee_r(trades)
    outc = {}
    for t in trades:
        outc[t.get("outcome")] = outc.get(t.get("outcome"), 0) + 1
    n = len(trades)
    return {
        "gross": round(statistics.fmean(gross), 4) if gross else None,
        "fee_r_median": round(statistics.median(fr), 4) if fr else None,
        "win_pct": round(sum(1 for g in gross if g > 0) / len(gross) * 100, 1)
        if gross else None,
        "timeout_pct": round(outc.get("timeout", 0) / n * 100, 1),
        "stop_pct_median": round(statistics.median(
            [abs(t["entry"] - t["sl"]) / t["entry"] * 100 for t in trades]), 3),
        "outcomes": outc,
    }


def _key(t):
    """هویتِ یک معامله برای مقایسهٔ دو دفتر — بی‌برچسبِ بازو."""
    return (t.get("sym"), t.get("opened"), t.get("dir"), t.get("entry"),
            t.get("sl"), t.get("tp1"), t.get("outcome"), t.get("R"))


def _proof(per_arm):
    """اثباتِ محصول: مسیرِ پیش‌فرضِ موتور = همان خانهٔ سنجیده‌شده؟

    اگر بازوی اثبات در این تکه نبود، `missing` برمی‌گردد — نه `True`.
    ادعای اثباتِ نگرفته، بدتر از نگفتن است.
    """
    if PROOF_ARM not in per_arm:
        return {"status": "missing", "expected_arm": PROOF_EQUALS}
    a = [_key(t) for t in per_arm[PROOF_ARM]]
    b = [_key(t) for t in per_arm.get(PROOF_EQUALS, [])]
    return {"status": "ok" if a == b and a else "MISMATCH",
            "expected_arm": PROOF_EQUALS,
            "engine_min_stop": TR.MIN_STOP_PCT, "engine_rr": TR.RR,
            "n_default": len(a), "n_expected": len(b)}


def judge(per_arm):
    nets = {a: _net(t) for a, t in per_arm.items()}
    by_sym = {a: {s: _net(v) for s, v in _by_symbol(t).items()}
              for a, t in per_arm.items()}
    res = {"alpha_sidak": round(ALPHA_SIDAK, 5),
           "comparisons": len(COMPARISONS),
           "control": CONTROL,
           "max_hold_bars": MAX_HOLD,
           "arms": {a: dict(_stats(nets[a]), **_mech(per_arm[a]))
                    for a in LEDGERS if a in per_arm},
           "product_proof": _proof(per_arm),
           "vs_control": {}}
    for a in COMPARISONS:
        ci = _cluster_boot(by_sym[a], by_sym[CONTROL], ALPHA_SIDAK)
        st_a, st_b = res["arms"][a], res["arms"][CONTROL]
        d = (st_a.get("mean") or 0) - (st_b.get("mean") or 0)
        res["vs_control"][a] = {
            "diff": round(d, 4),
            "ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "n_arm": st_a.get("n", 0),
            # `changed_pct` این‌جا معنا ندارد: عوض‌کردنِ rr **هر** تارگت را
            # عوض می‌کند، پس همیشه ~۱۰۰٪ است و محافظِ بی‌اثری لازم نیست.
            "verdict": _verdict(ci, st_a.get("n", 0), 100.0),
        }
    return res


def run(symbols=None, bars=2000, shard=0, shards=1, fetch=None, quiet=False):
    per_arm = {a: [] for a in LEDGERS}
    skipped = []
    if fetch is None:
        import sources

        def fetch(sym, n):
            rows = sources.klines_deep(sym, TF, n) \
                if hasattr(sources, "klines_deep") else sources.klines(sym, TF, n)
            return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3],
                     "c": k[4], "v": k[5]} for k in rows]
    if symbols is None:
        symbols = TR.top_symbols()
    symbols = sorted(symbols)
    mine = [s for i, s in enumerate(symbols) if i % shards == shard]
    for sym in mine:
        try:
            cd = fetch(sym, bars)
        except Exception as e:                                # noqa: BLE001
            skipped.append(f"{sym}: {type(e).__name__}")
            continue
        if len(cd) < TR.TFS[TF]["warmup"] + 60:
            skipped.append(f"{sym}: کندل کم ({len(cd)})")
            continue
        got = run_symbol(sym, cd)
        for a in LEDGERS:
            per_arm[a] += got[a]
        if not quiet:
            print(f"  {sym}: " + " · ".join(f"{a}={len(got[a])}"
                                            for a in sorted(ARMS)), flush=True)
    return {"per_arm": per_arm, "skipped": skipped, "n_symbols": len(mine)}


def _envelope(parts):
    per_arm = {a: [] for a in LEDGERS}
    skipped, nsym = [], 0
    for p in parts:
        for a in LEDGERS:
            per_arm[a] += p["per_arm"].get(a, [])
        skipped += p.get("skipped") or []
        nsym += p.get("n_symbols") or 0
    j = judge(per_arm)
    spans = [t["opened"] for t in per_arm[CONTROL] if t.get("opened")]
    j.update({
        "generated": int(time.time() * 1000),
        "tf": TF, "n_symbols": nsym, "n_skipped": len(skipped),
        "skipped": skipped[:10],
        "span": [time.strftime("%Y-%m-%d", time.gmtime(min(spans) / 1000)),
                 time.strftime("%Y-%m-%d", time.gmtime(max(spans) / 1000))]
        if spans else None,
        "stopping_rule": {"promote_min_n": MIN_N_PROMOTE,
                          "reject_min_n": MIN_N_REJECT,
                          "metric": "خالص از کارمزد (hamid/fees)",
                          "bootstrap": "خوشه‌ای روی نماد"},
        "boundary": ("بازپخش با فیلِ کامل و بی‌لغزش (سقفِ خوش‌بینانه). "
                     "سقفِ نگه‌داری در همهٔ خانه‌ها ثابت ۹۶ کندل است؛ "
                     "تارگتِ بزرگ‌تر با سقفِ ثابت تایم‌اوتِ بیشتر می‌سازد و "
                     "تایم‌اوت میانگین را به سمت صفر می‌کشد — پس "
                     "`timeout_pct` هر خانه باید کنارِ عددش خوانده شود. "
                     "کفِ استاپ هم نمونه را **غیرتصادفی** کم می‌کند "
                     "(نمادهای کم‌نوسان حذف می‌شوند). "
                     "PROMOTE_CANDIDATE = پیشنهاد، نه اجرا (قانون ۰۳)."),
        "panel": "لیام تریدر ۹",
    })
    return j


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--universe", type=int, default=100)
    ap.add_argument("--bars", type=int, default=2000)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out")
    ap.add_argument("--merge", nargs="*")
    a = ap.parse_args(list(argv))
    if a.selftest:
        return _selftest()
    if a.merge:
        parts = [json.loads(Path(p).read_text(encoding="utf-8"))
                 for p in a.merge]
        j = _envelope(parts)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(j, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(json.dumps({k: j[k] for k in ("arms", "vs_control", "n_symbols",
                                            "n_skipped", "span")},
                         ensure_ascii=False, indent=1))
        return 0
    r = run(TR.top_symbols(a.universe), bars=a.bars, shard=a.shard,
            shards=a.shards)
    if a.out:
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False),
                               encoding="utf-8")
        print(f"تکه {a.shard}: " + " · ".join(f"{k}={len(v)}"
                                              for k, v in sorted(r["per_arm"].items())))
    else:
        print(json.dumps(_envelope([r]), ensure_ascii=False, indent=1))
    return 0


# ── خودآزمایی ─────────────────────────────────────────────────────────────

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
    cd = stairs._ladder(steps=18, start=200.0, leg=6.0, back=2.2, bars=7)

    # ۱) کنترل **مو به مو** همان مسیرِ پیش‌فرضِ trainer است
    base, _ = TR.replay_symbol("XUSDT", cd, tf=TF)
    ctrl, _ = TR.replay_symbol("XUSDT", cd, tf=TF, **ARMS[CONTROL],
                               max_hold=MAX_HOLD)
    key = lambda t: (t["dir"], t["entry"], t["sl"], t["tp1"],  # noqa: E731
                     t["opened"], t["outcome"], t["R"])
    chk([key(t) for t in base] == [key(t) for t in ctrl],
        "خانهٔ کنترل با مسیرِ پیش‌فرضِ trainer یکی نیست — دفتر بی‌اعتبار می‌شود")
    chk(TR.RR == 2.0 and CONTROL == "rr2.0/stop0.15",
        "کنترل با مقدارِ واقعیِ امروز هم‌گام نیست")

    # ۲) **رفعِ عیبِ نهفته**: R روی تارگت از خودِ تارگت می‌آید، نه از
    #    ثابتِ ماژول. با rr=4 باید ۴ برگردد، نه ۲.
    for rr in (2.0, 3.0, 4.0):
        tr, _ = TR.replay_symbol("XUSDT", cd, tf=TF, rr=rr, max_hold=MAX_HOLD)
        hits = [t["R"] for t in tr if t["outcome"] == "target"]
        # بدون این خط، `all()` روی فهرستِ خالی True است و بررسی **توخالی**
        # می‌شود. اثبات منفیِ اول دقیقاً همین‌جا گیر کرد و اول نگرفت.
        chk(hits, f"با rr={rr} هیچ تارگتی نخورد — بررسی توخالی می‌شود")
        chk(all(abs(r - rr) < 0.01 for r in hits),
            f"با rr={rr} تارگت R={set(hits)} داد — عیبِ ثابتِ ماژول برنگشته؟")
        chk(all((t.get("why") or {}).get("rr") == rr for t in tr),
            f"اثرانگشتِ rr={rr} روی ردیف ثبت نشد")

    # ۳) هندسه واقعاً تارگت را جابه‌جا می‌کند (وگرنه آزمون توخالی است)
    t2, _ = TR.replay_symbol("XUSDT", cd, tf=TF, rr=2.0, max_hold=MAX_HOLD)
    t4, _ = TR.replay_symbol("XUSDT", cd, tf=TF, rr=4.0, max_hold=MAX_HOLD)
    chk(t2 and t4, "بازپخشِ سریِ آزمون معامله‌ای نساخت")
    if t2 and t4:
        chk(t2[0]["tp1"] != t4[0]["tp1"], "تغییر rr تارگت را عوض نکرد")
        chk(t2[0]["sl"] == t4[0]["sl"], "تغییر rr نباید استاپ را عوض کند")

    # ۴) کفِ استاپ واقعاً فیلتر می‌کند و نمونه را کم می‌کند
    lo, _ = TR.replay_symbol("XUSDT", cd, tf=TF, min_stop=0.15,
                             max_hold=MAX_HOLD)
    hi, _ = TR.replay_symbol("XUSDT", cd, tf=TF, min_stop=5.0,
                             max_hold=MAX_HOLD)
    chk(len(hi) <= len(lo), "کفِ بالاتر نمونه را بیشتر کرد — بی‌معنا")
    chk(all(abs(t["entry"] - t["sl"]) / t["entry"] * 100 >= 5.0 for t in hi),
        "ردیفی زیرِ کفِ استاپ عبور کرد")

    # ۵) شبکه و تصحیح چندآزمونی
    chk(len(ARMS) == 9, f"شبکه ۹ خانه نیست: {len(ARMS)}")
    chk(len(COMPARISONS) == 8, f"مقایسه‌ها ۸ تا نیست: {len(COMPARISONS)}")
    chk(abs(ALPHA_SIDAK - (1 - 0.95 ** (1 / 8))) < 1e-12, "Šidák غلط")
    chk(ALPHA_SIDAK < 0.05, "تصحیح چندآزمونی آستانه را شل کرد")
    chk(CONTROL in ARMS, "کنترل داخل شبکه نیست")

    # ۶) مکانیزم گزارش می‌شود — بدونش «بهتر شد» بی‌توضیح است
    m = _mech(t2)
    for k in ("gross", "fee_r_median", "win_pct", "timeout_pct",
              "stop_pct_median"):
        chk(k in m, f"مکانیزم {k} گزارش نمی‌شود")
    chk(m["fee_r_median"] is None or m["fee_r_median"] > 0,
        "سهمِ کارمزد صفر/منفی درآمد")

    # ۷) **مکانیزمِ ادعا**: استاپِ گشادتر باید سهمِ کارمزد را کم کند.
    #    این اتحادِ حسابی است؛ اگر نقض شود یعنی محاسبه خراب است.
    from hamid import fees
    a1 = fees.cost_in_r(100.0, 100.5)          # استاپ ۰.۵٪
    a2 = fees.cost_in_r(100.0, 102.0)          # استاپ ۲.۰٪
    chk(a1 is not None and a2 is not None and a1 > a2,
        f"استاپِ گشادتر سهمِ کارمزد را کم نکرد: {a1} در برابر {a2}")
    chk(abs(a1 / a2 - 4.0) < 0.05,
        f"نسبتِ سهمِ کارمزد با نسبتِ استاپ نمی‌خواند: {a1}/{a2}")

    # ۸) داور: بی‌نمونه حکم نمی‌دهد
    j = judge({a: [] for a in ARMS})
    chk(all(v["verdict"] == "UNDECIDED" for v in j["vs_control"].values()),
        "بی‌نمونه حکم صادر شد")
    chk(j["control"] == CONTROL and j["max_hold_bars"] == MAX_HOLD,
        "قیدهای آزمایش روی خروجی اعلام نشدند")

    # ۹) آزمایشگاه دفترِ تولید را نمی‌نویسد (قانون ۰۵)
    src = (HERE / "geom_lab.py").read_text(encoding="utf-8")
    body = src.split("def _selftest(")[0]
    for bad in ("paper._append", "_save_state", "digest_closed", "import paper"):
        chk(bad not in body, f"آزمایشگاه دفتر تولید را دست زد: {bad}")
    chk("def _selftest(" in src, "بخشِ خودآزمایی پیدا نشد — برشِ بالا بی‌اثر")

    # ۱۰) آمار قرض گرفته شده، بازنویسی نشده
    chk("from hamid.ob_lab import" in body,
        "آمار از ob_lab قرض گرفته نشده — خطرِ تعریفِ دوم از CI")

    # ۱۱) بازوی اثباتِ محصول — کفِ تولید واقعاً همان خانهٔ سنجیده‌شده است
    chk(PROOF_ARM not in ARMS, "بازوی اثبات وارد شبکه شد — Šidák جابه‌جا می‌شود")
    chk(len(COMPARISONS) == 8, "بازوی اثبات شمارِ مقایسه‌ها را عوض کرد")
    chk(PROOF_EQUALS in ARMS,
        f"خانهٔ متناظرِ پیش‌فرضِ موتور در شبکه نیست: {PROOF_EQUALS}")
    # فیکسچرِ نردبانِ اصلی همهٔ استاپ‌هایش گشاد است، پس کنترل و خانهٔ ۱.۵
    # روی آن یکی درمی‌آیند و برابریِ پیش‌فرض چیزی را اثبات نمی‌کند. این
    # فیکسچرِ دوم عمداً جوری کوک شده که **کف گاز بگیرد**: ۴ معامله در
    # کنترل، ۲ تا بعد از کف.
    cdp = stairs._ladder(steps=18, start=200.0, leg=3.5, back=1.3, bars=8)
    got = run_symbol("XUSDT", cdp)
    chk(len(got[CONTROL]) > len(got[PROOF_EQUALS]) > 0,
        f"فیکسچرِ اثبات تفکیک نمی‌کند: کنترل={len(got[CONTROL])} "
        f"· {PROOF_EQUALS}={len(got[PROOF_EQUALS])}")
    chk(PROOF_ARM in got and len(got[PROOF_ARM]) > 0,
        "بازوی اثبات معامله‌ای نساخت — اثباتِ توخالی")
    pr = _proof(got)
    chk(pr["status"] == "ok", f"مسیرِ پیش‌فرضِ موتور با {PROOF_EQUALS} یکی نیست: {pr}")
    chk(pr["engine_min_stop"] == TR.MIN_STOP_PCT == 1.5,
        f"کفِ تولید ۱.۵ نیست: {TR.MIN_STOP_PCT}")
    # اثباتِ منفی: اگر پیش‌فرضِ موتور هنوز کنترل بود، همین بررسی می‌افتاد
    _bad = dict(got, **{PROOF_EQUALS: got[CONTROL]})
    chk(_proof(_bad)["status"] == "MISMATCH",
        "بررسیِ اثبات گاز نمی‌گیرد — با دفترِ اشتباه هم ok گفت")
    chk(_proof({a: [] for a in ARMS})["status"] == "missing",
        "بازوی غایب «ok» گزارش شد — ادعای اثباتِ نگرفته")

    print(f"geom_lab: {ok} بررسی سبز" + (f" · {fails} قرمز" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
