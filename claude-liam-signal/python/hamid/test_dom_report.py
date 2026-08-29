"""پاسبان گزارش ساعتی دامیننس (دستور حمید، ۲۶ اوت شب).

خطرها: گزارش بی‌امضا، نظریه از دادهٔ کهنه (نقض قانون ۱)، سناریوی
یک‌طرفه (نقض قانون ۱۱: همیشه درخت دو جهت)، و اسپم زیر ۵۰ دقیقه.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import dominance_report as DR             # noqa: E402

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


TMP = Path(tempfile.mkdtemp(prefix="domrep-"))
now = time.time() * 1000
old = (DR.DOM, DR.STATE, DR.SERIES)
DR.DOM = TMP / "dominance.json"
DR.STATE = TMP / "state.json"
DR.SERIES = TMP / "series.json"
try:
    fresh = {"generated": now, "usdt_dominance": 6.9, "btc_dominance": 59.2,
             "verdict": "آزمایشی",
             "multi_tf": {"usdt": {"1h": {"trend": "up", "px": 6.9,
                                          "levels_above": [6.95],
                                          "levels_below": [6.85]},
                                   "4h": {"trend": "down"}},
                          "btc_d": {"1h": {"trend": "range", "px": 59.2,
                                           "levels_above": [59.4],
                                           "levels_below": [59.0]},
                                    "4h": {"trend": "range"}}},
             "macro": [{"title": "GDP m/m", "in_hours": 17.9, "country": "CAD"},
                       {"title": "Fed Chairman Speaks", "in_hours": 19.4,
                        "country": "USD"},
                       {"title": "Payrolls Revision", "in_hours": 19.4,
                        "country": "USD"}],
             "forecast": {"scoreboard": {
                 "USDT.D|30m": {"n": 10, "hit": 6, "dir_n": 4,
                                "dir_hit_pct": 25.0,
                                "baseline_flat_pct": 70.0, "skill": -10.0}}}}
    DR.DOM.write_text(json.dumps(fresh))
    cap = DR.build()
    check("گزارش امضای پنل دارد", "لیام تریدر ۹" in cap)
    # تقویم کامل (درس ۲۷ اوت: سخنرانی فد نباید پشت GDP گم شود)
    check("هر سه رویداد تقویم در گزارش‌اند، نه فقط نزدیک‌ترین",
          all(t in cap for t in ("GDP m/m", "Fed Chairman", "Payrolls")), cap)
    check("رویداد تقویم ساعت تهران دارد", "📅" in cap and "ساعت" in cap)
    check("منابع و مرز صادقانه روی گزارش است (قانون ۱۲)",
          "🔗 منابع" in cap and "⚖️" in cap)
    check("روند ۱س و ۴س هر دو نماد در گزارش است",
          "USDT.D" in cap and "BTC.D" in cap and "۴س" in cap)
    check("سناریوی هر دو جهت نوشته می‌شود (قانون ۱۱)",
          "بالا برود" in cap and "پایین بیاید" in cap, cap)
    check("کارنامهٔ پیش‌بینی با شمارش می‌آید", "6/10" in cap)
    # درس ۲۹ اوت: درصدِ کل بدون بنچمارک، اعتبارنامهٔ کاذب است — ۸۷.۶٪
    # پیش‌بینی‌ها FLAT بودند و آن درصد عمدتاً پاداشِ سکوت بود.
    check("کارنامه بدون بنچمارک چاپ نمی‌شود (مهارت کنارش می‌آید)",
          "مهارت -10" in cap and "همیشه FLAT" in cap, cap)
    check("سهم ادعای جهت‌دار جدا گزارش می‌شود",
          "جهت‌دار 4 نوبت" in cap, cap)

    stale = dict(fresh, generated=now - 3 * 3600 * 1000)
    DR.DOM.write_text(json.dumps(stale))
    cap2 = DR.build()
    check("دادهٔ کهنه → هشدار و بدون نظریهٔ تازه (قانون ۱)",
          "کهنه" in cap2 and "بالا برود" not in cap2, cap2)

    # ضدتکرار ۵۰ دقیقه
    DR.STATE.write_text(json.dumps({"last_sent": now - 10 * 60 * 1000}))
    check("زیر ۵۰ دقیقه دوباره نمی‌فرستد", DR.already_sent_recently())
    DR.STATE.write_text(json.dumps({"last_sent": now - 70 * 60 * 1000}))
    check("بعد از یک ساعت آزاد است", not DR.already_sent_recently())

    # سری کوتاه → چارت None (بی‌ادعا)
    DR.SERIES.write_text(json.dumps({"points": [
        {"t": now - i * 240000, "u": 6.9, "b": 59.2} for i in range(20)]}))
    check("سری کوتاه → چارت کشیده نمی‌شود، خطا هم نمی‌دهد",
          DR.render(str(TMP / "x.png")) is None)

    # ماژول در DIRECT_OK با دلیل تاریخ‌دار ثبت است
    src = (HERE / "test_alert_gate.py").read_text(encoding="utf-8")
    check("dominance_report در DIRECT_OK با دلیل ثبت است",
          '"dominance_report.py"' in src and "۲۶ اوت" in src)
finally:
    DR.DOM, DR.STATE, DR.SERIES = old

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
