"""پاسبان خط‌کشی رو-به-جلو (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دقیقاً همان چیزهایی را که حمید خواست و همان‌هایی که در ساختِ
این موتور یک بار شکستند:

- خط از **یک هفته قبل** ساخته می‌شود و آینده فقط نمره می‌دهد
  (اثبات منفی: آیندهٔ عوض‌شده نباید نامزدها را تکان بدهد).
- **کانال تحمیل نمی‌شود** — مثلث متقارن/صعودی/نزولی، رنج و پهن‌شونده هم
  باید با نام خودشان شناخته شوند.
- برخورد **رویداد** است نه کندل (وگرنه ۱۵۳ برخورد در ۱۵۰ کندل).
- خطی که قیمت نصفِ عمرش را آن‌سویش بسته، **سطح نیست** — همان عیبی که
  کانالِ صعودی را از هندسه بیرون کرده بود.
- ویک و بدنه دو ستون جدا (قانون ۰۰ و سند خطوط).
- هر حذف **دلیل** دارد؛ بی‌صدا نمی‌افتد.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import lines_wf as L                      # noqa: E402

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


# ── ۱. هندسه کشف می‌شود، تحمیل نمی‌شود ────────────────────────────────────
SHAPES = ("ascending_triangle", "descending_triangle", "symmetric_triangle",
          "channel_up", "channel_down", "range", "broadening")
built = {}
for s in SHAPES:
    r = L.build(L.synth(s), "15m", days=2.0)
    built[s] = r
    check(f"هندسهٔ {s} درست شناخته شد", r["geometry"]["shape"] == s,
          f"گرفت: {r['geometry']['shape']}")
check("هر هندسه دلیلِ فارسی دارد", all(built[s]["geometry"].get("why") for s in SHAPES))
check("سه مثلث با هم قاطی نمی‌شوند (دستور: کانال اجباری نیست)",
      len({built[s]["geometry"]["shape"] for s in
           ("ascending_triangle", "descending_triangle", "symmetric_triangle")}) == 3)
check("کانال صعودی و نزولی از هم جدا می‌مانند",
      built["channel_up"]["geometry"]["shape"] != built["channel_down"]["geometry"]["shape"])

# هندسهٔ بی‌جفت = none صریح، نه کانالِ زورکی
g = L.geometry([{"kind": "res", "type": "trend", "i0": 0, "p0": 100.0, "slope": 0.0,
                 "score": {"wick_touches": 5}}], L.synth("range"), a=1.0)
check("بدون خطِ حمایت هندسه ساخته نمی‌شود و صریح none می‌گوید",
      g["shape"] == "none" and "حمایت" in g["why"])

# ── ۲. اثبات منفی: آینده خط نمی‌سازد ─────────────────────────────────────
cd = L.synth("channel_up")
i0 = L.anchor_index(cd, 2.0, "15m")
a = L.atr(cd[:i0]) or L.atr(cd)
c_base = L.candidates(cd[:i0], a)

cd2 = [dict(x) for x in cd]
for i in range(i0, len(cd2)):                        # آینده را زیر و رو می‌کنیم
    cd2[i] = dict(cd2[i], h=cd2[i]["h"] * 3, l=cd2[i]["l"] / 3,
                  c=cd2[i]["c"] * 2, o=cd2[i]["o"] * 2)
c_after = L.candidates(cd2[:i0], a)
key = lambda ls: sorted((l["kind"], l["type"], round(l["p0"], 9), round(l["slope"], 9))  # noqa: E731
                        for l in ls)
check("آیندهٔ عوض‌شده نامزدها را تکان نمی‌دهد (خط‌کشی بدون دیدن آینده)",
      key(c_base) == key(c_after), f"{len(c_base)} vs {len(c_after)}")
check("و نامزد اصلاً وجود دارد — آزمونِ توخالی نباشد", len(c_base) >= 5, str(len(c_base)))
r1, r2 = L.build(cd, "15m", days=2.0), L.build(cd2, "15m", days=2.0)
check("ولی نمرهٔ همان نامزدها با آیندهٔ دیگر فرق می‌کند (آینده فقط نمره می‌دهد)",
      r1["kept_n"] != r2["kept_n"] or r1["dropped_n"] != r2["dropped_n"])
for s in SHAPES:                                     # همین را از مسیر خودِ build هم می‌بندیم
    b = built[s]
    late = [l for l in b["kept"] if max(l["anchors"]) >= b["anchor_i"]]
    check(f"[{s}] هیچ خطِ ماندگاری لنگرِ بعد از نقطهٔ لنگر ندارد", not late,
          f"{len(late)} خط از آینده لنگر گرفته")
check("لنگر جلوتر از کندل‌های تأیید پیوت است",
      i0 >= L.PIVOT_L * 2 + 2 and i0 < len(cd) - 1, str(i0))
check("لنگر ۲ روزه روی ۱۵د ≈ ۱۹۲ کندل عقب است",
      abs((len(cd) - i0) - 192) <= 2, f"{len(cd) - i0}")

# ── ۳. برخورد رویداد است، نه کندل ────────────────────────────────────────
flat = [{"t": i * 900_000, "o": 100.0, "h": 100.05, "l": 99.95, "c": 100.0, "v": 1.0}
        for i in range(150)]
line = {"kind": "res", "type": "level", "i0": 0, "p0": 100.05, "slope": 0.0}
st = L.score_forward(line, flat, 0, a=1.0)
check("قیمتِ چسبیده به خط یک برخورد است نه ۱۵۰تا",
      st["wick_touches"] == 1, f"{st['wick_touches']} برخورد")
zig = []
for i in range(150):                                 # هر ۱۰ کندل یک بار می‌رسد
    top = 100.0 if i % 10 == 0 else 96.0
    zig.append({"t": i * 900_000, "o": top - 1, "h": top, "l": top - 2, "c": top - 1, "v": 1.0})
st = L.score_forward({"kind": "res", "type": "level", "i0": 0, "p0": 100.0, "slope": 0.0},
                     zig, 0, a=1.0)
check("رسیدنِ دوره‌ای، به تعداد دفعات شمرده می‌شود", st["wick_touches"] == 15,
      str(st["wick_touches"]))

# ── ۴. ویک و بدنه جدا ────────────────────────────────────────────────────
wick_only = [{"t": i * 900_000, "o": 98.0, "h": 100.0, "l": 97.0, "c": 98.0, "v": 1.0}
             if i % 10 == 0 else
             {"t": i * 900_000, "o": 96.0, "h": 96.5, "l": 95.5, "c": 96.0, "v": 1.0}
             for i in range(60)]
st = L.score_forward({"kind": "res", "type": "level", "i0": 0, "p0": 100.0, "slope": 0.0},
                     wick_only, 0, a=1.0)
check("ویک خورده ولی بدنه نپذیرفته → دو ستون جدا",
      st["wick_touches"] >= 5 and st["body_accepts"] == 0, str(st))
check("خطِ فقط-ویکی ACTIVE می‌ماند و شکسته اعلام نمی‌شود", st["state"] == "ACTIVE")

# ── ۵. احترام: خطِ تزئینی می‌افتد ────────────────────────────────────────
cross = []
for i in range(90):
    if i % 9 == 0:                                   # هر ۹ کندل یک بار خط را لمس می‌کند
        cross.append({"t": i * 900_000, "o": 99.0, "h": 100.1, "l": 98.0, "c": 99.0, "v": 1.0})
    elif i % 9 == 1:                                 # و واکنشِ واقعی هم می‌دهد
        cross.append({"t": i * 900_000, "o": 98.0, "h": 98.5, "l": 97.0, "c": 97.5, "v": 1.0})
    else:                                            # ولی بیشترِ عمرش بالای خط بسته می‌شود
        cross.append({"t": i * 900_000, "o": 104.0, "h": 105.0, "l": 103.0, "c": 104.0, "v": 1.0})
st = L.score_forward({"kind": "res", "type": "level", "i0": 0, "p0": 100.0, "slope": 0.0},
                     cross, 0, a=1.0)
check("خطی که قیمت بیشترِ عمرش را آن‌سویش بسته، احترام پایین می‌گیرد",
      st["wick_touches"] >= L.MIN_TOUCH and st["reactions"] >= L.MIN_REACT
      and st["respect"] < L.RESPECT_MIN, str(st))
ok, why = L.keep_or_drop({}, st)
check("و با دلیلِ صریح پاک می‌شود، بی‌صدا نمی‌ماند",
      ok is False and "تزئینی" in why, why)
ok, why = L.keep_or_drop({}, {"wick_touches": 2, "reactions": 2, "respect": 1.0})
check("کمتر از سه برخورد = رد (Edwards & Magee + قاعدهٔ حمید)",
      ok is False and str(L.MIN_TOUCH) in why, why)
ok, why = L.keep_or_drop({}, {"wick_touches": 5, "reactions": 1, "respect": 1.0})
check("برخورد بی‌واکنش = خطِ بی‌اثر", ok is False and "بی‌اثر" in why, why)
ok, why = L.keep_or_drop({}, {"wick_touches": 4, "reactions": 3, "respect": 1.0,
                              "state": "ACTIVE"})
check("خطِ سالم می‌ماند و کارنامه‌اش روی دلیل چاپ می‌شود",
      ok is True and "احترام" in why and "برخورد" in why, why)
check("احترام روی خروجی هر خط ثبت می‌شود",
      all("respect" in l["score"] for l in built["range"]["kept"]))

# ── ۵ب. هوریزنتال ری: سقف/کفی که نقش S/R گرفته، افقی علامت می‌خورد ──────
check("رنج دو ری افقی می‌دهد (سقف و کف)",
      len(built["range"]["rays"]) == 2
      and {r["kind"] for r in built["range"]["rays"]} == {"sup", "res"},
      str(built["range"]["rays"]))
check("مثلث صعودی فقط سقفش ری است، کفِ بالارونده ری نیست",
      [r["kind"] for r in built["ascending_triangle"]["rays"]] == ["res"],
      str(built["ascending_triangle"]["rays"]))
check("مثلث نزولی فقط کفش ری است",
      [r["kind"] for r in built["descending_triangle"]["rays"]] == ["sup"],
      str(built["descending_triangle"]["rays"]))
check("کانال هیچ ری افقی ندارد — خط مورب ری نمی‌شود",
      built["channel_up"]["rays"] == [] and built["channel_down"]["rays"] == [])
check("هر ری قیمت و دلیل خودش را همراه دارد",
      all(r.get("price") is not None and r.get("why") for r in built["range"]["rays"]))

# ── ۶. Sperandeo: خط از قیمتِ بین دو لنگر رد نمی‌شود ────────────────────
for s in ("symmetric_triangle", "channel_up"):
    cdx = L.synth(s)
    ix = L.anchor_index(cdx, 2.0, "15m")
    ax = L.atr(cdx[:ix]) or 1.0
    bad = []
    for ln in L.candidates(cdx[:ix], ax):
        if ln["type"] != "trend":
            continue
        i1, i2 = ln["anchors"][0], ln["anchors"][-1]
        for j in range(i1 + 1, i2):
            lp = L._line_at(ln, j)
            if ln["kind"] == "res" and cdx[j]["h"] > lp + 0.16 * ax:
                bad.append((s, j))
            if ln["kind"] == "sup" and cdx[j]["l"] < lp - 0.16 * ax:
                bad.append((s, j))
    check(f"[{s}] هیچ خط روندی از قیمتِ بین دو لنگرش رد نشده (Sperandeo)",
          not bad, str(bad[:3]))

# ── ۷. حذف با دلیل، و شلوغی مهار می‌شود ─────────────────────────────────
r = built["symmetric_triangle"]
check("حذف‌ها با دلیل گزارش می‌شوند (نه بی‌صدا)",
      r["dropped_n"] > 0 and all(d.get("why") for d in r["dropped"]))
check("شمار واقعیِ ماندگارها جدا از فهرستِ بریده گزارش می‌شود",
      r["kept_n"] == len([x for x in r["kept"]]) or r["kept_n"] >= len(r["kept"]))
check("چارت شلوغ نمی‌شود (انضباط Brandt) — حداکثر ۱۲ خط روی خروجی",
      all(len(built[s]["kept"]) <= 12 for s in SHAPES))
check("ده‌ها نامزد به چند خط می‌رسند",
      all(built[s]["candidates"] > built[s]["kept_n"] for s in SHAPES))

# ── ۸. دادهٔ کم: صریح، نه خطِ جعلی ───────────────────────────────────────
r = L.build([{"t": i, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1} for i in range(20)], "15m")
check("کندل کم = اعلام صریح، نه خط‌کشی روی هوا",
      r["ok"] is False and r["geometry"]["shape"] == "none" and "کندل کم" in r["why"])
check("و همان‌جا هم کلیدهای خروجی سر جایشان‌اند", set(("kept", "dropped")) <= set(r))

# ── ۹. سیم‌کشی ───────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
check("قانونِ مرجع خطوط موجود است",
      (ROOT / ".claude" / "rules" / "trendlines-canon.md").exists())
check("خروجی قاعده‌اش را روی خودش می‌نویسد",
      "آینده فقط نمره" in built["range"]["rule"])

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
