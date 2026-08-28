"""پاسبان حلقهٔ بسته (دستور حمید، ۲۸ اوت شب).

«هیچ فعالیتی خارج از قوانین جعبه انجام نشود. سیگنالی که از تلگرام
می‌رود باید هم در تست‌های یادگیری باشد، هم در سیگنال نهایی پنل، و هم
نتیجه‌اش در یادگیری و علت‌یابی.»

خطرِ کلاس که این آزمون می‌بندد: دروازه‌ای در یک سر سامانه سیگنال را
عبور بدهد و دروازه‌ای در سر دیگر همان را بی‌صدا بیندازد. اندازه‌گیری
شبِ کشف: ۲۸ از ۴۰ سیگنالِ ارسالی کارمزد ≥۰.۲۵R داشتند و دفتر یادگیری
ردشان می‌کرد — یعنی ۷۰٪ از آنچه واقعاً فرستاده شد، هیچ تجربه‌ای
نمی‌ساخت و کارنامه از زیرمجموعه‌ای خوش‌بینانه ساخته می‌شد.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import loop_audit as LA                   # noqa: E402
from hamid import paper as P                         # noqa: E402

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


# ── قلبِ رفع: ارسالی هرگز به‌خاطر کارمزد از دفتر نمی‌افتد ─────────────────
TMP = Path(tempfile.mkdtemp(prefix="loopaudit-"))
old_open, old_closed = P.OPEN, P.CLOSED
P.OPEN, P.CLOSED = TMP / "open.jsonl", TMP / "closed.jsonl"
try:
    # استاپ عمداً تنگ: کارمزد به‌روشنی از ۰.۲۵R بیشتر می‌شود
    tight = {"symbol": "BTCUSDT", "dir": "LONG", "entry": 100000.0,
             "sl": 99980.0, "tp1": 100060.0, "tf": "5m"}
    P.open_from([dict(tight, stage_tag="sig-ibs")], {"tg_msg_id": 111})
    rows = [json.loads(x) for x in P.OPEN.read_text().splitlines() if x.strip()]
    check("سیگنالِ ارسالیِ استاپ‌تنگ در دفتر یادگیری ثبت می‌شود",
          len(rows) == 1, f"{len(rows)} ردیف")
    if rows:
        check("کارمزدِ ردیف روی خودش نوشته می‌شود",
              rows[0].get("fee_r") is not None, str(rows[0].get("fee_r")))
        check("ردیفِ تلهٔ کارمزد صریح برچسب می‌خورد (پنهان نمی‌شود)",
              rows[0].get("fee_trap") is True, str(rows[0].get("fee_trap")))
        check("شمارهٔ پیام تلگرام روی ردیف می‌ماند (ریپلای نتیجه)",
              (rows[0].get("why") or {}).get("tg_msg_id") == 111)

    # و دفترِ غیرارسالی هنوز دروازهٔ کارمزد را دارد — رفع، دروازه را نشکست
    P.OPEN.write_text("")
    P.open_from([dict(tight, symbol="ETHUSDT", entry=4000.0, sl=3999.2,
                      tp1=4002.4, stage_tag="second")], {})
    rows2 = [json.loads(x) for x in P.OPEN.read_text().splitlines() if x.strip()]
    check("دفترِ غیرارسالی همچنان استاپِ تنگ را رد می‌کند (دروازه نشکست)",
          len(rows2) == 0, f"{len(rows2)} ردیف")
finally:
    P.OPEN, P.CLOSED = old_open, old_closed

# ── ممیز روی دادهٔ واقعی کار می‌کند و بستهٔ شواهد کامل می‌دهد ─────────────
a = LA.audit()
check("ممیز روی دفترهای واقعی اجرا می‌شود",
      isinstance(a.get("n_sent"), int) and "leaks" in a)
from hamid import evidence_packet as EP              # noqa: E402
check("خروجی ممیز بستهٔ شواهد کامل دارد (قانون ۱۲)",
      EP.validate(LA.packet(a)) == [], str(EP.validate(LA.packet(a))))
check("پنجرهٔ ممیزی اعلام‌شده است", a.get("window_h") == LA.WINDOW_H)

# مرزِ پنل واقعاً در کد اجرا شده، نه فقط در متن ادعا شده
src = (HERE / "loop_audit.py").read_text(encoding="utf-8")
check("مرزِ «دفتر پنل از چه زمانی هست» در کد اعمال شده",
      "feed_since" in src and "at >= feed_since" in src)

# منبعِ رفع مستند است — عدد کشف روی خودِ کد می‌ماند
psrc = (HERE / "paper.py").read_text(encoding="utf-8")
check("دلیلِ عددیِ رفع روی کد ثبت است", "۲۸ از ۴۰" in psrc)
check("ارسالی از دروازهٔ کارمزد مستثناست", '_is_sent = str(_stage).startswith("sig-")' in psrc)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
