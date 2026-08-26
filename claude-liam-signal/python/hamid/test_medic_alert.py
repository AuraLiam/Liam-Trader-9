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
check("خراب → سالم: دیگر پیام نمی‌رود — فقط لاگ/پنل (دستور ۲۶ اوت)",
      M.alert_decision(WELL, {"sick": True}) == (False, "recovered_quiet"))
# خرابی غیربحرانی (محصول سالم است) → عیب‌یاب ساکت خودش تعمیر می‌کند
SICK_SOFT = {"sick": True, "at": 10_000_000,
             "faults": ["⚠️ «Deep symbol» ۲ بار شکست خورده — عیب واقعی است"],
             "findings": ["⚠️ «Deep symbol» ۲ بار شکست خورده — عیب واقعی است"]}
check("خرابی غیربحرانی: تلگرام ساکت، تعمیر خاموش",
      M.alert_decision(SICK_SOFT, {}) == (False, "quiet_selfheal"))
check("خرابی بحرانی (زنجیرهٔ سیگنال) همچنان آلارم دارد",
      M.product_critical(["⚠️ «Signal chain» ۲ بار شکست خورده"]) is True)
check("خرابی تلگرام هم بحرانی است",
      M.product_critical(["تلگرام آماده نیست"]) is True)
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

# ── درس ۲۵ اوت: ملاک گیت‌هاب وضعِ فعلی است، نه پنجرهٔ گذشته ────────────
# «۲ اجرای ناموفق در ۶ ساعت اخیر» تا نیمه‌شب پیام می‌شد در حالی که همان
# خرابی ساعت ۱۹:۲۴ ریشه‌ای رفع شده و ۸ اجرای پیاپی سبز بود.


def _run(name, concl, t):
    return {"name": name, "status": "completed", "conclusion": concl,
            "created_at": f"2026-08-24T{t}:00Z"}


runs = ([_run("Hamid cycle", "success", f"{h:02d}:04") for h in range(20, 24)]
        + [_run("Hamid cycle", "failure", "19:18"),
           _run("Hamid cycle", "failure", "18:59"),
           _run("Hamid cycle", "success", "17:47")])
f_, i_, s_, w_ = M.github_health(runs)
check("شکستِ رفع‌شده دیگر خرابی نیست (عین سناریوی پیام ۲۴ اوت)",
      f_ == [] and not s_, str(f_))
check("ولی پنهان هم نمی‌شود — یک خط خبرِ برطرف‌شدن",
      any("برطرف شده" in x and "Hamid cycle" in x for x in i_), str(i_))
check("و آن خط آلارم‌ساز نیست (کلیدواژهٔ ماشه ندارد)",
      M.fault_lines(i_) == [], str(i_))

f2, i2, s2, w2 = M.github_health(
    [_run("Hamid cycle", "failure", "22:30"),
     _run("Hamid cycle", "failure", "22:00"),
     _run("Hamid cycle", "success", "21:00")])
check("۲ شکستِ پیاپی در انتها = «الان قرمز» + sick",
      len(f2) == 1 and s2 and "الان قرمز" in f2[0], str(f2))
check("و چرخهٔ حمید heartbeat را بیدار می‌کند", "heartbeat.yml" in w2)
f3, _, s3, _ = M.github_health(
    [_run("X", "failure", "22:30"), _run("X", "success", "21:00")])
check("یک قرمزِ تک: اعلام می‌شود ولی sick نمی‌کند (نوسان ممکن است)",
      len(f3) == 1 and not s3)
fb, _, sb, _ = M.github_health([_run(".github/workflows/x.yml", "failure", "22:00")])
check("ورک‌فلوی نامعتبر همچنان بلند و sick است",
      sb and any("نامعتبر" in x for x in fb))
check("cancelled شمارش پیاپی را نمی‌شکند",
      M.github_health([_run("Y", "failure", "23:00"),
                       _run("Y", "cancelled", "22:30"),
                       _run("Y", "failure", "22:00"),
                       _run("Y", "success", "21:00")])[2])
check("فهرست خالی/None خطا نمی‌دهد و سالم است",
      M.github_health(None)[0] == [] and not M.github_health([])[2])

# ── خرابیِ ساختاری: علتِ sick باید همان بولت پیام باشد ──────────────────
# کلاس عیب ۲۴ اوت: «رادار پامپ کهنه» sick کرده بود ولی چون کلیدواژهٔ
# ماشه نداشت در پیام نبود؛ به‌جایش خبر تاریخی گیت‌هاب نشسته بود.
st_pump = {"sick": True, "at": 1, "treated": None,
           "findings": ["چرخه سالم: ۱۰ دقیقه پیش",
                        "رادار پامپ کهنه است — ۸۹۹ دقیقه پیش (سقف ۳۸۰د)"],
           "faults": ["رادار پامپ کهنه است — ۸۹۹ دقیقه پیش (سقف ۳۸۰د)"]}
txt2 = M.alert_text(st_pump, "new")
check("علتِ واقعی sick در پیام می‌آید حتی بدون کلیدواژهٔ ماشه",
      "رادار پامپ کهنه" in txt2.splitlines()[1], txt2)
check("وضعیت قدیمیِ بدون faults همچنان پیام درست می‌سازد (سازگاری)",
      "Signal chain" in M.alert_text(SICK, "new"))

# ── دکترین کادنس پامپ (قانون ۰۷) — پاسبان‌ها با کادنس واقعی هم‌قدم ──────
check("آستانهٔ رادار پامپِ عیب‌یاب با کادنس ۵نوبته می‌خواند (≥۳۶۰د)",
      M.PUMP_RADAR_MAX_MIN >= 360, str(M.PUMP_RADAR_MAX_MIN))
from hamid import conformance as _CF                 # noqa: E402
check("پاسبان C5 هم هم‌قدم است (نه ۲۰ دقیقهٔ دورهٔ قبل)",
      _CF.FRESHNESS_MAX_MIN["signals/pump-radar.json"] >= 360)
_msrc = Path(M.__file__).read_text(encoding="utf-8")
check("درمانِ رادارِ کهنه خودِ تولیدکننده است (pump-review.yml)",
      '"pump-review.yml")' in _msrc)
REPO = Path(__file__).resolve().parents[3]
_chain = (REPO / ".github" / "workflows" / "pump-radar.yml").read_text(encoding="utf-8")
for _f in ("signals/pump-radar.json", "signals/bubbles.json",
           "brain/pump-radar-sent.json"):
    check(f"زنجیرهٔ سیگنال دیگر {_f.split('/')[-1]} را بکاپ/بازنشانی نمی‌کند "
          "(فقط تولیدکننده)", f'cp {_f} "$BK/"' not in _chain)
_review = (REPO / ".github" / "workflows" / "pump-review.yml").read_text(encoding="utf-8")
check("و تولیدکننده (pump-review) بازنشانی خودش را نگه داشته",
      'cp signals/pump-radar.json "$BK/"' in _review)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان آلارم عیب‌یاب: هر {OK} بررسی سبز")
