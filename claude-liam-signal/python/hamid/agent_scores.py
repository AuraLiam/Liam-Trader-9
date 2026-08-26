#!/usr/bin/env python3
"""امتیاز و وزنِ اتاق‌های ایجنت از عملکردِ واقعی در پیپرمود.

دستور حمید (۲۷ اوت): «به ایجنت‌ها بر اساس عملکردشون در زمان و موقعیت‌های
مختلف امتیاز میدی در پیپر مود و بعد بر اساس امتیازهاشون در تصمیم‌گیری
نهایی که سیگنال در تایم ۱۵ دقیقه ارسال می‌شود وزن می‌دی… اگه ایجنتی توی
ریزش دامیننس تتر چند بار سیگنال رو هم شورت تشخیص داده یعنی دچار اشتباه
شده… و این امر متغیر است؛ شاید همین ایجنت با یادگیری در گذر زمان بتواند
امتیاز بیشتری بگیرد.»

## چطور امتیاز ساخته می‌شود (نه ادعا — شمارش)

هر معاملهٔ بستهٔ دفتر پیپر یک «رأی» از هر اتاق روی خودش دارد که لحظهٔ
تصمیم ثبت شده بود (`why.ob_align`، `why.pattern_align`، …). قاعده:

- رأی «هم‌جهت» (with) یعنی آن اتاق این معامله را تأیید کرده → اعتبارش
  همان R معامله است. معامله سود داد، اتاق درست گفته؛ ضرر داد، غلط.
- رأی «مخالف» (against) یعنی اتاق هشدار داده → اعتبارش −R است. معامله
  ضرر داد یعنی هشدارش درست بوده.
- رأی نداده = هیچ اعتباری، نه مثبت نه منفی.

## هر اتاق قانون خودش را دارد (خواستهٔ صریح حمید)

جدول `ROOMS` پایین: هر اتاق می‌گوید کدام میدان‌ها رأیش است و رأیش چطور
به عدد ترجمه می‌شود. اتاق تازه بدون قانونِ نوشته‌شده امتیاز نمی‌گیرد.

## موقعیت بازار جزء کلید است

امتیاز به تفکیک **بستر** شمرده می‌شود: ریزش/صعود/خنثیِ USDT.D در لحظهٔ
باز شدن معامله (از سری واقعی اتاق دامیننس). پس دقیقاً همان چیزی که حمید
گفت قابل شمارش می‌شود: «این اتاق در ریزش دامیننس تتر چند بار شورت را
تأیید کرد و نتیجه چه شد.»

## سه محافظِ ضدِ فریب خودمان

۱. **کهنگی**: وزن‌دهی بر پایهٔ گذشته یک تلهٔ شناخته‌شده دارد — در ادبیات
   پیش‌بینی گروهی ثبت شده که وزنِ آموخته از گذشته درست وقتی یک عضو
   افت می‌کند او را سنگین‌تر می‌کند. درمان: نیم‌عمر ۷ روزه (گذشتهٔ دور
   کم‌اثر) + بی‌اثر شدن وزنِ اتاقی که ۷۲ ساعت رأی نداده.
۲. **کوچکیِ نمونه**: انقباض به سمت وزن خنثی با n/(n+۲۰). ده معامله حق
   ندارد وزن را جابه‌جا کند.
۳. **مرز قانون ۰۳**: باند حرکت وزن پیش‌فرض ±۰.۱۵ است (اکتشافی)؛ باند
   کاملِ ±۰.۴۰ فقط وقتی باز می‌شود که بازهٔ اطمینان همان اتاق از صفر رد
   کرده باشد. **هیچ اتاقی حق وتو ندارد** — وزن فقط سهمِ امتیازِ همان
   اتاق را کم و زیاد می‌کند.

خروجی: `signals/agent-weights.json` با شناسنامهٔ کامل (n، میانگین، CI،
باند، دلیل) تا هر وزن قابل بازتولید باشد.
"""
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
DOM_SERIES = ROOT / "brain" / "dominance-series.json"
OUT = ROOT / "signals" / "agent-weights.json"

HALF_LIFE_DAYS = 7.0        # نیم‌عمر تازگی — ضد کهنگیِ وزن
SHRINK_N0 = 20.0            # انقباض به خنثی تا وقتی نمونه کم است
R_SCALE = 0.50              # ۰.۵R اعتبار ≈ سقف باند
BAND_EXPLORATORY = 0.15     # بدون CI-گذشته
BAND_CONFIRMED = 0.40       # با CI کاملاً بالای/زیر صفر
STALE_HOURS = 72.0          # رأی‌ندادن طولانی → برگشت به وزن خنثی
MIN_N = 12                  # زیر این، وزن اصلاً حرکت نمی‌کند


def _with_against(v):
    """نگاشت استانداردِ رأی رشته‌ای به +۱ (هم‌جهت) / −۱ (مخالف)."""
    if v == "with":
        return 1
    if v == "against":
        return -1
    return None


def _bool_vote(v):
    """میدان بولی: True = اتاق حرفی برای تأیید داشت؛ False = رأی نداده."""
    return 1 if v is True else None


def _fib_golden(v):
    """ناحیهٔ طلایی فیبوناچی تأیید است؛ بیرونش رأیِ مخالف نیست، سکوت است."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return 1 if 0.38 <= f <= 0.705 else None


# ── قانون امتیاز هر اتاق (خواستهٔ صریح حمید: هر اتاق قانون خودش) ────────
ROOMS = {
    "structure": {"engine": "E07", "label": "ساختار (سقف/کف، روند)",
                  "fields": {"supertrend_align": _with_against,
                             "ema200_align": _with_against},
                  "rule": "رأی = هم‌جهتیِ روندِ ساختاری با جهت معامله"},
    "smc": {"engine": "E08", "label": "اردر بلاک و FVG",
            "fields": {"ob_align": _with_against},
            "rule": "رأی = هم‌جهتیِ اردر بلاک معتبر با جهت معامله"},
    "candles": {"engine": "E09", "label": "کندل و هندسهٔ ورود",
                "fields": {"pattern_align": _with_against},
                "rule": "رأی = الگوی کندلی هم‌جهت/مخالف"},
    "ict": {"engine": "E08", "label": "ساختار ICT",
            "fields": {"ict_align": _with_against},
            "rule": "رأی = هم‌جهتی ساختار ICT"},
    "experience": {"engine": "E21", "label": "حافظه و تجربه",
                   "fields": {"exp_used": _bool_vote},
                   "rule": "رأی = کارنامهٔ همان ارز/جهت پشت این تصمیم بود"},
    "fib": {"engine": "E09", "label": "عمق پولبک (فیبوناچی)",
            "fields": {"fib_ratio": _fib_golden},
            "rule": "رأی = عمق پولبک در ناحیهٔ طلایی ۰.۳۸–۰.۷۰۵"},
}


def _dom_points():
    try:
        return json.loads(DOM_SERIES.read_text()).get("points") or []
    except Exception:                                # noqa: BLE001
        return []


def context_at(ts_ms, pts):
    """بسترِ بازار در لحظهٔ تصمیم — از سری واقعی USDT.D، نه حدس.

    تغییر ۴ ساعتهٔ USDT.D: منفی‌تر از −۰.۰۵ = ریزش دامیننس (بازار رو به
    بالا)، مثبت‌تر از +۰.۰۵ = صعود دامیننس (بازار رو به پایین). بیرون
    از پوشش سری = `unknown`؛ عددِ ساختگی جای دادهٔ نبوده نمی‌نشیند."""
    if not ts_ms or not pts:
        return "unknown"
    if ts_ms < pts[0]["t"] or ts_ms > pts[-1]["t"] + 3_600_000:
        return "unknown"
    now = min(pts, key=lambda p: abs(p["t"] - ts_ms))
    past_t = ts_ms - 4 * 3_600_000
    if past_t < pts[0]["t"]:
        return "unknown"
    past = min(pts, key=lambda p: abs(p["t"] - past_t))
    d = now["u"] - past["u"]
    if d <= -0.05:
        return "usdtd_down"
    if d >= 0.05:
        return "usdtd_up"
    return "usdtd_flat"


def votes_of(why):
    """رأی هر اتاق روی یک معاملهٔ بسته: {اتاق: +۱/−۱}."""
    out = {}
    for room, spec in ROOMS.items():
        for field, fn in spec["fields"].items():
            v = fn(why.get(field))
            if v is not None:
                out[room] = v
                break
    return out


def _ci95(xs):
    """بازهٔ اطمینان نرمالِ میانگین — همان معیارِ همیشگی «از صفر رد شد؟»."""
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return [round(m - 1.96 * se, 4), round(m + 1.96 * se, 4)]


def _weight(mean_credit, n, ci, last_ts, now_ms):
    """وزن نهایی + دلیلش. هرگز وتو؛ فقط ضریبِ سهمِ همان اتاق."""
    if n < MIN_N:
        return 1.0, f"نمونه کم ({n} < {MIN_N}) — وزن خنثی"
    band = BAND_EXPLORATORY
    note = "باند اکتشافی (CI صفر را در بر می‌گیرد)"
    if ci and (ci[0] > 0 or ci[1] < 0):
        band = BAND_CONFIRMED
        note = "باند کامل — CI از صفر رد کرده"
    shrink = n / (n + SHRINK_N0)
    raw = (mean_credit / R_SCALE) * shrink
    w = 1.0 + max(-band, min(band, raw))
    age_h = (now_ms - last_ts) / 3_600_000 if last_ts else 1e9
    if age_h > STALE_HOURS:
        # کهنه: به خنثی برمی‌گردد — وزنِ ساکت، وزنِ اثبات‌شده نیست
        decay = max(0.0, 1.0 - (age_h - STALE_HOURS) / STALE_HOURS)
        w = 1.0 + (w - 1.0) * decay
        note += f" · کهنه ({age_h:.0f}س بی‌رأی) — به خنثی نزدیک شد"
    return round(w, 3), note


def build(now_ms=None, closed_path=None, dom_points=None):
    now_ms = now_ms or time.time() * 1000
    pts = _dom_points() if dom_points is None else dom_points
    path = Path(closed_path) if closed_path else CLOSED
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:                        # noqa: BLE001
                continue
    # دفترِ پیپر، همان‌طور که حمید خواست: امتیاز از پیپرمود می‌آید
    acc = {}          # (room, ctx) → dict
    for r in rows:
        why = r.get("why") or {}
        R = r.get("R")
        ts = r.get("opened") or why.get("sent_at")
        if R is None or not ts:
            continue
        try:
            R = float(R)
        except (TypeError, ValueError):
            continue
        ctx = context_at(ts, pts)
        age_days = (now_ms - float(ts)) / 86_400_000
        if age_days < 0:
            continue
        w_recency = 0.5 ** (age_days / HALF_LIFE_DAYS)
        for room, side in votes_of(why).items():
            credit = side * R
            for key in ((room, ctx), (room, "all")):
                a = acc.setdefault(key, {"raw": [], "wsum": 0.0, "wx": 0.0,
                                         "last": 0, "with": 0, "against": 0})
                a["raw"].append(credit)
                a["wsum"] += w_recency
                a["wx"] += w_recency * credit
                a["last"] = max(a["last"], float(ts))
                a["with" if side > 0 else "against"] += 1
    out = {"generated": int(now_ms), "panel": "لیام تریدر ۹",
           "source": "brain/paper/closed.jsonl — دفتر پیپر",
           "half_life_days": HALF_LIFE_DAYS, "min_n": MIN_N,
           "band": {"exploratory": BAND_EXPLORATORY,
                    "confirmed": BAND_CONFIRMED},
           "rooms": {}}
    for (room, ctx), a in sorted(acc.items()):
        n = len(a["raw"])
        mean_recent = a["wx"] / a["wsum"] if a["wsum"] else 0.0
        ci = _ci95(a["raw"])
        w, note = _weight(mean_recent, n, ci, a["last"], now_ms)
        spec = ROOMS[room]
        out["rooms"].setdefault(room, {
            "engine": spec["engine"], "label": spec["label"],
            "rule": spec["rule"], "by_context": {}})
        out["rooms"][room]["by_context"][ctx] = {
            "n": n, "with": a["with"], "against": a["against"],
            "mean_credit_recent": round(mean_recent, 4),
            "mean_credit_plain": round(sum(a["raw"]) / n, 4) if n else None,
            "ci95": ci, "weight": w, "why": note,
            "last_vote_h": round((now_ms - a["last"]) / 3_600_000, 1)
            if a["last"] else None}
    # اتاق‌های بی‌رأی هم صریح ثبت می‌شوند — سکوت باید دیده شود
    for room, spec in ROOMS.items():
        out["rooms"].setdefault(room, {
            "engine": spec["engine"], "label": spec["label"],
            "rule": spec["rule"], "by_context": {},
            "note": "هیچ رأی ثبت‌شده‌ای در دفتر پیپر ندارد"})
    return out


def weights_for(ctx, data=None, max_age_h=48.0, now_ms=None):
    """وزن هر اتاق برای بسترِ فعلی — همان چیزی که موتور سیگنال می‌خواند.

    قفسهٔ کهنه‌تر از ۴۸ ساعت بی‌اثر است (همان قاعدهٔ قفسهٔ لبه). بسترِ
    خواسته‌شده اگر نمونه نداشت، به `all` برمی‌گردد؛ آن هم نبود → ۱.۰."""
    now_ms = now_ms or time.time() * 1000
    if data is None:
        try:
            data = json.loads(OUT.read_text())
        except Exception:                            # noqa: BLE001
            return {r: 1.0 for r in ROOMS}
    age_h = (now_ms - (data.get("generated") or 0)) / 3_600_000
    if age_h > max_age_h:
        return {r: 1.0 for r in ROOMS}
    res = {}
    for room in ROOMS:
        rec = (data.get("rooms") or {}).get(room) or {}
        by = rec.get("by_context") or {}
        pick = by.get(ctx) or by.get("all")
        res[room] = float((pick or {}).get("weight") or 1.0)
    return res


def main(argv):
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"وزن اتاق‌ها ← {OUT.relative_to(ROOT)}")
    for room, rec in data["rooms"].items():
        by = rec.get("by_context") or {}
        if not by:
            print(f"  {rec['label']}: بی‌رأی")
            continue
        allr = by.get("all") or {}
        line = (f"  {rec['label']} ({rec['engine']}): وزن کل "
                f"{allr.get('weight', 1.0)} · n={allr.get('n', 0)} "
                f"· اعتبار {allr.get('mean_credit_recent')}R")
        print(line)
        for ctx in ("usdtd_down", "usdtd_up", "usdtd_flat"):
            c = by.get(ctx)
            if c and c["n"] >= MIN_N:
                print(f"      {ctx}: وزن {c['weight']} · n={c['n']} "
                      f"· {c['mean_credit_recent']}R · CI={c['ci95']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
