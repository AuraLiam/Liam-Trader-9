"""انتخاب ۳۰ ارز پرنوسانِ **قابل‌معامله** — دستور حمید (۲۲ اوت).

«۳۰ ارز برتر رو انتخاب کن که بیشترین نوسان رو داشته.»

نکته‌ای که بک‌تست‌های ۲۲ اوت با عدد نشان دادند و این ماژول بر پایه‌اش
ساخته شده: «پرنوسان‌ترین» به‌تنهایی معیار غلطی است. اسکلپ ساختاریِ ۱-۳
دقیقه فقط در یک **نوار** زیست‌پذیر است:

  • نوسانِ خیلی کم  → استاپ ساختاری چنان تنگ می‌شود که کارمزد سهم بزرگی
    از R را می‌خورد → دام کارمزد.
  • نوسانِ خیلی زیاد → استاپ از سقف ریسک اسکلپ رد می‌شود → یا سیگنال
    صادر نمی‌شود، یا با استاپِ بیش‌ازحد پهن صادر می‌شود که با اهرم بالا
    خطرناک است.

پس رتبه‌بندی این‌جا «بیشترین ATR» نیست؛ **بیشترین ATR داخل نوار مجاز**
است. ارزی که از سقف نوار رد شده حذف می‌شود، نه اینکه چون پرنوسان‌تر است
اول لیست بیاید.

نقدشوندگی هم دروازهٔ سخت است: با اهرم ۱۰-۱۵ ورود به بازارِ کم‌عمق یعنی
لغزشی که کل لبه را می‌خورد. پس اول حجم، بعد نوسان.

خروجی: signals/volatile-universe.json
اجرا:  python3 -m hamid.volatility_universe --n 30
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "signals" / "volatile-universe.json"

# نوار زیست‌پذیری بر حسب ATR٪ هر کندل (اندازه‌گیری‌شدهٔ ۲۲ اوت روی همین
# موتور). این‌ها پیش‌فرضِ کاری‌اند نه حقیقت ابدی — بک‌تست می‌تواند
# جابه‌جاشان کند، ولی نه با حدس.
BAND = {"1m": (0.13, 0.40), "3m": (0.22, 0.70)}
LIQ_POOL = 120          # از این تعداد نمادِ پرحجم شروع می‌کنیم
MIN_BARS = 120


def atr_pct(cd, n=14):
    """ATR بر حسب درصد قیمت — تنها شکلی که بین نمادها قابل‌مقایسه است."""
    if len(cd) < n + 1:
        return None
    tr = []
    for i in range(len(cd) - n, len(cd)):
        h, l, pc = cd[i]["h"], cd[i]["l"], cd[i - 1]["c"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(tr) / len(tr)
    px = cd[-1]["c"]
    return (a / px * 100) if px > 0 else None


def build(n=30, tf="3m", pool=LIQ_POOL, bars=200, quiet=False, offset=0):
    import sources
    from hamid.scenario_backtest import resample, _cd
    lo, hi = BAND[tf]
    try:
        syms = sources.top_symbols(pool)
    except Exception:                                  # noqa: BLE001
        from hamid.trainer import top_symbols
        syms = top_symbols(pool)

    rows, drops = [], {}
    for rank, s in enumerate(syms, 1):
        try:
            c1 = _cd(sources.klines(s, "1m", bars))
        except Exception as e:                         # noqa: BLE001
            drops[type(e).__name__] = drops.get(type(e).__name__, 0) + 1
            continue
        cd = resample(c1, int(tf.replace("m", "")))
        if len(cd) < MIN_BARS // int(tf.replace("m", "")):
            drops["سری کوتاه"] = drops.get("سری کوتاه", 0) + 1
            continue
        a = atr_pct(cd)
        if a is None:
            drops["ATR نامعتبر"] = drops.get("ATR نامعتبر", 0) + 1
            continue
        rows.append({"sym": s, "liq_rank": rank, "atr_pct": round(a, 4),
                     "in_band": lo <= a <= hi})
        if not quiet and rank % 20 == 0:
            print(f"  {rank}/{len(syms)} بررسی شد", flush=True)

    in_band = [r for r in rows if r["in_band"]]
    # داخل نوار، پرنوسان‌ترین اول — چون همان‌ها بیشترین فرصت را می‌سازند
    # بدون اینکه از سقف ریسک رد شوند.
    in_band.sort(key=lambda r: -r["atr_pct"])
    # offset: نمونهٔ نمادیِ **مستقل**. برای تأیید یک فرضیه، دوباره برش‌زدن
    # همان نمونه بی‌فایده است؛ نمادهای رتبهٔ n+1 تا 2n یک آزمون واقعاً جدا
    # می‌دهند (قانون CI + تصحیح چندآزمونی).
    picked = in_band[offset:offset + n]
    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "tf": tf, "band_atr_pct": {"min": lo, "max": hi},
           "pool_scanned": len(rows), "in_band": len(in_band),
           "too_quiet": sum(1 for r in rows if r["atr_pct"] < lo),
           "too_wild": sum(1 for r in rows if r["atr_pct"] > hi),
           "drop_reasons": drops,
           "offset": offset,
           "symbols": [r["sym"] for r in picked],
           "detail": picked,
           "note": ("رتبه = پرنوسان‌ترینِ *داخل نوار مجاز*، نه پرنوسان‌ترینِ مطلق. "
                    "بیرونِ نوار یعنی یا دام کارمزد یا استاپِ بیش‌ازحد پهن.")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        print(f"\nاز {len(rows)} نماد: {len(in_band)} داخل نوار · "
              f"{res['too_quiet']} خیلی آرام · {res['too_wild']} خیلی وحشی")
        for r in picked[:10]:
            print(f"  {r['sym']:<14} ATR {r['atr_pct']:.3f}٪  (رتبهٔ حجم {r['liq_rank']})")
        print(f"نوشته شد: {OUT}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--tf", default="3m", choices=list(BAND))
    ap.add_argument("--pool", type=int, default=LIQ_POOL)
    ap.add_argument("--offset", type=int, default=0)
    a = ap.parse_args()
    build(n=a.n, tf=a.tf, pool=a.pool, offset=a.offset)
