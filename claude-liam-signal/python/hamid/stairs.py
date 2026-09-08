"""نردبانِ ریزش — شمارشِ «پله» روی ۱۵د (دستور حمید، ۸ سپتامبر).

حمید: «بری ارزها رو در تایم فریم ۱۵ دقیقه چک کنی اکثرا دارن پله‌ای
می‌ریزن و به اصطلاح با پولبک‌های پیاپی به اوردر بلاک‌های بالاییشون
برخورد می‌کنن و میان پایین. یعنی دقیقا ریزش و بعدش برخورد به زیر آخرین
کندل و باز ریزش. البته می‌تونه روند برگرده.»

═══════════════════════════════════════════════════════════════════════
  این فایل **دروازه نیست** — فقط می‌شمارد و برچسب می‌زند
═══════════════════════════════════════════════════════════════════════

قانون ۰۳/۱۲: هیچ ستاپی به‌خاطر یک مشاهده حذف یا تأیید نمی‌شود. کاری که
این ماژول می‌کند این است که ادعای حمید را به یک **عددِ قابل شمارش**
تبدیل کند تا ماشین شبانه بتواند داوری‌اش کند. اگر بازهٔ اطمینان از صفر
رد کرد، آن‌وقت (و فقط با تأیید صریح حمید) می‌تواند وارد تصمیم شود.

──────────────── چرا «برچسب» و نه «فیلترِ تازه» ────────────────

نسخهٔ ۱.۰ موتور شورت دقیقاً از راهِ مخالف رفت: چهار فیلتر از روی دفتر
انتخاب شد، مستقیم وارد موتور شد، و بک‌تستِ خارج از زمان **باطلش کرد**
(فیلترشده −۰.۴۶R در برابر بی‌فیلتر −۰.۱۵R). درسش این بود که فیلتر باید
اول برچسب باشد و بعد — اگر ماند — دروازه.

──────────────── تعریف‌ها، همه از کدِ موجود قرض گرفته شده ────────────────

هیچ تعریفی این‌جا از نو نوشته نشده (همان درسِ نسخهٔ ۱.۰):
  · زنجیرهٔ ساختار (پیوت + BOS/CHoCH): `microstructure.pivots/structure` —
    نسخه‌دار، با تأییدِ پیوت (`confirmed_at_i`)، با مصرفِ سطحِ شکسته، و
    با کفِ لگ `MIN_LEG_ATR` تا تکان از نوسان جدا شود.
  · اردر بلاک: `orderblocks.find` — همان تعریفی که بقیهٔ سامانه دارد.

**پله (step)** = یک رویدادِ ساختاریِ هم‌جهت. `steps=2` یعنی دو رویدادِ
نزولیِ پیاپی بدون رویداد صعودی بینشان — همان «ریزش، پولبک، باز ریزش»
که حمید توصیف کرد.

⚠️ **چرا از `structure.swings` استفاده نشد**: ممیزی E07 (۸ سپتامبر)
نشان داد پنج تعریفِ همزمان از BOS در ریپو زنده است. ساختنِ ششمی روی
`swings` دقیقاً همان اشتباهی بود که موتور شورت نسخهٔ ۱.۰ را باطل کرد.
`microstructure` انتخاب شد چون تنها یکی است که نسخه، تأییدِ پیوت، مصرفِ
سطح و محافظ دارد.

⚠️ **مرزِ صادقانه دربارهٔ `MIN_LEG_ATR=1.0`**: خودِ آن ماژول نوشته این
عدد **اعتبارسنجی‌نشده** است. شمارشِ پله به آن حساس است؛ تا sweep نشده،
هر عددِ «تعداد پله» مشروط به همین پارامتر است و باید همراهش گفته شود.

**زیرِ آخرین کندل** = فاصلهٔ قیمت تا **لبهٔ پایینیِ** نزدیک‌ترین اردر
بلاکِ بالاسری. سه حالت جدا برچسب می‌خورند چون سه چیزِ متفاوت‌اند:
  · `inside`     — قیمت داخل باکس است
  · `under_edge` — قیمت زیرِ لبه ولی نزدیک (≤ `EDGE_ATR × ATR`)؛ همان
                   چیزی که حمید توصیف کرد
  · `far`        — باکس هست ولی دور است
  · `none`       — باکس بالاسری نیست

**شکستِ نردبان** = آخرین رویدادِ ساختاری `CHoCH` باشد نه `BOS` — یعنی
ساختار همین حالا عوض شده. حمید خودش گفت «می‌تونه روند برگرده»؛ بدون این
برچسب، نردبانِ مرده از نردبانِ زنده جدا نمی‌شود.

──────────────── فرضیه‌های از پیش ثبت‌شده ────────────────

**قبل** از دیدن هر عددی ثبت شد (وگرنه برشِ بعد از دیدنِ نتیجه است):

  H1  شورت روی پلهٔ ≥۲ بهتر از پلهٔ ۱
  H2  شورت روی پلهٔ ≥۳ بهتر از پلهٔ ۱
  H3  پولبکِ «زیرِ لبهٔ OB» بهتر از «داخلِ OB»
  H4  پولبکِ عمیق (≥۰.۵ لگِ قبل) بهتر از کم‌عمق
  H5  نردبانِ نشکسته بهتر از شکسته
  H6  نردبانِ هم‌جهت با معامله بهتر از خلاف‌جهت

m=۶ فرضیه، تصحیح Šidák: α هر آزمون = ۱−۰.۹۵^(۱/۶) ≈ ۰.۰۰۸۵۱.

**قاعدهٔ توقف** (آینهٔ `scalp_verdict` و `gate_verdict`، خالص از کارمزد
با منبع واحد `hamid/fees.py`):

| حکم | شرط |
|---|---|
| `PROMOTE_CANDIDATE` | CI اختلاف کاملاً بالای صفر، n≥۱۵۰ در بازوی کوچک‌تر → فقط **پیشنهاد** به حمید |
| `REJECT` | CI اختلاف کاملاً زیر صفر روی n≥۳۰۰ |
| `UNDECIDED` | بقیه، با برآوردِ «چند نمونهٔ دیگر» |

`PROMOTE_CANDIDATE` هیچ آستانه‌ای را عوض نمی‌کند — قانون ۰۳.

اجرا:
    python3 -m hamid.stairs --selftest
    python3 -m hamid.stairs --judge          # داوری روی دفترهای موجود
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# «نزدیکِ لبه» — همان «برخورد به زیرِ آخرین کندل».
EDGE_ATR = 0.50

MAX_STEPS = 8            # سقفِ شمارش؛ بالاتر از این عدد معنا اضافه نمی‌کند

# آستانهٔ Šidák برای m=۶ فرضیهٔ از پیش ثبت‌شده (بالای همین فایل).
HYPOTHESES = 6
ALPHA_SIDAK = 1 - (1 - 0.05) ** (1 / HYPOTHESES)

# قاعدهٔ توقف — از پیش ثبت‌شده، نه بعد از دیدن عدد.
PROMOTE_MIN_N = 150
REJECT_MIN_N = 300


# ── ۱. شمارش پله ──────────────────────────────────────────────────────────
#
# **زنجیرهٔ ساختار از `hamid/microstructure.py` قرض گرفته می‌شود، نه از نو
# نوشته می‌شود.** ممیزی E07 (۸ سپتامبر) نشان داد در ریپو **پنج** تعریفِ
# همزمان از BOS زنده است (`microstructure.structure` · `ob_intel.bos_after`
# · `trainer.decide` بند B · `engine.js:smcOrderBlocks` ·
# `index.html:ibsDetectBOS`). همین کلاسِ عیب بود که موتور شورت نسخهٔ ۱.۰ را
# باطل کرد. از میان آن پنج، `microstructure` تنها یکی است که:
#   · نسخه دارد (`STRUCT_VERSION`)،
#   · سطحِ شکسته را **مصرف** می‌کند (بدون آن، روندِ صاف هر کندل یک BOS
#     می‌داد — اندازه‌گیری‌شده: ۳۵۴ رویداد از ۳ پیوت)،
#   · پیوتِ تأییدنشده را وارد تصمیم نمی‌کند (`confirmed_at_i`)،
#   · و محافظ دارد (`test_microstructure`).
# پس تعریفِ «پله» این‌جا فقط یک **شمارش روی همان زنجیره** است، نه هندسهٔ
# تازه: پله = رویدادِ ساختاریِ هم‌جهتِ پیاپی، بدون رویداد مخالف بینشان.

# سقفِ پنجره‌ای که به موتور ساختار داده می‌شود. نردبانِ امروز، نه دیروز —
# و هزینهٔ محاسبه را هم کران‌دار می‌کند.
BARS = 300


def staircase(cd, bars=BARS):
    """نردبانِ فعلی: جهت، تعداد پله، و اینکه تازه برگشته یا نه.

    فقط از `cd` می‌خواند — یعنی هر چه فراخوان به آن داده.
    """
    from hamid.microstructure import structure
    win = cd[-bars:] if len(cd) > bars else cd
    unknown = {"dir": None, "steps": 0, "hi": None, "lo": None, "lag": None,
               "broken": None, "n_ev": 0, "last_kind": None}
    st = structure(win)
    if not st or not st.get("events"):
        return dict(unknown, why="ساختاری ثبت نشد")
    evs = st["events"]
    last = evs[-1]
    d = last["dir"]
    steps = 0
    for e in reversed(evs):
        if e["dir"] != d:
            break
        steps += 1
        if steps >= MAX_STEPS:
            break
    sh, sl = st.get("swing_high"), st.get("swing_low")
    return {
        "dir": d,
        "steps": steps,
        "hi": sh["px"] if sh else None,
        "lo": sl["px"] if sl else None,
        # چند کندل از آخرین پلهٔ ثبت‌شده گذشته. نردبانِ کهنه، نردبانِ زنده
        # نیست — و بدون این عدد نمی‌شود آن دو را از هم جدا کرد.
        "lag": len(win) - 1 - last["i"],
        # «می‌تونه روند برگرده» (خودِ حمید). CHoCH یعنی ساختار همین الان
        # عوض شده؛ BOS یعنی همان جهت ادامه دارد.
        "broken": last["kind"] == "CHoCH",
        "last_kind": last["kind"],
        "n_ev": len(evs),
        "why": None,
    }


# ── ۳. عمق پولبک و رابطه با اردر بلاک بالاسری ─────────────────────────────

def depth(cd, st):
    """قیمت کجای آخرین لگ است. ۰ = روی کف، ۱ = روی سقف. None = نامعلوم."""
    hi, lo = st.get("hi"), st.get("lo")
    if hi is None or lo is None or hi <= lo:
        return None
    px = cd[-1]["c"]
    return round((px - lo) / (hi - lo), 3)


def overhead_ob(cd, tf="15m"):
    """نزدیک‌ترین اردر بلاکِ بالاسریِ نشکسته + رابطهٔ قیمت با آن.

    خروجی: (برچسب، باکس یا None). برچسب‌ها در داک‌استرینگ بالای فایل.
    """
    from hamid.orderblocks import find
    from hamid.structure import atr
    px = cd[-1]["c"]
    a = atr(cd) or px * 0.005
    best, best_d = None, None
    for b in find(cd, tf=tf):
        if b.get("broken"):
            continue
        if b["low"] <= px <= b["high"]:
            return "inside", b
        if b["low"] > px:
            d = b["low"] - px
            if best_d is None or d < best_d:
                best, best_d = b, d
    if best is None:
        return "none", None
    return ("under_edge" if best_d <= EDGE_ATR * a else "far"), best


# ── ۴. برچسبِ آمادهٔ دفتر ──────────────────────────────────────────────────

def label(cd, tf="15m", direction=None, box=None):
    """برچسبِ نردبان برای گذاشتن روی `why` هر معامله.

    `direction` (LONG/SHORT) اختیاری است؛ اگر بیاید `stair_align` هم
    ساخته می‌شود تا شرط‌های شبانه لازم نباشد جهت را از جای دیگر بخوانند.
    هیچ کلیدی حذف نمی‌شود — «نمی‌دانم» با None نوشته می‌شود، جعل نمی‌شود
    (قانون ۰۱ بند ۱).

    `box` = باکسی که خودِ موتور روی آن وارد شده. اگر بیاید،
    `stair_ob_stale` می‌گوید آن باکس **همان نزدیک‌ترین** باکسِ بالاسری
    بوده یا نه.

    چرا این فیلد اضافه شد (ممیزی اردر بلاک، ۸ سپتامبر): `orderblocks.find`
    خروجی را با `sort(key=-reactions)` مرتب می‌کند و `near()` اولین باکسِ
    آن ترتیب را برمی‌دارد — یعنی **پرواکنش‌ترین**، نه نزدیک‌ترین. در
    ریزشِ پله‌ای هر پله یک باکسِ تازه می‌سازد که `reactions=0` دارد، پس
    ته صف می‌ایستد و موتور به باکسِ کهنهٔ پلهٔ اول می‌چسبد. این دقیقاً
    همان رفتاری است که حمید توصیف کرد.
    اثباتِ ممیزی: باکسِ کهنهٔ [۱۰۲.۰–۱۰۲.۶] با ۳ واکنش (فاصله ۲.۰×ATR)
    بر باکسِ تازهٔ [۱۰۰.۶–۱۰۱.۰] (فاصله ۰.۶×ATR) مقدم شد.
    **این‌جا چیزی عوض نمی‌شود** — فقط اندازه گرفته می‌شود تا معلوم شود
    آن انتخاب چقدر هزینه دارد (قانون ۰۳).
    """
    st = staircase(cd)
    rel, near_box = overhead_ob(cd, tf=tf)
    out = {"stair_dir": st["dir"], "stair_steps": st["steps"],
           "stair_broken": st["broken"], "stair_depth": depth(cd, st),
           "stair_ob": rel, "stair_lag": st["lag"]}
    if near_box is not None:
        out["stair_ob_fresh"] = near_box.get("fresh")
        out["stair_ob_reactions"] = near_box.get("reactions")
    if box is not None and near_box is not None:
        out["stair_ob_stale"] = box.get("i") != near_box.get("i")
    if direction in ("LONG", "SHORT") and st["dir"]:
        want = "up" if direction == "LONG" else "down"
        out["stair_align"] = "with" if st["dir"] == want else "against"
    return out


def fa(lb):
    """یک خط فارسی برای کپشن/گزارش — از همان برچسب، بدون عددِ تازه."""
    if not lb or not lb.get("stair_dir"):
        return "نردبان: تشخیص داده نشد"
    d = "ریزشی" if lb["stair_dir"] == "down" else "صعودی"
    bits = [f"نردبان {d} · پلهٔ {lb['stair_steps']}"]
    rel = {"inside": "داخل اردر بلاک بالاسری",
           "under_edge": "چسبیده به زیرِ اردر بلاک بالاسری",
           "far": "دور از اردر بلاک بالاسری",
           "none": "اردر بلاک بالاسری ندارد"}.get(lb.get("stair_ob"))
    if rel:
        bits.append(rel)
    if lb.get("stair_depth") is not None:
        bits.append(f"عمق پولبک {lb['stair_depth']:.2f}")
    if lb.get("stair_broken"):
        bits.append("⚠ نردبان شکسته (برگشت محتمل)")
    return " · ".join(bits)


# ── ۵. داوری روی دفترهای موجود ────────────────────────────────────────────

def _boot(a, b, n=3000, alpha=0.05):
    """بازهٔ اختلافِ میانگین‌ها با بوت‌استرپ. None = نمونهٔ کم."""
    import random
    if len(a) < 8 or len(b) < 8:
        return None
    d = []
    for _ in range(n):
        sa = [random.choice(a) for _ in a]
        sb = [random.choice(b) for _ in b]
        d.append(sum(sa) / len(sa) - sum(sb) / len(sb))
    d.sort()
    return d[int(n * alpha / 2)], d[int(n * (1 - alpha / 2))]


def _verdict(lo, hi, n_small):
    if lo is None:
        return "UNDECIDED"
    if lo > 0 and n_small >= PROMOTE_MIN_N:
        return "PROMOTE_CANDIDATE"
    if hi < 0 and n_small >= REJECT_MIN_N:
        return "REJECT"
    return "UNDECIDED"


def _need(a, b, half=0.10):
    """چند نمونه در هر بازو تا نیم‌پهنای CI به `half` برسد."""
    xs = list(a) + list(b)
    if len(xs) < 4:
        return None
    sd = statistics.stdev(xs)
    return int(round(2 * (1.96 * sd / half) ** 2))


TESTS = (
    ("H1 پلهٔ ≥۲ در برابر پلهٔ ۱",
     lambda w: (w.get("stair_steps") or 0) >= 2,
     lambda w: (w.get("stair_steps") or 0) == 1),
    ("H2 پلهٔ ≥۳ در برابر پلهٔ ۱",
     lambda w: (w.get("stair_steps") or 0) >= 3,
     lambda w: (w.get("stair_steps") or 0) == 1),
    ("H3 زیرِ لبهٔ OB در برابر داخلِ OB",
     lambda w: w.get("stair_ob") == "under_edge",
     lambda w: w.get("stair_ob") == "inside"),
    ("H4 پولبک عمیق (≥۰.۵) در برابر کم‌عمق",
     lambda w: (w.get("stair_depth") is not None and w["stair_depth"] >= 0.5),
     lambda w: (w.get("stair_depth") is not None and w["stair_depth"] < 0.5)),
    ("H5 نردبان نشکسته در برابر شکسته",
     lambda w: w.get("stair_broken") is False,
     lambda w: w.get("stair_broken") is True),
    ("H6 نردبان هم‌جهت در برابر خلاف‌جهت",
     lambda w: w.get("stair_align") == "with",
     lambda w: w.get("stair_align") == "against"),
)


def judge(rows, verbose=True):
    """داوریِ شش فرضیهٔ از پیش ثبت‌شده روی ردیف‌هایی که برچسب دارند."""
    tagged = [r for r in rows if (r.get("why") or {}).get("stair_dir") is not None]
    out = {"n_rows": len(rows), "n_tagged": len(tagged),
           "alpha_sidak": round(ALPHA_SIDAK, 5), "tests": []}
    if verbose:
        print(f"ردیفِ یکتا: {len(rows)} · با برچسبِ نردبان: {len(tagged)}")
        print(f"آستانهٔ Šidák برای {HYPOTHESES} فرضیه: "
              f"α={ALPHA_SIDAK:.5f}\n")
    for name, fa_, fb in TESTS:
        a = [r["R_net"] for r in tagged if fa_(r.get("why") or {})]
        b = [r["R_net"] for r in tagged if fb(r.get("why") or {})]
        rec = {"test": name, "n_a": len(a), "n_b": len(b)}
        if len(a) < 8 or len(b) < 8:
            rec["verdict"] = "UNDECIDED"
            rec["why"] = "نمونهٔ کم"
            rec["need_per_arm"] = _need(a, b)
            if verbose:
                print(f"  {name:<38} n={len(a)}/{len(b)} — نمونهٔ کم")
            out["tests"].append(rec)
            continue
        ea, eb = statistics.fmean(a), statistics.fmean(b)
        ci = _boot(a, b, alpha=ALPHA_SIDAK)
        n_small = min(len(a), len(b))
        rec.update({"ev_a": round(ea, 4), "ev_b": round(eb, 4),
                    "diff": round(ea - eb, 4),
                    "ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
                    "verdict": _verdict(ci[0] if ci else None,
                                        ci[1] if ci else None, n_small),
                    "need_per_arm": _need(a, b)})
        out["tests"].append(rec)
        if verbose:
            c = f"[{ci[0]:+.4f}, {ci[1]:+.4f}]" if ci else "—"
            print(f"  {name:<38} n={len(a):<5}/{len(b):<5} "
                  f"{ea - eb:+.4f}  {c}  {rec['verdict']}")
    return out


def main(argv=()):
    if "--selftest" in argv:
        return _selftest()
    if "--judge" in argv:
        from hamid.direction_autopsy import load
        rows = []
        for pre in ("practice", "sig-", "vetoed", "first", "second"):
            rows += load(pre)
        r = judge(rows)
        if not r["n_tagged"]:
            print("\nهیچ ردیفی هنوز برچسبِ نردبان ندارد — برچسب از امروز "
                  "روی معامله‌های تازه نوشته می‌شود. عددی گزارش نمی‌شود؛\n"
                  "ادعای زودرس از نگفتن بدتر است.")
        return 0
    print(__doc__)
    return 0


# ── خودآزمایی ─────────────────────────────────────────────────────────────

def _c(t, o, h, l, c, v=100.0):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


def _ladder(steps=3, start=100.0, leg=4.0, back=1.5, bars=6, t0=0):
    """نردبانِ ریزشیِ ساختگی: هر پله یک ریزش و یک پولبکِ کوتاه‌تر."""
    cd, px, t = [], start, t0
    for _ in range(20):                                   # گرم‌کردن
        cd.append(_c(t, px, px + 0.1, px - 0.1, px)); t += 900_000
    # ⚠️ سقف/کفِ **دقیقاً برابر** ممنوع: فرکتالِ `microstructure.pivots`
    # با `<` سخت کار می‌کند، پس دو کندلِ هم‌سقف هر دو را حذف می‌کند و
    # سریِ ساختگی «بی‌پیوت» درمی‌آید. (همین یک بار اتفاق افتاد و سری
    # صفر پیوت داد — عیبِ سازندهٔ تست بود، نه عیبِ موتور.)
    for _ in range(steps):
        for k in range(bars):                             # ریزش
            nxt = px - leg / bars
            cd.append(_c(t, px, px, nxt - 0.05, nxt)); t += 900_000
            px = nxt
        for k in range(bars):                             # پولبک کوتاه‌تر
            nxt = px + back / bars
            cd.append(_c(t, px, nxt + 0.05, px, nxt)); t += 900_000
            px = nxt
    for _ in range(3):                                    # دنبالهٔ آرام
        cd.append(_c(t, px, px + 0.05, px - 0.05, px)); t += 900_000
    return cd


def _selftest():
    ok = fails = 0

    def chk(cond, msg):
        nonlocal ok, fails
        if cond:
            ok += 1
        else:
            fails += 1
            print(f"  ✗ {msg}")

    # ۱) نردبانِ ریزشی شناخته می‌شود و جهتش درست است
    cd = _ladder(steps=3)
    st = staircase(cd)
    chk(st["dir"] == "down", f"نردبان ریزشی تشخیص داده نشد: {st}")
    chk(st["steps"] >= 2, f"پله کم شمرده شد: {st['steps']}")
    chk(st["broken"] is False, "نردبانِ سالم «شکسته» خوانده شد")

    # ۲) قرینه: نردبانِ صعودی
    up = [_c(c["t"], -c["o"] + 200, -c["l"] + 200, -c["h"] + 200,
             -c["c"] + 200, c["v"]) for c in cd]
    chk(staircase(up)["dir"] == "up", "نردبانِ صعودی تشخیص داده نشد")

    # ۳) بازارِ رنج پله نمی‌سازد
    flat = [_c(i * 900_000, 100, 100.4, 99.6, 100 + (0.2 if i % 2 else -0.2))
            for i in range(120)]
    chk(staircase(flat)["steps"] == 0, "بازار رنج پله ساخت")

    # ۴) **خلوصِ تابع**: یک پنجره، همیشه یک جواب — حتی اگر بین دو
    #    فراخوانی پنجرهٔ دیگری (با آینده‌ای کاملاً متفاوت) دیده شده باشد.
    #    این حالتِ کش/حالتِ ماژولی را می‌گیرد؛ کلاسِ عیبی که یک تابعِ
    #    ظاهراً خالص را به آینده وصل می‌کند.
    #
    #    ⚠️ نکتهٔ صادقانه: چون این تابع فقط همان پنجره‌ای را می‌بیند که
    #    به آن داده‌اند، «نگاه به آینده» این‌جا **قابل رخ‌دادن نیست** —
    #    قرارداد بر عهدهٔ فراخوان است. اثباتِ ضدآیندهٔ واقعی در آزمونِ
    #    سیم‌کشی است (`test_stairs.py`، جاسوسِ پنجرهٔ فراخوان)، نه این‌جا.
    #    آزمونی که این را ادعا کند و در واقع دو برشِ یکسان را مقایسه کند،
    #    آزمونِ توخالی است.
    base = _ladder(steps=3)
    i = len(base) - 12
    a = staircase(base[:i + 1])
    staircase(base[:i + 1] + [_c(base[i]["t"] + (k + 1) * 900_000,
                                 500, 900, 400, 800) for k in range(12)])
    chk(staircase(base[:i + 1]) == a, "تابع بین دو فراخوانی حالت نگه داشت")

    # ۵) زنجیره از موتورِ ساختارِ نسخه‌دار می‌آید، نه از تعریفِ تازه
    import hamid.microstructure as _ms
    chk(_ms.STRUCT_VERSION.startswith("e07-micro"),
        "موتور ساختار عوض شده — تعریفِ پله باید بازبینی شود")
    src = (HERE / "stairs.py").read_text(encoding="utf-8")
    chk("from hamid.microstructure import structure" in src,
        "زنجیرهٔ ساختار قرض گرفته نشده — خطرِ تعریفِ ششم")

    # ۶) پیوتِ تأییدنشده وارد شمارش نمی‌شود: رویدادِ آخر نمی‌تواند روی
    #    سطحی باشد که هنوز `confirmed_at_i` نگرفته (قراردادِ خودِ موتور).
    win = base[-BARS:] if len(base) > BARS else base
    full = _ms.structure(win)
    if full and full.get("events"):
        hi, lo = _ms.pivots(win)
        levels = {round(p["px"], 8) for p in hi + lo
                  if p["confirmed_at_i"] <= full["events"][-1]["i"] - 1}
        chk(round(full["events"][-1]["level"], 8) in levels,
            "رویدادِ ساختاری روی سطحِ تأییدنشده ثبت شد")

    # ۷) نویز پله نمی‌سازد: دامنهٔ ریز، زیرِ کفِ لگِ ATR موتور
    tiny = _ladder(steps=3, leg=0.02, back=0.01)
    chk(staircase(tiny)["steps"] <= 1,
        "حرکتِ زیرِ کفِ لگ به‌عنوان نردبانِ چندپله شمرده شد")

    # ۸) برگشت دیده می‌شود: صعودِ قاطع بعد از نردبانِ ریزشی
    brk = list(base)
    top = max(c["h"] for c in base[-40:])
    px = base[-1]["c"]
    for k in range(6):
        nxt = px + (top * 1.06 - px) / 6
        brk.append(_c(base[-1]["t"] + (k + 1) * 900_000, px,
                      nxt + 0.05, px - 0.05, nxt))
        px = nxt
    rb = staircase(brk)
    chk(rb["dir"] == "up" or rb["broken"] is True,
        f"برگشتِ روند دیده نشد: {rb}")

    # ۹) برچسب: کلیدها همیشه هستند، «نمی‌دانم» None است نه جعل
    lb = label(base, direction="SHORT")
    for k in ("stair_dir", "stair_steps", "stair_broken", "stair_depth",
              "stair_ob", "stair_lag"):
        chk(k in lb, f"کلید {k} در برچسب نیست")
    chk(lb.get("stair_align") == "with",
        f"هم‌جهتی شورت با نردبانِ ریزشی غلط: {lb.get('stair_align')}")
    chk(label(flat, direction="SHORT").get("stair_align") is None,
        "بی‌نردبان، هم‌جهتی جعل شد")

    # ۱۰) عمق پولبک بین ۰ و ۱ می‌ماند وقتی قیمت داخل لگ است
    d = lb.get("stair_depth")
    chk(d is None or -0.5 <= d <= 1.5, f"عمق پولبکِ بی‌معنا: {d}")

    # ۱۱) پنجرهٔ کوتاه = «نمی‌دانم»، نه حدس
    chk(staircase(base[:10])["dir"] is None, "پنجرهٔ کوتاه جواب ساخت")

    # ۱۲) fa بدون عددِ تازه و بدون ترکیدن
    chk("نردبان" in fa(lb), "خط فارسی ساخته نشد")
    chk("تشخیص داده نشد" in fa({}), "برچسبِ خالی پیام درست نداد")

    # ۱۳) داور: بدون برچسب، هیچ حکمی صادر نمی‌شود
    j = judge([{"R_net": 0.1, "why": {}} for _ in range(50)], verbose=False)
    chk(j["n_tagged"] == 0, "ردیفِ بی‌برچسب شمرده شد")
    chk(all(t["verdict"] == "UNDECIDED" for t in j["tests"]),
        "بدون نمونه حکم صادر شد")

    # ۱۴) داور: بازوی کوچک زیرِ کف، PROMOTE نمی‌دهد (اثبات منفی)
    rows = ([{"R_net": 1.0, "why": {"stair_dir": "down", "stair_steps": 3}}
             for _ in range(30)]
            + [{"R_net": -1.0, "why": {"stair_dir": "down", "stair_steps": 1}}
               for _ in range(30)])
    j2 = judge(rows, verbose=False)
    h1 = next(t for t in j2["tests"] if t["test"].startswith("H1"))
    chk(h1["diff"] > 0, "اختلافِ آشکار دیده نشد")
    chk(h1["verdict"] == "UNDECIDED",
        f"با n={h1['n_a']} حکمِ زودرس داد: {h1['verdict']}")

    # ۱۵) آستانهٔ Šidák درست حساب شده
    chk(abs(ALPHA_SIDAK - (1 - 0.95 ** (1 / 6))) < 1e-12, "Šidák غلط")
    chk(ALPHA_SIDAK < 0.05, "تصحیح چندآزمونی آستانه را شل کرد")

    print(f"stairs: {ok} بررسی سبز" + (f" · {fails} قرمز" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
