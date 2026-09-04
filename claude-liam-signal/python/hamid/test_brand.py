"""پاسبان امضای پنل روی عکس چارت (۴ سپتامبر) — آفلاین، بدون شبکه.

دستور صریح حمید (۳ سپتامبر): «در سیگنالی که ارسال می‌شود، عکس چارت
نوشته شود؛ حتماً بنویس **پنل ققنوس و محافظانش**» و «اطلاعات تکمیلیِ
کمک‌کننده به حافظه از گذشته به پنل جدید داده شود».

عیبی که این پاسبان می‌بندد ریز ولی کشنده است: matplotlib فارسی را
نه می‌چسباند نه راست‌به‌چپ می‌چیند، و فونتِ رانر اموجی ندارد. امضایی که
«حروف جدا و برعکس» یا «مربع خالی» چاپ شود، امضا نیست.
"""
import sys
import tempfile
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import chart                                          # noqa: E402

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


def synth(n=140):
    cd, p = [], 100.0
    for i in range(n):
        p *= 1.0 + (0.004 if i % 3 else -0.003)
        o = p
        c = p * (1.002 if i % 2 else 0.998)
        cd.append({"t": 1_700_000_000_000 + i * 900_000, "o": o,
                   "h": max(o, c) * 1.002, "l": min(o, c) * 0.998, "c": c, "v": 100.0})
    return cd


CD = synth()
SETUP = {"sym": "BTCUSDT", "tf": "15m", "dir": "LONG", "strategy": "ibs", "rr": 2.1,
         "conf": 68, "entry": CD[-1]["c"], "sl": CD[-1]["c"] * 0.97,
         "tp1": CD[-1]["c"] * 1.04, "tp2": CD[-1]["c"] * 1.08}

# ── ۱. متن امضا ─────────────────────────────────────────────────────────
check("متن امضا دقیقاً همان جملهٔ حمید است",
      chart.BRAND_FA == "پنل ققنوس و محافظانش", chart.BRAND_FA)
shaped = chart.fa(chart.BRAND_FA)
check("متن فارسی به شکل‌های چسبان تبدیل می‌شود (نه حروف جدا)",
      shaped != chart.BRAND_FA and any(0xFE70 <= ord(c) <= 0xFEFF for c in shaped),
      repr(shaped))
check("و راست‌به‌چپ چیده می‌شود — حرف اولِ دیداری آخرِ منطقی است",
      shaped.strip()[0] != chart.BRAND_FA[0], repr(shaped))
check("متن انگلیسی دست‌نخورده می‌ماند", chart.fa("LONG BTCUSDT") == "LONG BTCUSDT")
check("متن خالی موتور را نمی‌ترکاند", chart.fa("") == "")

# ── ۲. فونت واقعاً گلیف دارد ────────────────────────────────────────────
from matplotlib import font_manager as fm             # noqa: E402
from fontTools.ttLib import TTFont                    # noqa: E402

path = fm.findfont(fm.FontProperties(family=chart._FA_FAMILY), fallback_to_default=False)
cps = set()
for t in TTFont(path, fontNumber=0)["cmap"].tables:
    cps |= set(t.cmap)
missing = [hex(ord(c)) for c in shaped if c != " " and ord(c) not in cps]
check(f"فونت {chart._FA_FAMILY} همهٔ گلیف‌های امضا را دارد", not missing, str(missing))
check("نشانِ کنار امضا هم در فونت هست (اموجی نه — مربع خالی ممنوع)",
      ord("✦") in cps and ord("🔥") not in cps)
check("و کد از همان نشانِ موجود استفاده می‌کند، نه اموجی",
      "✦" in (HERE.parent / "chart.py").read_text(encoding="utf-8"))

# ── ۳. ترسیم واقعی بدون هشدارِ گلیفِ گم‌شده ────────────────────────────
with tempfile.TemporaryDirectory() as td:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        out = chart.render(CD, dict(SETUP), str(Path(td) / "a.png"))
        glyph = [str(x.message) for x in w if "missing from font" in str(x.message)]
    check("عکس ساخته می‌شود", Path(out).exists() and Path(out).stat().st_size > 5000)
    check("و هیچ گلیفی گم نیست (امضای مربع‌خالی = امضای خراب)", not glyph, str(glyph[:2]))

    # با حکم شورا
    s2 = dict(SETUP, phoenix={"label": "تأیید قوی", "score": 0.52})
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        out2 = chart.render(CD, s2, str(Path(td) / "b.png"))
        glyph2 = [str(x.message) for x in w if "missing from font" in str(x.message)]
    check("حکم ققنوس هم روی عکس می‌آید و گلیفش کامل است",
          Path(out2).exists() and not glyph2, str(glyph2[:2]))
    check("عکسِ با حکم از عکسِ بی‌حکم متفاوت است (خط واقعاً کشیده شد)",
          Path(out2).stat().st_size != Path(out).stat().st_size)

    # حکمِ ناقص نباید چیزی بشکند
    for bad in ({"phoenix": {}}, {"phoenix": {"score": 0.1}},
                {"phoenix": {"label": "تأیید", "score": None}}):
        try:
            chart.render(CD, dict(SETUP, **bad), str(Path(td) / "c.png"))
            ok = True
        except Exception as e:                        # noqa: BLE001
            ok = False
            print(f"      ↳ {type(e).__name__}: {e}")
        check(f"حکمِ ناقص {list(bad['phoenix'].keys()) or 'خالی'} عکس را نمی‌کشد", ok)

# ── ۴. امضا جای درست می‌نشیند (قانون ۰۴: دور از ورود/استاپ/تارگت) ──────
src = (HERE.parent / "chart.py").read_text(encoding="utf-8")
check("امضا بالای نمودار است، نه روی ناحیهٔ قیمت",
      'ax.text(1.0, 1.085, "✦ "' in src)
check("و از تابع مستقل _brand می‌آید تا یک‌جا نگهداری شود", "def _brand(" in src)
check("امضای کانال Trade_Osuli حذف نشده — این‌یکی کنارش نشست",
      "@Trade_Osuli" in src)
check("_brand در مسیر ترسیم واقعاً صدا زده می‌شود",
      '_brand(ax, s.get("phoenix"))' in src)

# ── ۵. اطلاعات تکمیلیِ حافظه روی پیام (بند دوم دستور) ──────────────────
tg = (HERE.parent / "telegram.py").read_text(encoding="utf-8")
check("جملهٔ حافظه دربارهٔ همین ارز/جهت روی کپشن می‌آید",
      's.get("memory")' in tg and "🧠" in tg)
check("امضای پنل روی هر پیام هست (قانون ۱۶ اوت)", "PANEL_NAME" in tg)
check("حکم شورا هم روی کپشن می‌آید", "caption_lines" in tg)
check("و حکم قبل از ترسیم عکس ساخته می‌شود، پس عکس آن را دارد",
      tg.index('s["phoenix"] = _phx.judge') < tg.index("png = render_chart(s"))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
