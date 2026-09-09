"""آزمایشگاه اردر بلاک — بک‌تستِ دو یافتهٔ ممیزی (دستور حمید، ۹ سپتامبر).

حمید: «هر دو یافتهٔ اردر بلاک رو بک‌تست بگیر.»

═══════════════════════════════════════════════════════════════════════
  دو یافته‌ای که سنجیده می‌شوند
═══════════════════════════════════════════════════════════════════════

**یافتهٔ ۱ — انتخابِ باکس: پرواکنش‌ترین یا نزدیک‌ترین؟**
`orderblocks.find` خروجی را با `sort(key=(-reactions, age))` مرتب می‌کند
و `near()` اولینِ همان ترتیب را برمی‌دارد. یعنی موتور همیشه
*پرواکنش‌ترین* باکس را می‌گیرد، نه *نزدیک‌ترین*. در ریزشِ پله‌ای هر پله
یک باکسِ تازه با `reactions=0` می‌سازد که ته صف می‌ایستد — پس موتور به
باکسِ کهنهٔ پلهٔ اول می‌چسبد. اثباتِ اجراشدهٔ ممیزی ۸ سپتامبر: باکسِ
کهنهٔ [۱۰۲.۰–۱۰۲.۶] با ۳ واکنش (فاصله ۲.۰×ATR) بر باکسِ تازهٔ
[۱۰۰.۶–۱۰۱.۰] (فاصله ۰.۶×ATR) مقدم شد. بازوی `nearest`.

**یافتهٔ ۲ — شرطِ رنگ.** متنِ خودِ حمید (قانون ۱۱): «بعد از ریزش
برمی‌گردیم تا **اولین کندل سبزِ قوی**». `orderblocks.hamid_candle` هیچ
شرط رنگی نداشت، پس در الگویِ «کندلِ قرمزِ بزرگ که خودش سقف را ساخت»
باکس می‌توانست خودِ کندلِ ریزش بشود (ارتفاعِ باکس در نمونهٔ ممیزی ۳
برابر — و ارتفاعِ باکس مستقیم روی پهنای استاپ می‌نشیند). بازوی
`colored`.

═══════════════════════════════════════════════════════════════════════
  روش — چهار بازو روی **همان** کندل‌ها
═══════════════════════════════════════════════════════════════════════

| بازو | انتخاب باکس | شرط رنگ |
|---|---|---|
| `base` | پرواکنش‌ترین (امروز) | ندارد (امروز) |
| `nearest` | **نزدیک‌ترین** | ندارد |
| `colored` | پرواکنش‌ترین | **دارد** |
| `both` | **نزدیک‌ترین** | **دارد** |

موتور، هندسهٔ استاپ، تارگت، تسویه و سقفِ نگه‌داری **عیناً** از
`hamid/trainer.py` قرض گرفته می‌شوند (`decide` + `resolve`) — تنها چیزی
که عوض می‌شود همان انتخابگرِ باکس است. این همان درسِ نسخهٔ ۱.۰ موتور
شورت است: تعریفِ بازنویسی‌شده، بک‌تست را دربارهٔ چیزِ دیگری می‌کند.

**مقایسه جفتی در سطحِ نماد است، نه در سطحِ معامله.** عوض‌کردنِ باکس،
استاپ و در نتیجه نتیجهٔ معامله را عوض می‌کند، پس دو بازو **مجموعهٔ
معاملهٔ متفاوتی** می‌سازند و جفت‌کردنِ ردیف‌به‌ردیف ممکن نیست. ولی هر دو
روی همان نمادها و همان کندل‌ها اجرا می‌شوند، پس بوت‌استرپِ **خوشه‌ای روی
نماد** پایه درست است: نماد قوی/ضعیف به هر دو بازو هم‌زمان می‌افتد.

**عددِ حیاتی که باید همراه هر نتیجه گفته شود: `changed_pct`** — چند
درصد از تصمیم‌ها واقعاً عوض شدند. اگر بازویی ۹۸٪ همان باکس را انتخاب
کند، «اختلاف بی‌معنا» یعنی آزمون ضعیف بود، نه یافته غلط.

خالص همیشه از منبع واحد `hamid/fees.py` بازمحاسبه می‌شود.

──────────────── قاعدهٔ توقفِ از پیش ثبت‌شده ────────────────

سه مقایسه در برابر `base` → تصحیح Šidák: α = ۱−۰.۹۵^(۱/۳) ≈ ۰.۰۱۶۹۵.

| حکم | شرط |
|---|---|
| `PROMOTE_CANDIDATE` | CI اختلاف (در α تصحیح‌شده) کاملاً بالای صفر **و** n بازو ≥ ۲۰۰ **و** `changed_pct` ≥ ۱۰٪ → فقط **پیشنهاد** به حمید |
| `REJECT` | CI اختلاف کاملاً زیر صفر **و** n ≥ ۵۰۰ |
| `UNDECIDED` | بقیه |

n=۲۰۰/۵۰۰ آینهٔ `short_backtest.MIN_N_PROMOTE/REJECT` است تا دو
آزمایشگاه با دو کف قضاوت نکنند.

`PROMOTE_CANDIDATE` هیچ چیزی را عوض نمی‌کند (قانون ۰۳/۱۲) — پیش‌فرضِ
`orderblocks` دست‌نخورده می‌ماند تا حمید صریح تأیید کند.

    python3 -m hamid.ob_lab --selftest
    python3 -m hamid.ob_lab --universe 100 --bars 20000 --shard 0 --shards 8
    python3 -m hamid.ob_lab --merge out/*.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "ob-lab.json"

from hamid import trainer as TR                              # noqa: E402

# چهار بازو. کلیدها به `orderblocks.near` می‌روند؛ `base` عیناً پیش‌فرض.
ARMS = {
    "base":    {"by_distance": False, "ob_color": False},
    "nearest": {"by_distance": True,  "ob_color": False},
    "colored": {"by_distance": False, "ob_color": True},
    "both":    {"by_distance": True,  "ob_color": True},
}
CONTROL = "base"
COMPARISONS = [a for a in ARMS if a != CONTROL]
ALPHA_SIDAK = 1 - (1 - 0.05) ** (1 / len(COMPARISONS))

MIN_N_PROMOTE = 200
MIN_N_REJECT = 500
MIN_CHANGED_PCT = 10.0          # آزمونی که تصمیم را عوض نکند، آزمون نیست

TF = "15m"
BOOT = 3000

# تنها ستاپی که انتخابگرِ باکس رویش اثر دارد. شاخهٔ `bos_continuation`
# باکس نمی‌بیند، پس جزء **جمعیتِ مرجعِ** این آزمایش نیست.
OB_SETUP = "ob_pullback"


def near_for(arm):
    """انتخابگرِ باکسِ همان بازو — از `orderblocks.near`، بی بازنویسی."""
    kw = ARMS[arm]
    from hamid.orderblocks import near

    def _f(cd, tf="1h"):
        return near(cd, tf=tf, **kw)
    return _f


def run_symbol(sym, cd):
    """یک نماد، چهار بازو، همان کندل‌ها. → {بازو: [معامله‌ها]} + شمارِ تفاوت.

    `after_ms=0` و `cap` بزرگ: کلِ سری بازپخش می‌شود، بی حالتِ ماندگار —
    آزمایشگاه دفترِ تولید را نمی‌خواند و نمی‌نویسد (قانون ۰۵).
    """
    out, keys = {}, {}
    for arm in ARMS:
        trades, _ = TR.replay_symbol(sym, cd, after_ms=0, cap=10_000, tf=TF,
                                     near_fn=near_for(arm))
        for t in trades:
            t["_arm"] = arm
        out[arm] = trades
        # هویتِ تصمیم = (کندلِ ورود، جهت، استاپ). استاپ داخل کلید است چون
        # عوض‌شدنِ باکس **همان جا** خودش را نشان می‌دهد.
        #
        # ⚠️ فقط ستاپِ `ob_pullback` شمرده می‌شود. `trainer.decide` شاخهٔ
        # دومی هم دارد (`bos_continuation`) که **اصلاً باکس را نگاه
        # نمی‌کند** — پس شمردنش در مخرج، نرخِ تغییر را رقیق می‌کند و
        # محافظِ `MIN_CHANGED_PCT` را الکی خوشحال/ناراحت می‌کند.
        # این را اجرای خشکِ محلی نشان داد: روی یک سریِ ساختگی هر ۴ معامله
        # از شاخهٔ BOS آمدند، پس چهار بازو خروجیِ **یکسان** دادند و
        # `changed_pct` صفر شد — اگر روی Actions اجرا می‌شد، ۸ تکه وقت
        # تلف می‌کرد و «هیچ اختلافی نیست» گزارش می‌شد.
        keys[arm] = {(t["opened"], t["dir"], round(t["sl"], 10))
                     for t in trades
                     if (t.get("why") or {}).get("setup") == OB_SETUP}
    base = keys[CONTROL]
    changed = {a: len(keys[a] ^ base) for a in ARMS}
    total = {a: max(1, len(keys[a] | base)) for a in ARMS}
    return out, changed, total


def _net(trades):
    """خالص از کارمزد با منبع واحد. → فهرست R_net."""
    from hamid import fees
    rows = [{"entry": t["entry"], "sl": t["sl"], "sym": t["sym"],
             "R": t["R"], "R_net": None} for t in trades]
    fees.apply_net(rows)
    return [r["R_net"] for r in rows if r["R_net"] is not None]


def _by_symbol(trades):
    d = {}
    for t in trades:
        d.setdefault(t["sym"], []).append(t)
    return d


def _cluster_boot(a_by_sym, b_by_sym, alpha, n=BOOT, seed=7):
    """بازهٔ اختلافِ میانگین با بوت‌استرپِ **خوشه‌ای روی نماد**.

    چرا خوشه‌ای: معامله‌های یک نماد هم‌حرکت‌اند (بتای BTC، ستاپ تکراری) و
    بوت‌استرپِ i.i.d نمونهٔ متورم می‌سازد و CI را به‌دروغ تنگ می‌کند —
    همان درسِ `paper._boot_diff`. نمادها با هم کشیده می‌شوند تا هر دو
    بازو همان نمادها را ببینند (جفت‌شدگی در سطحِ نماد).
    """
    syms = sorted(set(a_by_sym) | set(b_by_sym))
    if len(syms) < 4:
        return None
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        pick = [rng.choice(syms) for _ in syms]
        av = [x for s in pick for x in a_by_sym.get(s, [])]
        bv = [x for s in pick for x in b_by_sym.get(s, [])]
        if len(av) < 4 or len(bv) < 4:
            continue
        diffs.append(sum(av) / len(av) - sum(bv) / len(bv))
    if len(diffs) < n // 10:
        return None
    diffs.sort()
    return (diffs[int(len(diffs) * alpha / 2)],
            diffs[int(len(diffs) * (1 - alpha / 2))])


def _stats(xs):
    if not xs:
        return {"n": 0}
    m = statistics.fmean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    half = 1.96 * sd / (len(xs) ** 0.5) if len(xs) > 1 else 0.0
    return {"n": len(xs), "mean": round(m, 4), "sd": round(sd, 4),
            "lo": round(m - half, 4), "hi": round(m + half, 4)}


def _verdict(ci, n_arm, changed_pct):
    if ci is None:
        return "UNDECIDED"
    if ci[0] > 0 and n_arm >= MIN_N_PROMOTE and changed_pct >= MIN_CHANGED_PCT:
        return "PROMOTE_CANDIDATE"
    if ci[1] < 0 and n_arm >= MIN_N_REJECT:
        return "REJECT"
    return "UNDECIDED"


def _only_ob(trades):
    return [t for t in trades if (t.get("why") or {}).get("setup") == OB_SETUP]


def judge(per_arm, changed, total):
    """حکمِ هر بازو در برابر `base`، با تصحیح چندآزمونی.

    **جمعیتِ مرجعِ حکم `ob_pullback` است، نه همهٔ معامله‌ها** — چون تنها
    همان شاخه باکس را می‌بیند. برشِ `all` هم گزارش می‌شود تا اثرِ کلی روی
    میز پیدا باشد، ولی حکم از آن گرفته نمی‌شود: افزودنِ معامله‌های
    **یکسانِ** شاخهٔ BOS به هر دو بازو، اختلافِ واقعی را رقیق و CI را
    به‌دروغ تنگ می‌کند.
    """
    ob_arm = {a: _only_ob(t) for a, t in per_arm.items()}
    nets_all = {a: _net(t) for a, t in per_arm.items()}
    nets_ob = {a: _net(t) for a, t in ob_arm.items()}
    by_sym = {a: {s: _net(v) for s, v in _by_symbol(t).items()}
              for a, t in ob_arm.items()}
    res = {"alpha_sidak": round(ALPHA_SIDAK, 5),
           "comparisons": len(COMPARISONS),
           "population": OB_SETUP,
           "arms": {a: _stats(nets_ob[a]) for a in ARMS},
           "arms_all_setups": {a: _stats(nets_all[a]) for a in ARMS},
           "n_bos_branch": {a: len(per_arm[a]) - len(ob_arm[a]) for a in ARMS},
           "changed_pct": {a: round(changed.get(a, 0) / max(1, total.get(a, 1))
                                    * 100, 1) for a in ARMS},
           "vs_base": {}}
    for a in COMPARISONS:
        ci = _cluster_boot(by_sym[a], by_sym[CONTROL], ALPHA_SIDAK)
        st_a, st_b = res["arms"][a], res["arms"][CONTROL]
        d = (st_a.get("mean") or 0) - (st_b.get("mean") or 0)
        res["vs_base"][a] = {
            "diff": round(d, 4),
            "ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "n_arm": st_a.get("n", 0),
            "changed_pct": res["changed_pct"][a],
            "verdict": _verdict(ci, st_a.get("n", 0), res["changed_pct"][a]),
        }
    return res


def run(symbols=None, bars=2000, shard=0, shards=1, fetch=None, quiet=False):
    per_arm = {a: [] for a in ARMS}
    changed = {a: 0 for a in ARMS}
    total = {a: 0 for a in ARMS}
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
        got, ch, tot = run_symbol(sym, cd)
        for a in ARMS:
            per_arm[a] += got[a]
            changed[a] += ch[a]
            total[a] += tot[a]
        if not quiet:
            print(f"  {sym}: " + " · ".join(
                f"{a}={len(got[a])}" for a in ARMS), flush=True)
    return {"per_arm": per_arm, "changed": changed, "total": total,
            "skipped": skipped, "n_symbols": len(mine)}


def _envelope(parts):
    per_arm = {a: [] for a in ARMS}
    changed = {a: 0 for a in ARMS}
    total = {a: 0 for a in ARMS}
    skipped, nsym = [], 0
    for p in parts:
        for a in ARMS:
            per_arm[a] += p["per_arm"].get(a, [])
            changed[a] += p["changed"].get(a, 0)
            total[a] += p["total"].get(a, 0)
        skipped += p.get("skipped") or []
        nsym += p.get("n_symbols") or 0
    j = judge(per_arm, changed, total)
    spans = [t["opened"] for t in per_arm[CONTROL] if t.get("opened")]
    j.update({
        "generated": int(time.time() * 1000),
        "tf": TF,
        "n_symbols": nsym,
        "n_skipped": len(skipped),
        "skipped": skipped[:10],
        "span": [time.strftime("%Y-%m-%d", time.gmtime(min(spans) / 1000)),
                 time.strftime("%Y-%m-%d", time.gmtime(max(spans) / 1000))]
        if spans else None,
        "stopping_rule": {"promote_min_n": MIN_N_PROMOTE,
                          "reject_min_n": MIN_N_REJECT,
                          "min_changed_pct": MIN_CHANGED_PCT,
                          "metric": "خالص از کارمزد (hamid/fees)",
                          "bootstrap": "خوشه‌ای روی نماد"},
        "boundary": ("بازپخش با فیلِ کامل و بی‌لغزش (سقفِ خوش‌بینانه). "
                     "موتور/استاپ/تارگت عیناً از hamid/trainer.py؛ تنها "
                     "متغیرِ عوض‌شده انتخابگرِ باکس است. حکم فقط دربارهٔ "
                     "همین انتخابگر است، نه دربارهٔ کلِ استراتژی. "
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
        parts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.merge]
        j = _envelope(parts)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(j, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(json.dumps({k: j[k] for k in ("arms", "vs_base", "changed_pct",
                                            "n_symbols", "n_skipped", "span")},
                         ensure_ascii=False, indent=1))
        return 0
    syms = TR.top_symbols(a.universe)
    r = run(syms, bars=a.bars, shard=a.shard, shards=a.shards)
    if a.out:
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False),
                               encoding="utf-8")
        print(f"تکه {a.shard}: " + " · ".join(
            f"{k}={len(v)}" for k, v in r['per_arm'].items()))
    else:
        print(json.dumps(_envelope([r]), ensure_ascii=False, indent=1))
    return 0


# ── خودآزمایی ─────────────────────────────────────────────────────────────

def _red_top_series():
    """سری‌ای که سقفش را **خودِ کندلِ قرمزِ قوی** می‌سازد، بعد می‌ریزد.

    همان الگویی که ممیزی ۸ سپتامبر نشان داد باکس را از «اولین سبزِ قوی»
    به «خودِ کندل ریزش» منحرف می‌کند. کندل‌ها عمداً سقف/کفِ برابر
    نمی‌سازند (فرکتالِ سختِ موتور با تساوی پیوت نمی‌دهد).
    """
    cd, t, px = [], 0, 100.0
    def add(o, h, l, c):
        nonlocal t
        cd.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": 1000.0})
        t += 900_000
    for k in range(40):                       # بسترِ آرامِ کمی صعودی
        n = px + 0.02
        add(px, n + 0.01, px - 0.01, n); px = n
    for k in range(6):                        # صعودِ سبزِ قوی (باکسِ درست)
        n = px + 1.2
        add(px, n + 0.02, px - 0.02, n); px = n
    # کندلِ قرمزِ قوی که **خودش** سقف را می‌سازد: ویکِ بالا ریز (پس سقفِ
    # محلی است) و بدنه بزرگ‌تر از مجموع شدوها (پس `hamid_candle` قبولش
    # می‌کند). بی این دو شرط، لنگر روی کندلِ سبزِ قبلی می‌افتد و اصلاً
    # واگرایی‌ای وجود ندارد — نسخهٔ اولِ همین سری همین‌طور شد و بررسی
    # درست گرفتش.
    add(px, px + 0.05, px - 3.00, px - 2.85); px -= 2.85
    for k in range(12):                       # ریزشِ ایمپالسی
        n = px - 1.6
        add(px, px + 0.02, n - 0.02, n); px = n
    for k in range(30):                       # امتدادِ باکس تا انتهای چارت
        n = px + 0.05
        add(px, n + 0.02, px - 0.02, n); px = n
    return cd


def _selftest():
    ok = fails = 0

    def chk(cond, msg):
        nonlocal ok, fails
        if cond:
            ok += 1
        else:
            fails += 1
            print(f"  ✗ {msg}")

    from hamid import orderblocks as OB, stairs

    # ۱) پیش‌فرضِ `near` **مو به مو** همان رفتار قبلی است
    cd = stairs._ladder(steps=18, start=200.0, leg=6.0, back=2.2, bars=7)
    chk(OB.near(cd, tf=TF) == OB.near(cd, tf=TF, by_distance=False,
                                      ob_color=False),
        "پیش‌فرضِ near با آرگومان‌های صریحِ پیش‌فرض یکی نیست")
    chk(OB.find(cd, tf=TF) == OB.find(cd, tf=TF, ob_color=False),
        "پیش‌فرضِ find عوض شده — دفتر تاریخی بی‌اعتبار می‌شود")

    # ۲) شرط رنگ واقعاً اعمال می‌شود
    green = {"t": 0, "o": 10.0, "h": 11.1, "l": 9.95, "c": 11.0, "v": 1}
    red = {"t": 0, "o": 11.0, "h": 11.05, "l": 9.9, "c": 10.0, "v": 1}
    chk(OB.hamid_candle(green) and OB.hamid_candle(red),
        "بی‌شرطِ رنگ، هر دو کندلِ قوی باید قبول شوند")
    chk(OB.hamid_candle(green, want="up") is True, "کندل سبز رد شد")
    chk(OB.hamid_candle(green, want="down") is False, "سبز به‌جای قرمز قبول شد")
    chk(OB.hamid_candle(red, want="down") is True, "کندل قرمز رد شد")
    chk(OB.hamid_candle(red, want="up") is False, "قرمز به‌جای سبز قبول شد")
    doji = {"t": 0, "o": 10.0, "h": 12.0, "l": 8.0, "c": 10.05, "v": 1}
    chk(OB.hamid_candle(doji, want="up") is False,
        "کندلِ ضعیف با رنگِ درست قبول شد — شرطِ بدنه نباید دور زده شود")

    # ۲ب) **سیم‌کشیِ شرط رنگ در `find`** — نه فقط خودِ محمولهٔ رنگ.
    #     اثبات منفی نشان داد بی این بررسی، خاموش‌کردنِ رنگ در `find`
    #     هیچ آزمونی را نمی‌انداخت: یعنی آزمایشگاه می‌توانست بازوی
    #     `colored` را اجرا کند و در واقع همان `base` را بسنجد.
    #     سریِ آزمون عمداً همان الگویی است که ممیزی پیدا کرد: کندلِ
    #     **قرمزِ قوی که خودش سقف را می‌سازد**، پس بی شرطِ رنگ خودش باکس
    #     می‌شود و با شرطِ رنگ باید به سبزِ قبلش عقب برود.
    red_top = _red_top_series()
    b_off = OB.find(red_top, tf=TF, ob_color=False)
    b_on = OB.find(red_top, tf=TF, ob_color=True)
    off_i = {b["i"] for b in b_off if b["move"] == "down"}
    on_i = {b["i"] for b in b_on if b["move"] == "down"}
    chk(off_i, "سریِ آزمون هیچ باکسِ نزولی نساخت — بررسی بی‌اثر است")
    chk(off_i != on_i,
        f"شرطِ رنگ در find بی‌اثر است: بی‌رنگ={sorted(off_i)} "
        f"با‌رنگ={sorted(on_i)}")
    for b in b_on:
        c = red_top[b["i"]]
        want_green = b["move"] == "down"
        chk((c["c"] > c["o"]) == want_green,
            f"باکسِ رنگی در جهت {b['move']} رنگِ غلط دارد (i={b['i']})")

    # ۳) انتخابِ نزدیک‌ترین: بازسازیِ همان نمونهٔ ممیزی
    #    باکسِ کهنهٔ پرواکنش دور، باکسِ تازهٔ نزدیک — کدام برگردانده می‌شود؟
    px = 100.0
    stale = {"low": 102.0, "high": 102.6, "reactions": 3, "age": 90,
             "fresh": False, "broken": False, "i": 10, "tf": TF}
    fresh = {"low": 100.6, "high": 101.0, "reactions": 0, "age": 4,
             "fresh": True, "broken": False, "i": 96, "tf": TF}
    fake = [dict(stale), dict(fresh)]                 # ترتیبِ `find`: واکنش نزولی
    orig_find, orig_atr = OB.find, OB.atr
    OB.find = lambda cd, tf="1h", min_reactions=2, ob_color=False: \
        [dict(b) for b in fake]
    OB.atr = lambda cd, n=14: 1.0
    try:
        probe = [{"t": 0, "o": px, "h": px, "l": px, "c": px, "v": 1}] * 3
        _, n_base = OB.near(probe, tf=TF)
        _, n_dist = OB.near(probe, tf=TF, by_distance=True)
        chk(n_base is not None and n_base["i"] == 10,
            f"بازوی base باکسِ پرواکنشِ کهنه را نگرفت: {n_base}")
        chk(n_dist is not None and n_dist["i"] == 96,
            f"بازوی nearest باکسِ نزدیکِ تازه را نگرفت: {n_dist}")
        chk(n_base["i"] != n_dist["i"],
            "دو بازو یک باکس دادند — آزمون بی‌اثر است")
    finally:
        OB.find, OB.atr = orig_find, orig_atr

    # ۴) تزریق به trainer تصمیم را عوض می‌کند (وگرنه آزمایشگاه توخالی است)
    a_tr, _ = TR.replay_symbol("XUSDT", cd, tf=TF, near_fn=near_for("base"))
    b_tr, _ = TR.replay_symbol("XUSDT", cd, tf=TF, near_fn=near_for("both"))
    chk(len(a_tr) > 0, "بازپخشِ سریِ آزمون هیچ معامله‌ای نساخت")
    chk(TR.replay_symbol("XUSDT", cd, tf=TF)[0] == a_tr,
        "بازوی base با مسیرِ پیش‌فرضِ trainer یکی نیست")

    # ۴ب) **جمعیتِ مرجع**: شاخهٔ BOS نه در شمارشِ تغییر می‌آید نه در حکم.
    #     با `replay_symbol` جعلی سنجیده می‌شود تا سریعتر و صریح‌تر باشد.
    def fake_replay(sym, cd, after_ms=0, cap=0, tf=TF, near_fn=None):
        arm = "nearest" if near_fn and near_fn.__closure__ and \
            near_fn.__closure__[0].cell_contents.get("by_distance") else "base"
        sl_ob = 11.0 if arm == "base" else 12.0        # باکس عوض شد
        return ([
            {"sym": sym, "dir": "SHORT", "entry": 10.0, "sl": sl_ob,
             "tp1": 8.0, "opened": 1000, "outcome": "stop", "R": -1.0,
             "why": {"setup": "ob_pullback"}},
            # شاخهٔ BOS: **در هر دو بازو یکسان** — نباید مخرج را باد کند
            {"sym": sym, "dir": "SHORT", "entry": 20.0, "sl": 21.0,
             "tp1": 18.0, "opened": 2000, "outcome": "target", "R": 2.0,
             "why": {"setup": "bos_continuation"}},
        ], 0)
    orig_replay = TR.replay_symbol
    TR.replay_symbol = fake_replay
    try:
        got, ch, tot = run_symbol("ZUSDT", [{"t": 0}])
        chk(ch["nearest"] == 2 and tot["nearest"] == 2,
            f"شمارشِ تغییر شاخهٔ BOS را هم شمرد: changed={ch} total={tot}")
        j2 = judge(got, ch, tot)
        chk(j2["population"] == OB_SETUP, "جمعیتِ مرجع اعلام نشده")
        chk(j2["arms"]["base"]["n"] == 1,
            f"حکم روی همهٔ ستاپ‌ها گرفته شد: {j2['arms']['base']}")
        chk(j2["n_bos_branch"]["base"] == 1, "شمارِ شاخهٔ BOS گزارش نشد")
        chk(j2["arms_all_setups"]["base"]["n"] == 2,
            "برشِ همهٔ ستاپ‌ها گزارش نشد")
        chk(j2["changed_pct"]["nearest"] == 100.0,
            f"نرخِ تغییر غلط: {j2['changed_pct']}")
    finally:
        TR.replay_symbol = orig_replay

    # ۵) داور: بی‌نمونه حکم نمی‌دهد؛ و تفاوتِ صفر PROMOTE نمی‌گیرد
    j = judge({a: [] for a in ARMS}, {a: 0 for a in ARMS},
              {a: 1 for a in ARMS})
    chk(all(v["verdict"] == "UNDECIDED" for v in j["vs_base"].values()),
        "بی‌نمونه حکم صادر شد")
    # روی **ثابت** سنجیده می‌شود نه روی خروجیِ گِردشده — نسخهٔ اول این را
    # با `j["alpha_sidak"]` (گِردشده به ۵ رقم) سنجید و به‌درستی افتاد.
    chk(abs(ALPHA_SIDAK - (1 - 0.95 ** (1 / 3))) < 1e-12, "Šidák غلط")
    chk(ALPHA_SIDAK < 0.05, "تصحیح چندآزمونی آستانه را شل کرد")
    chk(len(COMPARISONS) == 3, "تعداد مقایسه با تصحیح Šidák هم‌گام نیست")

    # ۶) **اثبات منفی روی خودِ قاعدهٔ توقف**: اختلافِ آشکار ولی
    #    `changed_pct` ناچیز → نباید PROMOTE بدهد
    chk(_verdict((0.5, 0.9), 400, 2.0) == "UNDECIDED",
        "با تصمیمِ عوض‌نشده PROMOTE داد — آزمونِ توخالی قبول شد")
    chk(_verdict((0.5, 0.9), 400, 20.0) == "PROMOTE_CANDIDATE",
        "اختلافِ واقعی با نمونهٔ کافی PROMOTE نگرفت")
    chk(_verdict((0.5, 0.9), 50, 20.0) == "UNDECIDED", "n کم PROMOTE گرفت")
    chk(_verdict((-0.9, -0.5), 600, 20.0) == "REJECT", "REJECT صادر نشد")
    chk(_verdict((-0.9, -0.5), 100, 20.0) == "UNDECIDED",
        "REJECT با n کم صادر شد")
    chk(_verdict((-0.2, 0.3), 900, 50.0) == "UNDECIDED",
        "CI شاملِ صفر حکم گرفت")

    # ۷) بوت‌استرپِ خوشه‌ای: با نمادِ کم، None (نه عددِ ساختگی)
    chk(_cluster_boot({"A": [1.0] * 9}, {"A": [0.0] * 9}, 0.05) is None,
        "با یک نماد بازه ساخت — خوشه‌بندی بی‌اثر است")
    many_a = {f"S{i}": [1.0] * 5 for i in range(12)}
    many_b = {f"S{i}": [0.0] * 5 for i in range(12)}
    ci = _cluster_boot(many_a, many_b, 0.05)
    chk(ci is not None and ci[0] > 0.5, f"اختلافِ آشکار دیده نشد: {ci}")

    # ۸) آزمایشگاه دفترِ تولید را نمی‌نویسد (قانون ۰۵).
    #    فقط **کدِ اجرایی** سنجیده می‌شود، نه متنِ خودِ خودآزمایی — نسخهٔ
    #    اول کلِ فایل را می‌خواند و روی نامِ همان چیزهایی می‌افتاد که
    #    داشت منعشان می‌کرد (همان تلهٔ خودارجاعِ ۸ سپتامبر).
    src = (HERE / "ob_lab.py").read_text(encoding="utf-8")
    body = src.split("def _selftest(")[0]
    for bad in ("paper._append", "_save_state", "digest_closed",
                "OUT.write_text" if False else "import paper"):
        chk(bad not in body, f"آزمایشگاه دفتر تولید را دست زد: {bad}")
    chk("def _selftest(" in src, "بخشِ خودآزمایی پیدا نشد — برشِ بالا بی‌اثر است")

    print(f"ob_lab: {ok} بررسی سبز" + (f" · {fails} قرمز" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
