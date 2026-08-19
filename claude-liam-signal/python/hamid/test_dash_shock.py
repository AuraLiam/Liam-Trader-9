"""آزمون فایل داشبوردیِ شوک — تازگی نسبت به منبع + قرارداد بارگذار.

کلاس خطایی که می‌بندد: فایل تولیدی (liam9_shock_strategy.py) از منبع
(liam9_shock.py / liam9_link.py) عقب بیفتد و داشبورد ماه‌ها با منطق کهنه
بچرخد بدون این‌که کسی بفهمد. هر تغییر منبع بدون بازساخت = این تست قرمز.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def run():
    out = PY / "liam9_shock_strategy.py"
    check("فایل داشبورد وجود دارد", out.exists())

    # ۱) تازگی: بازساخت نباید چیزی را عوض کند
    before = out.read_text()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_dash_shock.py")],
                   check=True, capture_output=True)
    check("فایل تولیدی از منبع عقب نمانده (بازساخت = بدون تغییر)",
          out.read_text() == before)

    # ۲) خوداتکایی: هیچ import محلی — فقط کتابخانهٔ استاندارد
    txt = out.read_text()
    for bad in ("import liam9_shock", "import liam9_link", "from liam9",
                "from hamid", "import sources"):
        check(f"وابستگی محلی ندارد ({bad})", bad not in txt)

    # ۳) قرارداد بارگذار داشبورد + خودآزمایی کامل فایل، در پروسهٔ جدا
    #    (پروسهٔ جدا = همان شرایط داشبورد، بدون ماژول‌های این ریپو در حافظه)
    r = subprocess.run([sys.executable, str(out), "--selftest"],
                       capture_output=True, text=True, timeout=300)
    check("خودآزمایی فایل داشبورد در پروسهٔ ایزوله سبز است",
          r.returncode == 0 and "خودآزمایی فایل داشبورد گذشت" in r.stdout,
          (r.stdout + r.stderr)[-300:])

    # ۴) سکرت هرگز داخل فایل نیست
    check("هیچ سکرت/کلیدی در فایل نیست",
          "LIAM9_LINK_SECRET" in txt              # فقط نامِ متغیر محیطی
          and "hexdigest" in txt
          and not any(x in txt for x in ("BEGIN PRIVATE", "api_secret =",
                                         "token =")))

    print(f"\n✓ همهٔ {OK} آزمون فایل داشبوردی شوک گذشت")


if __name__ == "__main__":
    run()
