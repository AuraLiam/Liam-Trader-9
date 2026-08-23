"""کارنامهٔ اسکلپ — عدد قابل‌تولید مجدد از دفتر پیپر.

## چه چیزی را می‌سنجد و چه چیزی را نه

دفتر `brain/paper/closed.jsonl` دفترهای چند میز را کنار هم نگه می‌دارد
(`why.stage`: scalp · shock · practice · first · second · alarm · …) و
قاطی کردنشان عدد را بی‌معنا می‌کند (قانون ۹: هر دفتر آمار جدا). این
گزارش فقط `stage="scalp"` را می‌گیرد.

**`replay: 1` روی این دفتر بک‌تستِ تاریخی نیست.** میز اسکلپ عمداً
ریپلیِ رو به جلو روی کندل واقعی ۱ دقیقه است: مرزِ پیشرونده
(`scalp-state.json`) نگه می‌دارد هر کندل فقط **یک بار** ارزیابی شود،
تصمیم روی `cd[:i+1]` گرفته می‌شود و نتیجه از کندل‌های بعد شبیه‌سازی —
یعنی walk-forward بدون نگاه به آینده، نه بهینه‌سازی روی گذشته. پس عدد
این دفتر عددِ پیپر است، با همان مرزهای پیپر.

## مرزهای صادقانه

- این پیپر است، نه پول واقعی. عدد پیپر سقفِ خوش‌بینانه است: فرض فیل
  کامل و بدون لغزشِ اضافه (قانون آستانهٔ پول واقعی، بند ۵).
- `R_net` کارمزد را کسر کرده؛ `R` نکرده. هر ادعایی باید روی `R_net`
  باشد وگرنه کارمزد را نادیده گرفته‌ایم.
- حکم فقط از **بازهٔ اطمینان بوت‌استرپ** می‌آید. میانگینِ تنها، بدون CI،
  تصمیم‌ساز نیست (قانون CI).
- نتیجهٔ `trail` برد نیست: خروجِ استاپ‌درسود است. جدا شمرده می‌شود چون
  قاطی کردنش با `target` نرخ برد را بی‌دلیل باد می‌کند.

اجرا:  python3 -m hamid.scalp_report                 (میز اسکلپ، ۱ دقیقه)
       python3 -m hamid.scalp_report --days 2
       python3 -m hamid.scalp_report --stage shock --tf 5m
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEDGER = ROOT / "brain" / "paper" / "closed.jsonl"
MIN_N = 30                     # کف نمونه برای گزارش CI


def load(tf="1m", stage="scalp", ledger=None):
    """معامله‌های بستهٔ یک میز و یک تایم‌فریم.

    فیلتر روی `why.stage` است نه تایم‌فریم تنها: چند میز می‌توانند روی
    یک تایم بنویسند و قانون ۹ آمارشان را جدا می‌خواهد."""
    p = Path(ledger) if ledger else LEDGER
    out = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if tf and r.get("tf") != tf:
            continue
        why = r.get("why") if isinstance(r.get("why"), dict) else {}
        if stage and why.get("stage") != stage:
            continue
        out.append(r)
    out.sort(key=lambda r: r.get("opened") or 0)
    return out


def boot_ci(xs, n_boot=3000, seed=7, alpha=0.05):
    """CI درصدیِ بوت‌استرپ روی میانگین — همان روش بقیهٔ سنجه‌ها."""
    if len(xs) < 2:
        return None, None
    rnd = random.Random(seed)
    n = len(xs)
    means = sorted(sum(xs[rnd.randrange(n)] for _ in range(n)) / n
                   for _ in range(n_boot))
    return (means[int(alpha / 2 * n_boot)],
            means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))])


def summarize(rows, min_n=MIN_N):
    """آمار یک مجموعه معامله. بدون CI اگر نمونه کم باشد."""
    if not rows:
        return {"n": 0, "verdict": "هیچ معامله‌ای در این دسته نیست"}
    net = [r.get("R_net", 0.0) for r in rows]
    gross = [r.get("R", 0.0) for r in rows]
    fees = [r.get("fee_r", 0.0) for r in rows]
    oc = {}
    for r in rows:
        oc[r.get("outcome", "?")] = oc.get(r.get("outcome", "?"), 0) + 1
    n = len(rows)
    mean_net = sum(net) / n
    lo, hi = boot_ci(net) if n >= min_n else (None, None)
    wins = sum(1 for x in net if x > 0)
    res = {
        "n": n,
        "from": rows[0].get("opened"), "to": rows[-1].get("opened"),
        "outcomes": oc,
        "R_gross_mean": round(sum(gross) / n, 4),
        "fee_R_mean": round(sum(fees) / n, 4),
        "R_net_mean": round(mean_net, 4),
        "ci95": [round(lo, 4), round(hi, 4)] if lo is not None else None,
        # «برد» = R خالص مثبت. target و trail جدا شمرده می‌شوند چون
        # trail خروجِ استاپ‌درسود است نه رسیدن به هدف.
        "win_rate_net": round(wins / n * 100, 1),
        "target_rate": round(oc.get("target", 0) / n * 100, 1),
        "trail_rate": round(oc.get("trail", 0) / n * 100, 1),
        "stop_rate": round(oc.get("stop", 0) / n * 100, 1),
        "total_R_net": round(sum(net), 2),
    }
    if n < min_n:
        res["verdict"] = f"نمونه کم است ({n} < {min_n}) — CI گزارش نمی‌شود"
    elif lo > 0:
        res["verdict"] = (f"لبهٔ مثبت: CI کاملاً بالای صفر "
                          f"[{lo:+.4f}, {hi:+.4f}]R")
    elif hi < 0:
        res["verdict"] = (f"لبهٔ منفی — این پیکربندی ضرر می‌دهد: CI کاملاً "
                          f"زیر صفر [{lo:+.4f}, {hi:+.4f}]R")
    else:
        res["verdict"] = (f"بی‌نتیجه: CI صفر را در بر می‌گیرد "
                          f"[{lo:+.4f}, {hi:+.4f}]R — نه لبه‌ای اثبات شد "
                          f"نه ردی")
    return res


def by_key(rows, keyfn, min_n=MIN_N, top=8):
    """تفکیک بر اساس یک کلید (نماد، جهت، ...) — فقط دسته‌های به‌اندازه."""
    buckets = {}
    for r in rows:
        buckets.setdefault(keyfn(r), []).append(r)
    out = []
    for k, v in buckets.items():
        if len(v) < min_n:
            continue
        s = summarize(v, min_n)
        out.append({"key": k, "n": s["n"], "R_net_mean": s["R_net_mean"],
                    "ci95": s["ci95"], "win_rate_net": s["win_rate_net"]})
    out.sort(key=lambda x: -x["R_net_mean"])
    return out[:top], len(buckets)


def fmt_t(ms):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ms / 1000)) if ms else "?"


def run(tf="1m", stage="scalp", quiet=False, ledger=None, recent_days=None):
    rows = load(tf, stage, ledger)
    if recent_days and rows:
        cut = max(r["opened"] for r in rows) - recent_days * 86400000
        rows = [r for r in rows if r.get("opened", 0) >= cut]
    res = summarize(rows)
    res["tf"] = tf
    res["book"] = f"paper/{stage}"
    res["by_symbol"], res["symbols_total"] = by_key(rows, lambda r: r.get("sym", "?"))
    res["by_dir"], _ = by_key(rows, lambda r: r.get("dir", "?"))
    if not quiet:
        print(f"دفتر: {res['book']} · تایم: {tf} · معامله: {res['n']}")
        if res["n"]:
            print(f"بازه: {fmt_t(res['from'])} → {fmt_t(res['to'])} UTC")
            print(f"نتیجه‌ها: {res['outcomes']}")
            print()
            print(f"  R ناخالص  {res['R_gross_mean']:+.4f}")
            print(f"  کارمزد    {res['fee_R_mean']:+.4f}   ← سهم کارمزد از R")
            print(f"  R خالص    {res['R_net_mean']:+.4f}   CI95 {res['ci95']}")
            print(f"  مجموع R خالص: {res['total_R_net']:+.2f}")
            print()
            print(f"  برد خالص {res['win_rate_net']}% · تارگت "
                  f"{res['target_rate']}% · تریل {res['trail_rate']}% · "
                  f"استاپ {res['stop_rate']}%")
            print()
            print(f"حکم: {res['verdict']}")
            if res["by_dir"]:
                print("\nبه تفکیک جهت:")
                for d in res["by_dir"]:
                    print(f"  {d['key']:<6} n={d['n']:<5} R={d['R_net_mean']:+.4f} "
                          f"CI={d['ci95']}")
            if res["by_symbol"]:
                print(f"\nبهترین نمادها (از {res['symbols_total']}، فقط n≥{MIN_N}):")
                for d in res["by_symbol"]:
                    print(f"  {d['key']:<12} n={d['n']:<5} R={d['R_net_mean']:+.4f} "
                          f"CI={d['ci95']}")
        else:
            print(res["verdict"])
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1m")
    ap.add_argument("--stage", default="scalp")
    ap.add_argument("--days", type=int, default=None)
    a = ap.parse_args()
    run(tf=a.tf, stage=a.stage, recent_days=a.days)
    sys.exit(0)
