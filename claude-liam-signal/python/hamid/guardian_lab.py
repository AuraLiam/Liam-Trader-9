#!/usr/bin/env python3
"""آزمایشگاه مراقبان — ۱۲ استراتژی، سه تایم‌فریم، بدون خبر از فردا.

دستور حمید (۳ سپتامبر): «حالا پیپرمود وارد مرحلهٔ جدیدی می‌شود؛ ۱۲
متخصص ۱۲ استراتژی جدید اضافه می‌کنند و هر کدام ستاپ پیشنهادی خودش را
می‌دهد، و پیپر تریدینگ روی ۱س و ۱۵د و ۵د روی همان ارزها **جداگانه**
اجرا می‌شود… برای جمع‌آوری دادهٔ تاریخی بیشتر، ۲ تا ۳ سال عقب برویم و
**بدون اطلاع از یک روز جلوتر** طبق استراتژی خودم ترید کنیم. برای هر
ترید، ۱۲ ایجنت نتیجه را پیش‌بینی کنند: درست +۱، غلط −۱… و در آخر
بررسی شود ۱س چه نتیجه‌ای داد، ۱۵د چه، و کدام متخصص‌ها امتیاز بیشتری
گرفتند.»

## چهار قاعده‌ای که این آزمایشگاه را از یک بک‌تستِ معمولی جدا می‌کند

**۱. هیچ تابعی کندلِ بعد از `i` را نمی‌بیند.** ورودی هر استراتژی
`cd[:i+1]` است — برشِ واقعی، نه شاخصِ نگاه‌نکردنی. پس نشتِ آینده
غیرممکن است نه «بعید»؛ و آزمون با اثبات منفی همین را قفل می‌کند.

**۲. سه تایم‌فریم، سه دفترِ جدا.** حمید گفت «جداگانه». اختلاطشان یعنی
نتیجهٔ ۵د پشتِ نتیجهٔ ۱س پنهان شود، در حالی که سؤال دقیقاً همین است که
کدام تایم بهتر جواب می‌دهد.

**۳. پیش‌بینی جدا از پیشنهاد است.** هر مراقب روی **هر** معامله رأی
می‌دهد — چه خودش پیشنهادش داده باشد چه نه. ممتنع مجاز است و صفر امتیاز
می‌گیرد؛ «چیزی نمی‌گویم» جوابِ معتبر است و نباید با حدسِ تصادفی جایگزین
شود.

**۴. دلیلِ استاپ و دلیلِ تارگت ثبت می‌شود** (بند H7.6): هر معامله با
`exit_reason` بسته می‌شود — تارگت، استاپ، سقفِ نگهداری، یا پایانِ داده.

## مرز

خروجی این آزمایشگاه **دفتر آزمایش** است، جدا از دفتر پیپر تولید. هیچ
استراتژی‌ای از این‌جا وارد سیگنال واقعی نمی‌شود مگر از مسیر قانون ۰۳:
CI بالای صفر روی دادهٔ خارج-از-نمونه و تأیید صریح حمید.

    python3 -m hamid.guardian_lab --demo
"""
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import phoenix as PHX                     # noqa: E402

ROOT = HERE.parents[2]
BRAIN = ROOT / "brain" / "guardian-lab"
TRADES = BRAIN / "trades.jsonl"                      # append-only
OUT = ROOT / "signals" / "guardian-lab.json"

ENGINE = "E18"
PANEL = "لیام تریدر ۹"

TFS = ("1h", "15m", "5m")                            # دستور حمید — جداگانه
WARMUP = 60                  # کندل لازم پیش از اولین تصمیم
MAX_HOLD = {"1h": 24, "15m": 32, "5m": 48}           # سقف نگهداری، به کندل
RR = 2.0                     # تارگت = این‌قدر برابرِ استاپ
STOP_ATR = 1.5               # استاپ = این‌قدر ATR
FEE_ROUND_TRIP_PCT = 0.15    # کارمزد دو سر + لغزش (راستی‌آزمایی‌شدهٔ ۱۶ اوت)
MIN_TRADES_VERDICT = 100     # زیر این، حکمِ تایم‌فریم اعلام نمی‌شود


# ── کمکی‌های قطعی (فقط از گذشته) ────────────────────────────────────────
def _atr(cd, n=14):
    if len(cd) < 2:
        return 0.0
    tr = [max(cd[i]["h"] - cd[i]["l"], abs(cd[i]["h"] - cd[i - 1]["c"]),
              abs(cd[i]["l"] - cd[i - 1]["c"])) for i in range(1, len(cd))]
    tr = tr[-n:]
    return sum(tr) / len(tr) if tr else 0.0


def _ema(vals, n):
    if not vals:
        return None
    k = 2.0 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def _ibs(c):
    rng = c["h"] - c["l"]
    return (c["c"] - c["l"]) / rng if rng > 0 else 0.5


def _swings(cd, left=2, right=2):
    hi, lo = [], []
    for i in range(left, len(cd) - right):
        w = cd[i - left:i + right + 1]
        if cd[i]["h"] >= max(x["h"] for x in w):
            hi.append(i)
        if cd[i]["l"] <= min(x["l"] for x in w):
            lo.append(i)
    return hi, lo


# ── دوازده استراتژی، هر کدام از میدانِ تخصص خودِ همان مراقب ─────────────
# قرارداد: `f(cd)` که `cd` برشِ **بسته‌شدهٔ** تا همین لحظه است. خروجی
# "long" / "short" / None. هیچ‌کدام حق دیدن کندل بعدی را ندارد.

def _s_taurus(cd, ctx=None):
    """ثور — روند تایم بالا: EMA۲۱ بالای EMA۵۵ و پولبک به EMA۲۱."""
    cl = [c["c"] for c in cd]
    e21, e55 = _ema(cl[-80:], 21), _ema(cl[-120:], 55)
    if e21 is None or e55 is None:
        return None
    last = cd[-1]
    if e21 > e55 and last["l"] <= e21 <= last["c"]:
        return "long"
    if e21 < e55 and last["h"] >= e21 >= last["c"]:
        return "short"
    return None


def _s_aries(cd, ctx=None):
    """حمل — ایمپالس، BOS، و **پولبک دوم** (روش حمید، نه پولبک اول)."""
    hi, lo = _swings(cd)
    if len(hi) < 2 or len(lo) < 2:
        return None
    a = _atr(cd)
    if a <= 0:
        return None
    last = cd[-1]
    # شکست سقف قبلی (BOS)، بعد دو بار برگشت به همان ناحیه
    top = cd[hi[-2]]["h"]
    bot = cd[lo[-2]]["l"]
    broke_up = any(c["c"] > top for c in cd[hi[-2] + 1:])
    broke_dn = any(c["c"] < bot for c in cd[lo[-2] + 1:])
    if broke_up:
        backs = sum(1 for c in cd[hi[-2] + 1:] if c["l"] <= top + 0.2 * a)
        if backs >= 2 and last["l"] <= top + 0.5 * a <= last["c"]:
            return "long"
    if broke_dn:
        backs = sum(1 for c in cd[lo[-2] + 1:] if c["h"] >= bot - 0.2 * a)
        if backs >= 2 and last["h"] >= bot - 0.5 * a >= last["c"]:
            return "short"
    return None


def _s_leo(cd, ctx=None):
    """اسد — اردر بلاک به تعریف حمید: اولین کندلِ قویِ مخالف پیش از حرکت."""
    a = _atr(cd)
    if a <= 0 or len(cd) < 30:
        return None
    last = cd[-1]
    for j in range(len(cd) - 25, len(cd) - 3):
        c = cd[j]
        body = abs(c["c"] - c["o"])
        wick = (c["h"] - max(c["o"], c["c"])) + (min(c["o"], c["c"]) - c["l"])
        if body <= wick or body < 0.8 * a:
            continue
        moved = cd[j + 1]["c"] - c["c"]
        if c["c"] > c["o"] and moved > a and last["l"] <= c["h"] and last["c"] >= c["l"]:
            return "long"
        if c["c"] < c["o"] and moved < -a and last["h"] >= c["l"] and last["c"] <= c["h"]:
            return "short"
    return None


def _s_cancer(cd, ctx=None):
    """سرطان — سوییپ نقدینگی: ویک زیر کف اخیر، بستنِ بالای آن."""
    a = _atr(cd)
    if a <= 0 or len(cd) < 25:
        return None
    prev = cd[-21:-1]
    lo = min(c["l"] for c in prev)
    hi = max(c["h"] for c in prev)
    last = cd[-1]
    if last["l"] < lo - 0.1 * a and last["c"] > lo:
        return "long"
    if last["h"] > hi + 0.1 * a and last["c"] < hi:
        return "short"
    return None


def _s_pisces(cd, ctx=None):
    """حوت — هندسهٔ کندل: IBS در انتهای دامنه + بدنهٔ بزرگ‌تر از میانه."""
    if len(cd) < 25:
        return None
    last = cd[-1]
    bodies = [abs(c["c"] - c["o"]) for c in cd[-21:-1]]
    med = statistics.median(bodies) if bodies else 0
    if abs(last["c"] - last["o"]) < med * 1.2:
        return None
    v = _ibs(last)
    if v <= 0.25:
        return "long"
    if v >= 0.75:
        return "short"
    return None


def _s_libra(cd, ctx=None):
    """میزان — فقط جایی که هندسه کارمزد را می‌خرد: استاپ به‌قدر کافی گشاد."""
    a = _atr(cd)
    last = cd[-1]
    if a <= 0 or last["c"] <= 0:
        return None
    stop_pct = STOP_ATR * a / last["c"] * 100
    if stop_pct < FEE_ROUND_TRIP_PCT / 0.15:         # کارمزد ≤ ۰.۱۵R
        return None
    return _s_taurus(cd, ctx)                        # جهت از روند، دروازه از هندسه


def _s_virgo(cd, ctx=None):
    """سنبله — کیفیت داده: شکاف یا کندلِ مرده = معامله نکن."""
    if len(cd) < 25:
        return None
    for i in range(len(cd) - 20, len(cd)):
        if cd[i]["h"] <= cd[i]["l"]:
            return None
        gap = abs(cd[i]["o"] - cd[i - 1]["c"]) / max(cd[i - 1]["c"], 1e-12)
        if gap > 0.03:
            return None
    return _s_pisces(cd, ctx)


def _s_capricorn(cd, ctx=None):
    """جدی — حافظه: همان جهتی که در ۵۰ کندل اخیر بازده مثبت داده."""
    if len(cd) < 60:
        return None
    d = _s_taurus(cd, ctx)
    if d is None:
        return None
    rets = [cd[i]["c"] / cd[i - 1]["c"] - 1 for i in range(len(cd) - 50, len(cd))]
    drift = sum(rets)
    if d == "long" and drift <= 0:
        return None
    if d == "short" and drift >= 0:
        return None
    return d


def _s_scorpio(cd, ctx=None):
    """عقرب — دامیننس: بی‌سری دامیننس، رأی نمی‌دهد (قانون ۱)."""
    dom = (ctx or {}).get("dominance")
    if not dom or len(dom) < 3:
        return None
    d = _s_taurus(cd, ctx)
    if d is None:
        return None
    rising = dom[-1] > dom[-3]
    if d == "long" and rising:                       # USDT.D صعودی = بازار نزولی
        return None
    if d == "short" and not rising:
        return None
    return d


def _s_gemini(cd, ctx=None):
    """جوزا — بستر بیت‌کوین: بی‌سری BTC، رأی نمی‌دهد."""
    btc = (ctx or {}).get("btc")
    if not btc or len(btc) < 5:
        return None
    d = _s_taurus(cd, ctx)
    if d is None:
        return None
    up = btc[-1] > btc[-5]
    return d if ((d == "long") == up) else None


def _s_sagittarius(cd, ctx=None):
    """قوس — خبر: در بک‌تست تاریخی خبرِ هم‌ترازِ زمان نداریم، پس ممتنع."""
    return None


def _s_aquarius(cd, ctx=None):
    """دلو — جمعیت: فاندینگ/ترند تاریخی هم‌تراز نداریم، پس ممتنع."""
    return None


STRATEGIES = {"taurus": _s_taurus, "aries": _s_aries, "leo": _s_leo,
              "cancer": _s_cancer, "pisces": _s_pisces, "libra": _s_libra,
              "virgo": _s_virgo, "capricorn": _s_capricorn,
              "scorpio": _s_scorpio, "gemini": _s_gemini,
              "sagittarius": _s_sagittarius, "aquarius": _s_aquarius}

# دو مراقبِ عمداً ساکت — نبودِ دادهٔ هم‌ترازِ زمان، نه نبودِ تخصص.
SILENT = {"sagittarius": "خبرِ هم‌ترازِ زمانِ گذشته در دفتر نیست — عدد جعل نمی‌شود",
          "aquarius": "فاندینگ/ترند تاریخیِ هم‌تراز نداریم — ممتنع"}


# ── پیش‌بینی: هر مراقب روی هر معامله ────────────────────────────────────
def predict(gid, cd, direction, ctx=None):
    """رأی این مراقب دربارهٔ نتیجهٔ همین معامله: +۱ / −۱ / ممتنع.

    قاعده‌اش ساده و قطعی است: اگر استراتژی خودش همین جهت را می‌دید،
    می‌گوید «می‌رسد»؛ اگر جهت مخالف را می‌دید، می‌گوید «نمی‌رسد»؛ اگر
    چیزی نمی‌دید، **ممتنع** — و ممتنع صفر امتیاز می‌گیرد، نه حدسِ سکه.
    """
    f = STRATEGIES.get(gid)
    if f is None:
        return None
    try:
        own = f(cd, ctx)
    except Exception:                                # noqa: BLE001
        return None
    if own is None:
        return None
    return 1 if own == direction else -1


# ── شبیه‌سازی یک معامله، فقط با کندل‌های بعدی ──────────────────────────
def simulate(cd, i, direction, tf, rr=RR, stop_atr=STOP_ATR,
             fee_pct=FEE_ROUND_TRIP_PCT):
    """ورود روی بستِ کندل i؛ خروج با اولین برخورد. دلیل خروج ثبت می‌شود."""
    a = _atr(cd[:i + 1])
    entry = cd[i]["c"]
    if a <= 0 or entry <= 0:
        return None
    risk = stop_atr * a
    if direction == "long":
        sl, tp = entry - risk, entry + rr * risk
    else:
        sl, tp = entry + risk, entry - rr * risk
    hold = MAX_HOLD.get(tf, 24)
    fee_r = (fee_pct / 100.0) * entry / risk
    for j in range(i + 1, min(len(cd), i + 1 + hold)):
        c = cd[j]
        hit_sl = (c["l"] <= sl) if direction == "long" else (c["h"] >= sl)
        hit_tp = (c["h"] >= tp) if direction == "long" else (c["l"] <= tp)
        if hit_sl and hit_tp:
            # هر دو در یک کندل: بدبینانه استاپ. خوش‌بینیِ درون‌کندلی
            # همان چیزی است که بک‌تست را دروغ‌گو می‌کند.
            return {"R": -1.0, "R_net": round(-1.0 - fee_r, 4), "bars": j - i,
                    "exit_reason": "استاپ (هر دو در یک کندل — فرضِ بدبینانه)",
                    "entry": entry, "sl": sl, "tp": tp, "fee_r": round(fee_r, 4)}
        if hit_sl:
            return {"R": -1.0, "R_net": round(-1.0 - fee_r, 4), "bars": j - i,
                    "exit_reason": "استاپ — قیمت به نقطهٔ ابطال رسید",
                    "entry": entry, "sl": sl, "tp": tp, "fee_r": round(fee_r, 4)}
        if hit_tp:
            return {"R": float(rr), "R_net": round(rr - fee_r, 4), "bars": j - i,
                    "exit_reason": f"تارگت — {rr}R پیش از استاپ خورد",
                    "entry": entry, "sl": sl, "tp": tp, "fee_r": round(fee_r, 4)}
    j = min(len(cd) - 1, i + hold)
    if j <= i:
        return None
    out = cd[j]["c"]
    r = ((out - entry) if direction == "long" else (entry - out)) / risk
    ended = j >= len(cd) - 1 and j < i + hold
    return {"R": round(r, 4), "R_net": round(r - fee_r, 4), "bars": j - i,
            "exit_reason": ("پایان داده — معامله باز بود" if ended
                            else f"سقف نگهداری ({hold} کندل) — نه تارگت، نه استاپ"),
            "entry": entry, "sl": sl, "tp": tp, "fee_r": round(fee_r, 4)}


# ── اجرای رو-به-جلو روی یک تایم‌فریم ────────────────────────────────────
def run_tf(sym, tf, cd, ctx=None, warmup=WARMUP, step=1, now_ms=None):
    """هر کندل، هر مراقب پیشنهاد می‌دهد؛ همه پیش‌بینی می‌کنند.

    برشِ `cd[:i+1]` تنها چیزی است که به استراتژی می‌رسد — پس نشتِ آینده
    ساختاراً ناممکن است، نه «مراقبیم که نشود».
    """
    ctx = ctx or {}
    trades = []
    for i in range(warmup, len(cd) - 2, step):
        past = cd[:i + 1]
        sub = {"dominance": (ctx.get("dominance") or [])[:i + 1] or None,
               "btc": (ctx.get("btc") or [])[:i + 1] or None}
        for gid, f in STRATEGIES.items():
            try:
                d = f(past, sub)
            except Exception:                        # noqa: BLE001
                d = None
            if d not in ("long", "short"):
                continue
            res = simulate(cd, i, d, tf)
            if res is None:
                continue
            votes = {}
            for other in STRATEGIES:
                v = predict(other, past, d, sub)
                if v is not None:
                    votes[other] = v
            trades.append({"sym": sym, "tf": tf, "i": i, "t": cd[i]["t"],
                           "by": gid, "dir": d, **res, "votes": votes})
    return trades


# ── نمره‌دهی: به تفکیک تایم‌فریم و به تفکیک متخصص ──────────────────────
def score(trades):
    """درست +۱، غلط −۱ (دستور حمید). ممتنع اصلاً در دفتر نیست."""
    by_tf, by_g, by_g_tf = {}, {}, {}
    for t in trades:
        good = t["R_net"] > 0
        tf = t["tf"]
        s = by_tf.setdefault(tf, {"n": 0, "wins": 0, "sum_R": 0.0, "sum_net": 0.0,
                                  "by_reason": {}})
        s["n"] += 1
        s["wins"] += 1 if good else 0
        s["sum_R"] += t["R"]
        s["sum_net"] += t["R_net"]
        rk = (t.get("exit_reason") or "?").split("—")[0].strip()
        s["by_reason"][rk] = s["by_reason"].get(rk, 0) + 1
        # پیشنهاددهنده
        p = by_g.setdefault(t["by"], {"proposed": 0, "points": 0, "votes": 0,
                                      "sum_net": 0.0})
        p["proposed"] += 1
        p["sum_net"] += t["R_net"]
        # پیش‌بینی‌کننده‌ها
        for gid, v in (t.get("votes") or {}).items():
            g = by_g.setdefault(gid, {"proposed": 0, "points": 0, "votes": 0,
                                      "sum_net": 0.0})
            g["votes"] += 1
            g["points"] += 1 if (v > 0) == good else -1
            gt = by_g_tf.setdefault(gid, {}).setdefault(tf, {"votes": 0, "points": 0})
            gt["votes"] += 1
            gt["points"] += 1 if (v > 0) == good else -1
    for s in by_tf.values():
        s["win_pct"] = round(100 * s["wins"] / s["n"], 1) if s["n"] else None
        s["mean_R"] = round(s["sum_R"] / s["n"], 4) if s["n"] else None
        s["mean_net"] = round(s["sum_net"] / s["n"], 4) if s["n"] else None
        s["ci95_net"] = _ci([t for t in trades], None) if False else None
    for tf, s in by_tf.items():
        xs = [t["R_net"] for t in trades if t["tf"] == tf]
        s["ci95_net"] = _ci(xs)
        s["verdict"] = _verdict(s["n"], s["ci95_net"])
    for gid, g in by_g.items():
        g["accuracy"] = (round(100 * (g["points"] + g["votes"]) / (2 * g["votes"]), 1)
                         if g["votes"] else None)
        g["mean_net"] = round(g["sum_net"] / g["proposed"], 4) if g["proposed"] else None
        g["silent_why"] = SILENT.get(gid)
    return {"by_tf": by_tf, "by_guardian": by_g, "by_guardian_tf": by_g_tf,
            "trades": len(trades)}


def _ci(xs, _=None):
    n = len(xs)
    if n < 2:
        return None
    m = statistics.mean(xs)
    sd = statistics.stdev(xs)
    h = 1.96 * sd / math.sqrt(n)
    return [round(m - h, 4), round(m + h, 4)]


def _verdict(n, ci):
    if n < MIN_TRADES_VERDICT:
        return f"UNDECIDED — n={n} کمتر از {MIN_TRADES_VERDICT}، حکم اعلام نمی‌شود"
    if ci and ci[0] > 0:
        return "لبهٔ خالص بالای صفر — نامزد قانون ۰۳ (نه ورود خودکار)"
    if ci and ci[1] < 0:
        return "لبهٔ خالص زیر صفر — این هندسه اجرا نشود"
    return "CI شامل صفر — از نویز جدا نشده"


def snapshot(res, syms=None, span=None, now_ms=None):
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    return {"generated": now, "engine": ENGINE, "panel": PANEL,
            "symbols": list(syms or []), "span": span,
            "timeframes": list(TFS),
            "trades": res["trades"], "by_tf": res["by_tf"],
            "by_guardian": res["by_guardian"],
            "by_guardian_tf": res["by_guardian_tf"],
            "rules": {"rr": RR, "stop_atr": STOP_ATR, "max_hold": MAX_HOLD,
                      "fee_round_trip_pct": FEE_ROUND_TRIP_PCT,
                      "min_trades_verdict": MIN_TRADES_VERDICT},
            "boundary": "دفتر آزمایش است، جدا از پیپر تولید. هیچ استراتژی‌ای از "
                        "این‌جا وارد سیگنال واقعی نمی‌شود مگر با CI بالای صفر روی "
                        "دادهٔ خارج-از-نمونه و تأیید صریح حمید (قانون ۰۳)."}


def append_trades(trades, path=None):
    p = Path(path or TRADES)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for t in trades:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    return len(trades)


# ── نمایش ────────────────────────────────────────────────────────────────
def _demo_series(n=900, seed=11):
    """سری قطعیِ روندی-نوسانی — فقط برای نمایش و آزمون، نه ادعای عملکرد."""
    cd, p, s = [], 100.0, seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        u = s / 2147483648.0 - 0.5
        p *= 1 + 0.0016 * math.sin(i / 41.0) + 0.004 * u
        o = p
        c = p * (1 + 0.002 * u)
        cd.append({"t": 1_700_000_000_000 + i * 900_000, "o": o,
                   "h": max(o, c) * 1.0025, "l": min(o, c) * 0.9975, "c": c,
                   "v": 100.0 + 10 * abs(u)})
    return cd


def resample(cd, k):
    """k کندل را به یک کندل تبدیل می‌کند — ۵د → ۱۵د (k=3) و → ۱س (k=12).

    بدون این، «سه تایم‌فریم جداگانه» روی یک سریِ یکسان اجرا می‌شد و هر
    سه عددِ یکسان می‌دادند؛ یعنی دقیقاً همان سؤالی که حمید پرسید
    («۱س چه داد، ۱۵د چه داد») بی‌جواب می‌ماند.
    """
    out = []
    for i in range(0, len(cd) - k + 1, k):
        w = cd[i:i + k]
        out.append({"t": w[0]["t"], "o": w[0]["o"],
                    "h": max(x["h"] for x in w), "l": min(x["l"] for x in w),
                    "c": w[-1]["c"], "v": sum(x.get("v") or 0 for x in w)})
    return out


def run_real(syms, years=2.0, step=1, quiet=False):
    """اجرای واقعی روی کندل بازار — «۲ تا ۳ سال عقب» (بند H7.3).

    هر تایم‌فریم سریِ خودش را از منبع می‌گیرد (نه بازنمونه‌گیریِ ۵د)، چون
    عمقِ تاریخیِ در دسترس برای هر تایم فرق می‌کند و بازنمونه‌گیری از سریِ
    کوتاه، «۲ سال ۱ساعته» نمی‌سازد.
    """
    import sources
    need = {"1h": int(years * 365 * 24), "15m": int(years * 365 * 96),
            "5m": int(years * 365 * 288)}
    trades, got = [], {}
    for sym in syms:
        for tf in TFS:
            try:
                cd = sources.klines(sym, tf, need[tf], quiet=quiet)
            except Exception as e:                   # noqa: BLE001
                print(f"  {sym} {tf}: کندل نیامد ({type(e).__name__}) — کنار گذاشته شد",
                      flush=True)
                continue
            if not cd or len(cd) < WARMUP + 50:
                print(f"  {sym} {tf}: فقط {len(cd or [])} کندل — کم است", flush=True)
                continue
            got.setdefault(tf, []).append(len(cd))
            trades += run_tf(sym, tf, cd, step=step)
    span = {tf: {"series": len(v), "bars_median": int(statistics.median(v))}
            for tf, v in got.items()}
    return trades, span


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--real" in argv:
        syms = [a for a in argv if a.endswith("USDT")] or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        yrs = 2.0
        for a in argv:
            if a.startswith("--years="):
                yrs = float(a.split("=", 1)[1])
        trades, span = run_real(syms, yrs, step=1)
        res = score(trades)
        snap = snapshot(res, syms, {"years": yrs, **span})
        append_trades(trades)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"آزمایشگاه (واقعی) — {res['trades']} معامله روی {len(syms)} نماد، {yrs} سال")
        for tf, s in res["by_tf"].items():
            print(f"  {tf}: n={s['n']} · برد {s['win_pct']}٪ · خالص {s['mean_net']}R "
                  f"· CI {s['ci95_net']} · {s['verdict']}")
        return 0
    base = _demo_series(n=3600)
    series = {"5m": base, "15m": resample(base, 3), "1h": resample(base, 12)}
    trades = []
    for tf in TFS:
        trades += run_tf("DEMOUSDT", tf, series[tf], step=3)
    res = score(trades)
    snap = snapshot(res, ["DEMOUSDT"], "سری نمایشی")
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"تابلوی آزمایشگاه نوشته شد: {OUT.relative_to(ROOT)}")
    print(f"آزمایشگاه مراقبان — {res['trades']} معاملهٔ آزمایشی")
    for tf, s in res["by_tf"].items():
        print(f"  {tf}: n={s['n']} · برد {s['win_pct']}٪ · خالص {s['mean_net']}R "
              f"· CI {s['ci95_net']} · {s['verdict']}")
    top = sorted(res["by_guardian"].items(), key=lambda x: -(x[1]["points"] or 0))
    for gid, g in top[:6]:
        name = PHX.BY_ID[gid]["name"]
        print(f"  {name}: {g['points']:+d} امتیاز از {g['votes']} رأی "
              f"(دقت {g['accuracy']}٪) · {g['proposed']} پیشنهاد")
    for gid, why in SILENT.items():
        print(f"  {PHX.BY_ID[gid]['name']}: ممتنع — {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
