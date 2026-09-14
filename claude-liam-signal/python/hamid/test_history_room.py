"""آزمون آفلاین اتاق تمرین تاریخی — هیچ عددی جعل نمی‌شود.

  ۱. با فایل‌های واقعی‌شکل: اعداد عیناً از همان فایل‌ها می‌آیند.
  ۲. فایلِ غایب: بخش absent با دلیل — نه عدد ساختگی، نه استثنا.
  ۳. مانیفست ۵د: فقط DONEها شمرده می‌شوند.
  ۴. شکاف خبر تاریخی همیشه صریح اعلام می‌شود (قانون ۱۲ — مرز صادقانه).

    python3 -m hamid.test_history_room
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import history_room as hr                 # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="hroom-"))
for name in ("INVENTORY", "BT3Y", "BT3Y_WIDE", "NIGHTLY", "MANIFEST_5M", "OUT"):
    setattr(hr, name, TMP / f"{name}.json")

FAIL = 0


def check(n, ok, txt):
    global FAIL
    print(f"{n} {'✅' if ok else '❌'} {txt}")
    if not ok:
        FAIL += 1


# ۲ اول: همه‌چیز غایب → absent با دلیل، بدون استثنا
room = hr.build()
check("۱", all("absent" in room[k] for k in
               ("bundle_15m", "replay_3y", "nightly", "bundle_5m")),
      "فایل غایب → «ندارد» با دلیل، نه عدد ساختگی")
check("۲", any("خبرِ تاریخی" in g for g in room["gaps"])
      and room["panel"] == "لیام تریدر ۹",
      "شکاف خبر تاریخی صریح است + امضای پنل")

# ۱: با فایل‌های واقعی‌شکل
hr.INVENTORY.write_text(json.dumps({
    "summary": {"klines_ok": 298, "total_bytes": 545_389_152,
                "meta_files": 10},
    "validation_status": "UNVERIFIED", "retrieved_at": "2026-08-26"}))
hr.BT3Y.write_text(json.dumps({
    "engine": "liam9 v2.8", "tf": "15m", "symbols": 296,
    "trade_span": ["2023-10-01", "2026-08-25"],
    "overall": {"n": 153_971, "mean_r_net": -0.097,
                "ci95": [-0.104, -0.089], "win_pct": 33.7}}))
hr.BT3Y_WIDE.write_text(json.dumps(
    {"overall": {"n": 94_969, "mean_r_net": -0.046,
                 "ci95": [-0.058, -0.036], "win_pct": 26.0}}))
hr.NIGHTLY.write_text(json.dumps({
    "generated": "2026-09-14 16:40 UTC", "trades": 26_785,
    "source": "real klines replay",
    "stats": {"BTCUSDT|LONG": {}, "ETHUSDT|SHORT": {}}}))
hr.MANIFEST_5M.write_text(json.dumps({
    "target_days": 730, "updated": 5,
    "symbols": {"A": {"status": "DONE", "rows": 100},
                "B": {"status": "DONE", "rows": 50},
                "C": {"status": "FAILED"},
                "D": {"status": "PENDING"}}}))

room = hr.build()
check("۳", room["bundle_15m"]["symbols_ok"] == 298
      and room["replay_3y"]["overall"]["n"] == 153_971
      and room["replay_3y"]["rr3wide"]["ci95"] == [-0.058, -0.036]
      and room["nightly"]["trades"] == 26_785
      and room["nightly"]["pairs"] == 2,
      "اعداد عیناً از فایل‌های منبع آمدند")
check("۴", room["bundle_5m"]["done"] == 2 and room["bundle_5m"]["total"] == 4
      and room["bundle_5m"]["rows"] == 150,
      "۵د: فقط DONEها شمرده شدند (۲ از ۴)")

print()
if FAIL:
    print(f"{FAIL} آزمون شکست")
    sys.exit(1)
print("همهٔ ۴ آزمون اتاق تمرین تاریخی گذشت")
