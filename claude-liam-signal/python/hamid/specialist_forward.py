#!/usr/bin/env python3
"""میزِ رو-به-جلوی متخصصین — «چقدر روی خودشان اثر مثبت گذاشتند؟»

حمید، ۱۷ سپتامبر: «گزارش کار متخصصین رو بده که خودشون چقدر روی خودشون
تاثیر مثبت گذاشتن؟»

═══════════════════════════════════════════════════════════════════════
  چرا میزِ موجود نمی‌توانست این را جواب بدهد
═══════════════════════════════════════════════════════════════════════

میز متخصصین (`specialist_run`) هر بار روی «نیمهٔ دومِ ~۲۱ روز اخیر»
قضاوت می‌کند. دو اجرا که ۱۰ ساعت فاصله دارند تقریباً **همان داده** را
می‌بینند، پس تفاوتشان بیشتر «قرعهٔ دوباره» است تا «بهتر شدن».

اندازه‌گیریِ همان دو اجرا (۱۶ سپتامبر ۲۲:۰۸ و ۱۷ سپتامبر ۰۸:۳۵):

  · میانگین تغییر روی ۱۲ میز: **−۰.۰۱۵۱R** · بهتر ۶ از ۱۲ · میانه ~۰
  · از ۶ ایدهٔ پذیرفته‌شده، فقط **۴** در اجرای بعد هم پذیرفته ماندند —
    سرطان و سنبله ایده‌شان را پس گرفتند، حوت و عقرب ایدهٔ تازه برداشتند،
    **روی داده‌ای که ۹۵٪‌اش همان دادهٔ قبل بود**.

انتخابی که روی همان داده عوض می‌شود، نویز را دنبال می‌کند نه لبه را.

═══════════════════════════════════════════════════════════════════════
  کاری که این فایل می‌کند
═══════════════════════════════════════════════════════════════════════

۱. **قفل (freeze)**: پارامترهای فعلیِ هر متخصص (پذیرفته‌شده) و پارامترِ
   پایه‌اش با مهرِ زمان و اثرانگشت ثبت می‌شوند.
۲. **نمره فقط روی کندلِ بعد از قفل**: هر اجرا، هر دو نسخه روی
   **کندل‌هایی که لحظهٔ قفل هنوز وجود نداشتند** بازپخش می‌شوند. پنجره
   با گذشت زمان بزرگ می‌شود؛ داده هرگز دوباره انتخاب نمی‌شود.
۳. **قاعدهٔ توقف از پیش ثبت‌شده** (پایین) — نه بعد از دیدن عدد.

## سه قیدی که این را از «باز هم بهینه‌سازی» جدا می‌کند

- **قفل تکان نمی‌خورد.** اجرای بعدیِ آزمایشگاه اگر ایدهٔ دیگری بپسندد،
  به این قفل کاری ندارد. تنها راه عوض‌شدنش `--refreeze` است، یعنی
  تصمیم صریح. بی این قید، هر اجرا قفل را از نو می‌ساخت و پنجرهٔ
  رو-به-جلو هیچ‌وقت بزرگ نمی‌شد — همان چیزی که کلِ این میز را بی‌معنا
  می‌کرد.
- **بازمحاسبهٔ کامل، نه انباشت.** هر اجرا کلِ پنجرهٔ بعدِ قفل را از نو
  می‌سنجد و خلاصه را بازمی‌نویسد؛ دفتر `forward.jsonl` فقط عکس‌فوریِ هر
  اجراست. انباشتِ ردیف‌ها همان دامی است که ۲۴ اوت دفتر پیپر را باددار
  کرد (۷۲.۹٪ تکرار) و CI را ساختگی تنگ کرد.
- **کارمزد همیشه کسر است** و مقایسه با **پایهٔ خودِ همان متخصص** انجام
  می‌شود، نه با میانگین بقیه — وگرنه رژیمِ بازار به حساب مهارت نوشته
  می‌شود (درسِ ۱۷ سپتامبر: هر ۱۲ مراقب با هم افتادند).

## قاعدهٔ توقف (ثبت‌شده پیش از دیدن هر عددی)

| حکم | شرط |
|---|---|
| `IMPROVED` | CI۹۵ اختلافِ خالص (شیداک ۱۲ آزمون، z=۲.۵۸) کاملاً **بالای** صفر روی n≥۲۰۰ در هر بازو |
| `NOT_IMPROVED` | CI کاملاً **زیر** صفر روی n≥۴۰۰ |
| `UNDECIDED` | بقیه، با برآوردِ نمونهٔ لازم |

خروجی: `signals/specialist-forward.json` (ردیف قرارداد، مالک E18) ·
دفتر: `brain/specialists/frozen.json` + `brain/specialists/forward.jsonl`

    python3 -m hamid.specialist_forward --freeze --write
    python3 -m hamid.specialist_forward --score --write
    python3 -m hamid.specialist_forward --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]

from hamid.specialist_lab import (SPECIALISTS, BY_ID, TF, PER_SYMBOL,   # noqa: E402
                                  WARMUP, replay, summarize)

LAB = ROOT / "signals" / "specialist-lab.json"
FROZEN = ROOT / "brain" / "specialists" / "frozen.json"
FWD_LEDGER = ROOT / "brain" / "specialists" / "forward.jsonl"
OUT = ROOT / "signals" / "specialist-forward.json"

Z_SIDAK = 2.58                 # ۱۲ آزمون هم‌زمان، دوطرفه ۰.۰۵
N_PROMOTE = 200
N_REJECT = 400
BAR_MIN = 15                   # دقیقه — تایم‌فریم میز
MIN_BARS = 400
MAX_BARS = 2000


def fingerprint(params):
    """اثرانگشتِ قطعیِ یک مجموعه پارامتر — تغییرش یعنی دفترِ حکم از صفر."""
    blob = json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def _load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def freeze(now_ms=None, refreeze=False, lab=None, log=print):
    """پارامترهای فعلی را قفل کن. قفلِ موجود دست نمی‌خورد مگر با refreeze.

    نبودِ خروجیِ آزمایشگاه یعنی «قفلی ساخته نمی‌شود»، نه «پارامتر پایه را
    قفل کن» — قفلِ ساختگی بدتر از نداشتنش است (قانون ۱).
    """
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    src = lab if lab is not None else _load(LAB, None)
    if not src or not src.get("desks"):
        return {"ok": False, "why": "خروجی آزمایشگاه متخصصین خوانده نشد — قفلی ساخته نشد"}
    cur = _load(FROZEN, {"specs": {}, "history": []})
    specs = cur.setdefault("specs", {})
    hist = cur.setdefault("history", [])
    made, kept = [], []
    for sid, d in src["desks"].items():
        used = d.get("params_used") or {}
        base = d.get("params_base") or {}
        fp = fingerprint(used)
        old = specs.get(sid)
        if old and not refreeze:
            kept.append(sid)
            continue
        if old and refreeze and old.get("fp") != fp:
            hist.append({**old, "retired_at": now})
        specs[sid] = {"id": sid, "fa": d.get("fa"), "strategy_fa": d.get("strategy_fa"),
                      "frozen_at": now, "fp": fp, "params": used, "base": base,
                      "adopted": bool((d.get("improvement") or {}).get("adopted")),
                      "lab_generated": src.get("generated")}
        made.append(sid)
    cur["generated"] = now
    FROZEN.parent.mkdir(parents=True, exist_ok=True)
    FROZEN.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"قفل: {len(made)} تازه · {len(kept)} دست‌نخورده", flush=True)
    return {"ok": True, "frozen": made, "kept": kept, "n": len(specs)}


def _diff_ci(a, b, z=Z_SIDAK):
    if len(a) < 2 or len(b) < 2:
        return None, (None, None), None
    d = statistics.fmean(a) - statistics.fmean(b)
    se = math.sqrt(statistics.pvariance(a) / len(a) + statistics.pvariance(b) / len(b))
    return round(d, 4), (round(d - z * se, 4), round(d + z * se, 4)), se


def _verdict(d, ci, n_arm, n_base, se):
    lo, hi = ci
    n = min(n_arm, n_base)
    if d is None or lo is None:
        return "UNDECIDED", "نمونه هنوز برای برآورد هم کم است"
    if n >= N_PROMOTE and lo > 0:
        return "IMPROVED", f"CI کاملاً بالای صفر روی n={n}"
    if n >= N_REJECT and hi < 0:
        return "NOT_IMPROVED", f"CI کاملاً زیر صفر روی n={n}"
    need = ""
    if se and se > 0:
        # نمونهٔ لازم تا نیم‌پهنای ۰.۰۵R (تقریب: se ~ 1/sqrt(n))
        k = (Z_SIDAK * se / 0.05) ** 2
        need = f"؛ برآورد ~{max(0, int(k * n - n))} نمونهٔ دیگر تا نیم‌پهنای ۰.۰۵R"
    return "UNDECIDED", f"n={n}{need}"


def _first_index_after(cd, ts):
    """اولین کندلی که لحظهٔ قفل هنوز **بسته نشده بود**.

    ملاک زمانِ بازشدن نیست: کندلی که موقع قفل باز بوده، بخشی از گذشته را
    در خودش دارد. پس کندلی حساب می‌شود که *شروعش* بعد از قفل باشد.
    """
    for i, k in enumerate(cd):
        if k["t"] > ts:
            return i
    return len(cd)


def score(now_ms=None, n_symbols=200, per_symbol=PER_SYMBOL, klines=None,
          universe=None, log=print):
    """هر متخصص: نسخهٔ قفل‌شده در برابر پایهٔ خودش، فقط روی کندلِ بعد از قفل."""
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    fr = _load(FROZEN, {"specs": {}})
    specs = fr.get("specs") or {}
    if not specs:
        return {"generated": now, "ok": False,
                "why": "هیچ قفلی ثبت نشده — اول --freeze"}
    oldest = min(v["frozen_at"] for v in specs.values())
    age_min = max(0.0, (now - oldest) / 60000.0)
    need = int(WARMUP + age_min / BAR_MIN + 20)
    bars = max(MIN_BARS, min(MAX_BARS, need))

    if universe is None:
        from hamid.specialist_run import _universe
        universe = _universe(n_symbols * 3)[:n_symbols]
    if klines is None:
        from hamid.specialist_run import _klines
        klines = lambda s: _klines(s, bars)          # noqa: E731

    series = []
    for s in universe:
        cd = klines(s)
        if len(cd) >= WARMUP + 5:
            series.append((s, cd))
        if len(series) >= n_symbols:
            break
    log(f"کندل: {len(series)} ارز · عمقِ خواسته {bars} · سنِ قفل {age_min:.0f} دقیقه",
        flush=True)

    desks, t0 = {}, time.time()
    for sid, f in specs.items():
        spec = BY_ID.get(sid)
        if not spec:
            continue
        arm, base = [], []
        for sym, cd in series:
            lo = _first_index_after(cd, f["frozen_at"])
            lo = max(lo, WARMUP)
            if lo >= len(cd) - 3:
                continue
            arm += replay(sym, cd, spec, f["params"], lo=lo, cap=per_symbol)
            base += replay(sym, cd, spec, f["base"], lo=lo, cap=per_symbol)
        an = [t["net_r"] for t in arm if t.get("net_r") is not None]
        bn = [t["net_r"] for t in base if t.get("net_r") is not None]
        d, ci, se = _diff_ci(an, bn)
        v, why = _verdict(d, ci, len(an), len(bn), se)
        desks[sid] = {
            "fa": f.get("fa"), "strategy_fa": f.get("strategy_fa"),
            "frozen_at": f["frozen_at"], "fp": f["fp"], "adopted": f.get("adopted"),
            "window_min": round(age_min, 1),
            "arm": summarize(arm), "base": summarize(base),
            "diff_net": d, "diff_ci": list(ci), "verdict": v, "why": why,
            "params": f["params"], "params_base": f["base"]}
    out = {
        "generated": now, "ok": True, "panel": "لیام تریدر ۹", "owner": "E18",
        "tf": TF, "n_symbols": len(series), "per_symbol": per_symbol,
        "window_min": round(age_min, 1), "seconds": round(time.time() - t0, 1),
        "desks": desks,
        "method": ("پارامترِ قفل‌شدهٔ هر متخصص در برابر پایهٔ خودش، فقط روی "
                   "کندل‌هایی که لحظهٔ قفل هنوز شروع نشده بودند. هر اجرا کلِ "
                   "پنجرهٔ بعدِ قفل را از نو می‌سنجد (بازمحاسبه، نه انباشت)، "
                   "پس هیچ معامله‌ای دوبار شمرده نمی‌شود."),
        "stop_rule": {"IMPROVED": f"CI بالای صفر روی n≥{N_PROMOTE}",
                      "NOT_IMPROVED": f"CI زیر صفر روی n≥{N_REJECT}",
                      "z": Z_SIDAK, "tests": 12},
        "boundary": ("دفتر پیپر است: فیل کامل و بی‌لغزش فرض می‌شود، پس سقفِ "
                     "خوش‌بینانه است نه انتظارِ لایو. حکمِ IMPROVED فقط "
                     "*پیشنهاد* است؛ ورود به تولید تأیید صریح حمید می‌خواهد "
                     "(قانون ۰۳/۱۲). این میز هیچ دروازه، سایز یا پیامی را "
                     "عوض نمی‌کند.")}
    return out


def write(out):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        FWD_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with FWD_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": out["generated"], "window_min": out.get("window_min"),
                                "desks": {k: {"n": (v["arm"] or {}).get("n"),
                                              "arm": (v["arm"] or {}).get("net"),
                                              "base": (v["base"] or {}).get("net"),
                                              "diff": v.get("diff_net"),
                                              "verdict": v.get("verdict")}
                                          for k, v in (out.get("desks") or {}).items()}},
                               ensure_ascii=False) + "\n")
    except Exception:                                # noqa: BLE001
        pass


def render(d):
    if not d.get("ok"):
        return f"میز رو-به-جلو: {d.get('why')}"
    L = [f"میز رو-به-جلوی متخصصین — پنجره {d['window_min']:.0f} دقیقه پس از قفل "
         f"· {d['n_symbols']} ارز"]
    rows = sorted(d["desks"].items(),
                  key=lambda kv: (kv[1].get("diff_net") is None,
                                  -(kv[1].get("diff_net") or 0)))
    for sid, v in rows:
        a, b = v["arm"] or {}, v["base"] or {}
        L.append(f"  {v['fa']:<7} [{v['strategy_fa']}] n={a.get('n')}/{b.get('n')} "
                 f"قفل={a.get('net')} پایه={b.get('net')} Δ={v.get('diff_net')} "
                 f"CI={v.get('diff_ci')} {v['verdict']} — {v['why']}")
    return "\n".join(L)


def _selftest():
    ok, fail = 0, []

    def chk(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1; print(f"  ✓ {name}")
        else:
            fail.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))

    chk("اثرانگشت به ترتیب کلید وابسته نیست",
        fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1}))
    chk("و با عوض‌شدن مقدار عوض می‌شود",
        fingerprint({"a": 1}) != fingerprint({"a": 2}))

    cd = [{"t": i * 900_000, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1} for i in range(10)]
    chk("برشِ زمان فقط کندلِ شروع‌شده بعد از قفل را می‌گیرد",
        _first_index_after(cd, 3 * 900_000) == 4, str(_first_index_after(cd, 3 * 900_000)))
    chk("قفلِ آینده هیچ کندلی نمی‌دهد",
        _first_index_after(cd, 99 * 900_000) == len(cd))

    d, ci, se = _diff_ci([0.2] * 300, [0.0] * 300)
    chk("اختلافِ روشن حکم IMPROVED می‌گیرد",
        _verdict(d, ci, 300, 300, se)[0] == "IMPROVED", f"{d} {ci}")
    d2, ci2, se2 = _diff_ci([-0.2] * 500, [0.0] * 500)
    chk("اختلافِ منفیِ نمونه‌دار حکم NOT_IMPROVED می‌گیرد",
        _verdict(d2, ci2, 500, 500, se2)[0] == "NOT_IMPROVED", f"{d2} {ci2}")
    d3, ci3, se3 = _diff_ci([0.2] * 20, [0.0] * 20)
    chk("نمونهٔ کم، هر چقدر هم اختلاف زیاد، UNDECIDED می‌ماند",
        _verdict(d3, ci3, 20, 20, se3)[0] == "UNDECIDED", f"{d3} {ci3}")

    print()
    if fail:
        print(f"شکست: {len(fail)} از {ok + len(fail)}: {fail}")
        return 1
    print(f"خودآزمایی میز رو-به-جلو: هر {ok} بررسی سبز")
    return 0


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--refreeze", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--symbols", type=int, default=200)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(list(argv))
    if a.selftest:
        return _selftest()
    if a.freeze or a.refreeze:
        print(json.dumps(freeze(refreeze=a.refreeze), ensure_ascii=False))
    if a.score or not (a.freeze or a.refreeze):
        d = score(n_symbols=a.symbols)
        print(render(d))
        if a.write:
            write(d)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
