"""پاسبان ریزساختار تایم پایین — همراه اجباری microstructure.py + scenarios.py.

سه عیبِ واقعی که حین ساخت همین ماژول پیدا و رفع شدند، این‌جا برای همیشه
قفل می‌شوند (هر سه با اندازه‌گیری پیدا شدند، نه با بازخوانی کد):

۱. **برجستگیِ همسایه‌محور**: اولین فیلترِ معناداری، پیوت را با کندل‌های
   بلافصلش می‌سنجید. روی هر نقطهٔ برگشتِ نرم آن فاصله ذاتاً ~صفر است، پس
   *همهٔ* پیوت‌ها حذف می‌شدند و structure برمی‌گشت None. جایگزین: طولِ لگ.
۲. **مصرف‌نشدن سطح**: در روند صاف، `_last_confirmed` همان سقف قدیمی را
   برمی‌گرداند و هر کندل یک BOS تازه اعلام می‌شد — ۳۵۴ رویداد از فقط ۳
   پیوت. حالا سطح شکسته‌شده مصرف می‌شود.
۳. **زنجیرهٔ غیرمتناوب**: بدون قاعدهٔ زیگ‌زاگ، سقف‌های پشت‌سرهم جای هم را
   می‌گرفتند و کف هرگز پذیرفته نمی‌شد.
"""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import microstructure as MS               # noqa: E402
from hamid import scenarios as SC                    # noqa: E402

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


def walk(n=2000, seed=7, vol=0.0015):
    """قدم‌زدن تصادفی — نزدیک‌ترین چیز به «بازار بدون لبه».

    vol پیش‌فرض ۰.۱۵٪ بر کندل است، نه کمتر: با نوسان پایین‌تر، استاپِ
    ساختاریِ ۱ دقیقه آن‌قدر تنگ می‌شود که کارمزد بیش از ۳۰٪ از R را
    می‌خورد و دروازهٔ کارمزد (درست) همه‌چیز را رد می‌کند — پس فیکسچرِ
    کم‌نوسان، تستِ سناریو را روی لیست خالی «الکی سبز» می‌کرد."""
    rng = random.Random(seed)
    cd, px = [], 100.0
    for i in range(n):
        px *= (1 + rng.gauss(0, vol))
        cd.append({"t": i * 60000, "o": px,
                   "h": px + abs(rng.gauss(0, vol)) * px,
                   "l": px - abs(rng.gauss(0, vol)) * px,
                   "c": px, "v": 1.0})
    return cd


CD = walk()

# ── سشن ───────────────────────────────────────────────────────────────────
H = 3600000
check("سشن آسیا (۰۲ UTC)", MS.session_of(2 * H) == "asia")
check("سشن لندن (۰۹ UTC)", MS.session_of(9 * H) == "london")
check("همپوشانی لندن+نیویورک (۱۳ UTC)", MS.session_of(13 * H) == "overlap")
check("سشن نیویورک (۱۸ UTC)", MS.session_of(18 * H) == "ny")

# ── پیوت: تأیید تأخیری، تناوب، معناداری ──────────────────────────────────
hi, lo = MS.pivots(CD)
check("پیوت سقف و کف هر دو پیدا می‌شوند", len(hi) > 5 and len(lo) > 5,
      f"{len(hi)}H/{len(lo)}L")
check("هر پیوت دقیقاً R کندل بعد تأیید می‌شود (ضد نگاه به آینده)",
      all(p["confirmed_at_i"] == p["i"] + MS.PIVOT_R for p in hi + lo))
chain = sorted(hi + lo, key=lambda p: p["i"])
check("زنجیره سقف/کف یک‌درمیان است (قاعدهٔ زیگ‌زاگ — عیب ۳)",
      all(chain[k]["kind"] != chain[k + 1]["kind"] for k in range(len(chain) - 1)))

# عیب ۱: فیلتر معناداری نباید همه‌چیز را حذف کند
for leg in (0.0, 1.0, 2.0):
    h2, l2 = MS.pivots(CD, min_leg_atr=leg)
    check(f"با min_leg_atr={leg} هنوز پیوت می‌ماند (عیب ۱: حذف کامل)",
          len(h2) > 0 and len(l2) > 0, f"{len(h2)}H/{len(l2)}L")
h_lo, _ = MS.pivots(CD, min_leg_atr=0.0)
h_hi, _ = MS.pivots(CD, min_leg_atr=3.0)
check("سخت‌گیری بیشتر = پیوت کمتر (فیلتر واقعاً کار می‌کند)",
      len(h_hi) < len(h_lo), f"{len(h_hi)} < {len(h_lo)}")

# ── ساختار: چگالی رویداد، مصرف سطح، بدون نگاه به آینده ───────────────────
st = MS.structure(CD)
check("ساختار خروجی می‌دهد و نسخه‌دار است",
      st and st["formula_version"] == MS.STRUCT_VERSION)
ev = st["events"]
dens = len(ev) / (len(CD) / 100)
check("چگالی رویداد معقول است، نه هر کندل یک BOS (عیب ۲)",
      0.2 < dens < 20, f"{dens:.2f} رویداد در هر ۱۰۰ کندل")
check("هیچ سطحی دوبار پشت‌سرهم رویداد نمی‌سازد (مصرف سطح)",
      all(not (ev[k]["level"] == ev[k + 1]["level"] and ev[k]["dir"] == ev[k + 1]["dir"])
          for k in range(len(ev) - 1)))
check("روی قدم‌زدن تصادفی BOS و CHoCH هر دو دیده می‌شوند (نه فقط یکی)",
      any(e["kind"] == "BOS" for e in ev) and any(e["kind"] == "CHoCH" for e in ev))
check("هر رویداد برچسب سشن دارد (دستور حمید)",
      all(e.get("session") in ("asia", "london", "ny", "overlap") for e in ev))

# بدون نگاه به آینده: بریدن دنبالهٔ سری نباید رویدادهای گذشته را عوض کند
cut = 1200
st_full = MS.structure(CD)
st_pref = MS.structure(CD[:cut])
past_full = [e for e in st_full["events"] if e["i"] < cut - MS.PIVOT_R - 1]
past_pref = [e for e in st_pref["events"] if e["i"] < cut - MS.PIVOT_R - 1]
check("رویدادهای گذشته با دیدن آینده تغییر نمی‌کنند (اثبات، نه ادعا)",
      past_full == past_pref,
      f"full={len(past_full)} prefix={len(past_pref)}")

# ── سناریو: جدول شاخه‌ها ─────────────────────────────────────────────────
p = SC.plan(CD, "TESTUSDT")
check("دفتر سناریو شاخه می‌سازد", len(p["branches"]) >= 1, str(p.get("why")))
check("هر شاخه ماشهٔ عددی و جهت دارد",
      all(b.get("level") and b.get("action") in ("LONG", "SHORT")
          for b in p["branches"]))
check("هر شاخه نوعش (BOS/CHoCH) را حمل می‌کند تا جدا سنجیده شود",
      all(b["kind"] in ("BOS", "CHoCH") for b in p["branches"]))
check("اهرم هرگز از محافظ لیکویید رد نمی‌شود",
      all(b["leverage"] <= int(SC.P["liq_guard"] / b["stop_pct_at_level"])
          for b in p["branches"]))
check("شاخهٔ لانگ بالای سطح و شورت زیر سطح ماشه می‌خورد",
      all((b["condition"] == "close > level") == (b["action"] == "LONG")
          for b in p["branches"]))

# resolve: قرارداد اجرا کامل، هندسه درست
lng = next((b for b in p["branches"] if b["action"] == "LONG"), None)
if lng:
    r = SC.resolve(lng, lng["level"] * 1.0005)
    check("resolve: لانگ → استاپ زیر ورود، تارگت بالای ورود",
          r["sl"] < r["entry"] < r["tp1"], str(r))
    check("resolve: قرارداد اجرا (ایزوله + SL/TP اجباری)",
          r["margin_mode"] == "isolated" and r["sl_tp_mandatory"]
          and r["stop_loss"] == r["sl"] and r["take_profit"] == r["tp1"])
    check("resolve: فاصلهٔ استاپ همان چیزی است که از پیش حساب شده بود",
          abs((r["entry"] - r["sl"]) - lng["stop_dist"]) < 1e-8)
    check("resolve: نسبت تارگت به استاپ = rr_target",
          abs((r["tp1"] - r["entry"]) / (r["entry"] - r["sl"])
              - lng["rr_target"]) < 1e-6)
sht = next((b for b in p["branches"] if b["action"] == "SHORT"), None)
if sht:
    r2 = SC.resolve(sht, sht["level"] * 0.9995)
    check("resolve: شورت → استاپ بالای ورود، تارگت زیر ورود",
          r2["tp1"] < r2["entry"] < r2["sl"], str(r2))

# check(): ماشه فقط با بستن، نه ویک
if lng:
    below = {"c": lng["level"] * 0.999}
    above = {"c": lng["level"] * 1.001}
    check("ماشه با کلوزِ زیر سطح شلیک نمی‌شود",
          SC.check([lng], below) is None)
    check("ماشه با کلوزِ بالای سطح شلیک می‌شود",
          SC.check([lng], above) is lng)

# ── پنجرهٔ زیست‌پذیری نوسان (یافتهٔ ۲۲ اوت — قفل می‌شود) ─────────────────
# اسکلپ ساختاریِ ۱ دقیقه فقط در یک نوارِ نوسانی حساب می‌آید و این حسابِ
# ریاضی است، نه سلیقه:
#   • نوسانِ خیلی کم  → استاپ ساختاری چنان تنگ که کارمزد ۰.۱۵٪ بیش از
#     ۳۰٪ از R را می‌خورد → دام کارمزد → NO_TRADE
#   • نوسانِ خیلی زیاد → استاپ از سقف ۱.۶٪ اسکلپ رد می‌شود → NO_TRADE
# پس «کدام ۳۰ ارز» سؤال سلیقه‌ای نیست؛ جواب از همین نوار درمی‌آید.
band = {}
for v in (0.0006, 0.0010, 0.0015, 0.0020, 0.0030, 0.0045):
    band[v] = len(SC.plan(walk(vol=v), "X")["branches"])
check("نوسان خیلی کم = بی‌شاخه (دام کارمزد، نه سکوت بی‌دلیل)",
      band[0.0006] == 0 and band[0.0010] == 0, str(band))
check("نوسان میانه = شاخه ساخته می‌شود",
      band[0.0015] > 0 and band[0.0020] > 0 and band[0.0030] > 0, str(band))
check("نوسان خیلی زیاد = بی‌شاخه (استاپ از سقف اسکلپ رد می‌شود)",
      band[0.0045] == 0, str(band))

# دادهٔ ناکافی = بی‌شاخه با دلیل، نه حدس (قانون ۱)
short_plan = SC.plan(CD[:10], "X")
check("کندل ناکافی = بدون شاخه و با دلیلِ نوشته‌شده (قانون ۱)",
      short_plan["branches"] == [] and short_plan["why"], str(short_plan.get("why")))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان ریزساختار و سناریو: هر {OK} بررسی سبز")
