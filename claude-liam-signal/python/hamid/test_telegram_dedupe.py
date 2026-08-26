"""پاسبان ضدتکرار سه‌منبعی + دروازهٔ تایم‌فریم (رفع ریشه‌ای ۲۶ اوت شب).

عیب سنجیده‌شده: PAXGUSDT SHORT 5m با ورودی یکسان ۵ بار در ۲۱ دقیقه رفت
(۲۰:۲۸ تا ۲۰:۴۹) چون حافظهٔ ضدتکرار فقط روی sent.jsonِ گیت بود و از
۲۰:۱۲ تا ۲۱:۰۱ هیچ push روی main ننشست — هر دورِ زنجیره با reset به
حافظهٔ کهنه برمی‌گشت و دوباره می‌فرستاد.

رفع سه‌لایه که این آزمون قفلش می‌کند:
۱. حافظهٔ کناری /tmp (SIDECAR) مستقل از گیت، در هر دورِ رانر زنده.
۲. ذخیرهٔ فوری بعد از هر ارسال (_save_sent داخل حلقه)، نه فقط انتهای تابع.
۳. بازسازی کلید any| از خود telegram-log — سومین منبع حقیقت.
+ دروازهٔ تایم‌فریم: ارسال فقط 5m/15m (دستور صریح حمید، ۲۶ اوت شب).
+ آرشیو شماره‌دار append-only (دستور «اطلاعات را یکی نکن؛ شماره‌گذاری کن»).
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

import telegram as TG                                # noqa: E402

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


import tempfile                                      # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="tg-dedupe-"))
now = time.time() * 1000

old = (TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR)
TG.SENT = TMP / "sent.json"
TG.SIDECAR = TMP / "sidecar.json"
TG.TGLOG = TMP / "tglog.json"
TG.ARCHIVE_DIR = TMP / "archive"

try:
    # ── ۱) اجتماع سه‌منبعی ─────────────────────────────────────────────
    TG.SENT.write_text(json.dumps({"ibs|AAAUSDT|15m|LONG": now - 1000}))
    TG.SIDECAR.write_text(json.dumps({"ibs|PAXGUSDT|5m|SHORT": now - 2000,
                                      "ibs|AAAUSDT|15m|LONG": now - 500}))
    TG.TGLOG.write_text(json.dumps({"sent": [
        {"sym": "CCCUSDT", "tf": "15m", "dir": "LONG", "at": now - 3000},
        {"sym": "OLDUSDT", "tf": "15m", "dir": "LONG",
         "at": now - 13 * 3600 * 1000},
    ]}))
    loaded = TG._load_sent()
    check("کلیدی که فقط در حافظهٔ کناری است دیده می‌شود (سناریوی PAXG)",
          "ibs|PAXGUSDT|5m|SHORT" in loaded, str(sorted(loaded)))
    check("در تعارض دیسک/کناری، تازه‌ترین زمان برنده است",
          loaded.get("ibs|AAAUSDT|15m|LONG") == now - 500)
    check("ردیف لاگ ارسال، کلید any| را بازمی‌سازد (منبع سوم)",
          "any|CCCUSDT|15m|LONG" in loaded)
    check("ردیف لاگ کهنه‌تر از ۱۲ ساعت بازسازی نمی‌شود",
          "any|OLDUSDT|15m|LONG" not in loaded)

    # ── ۲) ذخیرهٔ دوخانه‌ای ────────────────────────────────────────────
    TG._save_sent({"k1": now})
    check("ذخیره در هر دو خانه می‌نشیند (دیسک + کناری)",
          json.loads(TG.SENT.read_text()) == {"k1": now}
          and json.loads(TG.SIDECAR.read_text()) == {"k1": now})

    # ── ۳) آرشیو شماره‌دار append-only ─────────────────────────────────
    TG._archive_sent({"sym": "XUSDT", "tf": "5m", "dir": "LONG",
                      "entry": 1.0, "sl": 0.9, "tp1": 1.2, "strategy": "ibs"})
    TG._archive_sent({"sym": "YUSDT", "tf": "15m", "dir": "SHORT",
                      "entry": 2.0, "sl": 2.2, "tp1": 1.7, "strategy": "ibs"})
    day = time.strftime("%Y%m%d", time.gmtime())
    arc = TG.ARCHIVE_DIR / f"telegram-sent-{day}.jsonl"
    rows = [json.loads(x) for x in arc.read_text().splitlines()]
    check("آرشیو append-only است و شماره‌های پیاپی دارد",
          [r["n"] for r in rows] == [1, 2], str(rows))
    check("ردیف آرشیو هویت کامل معامله را دارد",
          rows[0]["sym"] == "XUSDT" and rows[0]["tp1"] == 1.2)

    # ── ۴) دروازهٔ تایم‌فریم در گلوگاه ارسال ───────────────────────────
    check("فقط ۵د و ۱۵د مجازند (دستور ۲۶ اوت)",
          TG.ALLOWED_TFS == {"5m", "15m"})
    calls = []
    old_post, old_creds = TG._post, TG.creds
    TG._post = lambda *a, **k: calls.append(a) or {"result": {"message_id": 1}}
    TG.creds = lambda: ("tok", "chat")
    try:
        n = TG.send_signals(
            [{"sym": "ZUSDT", "tf": "1h", "dir": "LONG", "strategy": "ibs",
              "entry": 1, "sl": 0.9, "tp1": 1.3},
             {"sym": "WUSDT", "tf": "4h", "dir": "SHORT", "strategy": "ibs",
              "entry": 1, "sl": 1.1, "tp1": 0.7}],
            lambda s, p: None)
    finally:
        TG._post, TG.creds = old_post, old_creds
    check("سیگنال ۱س/۴س در گلوگاه رد می‌شود و هیچ ارسالی نمی‌رود",
          n == 0 and not calls, f"n={n} calls={len(calls)}")

    # ── ۵) کلاس عیب: ذخیرهٔ فوری داخل حلقه، نه فقط انتها ───────────────
    src = (PY / "telegram.py").read_text(encoding="utf-8")
    loop_after_send = src.split('sent[f"any|', 1)[1][:400]
    check("بعد از هر ارسال، همان لحظه ذخیره می‌شود (_save_sent داخل حلقه)",
          "_save_sent(sent)" in loop_after_send, loop_after_send[:120])
    check("هیچ نوشتن مستقیم SENT.write_text بیرون از _save_sent نیست",
          src.count("SENT.write_text") == 1)
    check("آرشیو در مسیر ارسال صدا زده می‌شود",
          "_archive_sent(s)" in loop_after_send)
finally:
    TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR = old

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
