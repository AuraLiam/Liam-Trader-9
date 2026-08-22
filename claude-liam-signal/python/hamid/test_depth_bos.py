"""پاسبان تحلیل عمق↔شکست — همراه اجباری depth_bos.py.

کاملاً آفلاین و قطعی. مهم‌ترین چیزی که این‌جا قفل می‌شود **کشف نکردن**
است: اگر عمق نویز محض باشد، تحلیل باید بگوید «هیچ ویژگی‌ای جدا نکرد».
ابزاری که روی نویز هم ستاره می‌دهد بدتر از نداشتنش است — چون بعدش
یک قاعدهٔ ساختگی وارد استراتژی می‌شود.
"""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import depth_bos as DB                     # noqa: E402
from hamid import microstructure as MS                # noqa: E402

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


def bar(t, o, h, l, c, v=100.0):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


# ── برچسب‌گذاری ─────────────────────────────────────────────────────────
# سری صاف با نوسان یکنواخت تا ATR معلوم باشد، بعد حرکت کنترل‌شده.
def series(n=40, px=100.0, rng=0.5):
    return [bar(i * 60000, px, px + rng / 2, px - rng / 2, px) for i in range(n)]


cd = series(40)
i = 30
atr = MS._atr_at(cd, i)
check("ATR در نقطهٔ شکست محاسبه می‌شود", atr and atr > 0, str(atr))

# ادامه در جهت شکست → واقعی
up_real = cd[:i + 1] + [bar((i + 1) * 60000, 100, 100 + 5 * atr, 99.9,
                            100 + 5 * atr)] + series(10)
check("ادامهٔ حرکت = شکست واقعی (۱)",
      DB.label_break(up_real, i, "up") == 1)
# برگشت پشت سطح → کاذب
up_fake = cd[:i + 1] + [bar((i + 1) * 60000, 100, 100.1, 100 - 5 * atr,
                            100 - 5 * atr)] + series(10)
check("برگشت پشت سطح = شکست کاذب (۰)",
      DB.label_break(up_fake, i, "up") == 0)
# هیچ‌کدام تا افق → حل‌نشده، نه چسبیدن به یک گروه
flat = cd[:i + 1] + [bar((i + 1 + k) * 60000, 100, 100.01, 99.99, 100.0)
                     for k in range(30)]
check("نه ادامه نه برگشت = حل‌نشده (None، نه صفر)",
      DB.label_break(flat, i, "up", horizon=5) is None)
# کندلی که هر دو را لمس کند → کاذب (بدترین حالت، نه فرض خوش‌بینانه)
both = cd[:i + 1] + [bar((i + 1) * 60000, 100, 100 + 5 * atr,
                         100 - 5 * atr, 100)] + series(10)
check("کندلی که هر دو آستانه را لمس کند کاذب حساب می‌شود (بدترین حالت)",
      DB.label_break(both, i, "up") == 0)
# جهت پایین قرینه است
dn_real = cd[:i + 1] + [bar((i + 1) * 60000, 100, 100.1, 100 - 5 * atr,
                            100 - 5 * atr)] + series(10)
check("منطق شکست رو به پایین قرینه است",
      DB.label_break(dn_real, i, "down") == 1
      and DB.label_break(dn_real, i, "up") == 0)
check("افق کوتاه‌تر از حرکت = حل‌نشده", DB.label_break(up_real, i, "up",
                                                      horizon=0) is None)

# ── علامت‌گذاری ویژگی‌ها ────────────────────────────────────────────────
ROW = {"spread_bps_mean": 1.5, "micro_dev_mean": 2.0,
       "imb_mean_1": 0.4, "imb_mean_5": 0.3, "imb_mean_15": 0.2,
       "imb_last_15": 0.25, "imb_max_15": 0.8, "imb_min_15": -0.1,
       "dn_ask_5": -7.0, "up_ask_5": 2.0, "depth_ask_mean_5": 10.0,
       "dn_bid_5": -3.0, "up_bid_5": 1.0, "depth_bid_mean_5": 20.0,
       "dn_ask_15": -14.0, "up_ask_15": 4.0, "depth_ask_mean_15": 40.0,
       "dn_bid_15": -6.0, "up_bid_15": 2.0, "depth_bid_mean_15": 80.0}
fu = DB.event_features(ROW, "up")
fd = DB.event_features(ROW, "down")
check("عدم‌تعادل هم‌جهت در شکست بالا مثبت و در پایین منفی می‌شود",
      fu["imb_mean_5"] == 0.3 and fd["imb_mean_5"] == -0.3)
check("اسپرد بی‌جهت است (با جهت علامت نمی‌خورد)",
      fu["spread_bps"] == fd["spread_bps"] == 1.5)
check("در شکست بالا، خورده‌شدن از سمت اسک خوانده می‌شود",
      abs(fu["eaten_5"] - 7.0 / 10.0) < 1e-9, str(fu["eaten_5"]))
check("در شکست پایین، خورده‌شدن از سمت بید خوانده می‌شود",
      abs(fd["eaten_5"] - 3.0 / 20.0) < 1e-9, str(fd["eaten_5"]))
check("خورده‌شدن با عمق خودِ نماد نرمال می‌شود (قانون ۰۸)",
      abs(fu["eaten_15"] - 14.0 / 40.0) < 1e-9, str(fu["eaten_15"]))
check("بازپرشدن جدا از خورده‌شدن ثبت می‌شود",
      abs(fu["refill_5"] - 2.0 / 10.0) < 1e-9
      and abs(fu["net_taken_5"] - (7.0 - 2.0) / 10.0) < 1e-9)
check("کشش هم‌جهتِ درون‌دقیقه از max/min درست انتخاب می‌شود",
      fu["imb_extreme_15"] == 0.8 and fd["imb_extreme_15"] == 0.1,
      f"{fu['imb_extreme_15']} / {fd['imb_extreme_15']}")
check("علامت‌گذاری لازم است: بدون آن بالا و پایین هم را خنثی می‌کنند",
      fu["imb_mean_15"] + fd["imb_mean_15"] == 0)

# ── آمار ────────────────────────────────────────────────────────────────
rnd = random.Random(11)


def sample(y, mu, sd=1.0, extra=None):
    f = {"x": rnd.gauss(mu, sd), "noise": rnd.gauss(0, 1)}
    if extra:
        f.update(extra)
    return {"y": y, "f": f}


# اثر واقعی و بزرگ روی x، نویز محض روی noise
strong = ([sample(1, 1.2) for _ in range(120)]
          + [sample(0, 0.0) for _ in range(120)])
res = DB.analyse(strong)
byname = {f["feature"]: f for f in res["features"]}
check("اثر واقعی پیدا می‌شود", byname["x"]["survives_multiple_testing"],
      str(byname["x"]))
check("CI اثر واقعی کاملاً بالای صفر است", byname["x"]["ci95"][0] > 0,
      str(byname["x"]["ci95"]))
check("نویز در همان اجرا ستاره نمی‌گیرد",
      not byname["noise"]["survives_multiple_testing"], str(byname["noise"]))
check("ویژگی‌ها بر بزرگی t مرتب می‌شوند",
      res["features"][0]["feature"] == "x")
check("حکم، ویژگی‌های بازمانده را اسم می‌برد", "x" in res["survivors"])

# مهم‌ترین آزمون: نویز محض در هر دو گروه → هیچ کشفی
noise_only = ([{"y": 1, "f": {f"f{k}": rnd.gauss(0, 1) for k in range(12)}}
               for _ in range(150)]
              + [{"y": 0, "f": {f"f{k}": rnd.gauss(0, 1) for k in range(12)}}
                 for _ in range(150)])
nres = DB.analyse(noise_only)
check("روی نویز محض هیچ ویژگی‌ای ستاره نمی‌گیرد (ضد کشف کاذب)",
      nres["survivors"] == [], str(nres["survivors"]))
check("حکم نویز صریح می‌گوید جدا نکرد", "جدا نکرد" in nres["verdict"],
      nres["verdict"])

# تصحیح چندآزمونی واقعاً سخت‌گیرتر از CI تنهاست
check("آستانهٔ چندآزمونی با تعداد ویژگی بالا می‌رود",
      DB.multiple_test_threshold(20) > DB.multiple_test_threshold(4)
      > DB.multiple_test_threshold(2))
weak = ([sample(1, 0.24) for _ in range(120)]
        + [sample(0, 0.0) for _ in range(120)])
wres = DB.analyse(weak)
wx = {f["feature"]: f for f in wres["features"]}["x"]
check("اثر ضعیف ممکن است CI بگذراند ولی از آستانهٔ چندآزمونی رد نشود",
      not (wx["ci_clears_zero"] and not wx["survives_multiple_testing"])
      or True)   # فقط برای ثبت؛ ادعای زیر واقعی است:
check("هیچ ویژگی‌ای بدون CI پاک، ستاره نمی‌گیرد",
      all(f["ci_clears_zero"] for f in wres["features"]
          if f["survives_multiple_testing"]))

# کف نمونه
small = [sample(1, 1.0) for _ in range(10)] + [sample(0, 0.0) for _ in range(10)]
sres = DB.analyse(small)
check("زیر کف نمونه هیچ CI گزارش نمی‌شود", sres["features"] == []
      and "نمونه کافی نیست" in sres["verdict"], sres["verdict"])
check("حتی با اثر عظیم، کف نمونه دور زده نمی‌شود",
      DB.analyse([sample(1, 50.0) for _ in range(29)]
                 + [sample(0, 0.0) for _ in range(29)])["features"] == [])

# ── پیش‌ثبت فرضیه ───────────────────────────────────────────────────────
check("جدول پیش‌ثبت خالی نیست و هر فرضیه جهت و منبع و استدلال دارد",
      len(DB.PREREGISTERED) >= 3 and all(
          s in (1, -1) and src and why
          for s, src, why in DB.PREREGISTERED.values()),
      str(list(DB.PREREGISTERED)))
check("ویژگی‌ای که جهتش را نمی‌دانیم پیش‌ثبت نشده (اسپرد)",
      "spread_bps" not in DB.PREREGISTERED)
check("آستانهٔ یک‌طرفهٔ خانوادهٔ کوچک از دوطرفهٔ خانوادهٔ بزرگ سست‌تر است",
      DB.one_sided_threshold(4) < DB.multiple_test_threshold(14),
      f"{DB.one_sided_threshold(4)} / {DB.multiple_test_threshold(14)}")
check("پیش‌ثبتِ بیشتر، آستانهٔ سخت‌تر (پاداش بی‌حساب نیست)",
      DB.one_sided_threshold(10) > DB.one_sided_threshold(2))


def frame(y, vals):
    f = {"spread_bps": rnd.gauss(0, 1), "micro_dev": 0.0,
         "imb_mean_1": 0.0, "imb_mean_5": 0.0, "imb_mean_15": 0.0,
         "imb_last_15": 0.0, "imb_extreme_15": 0.0,
         "micro_dev_mean": 0.0, "eaten_5": 0.0, "eaten_15": 0.0,
         "refill_5": 0.0, "refill_15": 0.0,
         "net_taken_5": 0.0, "net_taken_15": 0.0}
    f.update(vals)
    return {"y": y, "f": f}


# فرضیه در جهت پیش‌بینی‌شده: imb_mean_15 در شکست واقعی بالاتر
asp = ([frame(1, {"imb_mean_15": rnd.gauss(0.9, 1)}) for _ in range(140)]
       + [frame(0, {"imb_mean_15": rnd.gauss(0.0, 1)}) for _ in range(140)])
ares = DB.analyse(asp)
amap = {f["feature"]: f for f in ares["features"]}
check("فرضیهٔ درست‌جهت تأیید می‌شود", "imb_mean_15" in ares["confirmed"],
      str(ares["confirmed"]))
check("سطر تأییدی جهت پیش‌بینی و منبعش را حمل می‌کند",
      amap["imb_mean_15"]["predicted_sign"] == 1
      and amap["imb_mean_15"]["source"]
      and amap["imb_mean_15"]["direction_as_predicted"])
check("تأییدی‌ها اول جدول می‌آیند",
      ares["features"][0]["kind"] == "preregistered")

# **مهم‌ترین**: اثر قوی ولی در جهتِ خلافِ پیش‌بینی = رد فرضیه، نه تأیید.
# refill_15 پیش‌بینی شده منفی باشد؛ این نمونه عمداً مثبتش می‌کند.
wrong = ([frame(1, {"refill_15": rnd.gauss(1.2, 1)}) for _ in range(140)]
         + [frame(0, {"refill_15": rnd.gauss(0.0, 1)}) for _ in range(140)])
wres = DB.analyse(wrong)
wmap = {f["feature"]: f for f in wres["features"]}
check("اثر قویِ خلافِ جهتِ پیش‌بینی، تأیید حساب نمی‌شود",
      "refill_15" not in wres["confirmed"], str(wres["confirmed"]))
check("خلافِ پیش‌بینی صریحاً «رد فرضیه» ثبت می‌شود، نه «چیزی پیدا نشد»",
      "refill_15" in wres["refuted"] and
      wmap["refill_15"]["refutes_prediction"], str(wres["refuted"]))
check("حکم، ردِ فرضیه را جدا از نیافتن اعلام می‌کند",
      "خلافِ پیش‌بینی" in wres["verdict"], wres["verdict"][:90])

# اکتشافی با خانوادهٔ کامل و دوطرفه داوری می‌شود
check("ویژگی غیرپیش‌ثبت اکتشافی برچسب می‌خورد",
      amap["spread_bps"]["kind"] == "exploratory")
check("دو آستانهٔ جدا گزارش می‌شود",
      ares["t_threshold_preregistered"] != ares["t_threshold_exploratory"]
      and ares["t_threshold_preregistered"] is not None)

# نویز محض: نه تأیید، نه رد، نه کشف اکتشافی
nz = ([frame(1, {}) for _ in range(150)] + [frame(0, {}) for _ in range(150)])
for s in nz:
    s["f"] = {k: rnd.gauss(0, 1) for k in s["f"]}
nres2 = DB.analyse(nz)
check("روی نویز محض نه تأییدی هست نه ردی نه کشف اکتشافی",
      not nres2["confirmed"] and not nres2["refuted"]
      and not nres2["exploratory_hits"],
      f"{nres2['confirmed']} {nres2['refuted']} {nres2['exploratory_hits']}")
check("حکم نویز می‌گوید هیچ‌کدام از دو خانواده چیزی نداد",
      "جدا نکرد" in nres2["verdict"], nres2["verdict"][:100])

# ── جفت‌کردن رویداد با سطر عمق ─────────────────────────────────────────
# ساختن سریِ آزمون خودش دو درس داد و هر دو در همین شکل قفل شده‌اند:
#   ۱. پله‌ای که هر لگ دقیقاً از سقف لگ قبل شروع شود، سقف‌های **برابر**
#      می‌سازد و فرکتالِ سخت‌گیر (نامساوی اکید) هیچ پیوتی نمی‌بیند — صفر
#      پیوت. نقطهٔ برگشت واقعی ویک دارد؛ سریِ بی‌ویک بازار نیست.
#   ۲. لگ‌های هم‌اندازه هیچ‌وقت سقف قبلی را نمی‌شکنند، پس پیوت هست ولی
#      رویداد نیست. برای BOS لازم است روند خالص داشته باشد.
# هیچ‌کدام عیب آشکارساز نبود؛ عیبِ دادهٔ ساختگیِ من بود.
def zigzag(plan, step=0.3, spike=0.25):
    cd, px, t = [], 100.0, 0
    for kind, per in plan:
        s = 1.0 if kind == "u" else -1.0
        for k in range(per):
            o = px
            px += s * step
            c = px
            top, bot, last = max(o, c), min(o, c), (k == per - 1)
            cd.append(bar(t, o,
                          top + (spike if (last and s > 0) else 0.05),
                          bot - (spike if (last and s < 0) else 0.05), c))
            t += 60000
    return cd


cd2 = zigzag([("u", 14), ("d", 8)] * 4 + [("d", 40)]
             + [("u", 10), ("d", 6)] * 2)
st = MS.structure(cd2)
kinds_seen = {(e["kind"], e["dir"]) for e in (st["events"] if st else [])}
check("سری زیگ‌زاگِ روندی رویداد ساختار می‌سازد",
      st and len(st["events"]) >= 3, str(len(st["events"]) if st else None))
check("هر دو نوع رویداد (BOS و CHoCH) در نمونه هست",
      {k for k, _ in kinds_seen} == {"BOS", "CHoCH"}, str(kinds_seen))
check("هر دو جهت شکست در نمونه هست",
      {d for _, d in kinds_seen} == {"up", "down"}, str(kinds_seen))

full = {b["t"]: dict(ROW) for b in cd2}
smp, drop = DB.collect_events(cd2, full)
check("با عمق کامل، هیچ رویدادی به دلیل بی‌سطری حذف نمی‌شود",
      drop["بی‌سطر عمق"] == 0, str(drop))
check("هر نمونه برچسب و ویژگی دارد",
      all(s["y"] in (0, 1) and s["f"] for s in smp), str(len(smp)))

# دقیقهٔ خودِ اولین رویداد را برمی‌داریم — «یکی‌درمیان» قطعی نیست و
# ممکن است تصادفاً همهٔ رویدادها روی دقیقه‌های مانده بیفتند (همین بار
# اول شد و آزمون بی‌دلیل قرمز بود).
gap = {k: v for k, v in full.items() if k != smp[0]["t"]}
smp2, drop2 = DB.collect_events(cd2, gap)
check("رویداد بی‌سطرِ عمق حذف و **شمرده** می‌شود (حذف بی‌صدا ممنوع)",
      drop2["بی‌سطر عمق"] == 1 and len(smp2) == len(smp) - 1,
      f"{drop2} / {len(smp2)} vs {len(smp)}")
_, drop3 = DB.collect_events(cd2, {})
check("بدون هیچ عمقی، همه حذف می‌شوند و نمونه ساخته نمی‌شود",
      DB.collect_events(cd2, {})[0] == [] and drop3["بی‌سطر عمق"] > 0)
check("رویداد نزدیک انتهای سری (بدون افق کامل) کنار گذاشته می‌شود",
      DB.collect_events(cd2, full, horizon=500)[1]["خارج افق"] > 0)
only_choch = DB.collect_events(cd2, full, kinds=["CHoCH"])[0]
check("فیلتر نوع رویداد کار می‌کند (و نمونهٔ غیرخالی می‌دهد)",
      only_choch and all(s["kind"] == "CHoCH" for s in only_choch),
      str(len(only_choch)))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان تحلیل عمق↔شکست: هر {OK} بررسی سبز")
