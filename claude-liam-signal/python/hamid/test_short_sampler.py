"""پاسبان نمونه‌گیر شورت — سه خطری که این آزمایش را می‌تواند سمی کند.

۱. **آلودگی دفتر سیگنال**: برچسب آزمایش باید در هر هفت فهرست جداسازی
   باشد — وگرنه ۲۸۰ ردیف آزمایشی وارد کارنامه/تراز/گزارش کار می‌شود و
   همان CI باددارِ ۲۴ اوت با اسم تازه برمی‌گردد.
۲. **نشتی به تلگرام**: مسیر ارسال فقط ستاپ‌های `stage=="SIGNAL"` را
   می‌فرستد؛ نمونه‌گیر حق ندارد به stage هیچ ستاپی دست بزند یا چیزی جز
   دفتر بنویسد.
۳. **بودجهٔ بی‌ترمز**: نمونه‌گیری بی‌سقف یعنی «تا ابد بگیر» — و تعریفی
   که «تمام» ندارد هرگز تمام نمی‌شود (درس میز اسکلپ). سقف هر باند باید
   دقیقاً کمبودِ اندازه‌گیری‌شده باشد و پرشدنش نمونه‌گیری را بایستاند.

به‌علاوه: هندسهٔ بازو باید واقعاً در باند هدف بیفتد و RR ستاپ حفظ شود —
وگرنه نمونه به سؤالِ خودش جواب نمی‌دهد.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import short_sampler as S                          # noqa: E402

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


def setup(sym="AAAUSDT", q=80, entry=100.0, stop_pct=0.36, rr=1.5,
          stage="SIGNAL"):
    """ستاپ شورتِ واقع‌نما با هندسهٔ بومی ibs (استاپ ~۰.۳۶٪)."""
    sl = entry * (1 + stop_pct / 100)
    return {"sym": sym, "dir": "SHORT", "stage": stage, "tf": "15m",
            "entry": entry, "sl": sl,
            "tp1": entry - abs(sl - entry) * rr, "quality": q,
            "strategy": "ibs"}


def run():
    # ── ۱) هندسهٔ بازو ────────────────────────────────────────────────
    s = setup()
    for tag, (lo, hi, mid, _b) in S.BANDS.items():
        a = S._arm(s, tag)
        got = abs(a["sl"] - a["entry"]) / a["entry"] * 100
        check(f"{tag}: استاپ در باند هدف می‌افتد ({lo:g}–{hi:g}٪)",
              lo <= got < hi, f"{got:.3f}٪")
        rr_native = abs(s["tp1"] - s["entry"]) / abs(s["sl"] - s["entry"])
        rr_arm = abs(a["tp1"] - a["entry"]) / abs(a["sl"] - a["entry"])
        check(f"{tag}: RRِ ستاپ حفظ می‌شود", abs(rr_arm - rr_native) < 1e-6,
              f"{rr_native:.2f} → {rr_arm:.2f}")
        check(f"{tag}: جهت شورت است و استاپ بالای ورود",
              a["dir"] == "SHORT" and a["sl"] > a["entry"] > a["tp1"])
        check(f"{tag}: تایم‌فریم ستاپ منتقل می‌شود", a["tf"] == "15m")
    wild = setup(rr=9.0)
    a = S._arm(wild, "exp-short-b1")
    check("RR بیرون از بازهٔ عاقلانه مهار می‌شود",
          abs(abs(a["tp1"] - a["entry"]) / abs(a["sl"] - a["entry"])
              - S.RR_MAX) < 1e-6)
    check("ستاپ بی‌ریسک (entry=sl) بازو نمی‌سازد",
          S._arm({"sym": "X", "entry": 100.0, "sl": 100.0, "tp1": 99.0},
                 "exp-short-b1") is None)

    # ── ۲) انتخاب نامزد و بودجه ───────────────────────────────────────
    opened_rows = []

    def fake_open(rows, ctx):
        opened_rows.extend(rows)
        return len(rows)

    # مرحله‌ها عمداً مخلوط‌اند: اگر همه SIGNAL باشند، دست‌کاریِ
    # stage→SIGNAL نامرئی می‌شود و بررسی ضدنشتی کور می‌ماند (نقطهٔ کوری
    # که در اولین اثبات منفی همین آزمون پیدا شد).
    setups = ([setup(f"A{i}USDT", q=80,
                     stage=("ARMED" if i % 2 else "WATCH")) for i in range(9)]
              + [setup("LOWQUSDT", q=30)]
              + [{**setup("LNGUSDT", q=90), "dir": "LONG"}])
    before = [dict(x) for x in setups]
    real_counts = S.counts
    S.counts = lambda: {t: 0 for t in S.TAGS}
    try:
        r = S.sample(setups, opener=fake_open)
    finally:
        S.counts = real_counts
    check("نمونه‌گیری اجرا شد و ردیف باز کرد", r["opened"] > 0, str(r))
    check("سقف هر چرخه رعایت می‌شود",
          r["opened"] <= S.PER_CYCLE * len(S.TAGS),
          f"{r['opened']} > {S.PER_CYCLE * len(S.TAGS)}")
    check("ستاپ کم‌کیفیت نمونه نمی‌شود",
          not any(x["symbol"] == "LOWQUSDT" for x in opened_rows))
    check("لانگ هرگز وارد نمونهٔ شورت نمی‌شود",
          all(x["dir"] == "SHORT" for x in opened_rows))
    check("هر ردیف برچسب باند دارد",
          all(x.get("stage_tag") in S.TAGS for x in opened_rows))
    check("نمونه‌گیر به خودِ ستاپ‌ها دست نمی‌زند (ضد نشتی به ارسال)",
          setups == before)

    S.counts = lambda: {t: S.BANDS[t][3] for t in S.TAGS}
    try:
        r2 = S.sample(setups, opener=fake_open)
    finally:
        S.counts = real_counts
    check("بودجهٔ پر = توقف کامل، با دلیل صریح",
          r2["opened"] == 0 and "تمام" in (r2.get("why") or ""), str(r2))
    S.counts = lambda: {t: 0 for t in S.TAGS}
    try:
        r3 = S.sample([setup("X1USDT", q=30)], opener=fake_open)
    finally:
        S.counts = real_counts
    check("بی‌نامزد = صفر نمونهٔ ساختگی، با دلیل",
          r3["opened"] == 0 and "ساختگی" in (r3.get("why") or ""), str(r3))
    check("بودجهٔ باندها همان کمبود اندازه‌گیری‌شده است (۱۳۰ و ۱۵۰)",
          S.BANDS["exp-short-b1"][3] == 130
          and S.BANDS["exp-short-b2"][3] == 150)

    # ── ۳) هر هفت فهرست جداسازی ───────────────────────────────────────
    paper = (PY / "hamid" / "paper.py").read_text(encoding="utf-8")
    for what, src, needle in (
            ("کارنامهٔ تجربه", paper, '"exp-short-b1", "exp-short-b2"):\n            continue'),
            ("دروازهٔ کارمزد", paper, '"exp-short-b1", "exp-short-b2"):\n            if _fr'),
            ("ترازِ دفتر (_aside)", paper, '_aside = ("exp-short-b1", "exp-short-b2"'),
            ("نمرهٔ سیگنال (_siggrade)", paper, 'not st.startswith("exp-")')):
        check(f"جداسازی در {what}", needle in src)
    wr = (PY / "hamid" / "work_report.py").read_text(encoding="utf-8")
    check("جداسازی در گزارش کار",
          '"exp-short-b1"' in wr and "NOT_PERFORMANCE" in wr)
    br = (PY / "hamid" / "bridge.py").read_text(encoding="utf-8")
    check("جداسازی در پل یادگیری", 'st.startswith("exp-")' in br)
    cl = (PY / "hamid" / "classify.py").read_text(encoding="utf-8")
    check("نام فارسی در طبقه‌بند", "آزمایش شورت" in cl)

    # ── ۴) سیم‌کشی و مرز ارسال ────────────────────────────────────────
    scan = (PY / "scan.py").read_text(encoding="utf-8")
    check("اسکن نمونه‌گیر را صدا می‌زند", "short_sampler.sample(setups)" in scan)
    check("و شکستش اسکن را نمی‌کشد", "نمونه‌گیری اختیاری است" in scan)
    i_gate = scan.find("demoted = gate_stages(setups)")
    i_samp = scan.find("short_sampler.sample")
    check("نمونه‌گیری بعد از دروازه‌هاست (هیچ دروازه‌ای دور زده نمی‌شود)",
          0 <= i_gate < i_samp, f"gate={i_gate} sampler={i_samp}")
    ss = (PY / "hamid" / "short_sampler.py").read_text(encoding="utf-8")
    check("نمونه‌گیر هیچ‌جا تلگرام صدا نمی‌زند",
          "telegram" not in ss.lower().replace("صفر تلگرام", "")
          .replace("تلگرام**", ""), "ارجاع تلگرام در سورس")
    check("و فقط از open_from دفتر می‌نویسد", "paper.open_from" in ss)
    sl = (PY / "hamid" / "short_lab.py").read_text(encoding="utf-8")
    check("آزمایشگاه شورت دفتر آزمایش را می‌شمارد", '"exp-short"' in sl)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
