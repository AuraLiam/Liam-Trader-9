"""سنجشِ بازنگر: آیا دامیننسِ هم‌ترازِ تایم‌فریم نتیجه را عوض می‌کند؟

قاعدهٔ گزارش: «هر عدد از اندازه‌گیری قابل‌اجرای دوباره». این فایل همان
اندازه‌گیری است — نه ادعای شفاهی.

## سؤال‌ها

۱. اگر خوانشِ دامیننس را در **تایم‌فریمِ خودِ ستاپ** بگیریم (نه ۱ساعته)،
   سیگنال‌های هم‌جهت با رژیم، نتیجهٔ بهتری داشتند؟
۲. آستانهٔ توزیعی (صدک ۷۵ همان تایم‌فریم) در برابر آستانهٔ ثابت ۰.۱۵ —
   کدام واقعاً چیزی می‌گوید؟
۳. **چرا شورت ضرر می‌دهد؟** تفکیک شورت‌ها بر رژیم دامیننس، ساعت تهران
   و فاصلهٔ استاپ.

## بی‌آینده بودن

برای هر سیگنال فقط نقاطی از سری دامیننس استفاده می‌شود که **مهرشان از
زمان ارسال کوچک‌تر یا مساوی** است. اگر نقطه‌ای در آن لحظه نبوده، سیگنال
از نمونه بیرون می‌رود — جای عددِ نبوده، حدس نمی‌نشیند.

## مرز

خروجی این فایل هیچ دروازه‌ای را عوض نمی‌کند. اگر بازهٔ اطمینان از صفر رد
شد، **پیشنهاد** می‌شود و ورودش به تصمیم تأیید صریح حمید می‌خواهد
(قانون ۰۳/۱۲).

اجرا: `python3 -m hamid.dom_tf_study`
"""
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
SERIES = ROOT / "brain" / "dominance-series.json"
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"

FIXED_THR = 0.15         # آستانهٔ امروزِ premortem — برای مقایسه
TEHRAN_OFFSET_MS = 3.5 * 3600_000


def ci95(xs):
    """میانگین و بازهٔ اطمینان ۹۵٪ — همان روش بقیهٔ سنجه‌ها."""
    n = len(xs)
    if n < 2:
        return (round(statistics.mean(xs), 4) if n else None), None, None, n
    m = statistics.mean(xs)
    se = statistics.stdev(xs) / math.sqrt(n)
    return round(m, 4), round(m - 1.96 * se, 4), round(m + 1.96 * se, 4), n


def _fmt(label, xs):
    m, lo, hi, n = ci95(xs)
    if n < 2:
        return f"  {label:<26} n={n:<4} — نمونه کم"
    verdict = ("بالای صفر" if lo > 0 else "زیر صفر" if hi < 0 else "شامل صفر")
    return f"  {label:<26} n={n:<4} {m:+.4f}R  CI[{lo:+.4f}, {hi:+.4f}]  {verdict}"


def load_signals():
    """معامله‌های بستهٔ برآمده از سیگنالِ واقعاً ارسال‌شده، یکتا."""
    rows = []
    seen = set()
    for line in CLOSED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            r = json.loads(line)
        except Exception:                            # noqa: BLE001
            continue
        why = r.get("why") or {}
        stage = str(why.get("stage") or r.get("stage_tag") or "")
        if not stage.startswith("sig-"):
            continue
        # یکتاسازی بر هویتِ معامله (درس ۲۴ اوت: CI روی ردیف تکراری دروغ است)
        k = (r.get("sym"), r.get("dir"), r.get("opened"), r.get("entry"))
        if k in seen:
            continue
        seen.add(k)
        if r.get("R_net") is None:
            continue
        rows.append(r)
    return rows


def main(argv=()):
    from hamid import dom_tf

    pts = json.loads(SERIES.read_text(encoding="utf-8")).get("points") or []
    pts.sort(key=lambda p: p["t"])
    if not pts:
        print("سری دامیننس خالی است — سنجش انجام نشد")
        return 1
    t_first, t_last = pts[0]["t"], pts[-1]["t"]

    sigs = load_signals()
    inwin = [r for r in sigs if t_first <= (r.get("opened") or 0) <= t_last]
    print(f"دفتر: {len(sigs)} سیگنالِ بستهٔ یکتا · "
          f"{len(inwin)} داخل پنجرهٔ سری دامیننس "
          f"({round((t_last - t_first) / 3600_000, 1)} ساعت)\n")

    # برای هر سیگنال، خوانشِ بی‌آیندهٔ دامیننس در تایم‌فریمِ خودش
    buckets = {}
    rows = []
    for r in inwin:
        t = r["opened"]
        hist = [p for p in pts if p["t"] <= t]
        if len(hist) < 400:
            continue
        tf = r.get("tf") or (r.get("why") or {}).get("tf") or "15m"
        if tf not in dom_tf.TF_MS:
            tf = "15m"
        tfm = {k: {"usdt": dom_tf.read(hist, k, "u")} for k in ("15m", "1h", "4h")}
        ev = dom_tf.for_signal({"tf_map": tfm}, tf, r["dir"])
        u1 = None
        past = [p for p in hist if p["t"] <= t - 3600_000]
        if past:
            u1 = hist[-1]["u"] - past[-1]["u"]
        rows.append((r, ev, u1))

    def add(name, r):
        buckets.setdefault(name, []).append(r["R_net"])

    for r, ev, u1 in rows:
        al = ev.get("aligned")
        add("همه", r)
        add(f"دامیننس هم‌جهت={al}", r)
        add(f"پایهٔ حکم={ev.get('basis')}", r)
        if ev.get("regime"):
            add(f"رژیم {ev['regime']} · {r['dir']}", r)
        if u1 is not None:
            add("آستانهٔ ثابت ۰.۱۵ حرفی داشت"
                if abs(u1) >= FIXED_THR else "آستانهٔ ثابت ۰.۱۵ ساکت بود", r)

    print("### ۱) اثر هم‌ترازی دامیننس در تایم‌فریمِ خودِ ستاپ")
    for k in ("همه", "دامیننس هم‌جهت=True", "دامیننس هم‌جهت=False",
              "دامیننس هم‌جهت=None"):
        if k in buckets:
            print(_fmt(k, buckets[k]))
    tr = buckets.get("دامیننس هم‌جهت=True", [])
    fa = buckets.get("دامیننس هم‌جهت=False", [])
    if len(tr) >= 2 and len(fa) >= 2:
        d = statistics.mean(tr) - statistics.mean(fa)
        se = math.sqrt(statistics.stdev(tr) ** 2 / len(tr)
                       + statistics.stdev(fa) ** 2 / len(fa))
        lo, hi = d - 1.96 * se, d + 1.96 * se
        print(f"\n  اختلاف (هم‌جهت − خلاف): {d:+.4f}R  "
              f"CI[{lo:+.4f}, {hi:+.4f}]  "
              + ("**بالای صفر**" if lo > 0 else "**زیر صفر**" if hi < 0
                 else "شامل صفر — از نویز جدا نیست"))

    print("\n### ۲) آستانهٔ ثابت ۰.۱۵ چقدر اصلاً حرف می‌زند")
    for k in ("آستانهٔ ثابت ۰.۱۵ حرفی داشت", "آستانهٔ ثابت ۰.۱۵ ساکت بود"):
        if k in buckets:
            print(_fmt(k, buckets[k]))

    print("\n### ۳) چرا شورت ضرر می‌دهد — تفکیک")
    shorts = [(r, ev, u1) for r, ev, u1 in rows if r["dir"] == "SHORT"]
    longs = [(r, ev, u1) for r, ev, u1 in rows if r["dir"] == "LONG"]
    print(_fmt("LONG", [r["R_net"] for r, _, _ in longs]))
    print(_fmt("SHORT", [r["R_net"] for r, _, _ in shorts]))
    print()
    for reg in ("BULLISH", "BEARISH", "RANGE"):
        xs = [r["R_net"] for r, ev, _ in shorts if ev.get("regime") == reg]
        if xs:
            print(_fmt(f"SHORT · رژیم {reg}", xs))
    print()
    # فاصلهٔ استاپ: کارمزد سهمِ ثابتی از R نیست — استاپ تنگ، کارمزدخوار است
    def stop_pct(r):
        try:
            return abs(r["entry"] - r["sl"]) / r["entry"] * 100
        except Exception:                            # noqa: BLE001
            return None
    for lo_p, hi_p in ((0, 1.0), (1.0, 2.0), (2.0, 99)):
        xs = [r["R_net"] for r, _, _ in shorts
              if (sp := stop_pct(r)) is not None and lo_p <= sp < hi_p]
        if xs:
            print(_fmt(f"SHORT · استاپ {lo_p:g}–{hi_p:g}٪", xs))
    print()
    for lo_h, hi_h, name in ((0, 8, "۰۰–۰۸ تهران"), (8, 16, "۰۸–۱۶ تهران"),
                             (16, 24, "۱۶–۲۴ تهران")):
        xs = [r["R_net"] for r, _, _ in shorts
              if lo_h <= ((r["opened"] + TEHRAN_OFFSET_MS) // 3600_000) % 24 < hi_h]
        if xs:
            print(_fmt(f"SHORT · {name}", xs))

    print("\n### مرز صادقانه")
    print("  هیچ‌کدام از این اعداد تا وقتی CI از صفر رد نشده و حمید تأیید")
    print("  نکرده، دروازه نمی‌شود (قانون ۰۳). خوانش دامیننسِ هم‌تراز از")
    print("  امشب فقط روی پروندهٔ هر سیگنال ثبت می‌شود.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
