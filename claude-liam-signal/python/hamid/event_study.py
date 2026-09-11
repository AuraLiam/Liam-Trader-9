#!/usr/bin/env python3
"""واکنشِ بازار به رویداد و خبر — مطالعهٔ یک‌ساله (دستور حمید، ۱۱ سپتامبر شب).

حمید: «از استراتژی‌ها و اطلاعات و رویدادها به صورت کامل در یک سال اخیر
اطلاعات جمع کن و نتیجه‌گیری کن که در چه شرایطی مارکت نسبت به اتفاق‌ها و
اخبار و رویدادها چه واکنشی نشان داده. و همه را در حافظه بسپار و در
شرایط مشابه ازشون استفاده کن.»

═══════════════════════════════════════════════════════════════════════
  اول: چه داده‌ای واقعاً هست — چون بدون این، نتیجه ساختگی می‌شود
═══════════════════════════════════════════════════════════════════════

دفتر خبرِ داخلی (`brain/intel/history.jsonl`) فقط **۳۸ روز** را پوشش
می‌دهد، نه یک سال. پس «مطالعهٔ یک‌سالهٔ خبر» از رویِ آن دفتر ممکن نیست و
هر عددی که از آن دربیاید دروغ است.

آنچه **هست** و یک سال را واقعاً پوشش می‌دهد:

  · **تقویم اقتصادی** با بازهٔ تاریخی (TradingView) — رویدادِ زمان‌دار،
    با actual/forecast، یعنی می‌شود «غافلگیری» را هم اندازه گرفت.
  · **کندلِ واقعی** BTC/ETH با عمقِ یک سال از همان صرافی‌های چرخه.

پس این مطالعه روی همین دو می‌نشیند، و **شوکِ قیمتیِ مشتق‌شده از خودِ
کندل** را به‌عنوان خانوادهٔ دومِ رویداد اضافه می‌کند (روزهایی که بازار
خودش تکان خورده، بی‌آنکه لازم باشد خبرش را داشته باشیم).

═══════════════════════════════════════════════════════════════════════
  روش
═══════════════════════════════════════════════════════════════════════

برای هر رویداد: بازدهِ BTC و ETH در افق‌های ‎+۱س، +۴س، +۲۴س‎ نسبت به
کلوزِ ساعتِ قبل از رویداد، و رانشِ ‎−۴س‎ (قبلش چه شد).

هر اندازه‌گیری با **رژیم** برچسب می‌خورد، چون سؤال حمید دقیقاً همین است
(«در چه شرایطی»):

  · روندِ بستر: قیمت بالای/زیر میانگین ۲۰۰ کندلِ ۱ساعته
  · نوسان: ATR نسبی در صدکِ بالا/پایین/میانه
  · غافلگیری: actual در برابر forecast (بالاتر/پایین‌تر/بی‌داده)

و نتیجه فقط وقتی «قاعده» می‌شود که **بازهٔ اطمینان از صفر رد کند** —
همان قانون همیشگی. رویدادی با n<۸ عدد نمی‌گیرد، فقط شمرده می‌شود.

مرزِ صادقانه که از پیش نوشته شده:

۱. رویدادهای کلانِ تقویم روی **همهٔ** بازارها اثر دارند؛ این مطالعه
   می‌گوید BTC/ETH چه کردند، نه این‌که علت آن رویداد بوده. هم‌زمانی
   علیت نیست.
۲. تقویم گذشته‌نگر است: actual بعد از انتشار ثبت می‌شود. برای همین
   رانشِ قبل هم گزارش می‌شود — اگر حرکت *قبل* از رویداد شروع شده،
   یعنی بازار قیمت را از قبل خورده و ورود بعد از خبر دیر است.
۳. n کم = بی‌حکم، نه «اثری ندارد».

    python3 -m hamid.event_study --selftest
    python3 -m hamid.event_study --days 365
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "event-study.json"
MEM = ROOT / "brain" / "memory" / "event-reactions.json"

UA = {"User-Agent": "Mozilla/5.0 (compatible; liam9-event-study)"}
HORIZONS = (1, 4, 24)          # ساعت
PRE = 4                        # رانشِ قبل از رویداد
MIN_N = 8                      # زیر این، فقط شمارش — نه عدد

# دسته‌های رویداد. فهرست عمداً کوتاه: دستهٔ بلند همه‌چیز را «مهم» نشان
# می‌دهد و آن وقت هیچ‌چیز مهم نیست (همان اصلِ فهرستِ HOT در intel).
CLASSES = [
    ("نرخ بهرهٔ فد", ("fed interest rate", "fomc", "federal funds")),
    ("تورم CPI", ("cpi", "consumer price")),
    ("تورم تولیدکننده PPI", ("ppi", "producer price")),
    ("اشتغال NFP", ("nonfarm", "non-farm", "unemployment rate")),
    ("رشد GDP", ("gdp",)),
    ("خرده‌فروشی", ("retail sales",)),
]


def _json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _why(e):
    """چرا نیامد — کد و تکه‌ای از بدنه. «HTTPError» خالی تشخیص نیست."""
    code = getattr(e, "code", None)
    body = ""
    try:
        body = e.read()[:120].decode("utf8", "replace").replace("\n", " ")
    except Exception:                                    # noqa: BLE001
        pass
    return f"{type(e).__name__}" + (f" {code}" if code else "") + \
           (f" · {body}" if body else "")


# تقویم: چند شکلِ درخواست، به ترتیب. اولی که جواب داد قفل می‌شود تا بقیهٔ
# تکه‌ها همان را بزنند. دلیلِ چندشکلی: میزبانِ تقویم گاهی بدون Origin رد
# می‌کند و شکستِ آن، کلِ مطالعه را صفر می‌کرد (شبِ ۱۱ سپتامبر).
_TV = "https://economic-calendar.tradingview.com/events"
_TV_HDR = {"Origin": "https://www.tradingview.com",
           "Referer": "https://www.tradingview.com/"}
CAL_VARIANTS = [
    ("tv+origin", _TV + "?from={f}&to={t}&minImportance=1", _TV_HDR),
    ("tv+origin+countries", _TV + "?from={f}&to={t}&countries=US", _TV_HDR),
    ("tv+origin+bare", _TV + "?from={f}&to={t}", _TV_HDR),
    ("tv+plain", _TV + "?from={f}&to={t}&minImportance=1", {}),
]


def classify(title):
    t = (title or "").lower()
    for name, keys in CLASSES:
        if any(k in t for k in keys):
            return name
    return None


def calendar_year(days=365, chunk=30):
    """تقویم اقتصادیِ گذشته، تکه‌تکه (بازهٔ بلند را سرور رد می‌کند)."""
    now = datetime.now(timezone.utc)
    out, seen = [], set()
    start = now - timedelta(days=days)
    locked = None                       # شکلِ درخواستی که جواب داد
    while start < now:
        end = min(start + timedelta(days=chunk), now)
        f = start.strftime("%Y-%m-%dT00:00:00.000Z")
        t = end.strftime("%Y-%m-%dT00:00:00.000Z")
        rows = []
        for name, tmpl, hdr in ([locked] if locked else CAL_VARIANTS):
            try:
                j = _json(tmpl.format(f=f, t=t), hdr)
                rows = j.get("result") if isinstance(j, dict) else j
                if locked is None:
                    locked = (name, tmpl, hdr)
                    print(f"  تقویم: شکلِ «{name}» جواب داد", flush=True)
                break
            except Exception as e:                       # noqa: BLE001
                if locked is None:
                    print(f"  تقویم {start:%Y-%m-%d} «{name}»: {_why(e)}",
                          flush=True)
                else:
                    print(f"  تقویم {start:%Y-%m-%d}: {_why(e)}", flush=True)
        for e in rows or []:
            cls = classify(e.get("title"))
            if not cls or (e.get("country") or "").upper() not in ("US", ""):
                continue
            try:
                at = datetime.fromisoformat(
                    str(e["date"]).replace("Z", "+00:00")).timestamp() * 1000
            except Exception:                            # noqa: BLE001
                continue
            key = (cls, int(at))
            if key in seen:
                continue
            seen.add(key)
            out.append({"cls": cls, "at": int(at), "title": e.get("title"),
                        "actual": e.get("actual"), "forecast": e.get("forecast")})
        start = end
    out.sort(key=lambda x: x["at"])
    return out


def hourly(sym, hours):
    """کندل ۱ساعته با عمقِ لازم، از همان منبعِ چرخه."""
    import sources
    rows = (sources.klines_deep(sym, "1h", hours)
            if hasattr(sources, "klines_deep") else sources.klines(sym, "1h", hours))
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
             "c": float(k[4]), "v": float(k[5])} for k in rows]


def _idx_at(cd, ms):
    """آخرین کندلی که **قبل از** لحظهٔ رویداد بسته شده. هرگز بعدی."""
    lo, hi = 0, len(cd) - 1
    if not cd or cd[0]["t"] > ms:
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if cd[mid]["t"] <= ms:
            lo = mid
        else:
            hi = mid - 1
    return lo


def regime(cd, i):
    """رژیمِ بستر در همان لحظه — فقط از گذشته."""
    if i < 200:
        return None
    win = cd[max(0, i - 200):i + 1]
    ma = statistics.fmean(c["c"] for c in win)
    trend = "بالای میانگین" if cd[i]["c"] > ma else "زیر میانگین"
    trs = [max(c["h"] - c["l"], abs(c["h"] - p["c"]), abs(c["l"] - p["c"]))
           for p, c in zip(win, win[1:])]
    atr = statistics.fmean(trs[-24:]) / (cd[i]["c"] or 1) * 100
    hist = sorted(statistics.fmean(trs[max(0, k - 24):k]) / (win[k]["c"] or 1) * 100
                  for k in range(24, len(win)))
    if hist:
        rank = sum(1 for h in hist if h < atr) / len(hist)
        vol = "نوسان بالا" if rank > 0.7 else ("نوسان پایین" if rank < 0.3
                                               else "نوسان میانه")
    else:
        vol = "نوسان نامعلوم"
    return {"trend": trend, "vol": vol, "atr_pct": round(atr, 3)}


def shocks(cd, sym, k=2.5, floor_pct=1.0, cooldown_h=24):
    """خانوادهٔ دومِ رویداد — از خودِ کندل، بی‌نیاز به هیچ منبع بیرونی.

    چرا لازم است: شبِ ۱۱ سپتامبر تقویم HTTP خطا داد و کلِ مطالعه صفر شد.
    مطالعه‌ای که تنها پایش یک میزبانِ بیرونی است، یک قطعیِ شبکه فاصله دارد
    تا هیچ. این خانواده همیشه هست چون کندل هست.

    تعریفِ از پیش ثبت‌شده (تغییرش = دفترِ حکم از صفر): حرکتِ یک کندل ۱ساعته
    ≥ k×ATR(۲۴) **و** ≥ کفِ مطلق؛ ATR فقط از کندل‌های قبل. لحظهٔ رویداد =
    بستهٔ همان کندل، پس افق‌ها کاملاً در آینده‌اند و آینده‌نگری ندارد.
    فاصلهٔ اجباری cooldown_h بین دو شوکِ هم‌جهت، وگرنه یک ریزشِ ممتد ده
    «مشاهدهٔ مستقل» جعل می‌کند و بازهٔ اطمینان را ساختگی تنگ می‌کند
    (همان درسِ ۲۴ اوت دربارهٔ ردیف‌های تکراری).
    """
    out, last = [], {}
    for i in range(200, len(cd)):
        prev = cd[i - 1]["c"]
        if not prev:
            continue
        mv = (cd[i]["c"] - prev) / prev * 100
        trs = [max(c["h"] - c["l"], abs(c["h"] - p["c"]), abs(c["l"] - p["c"]))
               for p, c in zip(cd[i - 25:i - 1], cd[i - 24:i])]
        atr = statistics.fmean(trs) / prev * 100 if trs else 0.0
        if atr <= 0 or abs(mv) < max(k * atr, floor_pct):
            continue
        d = "مثبت" if mv > 0 else "منفی"
        at = cd[i]["t"] + 3_600_000 - 1          # بستهٔ همان کندل
        if at - last.get(d, 0) < cooldown_h * 3_600_000:
            continue
        last[d] = at
        out.append({"cls": f"شوک {d} ۱ساعته", "at": at, "sym": sym,
                    "title": f"{sym} {mv:+.2f}٪ در یک ساعت",
                    "actual": None, "forecast": None, "move_pct": round(mv, 3)})
    return out


def surprise(ev):
    a, f = ev.get("actual"), ev.get("forecast")
    try:
        a, f = float(a), float(f)
    except (TypeError, ValueError):
        return "بی‌داده"
    if a > f:
        return "بالاتر از انتظار"
    if a < f:
        return "پایین‌تر از انتظار"
    return "مطابق انتظار"


def _ci(xs):
    n = len(xs)
    if n < 2:
        return None, None, None
    m = statistics.fmean(xs)
    sd = statistics.pstdev(xs) * math.sqrt(n / (n - 1)) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n)
    return round(m, 3), round(m - half, 3), round(m + half, 3)


def measure(events, series):
    """هر رویداد × هر نماد → بازده در افق‌ها، با برچسبِ رژیم."""
    rows = []
    for ev in events:
        for sym, cd in series.items():
            # رویدادِ نمادی (شوک) فقط روی نمادِ خودش؛ رویدادِ کلان روی همه.
            if ev.get("sym") and ev["sym"] != sym:
                continue
            i = _idx_at(cd, ev["at"])
            if i is None or i < 200 or i + max(HORIZONS) >= len(cd):
                continue
            base = cd[i]["c"]
            if not base:
                continue
            r = {"cls": ev["cls"], "sym": sym, "at": ev["at"],
                 "surprise": surprise(ev), **(regime(cd, i) or {})}
            for h in HORIZONS:
                r[f"ret_{h}h"] = round((cd[i + h]["c"] - base) / base * 100, 3)
            if i - PRE >= 0:
                r["drift_pre"] = round((base - cd[i - PRE]["c"]) / cd[i - PRE]["c"]
                                       * 100, 3)
            rows.append(r)
    return rows


def cluster(rows, ref="BTCUSDT"):
    """یک رویداد = یک مشاهده.

    رویدادِ کلان روی BTC و ETH هم‌زمان اندازه گرفته می‌شود و آن دو
    هم‌بسته‌اند؛ شمردنشان به‌عنوان دو مشاهدهٔ مستقل، n را دو برابر و
    بازهٔ اطمینان را ساختگی تنگ می‌کند — همان بیماریِ ردیف‌های تکراری
    که ۲۴ اوت یک ادعا را باطل کرد. پس بازده‌ها میانگین گرفته می‌شوند و
    رژیم از نمادِ مرجع (بیت‌کوین) خوانده می‌شود.

    شوکِ هم‌زمانِ BTC و ETH هم یک حرکتِ بازار است نه دو تا، پس همان
    قاعده رویش اجرا می‌شود؛ شوکِ تک‌نماد خودش یک خوشهٔ تک‌عضوی است.
    """
    g = {}
    for r in rows:
        g.setdefault((r["cls"], r["at"]), []).append(r)
    out = []
    for _k, rs in g.items():
        rs.sort(key=lambda r: (r["sym"] != ref, r["sym"]))
        base = dict(rs[0])                 # رژیم و غافلگیریِ نمادِ مرجع
        base["n_symbols"] = len(rs)
        for f in [f"ret_{h}h" for h in HORIZONS] + ["drift_pre"]:
            xs = [r[f] for r in rs if r.get(f) is not None]
            base[f] = round(statistics.fmean(xs), 3) if xs else None
        out.append(base)
    out.sort(key=lambda r: r["at"])
    return out


def summarize(rows, by):
    """گروه‌بندی + بازهٔ اطمینان. زیر MIN_N فقط شمرده می‌شود."""
    g = {}
    for r in rows:
        k = by(r)
        if k is None:
            continue
        g.setdefault(k, []).append(r)
    out = {}
    for k, rs in sorted(g.items(), key=lambda kv: -len(kv[1])):
        item = {"n": len(rs)}
        if len(rs) >= MIN_N:
            for h in HORIZONS:
                xs = [r[f"ret_{h}h"] for r in rs if r.get(f"ret_{h}h") is not None]
                m, lo, hi = _ci(xs)
                item[f"ret_{h}h"] = {"mean_pct": m, "ci": [lo, hi],
                                     "clears_zero": bool(lo is not None and
                                                         (lo > 0 or hi < 0))}
            pre = [r["drift_pre"] for r in rs if r.get("drift_pre") is not None]
            if pre:
                m, lo, hi = _ci(pre)
                item["drift_pre_pct"] = {"mean_pct": m, "ci": [lo, hi]}
        else:
            item["note"] = "نمونه کم — فقط شمرده شد، عدد ندارد"
        out[k] = item
    return out


def _p_from_ci(mean, lo, hi):
    """p دوطرفه از همان بازهٔ اطمینان (نصفِ پهنا = ۱.۹۶×خطای معیار)."""
    if mean is None or lo is None or hi is None:
        return None
    se = (hi - lo) / (2 * 1.96)
    if se <= 0:
        return 0.0
    z = abs(mean) / se
    return 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))


def conclusions(by_cls, by_cls_regime, by_cls_surprise, alpha=0.05):
    """قاعده‌ها + **تصحیح چندآزمونی**.

    بازهٔ اطمینانِ تنها کافی نیست: این مطالعه ده‌ها خانه را هم‌زمان
    می‌سنجد (دسته × رژیم × غافلگیری × سه افق). با ۲۰۰ آزمون، ۱۰ خانه
    فقط از شانس «معنادار» می‌شوند. پس همان انضباطی که در آزمایشگاه‌های
    دیگرِ این مخزن هست این‌جا هم لازم است: آستانهٔ Šidák روی شمارِ
    واقعیِ خانه‌های آزموده‌شده.

    خروجی هر دو را نگه می‌دارد — «CI از صفر رد کرد» (نامزد) و
    «از آستانهٔ چندآزمونی هم رد شد» (قاعده). فقط دستهٔ دوم حق ورود به
    حافظه دارد؛ قفسهٔ خالی از قفسهٔ آلوده بهتر است.
    """
    found, tested = [], 0
    for label, table in (("دسته", by_cls), ("دسته×رژیم", by_cls_regime),
                         ("دسته×غافلگیری", by_cls_surprise)):
        for k, v in table.items():
            for h in HORIZONS:
                d = v.get(f"ret_{h}h") or {}
                if d.get("mean_pct") is None:
                    continue
                tested += 1
                if d.get("clears_zero"):
                    found.append({
                        "scope": label, "key": k, "horizon_h": h,
                        "n": v["n"], "mean_pct": d["mean_pct"], "ci": d["ci"],
                        "direction": "صعودی" if d["mean_pct"] > 0 else "نزولی",
                        "p": _p_from_ci(d["mean_pct"], *d["ci"]),
                    })
    thr = 1 - (1 - alpha) ** (1 / tested) if tested else alpha
    for r in found:
        r["m_tests"] = tested
        r["alpha_sidak"] = round(thr, 6)
        r["survives_multiple"] = bool(r["p"] is not None and r["p"] < thr)
    found.sort(key=lambda x: (not x["survives_multiple"], -abs(x["mean_pct"])))
    return found


def build(days=365, symbols=("BTCUSDT", "ETHUSDT")):
    print(f"تقویم {days} روز…", flush=True)
    cal = calendar_year(days)
    print(f"  {len(cal)} رویدادِ تقویمیِ دسته‌بندی‌شده", flush=True)
    hours = days * 24 + 300
    series = {}
    for s in symbols:
        try:
            cd = hourly(s, hours)
            if len(cd) > 250:
                series[s] = cd
                print(f"  {s}: {len(cd)} کندل ۱س", flush=True)
        except Exception as e:                           # noqa: BLE001
            print(f"  {s}: {_why(e)}", flush=True)
    shock = []
    for s, cd in series.items():
        got = shocks(cd, s)
        shock += got
        print(f"  {s}: {len(got)} شوکِ کندلی", flush=True)
    events = cal + shock
    families = {"تقویم اقتصادی": len(cal), "شوکِ کندلی": len(shock)}
    if not events or not series:
        return {"status": "NO_DATA", "n_events": len(events),
                "n_symbols": len(series), "families": families,
                "generated": int(time.time() * 1000)}
    raw = measure(events, series)
    # یک رویداد = یک مشاهده (BTC و ETH هم‌بسته‌اند) — وگرنه n دوبرابر و
    # بازهٔ اطمینان ساختگی تنگ می‌شود.
    rows = cluster(raw)
    print(f"  {len(raw)} مشاهدهٔ خام → {len(rows)} خوشه (یک رویداد = یکی)",
          flush=True)
    by_cls = summarize(rows, lambda r: r["cls"])
    by_reg = summarize(rows, lambda r: f'{r["cls"]} · {r.get("trend")} · {r.get("vol")}'
                       if r.get("trend") else None)
    by_sur = summarize(rows, lambda r: f'{r["cls"]} · {r["surprise"]}')
    rules = conclusions(by_cls, by_reg, by_sur)
    spans = [r["at"] for r in rows]
    return {
        "generated": int(time.time() * 1000),
        "days": days, "n_events": len(events), "n_obs": len(rows),
        "n_obs_raw": len(raw), "clustered_by": "یک رویداد = یک مشاهده",
        "families": families, "symbols": sorted(series),
        "span": [time.strftime("%Y-%m-%d", time.gmtime(min(spans) / 1000)),
                 time.strftime("%Y-%m-%d", time.gmtime(max(spans) / 1000))]
        if spans else None,
        "min_n": MIN_N, "horizons_h": list(HORIZONS),
        "by_class": by_cls, "by_class_regime": by_reg,
        "by_class_surprise": by_sur,
        "rules_ci_clears_zero": rules,
        "boundary": ("هم‌زمانی علیت نیست: این مطالعه می‌گوید BTC/ETH بعد از "
                     "رویداد چه کردند، نه این‌که رویداد علتش بود. رانشِ قبل "
                     "از رویداد هم گزارش می‌شود — اگر حرکت قبلش شروع شده، "
                     "ورود بعد از خبر دیر است. n زیر ۸ عدد نمی‌گیرد. "
                     "دفتر خبرِ داخلی فقط ۳۸ روز دارد، پس این مطالعه روی "
                     "تقویمِ اقتصادی و کندل بنا شده نه روی تیترها. "
                     "BTC و ETH هم‌بسته‌اند: دو مشاهده از یک رویدادِ کلان "
                     "کاملاً مستقل نیستند، پس بازهٔ اطمینان کمی تنگ‌تر از "
                     "واقع است. خانوادهٔ «شوکِ کندلی» با فاصلهٔ اجباری ۲۴ "
                     "ساعته شمرده می‌شود تا یک حرکتِ ممتد چند مشاهده جعل "
                     "نکند. اگر شمارِ خانوادهٔ تقویم صفر باشد، یعنی منبعِ "
                     "تقویم آن اجرا نیامد — نه این‌که رویدادی نبوده."),
        "panel": "لیام تریدر ۹",
    }


def write_memory(res):
    """حافظهٔ دائمی — فقط قاعده‌هایی که از **آستانهٔ چندآزمونی** هم رد شدند.

    قانون ۰۳ می‌گوید CI بالای صفر؛ ولی با ده‌ها آزمونِ هم‌زمان، CI تنها
    یعنی «نامزد»، نه «قاعده». حافظه فقط بازمانده‌های Šidák را می‌گیرد.
    """
    MEM.parent.mkdir(parents=True, exist_ok=True)
    rules = [r for r in (res.get("rules_ci_clears_zero") or [])
             if r.get("survives_multiple")]
    doc = {
        "generated": res.get("generated"),
        "source": "hamid/event_study.py",
        "span": res.get("span"),
        "n_obs": res.get("n_obs"),
        "validation_status": "BACKTESTED",
        "usage": ("در شرایط مشابه (همان دسته + همان رژیم) این‌ها شاهدند، "
                  "نه دروازه. ورود به تصمیم فقط از مسیر قانون ۰۳."),
        "rules": rules[:40],
        "n_candidates_ci_only": len(res.get("rules_ci_clears_zero") or []),
        "multiple_testing": ("Šidák روی شمارِ واقعیِ خانه‌های آزموده‌شده؛ "
                             "نامزدی که فقط CI را رد کرده وارد حافظه نشده."),
        "boundary": res.get("boundary"),
    }
    MEM.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return MEM


def _selftest():
    ok = fails = 0

    def chk(c, m):
        nonlocal ok, fails
        if c:
            ok += 1
        else:
            fails += 1
            print(f"  ✗ {m}")

    chk(classify("US CPI m/m") == "تورم CPI", "دسته‌بندی CPI کار نکرد")
    chk(classify("Fed Interest Rate Decision") == "نرخ بهرهٔ فد", "دسته‌بندی فد")
    chk(classify("Cheese Production") is None, "دستهٔ بی‌ربط رد نشد")

    # کندلِ ساختگی: ۵۰۰ ساعت، شیبِ ثابت
    cd = [{"t": 1_700_000_000_000 + i * 3_600_000, "o": 100 + i * 0.1,
           "h": 100.5 + i * 0.1, "l": 99.5 + i * 0.1, "c": 100 + i * 0.1,
           "v": 10} for i in range(500)]
    i = _idx_at(cd, cd[300]["t"] + 60_000)
    chk(i == 300, f"نمایه‌یابی غلط: {i}")
    chk(_idx_at(cd, cd[0]["t"] - 1) is None, "لحظهٔ قبل از شروع None نداد")
    # **هرگز کندلِ بعدی**: لحظهٔ دقیقاً روی مرز باید همان کندل را بدهد
    chk(_idx_at(cd, cd[250]["t"]) == 250, "مرز به کندلِ بعدی لغزید")

    r = regime(cd, 400)
    chk(r and r["trend"] == "بالای میانگین", f"رژیمِ روندِ صعودی غلط: {r}")
    chk(regime(cd, 50) is None, "رژیم با تاریخچهٔ کم عدد داد")

    ev = [{"cls": "تورم CPI", "at": cd[300]["t"] + 1000,
           "actual": 3.1, "forecast": 3.0}]
    rows = measure(ev, {"X": cd})
    chk(len(rows) == 1, f"اندازه‌گیری ردیف نساخت: {len(rows)}")
    chk(rows[0]["surprise"] == "بالاتر از انتظار", "غافلگیری غلط")
    chk(rows[0]["ret_1h"] > 0, "بازدهِ سریِ صعودی مثبت نشد")
    chk("drift_pre" in rows[0], "رانشِ قبل ثبت نشد")

    # ── خانوادهٔ شوک: بی‌نیاز از تقویم ─────────────────────────────────
    chk(shocks(cd, "X") == [], "سریِ آرام شوک ساخت")
    # پله (نه تیزه): بالا بردنِ یک کندلِ تنها، کندلِ بعدی را هم شوکِ
    # برگشتی می‌کند و آزمون را از موضوعش دور می‌اندازد.
    sc = [dict(c) for c in cd]
    for j in (260, 268, 400):                    # ۲۶۰ و ۲۶۸ داخل cooldown
        for q in range(j, len(sc)):
            for f in ("o", "h", "l", "c"):
                sc[q][f] *= 1.05
    sh = shocks(sc, "X")
    chk(len(sh) == 2, f"شوک: انتظار ۲ (cooldown یکی را بخورد)، شد {len(sh)}")
    chk(all(s["sym"] == "X" for s in sh), "شوک بی‌نمادِ مالک ساخته شد")
    chk(all(s["cls"].startswith("شوک") for s in sh), "برچسبِ شوک غلط")
    # لحظهٔ شوک باید به همان کندل نگاشت شود، نه بعدی (ضدآینده‌نگری)
    chk(_idx_at(sc, sh[0]["at"]) == 260, "لحظهٔ شوک به کندلِ دیگری افتاد")
    # اثباتِ منفی برای cooldown: بی‌فاصله باید ۳ بشود
    chk(len(shocks(sc, "X", cooldown_h=0)) == 3, "بی‌cooldown شمار عوض نشد")
    # رویدادِ نمادی نباید روی نمادِ دیگر اندازه گرفته شود
    cross = measure([{"cls": "ش", "at": cd[300]["t"] + 1000, "sym": "Y"}],
                    {"X": cd})
    chk(cross == [], "رویدادِ نمادِ Y روی نمادِ X اندازه گرفته شد")

    # زیر آستانه: عدد نمی‌گیرد
    sm = summarize(rows * 3, lambda r: r["cls"])
    chk("note" in sm["تورم CPI"], "با n کم عدد داد")
    sm2 = summarize(rows * 12, lambda r: r["cls"])
    chk("ret_1h" in sm2["تورم CPI"], "با n کافی عدد نداد")

    # قاعده فقط با CI رد از صفر
    fake = {"A": {"n": 20, "ret_1h": {"mean_pct": 1.0, "ci": [0.5, 1.5],
                                      "clears_zero": True}}}
    chk(len(conclusions(fake, {}, {})) == 1, "قاعدهٔ CI-گذشته پیدا نشد")
    fake2 = {"A": {"n": 20, "ret_1h": {"mean_pct": 1.0, "ci": [-0.5, 2.5],
                                       "clears_zero": False}}}
    chk(conclusions(fake2, {}, {}) == [], "قاعده‌ای با CI شاملِ صفر پذیرفته شد")

    # ── خوشه‌بندی: یک رویداد = یک مشاهده ──────────────────────────────
    ev1 = [{"cls": "تورم CPI", "at": cd[300]["t"] + 1000,
            "actual": 3.1, "forecast": 3.0}]
    two = measure(ev1, {"BTCUSDT": cd, "ETHUSDT": cd})
    chk(len(two) == 2, f"دو نماد دو ردیف نساختند: {len(two)}")
    cl = cluster(two)
    chk(len(cl) == 1, f"دو مشاهدهٔ یک رویداد خوشه نشدند: {len(cl)}")
    chk(cl[0]["sym"] == "BTCUSDT", "نمادِ مرجع بیت‌کوین نشد")
    chk(cl[0]["n_symbols"] == 2, "شمارِ نماد در خوشه ثبت نشد")
    chk(abs(cl[0]["ret_1h"] - two[0]["ret_1h"]) < 1e-9, "میانگینِ خوشه غلط")
    # دو رویدادِ جدا در دو لحظه، خوشهٔ جدا می‌مانند
    ev2 = ev1 + [{"cls": "تورم CPI", "at": cd[320]["t"] + 1000}]
    chk(len(cluster(measure(ev2, {"BTCUSDT": cd}))) == 2,
        "دو رویدادِ جدا به‌اشتباه یکی شدند")

    # ── تصحیح چندآزمونی: CI-گذشته ≠ قاعده ─────────────────────────────
    # یک خانه، به‌زور از صفر رد شده (p≈۰.۰۵): با یک آزمون می‌ماند…
    weak = {"A": {"n": 20, "ret_1h": {"mean_pct": 1.0, "ci": [0.02, 1.98],
                                      "clears_zero": True}}}
    one = conclusions(weak, {}, {})
    chk(len(one) == 1 and one[0]["m_tests"] == 1, f"شمارِ آزمون غلط: {one}")
    chk(one[0]["survives_multiple"], "با یک آزمون هم رد شد — آستانه غلط است")
    # …ولی کنارِ ۹۹ خانهٔ دیگر باید بیفتد
    many = dict(weak)
    for i in range(99):
        many[f"X{i}"] = {"n": 20, "ret_1h": {"mean_pct": 0.1,
                                             "ci": [-0.9, 1.1],
                                             "clears_zero": False}}
    got = conclusions(many, {}, {})
    chk(got and got[0]["m_tests"] == 100, f"شمارِ آزمون: {got[:1]}")
    chk(got and not got[0]["survives_multiple"],
        "با ۱۰۰ آزمون، نامزدِ مرزی هنوز «قاعده» شمرده شد")
    # و حافظه فقط بازمانده‌ها را می‌گیرد
    doc_rules = [r for r in got if r.get("survives_multiple")]
    chk(doc_rules == [], "نامزدِ نجات‌نیافته وارد فهرست حافظه شد")

    src = (HERE / "event_study.py").read_text(encoding="utf-8")
    body = src.split("def _selftest(")[0]
    for bad in ("paper._append", "telegram.", "digest_closed"):
        chk(bad not in body, f"مطالعه دفتر/ارسال تولید را دست زد: {bad}")

    print(f"event_study: {ok} بررسی سبز" + (f" · {fails} قرمز" if fails else ""))
    return 1 if fails else 0


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--days", type=int, default=365)
    a = ap.parse_args(list(argv))
    if a.selftest:
        return _selftest()
    res = build(a.days)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    p = write_memory(res)
    print(f"\nنوشته شد: {OUT}\nحافظه: {p}")
    print(f"رویداد {res.get('n_events')} · مشاهده {res.get('n_obs')} · "
          f"قاعدهٔ CI-گذشته {len(res.get('rules_ci_clears_zero') or [])}")
    for r in (res.get("rules_ci_clears_zero") or [])[:12]:
        print(f"  {r['key']} · +{r['horizon_h']}س · n={r['n']} · "
              f"{r['mean_pct']:+.2f}% CI={r['ci']} → {r['direction']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
