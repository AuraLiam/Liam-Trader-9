"""پاسبان بودجهٔ پامپ — قانون ۰۷ (دستور حمید، ۲۰ اوت).

«بررسی کردن روزی ۵ بار کفایت می‌کند؛ انرژی اضافه برای بهبود استراتژی و
لایهٔ تجربه.» پشتوانهٔ عددی: دفتر آلارم پامپ n=۳۰۹۶ با میانگین −۰.۱۸۰R
(CI کامل زیر صفر) در برابر دفتر سیگنال +۰.۰۸۸R (CI بالای صفر).

این آزمون قفل می‌کند که:
- رادار پامپ فقط در pump-review.yml و دقیقاً ۵ نوبت در روز اجرا شود؛
- زنجیرهٔ پیوسته (pump-radar.yml) دیگر رادارِ تازه اجرا نکند (reapply آزاد است)؛
- تنظیم مرکزی روی تایم تهران و ۵ نوبت بماند؛
- فایل‌های بستهٔ دانش نصب‌شده سالم و بدون ارجاع به ریپوی بیگانه باشند.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]

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


WF = ROOT / ".github" / "workflows"

# ۱) pump-review.yml: تنها خانهٔ رادارِ تازه، با دقیقاً ۵ ساعت در کرون
review = (WF / "pump-review.yml").read_text(encoding="utf-8")
crons = re.findall(r'cron:\s*"([^"]+)"', review)
check("pump-review.yml دقیقاً یک کرون دارد", len(crons) == 1, str(crons))
if crons:
    parts = crons[0].split()
    hours = parts[1].split(",") if len(parts) == 5 else []
    check("کرون مرور پامپ ۵ ساعت در روز دارد", len(hours) == 5, crons[0])
    check("کرون مرور پامپ از */N استفاده نمی‌کند", "*/" not in crons[0], crons[0])
check("مرور پامپ رادارِ تازه اجرا می‌کند",
      re.search(r"hamid\.pump_radar --min-pct", review) is not None)

# ۲) زنجیرهٔ پیوسته: رادار تازه ممنوع، reapply آزاد
chain = (WF / "pump-radar.yml").read_text(encoding="utf-8")
fresh = re.findall(r"hamid\.pump_radar(?! --reapply)[^\n]*", chain)
fresh = [f for f in fresh if "--reapply" not in f]
check("زنجیرهٔ سیگنال رادار پامپِ تازه اجرا نمی‌کند", not fresh, "؛ ".join(fresh))

# ۳) هیچ ورک‌فلوی زمان‌بندی‌شدهٔ دیگری رادار تازه اجرا نکند
offenders = []
for p in sorted(WF.glob("*.yml")):
    if p.name in ("pump-review.yml", "pump-radar.yml"):
        continue
    t = p.read_text(encoding="utf-8")
    if re.search(r"hamid\.pump_radar(?!\s+--reapply)", t) and "schedule" in t:
        offenders.append(p.name)
check("رادار تازه فقط در مرور پامپ زمان‌بندی شده", not offenders, "، ".join(offenders))

# ۴) تنظیم مرکزی: تهران + ۵ نوبت + پیش‌اجرای لایو خاموش
cfg_text = (ROOT / "config" / "liam9_signal_priority_v1.yaml").read_text(encoding="utf-8")
check("timezone تنظیم مرکزی Asia/Tehran است", "timezone: Asia/Tehran" in cfg_text)
check("reports_per_local_day برابر ۵ است", "reports_per_local_day: 5" in cfg_text)
check("live_execution در تنظیم مرکزی false است", "live_execution: false" in cfg_text)
m = re.search(r'cron_utc:\s*"([^"]+)"', cfg_text)
check("کرون تنظیم مرکزی با ورک‌فلو یکی است", bool(m and crons and m.group(1) == crons[0]),
      f"config={m.group(1) if m else '?'} workflow={crons[0] if crons else '?'}")

# ۵) فایل‌های بستهٔ دانش: موجود، سالم، بدون ریپوی بیگانه
pack_files = [
    ".claude/rules/07-signal-first-pump-budget.md",
    ".claude/rules/08-order-flow-level2-evidence.md",
    ".claude/rules/09-candlestick-evidence.md",
    ".claude/skills/liam-e10-order-flow-level2/SKILL.md",
    ".claude/skills/liam-e09-candlestick-evidence/SKILL.md",
    ".claude/skills/liam-e12-pump-review/SKILL.md",
    ".claude/skills/liam-e23-signal-health/SKILL.md",
    "config/liam9_signal_priority_v1.yaml",
    "config/liam9_level2_features_v1.yaml",
    "evals/acceptance_gates.md",
    "evals/backtest_protocol.md",
    "evals/knowledge_exam.yaml",
    "brain/library/curricula/order_flow_core.md",
    "brain/library/curricula/candlestick_core.md",
    "brain/library/curricula/level2_core.md",
]
missing = [f for f in pack_files if not (ROOT / f).exists()]
check("همهٔ فایل‌های بستهٔ دانش نصب‌اند", not missing, "، ".join(missing))
dirty = []
for f in pack_files:
    p = ROOT / f
    if p.exists() and re.search(r"sognal|Auraliam18", p.read_text(encoding="utf-8"), re.I):
        dirty.append(f)
check("هیچ فایل بسته به ریپوی بیگانه اشاره ندارد", not dirty, "، ".join(dirty))

schema_bad = []
for p in sorted((ROOT / "schemas").glob("*.json")):
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        schema_bad.append(f"{p.name}: {e}")
check("هر ۴ اسکیمای بسته JSON سالم‌اند",
      not schema_bad and len(list((ROOT / "schemas").glob("*.json"))) >= 4,
      "؛ ".join(schema_bad))

# حلقهٔ زندهٔ لپ‌تاپ هم زیر همین بودجه است (هم‌قدمی ۲۵ اوت): رادار کامل
# فقط ۵ نوبت روزانه در Actions — سرویس محلی حق اجرای pump_radar.run ندارد؛
# سهمش فقط شلیکِ دفتر انتظار (سیستم جایگزین ۱۷ اوت) است.
_live = (ROOT / "claude-liam-signal" / "python" / "hamid" /
         "live_service.py").read_text(encoding="utf-8")
check("سرویس محلی رادار کامل پامپ را اجرا نمی‌کند (قانون ۰۷)",
      "pump_radar.run()" not in _live)
check("ولی شلیک دفتر انتظار (🧠) سر جایش است", "send_ignitions" in _live)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان بودجهٔ پامپ: هر {OK} بررسی سبز")
