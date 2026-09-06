"""پاسبان قرارداد پنل (ممیزی ساختار، ۲۷ اوت).

چهار عیبِ اندازه‌گیری‌شده که این آزمون برگشتشان را ناممکن می‌کند:

۱. **نسخهٔ کش و نسخهٔ صفحه واگرا شدند.** CLAUDE.md بامپِ `CACHE` را در هر
   دیپلوی اجباری کرده بود ولی هیچ‌چیز اجرایش نمی‌کرد — روی gh-pages
   صفحهٔ v21.32 کنار کشِ v21.35 نشسته بود.
۲. **محافظِ «پنل کهنه است» مرده بود.** نام کش از `hsa-shell` به
   `auraliam-shell` عوض شد ولی regex قدیمی ماند؛ `server` همیشه
   undefined می‌شد و نه رفرش خودکار رخ می‌داد نه بنر هشدار.
۳. **کتابخانهٔ چارت کنار پنل منتشر نمی‌شد.** `index.html` مسیر نسبی
   `./lightweight-charts.js` را لود می‌کند و زیر `/aura/` نبود → ۴۰۴؛
   و چون `sw.js` از `addAll` اتمی استفاده می‌کند، همان یک ۴۰۴ کل کش را
   رد می‌کرد.
۴. **عددِ ساخته‌نشده روی پنل چاپ می‌شد.** `(s.ev||0).toFixed(2)` مقدارِ
   نداشته را «انتظار ریاضی 0.00R» نشان می‌داد — نقض «هیچ عددی ساخته
   نمی‌شود» (قانون سیگنال اجباری ممنوع).
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

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


html = (ROOT / "index.html").read_text(encoding="utf-8")
sw = (ROOT / "sw.js").read_text(encoding="utf-8")
wf = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")

# ── ۱) نسخهٔ صفحه و نسخهٔ کش باید یکی باشند ─────────────────────────────
m_page = re.search(r'id="ver">cycle v([\d.]+)', html)
m_cache = re.search(r'CACHE = "auraliam-shell-v([\d.]+)"', sw)
check("نسخهٔ صفحه در index.html پیدا می‌شود", bool(m_page))
check("نسخهٔ کش در sw.js پیدا می‌شود", bool(m_cache))
check("نسخهٔ کش با نسخهٔ صفحه یکی است (بامپ فراموش نشده)",
      bool(m_page and m_cache) and m_page.group(1) == m_cache.group(1),
      f"صفحه={m_page and m_page.group(1)} کش={m_cache and m_cache.group(1)}")

# ── ۲) محافظِ کهنگیِ پنل باید نام واقعیِ کش را بشناسد ───────────────────
m_re = re.search(r"t\.match\(/([^/]+)/\)", html)
check("regexِ تشخیص نسخهٔ سرور در پنل هست", bool(m_re), str(m_re))
if m_re and m_cache:
    pat = m_re.group(1)
    probe = f"CACHE = \"auraliam-shell-v{m_cache.group(1)}\""
    try:
        hit = re.search(pat, probe)
    except re.error as e:                            # noqa: BLE001
        hit = None
        print(f"      ↳ regex نامعتبر: {e}")
    check("همان regex نسخه را از محتوای واقعی sw.js بیرون می‌کشد "
          "(محافظ کهنگی زنده است)",
          bool(hit) and hit.group(1) == m_cache.group(1),
          f"pattern={pat}")

# ── ۳) هر چیزی که پنل لود می‌کند باید کنارش منتشر شود ───────────────────
needed = set(re.findall(r'(?:src|href)="\./([A-Za-z0-9_.-]+\.(?:js|png|webmanifest))"', html))
check("پنل دست‌کم کتابخانهٔ چارت را با مسیر نسبی لود می‌کند",
      "lightweight-charts.js" in needed, str(sorted(needed)))
pub = wf.split("mkdir -p /tmp/ghp/aura", 1)[-1].split("cd /tmp/ghp", 1)[0]
missing = [f for f in needed if f not in pub and f not in ("sw.js",)]
check("همهٔ دارایی‌های نسبیِ پنل در مرحلهٔ انتشار /aura/ کپی می‌شوند",
      not missing, f"کپی‌نشده: {missing}")

# ── ۴) عددِ ساخته‌نشده چاپ نمی‌شود ──────────────────────────────────────
check("انتظار ریاضیِ نداشته دیگر ۰.۰۰R نشان داده نمی‌شود",
      "(s.ev||0).toFixed(2)" not in html)
check("چیپ اعتماد/انتظار/پولبک روی مقدار null ساخته نمی‌شود",
      's.conf==null?""' in html and 's.ev==null?""' in html
      and 's.visits==null?""' in html)

# ── ۵) هر فایل signals که پنل می‌خواند باید به /aura/signals/ برسد ─────────
# عیبِ اندازه‌گیری‌شدهٔ ۲ سپتامبر: پنل ./signals/system-state.json و
# loop-audit و bubbles و telegram-feed را می‌خواند ولی فهرست کپیِ مرحلهٔ
# انتشار آن‌ها را نداشت — روی آدرس واقعی (/aura/) دو کارت همیشه «هنوز
# ساخته نشده» نشان می‌دادند. کلاس عیب: کارت تازه بی‌فهرست.
fetched = sorted(set(re.findall(r'\./signals/([A-Za-z0-9_-]+)\.json', html)))
m_wl = re.search(r'for f in (.*?); do\s*\n\s*cp "signals/\$f\.json" /tmp/ghp/aura', wf, re.S)
whitelist = set(m_wl.group(1).replace("\\\n", "").split()) if m_wl else set()
not_deployed = [f for f in fetched if f not in whitelist]
check("فهرست کپی مرحلهٔ انتشار پیدا می‌شود", bool(m_wl))
check("هر signals/*.json که پنل می‌خواند در فهرست انتشار /aura/ هست",
      bool(fetched) and not not_deployed, f"کپی‌نشده: {not_deployed}")


# ── ۶) ریشه هم باید ناشر داشته باشد، نه فقط /aura/ ─────────────────────
#
# عیبِ اندازه‌گیری‌شدهٔ ۶ سپتامبر — و علتِ این‌که ۱۹ روز کسی نفهمید:
# همهٔ پنج بررسی بالا فقط `/aura/` را می‌سنجیدند. مرحلهٔ انتشار هم فقط
# آن‌جا می‌نوشت، پس `index.html` **ریشه** روی gh-pages از ۱۸ اوت
# ۲۰:۱۷ UTC دست‌نخورده ماند (کش v21.35 در برابر v21.46 روی main) در
# حالی که `signals/` ریشه هر ۳ دقیقه تازه می‌شد — عددِ تازه در کارتِ
# کهنه، بدون هیچ خطایی.
#
# کلاسِ عیب: **پاسبانی که فقط یک آدرس را می‌بیند، آدرس دیگر را
# نامرئی می‌کند.** حالا هر دو اجباری‌اند.
check("پنل به ریشه هم منتشر می‌شود (آدرس اصلی حمید)",
      "cp index.html /tmp/ghp/index.html" in wf
      and "cp sw.js      /tmp/ghp/sw.js" in wf,
      "ریشه ناشر ندارد — همان عیبِ ۱۹روزهٔ ۶ سپتامبر")
_root_pub = wf.split("cp index.html /tmp/ghp/index.html", 1)[-1].split(
    "cd /tmp/ghp", 1)[0]
_missing_root = [f for f in needed if f not in _root_pub and f != "sw.js"]
check("دارایی‌های نسبیِ پنل به ریشه هم می‌روند (وگرنه ۴۰۴ و کشِ ردشده)",
      not _missing_root, f"کپی‌نشده در ریشه: {_missing_root}")
check("فهرست signals هم به ریشه کپی می‌شود",
      'cp "signals/$f.json" /tmp/ghp/signals/' in wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
