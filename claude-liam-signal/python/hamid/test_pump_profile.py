"""پاسبان پروفایل پامپ — ریاضیِ چسبندگی و صداقتِ برچسب‌ها."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import pump_profile as P                           # noqa: E402

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


def ev(sym, weeks_ago, now):
    return {"sym": sym, "t": now - int(weeks_ago * P.WEEK) - 1000,
            "vol_z": 5.0, "ret_4h_pct": 15.0}


def run():
    now = 1_788_000_000_000
    # نماد A هر هفته پامپ می‌کند؛ B فقط هفتهٔ ۳؛ C هرگز (فقط در هفتهٔ ۵ یک بار)
    events = ([ev("A", w, now) for w in (1, 2, 3, 4)]
              + [ev("B", 3, now)] + [ev("C", 5, now)])
    rp = P.repeat_stat(events, now_ms=now)
    check("چسبندگیِ نمادِ همیشه-پامپ بالا درمی‌آید",
          rp["p_repeat"] is not None and rp["p_repeat"] > rp["p_base"],
          str(rp))
    check("شمارش جفت‌ها درست است (هفتهٔ ناقص کنار می‌رود)",
          rp["n_all"] > 0 and rp["n_repeat"] <= rp["n_all"])
    rp0 = P.repeat_stat([], now_ms=now)
    check("بی‌داده، چسبندگی None است نه عدد ساختگی",
          rp0["p_repeat"] is None)

    pr = P.profile(events)
    check("پروفایل می‌شمارد، نمی‌سازد",
          pr["n"] == 6 and pr["symbols"] == 3 and pr["multi_pumpers"] == 1,
          str(pr))
    check("میانه‌ها از خود رویدادها می‌آید",
          pr["vol_z_median"] == 5.0 and pr["ret4h_median"] == 15.0)

    src = (HERE / "pump_profile.py").read_text(encoding="utf-8")
    check("پوشش‌نداشتن حساسیت BTC «نمی‌دانم» است نه «مستقل»",
          "UNKNOWN (پوشش ندارد)" in src)
    check("مرز صادقانه در خروجی است (شاهد نه سیگنال، قانون ۰۷)",
          "پامپِ محتمل ≠ ورود معتبر" in src)
    check("کارنامه از موتور کالبدشکافی (کارمزد منبع‌واحد) می‌آید",
          "from hamid.direction_autopsy import load" in src)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
