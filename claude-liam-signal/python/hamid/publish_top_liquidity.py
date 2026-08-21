#!/usr/bin/env python3
"""انتشار لایهٔ نقدشوندگی برتر ۶۰ برای مصرف بیرونی (داشبورد) — دستور
حمید ۲۱ اوت («خب همینو استراتژی کن»).

اندازه‌گیری‌شده روی dash-backtest واقعی (۲۱ اوت، کندل واقعی، بدون نگاه
به آینده): لایهٔ top60 n=145، میانگین +۰.۴۳۶R خالص، CI۹۵
[+۰.۱۹۹, +۰.۶۶۹] — کاملاً بالای صفر. رتبهٔ ۶۱+ n=107، CI [−۰.۱۹۹, +۰.۳۲۱]
هنوز صفر داخلش است، یعنی لبهٔ اثبات‌شده ندارد. تا سنجش تازه خلافش را نشان
بدهد، liam9_strategy.analyze() فقط برای نمادهای همین لایه سیگنال می‌دهد
(sync_top_liquidity در liam9_strategy.py).

منبع رتبه‌بندی همان hamid.trainer.top_symbols است: ۲۴ساعتهٔ حجم نقل‌شده،
استیبل/تکراری حذف — دقیقاً همان تابعی که dash_backtest.py برای رتبه‌دهی
تِیرها استفاده می‌کند، تا رتبهٔ زنده با رتبهٔ سنجیده‌شده یکی بماند.

خروجی `signals/top-liquidity.json`:
    {"generated":…, "panel":"لیام تریدر ۹", "n":60,
     "symbols": ["BTCUSDT", "ETHUSDT", …],
     "source_finding": "dash-backtest 21 Aug: top60 CI[+0.199,+0.669]"}
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "signals" / "top-liquidity.json"
N = 60


def build(n=N):
    try:
        import sources
        syms = sources.top_symbols(n)
    except Exception:                                 # noqa: BLE001
        from hamid.trainer import top_symbols
        syms = top_symbols(n)
    return {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
            "n": len(syms), "symbols": syms,
            "source_finding": ("dash-backtest ۲۱ اوت: top60 n=145 "
                               "CI[+0.199,+0.669]، رتبهٔ ۶۱+ n=107 "
                               "CI[-0.199,+0.321] هنوز صفر داخلش")}


def run(quiet=False, out=None):
    d = build()
    p = Path(out) if out else OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False))
    if not quiet:
        print(f"لایهٔ نقدشوندگی: {d['n']} نماد → {p}")
    return d


if __name__ == "__main__":
    run()
