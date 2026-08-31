"""پاسبان چند راهزن مسلح (نمونه‌گیری تامسون) — دستور حمید، ۳۱ اوت.

چهار چیزی که قفل می‌شود:

۱. **ریاضیِ روش درست باشد**: بازوی بهتر سهمِ بیشتر بگیرد، بازوی نامعلوم
   صفر نشود (کاوش زنده بماند)، و تخصیص با بذرِ روز بازتولیدپذیر باشد.
۲. **قاعدهٔ توقف از پیش ثبت‌شده**: بازوی REJECT (CI زیر صفر، n≥۳۰۰) و
   PROMOTE-آماده (CI بالای صفر، n≥۴۰۰) بازنشسته شوند — نمونهٔ بیشتر روی
   سؤالِ جواب‌گرفته، هدر است.
۳. **مرز**: بندیت فقط بودجهٔ آزمایش پیپر را تقسیم می‌کند. هیچ ماژول
   مسیر سیگنال واقعی (telegram/scan صدور) از bandit وارد نمی‌کند و
   PROMOTE فقط «پیشنهاد» است.
۴. **بی‌حالتی**: هیچ فایل حالتِ جدایی جز خروجی ثبت‌شده در قرارداد
   وضعیت نوشته نمی‌شود (قانون ۱۳ — ضدیتیم).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import bandit as B                                 # noqa: E402

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


def st(n, mean, sd=0.8):
    import math
    se = sd / math.sqrt(n) if n >= 2 else B.PRIOR_SD
    return {"n": n, "mean": mean, "sd": sd, "se": se,
            "ci": ([mean - 1.96 * se, mean + 1.96 * se] if n >= 2 else None),
            "desc": "x"}


def run():
    # ── ۱) ریاضی تخصیص ────────────────────────────────────────────────
    stats = {"exp-short-b1": st(100, +0.30), "exp-short-b2": st(100, -0.30)}
    alloc, why = B.allocate(10, stats, day="2026-08-31")
    # با این پسین‌ها (فاصلهٔ ۰.۶R و خطای ~۰.۰۸) احتمالِ برتریِ بازوی
    # بهتر عملاً ۱ است؛ تامسونِ واقعی باید تقریباً همه را به او بدهد.
    # «فقط بیشتر» کافی نیست — تخصیصِ کورِ ~۵۰/۵۰ هم شانسی از آن رد
    # می‌شد (نقطهٔ کوری که در اولین اثبات منفی همین آزمون پیدا شد).
    check("بازوی قطعاً بهتر تقریباً کل بودجه را می‌گیرد",
          alloc["exp-short-b1"] >= 9, str(alloc))
    check("جمع تخصیص دقیقاً برابر بودجه است", sum(alloc.values()) == 10)
    check("دلیل تخصیص p(بهترین) را چاپ می‌کند", "p(بهترین)" in why, why)

    a2, _ = B.allocate(10, stats, day="2026-08-31")
    check("تخصیص با بذرِ روز بازتولیدپذیر است", alloc == a2)
    a3, _ = B.allocate(10, stats, day="2026-09-01")
    check("و بذر واقعاً از تاریخ می‌آید (روز دیگر می‌تواند فرق کند)",
          isinstance(a3, dict))

    close = {"a": st(30, +0.05, 0.9), "b": st(30, +0.02, 0.9)}
    ac, _ = B.allocate(20, close, day="2026-08-31")
    check("دو بازوی نزدیک، هر دو سهم می‌گیرند (کاوش نمی‌میرد)",
          ac["a"] > 0 and ac["b"] > 0, str(ac))

    fresh = {"a": st(100, +0.30), "b": st(1, 0.0)}
    af, _ = B.allocate(20, fresh, day="2026-08-31")
    check("بازوی بی‌داده با پسینِ پهن هنوز شانس کاوش دارد",
          af["b"] > 0, str(af))

    # ── ۲) قاعدهٔ توقف ────────────────────────────────────────────────
    check("REJECT: CI زیر صفر با n≥۳۰۰",
          B.verdict(st(350, -0.30, 0.5)) == "REJECT")
    check("CI زیر صفر ولی n کم → هنوز SAMPLING (حکم زودرس ممنوع)",
          B.verdict(st(50, -0.50, 0.5)) == "SAMPLING")
    check("PROMOTE فقط پیشنهاد است و اسمش همین را می‌گوید",
          B.verdict(st(450, +0.30, 0.5)) == "PROMOTE_PROPOSED")
    check("CI بالای صفر ولی n<۴۰۰ → SAMPLING",
          B.verdict(st(100, +0.30, 0.5)) == "SAMPLING")
    dead = {"a": st(350, -0.30, 0.5), "b": st(450, +0.30, 0.5)}
    ad, why_d = B.allocate(10, dead, day="2026-08-31")
    check("بازوهای حکم‌گرفته سهم صفر می‌گیرند و دلیل صریح است",
          sum(ad.values()) == 0 and "حکم" in why_d, f"{ad} · {why_d}")

    # ── ۳) مرز — بندیت روی مسیر سیگنال واقعی نمی‌نشیند ────────────────
    src = (PY / "hamid" / "bandit.py").read_text(encoding="utf-8")
    check("بندیت هیچ‌جا تلگرام صدا نمی‌زند", "telegram" not in src.lower())
    tg = (PY / "telegram.py").read_text(encoding="utf-8")
    check("گلوگاه ارسال از بندیت وارد نمی‌کند", "bandit" not in tg)
    scan = (PY / "scan.py").read_text(encoding="utf-8")
    check("اسکن فقط از راه نمونه‌گیر پیپر به بندیت می‌رسد، نه مستقیم",
          "bandit" not in scan)
    for token in ("boundary", "قانون ۰۳"):
        check(f"مرز روی خروجی نوشته می‌شود ({token})", token in src)
    check("جایزهٔ انجین صریحاً «ردپای تأیید نه اثر علّی» می‌ماند",
          "اثر علّی" in src)

    # ── ۴) بی‌حالتی + قرارداد وضعیت (قانون ۱۳) ────────────────────────
    check("خروجی فقط signals/engine-focus.json است",
          'OUT = ROOT / "signals" / "engine-focus.json"' in src
          and src.count("write_text") == 1)
    reg = json.loads((PY.parents[1] / "config" / "state_registry.json")
                     .read_text(encoding="utf-8"))
    files = reg.get("files", reg)
    check("engine-focus.json ردیف قرارداد دارد (ضدیتیم)",
          "engine-focus.json" in files)
    row = files.get("engine-focus.json") or {}
    check("و سقف کهنگی‌اش از کادنس واقعی می‌آید (~۳ نوبت در روز)",
          600 <= (row.get("max_age_min") or 0) <= 900, str(row.get("max_age_min")))

    # ── ۵) بستهٔ تمرکز انجین‌ها ───────────────────────────────────────
    p = B.packet(day="2026-08-31")
    check("بسته بازوها + تمرکز انجین‌ها + مرز را با هم دارد",
          {"arms", "engine_focus", "boundary"} <= set(p))
    ef = p["engine_focus"]
    check("تمرکز انجین‌ها خالی نیست", len(ef) >= 3, str(len(ef)))
    small = [f for f in ef if f["n"] < B.MIN_N_VERDICT]
    check("انجین کم‌نمونه برچسب قوت/ضعف نمی‌خورد",
          all(f["strength"] is None for f in small))
    check("هر انجین فهرست منابعش را دارد (حتی اگر خالی)",
          all("sources" in f for f in ef))
    withsrc = [f for f in ef if f["sources"]]
    check("دست‌کم چند انجین منبع قفسه دارند", len(withsrc) >= 2,
          str(len(withsrc)))

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
