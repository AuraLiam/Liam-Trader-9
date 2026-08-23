"""پاسبانِ تزریق دانش به مهارت ایجنت‌ها — دستور حمید (۲۳ اوت).

حمید خواست قواعد و منابع تازه «مثل آمپول» به خودِ ایجنت‌ها تزریق شود، نه
فقط به فایل داشبورد. مشکلِ همیشگیِ چنین تزریقی این است که عدد در دو جا
می‌نشیند و بعد از یک تغییر، یکی عوض می‌شود و دیگری بی‌سروصدا کهنه
می‌ماند — ایجنتی که با عدد کهنه استدلال می‌کند بدتر از ایجنتِ بی‌عدد است.

پس این پاسبان دو چیز را می‌گیرد:

۱. بلوکِ تزریق‌شده اصلاً سرِ جایش هست (کسی حذفش نکرده).
۲. **عددهای داخل مهارت با منبع حقیقت یکی است** — `liam9_strategy.py`.
   هر واگرایی، چرخه را سرخ می‌کند.

اجرا:  python3 -m hamid.test_skill_injection
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
SKILLS = ROOT / ".claude" / "skills"
RULE10 = ROOT / ".claude" / "rules" / "10-scalp-1m-candle-entry.md"

sys.path.insert(0, str(PY))
import liam9_strategy as ST                              # noqa: E402

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


def skill(slug):
    p = SKILLS / slug / "SKILL.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


e09 = skill("liam-e09-candlestick-evidence")
e10 = skill("liam-e10-order-flow-level2")
e16 = skill("liam-e16-risk-portfolio")
e18 = skill("liam-e18-paper-replay-backtest")
e19 = skill("liam-e19-trade-management")

print("— بلوک تزریق سرِ جایش هست:")
check("E09 بلوک ورود اسکلپ ۱د را دارد", "Rule 10" in e09 and "Closed candles only" in e09)
check("E10 جایگاه برنامهٔ درسی و مرز ۳۰ث را دارد",
      "Harris + Cartea" in e10 and "30-second" in e10)
check("E16 بخش سایزِ اطمینان‌محور را دارد", "Confidence-scaled sizing" in e16)
check("E18 وضعیت اندازه‌گیری‌شدهٔ لبهٔ اسکلپ را دارد", "−0.1878R" in e18)
check("E19 بخش تریل و پوزیشن مانده را دارد",
      "trail_arm" in e19 and "position_watch.py" in e19)
check("قانون ۱۰ به‌عنوان سند مرجع موجود است و به داشبورد ارجاع می‌دهد",
      RULE10.exists() and "liam9_strategy" in RULE10.read_text(encoding="utf-8"))

print("\n— عددها با منبع حقیقت (liam9_strategy) یکی است:")


def nums(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text))


sizing = e16.split("Confidence-scaled sizing")[-1].split("## Learning routine")[0]
check(f"بازهٔ اهرم {ST.LEV_MIN}–{ST.LEV_MAX_CONF} در E16 همان است",
      f"**{ST.LEV_MIN}–{ST.LEV_MAX_CONF}**" in sizing, sizing[:200])
check("شیب اهرم (۱۵ + ۲۴×اطمینان) با دو سرِ بازه می‌خواند",
      f"{ST.LEV_MIN} + {ST.LEV_MAX_CONF - ST.LEV_MIN} ×" in sizing)
check(f"مارجین {ST.MARGIN_PCT_MIN:.0f}–{ST.MARGIN_PCT_MAX:.0f}٪ در E16 همان است",
      f"{ST.MARGIN_PCT_MIN:.0f}–{ST.MARGIN_PCT_MAX:.0f}%" in sizing)
check(f"سقف {ST.MAX_CONCURRENT} پوزیشن هم‌زمان در E16 همان است",
      f"**{ST.MAX_CONCURRENT}\n  concurrent positions**" in sizing
      or f"**{ST.MAX_CONCURRENT} concurrent positions**" in sizing
      or f"most **{ST.MAX_CONCURRENT}" in sizing, sizing[:400])
check("حاصل‌ضرب چیدمان (۳×۳۰٪=۹۰٪) درست چاپ شده",
      f"{ST.MAX_CONCURRENT} × {ST.MARGIN_PCT_MAX:.0f}% = "
      f"{ST.MAX_CONCURRENT * ST.MARGIN_PCT_MAX:.0f}%" in sizing)
check(f"محافظ لیکویید {ST.SCALP['liq_guard']:.0f}÷استاپ٪ در E16 همان است",
      f"{ST.SCALP['liq_guard']:.0f} ÷ stop%" in sizing)

_max_stop = ST.SCALP["liq_guard"] / ST.LEV_MIN
check(f"استاپِ بیشینه (~{_max_stop:.1f}٪) از همان دو عدد درآمده",
      f"{_max_stop:.1f}%" in sizing,
      f"انتظار {_max_stop:.1f}% از liq_guard/LEV_MIN")

zone = e09.split("Scalp 1m/30s entry")[-1]
_z = ST.SCALP["entry_zone_r"] if hasattr(ST, "SCALP") and \
    "entry_zone_r" in ST.SCALP else 0.35
check(f"ناحیهٔ ورود (±{_z}×ریسک) در E09 همان عدد استراتژی است",
      f"{_z} × risk" in zone, zone[:400])

print("\n— ادعای بی‌سنجش تزریق نشده:")
check("E18 صریح می‌گوید لبهٔ اسکلپ فعلاً اثبات نشده",
      "measured status of the 1m scalp edge: none" in e18)
check("E09 الگو را ماشهٔ مستقل نمی‌کند",
      "never the trigger" in e09)
check("E19 مرز اجرای زنده را نگه داشته (پاسبان نمی‌بندد)",
      "does not close" in e19 and "Rule 05" in e19)

# متنِ مهارت جریانِ خطی است و عبارت بین دو خط می‌شکند؛ بررسیِ نثر باید
# فاصله‌ها را یکدست کند وگرنه صرفاً به محلِ شکستِ خط حساس می‌شود.
def flat(s):
    return " ".join(s.split())


e09f, e10f = flat(e09), flat(e10)

print("\n— حقایق راستی‌آزمایی‌شدهٔ صرافی سرِ جایشان است:")
check("E09 معنی confirm را عیناً دارد",
      "confirm=true" in e09f and "the candle has closed" in e09f)
check("E09 فهرست بازه‌ها را دارد و می‌گوید زیر-دقیقه نیست",
      "1, 3, 5, 15, 30" in e09f and "no sub-minute" in e09f)
check("E10 می‌گوید S در استریم معامله سمتِ تیکر است",
      "Side of taker" in e10f)
check("E10 تلهٔ snapshot تکراری با همان u را دارد",
      "same `u`" in e10f and "3 seconds" in e10f)
check("E10 معنی درست side در لیکوییدیشن را عیناً دارد (وارونه‌خوانی رایج)",
      "a long position has been liquidated" in e10f
      and "not the order side" in e10f)
check("E10 هشدار می‌دهد p قیمت ورشکستگی است نه قیمت بازار",
      "bankruptcy price" in e10f)
check("هر ادعای صرافی به شواهدِ قابل‌بازبینی ارجاع دارد",
      "docs-probe.json" in e09f and "docs-probe.json" in e10f)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبانِ تزریق مهارت: هر {OK} بررسی سبز")
