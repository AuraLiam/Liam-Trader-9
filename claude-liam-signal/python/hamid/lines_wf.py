#!/usr/bin/env python3
"""خط‌کشی رو-به-جلو — از یک هفته قبل، بدون دیدن آینده (دستور حمید، ۳ سپتامبر).

حمید: «خط روند را با در نظر گرفتن شدو از یک هفته قبل در چارت همان ارز
بدون دیدن آینده شروع کند… و کم‌کم چارت را رو به جلو می‌بریم و خطوطی که
برای خط روند و حمایت و مقاومت بود را ادامه می‌دهیم و هر کدام که معتبر بود
و در آینده به عنوان سقف یا کف یا حمایت و یا مقاومت عمل کرده را نگه
می‌داریم و اضافی‌هایی که منطقی نیستند را پاک می‌کنیم.»

و صریح: «حتماً نیاز نیست که در آخر ما یک کانال موازی داشته باشیم… اگر
اصرار داشته باشیم که باید کانال شکل بگیرد شاید متوجه الگوهایی مثل مثلث
متقارن، مثلث صعودی، مثلث نزولی و… نشویم.»

## سه قاعده‌ای که این فایل را از «خط‌کشی معمولی» جدا می‌کند

**۱. لنگر، و بعد فقط رو به جلو.** نامزدهای خط **فقط** از کندل‌های تا لحظهٔ
لنگر (پیش‌فرض: یک هفته قبل) ساخته می‌شوند. کندل‌های بعدِ لنگر هرگز در
*ساختن* خط دخالت نمی‌کنند؛ فقط *نمره* می‌دهند. این تفاوت، تفاوتِ یک
خط‌کشی صادق با یک خط‌کشیِ از-آینده-خبردار است — و در `test_lines_wf`
با اثبات منفی قفل شده: آیندهٔ عوض‌شده نباید نامزدها را تکان بدهد.

**۲. شدو حساب می‌شود، ولی جدا از بدنه.** برخوردِ ویک و پذیرشِ بدنه دو
ستون جدا می‌مانند (قانون ۰۰ و سند خطوط). خطی که فقط ویک خورده با خطی که
بدنه پشتش بسته شده یکی نیست.

**۳. هندسه تحمیل نمی‌شود.** بعد از پالایش، اگر دو خطِ بازمانده به کانال
موازی خوردند «کانال» گفته می‌شود؛ اگر همگرا بودند مثلث/گُوه؛ اگر واگرا
بودند broadening؛ و اگر هیچ‌کدام، صریح `none` — نه کانالِ زورکی.

## مرز صادقانه

این ماژول **می‌کشد و نمره می‌دهد**؛ دروازهٔ معامله نیست. ورود هر قاعدهٔ
خطی به تصمیم فقط از مسیر قانون ۰۳ (بک‌تست بی‌آینده → CI بالای صفر →
تأیید حمید). مراجع روش: `.claude/rules/trendlines-canon.md`.
"""
import sys
from statistics import median

TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
         "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}

# آستانه‌ها — همه از سند مرجع، نه سلیقه.
PIVOT_L = 3               # کندل‌های چپ/راست برای تأیید سوینگ
TOUCH_ATR = 0.35          # نزدیکیِ ویک تا خط که «برخورد» شمرده شود
REACT_ATR = 0.80          # حرکت لازم بعد از برخورد که «واکنش» شمرده شود
REACT_BARS = 6            # پنجرهٔ واکنش
BREAK_PCT = 0.003         # فیلتر نفوذ Murphy (۰.۳٪) — یا دو کلوز پیاپی
MIN_TOUCH = 3             # قاعدهٔ حمید + Edwards & Magee: حداقل سه برخورد
MIN_REACT = 2             # از آن سه، دست‌کم دو تا واکنش واقعی داده باشد
RESPECT_MIN = 0.75        # سهمِ عمرِ خط که قیمت سمتِ درستش بوده (پایین را ببین)
ANCHOR_DAYS = 7.0         # «از یک هفته قبل»


# ── کمکی ──────────────────────────────────────────────────────────────────
def atr(cd, n=14):
    if len(cd) < 2:
        return 0.0
    tr = []
    for i in range(1, len(cd)):
        p = cd[i - 1]["c"]
        tr.append(max(cd[i]["h"] - cd[i]["l"], abs(cd[i]["h"] - p), abs(cd[i]["l"] - p)))
    tr = tr[-n:]
    return sum(tr) / len(tr) if tr else 0.0


def pivots(cd, left=PIVOT_L, right=PIVOT_L):
    """سوینگ‌های تأییدشده روی **شدو**. هر پیوت فقط `right` کندل بعد از خودش
    شناخته می‌شود — همان تأخیری که در واقعیت هم هست، نه دیدِ آینده."""
    hi, lo = [], []
    for i in range(left, len(cd) - right):
        w = cd[i - left:i + right + 1]
        if cd[i]["h"] >= max(x["h"] for x in w) and cd[i]["h"] > cd[i - 1]["h"]:
            hi.append({"i": i, "t": cd[i]["t"], "p": cd[i]["h"], "kind": "high"})
        if cd[i]["l"] <= min(x["l"] for x in w) and cd[i]["l"] < cd[i - 1]["l"]:
            lo.append({"i": i, "t": cd[i]["t"], "p": cd[i]["l"], "kind": "low"})
    return hi, lo


def anchor_index(cd, days=ANCHOR_DAYS, tf=None):
    """اندیس «یک هفته قبل». اگر داده کمتر بود، نصفِ آنچه هست — با اعلام."""
    if not cd:
        return 0
    if tf and tf in TF_MS:
        want = int(days * 86_400_000 / TF_MS[tf])
    else:
        step = (cd[-1]["t"] - cd[0]["t"]) / max(1, len(cd) - 1)
        want = int(days * 86_400_000 / step) if step > 0 else len(cd) // 2
    i0 = len(cd) - want
    return max(PIVOT_L * 2 + 2, min(i0, len(cd) - 2)) if i0 > 0 else max(len(cd) // 2, PIVOT_L * 2 + 2)


def _line_at(line, i):
    return line["p0"] + line["slope"] * (i - line["i0"])


# ── ساخت نامزدها (فقط از گذشتهٔ لنگر) ────────────────────────────────────
def candidates(cd_past, a=None):
    """نامزدهای خط روند و سطح افقی — فقط از کندل‌های تا لنگر.

    خط روند: هر جفت پیوتِ هم‌نوع، به شرط این‌که خط از قیمتِ بین آن دو
    نگذرد (تعریف الگوریتمیِ Sperandeo). سطح افقی: خوشهٔ پیوت‌های هم‌قیمت.
    """
    a = a if a is not None else atr(cd_past)
    hi, lo = pivots(cd_past)
    out = []
    for pts, kind in ((hi, "res"), (lo, "sup")):
        for x in range(len(pts)):
            for y in range(x + 1, len(pts)):
                p1, p2 = pts[x], pts[y]
                if p2["i"] - p1["i"] < PIVOT_L:
                    continue
                slope = (p2["p"] - p1["p"]) / (p2["i"] - p1["i"])
                line = {"kind": kind, "type": "trend", "i0": p1["i"], "t0": p1["t"],
                        "p0": p1["p"], "slope": slope, "anchors": [p1["i"], p2["i"]]}
                # خط نباید از قیمتِ بین دو لنگر رد شود (Sperandeo)
                bad = False
                for j in range(p1["i"] + 1, p2["i"]):
                    lp = _line_at(line, j)
                    if kind == "res" and cd_past[j]["h"] > lp + 0.15 * a:
                        bad = True
                        break
                    if kind == "sup" and cd_past[j]["l"] < lp - 0.15 * a:
                        bad = True
                        break
                if not bad:
                    out.append(line)
    # سطوح افقی: خوشه‌بندی قیمت پیوت‌ها
    tol = max(0.30 * a, 1e-12)
    for pts, kind in ((hi, "res"), (lo, "sup")):
        used = [False] * len(pts)
        for x in range(len(pts)):
            if used[x]:
                continue
            grp = [pts[x]]
            used[x] = True
            for y in range(x + 1, len(pts)):
                if not used[y] and abs(pts[y]["p"] - pts[x]["p"]) <= tol:
                    grp.append(pts[y])
                    used[y] = True
            if len(grp) >= 2:
                out.append({"kind": kind, "type": "level", "i0": grp[0]["i"],
                            "t0": grp[0]["t"], "p0": median(g["p"] for g in grp),
                            "slope": 0.0, "anchors": [g["i"] for g in grp]})
    return out


# ── نمره‌دهی رو به جلو ────────────────────────────────────────────────────
def score_forward(line, cd, i_from, a=None):
    """چارت را رو به جلو می‌برد و می‌گوید این خط واقعاً چه کرد.

    برخوردِ ویک، پذیرشِ بدنه، واکنش، و شکستِ قاطع — هر کدام جدا.
    """
    a = a if a is not None else atr(cd)
    tol, need = TOUCH_ATR * a, REACT_ATR * a
    st = {"wick_touches": 0, "body_accepts": 0, "reactions": 0, "breaks": 0,
          "state": "ACTIVE", "broke_at": None, "flipped": False,
          "bars": 0, "respect": 1.0}
    beyond = 0
    was_near = False                                 # برخورد = رویداد، نه کندل
    for i in range(i_from, len(cd)):
        lp = _line_at(line, i)
        if lp <= 0:
            continue
        c = cd[i]
        st["bars"] += 1
        near = (abs(c["l"] - lp) <= tol) if line["kind"] == "sup" else (abs(c["h"] - lp) <= tol)
        # قیمتی که ۵۰ کندل روی خط بنشیند یک برخورد است نه پنجاه‌تا؛
        # فقط لحظهٔ **رسیدن** شمرده می‌شود (کشف اجرای اول: ۱۵۳ «برخورد»
        # در ۱۵۰ کندل — عددی که فقط می‌گفت خط داخل نویز است).
        if near and not was_near:
            st["wick_touches"] += 1
            # واکنش: حرکت کافی در جهت انتظار، داخل پنجره
            w = cd[i + 1:i + 1 + REACT_BARS]
            if w:
                if line["kind"] == "sup" and max(x["h"] for x in w) - lp >= need:
                    st["reactions"] += 1
                elif line["kind"] == "res" and lp - min(x["l"] for x in w) >= need:
                    st["reactions"] += 1
        was_near = near
        # پذیرش بدنه آن‌سوی خط
        past = (c["c"] < lp * (1 - BREAK_PCT)) if line["kind"] == "sup" else (c["c"] > lp * (1 + BREAK_PCT))
        if past:
            beyond += 1
            st["body_accepts"] += 1
            if beyond >= 2 and st["state"] == "ACTIVE":
                st["state"] = "BROKEN"
                st["breaks"] += 1
                st["broke_at"] = c["t"]
        else:
            beyond = 0
            if st["state"] == "BROKEN" and st["wick_touches"] >= 1:
                # نقش عوض کرد و دوباره احترام گرفت (Role Flip — Murphy)
                st["state"] = "FLIPPED"
                st["flipped"] = True
    # احترام = سهمِ عمرِ خط که قیمت سمتِ *درستِ* آن بسته شده.
    # خطی که قیمت نصفِ عمرش را آن‌سویش زندگی کرده، سطح نیست؛ یک عددِ
    # وسطِ نوسان است که تصادفاً چند بار لمس شده (کشف: در کانالِ صعودی،
    # چهار «مقاومتِ افقی» با ۱۶–۲۰ برخورد بالا آمدند که قیمت ۶۱ تا ۱۱۲
    # کندل بالای‌شان بسته بود — و همان‌ها کانال را از هندسه بیرون کردند).
    if st["bars"]:
        st["respect"] = round(1.0 - st["body_accepts"] / st["bars"], 3)
    return st


def dedupe(lines, a, price_tol=0.5, slope_tol=0.02):
    """خطوطِ تقریباً یکسان یکی می‌شوند — چارتِ پر از خط یعنی هیچ خطی جدی نیست.

    انضباط Brandt: «چارت شلوغِ پر از خط یعنی هیچ خطی جدی نیست.» ده‌ها جفتِ
    پیوت تقریباً یک خط می‌سازند؛ آدم سه خط می‌کشد نه صد تا.
    """
    out = []
    for l in sorted(lines, key=lambda x: -(x["score"]["wick_touches"] * 2
                                           + x["score"]["reactions"])):
        dup = False
        for k in out:
            if k["kind"] != l["kind"]:
                continue
            if (abs(k["price_now"] - l["price_now"]) <= price_tol * a
                    and abs(k["slope"] - l["slope"]) <= slope_tol * max(a, 1e-9)):
                k.setdefault("merged", 0)
                k["merged"] += 1
                dup = True
                break
        if not dup:
            out.append(l)
    return out


def keep_or_drop(line, st):
    """قاعدهٔ نگه‌داشتن: حداقل سه برخورد و دو واکنش. وگرنه با دلیل پاک."""
    if st["wick_touches"] < MIN_TOUCH:
        return False, f"فقط {st['wick_touches']} برخورد — کمتر از {MIN_TOUCH} (قاعدهٔ حمید)"
    if st["reactions"] < MIN_REACT:
        return False, f"{st['wick_touches']} برخورد ولی {st['reactions']} واکنش — خطِ بی‌اثر"
    if st.get("respect", 1.0) < RESPECT_MIN:
        return False, (f"قیمت {round((1 - st['respect']) * 100)}٪ عمرِ خط را آن‌سویش بسته "
                       f"(احترام {st['respect']}) — خطِ تزئینی، نه سطح")
    return True, (f"{st['wick_touches']} برخورد · {st['reactions']} واکنش · "
                  f"احترام {st.get('respect', 1.0)} · وضعیت {st['state']}")


# ── هندسه: کانال اجباری نیست ─────────────────────────────────────────────
def geometry(lines, cd, a=None):
    """از خطوطِ بازمانده، هندسه را **کشف** می‌کند نه تحمیل.

    خروجی: نام الگو + دو خطِ سازنده + دلیل. اگر هیچ جفتی هندسه نساخت،
    صریح `none` — همان چیزی که حمید خواست.
    """
    a = a if a is not None else atr(cd)
    res = [l for l in lines if l["kind"] == "res"]
    sup = [l for l in lines if l["kind"] == "sup"]
    if not res or not sup:
        return {"shape": "none", "why": "برای هندسه هم خط مقاومت لازم است هم حمایت",
                "upper": None, "lower": None}
    n = len(cd) - 1
    best = None
    for u in res:
        for d in sup:
            top, bot = _line_at(u, n), _line_at(d, n)
            if top <= bot:
                continue
            # مقیاسِ مقایسه، **عرضِ خودِ الگو** است نه ATR: شیبِ «تخت» یعنی
            # خط در طول پنجره کمتر از یک‌پنجم عرض جابه‌جا شده. با مقیاس ATR
            # مثلث متقارن و کانال هر دو «تخت» خوانده می‌شدند (اجرای اول).
            i_s = max(u["i0"], d["i0"])
            span = max(1, n - i_s)
            w0 = _line_at(u, i_s) - _line_at(d, i_s)
            width_now = top - bot
            ref = max(w0, width_now, 1e-9)
            du, dd = u["slope"] * span, d["slope"] * span
            su, sd = du / ref, dd / ref
            flat_u, flat_d = abs(su) < 0.20, abs(sd) < 0.20
            conv = w0 > 0 and width_now < w0 * 0.75
            div = w0 > 0 and width_now > w0 * 1.35
            parallel = abs(su - sd) < 0.20 and not (flat_u and flat_d) and not conv and not div
            if flat_u and flat_d:
                shape, why = "range", "هر دو خط تخت — رنج افقی"
            elif parallel:
                shape = "channel_up" if su > 0 else "channel_down"
                why = "دو خط با شیب هم‌اندازه — کانال موازی"
            elif flat_u and sd > 0.20:
                shape, why = "ascending_triangle", "سقف تخت، کف بالارونده — مثلث صعودی"
            elif flat_d and su < -0.20:
                shape, why = "descending_triangle", "کف تخت، سقف پایین‌رونده — مثلث نزولی"
            elif conv and su < 0 and sd > 0:
                shape, why = "symmetric_triangle", "سقف پایین‌رونده و کف بالارونده — مثلث متقارن"
            elif conv and su > 0 and sd > 0:
                shape, why = "rising_wedge", "هر دو بالارونده و همگرا — گُوهٔ صعودی"
            elif conv and su < 0 and sd < 0:
                shape, why = "falling_wedge", "هر دو پایین‌رونده و همگرا — گُوهٔ نزولی"
            elif div:
                shape, why = "broadening", "واگرا — الگوی پهن‌شونده"
            else:
                continue
            strength = (u.get("score", {}).get("wick_touches", 0)
                        + d.get("score", {}).get("wick_touches", 0))
            if best is None or strength > best["strength"]:
                best = {"shape": shape, "why": why, "upper": u, "lower": d,
                        "strength": strength, "top": top, "bottom": bot,
                        "mid": (top + bot) / 2}
    if not best:
        return {"shape": "none", "upper": None, "lower": None,
                "why": "خطوط بازمانده هندسهٔ شناخته‌شده‌ای نساختند — کانال تحمیل نمی‌شود"}
    return best


# ── اجرای کامل ────────────────────────────────────────────────────────────
def build(cd, tf=None, days=ANCHOR_DAYS):
    """نقشهٔ کاملِ یک تایم‌فریم: نامزد از گذشته، نمره از آینده، هندسه از بازمانده."""
    if len(cd) < 40:
        return {"ok": False, "why": f"کندل کم است ({len(cd)}) — خط‌کشی معنا ندارد",
                "kept": [], "dropped": [], "geometry": {"shape": "none"}}
    i0 = anchor_index(cd, days, tf)
    a = atr(cd[:i0]) or atr(cd)
    cands = candidates(cd[:i0], a)
    kept, dropped = [], []
    for line in cands:
        st = score_forward(line, cd, i0, a)
        line["score"] = st
        ok, why = keep_or_drop(line, st)
        line["why"] = why
        # ۱۱۰.۰۰۰۰۰۰۰۰۱ روی گزارش، عددِ دقیق‌تری از ۱۱۰ نیست؛ فقط نویزِ
        # ممیز شناور است. ۱۰ رقم بامعنا برای ارزهای کم‌قیمت هم کافی است.
        line["price_now"] = float(f"{_line_at(line, len(cd) - 1):.10g}")
        # «هوریزنتال ری» (دستور حمید، بند سقف/کف‌های ۴س): خطی که در طول کلِ
        # پنجره کمتر از یک‌دهم ATR جابه‌جا می‌شود، افقی است — چه از خوشهٔ
        # سطح آمده باشد چه از جفتِ پیوتِ هم‌قیمت. برچسب اینجا زده می‌شود تا
        # گزارش و چارت بدانند این را ری بکشند نه خط مورب.
        line["ray"] = abs(line["slope"]) * max(1, len(cd) - line["i0"]) <= 0.10 * a
        (kept if ok else dropped).append(line)
    kept = dedupe(kept, a)
    geo = geometry(kept, cd, a)
    return {"ok": True, "tf": tf, "bars": len(cd), "anchor_i": i0,
            "anchor_t": cd[i0]["t"], "atr": round(a, 10),
            "candidates": len(cands), "kept_n": len(kept),
            "rays": [{"kind": l["kind"], "price": l["price_now"], "why": l["why"]}
                     for l in kept if l.get("ray")],
            "kept": kept[:12], "dropped_n": len(dropped),
            "dropped": [{"kind": d["kind"], "type": d["type"], "why": d["why"]}
                        for d in dropped[:8]],
            "geometry": {k: v for k, v in geo.items() if k not in ("upper", "lower")},
            "geometry_lines": {"upper": geo.get("upper"), "lower": geo.get("lower")},
            "rule": "نامزد فقط از قبلِ لنگر؛ آینده فقط نمره می‌دهد، خط نمی‌سازد"}


def synth(shape="ascending_triangle", n=300, seed=7):
    """سری مصنوعیِ قطعی که جوابش را از پیش می‌دانیم — فقط برای آزمون و نمایش.

    قیمت بین دو مرزِ تعریف‌شده بالا و پایین می‌رود، پس مرزها واقعاً همان
    خطوطی می‌شوند که موتور باید پیدا کند. بدون تصادفِ واقعی: هر اجرا یکی.
    """
    def bounds(i):
        f = i / max(1, n - 1)
        if shape == "ascending_triangle":
            return 90 + 18 * f, 110.0
        if shape == "descending_triangle":
            return 90.0, 110 - 18 * f
        if shape == "symmetric_triangle":
            return 90 + 9 * f, 110 - 9 * f
        if shape == "channel_up":
            return 90 + 20 * f, 110 + 20 * f
        if shape == "channel_down":
            return 90 - 20 * f, 110 - 20 * f
        if shape == "broadening":
            return 100 - 12 * f, 100 + 12 * f
        return 90.0, 110.0                           # range
    cd = []
    for i in range(n):
        lo_b, hi_b = bounds(i)
        mid, half = (lo_b + hi_b) / 2, (hi_b - lo_b) / 2
        # موج مثلثی با دورهٔ ۱۴ کندل: هر نیم‌دوره یک بار به مرز می‌رسد
        ph = (i % 14) / 14.0
        tri = 4 * ph - 1 if ph < 0.5 else 3 - 4 * ph
        c = mid + half * tri * 0.97
        o = mid + half * (4 * ((i - 1) % 14) / 14.0 - 1 if ((i - 1) % 14) / 14.0 < 0.5
                          else 3 - 4 * ((i - 1) % 14) / 14.0) * 0.97
        wick = half * 0.03 + (seed % 3) * 1e-9
        cd.append({"t": 1_700_000_000_000 + i * 900_000, "o": o,
                   "h": max(o, c) + wick, "l": min(o, c) - wick, "c": c, "v": 100.0})
    return cd


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    shape = next((a for a in argv if not a.startswith("-")), "ascending_triangle")
    r = build(synth(shape), "15m", days=2.0)
    print(f"[{shape}] ", end="")
    print(f"خط‌کشی رو-به-جلو: {r['candidates']} نامزد → {r['kept_n']} ماند، "
          f"{r['dropped_n']} پاک شد · هندسه: {r['geometry']['shape']}")
    for l in r["kept"][:6]:
        print(f"  {l['kind']:<4} {l['type']:<6} {l['why']}")
    for d in r["dropped"][:3]:
        print(f"  پاک: {d['kind']} {d['type']} — {d['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
