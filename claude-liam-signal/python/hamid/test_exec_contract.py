"""پاسبان قرارداد اجرا — دستور حمید، ۲۰ اوت.

«در داشبورد نه استاپ گذاشته می‌شود نه تارگت؛ همهٔ پوزیشن‌ها باید ایزوله
باشند و اصلاً کراس باز نشود؛ و هیچ‌وقت خلاف جهت مارکت پوزیشن باز نکند،
مگر اسکلپ یا با همهٔ تأییدیه‌ها.» — نمونهٔ دیده‌شده: شورت ARB در بازار مثبت.

این آزمون قفل می‌کند:
۱. هر خروجی قابل‌معاملهٔ هر سه فایل داشبوردی margin_mode=isolated و
   stop_loss/take_profit دارد.
۲. آلت بدون بستر BTC سیگنال نمی‌گیرد؛ هر دو تایم BTC خلاف = وتوی مطلق.
۳. خط اجرا (liam9_link) سفارش بدون tp1 یا با مارجین کراس را رد می‌کند.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import liam9_strategy as ST            # noqa: E402
import liam9_h1_strategy as H1         # noqa: E402
import liam9_link as LK                # noqa: E402

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


def mk(path, tf_ms=900000, t0=0):
    return [{"t": t0 + i * tf_ms, "o": p, "h": p * 1.004, "l": p * 0.996,
             "c": p} for i, p in enumerate(path)]


up = [100 + i * 0.4 for i in range(230)]
dn = [200 - i * 0.4 for i in range(230)]
c4 = c1 = mk(up)
pull = up + [up[-1] - i * 0.5 for i in range(1, 16)]
c15 = mk(pull)
c15[-1]["l"], c15[-1]["c"] = c15[-1]["c"] * 0.99, c15[-1]["c"] * 0.9905

ST.EXPERIENCE.clear()
r = ST.analyze("TESTUSDT", c4, c1, c15, btc4h=mk(up), btc1h=mk(up))
check("سوینگ: سیگنال با ایزوله + استاپ/تارگت صادر می‌شود",
      r.get("action") == "LONG" and r.get("margin_mode") == "isolated"
      and r.get("stop_loss") and r.get("take_profit")
      and r.get("sl_tp_mandatory") is True, str(r.get("why")))
check("سوینگ: آلت بدون بستر BTC = NO_SIGNAL",
      ST.analyze("TESTUSDT", c4, c1, c15)["action"] == "NO_SIGNAL")
g2 = ST.analyze("TESTUSDT", c4, c1, c15, btc4h=mk(dn), btc1h=mk(dn))
check("سوینگ: هر دو تایم BTC خلاف = وتوی مطلق",
      g2["action"] == "NO_SIGNAL" and "وتوی مطلق" in g2["why"], str(g2.get("why")))
check("سوینگ: خود BTC از دروازهٔ بستر معاف است",
      ST.analyze("BTCUSDT", c4, c1, c15)["action"] == "LONG")

# اسکلپ: استثنای صریح حمید — دروازهٔ بازار ندارد ولی قرارداد اجرا دارد
up1 = [100 + i * 0.05 for i in range(120)]
p1 = up1 + [up1[-1] - i * 0.03 for i in range(1, 7)]
c1m = mk(p1, tf_ms=60000, t0=int(time.time() * 1000) - 126 * 60000)
c1m[-1]["l"], c1m[-1]["c"] = c1m[-1]["c"] * 0.998, c1m[-1]["c"] * 0.9982
c1m[-4]["l"] = c1m[-1]["c"] * 0.993
s = ST.scalp_decide(c1m, "TESTUSDT")
check("اسکلپ: بدون بستر BTC مجاز است (استثنای صریح) ولی ایزوله + SL/TP دارد",
      s.get("action") == "LONG" and s.get("margin_mode") == "isolated"
      and s.get("stop_loss") and s.get("take_profit"), str(s.get("why")))

# موتور ۱ ساعته
H4 = 14400000
h4 = mk([100 + i * 0.35 for i in range(260)], tf_ms=H4)
hp = [100 + i * 0.35 for i in range(260)]
hc1 = mk(hp + [hp[-1] - i * 1.2 for i in range(1, 9)], tf_ms=3600000)
hc1[-1]["l"], hc1[-1]["c"] = hc1[-1]["c"] * 0.988, hc1[-1]["c"] * 0.9895
H1.EXPERIENCE.clear()
hr = H1.analyze("TESTUSDT", h4, hc1, btc4h=h4, btc1h=mk(hp, tf_ms=3600000))
check("۱ساعته: سیگنال با ایزوله + استاپ/تارگت صادر می‌شود",
      hr.get("action") == "LONG" and hr.get("margin_mode") == "isolated"
      and hr.get("stop_loss") and hr.get("take_profit"), str(hr.get("why")))
check("۱ساعته: آلت بدون بستر BTC = NO_SIGNAL",
      H1.analyze("TESTUSDT", h4, hc1)["action"] == "NO_SIGNAL")

# خط اجرا: سفارش بی‌تارگت یا کراس رد می‌شود
base = {"product": "futures", "symbol": "ETHUSDT", "side": "LONG",
        "entry": 100.0, "sl": 99.0, "tp1": 102.0, "stop_pct": 1.0,
        "leverage": 10, "notional_usd": 100.0,
        "margin_mode": "isolated", "mode": "demo"}
check("خط اجرا: سفارش سالم قبول می‌شود", LK.validate_exec(dict(base)) == [])
no_tp = dict(base, tp1=None)
check("خط اجرا: سفارش بدون تارگت رد می‌شود",
      any("tp1" in e for e in LK.validate_exec(no_tp)))
cross = dict(base, margin_mode="cross")
check("خط اجرا: مارجین کراس رد می‌شود",
      any("کراس" in e or "isolated" in e for e in LK.validate_exec(cross)))
no_mm = dict(base)
no_mm.pop("margin_mode")
check("خط اجرا: سفارش بدون حالت مارجین رد می‌شود",
      LK.validate_exec(no_mm) != [])

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان قرارداد اجرا: هر {OK} بررسی سبز")
