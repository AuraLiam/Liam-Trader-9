"""پاسبان جریان سیگنال — پروندهٔ «چرا سیگنال کم می‌آید» (حمید، ۲۰ اوت).

سه عیبِ سنجیده‌شده که این آزمون برگشتشان را ناممکن می‌کند:

۱. **ردِ موقت = ممنوعیت ۱۲ ساعته.** هر رد لحظه‌ای (قیمت دور بود، روند همان
   دقیقه مخالف بود) کلید `skip|` می‌نوشت با همان عمر ۱۲ ساعتهٔ ارسال‌شده‌ها.
   اندازه‌گیری: ۱۳۹ skip در برابر ۳۶ ارسال در ۲۴ ساعت. حالا skip فقط ۳۰
   دقیقه عمر دارد و ستاپ دوباره از همهٔ دروازه‌ها رد می‌شود.
۲. **بستر USDT.D/BTC.D همیشه «نامعلوم».** چرخه به market_first مقدار None
   می‌داد در حالی که اتاق دامیننس ۲۳۲ کندل ۱ساعته داشت — قانون ۳ (بستر
   اجباری) عملاً در هر تصمیم غایب بود.
۳. **قیف بی‌ثبت.** دلیل رد فقط در لاگ Actions چاپ می‌شد و گم می‌شد؛ قانون
   ۰۷ می‌گوید سکوت باید با شواهد طبقه‌بندی شود.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

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


# ۱) عمر کلیدها: ارسال ۱۲ ساعت، ردِ موقت ۳۰ دقیقه
import telegram as TG                                # noqa: E402

check("عمر ردِ موقت کوتاه‌تر از عمر ارسال‌شده است",
      TG.SKIP_TTL_MS < TG.TTL_MS, f"skip={TG.SKIP_TTL_MS} ttl={TG.TTL_MS}")
check("عمر ردِ موقت حداکثر یک ساعت است (شرط لحظه‌ای، نه حکم ابدی)",
      TG.SKIP_TTL_MS <= 3600 * 1000, str(TG.SKIP_TTL_MS))

now = time.time() * 1000
old_sent = TG.SENT
tmp = ROOT / "signals" / "sent-test.json"
TG.SENT = tmp
try:
    tmp.write_text(json.dumps({
        "ibs|AAAUSDT|15m|LONG": now - 60 * 60 * 1000,        # ارسال ۱ ساعت پیش
        "skip|ibs|BBBUSDT|15m|LONG": now - 60 * 60 * 1000,   # ردِ ۱ ساعت پیش
        "skip|ibs|CCCUSDT|15m|LONG": now - 5 * 60 * 1000,    # ردِ ۵ دقیقه پیش
        "ibs|DDDUSDT|15m|LONG": now - 13 * 3600 * 1000,      # ارسال ۱۳ ساعت پیش
    }))
    loaded = TG._load_sent()
    check("ارسالِ ۱ ساعت پیش هنوز یادش هست (ضدتکرار سر جایش)",
          "ibs|AAAUSDT|15m|LONG" in loaded)
    check("ردِ موقتِ ۱ ساعت پیش آزاد شده (عیب اصلی)",
          "skip|ibs|BBBUSDT|15m|LONG" not in loaded, str(sorted(loaded)))
    check("ردِ موقتِ ۵ دقیقه پیش هنوز نگه داشته می‌شود (ضد اسپم)",
          "skip|ibs|CCCUSDT|15m|LONG" in loaded)
    check("ارسالِ کهنه‌تر از ۱۲ ساعت فراموش می‌شود",
          "ibs|DDDUSDT|15m|LONG" not in loaded)
finally:
    TG.SENT = old_sent
    tmp.unlink(missing_ok=True)

# ۲) چرخه باید کندل واقعی دامیننس را به market_first بدهد، نه None
src = (PY / "hamid" / "cycle.py").read_text(encoding="utf-8")
check("چرخه دیگر market_first(btc4, None, None) صدا نمی‌زند",
      "market_first(btc4, None, None)" not in src)
check("چرخه سری دامیننس را می‌خواند و پاس می‌دهد",
      "market_first(btc4, usdt_d4, btc_d4)" in src and "_dom._bars(_pts" in src)

from hamid.stack import market_first                 # noqa: E402
from hamid import dominance as DOM                   # noqa: E402

try:
    pts = json.loads(DOM.SERIES.read_text()).get("points") or []
except Exception:                                    # noqa: BLE001
    pts = []
if len(pts) > 200:
    mf = market_first(None, DOM._bars(pts, "u"), DOM._bars(pts, "b"))
    check("با سری واقعی، USDT.D دیگر «کندل کافی نیست» نمی‌دهد",
          mf["USDT.D"].get("trend") not in (None, "unknown"),
          json.dumps(mf["USDT.D"], ensure_ascii=False))
    check("با سری واقعی، BTC.D هم خوانده می‌شود",
          mf["BTC.D"].get("trend") not in (None, "unknown"))
    # «نامشخص» دیگر دو معنی ندارد: بی‌داده ≠ بی‌جهت
    bars = DOM._bars(pts, "u")
    full = market_first(bars, bars, bars)            # هر سه معلوم
    check("بستر کامل = context_known و کد جهت‌دار",
          full.get("context_known") is True
          and full.get("verdict_code") in ("TETHER_UP", "RISK_ON", "RISK_OFF",
                                           "NEUTRAL"), str(full.get("verdict_code")))
    empty = market_first(None, None, None)
    check("بستر ناقص = INSUFFICIENT_CONTEXT (نه «نامشخص» مبهم)",
          empty.get("verdict_code") == "INSUFFICIENT_CONTEXT"
          and empty.get("context_known") is False, str(empty.get("verdict_code")))
else:
    print("  … سری دامیننس در این محیط خالی است — دو بررسی رد شد (نه شکست)")

# ۳) قیف: اسکن باید طبقه‌بندی سلامت را بنویسد (قانون ۰۷)
import scan as SC                                    # noqa: E402

check("اسکن تابع ثبت قیف دارد", hasattr(SC, "funnel_report"))
if hasattr(SC, "funnel_report"):
    setups = [
        {"sym": "AUSDT", "stage": "SIGNAL", "strategy": "ibs", "dir": "LONG"},
        {"sym": "BUSDT", "stage": "WATCH", "strategy": "ibs", "dir": "SHORT",
         "skip": "هر دو تایم بالا خلاف SHORT است (۴س=up، ۱س=up) — وتوی مطلق"},
        {"sym": "CUSDT", "stage": "ARMED", "strategy": "smc", "dir": "LONG",
         "waitReason": "قیمت هنوز به باکس نرسیده"},
    ]
    f = SC.funnel_report(setups, sent=1, demoted=1, held=0, series=120, failed=0)
    check("قیف طبقه‌بندی معتبر می‌دهد",
          f["classification"] in ("SIGNAL_READY", "NO_VALID_SETUP_HEALTHY",
                                  "PIPELINE_DEGRADED", "SIGNAL_SUPPRESSED_BY_RISK",
                                  "DELIVERY_FAILED"), str(f.get("classification")))
    check("قیف دلیل ردها را می‌شمارد", bool(f.get("top_reasons")),
          json.dumps(f.get("top_reasons"), ensure_ascii=False)[:120])
    check("دادهٔ ناموجود = PIPELINE_DEGRADED",
          SC.funnel_report([], sent=0, demoted=0, held=0, series=0,
                           failed=12)["classification"] == "PIPELINE_DEGRADED")
    check("سیگنال ساخته و فرستاده‌شده = SIGNAL_READY",
          f["classification"] == "SIGNAL_READY", str(f["classification"]))
    check("بدون ستاپ ولی دادهٔ سالم = NO_VALID_SETUP_HEALTHY",
          SC.funnel_report([{"sym": "X", "stage": "WATCH", "strategy": "ibs"}],
                           sent=0, demoted=0, held=0, series=120,
                           failed=0)["classification"] == "NO_VALID_SETUP_HEALTHY")

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان جریان سیگنال: هر {OK} بررسی سبز")
