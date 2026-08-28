"""پاسبان دفتر تلگرام روی پنل (دستور حمید، ۲۸ اوت).

«اطلاعاتی که از تلگرام داری می‌فرستی روی پنل هم باشه.»

خطرها: دفتری که فقط سیگنال را ثبت کند (وضع قبلی)، دفتری که بی‌سقف رشد
کند، آرشیوی که شماره نداشته باشد (نقض قانون ضد-merge)، و کلاسِ عیب:
ماژول تازه‌ای که به تلگرام بفرستد و ردی روی پنل نگذارد.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

import telegram as tg                                 # noqa: E402

OK = 0
FAIL = []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}")
        if extra:
            print(f"      ↳ {extra}")


TMP = Path(tempfile.mkdtemp(prefix="tgfeed-"))
old_feed, old_arch, old_cap = tg.FEED, tg.ARCHIVE_DIR, tg.FEED_CAP
tg.FEED = TMP / "telegram-feed.json"
tg.ARCHIVE_DIR = TMP / "archive"
try:
    r = tg.record_out("signal", "BTCUSDT 15m LONG",
                      {"entry": 1.5, "sl": 1.4, "tp1": 1.8}, 4242)
    check("ردیف با زمان/نوع/عنوان ساخته می‌شود",
          r["kind"] == "signal" and r["at"] > 0 and r["msg_id"] == 4242)
    j = json.loads(tg.FEED.read_text())
    check("دفتر پنل نوشته شد", len(j["rows"]) == 1 and j.get("generated"))
    check("عددهای سیگنال داخل ردیف‌اند", j["rows"][0]["extra"]["entry"] == 1.5)

    tg.record_out("dom_report", "نظریهٔ ساعتی دامیننس")
    tg.record_out("work_report", "گزارش کار")
    tg.record_out("pump_report", "گزارش پامپ — ۳ نامزد", {"n": 3})
    tg.record_out("outcome", "BTCUSDT target", {"r": 1.5})
    j = json.loads(tg.FEED.read_text())
    kinds = {x["kind"] for x in j["rows"]}
    check("هر پنج نوع پیام ثبت می‌شود، نه فقط سیگنال",
          kinds == {"signal", "dom_report", "work_report", "pump_report",
                    "outcome"}, str(sorted(kinds)))

    # آرشیو شماره‌دار append-only (قانون ضد-merge)
    files = list((TMP / "archive").glob("telegram-feed-*.jsonl"))
    check("آرشیو شماره‌دار روزانه ساخته شد", len(files) == 1, str(files))
    lines = [json.loads(x) for x in files[0].read_text().splitlines()]
    check("شماره‌ها پیاپی‌اند (۱..۵)", [x["n"] for x in lines] == [1, 2, 3, 4, 5],
          str([x["n"] for x in lines]))

    # سقف حلقه
    tg.FEED_CAP = 3
    tg.record_out("signal", "X")
    j = json.loads(tg.FEED.read_text())
    check("دفتر پنل سقف دارد و بی‌نهایت رشد نمی‌کند", len(j["rows"]) == 3,
          str(len(j["rows"])))

    # خطای نوشتن نباید ارسال را بکشد
    tg.FEED = TMP / "no-such-dir" / "deep" / "x.json"
    tg.ARCHIVE_DIR = Path("/proc/nope")
    try:
        tg.record_out("signal", "بدون مقصد")
        check("خطای دفتر، ارسال را نمی‌کشد", True)
    except Exception as e:                            # noqa: BLE001
        check("خطای دفتر، ارسال را نمی‌کشد", False, repr(e))
finally:
    tg.FEED, tg.ARCHIVE_DIR, tg.FEED_CAP = old_feed, old_arch, old_cap

# ── کلاسِ عیب: هر فرستنده باید ردِ پنل بگذارد ─────────────────────────────
WIRED = {"telegram.py": "signal", "hamid/cycle.py": "outcome",
         "hamid/dominance_report.py": "dom_report",
         "hamid/work_report.py": "work_report",
         "hamid/pump_radar.py": "pump_report"}
for rel, kind in WIRED.items():
    src = (PY / rel).read_text(encoding="utf-8")
    check(f"{rel} ردِ «{kind}» روی پنل می‌گذارد",
          "record_out(" in src and f'"{kind}"' in src)

# پنل واقعاً همین فایل را می‌خواند و می‌سازد
panel = (PY.parents[1] / "index.html").read_text(encoding="utf-8")
check("پنل فایل دفتر تلگرام را می‌خواند",
      "signals/telegram-feed.json" in panel)
check("پنل کارت «آنچه به تلگرام رفت» را دارد",
      'id="tgFeedBox"' in panel and "آنچه به تلگرام رفت" in panel)
check("پنل هر پنج نوع را برچسب فارسی دارد",
      all(k in panel for k in ("signal:", "outcome:", "dom_report:",
                               "work_report:", "pump_report:")))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
