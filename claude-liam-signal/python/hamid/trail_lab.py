"""آزمایشگاه تریل — چرا با ۶۶٪ برد ضرر می‌دهیم، و کدام نردبان بهتر است.

## یافتهٔ ۱ سپتامبر که این فایل را لازم کرد

روی ۲۵۶ معاملهٔ بستهٔ سیگنال:

| نتیجه | n | خالص |
|---|---|---|
| تارگت | ۳۰ | **+۱.۳۵۵R** |
| تریل | ۱۳۴ | **+۰.۰۶۶R** — و ۸۴٪ آن‌ها دقیقاً صفر |
| استاپ | ۸۱ | −۱.۲۶۵R |

و عددی که همه‌چیز را توضیح می‌دهد: معامله‌های تریل‌شده به‌طور میانه
**MFE ‎+۰.۸۵۰R** دیدند و **‎+۰.۰۰۰R** برداشتند.

این باگ نیست — قاعدهٔ ۱۲ اوت دقیقاً همین را می‌گوید: در ⅓ مسیر تا
تارگت، استاپ می‌رود روی «ورود + کارمزد». مسئله درست‌بودنِ قاعده نیست؛
**زودبودنش** است: در ⅓ مسلح می‌شود در حالی که قیمت معمولاً تا ۰.۸۵R
می‌رود.

## دو روش بازپخش — و چرا فقط یکی حق رأی دارد

**۱. دونقطه‌ای (`points`) — مردود برای رتبه‌بندی.** هر معامله `mfe`،
`mae` و شمارهٔ کندلِ هرکدام را دارد. وسوسه‌انگیز است که مسیر را با همین
دو نقطه بسازیم. اولین اجرا (۱ سپتامبر) همین کار را کرد و جواب داد
«نگه‌داشت ۸۰٪ قله بهترین است، ‎+۰.۳۶R». **آن عدد آشغال است** و ترتیبش
اثرِ خودِ روش بود نه واقعیت:

بین ورود و قله ده‌ها کندل هست. تریلِ نسبتیِ تنگ در همان مسیرِ بالا
رفتن، با هر پولبکِ میانیِ بیش از (۱−frac) می‌خورد و معامله همان‌جا
بسته می‌شود. بازپخشِ دونقطه‌ای این پولبک‌ها را **نمی‌بیند**، پس فرض
می‌کند تریل تا خودِ قله زنده مانده. یعنی: **هرچه تریل تنگ‌تر، خطای
روش به نفعش بیشتر.** ترتیبِ ۸۰٪ > ۶۵٪ > ۵۰٪ دقیقاً همان چیزی است که
این خطا پیش‌بینی می‌کند — پس شاهدِ درستیِ قاعده نیست، شاهدِ خرابیِ
اندازه‌گیری است. اندازهٔ خطا در `bias_demo()` عددی اثبات می‌شود.

**۲. کندل‌به‌کندل (`bars`) — مرجع.** همان حلقهٔ `paper._settle_one` روی
کندل‌های واقعی ۱۵د، با همان قیدهای محافظه‌کارانه: تریل از اکسترمم
کندل‌های *قبلی* (بدون خوش‌بینی درون-کندلی) و برخوردِ هم‌زمان استاپ و
تارگت → استاپ. تنها چیزی که عوض می‌شود، تابعِ سطحِ تریل است. حکم فقط
از این حالت خوانده می‌شود.

شبکهٔ این نشست به صرافی‌ها راه ندارد (پراکسی ۴۰۳)، پس حالت `bars` روی
رانرِ Actions اجرا می‌شود — همان‌جا که طبق CLAUDE.md همهٔ محاسبهٔ سنگین
می‌نشیند.

## مرز صادقانه

خروجی این فایل **فرضیه** است نه قاعده، حتی در حالت `bars`: بازپخش روی
همان معامله‌هایی است که با قاعدهٔ فعلی انتخاب شده‌اند (سوگیریِ انتخاب)،
و کندل ۱۵د حرکتِ داخلِ کندل را نمی‌بیند. ورودش به تولید فقط از مسیر
قانون ۰۳: A/B زنده در پیپر با دفتر جدا، و CI بالای صفر.

اجرا: `python3 -m hamid.trail_lab [--bars] [--json] [--write]`
"""
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
ROOT = PY.parent.parent
OUT = ROOT / "signals" / "trail-lab.json"

TF = "15m"                      # همان تایمی که دفتر با آن mfe/mae را ساخت
MAX_BARS = 1000                 # سقف واقعیِ اکثر صرافی‌ها


def ci95(xs):
    n = len(xs)
    if n < 2:
        return None, None, None, n
    m = statistics.mean(xs)
    sd = statistics.stdev(xs)
    if sd == 0:
        return round(m, 4), round(m, 4), round(m, 4), n
    se = sd / math.sqrt(n)
    return round(m, 4), round(m - 1.96 * se, 4), round(m + 1.96 * se, 4), n


def verdict(lo, hi):
    if lo is None:
        return "بی‌نمونه"
    return "بالای صفر" if lo > 0 else "زیر صفر" if hi < 0 else "شامل صفر"


# ── قاعده‌های تریل ───────────────────────────────────────────────────────
#
# هر قاعده: (best_r, rr, fee_r) → سطحِ استاپ بر حسب R (نسبت به ورود)، یا
# None یعنی «هنوز مسلح نشو، استاپِ اولیه سرِ جایش».
#   best_r — بهترین سودِ دیده‌شده تا **کندلِ قبل**، بر حسب R
#   rr     — فاصلهٔ تارگتِ همین معامله بر حسب R
#   fee_r  — کارمزد رفت‌وبرگشت بر حسب R (سربه‌سرِ واقعی)

def rule_current(best_r, rr, fee_r):
    """قاعدهٔ ۱۲ اوت (تولید): ⅓ مسیر → سربه‌سرِ کارمزددار؛ ⅔ → همان ⅓."""
    prog = best_r / rr if rr else 0.0
    if prog >= 2 / 3:
        return rr / 3
    if prog >= 1 / 3:
        return fee_r
    return None


def rule_late(best_r, rr, fee_r):
    """مسلح‌شدن دیرتر: هیچ‌کاری تا ⅔، بعد سربه‌سر؛ روی تارگت → ⅔."""
    prog = best_r / rr if rr else 0.0
    if prog >= 1.0:
        return rr * 2 / 3
    if prog >= 2 / 3:
        return fee_r
    return None


def rule_giveback(frac, arm=None):
    """تریلِ نسبتی: `frac` از قلهٔ دیده‌شده را نگه دار.

    تنها خانواده‌ای که با **اندازهٔ حرکت** مقیاس می‌شود؛ نردبانِ پله‌ای در
    حرکتِ بزرگ همان‌قدر می‌گیرد که در کوچک. `arm` کفِ مسلح‌شدن است: زیر
    آن اصلاً تریل نمی‌گذاریم، وگرنه در نوسانِ اولِ معامله ضرر قفل می‌شود.
    """
    def f(best_r, rr, fee_r):
        floor = fee_r if arm is None else max(arm, fee_r)
        if best_r < floor:
            return None
        lvl = best_r * frac
        return lvl if lvl >= fee_r else None
    return f


def rule_none(best_r, rr, fee_r):
    """بی‌تریل — فقط استاپ و تارگت. پایهٔ مقایسه."""
    return None


BASE = "فعلی (⅓ سربه‌سر)"
RULES = {
    BASE: rule_current,
    "دیرمسلح (⅔)": rule_late,
    "نگه‌داشت ۵۰٪ قله": rule_giveback(0.50),
    "نگه‌داشت ۶۵٪ قله": rule_giveback(0.65),
    "نگه‌داشت ۸۰٪ قله": rule_giveback(0.80),
    "۵۰٪ قله، مسلح از ۱R": rule_giveback(0.50, arm=1.0),
    "۶۵٪ قله، مسلح از ۱R": rule_giveback(0.65, arm=1.0),
    "بی‌تریل": rule_none,
}


def geometry(r):
    """(risk قیمتی, rr بر حسب R, long?) — از هندسهٔ خودِ معامله."""
    risk = abs(r["entry"] - r["sl"])
    if not risk:
        return None
    rr = abs(r["tp1"] - r["entry"]) / risk
    return risk, (rr if rr > 0 else 1.5), (r.get("dir") == "LONG")


# ── ۱) بازپخشِ کندل‌به‌کندل — مرجع ───────────────────────────────────────

def replay_bars(r, rule, candles):
    """آینهٔ دقیقِ `paper._settle_one` با سطحِ تریلِ قابل‌تعویض.

    خروجی: (R ناخالص, برچسب) یا None اگر کندلی نبود.
    """
    g = geometry(r)
    if not g or not candles:
        return None
    risk, rr, long = g
    entry, fee_r = r["entry"], r.get("_fee_r") or 0.0
    sgn = 1 if long else -1
    tp = r["tp1"]
    sl_eff = r["sl"]
    best_r = 0.0                       # فقط از کندل‌های **قبلی**
    for c in candles:
        lvl = rule(best_r, rr, fee_r)
        if lvl is not None:
            px = entry + sgn * lvl * risk
            sl_eff = max(sl_eff, px) if long else min(sl_eff, px)
        hit_sl = (c["l"] <= sl_eff) if long else (c["h"] >= sl_eff)
        hit_tp = (c["h"] >= tp) if long else (c["l"] <= tp)
        trailed = (sl_eff > r["sl"]) if long else (sl_eff < r["sl"])
        if hit_sl:                     # هم‌زمانی → محافظه‌کار: استاپ اول
            R = sgn * (sl_eff - entry) / risk if trailed else -1.0
            return round(R, 4), ("تریل" if trailed else "استاپ")
        if hit_tp:
            return round(rr, 4), "تارگت"
        fav = ((c["h"] - entry) if long else (entry - c["l"])) / risk
        best_r = max(best_r, fav)
    return round(sgn * (candles[-1]["c"] - entry) / risk, 4), "باز-ماند"


# ── ۲) بازپخشِ دونقطه‌ای — فقط برای نشان‌دادنِ خطای خودش ──────────────────

def replay_points(r, rule):
    """کرانِ خوش‌بینانه. برای رتبه‌بندی **استفاده نمی‌شود** — بالا بخوان."""
    w = r.get("why") or {}
    mfe, mae = w.get("mfe"), w.get("mae")
    fb, ab = w.get("mfe_bar"), w.get("mae_bar")
    g = geometry(r)
    if None in (mfe, mae, fb, ab) or not g:
        return None
    _, rr, _ = g
    fee_r = r.get("_fee_r") or 0.0
    if ab < fb and mae <= -1.0:
        return -1.0, "استاپ (قبل از هر سودی)"
    if mfe >= rr:
        return round(rr, 4), "تارگت"
    # نامسلح یعنی استاپِ اولیه (‎−۱R)، نه «حتماً ضرر». اگر افت به آن نرسید،
    # معامله همان‌جا که واقعاً بست می‌بندد. (اولین نسخه این را اشتباه
    # می‌گرفت و پایهٔ «بی‌تریل» را مصنوعی خراب می‌کرد.)
    lvl = rule(mfe, rr, fee_r)
    eff = -1.0 if lvl is None else max(lvl, -1.0)
    if mae <= eff:
        return round(eff, 4), ("تریل" if eff > -1.0 else "استاپ")
    return round(r.get("R") or 0.0, 4), "همان‌طور که بود"


def bias_demo():
    """اثباتِ عددیِ این‌که بازپخشِ دونقطه‌ای تریلِ تنگ را بالا می‌برد.

    یک معاملهٔ ساختگی: لانگ، ریسک ۱ واحد، تارگت ۳R. قیمت تا ‎+۲R می‌رود،
    **وسط راه از ‎+۱.۵R به ‎+۰.۶R برمی‌گردد** (پولبکِ ۶۰٪)، بعد قله را
    می‌سازد و برمی‌گردد.

    - کندل‌به‌کندل: «نگه‌داشت ۸۰٪ قله» در همان پولبکِ میانی خورده — چون
      وقتی قله ۱.۵ بود، استاپ روی ۱.۲ نشست و قیمت رفت ۰.۶.
    - دونقطه‌ای: پولبکِ میانی را نمی‌بیند؛ فرض می‌کند تا ۲R زنده مانده و
      ۱.۶R برداشته.

    اختلاف = خطای روش، نه اختلافِ قاعده.
    """
    r = {"sym": "TEST", "dir": "LONG", "entry": 100.0, "sl": 99.0,
         "tp1": 103.0, "_fee_r": 0.05, "R": 0.0,
         "why": {"mfe": 2.0, "mae": -0.4, "mfe_bar": 4, "mae_bar": 6}}
    # h/l هر کندل بر حسب R: ۰→۱.۵ ، برگشت به ۰.۶ ، ۰.۶→۲.۰ ، برگشت
    path = [(1.5, 0.0), (0.9, 0.6), (2.0, 0.8), (2.0, -0.4)]
    candles = [{"t": i, "o": 100.0, "c": 100.0 + lo,
                "h": 100.0 + hi, "l": 100.0 + lo}
               for i, (hi, lo) in enumerate(path)]
    tight = RULES["نگه‌داشت ۸۰٪ قله"]
    b = replay_bars(r, tight, candles)
    p = replay_points(r, tight)
    return {"bars": b, "points": p,
            "gap": round((p[0] - b[0]), 4) if b and p else None}


# ── مطالعه ───────────────────────────────────────────────────────────────

def _candles(r):
    import sources
    since = r.get("filled") or r.get("opened")
    if not since:
        return []
    n = min(MAX_BARS, max(200, int((time.time() * 1000 - since) / 900_000) + 20))
    try:
        rows = sources.klines(r["sym"], TF, n)
    except Exception:                                # noqa: BLE001
        return []
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4]}
            for k in rows if k[0] >= since]


def study(mode="bars", rows=None, bars_by_key=None):
    from hamid.direction_autopsy import load
    if rows is None:
        rows = [r for r in load("sig-")
                if (r.get("why") or {}).get("mfe") is not None
                and (r.get("why") or {}).get("mae") is not None
                and r.get("_fee_r") is not None and geometry(r)]

    if mode == "bars":
        if bars_by_key is None:
            bars_by_key = {}
            for r in rows:
                cd = _candles(r)
                if cd:
                    bars_by_key[id(r)] = cd
        usable = [r for r in rows if bars_by_key.get(id(r))]

        def run(r, rule):
            return replay_bars(r, rule, bars_by_key[id(r)])
    else:
        usable = rows

        def run(r, rule):
            return replay_points(r, rule)

    out, per_rule = {}, {}
    for name, rule in RULES.items():
        nets, tags = [], {}
        got_by = {}
        for r in usable:
            got = run(r, rule)
            if not got:
                continue
            gross, tag = got
            got_by[id(r)] = gross
            nets.append(round(gross - (r.get("_fee_r") or 0.0), 4))
            tags[tag] = tags.get(tag, 0) + 1
        per_rule[name] = got_by
        m, lo, hi, n = ci95(nets)
        out[name] = {
            "mean_net": m, "ci": [lo, hi], "n": n, "verdict": verdict(lo, hi),
            "how": tags,
            "zero_pct": (round(100 * sum(1 for x in nets if abs(x) < 0.05)
                               / len(nets), 1) if nets else None)}

    pairs = {}
    for name in RULES:
        if name == BASE:
            continue
        d = [round(per_rule[name][k] - per_rule[BASE][k], 4)
             for k in per_rule[name] if k in per_rule[BASE]]
        m, lo, hi, n = ci95(d)
        pairs[name] = {"diff_vs_current": m, "ci": [lo, hi], "n": n,
                       "verdict": verdict(lo, hi)}

    boundary = (
        "بازپخش روی همان معامله‌هایی است که قاعدهٔ فعلی انتخابشان کرده "
        "(سوگیریِ انتخاب)، و کندل ۱۵د حرکتِ داخلِ کندل را نمی‌بیند. "
        "خروجی فرضیه است نه قاعده — ورود به تولید فقط با A/B زندهٔ پیپر و "
        "CI بالای صفر (قانون ۰۳).")
    if mode != "bars":
        boundary = ("⚠️ حالت دونقطه‌ای: تریلِ تنگ‌تر را سیستماتیک بالا "
                    "می‌برد چون پولبکِ میانی را نمی‌بیند. برای رتبه‌بندی "
                    "معتبر نیست — فقط `--bars` حق رأی دارد. " + boundary)
    return {"mode": mode, "generated": int(time.time() * 1000),
            "n_rows": len(usable), "n_candidates": len(rows),
            "rules": out, "vs_current": pairs,
            "bias_demo": bias_demo(), "boundary": boundary}


def render(s):
    L = [f"### آزمایشگاه تریل — حالت «{s['mode']}»، "
         f"{s['n_rows']} از {s['n_candidates']} معامله\n"]
    L.append(f"{'قاعده':<24} {'خالص':>9}  {'CI':>22}  {'صفرشده':>8}  حکم")
    for name, v in s["rules"].items():
        ci = (f"[{v['ci'][0]:+.3f}, {v['ci'][1]:+.3f}]"
              if v["ci"][0] is not None else "—")
        mn = f"{v['mean_net']:+9.4f}" if v["mean_net"] is not None else "    —    "
        z = (str(v["zero_pct"]) + "٪") if v["zero_pct"] is not None else "—"
        L.append(f"{name:<24} {mn}  {ci:>22}  {z:>8}  {v['verdict']}")
    L.append("\n### اختلاف با قاعدهٔ فعلی (جفتی، روی همان معامله‌ها)")
    for name, v in s["vs_current"].items():
        ci = (f"[{v['ci'][0]:+.3f}, {v['ci'][1]:+.3f}]"
              if v["ci"][0] is not None else "—")
        df = (f"{v['diff_vs_current']:+8.4f}R"
              if v["diff_vs_current"] is not None else "     —   ")
        L.append(f"  {name:<24} {df}  {ci:>22}  n={v['n']}  {v['verdict']}")
    b = s["bias_demo"]
    L.append("\n### اثباتِ خطای روشِ دونقطه‌ای (معاملهٔ ساختگی، تریل ۸۰٪)")
    L.append(f"  کندل‌به‌کندل: {b['bars']}   دونقطه‌ای: {b['points']}   "
             f"خطا: {b['gap']:+}R" if b["gap"] is not None else "  —")
    L.append(f"\n### مرز صادقانه\n  {s['boundary']}")
    return "\n".join(L)


def main(argv=()):
    mode = "bars" if "--bars" in argv else "points"
    s = study(mode)
    print(json.dumps(s, ensure_ascii=False, indent=1) if "--json" in argv
          else render(s))
    if "--write" in argv:
        OUT.write_text(json.dumps(s, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"\n  نوشته شد: {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
