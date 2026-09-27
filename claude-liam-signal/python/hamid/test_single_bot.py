"""پاسبان تک‌باتی و تک‌گیت‌هابی — دستور صریح حمید، ۲۰ اوت (+ استثنای ۲۷ سپتامبر).

«سیگنال‌ها فقط روی یک بات: @LiamTrader9_Bot. هر بات اضافه از کدها پاک شود.
همه‌چیز فقط روی گیت‌هاب Auraliam؛ هر ریپوی دیگری بیرون.»

این آزمون همان دو مرز را قفل می‌کند. اگر روزی کسی (از جمله خود من) مقصد
دومی اضافه کرد یا ارجاعی به ریپوی دیگری گذاشت، این‌جا سرخ می‌شود.

پیش‌زمینه: ۱۴ اوت یک «آینهٔ مقصد دوم» اضافه شده بود و همان باعث شد سیگنال
لیام تریدر ۹ به بیش از یک بات برسد. ۲۰ اوت کامل برداشته شد.
"""
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


# فایل‌هایی که تاریخ‌اند، نه کدِ زنده: پشتیبان، گزارش چرخه، مستند قدیمی.
SKIP_DIRS = (".git", "node_modules", "backup", "cycles", "__pycache__",
             # محیط پایتونِ محلی و هر پوشهٔ وابستگیِ شخص ثالث. بدون
             # این، اولین باری که سرویس محلی `.venv` می‌سازد، پاسبان
             # کدِ Pillow را «کد زندهٔ ما» می‌شمارد و چرخه سرخ می‌شود
             # — اندازه‌گیری‌شده روی همین ماشین، ۴ سپتامبر.
             ".venv", "venv", "env", "site-packages", ".tox",
             ".mypy_cache", ".pytest_cache", ".ruff_cache")
LIVE_EXT = (".py", ".js", ".yml", ".yaml", ".html", ".mjs")


def live_files():
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in LIVE_EXT:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def run():
    # ── ۱) هیچ مقصد دوم تلگرامی در کد زنده ─────────────────────────────
    BANNED_TG = ("TELEGRAM_BOT_TOKEN_2", "TELEGRAM_CHAT_ID_2",
                 "TG_TOKEN", "TG_CHAT", "HAMID_CHAT_ID",
                 "BOT_TOKEN_3", "CHAT_ID_3")
    hits = []
    for p in live_files():
        if p.name == Path(__file__).name:
            continue                                  # خودِ پاسبان
        txt = p.read_text(errors="ignore")
        for b in BANNED_TG:
            if b in txt:
                hits.append(f"{p.relative_to(ROOT)}: {b}")
    check("هیچ متغیر بات دوم/سوم در کد زنده نیست", not hits, "؛ ".join(hits[:6]))

    # ── ۲) تنها آینهٔ مجاز: سیگنال به بات دوم (دستور صریح حمید، ۲۷ سپتامبر) ──
    #
    # مرز قرمز ۲۰ اوت لغو نشد؛ یک استثنای محدود با شرط‌های قابل‌سنجش گرفت.
    tg = (PY / "telegram.py").read_text()
    check("telegram.py فقط یک جفت اعتبارنامهٔ اصلی می‌خواند",
          tg.count("TELEGRAM_BOT_TOKEN") >= 1 and "TELEGRAM_BOT_TOKEN_2" not in tg)
    check("آینهٔ قدیمی (۱۴ اوت) برنگشته",
          "creds2" not in tg and "MIRROR_METHODS" not in tg and "def _mirror" not in tg)
    body = tg[tg.index("def send_signals"):]
    _end = body.find("\ndef ", 10)
    body = body if _end < 0 else body[:_end]
    calls = [ln for ln in tg.splitlines()
             if "mirror_signal(" in ln and "def mirror_signal" not in ln]
    check("آینه فقط یک جا صدا زده می‌شود: داخل send_signals",
          len(calls) == 1 and "mirror_signal(s, png, cap_full)" in body, str(calls))
    check("آینه فقط بعد از تحویلِ تأییدشده روی بات اصلی",
          body.index("if tg_mid:\n                mirror_signal(") > body.index("_save_sent(sent)"))
    check("scrub توکن آینه را هم می‌پوشاند", '"SIGNAL_MIRROR_BOT_TOKEN"' in
          tg[tg.index("def scrub"):tg.index("def scrub") + 900])
    # رفتاری: بی سکرت آینه خاموش است؛ با سکرت، شکستش استثنا بیرون نمی‌دهد
    import os as _os
    sys.path.insert(0, str(PY))
    import telegram as _T
    for k in _T.MIRROR_ENV:
        _os.environ.pop(k, None)
    check("بی هر دو سکرت، آینه خاموش است", _T.mirror_signal({"sym": "X"}, None, "c") is False)
    _os.environ.update({_T.MIRROR_ENV[0]: "1:x", _T.MIRROR_ENV[1]: "1"})
    _op = _T._post_once
    _T._post_once = lambda *a, **k: (_ for _ in ()).throw(OSError("boom 1:x"))
    try:
        r = _T.mirror_signal({"sym": "X"}, None, "caption")
    except Exception:                                  # noqa: BLE001
        r = "raised"
    finally:
        _T._post_once = _op
        for k in _T.MIRROR_ENV:
            _os.environ.pop(k, None)
    check("شکستِ آینه استثنا بیرون نمی‌دهد (بات اصلی آسیب نمی‌بیند)", r is False, str(r))

    # ── ۳) سکرت آینه فقط در سه گامِ ارسالِ سیگنال ─────────────────────────
    ALLOWED_WF = {"pump-radar.yml", "live-scan.yml", "hamid-cycle.yml"}
    wf_hits, mirror_wf = [], set()
    for p in (ROOT / ".github" / "workflows").glob("*.yml"):
        t = p.read_text()
        for b in ("TELEGRAM_BOT_TOKEN_2", "TELEGRAM_CHAT_ID_2"):
            if b in t:
                wf_hits.append(f"{p.name}: {b}")
        if "SIGNAL_MIRROR_" in t:
            mirror_wf.add(p.name)
    check("هیچ ورک‌فلویی سکرت‌های ممنوعِ بات دوم را پاس نمی‌دهد", not wf_hits,
          "؛ ".join(wf_hits[:6]))
    check("سکرت آینه فقط به گام‌های ارسال سیگنال می‌رسد", mirror_wf <= ALLOWED_WF,
          str(sorted(mirror_wf - ALLOWED_WF)))
    stray = [str(p.relative_to(ROOT)) for p in live_files()
             if p.suffix == ".py" and p.name not in ("telegram.py", Path(__file__).name)
             and "SIGNAL_MIRROR_" in p.read_text(errors="ignore")]
    check("هیچ ماژول دیگری آینه را نمی‌خواند", not stray, str(stray))

    # ── ۴) فقط گیت‌هاب Auraliam ────────────────────────────────────────
    # ارجاع به هر مالک دیگری در کد زنده ممنوع است. «actions/» استثناست
    # چون اکشن‌های رسمی گیت‌هاب‌اند، نه ریپوی ما.
    # «repos» وقتی به‌تنهایی می‌ماند یعنی api.github.com/repos/<متغیر>/
    # که همیشه به همین ریپو (Auraliam) حل می‌شود، نه مالکی دیگر.
    # ranaroussi فقط نام کتابخانهٔ پایتون (quantstats) در رجیستری است، نه
    # اتصال به ریپو — اتصال واقعی فقط همان origin است که به Auraliam می‌رود.
    ALLOWED_OWNERS = {"auraliam", "actions", "ranaroussi", "repos"}
    repo_hits = []
    pat = re.compile(r"(?:api\.)?github\.com/(?:repos/)?([A-Za-z0-9_.-]+)/")
    for p in live_files():
        if p.name == Path(__file__).name:
            continue
        for m in pat.finditer(p.read_text(errors="ignore")):
            owner = m.group(1).lower()
            if owner not in ALLOWED_OWNERS:
                repo_hits.append(f"{p.relative_to(ROOT)}: {m.group(1)}")
    check("هیچ ارجاعی به گیت‌هاب غیر Auraliam در کد زنده نیست",
          not repo_hits, "؛ ".join(sorted(set(repo_hits))[:8]))

    # ── بزرگی حروف آدرس پنل (پروندهٔ «پنل بالا نمی‌آید»، ۲۰ اوت) ────────
    #
    # ریپو `AuraLiam/Liam-Trader-9` است و GitHub Pages به بزرگی حروف حساس:
    # auraliam.github.io/liam-trader-9 یعنی ۴۰۴. چهار فایل داشبوردی همان
    # املای غلط را داشتند، پس sync پارامتر/تجربه بی‌صدا شکست می‌خورد و
    # لینک قدیمی پنل بالا نمی‌آمد. این بررسی برگشتش را ناممکن می‌کند.
    bad_urls = ("auraliam.github.io/liam-trader-9",
                "githubusercontent.com/Auraliam/liam-trader-9")
    wrong = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in LIVE_EXT:
            continue
        if any(d in p.parts for d in SKIP_DIRS) or p.name == Path(__file__).name:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:                            # noqa: BLE001
            continue
        for bad in bad_urls:
            if bad in t:
                wrong.append(f"{p.relative_to(ROOT)}: {bad}")
    check("آدرس پنل/raw با املای درست ریپو است (Pages حساس به حروف)",
          not wrong, "؛ ".join(wrong[:5]))

    print()
    if FAIL:
        print(f"✗ {len(FAIL)} آزمون شکست: {FAIL}")
        raise SystemExit(1)
    print(f"✓ همهٔ {OK} آزمون تک‌باتی/تک‌گیت‌هابی گذشت")


if __name__ == "__main__":
    run()
