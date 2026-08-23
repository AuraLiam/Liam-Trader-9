"""پاسبان آلارم عیب‌یاب — درس ۲۳ اوت.

زنجیرهٔ سیگنال ۸ ساعت مرده بود. عیب‌یاب **درست تشخیص داده بود**
(`sick=True` از ۰۲:۴۸ به بعد، با خط صریح «Signal chain ۴۰ بار شکست
خورده») و شرط آلارم هم برقرار بود. چیزی که شکست، خودِ آلارم بود: هر ۱۵
دقیقه همان ۱۰ خط می‌رفت که شش خطش «سالم» بود و خبر واقعی خط هشتم.

آلارمی که یکنواخت تکرار شود دیگر آلارم نیست. قانون E23 هم صریح گفته
بود «routine still-alive spam ممنوع؛ فقط نقض SLO، بهبود، یا رویداد
تحویل». این آزمون همان را قفل می‌کند.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import medic as M                                       # noqa: E402

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


# همان یافته‌های واقعیِ شب خرابی
SICK = {"sick": True, "at": 10_000_000, "treated": None,
        "findings": ["چرخه سالم: ۳۷ دقیقه پیش، ۱۹۵ ارز",
                     "اسکن قبلی سالم: ۴۱ دقیقه پیش",
                     "تلگرام آماده است",
                     "صفحهٔ پنل بالا است",
                     "گیت‌هاب: ۴۰ اجرای ناموفق در ۶ ساعت اخیر — Signal chain×۴۰",
                     "⚠️ «Signal chain» ۴۰ بار شکست خورده — عیب واقعی است"]}
WELL = {"sick": False, "at": 10_000_000, "treated": None,
        "findings": ["چرخه سالم", "صفحهٔ پنل بالا است"]}

# ── جدا کردن خبر از نویز ────────────────────────────────────────────────
faults = M.fault_lines(SICK["findings"])
check("فقط خطوط خرابی برداشته می‌شوند", len(faults) == 2, str(faults))
check("خط «سالم» هرگز خرابی حساب نمی‌شود",
      not any("سالم" in f and "ناموفق" not in f for f in faults))
check("سالمِ خالص هیچ خط خرابی ندارد", M.fault_lines(WELL["findings"]) == [])
check("یافتهٔ خالی خطا نمی‌دهد", M.fault_lines(None) == [])

# ── کِی پیام برود ───────────────────────────────────────────────────────
check("سالم → خراب: آلارم می‌رود", M.alert_decision(SICK, {}) == (True, "new"))
check("خراب → خراب در فاصلهٔ کوتاه: سکوت (ضدِ اسپمِ ۱۵دقیقه‌ای)",
      M.alert_decision(SICK, {"sick": True, "alerted_at": SICK["at"] - 60_000},
                       now_ms=SICK["at"]) == (False, "duplicate"))
check("خرابیِ پابرجا بعد از یک ساعت یادآوری می‌گیرد (فراموش نمی‌شود)",
      M.alert_decision(SICK,
                       {"sick": True,
                        "alerted_at": SICK["at"] - M.ESCALATE_MS - 1},
                       now_ms=SICK["at"]) == (True, "still"))
check("مرزِ یادآوری دقیقاً روی ESCALATE_MS است، نه تقریبی",
      M.alert_decision(SICK, {"sick": True,
                              "alerted_at": SICK["at"] - M.ESCALATE_MS},
                       now_ms=SICK["at"])[0] is True)
check("خراب → سالم: بهبود هم خبر است",
      M.alert_decision(WELL, {"sick": True}) == (True, "recovered"))
check("سالم → سالم: هیچ پیامی نمی‌رود",
      M.alert_decision(WELL, {"sick": False}) == (False, "healthy"))
# شبیه‌سازی همان شب: ۸ ساعت خرابی پیوسته، عیب‌یاب هر ۱۵ دقیقه
prev = {}
sent = 0
now = 0
for _ in range(32):                       # ۸ ساعت × ۴ اجرا در ساعت
    now += 15 * 60_000
    st = dict(SICK, at=now)
    go, why = M.alert_decision(st, prev, now_ms=now)
    if go:
        sent += 1
    prev = {"sick": True, "alerted_at": now if go else prev.get("alerted_at", 0)}
# اولی سرِ «تازه خراب شد»، بعد هر ESCALATE_MS یکی. با استاندارد ۶ ساعتِ
# ۲۳ اوت: ۱ + ۱ = ۲ پیام در ۸ ساعت (قبلاً ساعتی بود و ۸ تا می‌شد).
_expect = 1 + int(8 * 3600_000 // M.ESCALATE_MS)
check(f"۸ ساعت خرابی پیوسته = {_expect} پیام، نه ۳۲ تا",
      sent == _expect, f"{sent} پیام")

# هم‌واژگیِ کادنس با دروازهٔ مشترک — دو عدد نباید از هم جدا بیفتند،
# وگرنه یکی از پاسبان‌ها دوباره پرحرف می‌شود بی‌آنکه کسی بفهمد.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hamid import alert_gate as _AG                  # noqa: E402
check("کادنس یادآوری عیب‌یاب با alert_gate یکی است (۶ ساعت)",
      M.ESCALATE_MS == int(_AG.REPEAT_H * 3600_000),
      f"medic={M.ESCALATE_MS} gate={_AG.REPEAT_H}")

# ── متن پیام ────────────────────────────────────────────────────────────
txt = M.alert_text(SICK, "new")
lines = txt.splitlines()
check("پیام با خرابی شروع می‌شود، نه با «سالم»", lines[0].startswith("⛔"))
check("خبر واقعی در دو خط اول بدنه است (نه خط هشتم)",
      any("Signal chain" in ln for ln in lines[1:3]), txt)
check("خطوط سالم تکرار نمی‌شوند، فقط شمرده می‌شوند",
      "چرخه سالم: ۳۷ دقیقه پیش، ۱۹۵ ارز" not in txt
      and "بررسی دیگر سالم" in txt and "4 بررسی" in txt, txt)
check("پیام از دامپِ همهٔ یافته‌ها کوتاه‌تر است",
      len(lines) < len(SICK["findings"]), f"{len(lines)} < {len(SICK['findings'])}")
check("پیام امضای پنل دارد (دستور ۱۶ اوت)", "لیام تریدر ۹" in txt)
check("تعمیر انجام‌شده در پیام می‌آید",
      "🔧" in M.alert_text(dict(SICK, treated="heartbeat بیدار شد"), "new"))
rec = M.alert_text(WELL, "recovered")
check("پیام بهبود مثبت و امضادار است",
      rec.startswith("✅") and "لیام تریدر ۹" in rec, rec)
check("یادآوری با «تازه» فرق دارد (تکرارِ کورکورانه نیست)",
      M.alert_text(SICK, "still") != M.alert_text(SICK, "new")
      and "پابرجا" in M.alert_text(SICK, "still"))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان آلارم عیب‌یاب: هر {OK} بررسی سبز")
