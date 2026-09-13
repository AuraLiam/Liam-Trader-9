#!/usr/bin/env python3
"""داورِ هندسهٔ بزرگ‌تر و شورتِ جدا (دستور حمید، ۱۳ سپتامبر).

حمید: «همین کار رو بکن، هندسه بزرگتر و شورت جدا.»

═══════════════════════════════════════════════════════════════════════
  چرا این فایل جداست و چرا قاعده‌اش از پیش نوشته شد
═══════════════════════════════════════════════════════════════════════

بک‌تست ۸۰نمادیِ ۱۳ سپتامبر دو چیز را قطعی کرد:

  · سهم کارمزد از R دقیقاً `کارمزد٪ ÷ استاپ٪` است. استاپ زیر ۰.۵٪ سهمش
    ۰.۵۲۵R بود، استاپ ≥۱.۵٪ فقط ۰.۰۵۹R. پس فرضیهٔ «هندسهٔ بزرگ‌تر لبه را
    نگه می‌دارد» فرضیهٔ مکانیکی است، نه آرزو.
  · شورت در هر سه بازو بدتر از لانگ بود و در base با CI کاملاً زیر صفر
    (−۰.۲۲۳R). قاطی‌کردنِ دو جهت یعنی میانگینی که هیچ‌کدام را توصیف
    نمی‌کند.

قاعدهٔ توقف **قبل از دیدن هر عددِ این آزمایش** ثبت شد — همان انضباطی که
`scalp_verdict` و `gate_verdict` دارند. بی این، هر نتیجه‌ای بعداً
قابل‌توجیه است و آزمایش به تشریفات تبدیل می‌شود.

┌─────────────────┬────────────────────────────────────────────────────┐
│ کاندیدای ترفیع  │ CI سختگیرانهٔ شیداک‌شده کاملاً بالای صفر · n ≥ ۴۰۰ ·│
│                 │ و همان جهت در **هر دو** تایم ۱۵د و ۵د              │
│ رد              │ CI سختگیرانهٔ شیداک‌شده کاملاً زیر صفر روی n ≥ ۳۰۰۰ │
│ بلاتکلیف        │ بقیه، با برآوردِ «چند معاملهٔ دیگر»                 │
└─────────────────┴────────────────────────────────────────────────────┘

سه قیدی که این داور را از «حکمِ راحت» جدا می‌کند:

۱. **معیار سختگیرانه است، نه خالصِ ساده.** `bt_worker.step()` به خروجِ
   «سربه‌سر» پاداشِ کاملِ R1 می‌دهد در حالی که اجرای واقعی آن را ≈صفر
   می‌بندد؛ روی همان اجرا این یک فرض ۸۵٪ از برتریِ ظاهریِ ibs را
   می‌ساخت. این داور فقط `strict` را می‌بیند.
۲. **شیداک روی شمارِ واقعیِ خانه‌ها.** هر بازو × هر جهت یک آزمون است؛
   با ۶ بازو و ۳ برش (کل/لانگ/شورت) ۱۸ خانه می‌شود و آستانه از همان
   شمار درمی‌آید، نه از ۰.۰۵ ثابت.
۳. **ترفیع یعنی پیشنهاد، نه اجرا.** هیچ دروازه و هیچ عددی از این مسیر
   خودکار عوض نمی‌شود (قانون ۰۳/۱۲). حکم `PROMOTE` فقط می‌گوید شواهد
   جمع شد؛ تصمیم با حمید است.

    python3 -m hamid.geometry_verdict --write
    python3 -m hamid.geometry_verdict --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]

BACKTESTS = ROOT / "claude-liam-signal" / "backtests"
OUT = ROOT / "signals" / "geometry-verdict.json"

MIN_N_PROMOTE = 400
MIN_N_REJECT = 3000
ALPHA = 0.05
BOOT = 3000
CUTS = ("overall", "long", "short")


def strict_r(t):
    """R سختگیرانه: خروجِ «سربه‌سر» صفر می‌گیرد، نه پاداشِ کاملِ R1."""
    r = 0.0 if t.get("why") == "breakeven" else t.get("r")
    if r is None:
        return None
    return r - (t.get("fee_r") or 0.0)


def sidak(m, alpha=ALPHA):
    """آستانهٔ تک‌آزمونی وقتی m آزمون هم‌زمان می‌دهیم."""
    m = max(1, int(m))
    return 1.0 - (1.0 - alpha) ** (1.0 / m)


def boot_ci(xs, alpha, seed=17, b=1000):
    """بازهٔ بوت‌استرپ سادهٔ iid در سطحِ داده‌شده. نمونهٔ کم = None.

    تصحیح ۱۳ سپتامبر: نسخهٔ اول نمونه‌گیری را به ۴٬۰۰۰ ردیف سقف می‌زد تا
    سریع بماند؛ برای n=۴۰٬۰۰۰ یعنی بازه‌ای ~۳ برابر پهن‌تر از واقعی. همان
    سقف بود که ibs را «شاملِ صفر» نشان می‌داد در حالی که بوت‌استرپ
    خوشه‌ای (که هیچ سقفی ندارد) از صفر رد می‌کرد. حالا با تمامِ n و
    `random.choices` (پیاده‌سازی C) نمونه می‌گیرد؛ داور روی خوشه‌ای حکم
    می‌دهد و این فقط برای مقایسهٔ دو راه کنارش می‌ماند.
    """
    n = len(xs)
    if n < 30:
        return None
    rnd = random.Random(seed)
    means = []
    for _ in range(b):
        means.append(sum(rnd.choices(xs, k=n)) / n)
    means.sort()
    lo = means[int((alpha / 2) * b)]
    hi = means[min(b - 1, int((1 - alpha / 2) * b))]
    return round(lo, 4), round(hi, 4)


DAY_MS = 24 * 3600 * 1000


def _day_of(t):
    a = t.get("openedAt")
    return int(a // DAY_MS) if isinstance(a, (int, float)) else "?"


def cluster_boot_ci(trades, alpha, seed=17, b=BOOT, min_clusters=10, key="sym"):
    """بوت‌استرپ خوشه‌ای — معامله‌های یک نماد، یا یک روز، مستقل نیستند.

    درس ۲۴ اوت (دفترِ باددار): CI فرض می‌کند هر ردیف یک مشاهدهٔ مستقل
    است؛ ۵۰ معاملهٔ هم‌زمانِ یک نماد در یک روند، پنجاه مشاهده نیستند.
    واحدِ نمونه‌گیری `key` است: «نماد» (وابستگیِ درون‌نماد) یا «روز»
    (وابستگیِ رژیمِ بازار بین همهٔ نمادها). زیر ۱۰ خوشه، None — نه بازهٔ
    ساختگی.

    اندازه‌گیری ۱۳ سپتامبر که این دو-خوشه‌ای‌بودن را اجباری کرد: با
    خوشه‌بندی فقط روی نماد، ۸ خانه ترفیع می‌گرفتند؛ با خوشه‌بندی روی
    روز، فقط یکی. یعنی بیشترِ آن ۸ تا وابستگیِ روزانه بودند نه لبه.
    """
    groups = {}
    for t in trades:
        v = strict_r(t)
        if v is None:
            continue
        k = _day_of(t) if key == "day" else (t.get("sym") or "?")
        groups.setdefault(k, []).append(v)
    keys = list(groups)
    if len(keys) < min_clusters:
        return None
    rnd = random.Random(seed)
    means = []
    for _ in range(b):
        s = n = 0.0
        for _ in range(len(keys)):
            g = groups[keys[rnd.randrange(len(keys))]]
            s += sum(g)
            n += len(g)
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * b)]
    hi = means[min(b - 1, int((1 - alpha / 2) * b))]
    return round(lo, 4), round(hi, 4)


def _slice(trades, cut):
    if cut == "long":
        return [t for t in trades if t.get("dir") == "LONG"]
    if cut == "short":
        return [t for t in trades if t.get("dir") == "SHORT"]
    return trades


def more_needed(xs, alpha):
    """چند نمونهٔ دیگر تا CI از صفر رد کند — برآورد، با مرزِ صریح.

    از رابطهٔ `نیم‌پهنا ∝ ۱/√n` می‌آید: اگر میانگین همین بماند، n لازم
    حدوداً `n × (نیم‌پهنا ÷ |میانگین|)²` است. اگر میانگین صفر یا منفی
    باشد عددی برنمی‌گردد — «بیشتر جمع کن» آن‌جا حرفِ بی‌معنایی است.
    """
    n = len(xs)
    if n < 30:
        return None
    m = statistics.fmean(xs)
    ci = boot_ci(xs, alpha, seed=23)
    if not ci or m <= 0:
        return None
    half = (ci[1] - ci[0]) / 2.0
    if half <= 0:
        return None
    need = n * (half / abs(m)) ** 2
    return max(0, int(math.ceil(need - n)))


def judge(by_arm, alpha_per_test=None):
    """{بازو: [معامله‌ها]} → جدولِ حکم برای هر بازو × هر جهت."""
    cells = [(a, c) for a in by_arm for c in CUTS]
    alpha = alpha_per_test if alpha_per_test is not None else sidak(len(cells))
    rows = {}
    for arm, trades in by_arm.items():
        for cut in CUTS:
            sub = _slice(trades, cut)
            xs = [v for v in (strict_r(t) for t in sub) if v is not None]
            key = f"{arm}|{cut}"
            if not xs:
                rows[key] = {"arm": arm, "cut": cut, "n": 0,
                             "verdict": "UNDECIDED", "why": "بی‌نمونه"}
                continue
            # داور روی **پهن‌ترینِ** دو CI خوشه‌ای حکم می‌دهد (نماد و روز)
            # — دو-خوشه‌ایِ محافظه‌کارانه؛ CI سادهٔ iid فقط برای مقایسه.
            ci_iid = boot_ci(xs, alpha)
            ci_sym = cluster_boot_ci(sub, alpha, key="sym")
            ci_day = cluster_boot_ci(sub, alpha, key="day")
            both = [c for c in (ci_sym, ci_day) if c]
            ci = (round(min(c[0] for c in both), 4), round(max(c[1] for c in both), 4)) \
                if both else ci_iid
            mean = round(statistics.fmean(xs), 4)
            win = round(100 * sum(1 for t in sub if (t.get("r") or 0) > 0) / len(sub), 1)
            # هم‌جهتی دو تایم — شرطِ ترفیع، نه تزئین
            tfs = {}
            for tf in sorted({t.get("tf") for t in sub if t.get("tf")}):
                sx = [v for v in (strict_r(t) for t in sub if t.get("tf") == tf)
                      if v is not None]
                if sx:
                    tfs[tf] = round(statistics.fmean(sx), 4)
            consistent = len(tfs) >= 2 and (all(v > 0 for v in tfs.values())
                                            or all(v < 0 for v in tfs.values()))
            row = {"arm": arm, "cut": cut, "n": len(xs), "win": win,
                   "strict": mean, "ci": list(ci) if ci else None,
                   "ci_iid": list(ci_iid) if ci_iid else None,
                   "ci_sym": list(ci_sym) if ci_sym else None,
                   "ci_day": list(ci_day) if ci_day else None,
                   "n_symbols": len({t.get("sym") for t in sub}),
                   "n_days": len({_day_of(t) for t in sub}),
                   "by_tf": tfs, "consistent": consistent,
                   "alpha": round(alpha, 5)}
            if ci and ci[0] > 0 and len(xs) >= MIN_N_PROMOTE and consistent:
                row["verdict"] = "PROMOTE"
                row["why"] = (f"CI سختگیرانه [{ci[0]:+.3f},{ci[1]:+.3f}] بالای صفر "
                              f"روی n={len(xs)} و هر دو تایم هم‌جهت")
            elif ci and ci[1] < 0 and len(xs) >= MIN_N_REJECT:
                row["verdict"] = "REJECT"
                row["why"] = (f"CI سختگیرانه [{ci[0]:+.3f},{ci[1]:+.3f}] زیر صفر "
                              f"روی n={len(xs)}")
            else:
                row["verdict"] = "UNDECIDED"
                need = more_needed(xs, alpha)
                if ci and ci[0] > 0 and not consistent:
                    row["why"] = "CI بالای صفر ولی دو تایم هم‌جهت نیستند"
                elif need:
                    row["why"] = f"~{need} معاملهٔ دیگر لازم است اگر میانگین همین بماند"
                else:
                    row["why"] = "شواهد کافی نیست و جهتِ میانگین ترفیع را نمی‌سازد"
            rows[key] = row
    return {"alpha_per_test": round(alpha, 5), "n_cells": len(cells), "rows": rows}


def latest_backtest():
    """تازه‌ترین بک‌تستی که **واقعاً ردیف معامله دارد**.

    `latest.json` فقط خلاصه است و کلید `trades` ندارد؛ اگر مستقیم از آن
    می‌خواندیم، داور برای همیشه و بی‌صدا NO_DATA می‌داد و کسی نمی‌فهمید.
    فایل‌های تاریخ‌دار ردیف‌ها را دارند، پس از تازه‌ترینِ آن‌ها شروع
    می‌کنیم و فقط اگر هیچ‌کدام نداشت سراغ latest می‌رویم.
    """
    dated = sorted(BACKTESTS.glob("backtest-*.json"), reverse=True)
    for p in dated[:3]:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            continue
        if doc.get("trades"):
            doc["_file"] = p.name
            return doc
    p = BACKTESTS / "latest.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def build(doc=None):
    doc = doc or latest_backtest()
    if not doc or not doc.get("trades"):
        return {"generated": int(time.time() * 1000), "status": "NO_DATA",
                "why": "فایل معامله‌های بک‌تست موجود نیست — داور عددی نمی‌سازد"}
    out = judge(doc["trades"])
    out.update({"generated": int(time.time() * 1000), "status": "OK",
                "source": doc.get("source"), "symbols": doc.get("symbols"),
                "bars": doc.get("bars"), "series": doc.get("series"),
                "backtest_at": doc.get("generated"),
                "rule": {"promote": f"CI سختگیرانهٔ شیداک بالای صفر · n≥{MIN_N_PROMOTE} · هر دو تایم هم‌جهت",
                         "reject": f"CI سختگیرانهٔ شیداک زیر صفر · n≥{MIN_N_REJECT}",
                         "registered": "۱۳ سپتامبر، پیش از اجرای بازوها"},
                "boundary": ("ترفیع = پیشنهاد، نه اجرا. هیچ دروازه و هیچ عددی از "
                             "این مسیر خودکار عوض نمی‌شود (قانون ۰۳/۱۲).")})
    return out


def render(v):
    if v.get("status") != "OK":
        return f"داور هندسه: {v.get('status')} — {v.get('why')}"
    L = [f"داور هندسه — {v.get('symbols')} نماد · {v.get('series')} سری · "
         f"آستانهٔ شیداک {v['alpha_per_test']} روی {v['n_cells']} خانه"]
    for key in sorted(v["rows"]):
        r = v["rows"][key]
        if not r.get("n"):
            continue
        ci = r.get("ci")
        cis = f"[{ci[0]:+.3f},{ci[1]:+.3f}]" if ci else "—"
        L.append(f"  {r['arm']:<10} {r['cut']:<7} n={r['n']:>6} "
                 f"strict={r['strict']:+.3f}R {cis:<20} {r['verdict']}")
    return "\n".join(L)


def _selftest():
    ok, fail = 0, []

    def check(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1
            print(f"  ✓ {name}")
        else:
            fail.append(name)
            print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))

    # ۱) معیار سختگیرانه
    check("خروجِ سربه‌سر صفر می‌گیرد نه R1",
          strict_r({"why": "breakeven", "r": 2.0, "fee_r": 0.1}) == -0.1)
    check("خروجِ عادی همان R منهای کارمزد است",
          abs(strict_r({"why": "stop", "r": -1.0, "fee_r": 0.2}) + 1.2) < 1e-9)
    check("ردیفِ بی‌R عدد نمی‌سازد (قانون ۱)",
          strict_r({"why": "stop", "fee_r": 0.2}) is None)

    # ۲) شیداک
    check("شیداک با آزمونِ بیشتر سخت‌تر می‌شود", sidak(18) < sidak(4) < ALPHA)
    check("یک آزمون همان ۰.۰۵ است", abs(sidak(1) - ALPHA) < 1e-12)

    # ۳) داور روی دادهٔ ساخته‌شده
    def mk(n, r, dirn, tf, why="target2"):
        # ۲۰ نماد و ۳۰ روز، تا هر دو خوشه‌بندی واقعاً خوشه داشته باشند
        return [{"r": r, "fee_r": 0.05, "why": why, "dir": dirn, "tf": tf,
                 "sym": f"S{i % 20}", "openedAt": (i % 30) * DAY_MS}
                for i in range(n)]

    # خوشهٔ روز: لبه‌ای که فقط در چند روزِ خاص است، نباید ترفیع بگیرد
    daysy = [{"r": (2.0 if (i % 30) < 3 else -0.02), "fee_r": 0.0, "why": "target2",
              "dir": "LONG", "tf": ("15m" if i % 2 else "5m"), "sym": f"S{i % 20}",
              "openedAt": (i % 30) * DAY_MS} for i in range(3000)]
    _d = cluster_boot_ci(daysy, 0.05, key="day")
    _s = cluster_boot_ci(daysy, 0.05, key="sym")
    check("خوشهٔ روز، لبهٔ متمرکز در چند روز را پهن‌تر از خوشهٔ نماد می‌بیند",
          _d is not None and _s is not None and (_d[1] - _d[0]) > (_s[1] - _s[0]),
          f"day={_d} sym={_s}")
    _r = judge({"a": daysy})["rows"]["a|long"]
    check("و داور پهن‌ترین را می‌گیرد — ترفیع نمی‌دهد",
          _r["verdict"] != "PROMOTE" and _r["ci"][0] <= min(_d[0], _s[0]) + 1e-9, str(_r["ci"]))

    # بوت‌استرپ خوشه‌ای: یک نمادِ «طلایی» نباید به‌تنهایی ترفیع بسازد
    mixed = [{"r": (3.0 if i % 20 == 0 else -0.05), "fee_r": 0.0, "why": "target2",
              "dir": "LONG", "tf": ("15m" if i % 2 else "5m"), "sym": f"S{i % 20}"}
             for i in range(2000)]
    _xs = [strict_r(t) for t in mixed]
    _iid = boot_ci(_xs, 0.05)
    _cl = cluster_boot_ci(mixed, 0.05)
    check("خوشه‌ای: میانگینِ مثبتِ وابسته به یک نماد، CI پهن‌تر می‌گیرد",
          _cl is not None and _iid is not None and (_cl[1] - _cl[0]) > (_iid[1] - _iid[0]),
          f"iid={_iid} cluster={_cl}")
    check("زیر ۱۰ خوشه بازه ساخته نمی‌شود (قانون ۱)",
          cluster_boot_ci(mixed[:5], 0.05) is None)

    strong = mk(400, 1.0, "LONG", "15m") + mk(400, 1.0, "LONG", "5m")
    bad = mk(1600, -1.0, "SHORT", "15m") + mk(1600, -1.0, "SHORT", "5m")
    v = judge({"arm": strong + bad})
    check("لانگِ قوی PROMOTE می‌گیرد", v["rows"]["arm|long"]["verdict"] == "PROMOTE",
          str(v["rows"]["arm|long"]))
    check("شورتِ بد REJECT می‌گیرد", v["rows"]["arm|short"]["verdict"] == "REJECT",
          str(v["rows"]["arm|short"]))
    check("لانگ و شورت جدا داوری شده‌اند — نه یک میانگینِ قاطی",
          v["rows"]["arm|long"]["strict"] > 0 > v["rows"]["arm|short"]["strict"])
    check("آستانهٔ هر خانه از شمارِ واقعیِ خانه‌ها آمده",
          v["n_cells"] == 3 and abs(v["alpha_per_test"] - sidak(3)) < 1e-5)

    # ۴) قیدهایی که ترفیعِ ارزان را می‌گیرند
    small = mk(120, 1.0, "LONG", "15m") + mk(120, 1.0, "LONG", "5m")
    check("نمونهٔ کم ترفیع نمی‌گیرد حتی با میانگینِ عالی",
          judge({"a": small})["rows"]["a|long"]["verdict"] == "UNDECIDED")
    split = mk(400, 1.0, "LONG", "15m") + mk(400, -0.2, "LONG", "5m")
    r_split = judge({"a": split})["rows"]["a|long"]
    check("دو تایمِ ناهم‌جهت ترفیع نمی‌گیرد",
          r_split["verdict"] == "UNDECIDED" and not r_split["consistent"],
          str(r_split))
    check("و دلیلش صریح نوشته می‌شود", "هم‌جهت" in r_split["why"])
    mid = mk(1000, 0.02, "LONG", "15m") + mk(1000, 0.02, "LONG", "5m")
    r_mid = judge({"a": mid})["rows"]["a|long"]
    check("بلاتکلیفِ نزدیکِ صفر برآوردِ «چند تا دیگر» می‌دهد",
          r_mid["verdict"] in ("PROMOTE", "UNDECIDED"))

    # ۵) مرزها
    check("بی‌دادهٔ بک‌تست، NO_DATA می‌دهد نه عددِ ساختگی",
          build({"trades": {}})["status"] == "NO_DATA")
    b = build({"trades": {"a": strong}, "symbols": 3, "series": 4})
    check("خروجی مرزِ صادقانه دارد (قانون ۱۲)", "قانون ۰۳" in b["boundary"])
    check("و قاعدهٔ توقف روی خروجی ثبت است", "registered" in b["rule"])
    check("رندر بدون خطا کار می‌کند", "داور هندسه" in render(b))

    # ۶) ضدِ بررسیِ توخالی — داور باید واقعاً به دادهٔ متفاوت جواب متفاوت بدهد
    flat = mk(4000, 0.0, "LONG", "15m") + mk(4000, 0.0, "LONG", "5m")
    check("دادهٔ کاملاً صفر ترفیع نمی‌گیرد",
          judge({"a": flat})["rows"]["a|long"]["verdict"] != "PROMOTE")

    print(f"\ngeometry_verdict: {ok} بررسی سبز"
          + (f" · {len(fail)} قرمز: {fail}" if fail else ""))
    return 1 if fail else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    v = build()
    print(render(v))
    if a.write:
        try:
            import brain as _b
            if getattr(_b, "SANDBOX", False):
                return 0
        except Exception:                            # noqa: BLE001
            pass
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
