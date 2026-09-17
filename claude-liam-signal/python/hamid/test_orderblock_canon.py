"""پاسبان تعریفِ اردر بلاک و ارزِ بلاک‌شده — دستور حمید، ۱۶ سپتامبر.

## چرا این فایل هست

حمید: «بارها دیده‌ام از ۱۰ موردی که می‌گویم چند مورد از قلم می‌افتد، مثل
همین شناسایی اردر بلاک در استراتژی خودم — من گفته بودم اولین کندل رنگ
مخالف که بدنهٔ آن از مجموع کل شدوهایش بزرگ‌تر باشد اردر بلاک است، و برای
اثبات آن باید گذشته را در همان تایم‌فریم بررسی کرد تا مشخص شود واکنشی
داشته یا خیر. ولی در پنل این اصل رعایت نشده.»

درست بود. `hamid/orderblock.py` از ۱۲ اوت تعریف را مو به مو داشت، ولی
موتور پنل (`liam9_strategy.order_block_zone`) پیاده‌سازیِ **جدای خودش** را
داشت که فقط رنگِ کندل را می‌سنجید. کلاسِ عیب: یک مفهوم، دو پیاده‌سازی،
یکی بی‌صدا واگرا می‌شود. این آزمون همان کلاس را می‌بندد — نه فقط این
نمونه را.

    python3 -m hamid.test_orderblock_canon
"""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import orderblock as OB                   # noqa: E402
from hamid import universe as U                      # noqa: E402
from hamid import base_map as BM                     # noqa: E402
import liam9_strategy as S                           # noqa: E402

ROOT = HERE.parents[2]
OK, FAIL = 0, []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


# ── ۱) دو پیاده‌سازیِ «بدنه > مجموع شدوها» هرگز واگرا نمی‌شوند ────────────
rnd = random.Random(17)
diverged = []
for _ in range(5000):
    o = rnd.uniform(1, 100)
    c = o * rnd.uniform(0.97, 1.03)
    hi = max(o, c) * rnd.uniform(1.0, 1.02)
    lo = min(o, c) * rnd.uniform(0.98, 1.0)
    k = {"o": o, "h": hi, "l": lo, "c": c}
    # **سه** پیاده‌سازی، نه دو. تصحیح ۱۷ سپتامبر: وقتی این پاسبان نوشته شد
    # گفتم «یک مفهوم، دو پیاده‌سازی» و همان را بستم — ولی نقشهٔ پایه
    # (`base_map._strong_body`) پیاده‌سازیِ سومی داشت که کسی نشمرده بود، و
    # دقیقاً همان چیزی است که **دامیننس تتر** با آن تحلیل می‌شود. محافظی
    # که کلاس را ناقص بشمارد، همان کلاس را باز می‌گذارد.
    if len({OB.body_beats_shadows(k), S.body_beats_shadows(k),
            BM._strong_body(k)}) != 1:
        diverged.append(k)
check("«بدنه > مجموع شدوها» در هر سه پیاده‌سازی یکی است (۵۰۰۰ کندل)",
      not diverged, str(diverged[:1]))

# دستی: نمونه‌هایی که تعریف را نشان می‌دهند
strong = {"o": 100.0, "c": 110.0, "h": 111.0, "l": 99.0}      # بدنه ۱۰، شدوها ۲
weak = {"o": 100.0, "c": 102.0, "h": 108.0, "l": 96.0}        # بدنه ۲، شدوها ۱۰
check("کندلِ بدنه‌دار قبول می‌شود", S.body_beats_shadows(strong))
check("کندلِ دو-دُم (بلاتکلیف) رد می‌شود — «مجموع» یعنی هر دو با هم",
      not S.body_beats_shadows(weak))
one_sided = {"o": 100.0, "c": 104.0, "h": 104.5, "l": 96.5}   # بدنه ۴، شدوها ۴
check("بدنه دقیقاً برابر مجموع شدوها = رد (باید «بزرگ‌تر» باشد)",
      not S.body_beats_shadows(one_sided))


# ── ۲) پنل بدون واکنشِ گذشته، اردر بلاک اعلام نمی‌کند ─────────────────────
def series(n=200, start=100.0, step=0.0):
    cd, px = [], start
    for i in range(n):
        o = px
        c = o + step
        cd.append({"t": 1_700_000_000_000 + i * 900_000, "o": o, "h": max(o, c) * 1.001,
                   "l": min(o, c) * 0.999, "c": c, "v": 10.0})
        px = c
    return cd


def put(cd, i, o, c, h=None, l=None):
    cd[i].update({"o": o, "c": c, "h": h if h is not None else max(o, c) * 1.0005,
                  "l": l if l is not None else min(o, c) * 0.9995})


# سریِ آرام + یک کندل قرمزِ بدنه‌دار و بعدش جهشِ بزرگ صعودی (زونِ demand)
cd = series(200)
put(cd, 150, 100.6, 99.4)                      # کندل مخالفِ بدنه‌دار
put(cd, 151, 99.4, 108.0)                      # displacement
for k in cd[152:]:
    k.update({"o": 108.0, "c": 108.2, "h": 108.4, "l": 107.9})
zone_bare = S.order_block_zone(cd, "LONG", lookback=120)
check("زونِ بکر (قیمت هرگز برنگشته) اردر بلاکِ معتبر نیست", zone_bare is None,
      str(zone_bare))
check("و با require_reaction=False دیده می‌شود ولی proven=False",
      (S.order_block_zone(cd, "LONG", lookback=120, require_reaction=False) or {}).get("proven") is False)

# حالا قیمت به زون برمی‌گردد (واکنشِ گذشته در همان تایم‌فریم)
cd2 = [dict(k) for k in cd]
for j in (160, 161):
    put(cd2, j, 101.0, 100.2, h=101.2, l=99.8)     # لمسِ زون بدون بستنِ زیرش
zone_proven = S.order_block_zone(cd2, "LONG", lookback=120)
check("زونی که قیمت به آن واکنش داده، اردر بلاکِ اثبات‌شده است",
      zone_proven is not None and zone_proven["proven"] and zone_proven["reactions"] >= 1,
      str(zone_proven))
check("مرزهای زون از بدنهٔ کندلِ مخالف می‌آید، نه از شدوهایش",
      abs(zone_proven["lo"] - 99.4) < 1e-6 and abs(zone_proven["hi"] - 100.6) < 1e-6,
      str(zone_proven))

# کندلِ مخالفِ دو-دُم نباید زون بسازد
cd3 = [dict(k) for k in cd2]
put(cd3, 150, 100.1, 99.9, h=103.0, l=97.0)        # بدنهٔ ریز، شدوهای بلند
check("کندلِ مخالفِ بی‌بدنه اردر بلاک نمی‌سازد (بند «مجموع شدوها»)",
      S.order_block_zone(cd3, "LONG", lookback=120) is None)

# زونی که قیمت از آن رد شده = مصرف‌شده، نه معتبر
cd4 = [dict(k) for k in cd2]
for j in (170, 171):
    put(cd4, j, 99.0, 97.0)                        # کلوز زیر زون
check("زونِ مصرف‌شده (کلوز از آن رد شده) معتبر نیست",
      S.order_block_zone(cd4, "LONG", lookback=120) is None)

# قرینهٔ شورت
cdn = series(200)
put(cdn, 150, 99.4, 100.6)                         # کندل سبزِ بدنه‌دار
put(cdn, 151, 100.6, 92.0)                         # جهشِ نزولی
for k in cdn[152:]:
    k.update({"o": 92.0, "c": 91.8, "h": 92.1, "l": 91.6})
for j in (160, 161):
    put(cdn, j, 99.0, 99.8, h=100.2, l=98.8)
zs = S.order_block_zone(cdn, "SHORT", lookback=120)
check("قرینهٔ شورت هم همان دو بند را رعایت می‌کند",
      zs is not None and zs["role"] == "supply" and zs["proven"], str(zs))

# ── ۲ب) نقشهٔ پایه (و پس دامیننس تتر) هم بندِ اثباتِ واکنش را دارد ────────
#
# حمید، ۱۷ سپتامبر: «بررسی کانال تلگرام خودم برای این بود که بتونی از
# همین روش دامیننس تتر رو تحلیل کنی.» نقشهٔ پایه همان چیزی است که USDT.D
# با آن خوانده می‌شود، پس تعریفِ ناقصِ OB این‌جا مستقیم روی بسترِ تصمیم
# می‌نشیند. `touched` از قبل شمرده می‌شد ولی استفاده نمی‌شد.
_bm = series(200)
put(_bm, 150, 99.4, 100.6)                         # کندلِ سبزِ بدنه‌دار
for k in _bm[151:]:
    k.update({"o": 92.0, "c": 91.8, "h": 92.1, "l": 91.6})   # قیمت پایین، برنمی‌گردد
_bare = BM.order_block_hamid(_bm, "above")
check("نقشهٔ پایه: زونِ بکر برمی‌گردد ولی proven=False",
      _bare is not None and _bare["proven"] is False and _bare["touched"] == 0,
      str(_bare))
_bm2 = [dict(k) for k in _bm]
for j in (160, 161):
    put(_bm2, j, 99.0, 99.6, h=100.0, l=98.9)      # لمسِ زون = واکنش
_pv = BM.order_block_hamid(_bm2, "above")
check("نقشهٔ پایه: زونِ واکنش‌دیده proven=True می‌شود",
      _pv is not None and _pv["proven"] and _pv["touched"] >= 1, str(_pv))
_pts_bare = [p for p in BM.reaction_points({"4h": {"ob_above": _bare}})
             if "OB" in p["kind"]]
_pts_pv = [p for p in BM.reaction_points({"4h": {"ob_above": _pv}})
           if "OB" in p["kind"]]
check("زونِ اثبات‌نشده روی نقشه برچسب می‌خورد و وزنش کمتر است",
      _pts_bare and "اثبات‌نشده" in _pts_bare[0]["kind"]
      and _pts_bare[0]["weight"] < _pts_pv[0]["weight"],
      f"{_pts_bare[:1]} · {_pts_pv[:1]}")
check("زونِ بکر حذف نمی‌شود (قانون ۱ بند ۶ — چرخهٔ عمر، نه پاک‌کردن)",
      len(_pts_bare) == 1)

# ── ۳) ارزِ بلاک‌شده (دستور حمید دربارهٔ TRX) ─────────────────────────────
check("TRX در فهرست بلاک است", "TRX" in U.BLOCKED)
for s in ("TRXUSDT", "TRX", "trxusdt", "TrxUsdt"):
    check(f"«{s}» بلاک شناخته می‌شود", U.is_blocked(s))
for s in ("BTCUSDT", "TRUMPUSDT", "TRUUSDT", "", None):
    check(f"«{s}» بلاک نیست (ارزِ هم‌ریشه قربانی نمی‌شود)", not U.is_blocked(s))

bt = (HERE.parent / "backtest.py").read_text(encoding="utf-8")
check("جهانِ نمادها ارزِ بلاک‌شده را از تحلیل بیرون می‌گذارد", "is_blocked(r[\"symbol\"])" in bt)
tg = (HERE.parent / "telegram.py").read_text(encoding="utf-8")
check("گلوگاه ارسال لایهٔ دوم بلاک را دارد", "is_blocked as _blk" in tg)
pp = (HERE / "paper.py").read_text(encoding="utf-8")
check("هیچ دفتری (سیگنال یا آزمایش) ردیفِ ارزِ بلاک‌شده نمی‌سازد",
      "if is_blocked(s[\"symbol\"]):" in pp)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}: {FAIL}")
    sys.exit(1)
print(f"پاسبان تعریف اردر بلاک و ارزِ بلاک‌شده: هر {OK} بررسی سبز")
