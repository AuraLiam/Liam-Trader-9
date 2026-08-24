"""پاسبان نگهبان یکپارچگی — همراه اجباری sentinel.py (قانون رفع قطعی).

نگهبانی که خودش آزمون ندارد، فقط یک ادعای امنیتی است. این آزمون ثابت
می‌کند سه تشخیص واقعاً کار می‌کنند: ورک‌فلوی تازه، نویسندهٔ ناشناس،
سکرت لو رفته — و اینکه حالت پاک، آلارم کاذب نمی‌دهد.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import sentinel as S            # noqa: E402

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


# فهرست سفید: خودی‌ها شناخته می‌شوند، غریبه نه
check("کامیت ایجنت خودی شناخته می‌شود",
      S._known("Claude", "noreply@anthropic.com"))
check("ورک‌فلوی conformance خودی است",
      S._known("Conformance", "conformance@liam9.ai"))
check("ربات اکشنز خودی است",
      S._known("github-actions[bot]", "actions@users.noreply.github.com"))
check("نویسندهٔ غریبه رد می‌شود",
      not S._known("Some Other AI", "bot@example.com"))
check("ایمیل ناشناس با نام جعلیِ شبیه خودی هم بدون دامنهٔ مجاز رد می‌شود",
      not S._known("claude-fake", "attacker@evil.tld"))

# تشخیص ورک‌فلوی تازه/عوض‌شده روی مرجع ساختگی
real_base, real_out = S.BASELINE, S.OUT
tmp_base = S.ROOT / "brain" / "sentinel-baseline-test.json"
tmp_out = S.ROOT / "signals" / "sentinel-test.json"
S.BASELINE, S.OUT = tmp_base, tmp_out
try:
    now = S.workflow_prints()
    check("اثر انگشت ورک‌فلوها گرفته می‌شود", len(now) > 5, str(len(now)))
    # مرجعی که یک فایل کمتر و یکی دست‌کاری‌شده دارد
    fake = dict(now)
    victim = sorted(fake)[0]
    fake[victim] = "0000deadbeef0000"
    dropped = sorted(fake)[1]
    del fake[dropped]
    tmp_base.write_text(json.dumps({"accepted_at": int(time.time() * 1000),
                                    "workflows": fake}, ensure_ascii=False))
    r = S.check(accept=False)
    kinds = {f["kind"] for f in r["findings"]}
    check("ورک‌فلوی تازهٔ ثبت‌نشده high گرفته می‌شود",
          any(f["kind"] == "workflow_added" and f["level"] == "high"
              for f in r["findings"]), str(sorted(kinds)))
    check("ورک‌فلوی عوض‌شده تشخیص داده می‌شود", "workflow_changed" in kinds)
    check("خروجی نگهبان نوشته می‌شود", tmp_out.exists())

    # حالت پاک: مرجع = وضعیت فعلی → هیچ یافته‌ای از جنس ورک‌فلو
    tmp_base.write_text(json.dumps({"accepted_at": int(time.time() * 1000),
                                    "workflows": now}, ensure_ascii=False))
    r2 = S.check(accept=False)
    wf_findings = [f for f in r2["findings"] if f["kind"].startswith("workflow")]
    check("وضعیت هم‌خوان آلارم کاذب نمی‌دهد", not wf_findings,
          str(wf_findings[:2]))
    check("ریپوی فعلی نشت سکرت ندارد",
          not [f for f in r2["findings"] if f["kind"] == "secret_leak"],
          str([f["what"] for f in r2["findings"] if f["kind"] == "secret_leak"][:3]))
    check("ریپوی فعلی نویسندهٔ ناشناس ندارد",
          not [f for f in r2["findings"] if f["kind"] == "unknown_author"],
          str([f["what"] for f in r2["findings"]
               if f["kind"] == "unknown_author"][:3]))
finally:
    S.BASELINE, S.OUT = real_base, real_out
    tmp_base.unlink(missing_ok=True)
    tmp_out.unlink(missing_ok=True)

# تشخیص سکرت روی نمونهٔ ساختگی (بدون نوشتن روی ریپو)
import re                                   # noqa: E402
fake_token = "123456789:" + "A" * 35
check("الگوی توکن تلگرام شناسایی می‌شود",
      any(p.search(fake_token) for p, _ in S.SECRET_PAT))
check("متن معمولی توکن حساب نمی‌شود",
      not any(p.search("این فقط یک جملهٔ فارسی است") for p, _ in S.SECRET_PAT))

# ── صاحب ریپو خودی است (رفع ۲۴ اوت) ────────────────────────────────────
# merge از دکمه/API گیت‌هاب کامیتی با هویت حساب حمید می‌سازد. نبودن این
# هویت در فهرست، اولین merge را «ناشناس» گرفت و چون sentinel در دروازهٔ
# سخت است، همهٔ چرخه‌های بعد قرمز شدند و سیگنال از کار افتاد — آلارم
# کاذبی که خودش شد منبعِ «پیام‌های خرابی».
check("کامیتِ merge حساب حمید (AuraLiam9) خودی است",
      S._known("AuraLiam9", "18r.liam@gmail.com"))
check("و با هر بزرگی/کوچکی حروف",
      S._known("auraliam9", "18R.LIAM@GMAIL.COM"))
check("ولی جیمیلِ غریبه هنوز غریبه است (فهرست دقیق است، نه پسوند gmail)",
      not S._known("Someone", "someone.else@gmail.com"))
# رفعِ اول فقط author را دید و روی رانر دوباره افتاد: بررسی، committer را
# هم می‌سنجد و committer هر merge سرورساید «GitHub <noreply@github.com>» است.
check("committerِ merge سرورساید گیت‌هاب هم خودی است",
      S._known("GitHub", "noreply@github.com"))
check("جفتِ کاملِ کامیتِ merge (author+committer) هر دو خودی‌اند",
      S._known("AuraLiam9", "18r.liam@gmail.com")
      and S._known("GitHub", "noreply@github.com"))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان نگهبان یکپارچگی: هر {OK} بررسی سبز")
