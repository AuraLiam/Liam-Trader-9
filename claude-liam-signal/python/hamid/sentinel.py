"""نگهبان یکپارچگی ریپو — «هیچ‌کس جز خودمان چیزی این‌جا نگذارد»
(دستور حمید، ۲۰ اوت).

چیزی که حمید خواست: «هیچ هوش مصنوعی دیگر یا حتی یک چت جدید نتواند فایلی
در گیت‌هاب بارگذاری و اجرا کند.»

صادقانه: **رمزنگاری فایل‌ها این را نمی‌دهد** — کسی که اجازهٔ push دارد،
چه فایل رمز باشد چه نباشد، می‌تواند بنویسد؛ و کد رمزشده را نه Actions
اجرا می‌کند نه مرورگر می‌خواند. آنچه واقعاً جلوی نوشتن را می‌گیرد فقط
دسترسی گیت‌هاب است (تنظیمات حساب حمید). کاری که کد می‌تواند بکند این
است: **هر ورودِ ناشناس را همان لحظه ببیند و داد بزند.**

این نگهبان سه چیز را می‌پاید:

۱. **نویسندهٔ هر کامیت** — هر کامیت روی main باید از فهرست سفید باشد.
   کامیت با نویسندهٔ ناشناس = نفوذ یا حساب لو رفته → آلارم.
۲. **ورک‌فلوها** — مسیر کلاسیک حمله: یک ورک‌فلوی تازه که سکرت‌ها را
   بیرون می‌فرستد. اثر انگشت همهٔ ورک‌فلوها ثبت می‌شود؛ فایل تازه یا
   عوض‌شدهٔ ثبت‌نشده → آلارم.
۳. **نشت سکرت** — الگوی توکن تلگرام/کلید در فایل‌های سورس‌کنترل‌شده.

خروجی: `signals/sentinel.json` + آلارم تلگرام روی تغییر مشکوک.
مرجع مورد انتظار: `brain/sentinel-baseline.json` (خودش بار اول ساخته
می‌شود؛ تغییر عمدی با `--accept` تأیید می‌شود).

    python3 -m hamid.sentinel            # بررسی
    python3 -m hamid.sentinel --accept   # تغییرات فعلی را مرجع کن
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
WF = ROOT / ".github" / "workflows"
BASELINE = ROOT / "brain" / "sentinel-baseline.json"
OUT = ROOT / "signals" / "sentinel.json"

# فهرست سفید نویسنده‌ها — فقط این‌ها حق نوشتن روی main دارند.
# فهرست سفید از خودِ ورک‌فلوهای ریپو استخراج شده — هر نامی که این‌جا
# نیست یعنی از بیرونِ سیستم نوشته شده (تأییدشده ۲۰ اوت: Conformance
# نویسندهٔ ورک‌فلوی conformance.yml خودمان است، نه غریبه).
ALLOWED_AUTHORS = {
    "claude", "hamid signal agent", "auraliam", "github-actions[bot]",
    "github-actions", "hamid", "conformance",
    # حساب گیت‌هاب خودِ حمید (صاحب ریپو). merge از روی دکمه/API گیت‌هاب
    # کامیتی با همین هویت می‌سازد؛ ۲۴ اوت نبودنش در فهرست، اولین merge
    # را «نویسندهٔ ناشناس» گرفت و چون این آزمون در دروازهٔ سخت است، همهٔ
    # چرخه‌های بعدش قرمز شدند و سیگنال از کار افتاد. صاحبِ ریپو بنا به
    # تعریف خودی است — غریبه گرفتنش آلارم کاذب از جنسِ «پیام بی‌معنی» است.
    "auraliam9",
}
ALLOWED_EMAILS_SUFFIX = (
    "@users.noreply.github.com", "@anthropic.com", "@privaterelay.appleid.com",
    "@liam9.ai",          # ورک‌فلوهای خودِ ریپو (conformance و هم‌خانواده)
)
# ایمیل‌های دقیقِ خودی — نه پسوندی. ایمیلِ کامیتِ حساب حمید در کل تاریخچهٔ
# عمومی ریپو هست؛ فهرست‌کردنش این‌جا افشای چیزی نیست، شناساندنِ صاحب است.
# «noreply@github.com» هویتِ committer در هر merge سرورسایدِ گیت‌هاب است
# (author = حساب کاربر، committer = خودِ GitHub) — بررسی نویسنده روی هر
# دو می‌نشیند، پس بدون این، هر merge از دکمه/API «ناشناس» می‌شد؛ رفعِ
# اولِ ۲۴ اوت فقط author را دید و همان بررسی دوباره افتاد.
ALLOWED_EMAILS_EXACT = {"18r.liam@gmail.com", "noreply@github.com"}

SECRET_PAT = [
    (re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"), "توکن ربات تلگرام"),
    (re.compile(r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{24,}"),
     "کلید/توکن هاردکدشده"),
]
SKIP_DIRS = (".git", "node_modules", "backup", "cycles", "__pycache__",
             # محیط پایتونِ محلی و هر پوشهٔ وابستگیِ شخص ثالث. بدون
             # این، اولین باری که سرویس محلی `.venv` می‌سازد، پاسبان
             # کدِ Pillow را «کد زندهٔ ما» می‌شمارد و چرخه سرخ می‌شود
             # — اندازه‌گیری‌شده روی همین ماشین، ۴ سپتامبر.
             ".venv", "venv", "env", "site-packages", ".tox",
             ".mypy_cache", ".pytest_cache", ".ruff_cache")
SCAN_EXT = (".py", ".js", ".mjs", ".html", ".yml", ".yaml", ".json", ".md")


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=60).stdout.strip()
    except Exception:                                # noqa: BLE001
        return ""


def workflow_prints():
    """اثر انگشت هر ورک‌فلو — نام → sha256 محتوا."""
    out = {}
    if WF.exists():
        for p in sorted(WF.glob("*.yml")):
            out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def recent_authors(n=80):
    """نویسنده و کامیت‌کنندهٔ n کامیت آخر main."""
    raw = _git("log", f"-{n}", "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%s")
    rows = []
    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 6:
            rows.append({"sha": parts[0][:8], "an": parts[1], "ae": parts[2],
                         "cn": parts[3], "ce": parts[4], "subject": parts[5][:60]})
    return rows


def _last_touch_known(wf_name):
    """آخرین کامیتی که این ورک‌فلو را دست زده، خودی بوده؟

    مبنای تصمیمِ «آلارم یا پذیرش خودکار». اگر تاریخچه در دسترس نبود
    (کلون کم‌عمق)، صادقانه False — یعنی سمتِ احتیاط، نه سمتِ سکوت."""
    raw = _git("log", "-1", "--format=%an%x1f%ae%x1f%cn%x1f%ce",
               "--", f".github/workflows/{wf_name}")
    parts = (raw.splitlines() or [""])[0].split("\x1f")
    if len(parts) != 4:
        return False
    return _known(parts[0], parts[1]) and _known(parts[2], parts[3])


def strangers_absent():
    """در کامیت‌های اخیر هیچ نویسندهٔ ناشناسی نیست؟"""
    return not [r for r in recent_authors()
                if not (_known(r["an"], r["ae"]) and _known(r["cn"], r["ce"]))]


def _known(name, email):
    if (name or "").strip().lower() in ALLOWED_AUTHORS:
        return True
    if (email or "").strip().lower() in ALLOWED_EMAILS_EXACT:
        return True
    return any((email or "").lower().endswith(s) for s in ALLOWED_EMAILS_SUFFIX)


def scan_secrets():
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in SCAN_EXT:
            continue
        if any(d in p.parts for d in SKIP_DIRS) or p.name == Path(__file__).name:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:                            # noqa: BLE001
            continue
        for pat, label in SECRET_PAT:
            if pat.search(t):
                hits.append(f"{p.relative_to(ROOT)}: {label}")
                break
    return hits


def check(accept=False):
    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text())
        except Exception:                            # noqa: BLE001
            base = {}
    now_wf = workflow_prints()
    old_wf = base.get("workflows") or {}
    findings = []

    # ۱) ورک‌فلوها
    #
    # درس ۲۷ اوت («این پیام‌ها نباید تکرار بشه»): ۸ ورک‌فلوی تازه که
    # خودِ ایجنت با کامیتِ امضادار ساخته بود، به حمید پیامِ «مسیر کلاسیک
    # نشت سکرت» داد. تغییرِ ورک‌فلو توسط **نویسندهٔ خودی** رویدادِ عادیِ
    # هر روز است، نه نفوذ — همان کلاسِ آلارمِ کاذبِ merge (قانون ۰۷ بند
    # ۲): پاسبانی که رویدادِ عادی را تهدید بگیرد، خودش خرابی است. حالا:
    # نویسندهٔ خودی → ثبتِ info + پذیرش خودکار در مرجع، بدون تلگرام؛
    # نویسندهٔ ناشناس → همان آلارم high قبلی.
    added = sorted(set(now_wf) - set(old_wf))
    removed = sorted(set(old_wf) - set(now_wf))
    changed = sorted(k for k in now_wf if k in old_wf and now_wf[k] != old_wf[k])
    self_change = False
    if old_wf:
        for a in added:
            if _last_touch_known(a):
                findings.append({"level": "info", "kind": "workflow_added",
                                 "what": a,
                                 "why": "ورک‌فلوی تازه با کامیت خودی — در مرجع ثبت شد"})
                self_change = True
            else:
                findings.append({"level": "high", "kind": "workflow_added",
                                 "what": a,
                                 "why": "ورک‌فلوی تازه با نویسندهٔ ناشناس — مسیر کلاسیک نشت سکرت"})
        for r in removed:
            findings.append({"level": "info" if strangers_absent() else "medium",
                             "kind": "workflow_removed", "what": r,
                             "why": "ورک‌فلوی ثبت‌شده حذف شده"})
            if strangers_absent():
                self_change = True
        for c in changed:
            if _last_touch_known(c):
                findings.append({"level": "info", "kind": "workflow_changed",
                                 "what": c, "why": "تغییر با کامیت خودی — مرجع به‌روز شد"})
                self_change = True
            else:
                findings.append({"level": "medium", "kind": "workflow_changed",
                                 "what": c, "why": "محتوای ورک‌فلو با نویسندهٔ ناشناس عوض شده"})

    # ۲) نویسندهٔ کامیت‌ها
    strangers = [r for r in recent_authors()
                 if not (_known(r["an"], r["ae"]) and _known(r["cn"], r["ce"]))]
    for s in strangers[:10]:
        findings.append({"level": "high", "kind": "unknown_author",
                         "what": f"{s['sha']} · {s['an']} <{s['ae']}>",
                         "why": "کامیت از نویسندهٔ خارج از فهرست سفید"})

    # ۳) نشت سکرت
    for h in scan_secrets():
        findings.append({"level": "high", "kind": "secret_leak", "what": h,
                         "why": "سکرت باید فقط در محیط باشد، نه در ریپو"})

    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "workflows_tracked": len(now_wf),
           "commits_checked": len(recent_authors()),
           "findings": findings,
           "verdict": ("پاک" if not any(f["level"] in ("high", "medium")
                                        for f in findings) else
                       f"{sum(1 for f in findings if f['level'] in ('high', 'medium'))} "
                       "مورد مشکوک — بررسی لازم است"),
           "note": ("این نگهبان جلوی نوشتن را نمی‌گیرد (آن کار تنظیمات "
                    "دسترسی گیت‌هاب است) — ورودِ ناشناس را می‌بیند و "
                    "همان لحظه اعلام می‌کند.")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))

    # پذیرش خودکارِ تغییرِ خودی: وقتی همهٔ تغییرهای ورک‌فلو با کامیت
    # امضادارِ خودی بوده و هیچ یافتهٔ high/medium ای در کار نیست، مرجع
    # همان لحظه به‌روز می‌شود تا همین یافته دور بعد دوباره ساخته نشود.
    # تغییرِ ناشناس هرگز خودکار پذیرفته نمی‌شود — فقط --accept دستی.
    auto_ok = self_change and not any(
        f["level"] in ("high", "medium") for f in findings)
    if accept or not old_wf or auto_ok:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(
            {"accepted_at": int(time.time() * 1000), "workflows": now_wf},
            ensure_ascii=False, indent=1))
    return res


def alert(res):
    """فقط تخلف high به تلگرام می‌رود — سروصدای بی‌مورد ممنوع (قانون ۰۷).

    و فقط **یک بار** برای هر مجموعهٔ یافته (۲۳ اوت): تا امروز این تابع
    حافظه نداشت، پس تا وقتی یک ورک‌فلوی ثبت‌نشده روی مرجع نمی‌نشست، همان
    هشدارِ «مسیر کلاسیک نشت سکرت» هر ۳۰ دقیقه تکرار می‌شد. حالا از
    دروازهٔ مشترک رد می‌شود: کلید = مجموعهٔ یافته‌های high."""
    high = [f for f in res["findings"] if f["level"] == "high"]
    from hamid import alert_gate
    key = ",".join(sorted(f"{f['kind']}:{f['what']}" for f in high))
    ok, _reason = alert_gate.decide("sentinel", key)
    if not ok:
        return False
    if not high:
        # «پیامِ برطرف شد نباید برای من بیاید» (دستور صریح ۲۶ اوت، قانون
        # ۱۱ بند ۳) — بهبود فقط در لاگ/پنل ثبت می‌شود، تلگرام ساکت.
        print("نگهبان: مورد مشکوک قبلی برطرف شد — فقط لاگ، بدون تلگرام")
        return False
    try:
        from telegram import creds, _post
    except Exception:                                # noqa: BLE001
        return False
    token, chat = creds()
    if not token:
        return False
    lines = ["🛡 <b>نگهبان یکپارچگی — لیام تریدر ۹</b>", ""]
    for f in high[:8]:
        lines.append(f"• <b>{f['kind']}</b>: {f['what']}\n  {f['why']}")
    lines.append("\nاگر کار خودت نبوده، همین حالا دسترسی‌های گیت‌هاب را بررسی کن.")
    _post(token, "sendMessage",
          {"chat_id": chat, "text": "\n".join(lines), "parse_mode": "HTML"})
    return True


if __name__ == "__main__":
    r = check(accept="--accept" in sys.argv)
    print(f"نگهبان: {r['verdict']} · {r['workflows_tracked']} ورک‌فلو · "
          f"{r['commits_checked']} کامیت بررسی شد")
    for f in r["findings"][:12]:
        print(f"  [{f['level']}] {f['kind']}: {f['what']}")
    if "--alert" in sys.argv and alert(r):
        print("آلارم تلگرام فرستاده شد")
    sys.exit(1 if any(f["level"] == "high" for f in r["findings"]) else 0)
