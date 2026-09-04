"""پاسبان راه‌اندازِ ویندوز (۴ سپتامبر) — آفلاین، بدون شبکه.

عیبی که این پاسبان کلاسش را می‌بندد، روی صفحهٔ خودِ حمید دیده شد: راه‌انداز
PowerShell با انبوه خطای قرمز ترکید، چون فایل UTF-8 بدون BOM بود و
Windows PowerShell 5.1 آن را ANSI خواند — هر حرف فارسی چند بایتِ بی‌معنا
شد و پارسر افتاد.

درسِ کلاس: **متنِ فارسی و منطق نباید در فایلی باشد که کدگذاری‌اش به
تنظیمات ویندوز وابسته است و من نمی‌توانم اجرایش کنم.** پس فایل‌های
`.cmd` فقط ASCII‌اند و همهٔ کار در پایتون است. این پاسبان همین را قفل
می‌کند.
"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parent.parent
sys.path.insert(0, str(PY))

import win_start as W                                # noqa: E402

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


# ── ۱. فایل‌های cmd فقط ASCII — همان عیبی که حمید دید ──────────────────
CMDS = ["LIAM9.cmd", "LIAM9-DOCTOR.cmd", "LIAM9-AUTOSTART.cmd", "لیام۹.cmd"]
for name in CMDS:
    p = ROOT / name
    check(f"{name} وجود دارد", p.exists())
    if not p.exists():
        continue
    raw = p.read_bytes()
    bad = [i for i, b in enumerate(raw) if b > 127]
    check(f"{name} هیچ بایت غیر-ASCII ندارد (درسِ BOM)",
          not bad, f"{len(bad)} بایت، اولین در جایگاه {bad[0] if bad else '-'}")

check("هیچ اسکریپت PowerShell در مسیر ویندوز نمانده",
      not (ROOT / "service" / "liam9.ps1").exists())
launcher = (ROOT / "LIAM9.cmd").read_text(encoding="ascii")
# روی خطوطِ **اجراشدنی** سنجیده می‌شود، نه روی کل متن: راه‌انداز در
# توضیحاتش می‌گوید چرا PowerShell را کنار گذاشتیم، و در یک `echo` به
# حمید می‌گوید پاورشل را برای نصب پایتون باز کند. هر دو درست‌اند.
# محافظی که مستنداتِ خودش را جرم بگیرد، آدم را وادار می‌کند مستندات را
# پاک کند تا سبز شود — همان درسِ بررسی «reset --hard» در آزمایشگاه.
_live = [ln.strip() for ln in launcher.splitlines()
         if ln.strip() and not ln.strip().lower().startswith(("rem ", "echo", "::"))]
check("راه‌انداز، PowerShell را **اجرا** نمی‌کند",
      not any("powershell" in ln.lower() for ln in _live),
      str([ln for ln in _live if "powershell" in ln.lower()]))
check("و کار را به پایتون می‌دهد", "win_start.py" in launcher)
check("با پرچم UTF-8 صریح، تا کنسولِ ویندوز فارسی را نشکند",
      "-X utf8" in launcher)
check("و اگر پایتون نبود، خطِ نصبش را نشان می‌دهد",
      "winget install" in launcher and "Python" in launcher)
check("سه فایلِ دیگر همه از همین یکی رد می‌شوند (یک مسیر، نه چهار)",
      all("LIAM9.cmd" in (ROOT / n).read_text(encoding="utf-8")
          for n in CMDS if n != "LIAM9.cmd"))

# ── ۲. خواندن توکن — عیبِ اندازه‌گیری‌شده ──────────────────────────────
#
# نسخهٔ اول با split/strip می‌خواند و روی توکنِ **خالی** خطِ بعدی را
# به‌عنوان مقدار برمی‌داشت، یعنی دکتر می‌گفت «توکن هست» در حالی که نبود.
T = W.ENV_TEMPLATE
check("توکنِ خالیِ قالب، «پرشده» خوانده نمی‌شود",
      W._env_value(T, "TELEGRAM_BOT_TOKEN") == "",
      repr(W._env_value(T, "TELEGRAM_BOT_TOKEN")))
check("و شناسهٔ چتِ خالی هم همین‌طور",
      W._env_value(T, "TELEGRAM_CHAT_ID") == "")
check("توکنِ واقعی درست خوانده می‌شود",
      W._env_value("TELEGRAM_BOT_TOKEN=123:abc\nTELEGRAM_CHAT_ID=9\n",
                   "TELEGRAM_BOT_TOKEN") == "123:abc")
check("فاصلهٔ اضافه اذیت نمی‌کند",
      W._env_value("  TELEGRAM_BOT_TOKEN = 7:z  \n", "TELEGRAM_BOT_TOKEN") == "7:z")
check("خطِ توضیحی به‌جای مقدار برداشته نمی‌شود",
      W._env_value("# TELEGRAM_BOT_TOKEN=fake\nTELEGRAM_BOT_TOKEN=real\n",
                   "TELEGRAM_BOT_TOKEN") == "real")
check("توکنِ فقط-فاصله خالی حساب می‌شود",
      W._env_value("TELEGRAM_BOT_TOKEN=   \nTELEGRAM_CHAT_ID=5\n",
                   "TELEGRAM_BOT_TOKEN") == "")

with tempfile.TemporaryDirectory() as td:
    saved = W.ENVF
    try:
        W.ENVF = Path(td) / "live.env"
        got = W.ensure_env()
        check("فایل نبود → ساخته می‌شود", W.ENVF.exists())
        check("و با توکنِ خالی، False برمی‌گرداند (نه ادعای آمادگی)",
              got is False, repr(got))
        check("قالبِ ساخته‌شده هر دو کلید را دارد",
              "TELEGRAM_BOT_TOKEN=" in W.ENVF.read_text(encoding="utf-8")
              and "TELEGRAM_CHAT_ID=" in W.ENVF.read_text(encoding="utf-8"))
        W.ENVF.write_text("TELEGRAM_BOT_TOKEN=1:a\nTELEGRAM_CHAT_ID=2\n",
                          encoding="utf-8")
        check("با توکنِ پرشده، True", W.ensure_env() is True)
    finally:
        W.ENVF = saved

# ── ۳. به‌روزرسانی فقط کد را می‌گیرد، نه دفترها ────────────────────────
check("مسیرهای کد فهرست شده‌اند", len(W.CODE_PATHS) >= 10)
for d in ("signals", "brain"):
    check(f"«{d}» در فهرست به‌روزرسانی **نیست** — دفتر محلی لمس نمی‌شود",
          d not in W.CODE_PATHS)
src = (PY / "win_start.py").read_text(encoding="utf-8")
check("و از pull/rebase/reset استفاده نمی‌شود (تصادم ساختاراً ممکن نیست)",
      '"pull"' not in src and '"rebase"' not in src and "reset --hard" not in src)
check("فقط checkout مسیرهای کد", '"checkout", "origin/main", "--"' in src)

# ── ۴. هیچ کاری حلقه را نمی‌کشد ────────────────────────────────────────
r = W._run(["__no_such_command__"], timeout=5)
check("فرمانِ ناموجود استثنا پرت نمی‌کند", r.returncode != 0)
r2 = W._run([sys.executable, "-c", "print('ok')"], timeout=30)
check("فرمانِ درست اجرا می‌شود", r2.returncode == 0 and "ok" in r2.stdout)

# ── ۵. همیشه‌روشن با schtasks، نه PowerShell ───────────────────────────
check("ثبتِ همیشه‌روشن از schtasks استفاده می‌کند", '"schtasks"' in src)
check("و راهِ لغوش صریح گفته می‌شود", "/Delete" in src)
check("نامِ کار ثابت است تا دوباره‌ثبت، دوتا نسازد", W.TASK == "LiamTrader9")

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
