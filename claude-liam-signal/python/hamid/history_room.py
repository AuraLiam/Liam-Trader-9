"""اتاق تمرین تاریخی — تابلوی صادقانهٔ داده و بازپخش (دستور حمید، ۱۴ سپتامبر).

حمید کارت «تمرین تاریخی و حافظهٔ پایدار» را خواست. قانون عددِ درست
(۵ سپتامبر): هیچ عددی ساخته نمی‌شود — این ماژول فقط از فایل‌های موجود
می‌خواند و هرچه نیست را صریح «ندارد» اعلام می‌کند:

  bundle_15m   ← brain/research/history/inventory.json  (بستهٔ درایو حمید)
  replay_3y    ← brain/research/history/backtest3y.json + rr3wide
  nightly      ← brain/history-stats.json               (تمرین شبانه)
  bundle_5m    ← brain/research/history/5m-manifest.json (جمع‌آوری تدریجی)
  gaps         ← لایه‌هایی که واقعاً نداریم (خبر تاریخی با زمان دسترسی)

خروجی: signals/history-room.json (ردیف قرارداد قانون ۱۳، مالک E13).
فقط می‌خواند و خروجی خودش را می‌نویسد (قانون ۰۵ — یک نویسنده).

اجرا:  python3 -m hamid.history_room --write
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
HIST = ROOT / "brain" / "research" / "history"
INVENTORY = HIST / "inventory.json"
BT3Y = HIST / "backtest3y.json"
BT3Y_WIDE = HIST / "backtest3y_rr3wide.json"
NIGHTLY = ROOT / "brain" / "history-stats.json"
MANIFEST_5M = HIST / "5m-manifest.json"
OUT = ROOT / "signals" / "history-room.json"


def _load(p):
    try:
        return json.loads(p.read_text())
    except Exception:                                # noqa: BLE001
        return None


def _overall(bt):
    o = (bt or {}).get("overall") or {}
    if not o:
        return None
    return {"n": o.get("n"), "mean_r_net": o.get("mean_r_net"),
            "ci95": o.get("ci95"), "win_pct": o.get("win_pct")}


def build():
    """تابلو را از روی دیسک می‌سازد — هر بخشِ غایب، دلیلِ غیبت دارد."""
    inv = _load(INVENTORY)
    bt = _load(BT3Y)
    wide = _load(BT3Y_WIDE)
    night = _load(NIGHTLY)
    m5 = _load(MANIFEST_5M)

    if inv:
        s = inv.get("summary") or {}
        bundle15 = {"symbols_ok": s.get("klines_ok"),
                    "total_bytes": s.get("total_bytes"),
                    "meta_files": s.get("meta_files"),
                    "validation": inv.get("validation_status"),
                    "retrieved_at": inv.get("retrieved_at")}
    else:
        bundle15 = {"absent": "inventory.json نیست — history-ingest اجرا نشده"}

    if bt:
        replay = {"engine": bt.get("engine"), "tf": bt.get("tf"),
                  "symbols": bt.get("symbols"),
                  "trade_span": bt.get("trade_span"),
                  "overall": _overall(bt),
                  "rr3wide": _overall(wide)}
    else:
        replay = {"absent": "backtest3y.json نیست — بازپخش چندساله اجرا نشده"}

    if night and isinstance(night.get("stats"), dict):
        nightly = {"generated": night.get("generated"),
                   "trades": night.get("trades"),
                   "pairs": len(night["stats"]),
                   "source": night.get("source")}
    else:
        nightly = {"absent": "history-stats.json نیست — بک‌تست شبانه اجرا نشده"}

    if m5 and isinstance(m5.get("symbols"), dict):
        syms = m5["symbols"]
        done = [v for v in syms.values() if v.get("status") == "DONE"]
        rows = sum(v.get("rows") or 0 for v in done)
        bundle5 = {"total": len(syms), "done": len(done), "rows": rows,
                   "target_days": m5.get("target_days"),
                   "updated": m5.get("updated")}
    else:
        bundle5 = {"absent": "جمع‌آوری ۵د هنوز شروع نشده — ورک‌فلوی candles-5m"}

    return {
        "generated": int(time.time() * 1000),
        "panel": "لیام تریدر ۹",
        "bundle_15m": bundle15,
        "replay_3y": replay,
        "nightly": nightly,
        "bundle_5m": bundle5,
        # مرز صادقانه (قانون ۱۲): چیزی که نداریم، «ندارد» می‌ماند — جعل نمی‌شود.
        "gaps": ["خبرِ تاریخی با زمان دسترسی واقعی — منبعی نداریم؛ "
                 "دامیننس/فاندینگ/فهرست ارز همان دوره در متای بسته هست"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    room = build()
    txt = json.dumps(room, ensure_ascii=False, indent=1)
    if a.write:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(txt)
        print(f"اتاق تمرین تاریخی نوشته شد: {OUT.name}")
    else:
        print(txt)


if __name__ == "__main__":
    main()
