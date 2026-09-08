"""محافظِ فایلِ تک‌فایلِ داشبوردِ شورت (دستور حمید، ۸ سپتامبر).

    python3 -m hamid.test_short_dashboard

دو خطرِ کلاس که این آزمون می‌بندد:
  ۱. **کهنه‌شدنِ بی‌صدا** — کسی `structure.py` را عوض کند و فایلِ داشبورد
     همان نسخهٔ دیروز بماند؛ آن‌وقت اجرا و اندازه‌گیری دوباره از هم جدا
     می‌شوند (همان عیبی که نسخهٔ ۱.۰ را بی‌معنا کرد).
  ۲. **وابستگیِ پنهان به ریپو** — فایلی که فقط روی این ماشین کار کند و
     در جعبهٔ داشبورد بترکد.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import build_short_dashboard as B          # noqa: E402

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


check("فایل داشبورد ساخته شده", B.OUT.exists(), str(B.OUT))
src = B.OUT.read_text(encoding="utf-8") if B.OUT.exists() else ""

# ── ۱) تازگی: هر تغییر در سورس باید دوباره ساخته شود ──────────────────
r = subprocess.run([sys.executable, "-m", "hamid.build_short_dashboard",
                    "--check"], capture_output=True, text=True, cwd=str(PY),
                   timeout=300)
check("فایل داشبورد با سورسِ ریپو هم‌گام است",
      r.returncode == 0, (r.stdout + r.stderr).strip()[-300:])

# ── ۲) واقعاً تک‌فایل است: بی‌ریپو هم اجرا می‌شود ─────────────────────
if src:
    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / "liam9_short_dash.py"
        copy.write_text(src, encoding="utf-8")
        rr = subprocess.run([sys.executable, str(copy), "--selftest"],
                            capture_output=True, text=True, cwd=td, timeout=300)
        check("خودآزمایی‌اش بیرون از ریپو سبز است",
              rr.returncode == 0, (rr.stdout + rr.stderr).strip()[-300:])
        # خاصیت، نه شکل: مقدارِ واقعیِ پرچم‌ها با **اجرا** خوانده می‌شود.
        # (نسخهٔ اولِ همین بررسی دنبال رشتهٔ «PRODUCTION_APPROVED = False»
        # می‌گشت و چون کم‌حجم‌ساز فاصله‌ها را عوض می‌کند، افتاد.)
        probe = ("import liam9_short_dash as D;"
                 "print(D.PRODUCTION_APPROVED, D.VALIDATION_STATUS)")
        rp = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                            text=True, cwd=td, timeout=300)
        flags = rp.stdout.strip()
        check("مجوز تولید ندارد (مقدارِ واقعی، نه متن)",
              rp.returncode == 0 and flags.startswith("False "), flags or rp.stderr[-200:])
        check("وضعیت ادعا غیرِتولیدی است",
              rp.returncode == 0 and not flags.split(" ", 1)[-1].startswith("PRODUCTION"),
              flags)

# ── ۳) تعریف‌ها قرض گرفته شده‌اند، نه بازنویسی (علتِ ریشه‌ایِ ۷ سپتامبر) ─
for mod in B.DEPS:
    check(f"سورسِ {mod} داخل فایل هست", f'_BUNDLED[{mod!r}]' in src)
check("و به‌عنوان ماژولِ واقعی نصب می‌شود (نه کپیِ دستی)",
      "_install_bundled()" in src and "_sys.modules[_name] = _m" in src)
check("فایل صریح می‌گوید تولیدشده است و دستی ویرایش نشود",
      "تولید می‌شود" in src and "دستی ویرایشش نکن" in src)

# ── ۴) مرزها روی نسخهٔ داشبورد هم هست ────────────────────────────────
check("هیچ‌جا LONG برنمی‌گرداند",
      '"action": "LONG"' not in src and "'action': 'LONG'" not in src)
check("قرارداد اجرا: مارجین ایزوله", '"isolated"' in src)
check("اولویتِ دامیننس داخل فایل داشبورد هم هست",
      "dominance_gate" in src and "alt_stance" in src)
check("و برای بستر، خودش از ریپو می‌کشد (بی‌نیاز از فایلِ محلی)",
      "sync_dominance" in src and "raw.githubusercontent.com" in src)

# ── ۵) اندازه: جعبهٔ داشبورد سقف دارد ────────────────────────────────
kb = len(src.encode("utf-8")) / 1024
check(f"اندازه زیر ۹۰KB است (واقعی: {kb:.0f}KB)", kb < 90, f"{kb:.0f}KB")

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
