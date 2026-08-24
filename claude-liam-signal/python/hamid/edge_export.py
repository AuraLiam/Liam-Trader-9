"""انتقال مهارت به داشبورد — فقط چیزی که CI از صفر رد کرده.

دستور حمید (۲۴ اوت): «از بهترین نتایج یک کد پایتون بساز و برو سمت
تأثیرگذاری و انتقال مهارت از این‌جا به داشبورد برای استفاده در ترید.»

## شکافی که این فایل می‌بندد

بک‌تست شبانه هر صبح روی کندل واقعی قانون‌ها را دوباره می‌سنجد و
`scan.confirmed_rules` فقط آن‌هایی را که بازهٔ اطمینانشان صفر را رد کرده
به کار می‌گیرد — ولی **فقط روی رانر**. فایل داشبورد (`liam9_strategy.py`
که حمید در داشبورد می‌گذارد) از این یادگیری بی‌خبر بود: پارامتر و تجربه
و لایهٔ نقدشوندگی را sync می‌کرد، قانون‌های تأییدشده را نه.

این فایل «قفسهٔ لبه» را می‌سازد: `signals/edge.json`. داشبورد آن را
مثل بقیهٔ syncها می‌کشد و همان دلتاهای اندازه‌گیری‌شده را روی امتیازش
اعمال می‌کند.

## تعریف «بهترین نتایج» — عمداً تنگ

فقط قانونی صادر می‌شود که:
  ۱. از بک‌تست شبانهٔ کندل واقعی آمده باشد (نه شبیه‌ساز، نه حس)،
  ۲. بازهٔ اطمینان بوت‌استرپش کاملاً بالای صفر یا کاملاً زیر صفر باشد،
  ۳. شناسنامه داشته باشد: n، CI، دلتا، تاریخ سنجش.

قانونِ منفی هم صادر می‌شود — «شورت هم‌سو با بیت‌کوین −۰.۵۵R» همان‌قدر
مهارت است که قانون مثبت؛ حذفش یعنی فقط خبرهای خوش منتقل شوند.

هر چیز دیگری — سرنخ، حدس، نتیجهٔ CI-نگذشته — صادر **نمی‌شود**. قفسهٔ
خالی از قفسهٔ آلوده بهتر است (قانون ۰۳).

## کهنگی

بک‌تستی که از STALE_H گذشته باشد دیگر «امروزِ بازار» نیست؛ خروجی با
`stale=true` علامت می‌خورد و داشبورد آن را نادیده می‌گیرد — قانونی که
تِیپ دیگر پاداشش نمی‌دهد، صبح بعد صندلی‌اش را از دست داده و نسخهٔ کهنه
نباید جایش بنشیند.

اجرا:  python3 -m hamid.edge_export
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
BACKTEST = ROOT / "brain" / "backtests" / "latest.json"
OUT = ROOT / "signals" / "edge.json"

STALE_H = 48


def confirmed(bt):
    """قانون‌های CI-گذشته، با شناسنامهٔ کامل. همان فیلتر scan.confirmed_rules
    — این‌جا دوباره نوشته نشده که واگرا شود؛ آزمون هم‌ارزی‌شان را می‌سنجد."""
    out = {}
    for strat, rs in (bt.get("reasons") or {}).items():
        keep = []
        for r in rs:
            ci = r.get("ci")
            if not ci or not (ci[0] > 0 or ci[1] < 0):
                continue                    # صفر داخل بازه = صادر نمی‌شود
            if r.get("delta") is None or not r.get("n"):
                continue                    # بی‌شناسنامه = صادر نمی‌شود
            keep.append({"condition": r.get("condition"),
                         "delta": r["delta"], "ci": ci, "n": r["n"]})
        if keep:
            out[strat] = keep
    return out


def _to_ms(v):
    """مهر زمان بک‌تست: عددی (ms) یا متنی «YYYY-MM-DD HH:MM UTC». ناخوانا = 0
    — و صفر یعنی stale، پس فرمتِ ناشناخته هرگز قانونِ کهنه را تازه جا نمی‌زند."""
    if isinstance(v, (int, float)) and v > 0:
        return int(v)
    if isinstance(v, str):
        try:
            return int(time.mktime(time.strptime(v.replace(" UTC", ""),
                                                 "%Y-%m-%d %H:%M"))
                       - time.timezone) * 1000
        except ValueError:
            return 0
    return 0


def build(bt=None, now_ms=None):
    now = now_ms or int(time.time() * 1000)
    if bt is None:
        try:
            bt = json.loads(BACKTEST.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            bt = {}
    measured_at = _to_ms(bt.get("generated"))
    age_h = (now - measured_at) / 3_600_000 if measured_at else None
    rules = confirmed(bt)
    return {
        "generated": now,
        "panel": "لیام تریدر ۹",
        "source": "python/backtest.py — بک‌تست شبانه روی کندل واقعی",
        "measured_at": measured_at,
        "age_h": round(age_h, 1) if age_h is not None else None,
        "stale": age_h is None or age_h > STALE_H,
        "n_rules": sum(len(v) for v in rules.values()),
        "rules": rules,
        "boundary": ("فقط قانون با CI ردشده از صفر. دلتاها وزن امتیازند، "
                     "وتو نیستند؛ دروازه‌های سخت داشبورد سرِ جایشان‌اند. "
                     "stale=true یعنی نادیده بگیر."),
    }


def run(quiet=False):
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    if not quiet:
        flag = " (کهنه — داشبورد نادیده می‌گیرد)" if doc["stale"] else ""
        print(f"قفسهٔ لبه: {doc['n_rules']} قانون CI-گذشته{flag}")
        for strat, rs in doc["rules"].items():
            for r in rs:
                print(f"  {strat}: {r['condition']} → {r['delta']:+}R "
                      f"CI {r['ci']} · n={r['n']}")
    return doc


if __name__ == "__main__":
    run()
