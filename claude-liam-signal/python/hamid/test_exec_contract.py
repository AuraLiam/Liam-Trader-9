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
ST.TOP_LIQUIDITY.clear()
ST.TOP_LIQUIDITY.update({"TESTUSDT", "BTCUSDT"})
ST._TOP_LIQ_OK = True
r = ST.analyze("TESTUSDT", c4, c1, c15, btc4h=mk(up), btc1h=mk(up))
check("سوینگ: سیگنال با ایزوله + استاپ/تارگت صادر می‌شود",
      r.get("action") == "LONG" and r.get("margin_mode") == "isolated"
      and r.get("stop_loss") and r.get("take_profit")
      and r.get("sl_tp_mandatory") is True, str(r.get("why")))
check("سوینگ: نردبان خروج دوپله همراه سیگنال می‌آید (دستور ۲۱ اوت)",
      "exit_plan" in r and r["exit_plan"]["tp1_close_pct"] == 33
      and r["exit_plan"]["tp2"] > r["tp1"] > r["entry"]
      and r["exit_plan"]["tp2_trail_lock_pct"] == 85, str(r.get("exit_plan")))
check("سوینگ: آلت بدون بستر BTC = NO_SIGNAL",
      ST.analyze("TESTUSDT", c4, c1, c15)["action"] == "NO_SIGNAL")
g2 = ST.analyze("TESTUSDT", c4, c1, c15, btc4h=mk(dn), btc1h=mk(dn))
check("سوینگ: هر دو تایم BTC خلاف = وتوی مطلق",
      g2["action"] == "NO_SIGNAL" and "وتوی مطلق" in g2["why"], str(g2.get("why")))
check("سوینگ: خود BTC از دروازهٔ بستر معاف است",
      ST.analyze("BTCUSDT", c4, c1, c15)["action"] == "LONG")

# دروازهٔ لایهٔ نقدشوندگی برتر ۶۰ (۲۱ اوت): تنها لایهٔ CI-تأییدشده
ST.TOP_LIQUIDITY.discard("TESTUSDT")
g3 = ST.analyze("TESTUSDT", c4, c1, c15, btc4h=mk(up), btc1h=mk(up))
check("سوینگ: نماد خارج از لایهٔ نقدشوندگی برتر ۶۰ = NO_SIGNAL",
      g3["action"] == "NO_SIGNAL" and "نقدشوندگی" in g3["why"], str(g3.get("why")))
ST.TOP_LIQUIDITY.add("TESTUSDT")
ST._TOP_LIQ_OK = False
g4 = ST.analyze("TESTUSDT", c4, c1, c15, btc4h=mk(up), btc1h=mk(up))
check("سوینگ: عدم همگام‌سازی لایهٔ نقدشوندگی = بی‌سیگنال، نه عبور کور",
      g4["action"] == "NO_SIGNAL" and "نقدشوندگی" in g4["why"], str(g4.get("why")))
ST._TOP_LIQ_OK = True

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

# قفل کراس (۲۰ اوت، بار دوم): محیط کراس دیده شود → هیچ سیگنالی
ST.set_environment({"margin_mode": "Cross"})
locked = ST.analyze("TESTUSDT", c4, c1, c15, btc4h=mk(up), btc1h=mk(up))
check("محیط کراس = قفل کامل استراتژی",
      locked["action"] == "NO_SIGNAL" and "CROSS" in locked["why"],
      str(locked.get("why")))
locked_sc = ST.scalp_decide(c1m, "TESTUSDT")
check("قفل کراس اسکلپ را هم می‌گیرد", locked_sc["action"] == "NO_SIGNAL")
ST.set_environment({"margin_mode": "isolated"})
check("محیط ایزوله = قفل باز می‌شود",
      ST.analyze("TESTUSDT", c4, c1, c15, btc4h=mk(up), btc1h=mk(up))["action"] == "LONG")
ST.ENV["margin_mode"] = None

# اسکن: ستاپ ARMED خلاف هر دو تایم بالا نباید منتشر شود (پروندهٔ ARB)
import scan as SC                      # noqa: E402

def _mk_tg(path, tf_ms):
    base = int(time.time() * 1000) - len(path) * tf_ms
    return [{"t": base + i * tf_ms, "o": p, "h": p * 1.004, "l": p * 0.996,
             "c": p, "v": 1.0} for i, p in enumerate(path)]

# روند صعودی با سوینگ واقعی — پلهٔ صاف سوینگ نمی‌سازد و structure.trend
# (درست) «رنج» می‌گوید؛ زیگزاگ بالارونده لازم است تا HH/HL ثبت شود.
import math
_up240 = [100 + i * 0.5 + 6 * math.sin(i / 3.0) for i in range(240)]

def _kget_up(sym, tf, n):
    return _mk_tg(_up240, 14400000 if tf == "4h" else 3600000)

# کندل ۵ دقیقه برای نقشهٔ نقدینگی — دروازه حالا نقشه را اجباری می‌گیرد
_liq_cd = _mk_tg([100 + (i % 7) * 0.3 for i in range(120)], 300000)
setups = [
    {"sym": "ARBUSDT", "dir": "SHORT", "tf": "5m", "stage": "ARMED",
     "quality": 56, "candles": _liq_cd},
    {"sym": "ARBUSDT", "dir": "LONG", "tf": "5m", "stage": "SIGNAL",
     "quality": 80, "candles": _liq_cd},
    {"sym": "XUSDT", "dir": "SHORT", "tf": "5m", "stage": "WATCH"},
]
n_dem, _dirs = SC.gate_stages(setups, kget=_kget_up)
check("اسکن: ARMED خلاف هر دو تایم بالا به WATCH تنزل می‌کند",
      setups[0]["stage"] == "WATCH" and "وتوی مطلق" in setups[0].get("skip", ""),
      str(setups[0].get("skip")))
check("اسکن: ستاپ هم‌جهت دست‌نخورده می‌ماند و روندش ثبت می‌شود",
      setups[1]["stage"] == "SIGNAL" and setups[1].get("trend4") == "up")
check("اسکن: مراحل WATCH بی‌جهت شبکه نمی‌خورند", "trend4" not in setups[2])
check("اسکن: نقشهٔ نقدینگی روی ستاپ منتشرشونده نشسته (دستور ۲۳ اوت)",
      setups[1].get("liq_map") and "magnet" in setups[1]["liq_map"],
      str(setups[1].get("liq_map"))[:150])

# ستاپ بی‌کندل = نقشه ساختنی نیست = انتشار ممنوع (قانون ۱)
s_noliq = [{"sym": "ZUSDT", "dir": "LONG", "tf": "5m", "stage": "SIGNAL",
            "quality": 80}]
SC.gate_stages(s_noliq, kget=_kget_up)
check("اسکن: بدون نقشهٔ نقدینگی، سیگنال منتشر نمی‌شود",
      s_noliq[0]["stage"] == "WATCH" and "نقدینگی" in s_noliq[0].get("skip", ""),
      str(s_noliq[0].get("skip")))

def _kget_boom(sym, tf, n):
    raise RuntimeError("network down")

s2 = [{"sym": "YUSDT", "dir": "LONG", "tf": "5m", "stage": "ARMED"}]
SC.gate_stages(s2, kget=_kget_boom)
check("اسکن: دادهٔ روند ناموجود = انتشار ممنوع (قانون ۱)",
      s2[0]["stage"] == "WATCH", str(s2[0]))


# ── درس ۲۶ اوت: گزارش/واچ‌لیست هرگز خودش را سیگنال جا نمی‌زند ────────────
# حمید در تلگرام «سیگنال»های بی‌تارگت و بی‌روند از رادار پامپ می‌دید —
# چون گزارش تحلیلی در دفتر سیگنال ثبت می‌شد و از همان‌جا به پل اجرا می‌رفت.
import telegram as _tg

_before = _tg.TGLOG.read_text() if _tg.TGLOG.exists() else None
_tg._log_final({"sym": "FAKEUSDT", "dir": "LONG", "tf": "15m",
                "entry": 1.0, "sl": 0.99, "tp1": None,
                "strategyName": "گزارش بدلی"})
_after = _tg.TGLOG.read_text() if _tg.TGLOG.exists() else None
check("دفتر سیگنال: ردیف بی‌تارگت ثبت نمی‌شود (قرارداد اجرا)",
      _before == _after)
_tg._log_final({"sym": "FAKEUSDT", "dir": "SHORT", "tf": "15m",
                "entry": 1.0, "sl": None, "tp1": 0.9,
                "strategyName": "گزارش بدلی"})
check("دفتر سیگنال: ردیف بی‌استاپ هم ثبت نمی‌شود",
      _after == (_tg.TGLOG.read_text() if _tg.TGLOG.exists() else None))

_HERE = Path(__file__).resolve().parent
_pr_src = (_HERE / "pump_radar.py").read_text(encoding="utf-8")
_pw_src = (_HERE / "pump_watchlist.py").read_text(encoding="utf-8")
check("رادار پامپ دیگر در دفتر سیگنال نمی‌نویسد", "_log_final" not in _pr_src)
check("دفتر انتظار پامپ دیگر در دفتر سیگنال نمی‌نویسد",
      "_log_final" not in _pw_src)
check("پیام رادار پامپ صریح می‌گوید «سیگنال ورود نیست»",
      "سیگنال ورود نیست" in _pr_src)
check("پیام دفتر انتظار صریح می‌گوید «سیگنال ورود نیست»",
      "سیگنال ورود نیست" in _pw_src)

# ── قیف باید جهت را بشمرد، و پیش از دروازه (۶ سپتامبر) ───────────────────
#
# سؤال حمید: «علت اینکه سیگنال شورت پیدا نمیشود باید دقیق بررسی شود.»
# با فیلدهای قبلی جواب‌دادنی نبود: قیف فقط شمارِ کلِ ستاپ را داشت. و چون
# `funnel_report` **بعد از** `gate_stages` صدا زده می‌شود، وضعیتِ
# پیش-دروازه بازیابی‌ناپذیر بود — یعنی نمی‌شد فهمید موتور شورت نمی‌سازد
# یا می‌سازد و دروازه می‌کشدش. اثباتِ محصول، نه اثباتِ اسکریپت:
from collections import Counter as _FC
_st = [{"stage": "SIGNAL", "dir": "LONG"}, {"stage": "SIGNAL", "dir": "SHORT"},
       {"stage": "ARMED", "dir": "SHORT"}]
_pre = _FC((s["stage"], s["dir"]) for s in _st)
_st[1]["stage"] = "WATCH"                      # دروازه شورت را تنزل داد
_st[2]["stage"] = "WATCH"
_fn = SC.funnel_report(_st, sent=1, demoted=2, held=0, series=9, failed=0,
                       pre_gate=_pre, demoted_dirs={"SHORT": 2})
check("قیف جهتِ همهٔ ستاپ‌ها را می‌شمرد",
      _fn.get("dirs") == {"LONG": 1, "SHORT": 2}, str(_fn.get("dirs")))
check("قیف عکسِ پیش از دروازه را نگه می‌دارد",
      (_fn.get("stage_dir_pre_gate") or {}).get("SIGNAL|SHORT") == 1,
      str(_fn.get("stage_dir_pre_gate")))
check("و پس از دروازه با آن فرق دارد (وگرنه عکس بی‌فایده است)",
      "SIGNAL|SHORT" not in (_fn.get("stage_dir_post_gate") or {}),
      str(_fn.get("stage_dir_post_gate")))
check("تنزلِ دروازهٔ روند به تفکیک جهت ثبت می‌شود",
      (_fn.get("trend_gate_demoted_dirs") or {}).get("SHORT") == 2,
      str(_fn.get("trend_gate_demoted_dirs")))
check("و دروازه خودش جهت‌ها را برمی‌گرداند، نه فقط یک عدد",
      isinstance(SC.gate_stages([], kget=_kget_up), tuple))
_scan_src = (Path(__file__).resolve().parents[1] / "scan.py").read_text(
    encoding="utf-8")
check("کلاس: عکسِ پیش-دروازه قبل از gate_stages گرفته می‌شود",
      0 <= _scan_src.find("_pre_gate = _PC(") < _scan_src.find("gate_stages(setups)"))
print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان قرارداد اجرا: هر {OK} بررسی سبز")
