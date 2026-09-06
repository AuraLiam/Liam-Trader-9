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

# ── ۳ب) فهرست‌ها مشتق باشند، نه دست‌نویس (رفعِ کلاس، ۶ سپتامبر) ────────
#
# سه حادثهٔ این مرحله (۲۷ اوت چارت، ۲ سپتامبر پنج فایل signals، ۶ سپتامبر
# کلِ مقصد ریشه) یک علت داشتند: **فهرستِ دست‌نویس**. تا وقتی فهرست
# دست‌نویس است، بررسیِ «آیا فلان اسم در متن هست؟» فقط حادثهٔ گذشته را
# می‌گیرد، نه حادثهٔ بعدی. پس ملاک عوض شد: فهرست باید از خودِ
# `index.html` استخراج شود و مقصدها حلقه بخورند.
pub = wf.split("PANEL_DESTS=", 1)[-1].split("cd /tmp/ghp", 1)[0]
check("مقصدهای پنل یک فهرست‌اند و حلقه می‌خورند (نه بلوکِ جدا برای هرکدام)",
      'PANEL_DESTS="/tmp/ghp /tmp/ghp/aura"' in wf and "for d in $PANEL_DESTS" in pub,
      pub[:200])
check("دارایی‌ها از خودِ index.html استخراج می‌شوند، نه تایپ‌شده",
      "grep -oE '(src|href)=" in pub)
check("فهرست signals هم از خودِ index.html می‌آید",
      "grep -oE '\\./signals/" in pub)
check("هر مقصد هم صفحه، هم دارایی، هم signals می‌گیرد",
      'cp index.html "$d/index.html"' in pub
      and 'for a in $ASSETS' in pub and 'for f in $WANTED' in pub)
# فقط خطوطِ فرمان سنجیده می‌شوند، نه توضیحات — پاسبانی که مستنداتِ
# خودش را جریمه کند، سه بار در همین مخزن آلارم کاذب داده.
_cmds = [ln.strip() for ln in wf.splitlines()
         if ln.strip() and not ln.strip().startswith("#")]
check("stage کامل است (مسیرِ دست‌نویس در git add، عیبِ وصلهٔ اولِ ۶ سپتامبر)",
      any(c == "git add -A" for c in _cmds)
      and not any(c.startswith("git add aura") for c in _cmds))

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
check("پنل دست‌کم چند فایل signals می‌خواند", len(fetched) >= 10, str(len(fetched)))
# فهرست دیگر تایپ نمی‌شود، پس چیزی برای «جا افتادن» نمانده — ولی همان
# regexِ استخراج باید واقعاً روی خودِ index.html جواب بدهد، وگرنه فهرست
# خالی می‌شود و هیچ فایلی منتشر نمی‌شود (خرابیِ ساکتِ تازه).
# استخراج باید روی خودِ صفحه جواب بدهد — فهرستِ خالی یعنی هیچ فایلی
# منتشر نمی‌شود، و آن خرابیِ ساکتِ تازه‌ای است که مشتق‌کردن می‌تواند
# بسازد. پس همان دو الگو این‌جا هم روی `index.html` اجرا می‌شوند.
_wf_signals = [c for c in _cmds if "grep -oE" in c and "signals/" in c]
_wf_assets = [c for c in _cmds if "grep -oE" in c and "src|href" in c]
check("ورک‌فلو فهرست signals را با grep از index.html می‌سازد",
      bool(_wf_signals), str(_cmds[:0]))
check("و فهرست دارایی را هم", bool(_wf_assets))
check("استخراجِ signals روی خودِ صفحه خالی درنمی‌آید",
      len(re.findall(r'\./signals/[A-Za-z0-9_-]+\.json', html)) >= 10)
check("استخراجِ دارایی روی خودِ صفحه خالی درنمی‌آید",
      len(re.findall(r'(?:src|href)="\./[A-Za-z0-9_.-]+\.(?:js|png|webmanifest)"',
                     html)) >= 1)

# ── ۵ب) شرطِ پایانی روی محصول است، نه اسکریپت ─────────────────────────
#
# هر سه حادثه یک ویژگی مشترک داشتند: اسکریپت سبز، محصول غلط. `cp` با
# `|| true` هرگز قرمز نمی‌شود و آزمونِ متنِ ورک‌فلو فقط می‌گوید «این خط
# نوشته شده»، نه «این فایل رسید». تنها بررسی‌ای که علتِ *بعدی* را هم
# می‌گیرد، مقایسهٔ هشِ منتشرشده با مبدأ است.
check("مرحلهٔ راستی‌آزمایی پنلِ منتشرشده وجود دارد",
      "راستی‌آزمایی پنلِ منتشرشده" in wf)
check("و هش را با مبدأ مقایسه می‌کند (نه صرفاً وجود فایل)",
      "git hash-object index.html" in wf
      and 'git rev-parse "origin/gh-pages:$p"' in wf)
check("هر دو آدرس راستی‌آزمایی می‌شوند (ریشه و /aura/)",
      "for p in index.html aura/index.html" in wf)
check("کهنه‌بودنِ پنل مرحله را قرمز می‌کند، نه اینکه فقط چاپ شود",
      re.search(r'\[ "\$BAD" = "0" \] \|\|.*?exit 1', wf, re.S) is not None)


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
check("ریشه (آدرس اصلی حمید) یکی از مقصدهاست",
      "/tmp/ghp " in wf.split("PANEL_DESTS=", 1)[-1][:60]
      or 'PANEL_DESTS="/tmp/ghp ' in wf,
      "ریشه ناشر ندارد — همان عیبِ ۱۹روزهٔ ۶ سپتامبر")
check("و /aura/ هم می‌ماند (بوکمارک‌های قبلی نمی‌شکنند)",
      "/tmp/ghp/aura" in wf.split("PANEL_DESTS=", 1)[-1][:60])

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
