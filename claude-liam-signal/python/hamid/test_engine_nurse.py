"""پاسبان پرستار انجین‌ها — همراه اجباری engine_nurse.py (دستور حمید، ۲۵ سپتامبر).

حمید: «راه حل همیشگی… باید به کل مجموعه متصل باشه.» این آزمون اتصالِ
پرستار به کل مجموعه را پایدار نگه می‌دارد:

۱. هر مالکِ قرارداد وضعیت، خطِ بیدارسازی یا ردِ مستند دارد — انجینی که
   کهنه شود بی‌درمان نمی‌ماند (نقض «به کل مجموعه متصل»).
۲. ورک‌فلوی هر خط واقعاً در ریپو هست — dispatchِ خطِ ناموجود یعنی
   درمانی که هرگز نمی‌رسد.
۳. پرستار خودش بیرون از قانون ۱۳ نمانده: nurse.json ثبت است و پنل
   وضعیتش را نشان می‌دهد.
۴. تجربه به دفتر مهارت می‌رود — «قابلیت کسب تجربه و مهارت» بدون ثبت،
   شعار است نه سازوکار.
۵. سیم‌کشی: پرستار در زنجیرهٔ ۵دقیقه‌ای و چرخهٔ حمید صدا زده می‌شود —
   ابزاری که هیچ‌جا اجرا نمی‌شود، محافظ نیست (درسِ test_paper، ۱۱ سپتامبر).
۶. اثباتِ یادگیریِ تولیدکنندهٔ اجراشونده دارد (درسِ ۶ سپتامبر): قراردادِ
   تجربه روی دو نویسندهٔ زنده (زنجیره + چرخه) بسته شده، نه سرویسِ مستقرنشده.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import engine_nurse as EN                     # noqa: E402
from hamid import state_bus as SB                        # noqa: E402

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


print("پاسبان پرستار انجین‌ها")

# ── ۱ و ۲: پوشش کامل مالک‌ها و وجودِ خطوط ─────────────────────────────────
reg = SB.registry()["files"]
owners = {s["owner"] for s in reg.values() if s.get("owner")}
uncovered = {o for o in owners if o not in EN.WAKE and o not in EN.NO_LIVE_FILES}
check("هر مالکِ قرارداد خطِ درمان یا ردِ مستند دارد", not uncovered,
      f"بی‌پوشش: {sorted(uncovered)}")
for owner, wf in sorted(EN.WAKE.items()):
    if wf:
        check(f"ورک‌فلوی خطِ {owner} ({wf}) در ریپو هست",
              (ROOT / ".github" / "workflows" / wf).exists())

# پادزهرها سالم‌اند — نه اسپم dispatch، نه درمانِ دیر
check("پادزهر پیش‌فرض بین ۱۰ و ۲۴۰ دقیقه",
      10 <= EN.WAKE_COOLDOWN_MIN["default"] <= 240)

# ── ۳: پرستار خودش داخل قرارداد است و پنل نشانش می‌دهد ────────────────────
check("nurse.json در قرارداد وضعیت ثبت است", "nurse.json" in reg)
check("سقف کهنگی nurse.json با کادنس زنجیره هم‌خوان است",
      reg.get("nurse.json", {}).get("max_age_min", 0) == 45)
panel = (ROOT / "index.html").read_text(encoding="utf-8")
check("پنل وضعیت پرستار را می‌خواند", "signals/nurse.json" in panel)
check("پنل کارت پرستار دارد", 'id="nurseBox"' in panel)

# ── ۴: تجربه به دفتر مهارت می‌رود ─────────────────────────────────────────
src = (PY / "hamid" / "engine_nurse.py").read_text(encoding="utf-8")
check("درمان موفق در دفتر مهارت ثبت می‌شود",
      "SL.learn" in src or "skill_ledger" in src)
check("تولیدِ تازهٔ هر انجین تجربهٔ خودِ انجین می‌شود",
      "تولیدِ تازه" in src)

# ── ۵: سیم‌کشی به هر دو خطِ زنده ──────────────────────────────────────────
chain = (ROOT / ".github" / "workflows" / "pump-radar.yml").read_text(encoding="utf-8")
cycle = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
check("پرستار در زنجیرهٔ ۵دقیقه‌ای صدا زده می‌شود",
      "hamid.engine_nurse" in chain)
check("پرستار در چرخهٔ حمید هم هست", "hamid.engine_nurse" in cycle)

# ── ۶: محافظ شنی — دفتر واقعی در آزمون برنده نمی‌شود ──────────────────────
import brain as _b                                       # noqa: E402
from hamid import skill_ledger as SL                     # noqa: E402
if EN._SANDBOX:
    check("در شنی، دفتر واقعی بسته است", _b.blocked(SL.LEDGER))
    EN._learn("__پاسبان__", "آزمونِ شنی", "باید به دفتر آزمایشی برود")
    check("دفتر واقعی در شنی دست‌نخورده ماند",
          not SL.LEDGER.exists() or "__پاسبان__" not in SL.LEDGER.read_text(encoding="utf-8"))
else:
    check("خارج از شنی، محافظ بی‌اثر است", not _b.blocked(SL.LEDGER))

# ── حکمِ معاینه صادقانه است ────────────────────────────────────────────────
doc = EN.examine(write=False)
check("خروجی معاینه مهرِ زمان دارد", bool(doc.get("generated")))
check("بدون توکن، درمان صادقانه غیرفعال گزارش می‌شود",
      doc.get("treatment_enabled") is False)
check("هر اقدام یک حکم از مجموعهٔ شناخته دارد",
      all(a.get("verdict") in ("monitor_only", "treatment_disabled",
                               "cooldown", "woken", "wake_failed")
          for a in doc.get("actions", [])))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
