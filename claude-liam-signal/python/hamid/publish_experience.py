#!/usr/bin/env python3
"""انتشار کارنامهٔ تجربه برای مصرف بیرونی (داشبورد) — دستور حمید ۱۹ اوت.

اندازه‌گیری‌شده روی دفتر سیگنال‌گرید (۱۹ اوت): معامله‌هایی که تجربهٔ همان
(ارز، جهت) پشتشان بود n=۱۳۷ · برد ۸۶.۹٪ · میانگین +۰.۳۱۹R، در برابر بدون
تجربه n=۲۵۷ · ۶۷.۷٪ · +۰.۰۰۸R. قوی‌ترین عامل با نمونهٔ کافی است، پس باید
بیرون از این ریپو هم در دسترس باشد — داشبورد بدون آن نصفِ لبه را از دست
می‌دهد.

خروجی `signals/experience.json`:
    {"generated":…, "min_n":12,
     "index": {"BTCUSDT|LONG": {"n":36,"win_pct":41.7,"mean_r":0.75,
                                "thin":false}, …},
     "summary": {"pairs":…, "usable":…}}

«usable» یعنی n ≥ min_n (تاریخچهٔ نازک حق وتو ندارد — همان قانون
paper.experience_index).
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "signals" / "experience.json"
MIN_N = 12


def build(min_n=MIN_N):
    from hamid import paper
    idx = paper.experience_index(min_n=min_n)
    out = {}
    for (sym, d), v in idx.items():
        out[f"{sym}|{d}"] = {"n": v["n"], "win_pct": v["win_pct"],
                             "mean_r": v["mean_r"], "thin": v["thin"]}
    usable = sum(1 for v in out.values() if not v["thin"])
    return {"generated": int(time.time() * 1000),
            "panel": "لیام تریدر ۹", "min_n": min_n,
            "note": ("کارنامهٔ بستهٔ هر (ارز، جهت) از دفتر سیگنال‌گرید؛ "
                     "thin=true یعنی نمونه کم است و حق وتو ندارد"),
            "index": out,
            "summary": {"pairs": len(out), "usable": usable}}


def run(quiet=False, out=None):
    d = build()
    p = Path(out) if out else OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False))
    if not quiet:
        print(f"کارنامهٔ تجربه: {d['summary']['pairs']} جفت "
              f"({d['summary']['usable']} قابل‌استناد) → {p}")
    return d


if __name__ == "__main__":
    run()
