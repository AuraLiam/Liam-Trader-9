#!/usr/bin/env python3
"""راه‌اندازِ ویندوز — همهٔ منطق و همهٔ متنِ فارسی، این‌جا.

## عیبی که این فایل بست (۴ سپتامبر، از روی صفحهٔ خودِ حمید)

نسخهٔ قبلی همین کار را در `service/liam9.ps1` می‌کرد و روی لپ‌تاپ حمید
با انبوهی خطای قرمز شکست:

    Missing closing '}' in statement block
    Unexpected token ')' in expression or statement
    ... ÛØ·Ù%Ø§ÛŒŒªÙ^Ù† ...

ریشه‌اش نحو نبود، **کدگذاری** بود: فایل UTF-8 بدون BOM ذخیره شده بود و
Windows PowerShell 5.1 — همان `powershell.exe` که روی هر ویندوزی هست —
اسکریپتِ بدون BOM را ANSI می‌خواند. پس هر حرف فارسی به چند بایتِ بی‌معنا
تبدیل شد، بعضی از آن بایت‌ها کاراکترِ نحوی بودند، و پارسر ترکید.

رفعِ سطحی این بود که BOM اضافه کنم. ولی درسِ کلاس این است: **متنِ فارسی
و منطق را نباید در فایلی گذاشت که کدگذاری‌اش به تنظیمات ویندوز وابسته
است و من نمی‌توانم اجرایش کنم.** پایتون UTF-8 را ذاتاً می‌خواند و من
همین‌جا تستش می‌کنم. پس PowerShell کلاً از مسیر بیرون رفت و `LIAM9.cmd`
فقط چند خط ASCII شد که پایتون را پیدا می‌کند و کار را به این‌جا می‌دهد.

## کارها

    python win_start.py run      روشن کن و روشن نگه دار (پیش‌فرض)
    python win_start.py doctor   فقط معاینه
    python win_start.py boot     با هر روشن‌شدن ویندوز خودش بالا بیاید
"""
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent          # claude-liam-signal/python
ROOT = HERE.parent.parent
ENVF = ROOT / "live.env"
OUT = ROOT / "signals" / "liam9d.out"
PORT = os.environ.get("LIAM9D_PORT", "9009")
TASK = "LiamTrader9"

# فقط مسیرهای کد از origin برداشته می‌شوند — نه دفترها. `git pull` معمولی
# این‌جا غلط است: سرویس هر دقیقه در signals/ و brain/ می‌نویسد و pull
# می‌خواهد آن نوشته‌ها را ادغام کند، پس دیر یا زود حمید پشت یک پیام
# conflict گیر می‌کند که هیچ ربطی به ترید ندارد. با برداشتنِ فقط کد،
# تصادم ساختاراً ممکن نیست.
CODE_PATHS = [
    "claude-liam-signal", "service", ".github", "config", "schemas",
    "prompts", "docs", ".claude", "scripts", "requirements-ci.txt",
    "index.html", "sw.js", "CLAUDE.md", "راهنمای-ویندوز.md",
    "LIAM9.cmd", "LIAM9-DOCTOR.cmd", "LIAM9-AUTOSTART.cmd",
]

ENV_TEMPLATE = """\
# توکن ربات تلگرام لیام تریدر ۹ — این فایل هرگز به گیت‌هاب نمی‌رود.
#
# دو خط آخر را پر کن، Ctrl+S بزن، و این پنجره را ببند.
#   TELEGRAM_BOT_TOKEN را از @BotFather بگیر (توکن @LiamTrader9_Bot).
#   TELEGRAM_CHAT_ID شناسهٔ عددی چت خودت است.

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
"""


def say(t=""):
    print(t, flush=True)


def _run(cmd, **kw):
    """اجرا بدون ترکیدن — روی ماشینِ حمید هیچ خطایی نباید حلقه را بکشد."""
    try:
        return subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                              text=True, timeout=kw.pop("timeout", 180), **kw)
    except Exception as e:                           # noqa: BLE001
        return subprocess.CompletedProcess(cmd, 1, "", f"{type(e).__name__}: {e}")


# ── ۱. آخرین نسخهٔ کد ──────────────────────────────────────────────────
def update_code():
    if not (ROOT / ".git").exists():
        return
    if _run(["git", "--version"], timeout=30).returncode != 0:
        say("  (گیت نصب نیست — با همین نسخه کار می‌کنم؛ برای نسخه‌های بعدی:")
        say("   winget install -e --id Git.Git)")
        return
    say("  → گرفتن آخرین نسخه از گیت‌هاب")
    if _run(["git", "fetch", "origin", "main", "-q"]).returncode != 0:
        say("    اینترنت نداد — با همین نسخه ادامه می‌دهم.")
        return
    have = [p for p in CODE_PATHS
            if _run(["git", "cat-file", "-e", f"origin/main:{p}"],
                    timeout=30).returncode == 0]
    if have:
        _run(["git", "checkout", "origin/main", "--", *have])
        _run(["git", "reset", "-q", "--", *have])    # از استیج در بیاور
    say("    کد به‌روز شد (دفترهای محلی دست‌نخورده).")


# ── ۲. توکن تلگرام ─────────────────────────────────────────────────────
def _env_value(txt, key):
    """مقدارِ یک کلید، خط‌به‌خط.

    نسخهٔ اول با `split(key)[1].strip()` می‌خواند و روی توکنِ **خالی**
    جواب غلط می‌داد: `strip()` خطِ خالی را جمع می‌کرد و خطِ بعدی
    (`TELEGRAM_CHAT_ID=`) را به‌عنوان مقدار برمی‌داشت. یعنی دکتر
    می‌گفت «توکن هست» در حالی که نبود — بدترین نوع خطا، چون حمید
    منتظر پیامی می‌ماند که هرگز نمی‌آید. اجرا شد، دیده شد، رفع شد.
    """
    for ln in txt.splitlines():
        ln = ln.strip()
        if ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return ""


def ensure_env():
    if ENVF.exists():
        txt = ENVF.read_text(encoding="utf-8", errors="replace")
        return bool(_env_value(txt, "TELEGRAM_BOT_TOKEN"))
    ENVF.write_text(ENV_TEMPLATE, encoding="utf-8")
    say()
    say("  فایل توکن ساخته شد و الان باز می‌شود.")
    say("  دو خط آخرش را پر کن، Ctrl+S بزن و پنجره را ببند.")
    say()
    try:
        subprocess.run(["notepad.exe", str(ENVF)], timeout=3600)
    except Exception:                                # noqa: BLE001
        say(f"  (خودت بازش کن: {ENVF})")
    return ensure_env() if ENVF.exists() else False


# ── ۳. معاینه ──────────────────────────────────────────────────────────
def doctor():
    return subprocess.run([sys.executable, "-m", "hamid.liam9d", "--doctor"],
                          cwd=str(HERE)).returncode


# ── ۴. همیشه‌روشن ──────────────────────────────────────────────────────
def boot():
    """با هر ورود به ویندوز خودش بالا بیاید — با schtasks، نه PowerShell."""
    cmd = str(ROOT / "LIAM9.cmd")
    r = _run(["schtasks", "/Create", "/TN", TASK,
              "/TR", f'cmd /c "{cmd}"', "/SC", "ONLOGON", "/RL", "LIMITED",
              "/F"], timeout=60)
    if r.returncode == 0:
        say("  ✓ از این به بعد با هر بار روشن‌شدن ویندوز، خودش بالا می‌آید.")
        say(f"    (برای لغو: schtasks /Delete /TN {TASK} /F)")
        return 0
    say("  ✗ ثبت نشد:")
    say(f"    {(r.stderr or r.stdout).strip()[:300]}")
    return 1


# ── ۵. حلقهٔ بی‌وقفه ────────────────────────────────────────────────────
def run():
    say()
    say("  لیام تریدر ۹ — سرویس محلی")
    say()
    update_code()
    has_token = ensure_env()
    if not has_token:
        say("  توکن خالی است — سرویس تحلیل می‌کند ولی به تلگرام چیزی نمی‌فرستد.")

    say()
    say("  معاینهٔ ماشین:")
    doctor()

    say()
    say(f"  پنل: http://127.0.0.1:{PORT}")
    say("  توقف: این پنجره را ببند")
    say(f"  لاگ: {OUT}")
    say()
    try:
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    except Exception:                                # noqa: BLE001
        pass

    n = 0
    while True:
        n += 1
        try:
            subprocess.run([sys.executable, "-m", "hamid.liam9d"], cwd=str(HERE))
        except KeyboardInterrupt:
            say("\n  خاموش شد.")
            return 0
        except Exception as e:                       # noqa: BLE001
            say(f"  {type(e).__name__}: {e}")
        say(f"  [{time.strftime('%H:%M:%S')}] سرویس ایستاد (بار {n}) — "
            "ده ثانیه دیگر دوباره")
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            say("\n  خاموش شد.")
            return 0


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    cmd = (argv[0] if argv else "run").lower()
    if cmd == "doctor":
        rc = doctor()
        try:
            input("\n  Enter بزن تا بسته شود ")
        except EOFError:
            pass
        return rc
    if cmd == "boot":
        rc = boot()
        try:
            input("\n  Enter بزن تا بسته شود ")
        except EOFError:
            pass
        return rc
    return run()


if __name__ == "__main__":
    sys.exit(main())
