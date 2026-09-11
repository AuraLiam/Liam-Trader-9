"""پاسبان نسخهٔ داشبورد (دستور حمید، ۲۹ اوت — «داشبورد نشونش نمیده»).

سه خطر:
۱. فایل دوباره از سقفِ جعبهٔ داشبورد رد شود و کسی نفهمد تا حمید ببیند.
۲. فشرده‌سازی رفتار را عوض کند (یک بار عوض کرد: کلیدِ دیکشنری را
   داک‌استرینگ گرفت و کل فایل با KeyError افتاد).
۳. نسخهٔ فشرده از منبع عقب بماند و حمید کدِ کهنه را روی داشبورد بگذارد.
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import build_dashboard as B                # noqa: E402

OK = 0
FAIL = []

# سقفِ محافظه‌کارانه: v2.8 با ۸۶KB روی داشبورد کار می‌کرد و v3.0 با ۹۵KB
# نه. مرزِ دقیقِ داشبورد را نمی‌دانیم، پس سقفِ خودمان را زیرِ آخرین
# اندازهٔ کارکرده می‌گذاریم تا حاشیه بماند.
SIZE_CAP = 80_000


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


src = B.SRC.read_text(encoding="utf-8")
out_path = B.OUT

check("فایل فشردهٔ داشبورد وجود دارد", out_path.exists())
if out_path.exists():
    n = len(out_path.read_bytes())
    check(f"نسخهٔ داشبورد زیر سقف اندازه است ({n:,} < {SIZE_CAP:,})",
          n < SIZE_CAP, f"{n:,} بایت")
    check("نسخهٔ فشرده واقعاً کوچک‌تر از منبع است",
          n < len(src.encode()) * 0.8,
          f"فشرده {n:,} در برابر منبع {len(src.encode()):,}")

# ── فشرده‌سازی رفتار را عوض نمی‌کند ───────────────────────────────────────
stripped = B.strip(src)
check("خروجی فشرده نحو درست دارد",
      compile(stripped, "<dash>", "exec") is not None)

# اثباتِ عیبی که یک بار رخ داد: کلیدِ دیکشنری نباید خالی شود
check("کلیدهای دیکشنری دست‌نخورده می‌مانند (عیبِ KeyError برنمی‌گردد)",
      '"version":' in stripped or "'version':" in stripped,
      "کلید version از دیکشنری پارامترها حذف شده")
for key in ("ibs_long_max", "rr_target", "fee_round_trip_pct"):
    check(f"کلید «{key}» در نسخهٔ فشرده هست", key in stripped)

# ── نسخهٔ فشرده از منبع عقب نمانده ───────────────────────────────────────
if out_path.exists():
    fresh = B.banner(src, stripped)
    body_now = "\n".join(fresh.splitlines()[13:])
    body_out = "\n".join(out_path.read_text(encoding="utf-8").splitlines()[13:])
    check("نسخهٔ داشبورد با منبعِ فعلی هم‌قدم است "
          "(وگرنه: python3 -m hamid.build_dashboard)",
          body_now == body_out,
          "منبع عوض شده ولی نسخهٔ داشبورد بازسازی نشده")

# ── خودِ خروجی اجرا می‌شود و خودآزمایی را پاس می‌کند ──────────────────────
if out_path.exists():
    t0 = time.time()
    r = subprocess.run([sys.executable, str(out_path), "--selftest"],
                       cwd=str(PY), capture_output=True, text=True, timeout=600)
    check("نسخهٔ داشبورد خودآزمایی استراتژی را پاس می‌کند",
          r.returncode == 0, (r.stdout + r.stderr)[-300:])
    check("خودآزمایی در زمان معقول تمام می‌شود",
          time.time() - t0 < 300, f"{time.time() - t0:.0f}s")

# ── سازنده بدون اثبات نمی‌نویسد (قید ایمنی) ──────────────────────────────
bsrc = (HERE / "build_dashboard.py").read_text(encoding="utf-8")
check("سازنده خروجیِ مردود را نمی‌نویسد",
      "if not ok:" in bsrc and "raise SystemExit" in bsrc)
check("سازنده جای داک‌استرینگ را از AST می‌گیرد نه حدس",
      "_docstring_spans" in bsrc and "ast.parse" in bsrc)

# ── نام موتور «ققنوس» (دستور حمید، ۱۱ سپتامبر) ─────────────────────────
#
# سه بررسی، و سومی مهم‌ترین است: نام و امضا دو چیز جدا هستند و نباید
# با هم جابه‌جا شوند.
check("نام موتور ققنوس است", B.ENGINE_FA == "ققنوس", B.ENGINE_FA)
check("خروجیِ سازنده ghoghnoos.py است", B.OUT.name == "ghoghnoos.py",
      B.OUT.name)
_built = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
check("سرآمدِ فایلِ ساخته‌شده نامِ ققنوس را دارد",
      "ققنوس" in _built.split('"""')[1] if '"""' in _built else False)

# امضای پنل روی خروجی باید بماند — نامِ موتور عوض شد، برندِ ارسال نه
# (دستور ۱۶ اوت: حمید باید بفهمد پیام از کدام پنل آمده).
# نسخهٔ اولِ این بررسی فقط **شمار** برند در کل فایل را می‌دید و
# اثباتِ منفی‌اش نگرفت: برداشتنِ برند از سرآمد، شمار را زیر آستانه
# نمی‌برد چون خودِ بدنه دو بار داردش. پس حالا همان فیلدی سنجیده
# می‌شود که واقعاً روی سیگنال می‌نشیند.
# فاصله‌ها را نشماریم: فشرده‌ساز `"panel": "…"` را به `"panel":"…"`
# تبدیل می‌کند و نسخهٔ اولِ همین خط با فاصله نوشته شده بود، پس در حالتِ
# سالم هم قرمز می‌داد.
import re as _re                                         # noqa: E402
_SIG = _re.compile(r'panel"\s*:\s*"لیام تریدر ۹"')
check("امضای پنل روی خروجیِ سیگنال دست‌نخورده ماند",
      len(_SIG.findall(_built)) >= 2, str(len(_SIG.findall(_built))))

# محافظِ کلاس: هیچ **سیم‌کشیِ** کهنه‌ای به نامِ قبلی نماند. بدون این،
# سند و محصول از هم جدا می‌افتند — همان کلاسی که ۶ سپتامبر پنل را ۱۹
# روز کهنه نگه داشت.
#
# نسخهٔ اولِ همین بررسی **متن** را می‌گشت و روی دو چیزِ بی‌ضرر افتاد:
# کامنتِ تاریخیِ خودِ سازنده (که دلیلِ تغییرِ نام را نگه می‌دارد) و متنِ
# خودِ همین آزمون. پس حالا فقط سیم‌کشی سنجیده می‌شود — خطِ کد، نه
# کامنت — و فایلِ آزمون از دایره بیرون است.
def _wired_to_old(path):
    try:
        txt = path.read_text(encoding="utf-8")
    except Exception:                                    # noqa: BLE001
        return False
    for line in txt.splitlines():
        code = line.split("#", 1)[0] if path.suffix == ".py" else line
        if "liam9_strategy_dash" in code:
            return True
    return False


_stale = [q.name for q in
          list(PY.glob("*.py")) + list(HERE.glob("*.py")) +
          list((ROOT / "claude-liam-signal").glob("*.md"))
          if q.name != "test_dashboard_build.py" and _wired_to_old(q)]
check("هیچ سیم‌کشیِ کهنه به نامِ قبلی نماند", not _stale, str(_stale))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
