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

    # ── میدانِ چرخان (۱ سپتامبر) ────────────────────────────────────────
    #
    # اندازه‌گیری ۳ روزه: از ۳۳۲ اسکنِ ثبت‌شده، ۳۲۵ تا ۶۰نمادی و فقط ۵ تا
    # ۲۰۰نمادی — اسکنِ پهن ۱.۷ بار در روز، نه هر ۱۵ دقیقه. و چون زنجیره
    # همیشه همان ۶۰ نمادِ اولِ حجم را می‌گرفت، رتبه‌های ۶۱–۲۰۰ عملاً هرگز
    # دیده نمی‌شدند.
    import scan as S
    _real = S.top_by_48h
    try:
        S.top_by_48h = lambda n: [f"S{i:03d}USDT" for i in range(n)]
        core_syms = [f"S{i:03d}USDT" for i in range(30)]
        slots = [S.rotating_field(60, universe=200, core=30, slot=k)
                 for k in range(6)]
        check("هستهٔ پرحجم در هر برش اسکن می‌شود (بسترِ اجباری قانون ۳)",
              all(g[:30] == core_syms for g in slots))
        check("هر برش دقیقاً به اندازهٔ خواسته و بدون تکرار است",
              all(len(g) == 60 and len(set(g)) == 60 for g in slots))
        cov = set().union(*[set(g) for g in slots])
        check("شش برش کلِ میدان ۲۰۰تایی را می‌پوشاند (~۳۰ دقیقه)",
              len(cov) == 200, f"{len(cov)} نماد")
        check("برش‌های پیاپی دُمِ متفاوت می‌گیرند (چرخش واقعی است)",
              slots[0][30:] != slots[1][30:])
        check("چرخش قطعی است — همان برش، همان نمادها",
              S.rotating_field(60, 200, 30, 3) == slots[3])
        check("بدون --rotate رفتار قدیمی دست‌نخورده می‌ماند",
              len(S.rotating_field(60, universe=0, core=30)) == 60)
        check("میدانِ کوچک‌تر از خواسته، چرخش نمی‌گیرد",
              len(S.rotating_field(60, universe=40, core=30)) == 60)
    finally:
        S.top_by_48h = _real
    src = (PY / "scan.py").read_text(encoding="utf-8")
    check("اسکن دفترِ پوششِ غلتان می‌نویسد", "scan-coverage.json" in src)
    check("دفتر پوشش نمادِ یکتای یک‌ساعته را می‌شمرد", "unique_1h" in src)
    wf = (PY.parent.parent / ".github/workflows/pump-radar.yml").read_text(
        encoding="utf-8")
    check("زنجیره با میدانِ چرخان اسکن می‌کند", "--rotate 200" in wf)
    import json as _json
    reg = _json.loads((PY.parent.parent / "config/state_registry.json")
                      .read_text(encoding="utf-8"))["files"]
    check("دفتر پوشش ردیف قرارداد دارد (قانون ۱۳)",
          "scan-coverage.json" in reg)

    # ── شناسایی ارز: کلاس مشتق می‌شود، فهرست‌وار نیست (۶ سپتامبر) ────────
    #
    # حمید: «باید تو شناسایی ارزها دقت بیشتری بکنی.» فهرستِ دست‌نویس
    # `WETH` را داشت ولی `WBETH` را نه، و WBETHUSDT سیگنال گرفت؛ طلای
    # توکنی (XAUT×۱۴ · PAXG×۱۰) در هیچ فهرستی نبود. علتِ کلاس همان است
    # که ۶ سپتامبر ثبت شد: فهرستی که آدم باید به‌خاطر بسپارد.
    from hamid.universe import sym_class, structureless
    # ۱) چیزهایی که باید گرفته شوند — از جمله همان‌هایی که فهرست جا انداخت
    for s in ("WBETHUSDT", "USD1USDT", "BETHUSDT", "RETHUSDT", "BNSOLUSDT",
              "SOLVBTCUSDT", "WBTCUSDT", "STETHUSDT", "RLUSDUSDT",
              "BFUSDUSDT", "USDGOUSDT", "BRLUSDT"):
        check(f"«{s}» ساختارِ معامله‌پذیر ندارد", structureless(s), sym_class(s))
    # ۲) و مهم‌تر: مثبتِ کاذب نسازد. این‌ها ارزهای واقعی‌اند که با پیشوندِ
    #    رپینگ شروع می‌شوند یا به نام مِیجر ختم می‌شوند.
    for s in ("WIFUSDT", "BCHUSDT", "STXUSDT", "RENDERUSDT", "BONKUSDT",
              "WLDUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
              "PUMPUSDT", "TRUMPUSDT", "ASTERUSDT"):
        check(f"«{s}» ارز عادی است و بلاک نمی‌شود",
              not structureless(s) and sym_class(s) == "crypto", sym_class(s))
    # ۳) کالا کلاسِ خودش را دارد و **بسته نیست** — چون n=۲۴ و
    #    میانگین +۰.۰۱۶R چیزی را اثبات نمی‌کند (قانون ۰۳).
    for s in ("XAUTUSDT", "PAXGUSDT"):
        check(f"«{s}» کالاست، نه بلاک‌شده",
              sym_class(s) == "commodity" and not structureless(s))
    # ۴) گلوگاه ارسال از همین منبع می‌خواند، نه از فهرستِ خودش
    tg = (PY / "telegram.py").read_text(encoding="utf-8")
    check("گلوگاه ارسال کلاس را از universe می‌گیرد",
          "from hamid.universe import structureless" in tg)
    check("کلاسِ نماد روی دفتر ثبت می‌شود",
          '"sym_class": _sym_class(' in tg)
    pap = (PY / "hamid" / "paper.py").read_text(encoding="utf-8")
    check("و ماشین شبانه شرطش را دارد",
          'w.get("sym_class") == "commodity"' in pap)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
