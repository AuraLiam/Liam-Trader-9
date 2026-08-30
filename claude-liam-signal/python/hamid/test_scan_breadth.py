"""پاسبان پهنای پایش — سؤال حمید ۳۰ اوت: «سیگنال‌ها روی ارزهای محدودی‌اند».

عیبِ اندازه‌گیری‌شده‌ای که این آزمون می‌بندد:

`live-scan.yml` تنها جایی است که ۲۰۰ نماد را می‌گردد. شرطِ کنارکشیدنش
فقط **سنِ** `signals/latest.json` بود. زنجیرهٔ اصلی (`pump-radar.yml`)
هر ~۱۵ دقیقه همان فایل را با اسکنِ **۶۰ نمادی** تازه می‌کرد، پس تورِ
ایمنی همیشه «زنجیره زنده است» می‌دید و کنار می‌کشید — و پهنای واقعیِ
پایش برای همیشه ۶۰ ماند نه ۲۰۰.

از بیرون هیچ‌چیز خراب به نظر نمی‌رسید: هر دو ورک‌فلو سبز بودند، پنل
داده داشت، و کسی مقایسه نمی‌کرد که «۶۰» روی خروجی با «۲۰۰»ی که
ورک‌فلو ادعا می‌کند یکی نیست. اندازه‌گیری ۳۰ اوت: در ۷ روز فقط **۳۱
نماد یکتا** سیگنال گرفتند، و اجرای ۱۳:۱۵ همان روز در **۲۴ ثانیه**
تمام شد — یعنی اسکنی اصلاً انجام نشد.

سه چیزی که قفل می‌شود:
۱. شرطِ کنارکشیدن باید **هم تازگی هم پهنا** را ببیند.
۲. اسکنِ پهن باید همان عددی را بخواهد که سند ادعا می‌کند.
۳. خروجی اسکن باید پهنای پوشش‌داده‌شده را **بنویسد** — وگرنه شرط بالا
   چیزی برای مقایسه ندارد و بی‌صدا به حالت قبل برمی‌گردد.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

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


# منطقِ کنارکشیدن، همان‌طور که در ورک‌فلو نوشته شده — این‌جا اجرایی می‌شود
def stands_aside(age_min, covered, wanted):
    return age_min < 12 and covered >= wanted


def run():
    live = (ROOT / ".github/workflows/live-scan.yml").read_text(encoding="utf-8")
    chain = (ROOT / ".github/workflows/pump-radar.yml").read_text(encoding="utf-8")

    # ── ۱) شرطِ کنارکشیدن هر دو تکه را دارد ──────────────────────────────
    check("تورِ ایمنی پهنا را هم می‌سنجد، نه فقط سن را",
          "COVERED" in live and '-ge "$WANT"' in live,
          "شرط دوباره تک‌تکه شده — همان عیبِ ۳۰ اوت")
    check("سنجهٔ پهنا از خودِ خروجی خوانده می‌شود (نه عددِ ثابت)",
          'j.get("symbols")' in live)

    # ── ۲) رفتارِ شرط، سناریو به سناریو ──────────────────────────────────
    for name, age, cov, want, exp in (
        ("زنجیرهٔ ۶۰تایی تازه → اسکنِ پهن باید اجرا شود", 5, 60, 200, False),
        ("زنجیرهٔ ۲۰۰تایی تازه → کار تکراری نکن", 5, 200, 200, True),
        ("زنجیرهٔ ۶۰تایی کهنه → اجرا شود", 40, 60, 200, False),
        ("خروجیِ غایب/خراب → اجرا شود (قانون ۱)", 999, 0, 200, False),
        ("پهنای بیشتر از خواسته هم قبول است", 5, 250, 200, True),
    ):
        check(name, stands_aside(age, cov, want) is exp,
              f"age={age} covered={cov} want={want}")

    # ── ۳) عددِ خواسته‌شده با سندِ ادعا یکی است ──────────────────────────
    m = re.search(r"inputs\.symbols \|\| '(\d+)'", live)
    check("اسکنِ پهن همان ۲۰۰ نماد را می‌خواهد",
          m and int(m.group(1)) >= 200, m.group(1) if m else "پیدا نشد")
    mc = re.search(r"scan\.py --symbols (\d+)", chain)
    check("پهنای زنجیرهٔ اصلی روی فایل ثبت است (برای مقایسه)",
          mc is not None, "خط اسکن زنجیره پیدا نشد")
    if m and mc:
        check("اسکنِ پهن واقعاً پهن‌تر از زنجیره است (وگرنه بی‌فایده است)",
              int(m.group(1)) > int(mc.group(1)),
              f"پهن={m.group(1)} زنجیره={mc.group(1)}")

    # ── ۴) خروجی اسکن پهنا را می‌نویسد — بدون این، شرط کور است ───────────
    scan = (PY / "scan.py").read_text(encoding="utf-8")
    check("scan.py تعداد نمادِ پوشش‌داده‌شده را در خروجی می‌نویسد",
          '"symbols": len(syms)' in scan,
          "بدون این فیلد، تورِ ایمنی نمی‌تواند پهنا را بسنجد")

    # ── ۵) خروجیِ تولید واقعاً همین فیلد را دارد ─────────────────────────
    p = ROOT / "signals" / "latest.json"
    if p.exists():
        try:
            d = json.loads(p.read_text())
            n = d.get("symbols")
            n = n if isinstance(n, int) else (len(n) if hasattr(n, "__len__") else None)
            check("خروجیِ فعلی پهنایش را اعلام می‌کند", isinstance(n, int),
                  f"symbols={d.get('symbols')!r}")
        except Exception as e:                       # noqa: BLE001
            check("خروجیِ فعلی خوانا است", False, str(e))

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
