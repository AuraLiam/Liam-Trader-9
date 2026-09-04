"""پاسبان اتاق ساختار (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دستور حمید: «گزارش بدهد این ارز در ۴س چه، ۱س چه، ۱۵د چه…
و نقص را به واحد مربوطه برگرداند — مثلاً به ایجنت روند بگوید این‌جا
باید کانال را بهتر بکشی — یا همه چیز اوکی است و می‌رود جلو.»

و مرزها: ترتیب ۴س→۱س→۱۵د، تایم پایین بالادست را نقض نمی‌کند، دادهٔ
نبوده جعل نمی‌شود، و این اتاق سیگنال صادر نمی‌کند.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import lines_wf as LW                     # noqa: E402
from hamid import structure_room as SR               # noqa: E402

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


def synth(shape, n=300):
    return LW.synth(shape, n=n)


def down(cd, drop=0.35):
    """همان سری، ولی نزولی — برای ساختن تعارضِ تایم‌ها."""
    out = []
    for i, c in enumerate(cd):
        f = 1.0 - drop * i / max(1, len(cd) - 1)
        out.append({**c, "o": c["o"] * f, "h": c["h"] * f,
                    "l": c["l"] * f, "c": c["c"] * f})
    return out


FULL = {"4h": synth("channel_up"), "1h": synth("ascending_triangle"),
        "15m": synth("range")}

# ── ۱. گزارش سه‌تایم ─────────────────────────────────────────────────────
r = SR.report("TESTUSDT", FULL)
check("ترتیب گزارش ۴س → ۱س → ۱۵د است (قانون ۰۰)", r["order"] == ["4h", "1h", "15m"])
check("هر سه تایم گزارش دادند", all(r["timeframes"][tf]["ok"] for tf in SR.ORDER))
for tf in SR.ORDER:
    t = r["timeframes"][tf]
    check(f"[{tf}] روند، نقشهٔ خط، مکان و حجم هر چهار آمدند",
          t.get("trend") and "geometry" in t["map"] and "location" in t and "volume" in t)
check("اردر بلاک فقط در ۱س و ۱۵د گزارش می‌شود (دستور حمید)",
      "ob" not in r["timeframes"]["4h"] and "ob" in r["timeframes"]["1h"]
      and "ob" in r["timeframes"]["15m"])
check("گزارش فارسی هر سه تایم را نام می‌برد",
      all(f"• {tf}:" in r["text"] for tf in SR.ORDER))
check("هندسه با نام فارسی چاپ می‌شود، نه کلید انگلیسی",
      "کانال صعودی" in r["text"] and "channel_up" not in r["text"])
check("مرز صادقانه روی خروجی نوشته شده", "سیگنال صادر نمی‌کند" in r["boundary"])

# ── ۲. نقص به واحد مربوطه برمی‌گردد ─────────────────────────────────────
short = {"4h": FULL["4h"], "1h": FULL["1h"], "15m": FULL["15m"][:20]}
r2 = SR.report("TESTUSDT", short)
d15 = [d for d in r2["defects"] if d["tf"] == "15m"]
check("تایمِ بی‌کندلِ کافی نقص می‌سازد، نه گزارشِ ساختگی",
      r2["timeframes"]["15m"]["ok"] is False and d15)
check("هر نقص مالک دارد (کدام واحد)", all(d.get("unit") and d.get("unit_fa") for d in r2["defects"]))
check("هر نقص کارِ خواسته‌شده را می‌نویسد، نه فقط شکایت",
      all(d.get("ask") for d in r2["defects"]))
check("نقص با نام فارسی واحد روی گزارش می‌آید",
      "برگشت به واحدها" in r2["text"] and "ایجنت" in r2["text"])
check("نقص سلسله‌مراتب هم گرفته می‌شود (کمتر از سه تایم)",
      any("سلسله‌مراتب" in d["what"] or "تایم از" in d["what"] for d in r2["defects"]),
      str([d["what"] for d in r2["defects"]]))

flat = [{"t": i * 900_000, "o": 100.0, "h": 100.02, "l": 99.98, "c": 100.0, "v": 10.0}
        for i in range(300)]
r3 = SR.report("FLATUSDT", {"4h": flat, "1h": flat, "15m": flat})
lines_d = [d for d in r3["defects"] if d["unit"] == "lines"]
check("سری بی‌ساختار → نقص به ایجنت خط‌کشی برمی‌گردد", bool(lines_d),
      str([d["what"] for d in r3["defects"]]))
check("و متنِ خواسته دقیقاً همان چیزی است که حمید گفت (بهتر بکش)",
      any("بهتر بکش" in d["ask"] or "بهتر بکش" in d["what"] for d in lines_d),
      str([d["ask"] for d in lines_d]))
check("نقص‌دار = آمادهٔ جلو رفتن نیست", r3["ready"] is False)

# ── ۳. «ستاپ نیست» نقص نیست ─────────────────────────────────────────────
rng = {"4h": synth("range"), "1h": synth("range"), "15m": synth("range")}
r4 = SR.report("RANGEUSDT", rng)
check("رنجِ سالم نقصِ خط‌کشی نمی‌سازد — نبودِ ستاپ عیب نیست",
      not [d for d in r4["defects"] if d["unit"] == "lines"],
      str([d["what"] for d in r4["defects"]]))
check("۴س رنج، ری افقی می‌دهد پس نقصِ ری هم ندارد",
      r4["timeframes"]["4h"]["map"]["rays"] != [])

# ── ۴. حجم: عدد ساخته نمی‌شود ───────────────────────────────────────────
nov = [{k: v for k, v in c.items() if k != "v"} for c in synth("range")]
v = SR.volume_state(nov)
check("بی‌حجم = unknown با دلیل، نه «عادی»",
      v["state"] == "unknown" and v["ratio"] is None and "ساخته نمی‌شود" in v["why"])
r5 = SR.report("NOVOLUSDT", {"4h": nov, "1h": nov, "15m": nov})
check("و همان بی‌حجمی به ایجنت حجم برمی‌گردد",
      any(d["unit"] == "volume" for d in r5["defects"]))
hot = [dict(c, v=10.0) for c in synth("range")]
for c in hot[-3:]:
    c["v"] = 100.0
check("حجم بالای میانه hot خوانده می‌شود", SR.volume_state(hot)["state"] == "hot")
cold = [dict(c, v=10.0) for c in synth("range")]
for c in cold[-3:]:
    c["v"] = 1.0
check("حجم زیر میانه cold خوانده می‌شود", SR.volume_state(cold)["state"] == "cold")
check("نسبت حجم عدد واقعی است نه برچسبِ تنها",
      isinstance(SR.volume_state(hot)["ratio"], float))

# ── ۵. جهت‌گیری: تایم بالا حاکم است ─────────────────────────────────────
s = SR.stance({"4h": {"trend": "up", "ok": True}, "1h": {"trend": "up", "ok": True},
               "15m": {"trend": "up", "ok": True}})
check("سه تایم صعودی = LONG", s["bias"] == "LONG")
s = SR.stance({"4h": {"trend": "up", "ok": True}, "1h": {"trend": "down", "ok": True},
               "15m": {"trend": "down", "ok": True}})
check("۴س خلافِ ۱س = CONFLICT و صریح می‌گوید تایم بالا حاکم است (قانون ۲)",
      s["bias"] == "CONFLICT" and "قانون ۲" in s["why"], str(s))
s = SR.stance({"4h": {"trend": "down", "ok": True}, "1h": {"trend": "down", "ok": True}})
check("دو تایم نزولی = SHORT", s["bias"] == "SHORT")
s = SR.stance({"4h": {"trend": "range", "ok": True}, "1h": {"trend": "range", "ok": True}})
check("بی‌جهت = RANGE، نه حدسِ جهت", s["bias"] == "RANGE")
s = SR.stance({"4h": {"trend": "up", "ok": True}})
check("یک تایم = UNKNOWN، جهت اعلام نمی‌شود", s["bias"] == "UNKNOWN")
r6 = SR.report("CONFUSDT", {"4h": synth("channel_up"), "1h": down(synth("channel_up")),
                            "15m": synth("range")})
check("تعارضِ واقعی از مسیر گزارش هم گرفته می‌شود",
      r6["stance"]["bias"] in ("CONFLICT", "RANGE", "UNKNOWN"), str(r6["stance"]))

# ── ۶. مکان قیمت ────────────────────────────────────────────────────────
loc = r["timeframes"]["4h"]["location"]
check("مکان قیمت داخل الگو با درصد ارتفاع گزارش می‌شود",
      loc["pos_pct"] is not None and 0 <= loc["pos_pct"] <= 100, str(loc))
loc1 = r["timeframes"]["1h"]["location"]
check("نزدیک‌ترین ری افقی با فاصلهٔ درصدی می‌آید",
      loc1["nearest_ray"] and loc1["ray_dist_pct"] is not None, str(loc1))
check("قیمت ری بدون نویزِ ممیز شناور چاپ می‌شود",
      len(str(loc1["nearest_ray"]["price"])) <= 14, str(loc1["nearest_ray"]["price"]))

# ── ۷. سیم‌کشی ──────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
check("برنامهٔ درسی اتاق ساختار موجود است",
      (ROOT / "brain" / "library" / "curricula" / "E07-structure-room.md").exists())
check("موتور خط‌کشی همین اتاق را تغذیه می‌کند", SR.LW is LW)
check("لنگرِ هر تایم تعریف‌شده است", set(SR.ANCHOR_DAYS) >= set(SR.ORDER))
check("اتاق چیزی روی دیسک نمی‌نویسد (قانون ۰۵: یک نویسنده برای هر دامنه)",
      "open(" not in (HERE / "structure_room.py").read_text(encoding="utf-8"))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
