"""داورِ برشِ رژیم — «بک‌فیل ۵د تا ۲۵۰ روز با برش رژیم» (دستور حمید، ۱۴ سپتامبر).

سؤال: لبهٔ `ibs` در روزهای صعودی و نزولی BTC **جدا** از صفر رد می‌شود یا
فقط سوارِ یک رژیمِ دوستانه است؟ (همان خطری که یک بار با پنجرهٔ تازگی
فریبمان داد.)

قاعدهٔ توقف — **از پیش ثبت‌شده، ۱۴ سپتامبر، پیش از دیدن هر عددی**:
  خانه = بازو (ibs/ibs_g2/ibs_g3) × تایم × رژیم (BULL/BEAR) × برش (کل/لانگ/شورت)
  آستانه = شیداک روی شمارِ واقعی خانه‌ها؛ CI = پهن‌ترینِ خوشهٔ نماد/روز
  PROMOTE   کران پایین CI > ۰ · n ≥ ۴۰۰ · روزهای خوشه ≥ MIN_DAYS
  REJECT    کران بالای CI < ۰ · n ≥ ۳۰۰۰
  UNDECIDED بقیه، با «چند روز/معامله دیگر»
  حکمِ استواری برای هر بازو×تایم:
    ROBUST    هر دو رژیم (برش کل) PROMOTE
    FRAGILE   یک رژیم کران پایین > ۰ و رژیم دیگر کران بالای CI < ۰
    UNDECIDED بقیه
  MIN_DAYS = ۱۰۰ نه ۱۵۰: پنجرهٔ ۲۵۰روزه بین دو رژیم تقسیم می‌شود (~۱۲۵ روز
  هر کدام)؛ با ۱۵۰ این آزمون به‌حکمِ ساختار هرگز تصمیم‌پذیر نمی‌شد. عددِ
  ثبت‌شده همین است و بعد از دیدن نتیجه عوض نمی‌شود.

رژیمِ هر روز از `report["regime"]["days"]` می‌آید (backtest.btc_regime_days:
کلوزِ دیروزِ BTC در برابر SMA20ِ قبلش — بی‌نگاه به آینده). روزِ بی‌برچسب
(پیش از گرم‌شدنِ SMA) از هر دو رژیم بیرون می‌ماند و شمرده می‌شود.

مرز: ترفیع = پیشنهاد، نه اجرا (قانون ۰۳/۱۲). هیچ دروازه‌ای از این مسیر
عوض نمی‌شود. عدد پیپر سقف خوش‌بینانه است (فیل کامل، بی‌لغزش).
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from hamid import geometry_verdict as GV

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "regime-verdict.json"

ARMS = ("ibs", "ibs_g2", "ibs_g3", "ibs_fill")
REGIMES = ("BULL", "BEAR")
CUTS = ("overall", "long", "short")
MIN_N_PROMOTE = 400
MIN_N_REJECT = 3000
MIN_DAYS = 100
RULE = {"promote": f"CI خوشه‌ای (شیداک) بالای صفر · n≥{MIN_N_PROMOTE} · روز≥{MIN_DAYS}",
        "reject": f"CI خوشه‌ای زیر صفر · n≥{MIN_N_REJECT}",
        "robust": "هر دو رژیم (برش کل) PROMOTE",
        "fragile": "یک رژیم کران پایین >۰ و دیگری کران بالا <۰",
        "registered": "۱۴ سپتامبر ۲۰۲۶، پیش از اجرای ۵د ۲۵۰روزه"}


def _date_of(t):
    """کلید روز به شکل YYYY-MM-DD (UTC) — همان کلیدی که backtest.btc_regime_days می‌نویسد."""
    a = t.get("openedAt")
    return time.strftime("%Y-%m-%d", time.gmtime(a / 1000)) if isinstance(a, (int, float)) else None


def _cell(trades, alpha):
    xs = [v for v in (GV.strict_r(t) for t in trades) if v is not None]
    if not xs:
        return {"n": 0, "verdict": "UNDECIDED", "why": "بی‌نمونه"}
    ci_sym = GV.cluster_boot_ci(trades, alpha, key="sym")
    ci_day = GV.cluster_boot_ci(trades, alpha, key="day")
    both = [c for c in (ci_sym, ci_day) if c]
    ci = (round(min(c[0] for c in both), 4), round(max(c[1] for c in both), 4)) if both else None
    n_days = len({GV._day_of(t) for t in trades})
    row = {"n": len(xs), "strict": round(statistics.fmean(xs), 4),
           "win": round(100 * sum(1 for t in trades if (t.get("r") or 0) > 0) / len(trades), 1),
           "ci": list(ci) if ci else None, "n_days": n_days,
           "n_symbols": len({t.get("sym") for t in trades}), "alpha": round(alpha, 5)}
    if ci and ci[0] > 0 and len(xs) >= MIN_N_PROMOTE and n_days >= MIN_DAYS:
        row["verdict"], row["why"] = "PROMOTE", f"CI [{ci[0]:+.3f},{ci[1]:+.3f}] بالای صفر · n={len(xs)} · {n_days} روز"
    elif ci and ci[1] < 0 and len(xs) >= MIN_N_REJECT:
        row["verdict"], row["why"] = "REJECT", f"CI [{ci[0]:+.3f},{ci[1]:+.3f}] زیر صفر · n={len(xs)}"
    else:
        row["verdict"] = "UNDECIDED"
        if ci and ci[0] > 0 and n_days < MIN_DAYS:
            row["why"] = f"CI بالای صفر ولی فقط {n_days} روز (کف {MIN_DAYS}) — پنجرهٔ بلندتر لازم است"
        elif ci is None:
            row["why"] = "خوشه‌های کافی برای CI نیست"
        else:
            row["why"] = f"CI [{ci[0]:+.3f},{ci[1]:+.3f}] صفر را در بر دارد"
    return row


def judge(by_arm, regime_days):
    """{بازو: [معامله]} + {روز: رژیم} → خانه‌ها + حکم استواری."""
    tfs = sorted({t.get("tf") for ts in by_arm.values() for t in ts if t.get("tf")})
    cells = [(a, tf, rg, c) for a in ARMS if a in by_arm for tf in tfs for rg in REGIMES for c in CUTS]
    alpha = GV.sidak(len(cells)) if cells else GV.ALPHA
    rows, unlabeled = {}, 0
    for arm in ARMS:
        if arm not in by_arm:
            continue
        ts = by_arm.get(arm) or []
        tagged = []
        for t in ts:
            rg = regime_days.get(_date_of(t))
            if rg is None:
                unlabeled += 1
                continue
            tagged.append((rg, t))
        for tf in tfs:
            for rg in REGIMES:
                base = [t for r_, t in tagged if r_ == rg and t.get("tf") == tf]
                for cut in CUTS:
                    sub = GV._slice(base, cut)
                    rows[f"{arm}|{tf}|{rg}|{cut}"] = {"arm": arm, "tf": tf, "regime": rg, "cut": cut, **_cell(sub, alpha)}
    robust = {}
    for arm in ARMS:
        if arm not in by_arm:
            continue
        for tf in tfs:
            b, r = rows.get(f"{arm}|{tf}|BULL|overall", {}), rows.get(f"{arm}|{tf}|BEAR|overall", {})
            cb, cr = b.get("ci"), r.get("ci")
            if b.get("verdict") == "PROMOTE" and r.get("verdict") == "PROMOTE":
                v, why = "ROBUST", "هر دو رژیم PROMOTE"
            elif cb and cr and ((cb[0] > 0 and cr[1] < 0) or (cr[0] > 0 and cb[1] < 0)):
                v, why = "FRAGILE", "لبه فقط در یک رژیم؛ در دیگری منفی"
            else:
                v, why = "UNDECIDED", "دست‌کم یک رژیم هنوز تصمیم‌پذیر نیست"
            robust[f"{arm}|{tf}"] = {"verdict": v, "why": why,
                                     "bull": {k: b.get(k) for k in ("n", "strict", "ci", "n_days", "verdict")},
                                     "bear": {k: r.get(k) for k in ("n", "strict", "ci", "n_days", "verdict")}}
    return {"alpha_per_test": round(alpha, 5), "n_cells": len(cells), "rows": rows,
            "robust": robust, "unlabeled_trades": unlabeled}


def build(doc=None):
    doc = doc or GV.latest_backtest()
    if not doc or not doc.get("trades"):
        return {"generated": int(time.time() * 1000), "status": "NO_DATA",
                "why": "هیچ بک‌تستی با ردیف معامله نیست"}
    rd = ((doc.get("regime") or {}).get("days")) or {}
    if not rd:
        return {"generated": int(time.time() * 1000), "status": "NO_REGIME",
                "why": "گزارش نقشهٔ رژیم ندارد (بک‌تست پیش از ۱۴ سپتامبر یا شکستِ کندل روزانه)",
                "backtest_at": doc.get("generated"), "file": doc.get("_file")}
    out = judge(doc["trades"], rd)
    out.update({"generated": int(time.time() * 1000), "status": "OK",
                "backtest_at": doc.get("generated"), "file": doc.get("_file"),
                "bars": doc.get("bars"), "symbols": doc.get("symbols"),
                "regime_rule": (doc.get("regime") or {}).get("rule"),
                "n_bull_days": (doc.get("regime") or {}).get("n_bull"),
                "n_bear_days": (doc.get("regime") or {}).get("n_bear"),
                "rule": RULE,
                "boundary": ("ترفیع = پیشنهاد، نه اجرا؛ هیچ دروازه‌ای از این مسیر خودکار عوض نمی‌شود "
                             "(قانون ۰۳/۱۲). عدد پیپر سقف خوش‌بینانه است.")})
    return out


def render(v):
    if v.get("status") != "OK":
        return f"داور رژیم: {v.get('status')} — {v.get('why')}"
    L = [f"داور رژیم — {v.get('symbols')} نماد · {v.get('n_bull_days')} روز BULL / {v.get('n_bear_days')} BEAR · "
         f"شیداک {v['alpha_per_test']} روی {v['n_cells']} خانه · {v['unlabeled_trades']} معاملهٔ بی‌برچسب"]
    for k, r in sorted(v["robust"].items()):
        b, e = r["bull"], r["bear"]
        L.append(f"  {k:<10} {r['verdict']:<9} BULL n={b.get('n') or 0:>6} {b.get('strict') if b.get('strict') is not None else 0:+.3f} {b.get('ci')}"
                 f"  BEAR n={e.get('n') or 0:>6} {e.get('strict') if e.get('strict') is not None else 0:+.3f} {e.get('ci')}")
    return "\n".join(L)


def write(v):
    try:
        import brain
        if getattr(brain, "SANDBOX", False):
            print("regime_verdict: sandbox — ننوشت")
            return False
    except Exception:                                # noqa: BLE001
        pass
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def _selftest():
    import random
    ok, fail = 0, []

    def check(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1
            print(f"  ✓ {name}")
        else:
            fail.append(name)
            print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))

    rnd = random.Random(7)
    day0 = 1_770_000_000_000
    days = 260
    regime = {time.strftime("%Y-%m-%d", time.gmtime((day0 + d * 86_400_000) / 1000)): ("BULL" if d % 2 == 0 else "BEAR")
              for d in range(days)}

    def trades(mean_bull, mean_bear, n_per_day=6, syms=40):
        out = []
        for d in range(days):
            rg = "BULL" if d % 2 == 0 else "BEAR"
            mu = mean_bull if rg == "BULL" else mean_bear
            for i in range(n_per_day):
                out.append({"sym": f"S{rnd.randrange(syms)}", "tf": "5m", "dir": rnd.choice(["LONG", "SHORT"]),
                            "r": rnd.gauss(mu, 0.9), "fee_r": 0.0, "why": "x",
                            "openedAt": day0 + d * 86_400_000 + i * 3_600_000})
        return out

    v = judge({"ibs": trades(+0.6, +0.6)}, regime)
    check("۶ خانه برای یک بازو × یک تایم × دو رژیم × سه برش (شیداک روی شمار واقعی)", v["n_cells"] == 6, str(v["n_cells"]))
    check("لبهٔ قوی در هر دو رژیم → ROBUST", v["robust"]["ibs|5m"]["verdict"] == "ROBUST", str(v["robust"]))
    v2 = judge({"ibs": trades(+0.7, -0.7)}, regime)
    check("لبه فقط در BULL و منفی در BEAR → FRAGILE", v2["robust"]["ibs|5m"]["verdict"] == "FRAGILE", str(v2["robust"]["ibs|5m"]))
    v3 = judge({"ibs": trades(0.02, 0.02)}, regime)
    check("نویز → UNDECIDED با CI شاملِ صفر", v3["robust"]["ibs|5m"]["verdict"] == "UNDECIDED"
          and "صفر" in v3["rows"]["ibs|5m|BULL|overall"]["why"], str(v3["rows"]["ibs|5m|BULL|overall"]))
    short = {k: v_ for k, v_ in list(regime.items())[:120]}   # فقط ۶۰ روز هر رژیم
    v4 = judge({"ibs": trades(+0.8, +0.8)}, short)
    r4 = v4["rows"]["ibs|5m|BULL|overall"]
    check("لبهٔ قوی ولی کمتر از ۱۰۰ روز → UNDECIDED با پیامِ «پنجرهٔ بلندتر»",
          r4["verdict"] == "UNDECIDED" and "روز" in r4["why"], str(r4))
    check("معاملهٔ روزِ بی‌برچسب شمرده و کنار گذاشته می‌شود", v4["unlabeled_trades"] > 0)
    check("بازوی غایب خانه نمی‌سازد", all(k.startswith("ibs|") for k in v["rows"]))
    check("build بی‌گزارش → NO_DATA", build({"trades": {}})["status"] == "NO_DATA")
    check("build با گزارشِ بی‌رژیم → NO_REGIME (نه حدس)",
          build({"trades": {"ibs": trades(0.5, 0.5)[:50]}})["status"] == "NO_REGIME")
    doc = {"trades": {"ibs": trades(0.6, 0.6)}, "regime": {"days": regime, "rule": "r", "n_bull": 130, "n_bear": 130},
           "symbols": 40, "generated": "t"}
    b = build(doc)
    check("build کامل: status OK + قاعدهٔ ثبت‌شده + مرز", b["status"] == "OK" and b["rule"]["registered"] and "پیشنهاد" in b["boundary"])
    check("رندر حکم استواری را چاپ می‌کند", "ROBUST" in render(b))
    check("قاعده از پیش ثبت‌شده و اعدادش ثابت است", MIN_DAYS == 100 and MIN_N_PROMOTE == 400 and MIN_N_REJECT == 3000)
    print(f"\nregime_verdict: {ok} بررسی سبز" + (f" — {len(fail)} افتاد: {fail}" if fail else ""))
    return 0 if not fail else 1


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
        write(v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
