#!/usr/bin/env python3
"""پاسبان موتور شورتِ داشبورد (۷ سپتامبر) — آفلاین، بدون شبکه.

خودآزماییِ خودِ فایل را می‌دود و روی آن **قراردادها** را قفل می‌کند:
هرگز LONG · مجوز تولید ندارد تا CI بدهد · قرارداد اجرا · اعدادِ داخل
سند با ثابت‌های کد یکی باشند (وگرنه سند و کد از هم جدا می‌افتند — همان
عیبی که `test_skill_injection` برای اسکلپ می‌گیرد).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

import liam9_short_strategy as S                     # noqa: E402

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


# ── ۱. خودآزماییِ خودِ موتور ─────────────────────────────────────────────
print("  — خودآزمایی موتور —")
check("خودآزمایی موتور سبز است", S._selftest())

# ── ۲. این موتور فقط شورت است ───────────────────────────────────────────
#
# فایلِ «استراتژی شورت» که بتواند LONG بدهد، یعنی استراتژی‌ها قاتی شده‌اند
# (قانون ۰۱ بند ۷: هر خروجی شناسه/نسخهٔ خودش را دارد و استراتژی‌ها مخلوط
# نمی‌شوند).
_src = (PY / "liam9_short_strategy.py").read_text(encoding="utf-8")
check('هیچ‌جا "LONG" برنمی‌گرداند',
      '"action": "LONG"' not in _src and "'action': 'LONG'" not in _src)

now = 1788800000000
cd = S._zig(end=now, **S.REF)
cd4 = S._zig(legs=6, down=10, up=5, end=now, tf_ms=14_400_000)
# بسترِ دامیننس، اولویتِ اولِ حمید (۸ سپتامبر) — بی‌آن، آلت سیگنال
# نمی‌گیرد (قانون ۰۱ بند ۳). سناریوی مرجع بسترِ هم‌جهت می‌گیرد.
d = S.decide("AAAUSDT", cd, cd_4h=cd4, btc_4h="down", btc_1h="down",
             equity=1000, now_ms=now, alt_stance="SHORT_ALT")
check("سناریوی مرجع به SHORT می‌رسد", d["action"] == "SHORT", d.get("why"))

# ── ۳. مرزِ قانون ۰۳/۱۲ — بی‌CI وارد تولید نمی‌شود ───────────────────────
check("مجوز تولید ندارد", S.PRODUCTION_APPROVED is False)
# خاصیت، نه شکل: وضعیت باید یکی از حالت‌های **غیرِتولیدیِ** قانون ۰۳ باشد.
# نسخهٔ قبل فقط «PAPER…» را می‌شناخت و وقتی فرضیه REJECTED شد، افتاد —
# یعنی محافظ به اسم چسبیده بود نه به معنا.
_NON_PROD = ("UNVERIFIED", "RESEARCHED", "BACKTESTED", "PAPER", "SHADOW",
             "REJECTED")
check("وضعیت ادعا از واژگان قانون ۰۳ و غیرِتولیدی است",
      S.VALIDATION_STATUS.startswith(_NON_PROD)
      and not S.VALIDATION_STATUS.startswith("PRODUCTION"),
      S.VALIDATION_STATUS)
check("و روی هر خروجی هم می‌آید",
      d["production_approved"] is False
      and d["validation_status"] == S.VALIDATION_STATUS)
check("مرزِ صادقانه روی خروجی هست و «سود» ادعا نمی‌کند",
      "PAPER_ONLY" in d["boundary"] and "شاملِ صفر" in d["boundary"])

# ── ۴. قرارداد اجرا (دستور حمید، ۲۰ اوت) ────────────────────────────────
check("مارجین ایزوله", d["margin_mode"] == "isolated")
check("کراس هیچ‌جا در فایل نیست", '"cross"' not in _src)
check("استاپ و تارگت اجباری روی خروجی",
      d.get("stop_loss") and d.get("take_profit") and d["sl_tp_mandatory"])
check("جهتِ اعداد درست است (شورت)",
      d["sl"] > d["entry"] > d["tp1"] > d["tp2"])
check("شناسه و نسخهٔ استراتژی", d["strategy"] == S.STRATEGY_ID
      and d["version"] == S.STRATEGY_VERSION)
check("امضای پنل", d["panel"] == "لیام تریدر ۹")

# ── ۵. محافظ لیکویید و سایز ─────────────────────────────────────────────
check("اهرم ≤ ۵۰÷استاپ٪ و ≤ سقف داشبورد",
      d["leverage"] <= min(S.P["max_leverage"],
                           int(S.P["liq_guard"] / d["stop_pct"])))
check("سایز از ریسکِ ۲٪ می‌آید نه از اهرم",
      abs(d["risk_usd"] - 20.0) < 0.01, str(d.get("risk_usd")))

# ── ۶. دروازه‌های اجباری واقعاً می‌بندند (قانون ۰۱) ──────────────────────
# اولویتِ اول (دستور حمید ۸ سپتامبر): بسترِ دامیننس، پیش از همه
check("بسترِ دامیننس ناموجود برای آلت = NO_SIGNAL",
      S.decide("AAAUSDT", cd, cd_4h=cd4, btc_4h="down", btc_1h="down",
               now_ms=now)["action"] == "NO_SIGNAL")
check("بسترِ ریسک‌آنِ صریح، شورتِ آلت را وتو می‌کند",
      S.decide("AAAUSDT", cd, cd_4h=cd4, btc_4h="down", btc_1h="down",
               now_ms=now, alt_stance="LONG_ALT_STRONG")["action"] == "NO_SIGNAL")
check("و مبنای این دروازه STABLE.D است نه USDT.D تنها",
      "stables" in _src and "alt_stance" in _src)
check("دروازهٔ دامیننس اولِ قیف است",
      [g["gate"] for g in d["funnel"]][:2] == ["داده", "دامیننس (اولویت ۱)"],
      str([g["gate"] for g in d["funnel"]][:3]))
check("بسترِ BTC ناموجود برای آلت = NO_SIGNAL",
      S.decide("AAAUSDT", cd, cd_4h=cd4,
               now_ms=now, alt_stance="SHORT_ALT")["action"] == "NO_SIGNAL")
check("هر دو تایمِ BTC صعودی = وتوی مطلق",
      S.decide("AAAUSDT", cd, cd_4h=cd4, btc_4h="up", btc_1h="up",
               now_ms=now, alt_stance="SHORT_ALT")["action"] == "NO_SIGNAL")
check("۴س صعودی = رد",
      S.decide("AAAUSDT", cd,
               cd_4h=S._zig(legs=6, down=10, up=5, direction="up",
                            end=now, tf_ms=14_400_000),
               btc_4h="down", btc_1h="down",
               now_ms=now, alt_stance="SHORT_ALT")["action"] == "NO_SIGNAL")
check("قیفِ دروازه‌ها روی هر خروجی هست — رد هم دلیلِ ساختاری دارد",
      isinstance(d.get("funnel"), list) and d["funnel"])

# ── ۷. سند و کد از هم جدا نیفتند ────────────────────────────────────────
#
# اعدادِ داخلِ متنِ سند اگر با ثابت‌ها یکی نمانند، فردا کسی از روی سند
# تصمیم می‌گیرد و از روی کدِ دیگری اجرا می‌شود.
_i = _src.index('"""')
doc = _src[_i + 3:_src.index('"""', _i + 3)]
check("کفِ استاپِ سند با کد یکی است",
      "استاپ ≥ ۱٪" in doc and S.P["min_stop_pct"] == 1.00)
# سه تعریفِ کلیدی باید **قرض گرفته** شوند، نه بازنویسی — ریشهٔ شکستِ
# نسخهٔ ۱.۰ همین بود و بی‌این بررسی، بی‌صدا برمی‌گردد.
check("ساختار از hamid.structure می‌آید، نه بازنویسی",
      "from hamid.structure import trend" in _src
      and "from hamid.structure import channel" in _src)
check("اردر بلاک از hamid.orderblocks می‌آید",
      "from hamid.orderblocks import near" in _src)
check("استاپ از ارتفاعِ باکس است نه ATR",
      'P["ob_buffer"] * max(ob["height"]' in _src and "0.25 * a" not in _src)
check("RR با trainer یکی است (۲.۰)", S.P["rr_target"] == 2.00)
check("آستانهٔ کانالِ سند با کد یکی است",
      "۰.۷۰" in doc and S.P["min_chan_pos"] == 0.70)
check("عددِ پایهٔ سند (−۰.۳۱۲R) نوشته شده", "−۰.۳۱۲R" in doc)
check("و نتیجهٔ خارج از نمونه هم", "خارج از نمونه" in doc)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
