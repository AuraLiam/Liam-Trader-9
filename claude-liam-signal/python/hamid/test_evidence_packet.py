"""پاسبان بستهٔ شواهد (قانون ۱۲) — همراه اجباری evidence_packet.py.

خطرها: بستهٔ ناقص که کامل جا زده شود، عدد تهی، سناریوی یک‌طرفه،
و جا افتادن بخش تقویم/منابع از گزارش دامیننس.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import evidence_packet as EP               # noqa: E402

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


full = EP.build(
    claim="USDT.D ساختار نزولی — بازار ریسک‌پذیر",
    numbers={"USDT.D": 6.773, "chg_1h": "+0.065"},
    track_record="پیش‌بینی ۳۰د: ۲۶۱/۴۰۸ (۶۴٪)",
    scenario_up="عبور از 6.84 → مقصد 6.95",
    scenario_down="شکست 6.72 → مقصد 6.60",
    invalidator="کلوز ۴س بالای 6.84",
    sources=["ForexFactory", "سری اتاق"],
    limit="شاهد است نه دروازه")
check("بستهٔ کامل عیبی ندارد", EP.validate(full) == [], str(EP.validate(full)))

txt = EP.render(full)
check("رندر هر هشت جزء را دارد",
      all(s in txt for s in ("💬", "🔢", "🎯", "بالا برود", "پایین بیاید",
                             "⛔", "🔗", "⚖️")), txt)
check("اعداد داخل رندر است", "6.773" in txt)
check("کارنامه داخل رندر است", "۶۴٪" in txt)

# اثبات منفی: هر جزء غایب باید گرفته شود
for miss in EP.REQUIRED:
    p = dict(full)
    p[miss] = ""
    check(f"غیبت «{miss}» گرفته می‌شود",
          f"missing:{miss}" in EP.validate(p))

check("عدد تهی (None) گرفته می‌شود",
      "empty_number:x" in EP.validate(dict(full, numbers={"x": None})))
check("سناریوی یک‌طرفه بستهٔ کامل نیست",
      EP.validate(dict(full, scenario_down="")) != [])

# ── گزارش دامیننس واقعاً از این مدل استفاده می‌کند (کلاس عیب: قانونِ
# فقط-روی-کاغذ). بررسی روی سورس، نه وعده.
src = (HERE / "dominance_report.py").read_text(encoding="utf-8")
check("گزارش دامیننس بخش تقویم پیش رو دارد", "_calendar_lines" in src
      and "📅" in src)
check("گزارش دامیننس خط منابع دارد", "🔗 منابع" in src)
check("گزارش دامیننس مرز صادقانه دارد", "⚖️ مرز صادقانه" in src)
check("گزارش دامیننس کپشن بلند را دوتکه می‌فرستد",
      "_split_caption" in src)
dsrc = (HERE / "dominance.py").read_text(encoding="utf-8")
check("رأی دامیننس همهٔ رویدادها را می‌برد نه فقط نزدیک‌ترین",
      "رویدادهای کلان پیش رو" in dsrc and "nearest" not in dsrc)
isrc = (HERE / "intel.py").read_text(encoding="utf-8")
check("منبع آنلاک سخت‌گیرانه است (شکل ناشناس = UNVERIFIED، نه حدس)",
      "UNVERIFIED_SHAPE" in isrc and "def unlocks" in isrc)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
