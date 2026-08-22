"""بیگ‌مانی — واگرایی پول درشت در برابر جمعیت (E10، دستور حمید، ۲۲ اوت).

منبع فایلی که حمید فرستاد (`big_money.py`، ایمیل‌نشده — از آپلود مستقیم):
یک مانیتور محلی با داشبورد HTML که روی Gate.io USDT-perp `contract_stats`
کار می‌کند. هستهٔ محاسباتیش (نه سرور HTTP/داشبورد مرورگرش که این‌جا لازم
نیست، چون معماری این ریپو Actions است نه حلقهٔ زندهٔ localhost — قانون
۰۲/۰۵) این‌جا عیناً پورت شده: fetch_stats، long_pct، ویژگی‌های خام،
z-score غلتان، و run_backtest (کوانتایل + این‌سمپل/اوت‌آف‌سمپل + هزینه).

سه خط توضیح حمید → سه فیلد API:
  خط قیمت              → mark_price
  سبز «پول‌های درشت»    → top_lsr_size (نسبت لانگ/شورت کوهورت برتر به حجم)
  آبی «کل پوزیشن لانگ»  → lsr_account (نسبت لانگ/شورت همهٔ حساب‌ها)
«قطع کردن این خطوط» = دقیقاً ویژگی div = topSizeLong% − allLong% که فایل
اصلی هم به‌عنوان اولین فیچر بک‌تست تعریف کرده بود — واگرایی پول درشت از
جمعیت.

مالکیت طبق قانون ۰۸: این داده «بستر مشتقات» است، نه اردر بلاک — پس E10.
هنوز BACKTESTED نیست؛ فقط RESEARCHED تا این بک‌تست روی Actions اجرا و
عدد واقعی ثبت شود (چرخهٔ قانون ۰۳).

منبع دادهٔ زنده به این ماژول از این سندباکس نشست غیرقابل‌دسترس است —
پروکسی صریحاً api.gateio.ws را ۴۰۳ می‌کند (سیاست شبکه). طبق قاعدهٔ ثابت
پروژه («GitHub Actions — تمام محاسبهٔ سنگین، هرگز لپ‌تاپ»)، اجرای واقعی
فقط روی Actions معنی دارد؛ تست‌های این ماژول کاملاً آفلاین‌اند.
"""
import json
import time
import urllib.request

STATS_URL = "https://api.gateio.ws/api/v4/futures/usdt/contract_stats"
UA = {"User-Agent": "liam9-big-money/1.0"}

# (تایم، ثانیه/کندل، بازهٔ نگهداری) — ریزترین اول. Gate.io حداکثر ۵ دقیقه
# را حدود ۵۵ روز و ۱ ساعته را حدود ۸۵ روز نگه می‌دارد (بررسی‌شدهٔ فایل اصلی).
STATS_TIERS = [("5m", 300, 55 * 86400), ("1h", 3600, 85 * 86400)]
STATS_PAGE = 100

BT_DAYS = 50                     # داخل بازهٔ نگهداری ۵ دقیقه‌ای، نه لبه‌اش
BT_BAR = 300
BT_ZWIN_SECS = 86400             # پنجرهٔ z-score غلتان = ۱ روز
BT_HORIZONS = [("1h", 3600), ("4h", 14400), ("24h", 86400)]
BT_COST_BPS = 15.0               # کارمزد دوسر لیام (نه پیش‌فرض ۱۰ فایل اصلی؛
                                  # همان عدد تأییدشدهٔ VIP0 بیت‌یونیکس در پروژه)
BT_OOS_SPLIT = 0.60

BT_FEATURES = [
    ("div",   "واگرایی — پول درشت منهای جمعیت",
     "لانگ٪ کوهورت برتر به حجم منهای لانگ٪ همهٔ حساب‌ها"),
    ("skew",  "چولگی حجم کوهورت",
     "(حجم لانگ - حجم شورت)/کل حجم، کوهورت برتر"),
    ("dsize", "مومنتوم حجم لانگِ کوهورت",
     "تغییر یک‌ساعتهٔ حجم پوزیشن لانگ کوهورت برتر"),
    ("crowd", "پوزیشن جمعیت",
     "لانگ٪ همهٔ حساب‌ها — معیار خلاف‌روند رایج"),
    ("size",  "پوزیشن پول درشت",
     "لانگ٪ کوهورت برتر به حجم، تنها"),
]


def _get_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception:                             # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def long_pct(ratio):
    """نسبت لانگ/شورت r به سهم لانگ از زوج تبدیل می‌شود: r/(1+r)."""
    r = float(ratio)
    return r / (1.0 + r) * 100.0


def _tier(from_ts):
    age = time.time() - from_ts
    for name, secs, keep in STATS_TIERS:
        if age <= keep:
            return name, secs
    return STATS_TIERS[-1][0], STATS_TIERS[-1][1]


def fetch_stats(sym, interval, frm, to):
    """contract_stats صفحه‌بندی‌شده — [{t, topSizeLong, allLong, topAcctLong,
    topLongSize, topShortSize, px}] صعودی زمانی، بدون تکرار."""
    step = dict((n, s) for n, s, _ in STATS_TIERS)[interval]
    out, cur = {}, int(frm)
    while cur < to:
        page = _get_json(f"{STATS_URL}?contract={sym}_USDT&interval={interval}"
                         f"&from={cur}&limit={STATS_PAGE}")
        if not page:
            break
        for r in page:
            t = int(r["time"])
            if t > to:
                continue
            try:
                out[t] = {
                    "t": t,
                    "allLong": round(long_pct(r["lsr_account"]), 2),
                    "topSizeLong": round(long_pct(r["top_lsr_size"]), 2),
                    "topAcctLong": round(long_pct(r["top_lsr_account"]), 2),
                    "topLongSize": float(r.get("top_long_size") or 0),
                    "topShortSize": float(r.get("top_short_size") or 0),
                    "px": float(r.get("mark_price") or 0),
                }
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
        last = max(int(r["time"]) for r in page)
        if last <= cur:
            break
        cur = last + step
        time.sleep(0.1)
    return [out[k] for k in sorted(out)]


def _raw_features(rows, bar_secs=BT_BAR):
    """ویژگی خام هر کندل — بدون نگاه به آینده: هر مقدار فقط از ردیف i یا قبلش."""
    back = max(1, 3600 // bar_secs)
    out = []
    for i, r in enumerate(rows):
        tot = r["topLongSize"] + r["topShortSize"]
        skew = ((r["topLongSize"] - r["topShortSize"]) / tot * 100) if tot else 0.0
        j = i - back
        prev = rows[j]["topLongSize"] if j >= 0 else None
        dsize = ((r["topLongSize"] / prev - 1) * 100) if prev else 0.0
        out.append({"div": r["topSizeLong"] - r["allLong"], "skew": skew,
                    "dsize": dsize, "crowd": r["allLong"], "size": r["topSizeLong"]})
    return out


def _zscores(vals, win):
    """z-score غلتان — سطح پایه هر نماد فرق دارد، پس فقط انحراف از میانگین
    اخیر خودش قابل‌مقایسه است."""
    z, s, s2 = [], 0.0, 0.0
    for i, v in enumerate(vals):
        s += v
        s2 += v * v
        if i >= win:
            s -= vals[i - win]
            s2 -= vals[i - win] ** 2
        n = min(i + 1, win)
        if n < win // 2:
            z.append(None)
            continue
        m = s / n
        var = max(0.0, s2 / n - m * m)
        sd = var ** 0.5
        z.append((v - m) / sd if sd > 1e-12 else 0.0)
    return z


def _tstat(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = (var / n) ** 0.5
    return m / se if se > 1e-15 else 0.0


def run_backtest(rows, cost_bps=BT_COST_BPS, bar_secs=BT_BAR):
    """مطالعهٔ رویدادی کوانتایل + چک این‌سمپل/اوت‌آف‌سمپل خالص از هزینه.

    جهت (بالا→لانگ یا بالا→شورت) فقط با نیمهٔ این‌سمپل تعیین و منجمد
    می‌شود؛ نیمهٔ اوت‌آف‌سمپل با همان جهتِ منجمد نمره می‌گیرد — نکتهٔ اصلی
    تمرین. نمونه‌گیری هم‌پوشانی ندارد (هر افق به‌اندازهٔ خودش جلو می‌رود)."""
    px = [r["px"] for r in rows]
    n = len(rows)
    zwin = max(12, BT_ZWIN_SECS // bar_secs)
    horizons = [(name, max(1, secs // bar_secs)) for name, secs in BT_HORIZONS]
    raw = _raw_features(rows, bar_secs)
    zs = {k: _zscores([f[k] for f in raw], zwin) for k, _, _ in BT_FEATURES}
    split = int(n * BT_OOS_SPLIT)
    cost = cost_bps / 10000.0
    results, best = [], None

    for key, label, desc in BT_FEATURES:
        z = zs[key]
        for hname, h in horizons:
            obs = []
            for i in range(0, n - h, h):
                if z[i] is None:
                    continue
                fwd = px[i + h] / px[i] - 1 if px[i] else None
                if fwd is None:
                    continue
                obs.append((i, z[i], fwd))
            if len(obs) < 40:
                continue
            zv = sorted(o[1] for o in obs)
            q20, q80 = zv[len(zv) // 5], zv[len(zv) * 4 // 5]
            ins = [(v, f) for i, v, f in obs if i < split]
            oos = [(v, f) for i, v, f in obs if i >= split]
            if len(ins) < 20 or len(oos) < 20:
                continue
            hi_in = [f for v, f in ins if v >= q80]
            lo_in = [f for v, f in ins if v <= q20]
            if len(hi_in) < 5 or len(lo_in) < 5:
                continue
            edge_in = (sum(hi_in) / len(hi_in)) - (sum(lo_in) / len(lo_in))
            sign = 1 if edge_in > 0 else -1
            trades_oos = [(sign * f if v >= q80 else -sign * f) - cost for v, f in oos
                          if v >= q80 or v <= q20]
            if not trades_oos:
                continue
            r = {"feature": key, "label": label, "desc": desc,
                 "horizon": hname, "bars": h, "sign": sign,
                 "n": len(obs), "oosN": len(trades_oos),
                 "oosMean": round(sum(trades_oos) / len(trades_oos) * 100, 4),
                 "oosHit": round(sum(1 for x in trades_oos if x > 0)
                                / len(trades_oos) * 100, 1),
                 "oosT": round(_tstat(trades_oos), 2),
                 "thin": len(trades_oos) < 30,
                 "oos_trades": trades_oos}
            results.append(r)
            if not r["thin"] and (best is None or r["oosMean"] > best["oosMean"]):
                best = r

    ntests = len(results)
    return {"results": sorted(results, key=lambda r: (r["thin"], -r["oosMean"])),
            "best": best, "tests": ntests,
            "bonferroni": round(2.58 if ntests <= 10 else 3.0, 2),
            "cost": cost_bps, "bars": n,
            "from": rows[0]["t"] if rows else 0, "to": rows[-1]["t"] if rows else 0}
