"""پاسبان تجزیهٔ دامیننس تتر — صورت در برابر مخرج (بند ۲، ۲۹ اوت).

چیزی که این آزمون نگه می‌دارد: **یک عدد، دو معنیِ متضاد.** اگر تجزیه
اشتباه کند، موتور «تترِ تازه mint شد» را «بازار ریخت» می‌خواند — و
تفسیرش دقیقاً برعکس واقعیت می‌شود.

سناریوها با عددِ دستی ساخته شده‌اند تا جوابِ درست از قبل معلوم باشد.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import dom_decomp as D                             # noqa: E402

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


def pts(pairs, step_min=5):
    """(دامیننس، کل بازار) → سری، آخرین نقطه = آخرین جفت."""
    n = len(pairs)
    return [{"t": (i - n + 1) * step_min * 60000 + 10**12,
             "u": u, "b": 56.0, "m": m} for i, (u, m) in enumerate(pairs)]


def run():
    T = 3.0e12                     # کل بازار پایه: ۳ تریلیون دلار

    # ── ۱) تترِ تازه: عرضه بالا، کل بازار ثابت ────────────────────────────
    # D از ۵٪ به ۵.۵٪ فقط چون S از ۱۵۰ به ۱۶۵ میلیارد رفته
    s = pts([(5.0, T)] * 48 + [(5.5, T * 1.005)])
    d = D.decompose(s, 240)
    check("تجزیه با دادهٔ کافی اجرا می‌شود", d["status"] == "OK", str(d)[:200])
    check("mint تازه = SUPPLY_DRIVEN (نه «بازار ریخت»)",
          d["label"] == "SUPPLY_DRIVEN", str(d)[:260])
    check("و تفسیرش صریح می‌گوید این ریزش نیست",
          "ریزش نیست" in d["story"], d["story"])
    check("سهم صورت غالب است", d["supply_share"] >= D.DOMINANT_SHARE,
          str(d["supply_share"]))

    # ── ۲) ریزش بازار: عرضه ثابت، کل بازار پایین ─────────────────────────
    # S ثابت ۱۵۰ میلیارد؛ T از ۳ به ۲.۷ تریلیون → D از ۵٪ به ۵.۵۵٪
    s2 = pts([(5.0, T)] * 48 + [(round(100 * 0.15e12 / (T * 0.9), 3), T * 0.9)])
    d2 = D.decompose(s2, 240)
    check("ریزش بازار = MARKET_DRIVEN", d2["label"] == "MARKET_DRIVEN",
          str(d2)[:260])
    check("و تفسیرش «ریزشِ واقعی» را نام می‌برد",
          "ریزشِ واقعی" in d2["story"], d2["story"])

    # ── ۳) دقتِ ریاضی: جمعِ دو اثر باید دقیقاً برابر تغییر نسبت باشد ──────
    for name, dd in (("mint", d), ("ریزش", d2)):
        gap = abs(dd["d_dom_pct"] - (dd["supply_effect_pct"]
                                     + dd["mcap_effect_pct"]))
        check(f"تجزیه در سناریوی «{name}» دقیق است (نه تقریبی)", gap < 0.01,
              f"اختلاف {gap}")

    # ── ۴) هر دو با هم = MIXED؛ تفسیر یک‌طرفه ممنوع ──────────────────────
    s3 = pts([(5.0, T)] * 48 + [(5.25, T * 0.98)])
    d3 = D.decompose(s3, 240)
    check("اثر هم‌زمانِ دو ریشه = MIXED", d3["label"] == "MIXED", str(d3)[:200])
    check("و صریح می‌گوید تفسیر یک‌طرفه ممنوع است",
          "یک‌طرفه" in d3["story"], d3["story"])

    # ── ۵) بی‌حرکت = FLAT، نه داستان‌سازی ────────────────────────────────
    s4 = pts([(5.0, T)] * 49)
    d4 = D.decompose(s4, 240)
    check("بازهٔ بی‌تکان = FLAT", d4["label"] == "FLAT", str(d4)[:200])
    check("و خطِ کپشن برای FLAT ساخته نمی‌شود", D.line(d4) is None)

    # ── ۶) دادهٔ ناقص = INSUFFICIENT، نه عددِ ساختگی (قانون ۱) ────────────
    old = [{"t": i * 300000, "u": 5.0, "b": 56.0} for i in range(60)]
    check("سری بدون کل بازار = INSUFFICIENT",
          D.decompose(old, 240)["status"] == "INSUFFICIENT")
    check("و دلیلِ نبودن نوشته می‌شود، نه حذفِ بی‌صدا",
          "why" in D.decompose(old, 240))
    short = pts([(5.0, T)] * 3)
    check("نقطهٔ بازهٔ گذشته نباشد = INSUFFICIENT",
          D.decompose(short, 1440)["status"] == "INSUFFICIENT")

    # ── ۷) خط کپشن و خلاصهٔ چندبازه‌ای ───────────────────────────────────
    ln = D.line(d)
    check("خط کپشن هر دو اثر را با عدد می‌گوید",
          ln and "عرضه" in ln and "کل بازار" in ln and "٪" in ln, str(ln))
    sm = D.summary(s)
    check("خلاصه روی سه بازه حساب می‌شود",
          {"60m", "240m", "1440m"} <= set(sm), str(list(sm)))

    # ── ۸) مرز صادقانه روی خودِ خروجی است (قانون ۱۲) ─────────────────────
    check("مرز صادقانه روی خروجی نوشته شده",
          "شاهد است نه دروازه" in d["limit"], d["limit"])

    # ── ۹) تفکیک USDT.D از USDC.D (بند ۳) ────────────────────────────────
    def spts(pairs, step_min=5):
        n = len(pairs)
        return [{"t": (i - n + 1) * step_min * 60000 + 10**12,
                 "u": u, "c": c, "b": 56.0, "m": T}
                for i, (u, c) in enumerate(pairs)]

    both_up = spts([(5.0, 2.0)] * 48 + [(5.2, 2.2)])
    sp = D.stable_split(both_up, 240)
    check("هر دو استیبل بالا = RISK_OFF (فرارِ واقعی)",
          sp["label"] == "RISK_OFF", str(sp)[:200])
    rot = spts([(5.0, 2.0)] * 48 + [(5.2, 1.8)])
    sp2 = D.stable_split(rot, 240)
    check("یکی بالا یکی پایین = چرخش بین استیبل‌ها، نه ریسک‌آف",
          sp2["label"] == "STABLE_ROTATION", str(sp2)[:200])
    check("و صریح می‌گوید خواندنش به‌عنوان ریسک‌آف خطاست",
          "خطای تفسیر" in sp2["story"], sp2["story"])
    down = spts([(5.0, 2.0)] * 48 + [(4.8, 1.8)])
    check("هر دو پایین = RISK_ON",
          D.stable_split(down, 240)["label"] == "RISK_ON")
    part = spts([(5.0, 2.0)] * 48 + [(5.2, 2.0)])
    check("فقط یکی حرکت کرده = شاهد ضعیف، نه حکم",
          D.stable_split(part, 240)["label"] == "PARTIAL")
    check("بدون USDC در سری = INSUFFICIENT (قانون ۱)",
          D.stable_split(s, 240)["status"] == "INSUFFICIENT")
    check("خط کپشن تفکیک، هر دو عدد را می‌گوید",
          "USDT.D" in (D.split_line(sp) or "")
          and "USDC.D" in (D.split_line(sp) or ""), str(D.split_line(sp)))
    check("خلاصه، تفکیک استیبل را هم دارد",
          "stable_split" in D.summary(both_up))
    rsrc = (HERE / "research.py").read_text(encoding="utf-8")
    check("منبع جهانی، USDC را جدا می‌خواند", '"usdc_dominance"' in rsrc)

    # ── ۹.۵) پهنای بازار: TOTAL در برابر TOTAL2/TOTAL3 (بند ۶) ───────────
    def bpts(rows, step_min=5):
        n = len(rows)
        return [{"t": (i - n + 1) * step_min * 60000 + 10**12,
                 "u": 5.0, "c": 2.0, "b": b, "e": e, "m": m}
                for i, (b, e, m) in enumerate(rows)]

    # آلت‌سیزن: کل بازار +۵٪ ولی سهم BTC/ETH پایین → TOTAL3 خیلی جلوتر
    alt = bpts([(56.0, 12.0, T)] * 288 + [(52.0, 11.0, T * 1.05)])
    ab = D.alt_breadth(alt, 1440)
    check("رشدِ عرضی = ALT_BREADTH", ab["label"] == "ALT_BREADTH", str(ab)[:220])
    check("و TOTAL3 واقعاً از TOTAL جلوتر شمرده شده",
          ab["total3_pct"] > ab["total_pct"], str(ab)[:200])
    # حرکت بیت‌کوینی: کل بازار +۵٪ ولی همه‌اش از BTC
    mega = bpts([(56.0, 12.0, T)] * 288 + [(60.0, 12.0, T * 1.05)])
    check("حرکت سرهای بزرگ = MEGA_CAP_LED",
          D.alt_breadth(mega, 1440)["label"] == "MEGA_CAP_LED",
          str(D.alt_breadth(mega, 1440))[:220])
    flat = bpts([(56.0, 12.0, T)] * 289)
    check("بازارِ بی‌تکان = FLAT و بدون خط کپشن",
          D.alt_breadth(flat, 1440)["label"] == "FLAT"
          and D.breadth_line(D.alt_breadth(flat, 1440)) is None)
    check("سری بدون سهم ETH = INSUFFICIENT (قانون ۱)",
          D.alt_breadth(s, 1440)["status"] == "INSUFFICIENT")
    check("خط کپشن هر سه عدد را می‌گوید",
          all(k in (D.breadth_line(ab) or "")
              for k in ("TOTAL", "TOTAL2", "TOTAL3")), str(D.breadth_line(ab)))
    check("خلاصه، پهنای بازار را هم دارد", "breadth" in D.summary(alt))

    # ── ۱۰) اتاق دامیننس واقعاً مخرج را ذخیره می‌کند ─────────────────────
    src = (HERE / "dominance.py").read_text(encoding="utf-8")
    check("سری، کل ارزش بازار را ذخیره می‌کند (وگرنه تجزیه ابدی خالی است)",
          '_pt["m"] = mcap' in src)
    check("تجزیه به خروجی اتاق وصل است", '"decomposition": decomp' in src)
    check("سری، USDC.D را هم ذخیره می‌کند (بند ۳)", '_pt["c"] = usdc' in src)
    check("سری، سهم ETH را هم ذخیره می‌کند (بند ۶ — TOTAL3)",
          '_pt["e"] = ethd' in src)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
