#!/usr/bin/env python3
"""گزارش کامل روزانه — یک دستور، همهٔ اعدادی که حمید هر روز می‌خواهد.

دستور حمید (۱۹ اوت): «هر روز که پیام می‌دهم بلافاصله همهٔ گزارش‌ها را بده،
از پیپر تریدینگ تا نتیجه‌های برد و باخت و استفاده از تجربه.»

خروجی متن فارسی + `signals/daily-report.json`. همهٔ اعداد از دفترهای
واقعی خوانده می‌شوند؛ هیچ عددی ساخته نمی‌شود.

    python3 -m hamid.daily_report            # امروز
    python3 -m hamid.daily_report --days 3   # سه روز اخیر
"""
import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "signals" / "daily-report.json"
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OPEN = ROOT / "brain" / "paper" / "open.jsonl"

SIG_STAGES = ("signal", "sig-ibs", "sig-smc", "sig-alarm", "sig-pump-radar")


def rows(path):
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:                                # noqa: BLE001
                pass
    # منبع واحد کارمزد — نه `R_net` ذخیره‌شده (توضیح در `fees.apply_net`)
    try:
        from hamid import fees as _fees
        _fees.apply_net(out)
    except Exception:                                        # noqa: BLE001
        pass
    return out


def boot_ci(vals, n=2000, seed=11):
    if len(vals) < 8:
        return [None, None]
    r = random.Random(seed)
    m = []
    for _ in range(n):
        s = [vals[r.randrange(len(vals))] for _ in range(len(vals))]
        m.append(sum(s) / len(s))
    m.sort()
    return [round(m[int(0.025 * n)], 3), round(m[int(0.975 * n)], 3)]


def stat(name, trades):
    if not trades:
        return {"name": name, "n": 0}
    v = [(t.get("R_net") if t.get("R_net") is not None else t.get("R")) or 0
         for t in trades]
    w = sum(1 for t in trades if (t.get("R") or 0) > 0)
    lo, hi = boot_ci(v)
    return {"name": name, "n": len(trades),
            "win_pct": round(100 * w / len(trades), 1),
            "mean_r": round(sum(v) / len(v), 3), "sum_r": round(sum(v), 2),
            "ci95": [lo, hi], "positive": bool(lo is not None and lo > 0)}


def build(days=1, now_ms=None):
    now = now_ms or int(time.time() * 1000)
    since = now - days * 86400_000
    cl = rows(CLOSED)
    recent = [t for t in cl if (t.get("closed") or t.get("opened") or 0) >= since]

    def stage(t):
        return (t.get("why") or {}).get("stage") or "signal"

    by_stage = defaultdict(list)
    for t in cl:
        by_stage[stage(t)].append(t)
    by_stage_recent = defaultdict(list)
    for t in recent:
        by_stage_recent[stage(t)].append(t)

    siggrade = [t for t in cl if stage(t) in SIG_STAGES]
    exp_used = [t for t in cl if (t.get("why") or {}).get("exp_used")]
    exp_not = [t for t in cl if (t.get("why") or {}).get("exp_used") is False]

    def snap(p):
        try:
            return json.loads((ROOT / "signals" / p).read_text())
        except Exception:                                    # noqa: BLE001
            return {}

    dom = (snap("dominance.json").get("forecast") or {}).get("scoreboard", {})
    rew = (snap("rewards.json").get("engines") or {})
    link = snap("live-link.json")
    execs = snap("scalp-exec.json")

    return {
        "generated": now, "panel": "لیام تریدر ۹", "days": days,
        "totals": {"closed_all": len(cl), "closed_window": len(recent),
                   "open": len(rows(OPEN))},
        "signal_grade": stat("سیگنال‌گرید (مرجع)", siggrade),
        "signal_grade_window": stat("سیگنال‌گرید در بازه",
                                    [t for t in recent if stage(t) in SIG_STAGES]),
        "desks": [stat(k, v) for k, v in
                  sorted(by_stage.items(), key=lambda kv: -len(kv[1]))],
        "desks_window": [stat(k, v) for k, v in
                         sorted(by_stage_recent.items(),
                                key=lambda kv: -len(kv[1]))],
        "experience": {"used": stat("با تجربه", exp_used),
                       "not_used": stat("بدون تجربه", exp_not)},
        "dominance_forecast": dom,
        "engine_rewards": {k: v.get("points") for k, v in rew.items()},
        "live_link": {"events": len(link.get("events") or []),
                      "signed": link.get("signed"),
                      "last_kind": ((link.get("events") or [{}])[-1]
                                    .get("kind"))},
        "exec_bridge": {"mode": execs.get("mode"),
                        "sent": len(execs.get("sent") or []),
                        "skipped": len(execs.get("skipped") or [])},
    }


def render(d):
    L = []
    a = L.append
    a("📊 گزارش کامل لیام تریدر ۹ — "
      + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(d["generated"] / 1000)))
    t = d["totals"]
    a(f"دفتر: {t['closed_all']} معاملهٔ بسته ({t['closed_window']} در بازه) "
      f"· {t['open']} باز")
    s = d["signal_grade"]
    if s["n"]:
        a(f"\n🎯 سیگنال‌گرید: n={s['n']} · برد {s['win_pct']}٪ · "
          f"میانگین {s['mean_r']:+}R · CI {s['ci95']}"
          + ("  ✅ بالای صفر" if s["positive"] else ""))
    a("\n📚 دفترها:")
    for x in d["desks"]:
        if x["n"] >= 5:
            a(f"  {x['name']:14s} n={x['n']:5d} برد={x.get('win_pct')}٪ "
              f"میانگین={x.get('mean_r'):+.3f}R CI={x.get('ci95')}"
              + ("  ✅" if x.get("positive") else ""))
    e = d["experience"]
    if e["used"]["n"]:
        a(f"\n🧠 استفاده از تجربه: n={e['used']['n']} برد "
          f"{e['used']['win_pct']}٪ میانگین {e['used']['mean_r']:+}R  —  "
          f"بدون تجربه: n={e['not_used']['n']} برد "
          f"{e['not_used'].get('win_pct')}٪ میانگین "
          f"{e['not_used'].get('mean_r'):+}R")
    if d["dominance_forecast"]:
        a("\n🧭 پیش‌بینی دامیننس: " + " · ".join(
            f"{k} {v['hit_pct']}٪ (n={v['n']})"
            for k, v in d["dominance_forecast"].items()))
    if d["engine_rewards"]:
        top = sorted(d["engine_rewards"].items(), key=lambda kv: -(kv[1] or 0))[:5]
        a("🏅 جایزهٔ انجین‌ها: " + " · ".join(f"{k}={v}" for k, v in top))
    lk = d["live_link"]
    a(f"\n🔌 خط زنده: {lk['events']} رویداد · امضا "
      f"{'فعال' if lk['signed'] else 'خاموش'} · آخرین {lk['last_kind']}")
    ex = d["exec_bridge"]
    if ex.get("mode"):
        a(f"⚡ پل اجرا ({ex['mode']}): {ex['sent']} سفارش فرستاده، "
          f"{ex['skipped']} ستاپ رد شد")
    return "\n".join(L)


def run(days=1, quiet=False):
    d = build(days=days)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    text = render(d)
    if not quiet:
        print(text)
    return d, text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    a = ap.parse_args()
    run(days=a.days)
