"""اسپات در برابر قرارداد دائمی — چقدر فرق می‌کند؟ (دستور حمید، ۳۱ اوت)

حمید: «تأکیدم این بود که بروی توی تریدینگ‌ویو، کریپتو را انتخاب کنی و
بعد ارز را به‌صورت پرپچوال انتخاب کنی.»

## عیبی که ممیزی پیدا کرد

کل تحلیل زنده روی کندل **اسپات** بود: `sources.py` سه صرافی اولش
(MEXC/KuCoin/Binance) همه `api/v3/klines` یعنی اسپات صدا می‌زنند، و
`backtest.py` هم فقط برای BTCDOMUSDT به میزبان فیوچرز می‌رفت. در حالی
که اجرا روی **فیوچرز بیت‌یونیکس** است.

چرا سال‌ها نامرئی ماند: شکل کندلِ فیوچرز بایننس با اسپات مو‌به‌مو یکی
است، پس هیچ لایه‌ای پایین‌دست نمی‌توانست بفهمد کدام را گرفته.

## چرا «فقط عوضش کن» جواب نیست

قیمتِ پرپ با اسپات سه فرق ساختاری دارد:

۱. **پایه (basis)**: پرپ معمولاً چند دهم درصد بالاتر/پایین‌تر معامله
   می‌شود؛ یعنی سطحِ افقیِ یکسان روی دو نمودار دو قیمت است.
۲. **ویکِ لیکوییدیشن**: آبشار لیکوییدیشن فقط در پرپ ویک می‌سازد. و
   استاپِ ما دقیقاً پشتِ همان ویک‌ها می‌نشیند — یعنی این تفاوت مستقیم
   روی نرخِ استاپ‌خوردن اثر دارد.
۳. **حجم**: حجمِ پرپ ابزار دیگری است؛ سنجهٔ «حجم ≥۵× نرمال» که پروفایل
   پامپ رویش بنا شده، روی دو منبع دو عدد می‌دهد.

و مهم‌تر: **کل دفتر تاریخی ما روی اسپات ساخته شده**. عوض‌کردنِ منبع
بدون سنجش، یعنی همهٔ کارنامه‌ها و CIهای موجود به یک بازارِ دیگر ربط
پیدا می‌کنند بی‌آنکه کسی متوجه شود — همان کلاسِ عیبِ «دو تعریف در یک
نمونه» که ۳۰ اوت با کارمزد داشتیم.

پس این فایل **اندازه می‌گیرد**، و سوییچ تصمیم صریح حمید است (قانون ۰۳).

## چه چیزی اندازه گرفته می‌شود

برای هر نماد و تایم‌فریم، روی کندل‌های هم‌زمان:

- **اختلاف قیمت (basis)**: میانه و صدک ۹۰ درصدِ |کلوزِ پرپ − کلوزِ اسپات|
- **اختلاف دامنه**: آیا پرپ ویک بلندتری دارد (نسبتِ دامنه)
- **اختلافِ محلِ استاپ**: مهم‌ترین — سقف/کفِ N کندل اخیر روی دو منبع
  چند درصد فرق دارد؟ این دقیقاً «استاپ من کجا می‌رفت» است.
- **پوشش**: چند نماد اصلاً قرارداد دائمی دارند

اجرا (به شبکه نیاز دارد — روی Actions):
  `python3 -m hamid.perp_vs_spot --symbols 25 --tf 15m --write`
"""
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "perp-vs-spot.json"

SWING_N = 20          # پنجرهٔ سقف/کف که استاپ پشتش می‌نشیند


def _pct(a, b):
    return abs(a - b) / b * 100 if b else None


def compare(sym, tf="15m", limit=200, spot_fn=None, perp_fn=None):
    """یک نماد: اسپات و پرپ را کنار هم می‌گذارد، فقط روی کندل‌های هم‌زمان."""
    import sources
    spot_fn = spot_fn or sources.spot_klines      # نه klines: با سوییچ perp همان پرپ می‌شد
    perp_fn = perp_fn or sources.perp_klines
    try:
        sp = spot_fn(sym, tf, limit)
    except Exception as e:                           # noqa: BLE001
        return {"sym": sym, "ok": False, "why": f"اسپات: {type(e).__name__}"}
    try:
        pp = perp_fn(sym, tf, limit)
    except Exception as e:                           # noqa: BLE001
        return {"sym": sym, "ok": False, "why": f"پرپ ندارد یا نگرفت: {type(e).__name__}"}

    # فقط کندل‌های هم‌زمان — تطبیق بر مهر زمان، نه بر ترتیب
    ps = {int(r[0]): r for r in pp}
    pairs = [(s, ps[int(s[0])]) for s in sp if int(s[0]) in ps]
    if len(pairs) < 30:
        return {"sym": sym, "ok": False,
                "why": f"کندل هم‌زمان کم ({len(pairs)}) — مقایسه بی‌معناست"}

    basis = [_pct(p[4], s[4]) for s, p in pairs]
    rng_s = [(s[2] - s[3]) / s[4] * 100 for s, p in pairs if s[4]]
    rng_p = [(p[2] - p[3]) / p[4] * 100 for s, p in pairs if p[4]]
    # محلِ استاپ: سقف/کف پنجرهٔ اخیر روی هر منبع
    hs = max(s[2] for s, _ in pairs[-SWING_N:])
    hp = max(p[2] for _, p in pairs[-SWING_N:])
    ls = min(s[3] for s, _ in pairs[-SWING_N:])
    lp = min(p[3] for _, p in pairs[-SWING_N:])
    b = sorted(basis)
    return {
        "sym": sym, "ok": True, "bars": len(pairs),
        "basis_med_pct": round(statistics.median(basis), 4),
        "basis_p90_pct": round(b[int(0.9 * (len(b) - 1))], 4),
        "range_med_spot_pct": round(statistics.median(rng_s), 4),
        "range_med_perp_pct": round(statistics.median(rng_p), 4),
        "range_ratio": round(statistics.median(rng_p) / statistics.median(rng_s), 3)
        if statistics.median(rng_s) else None,
        "swing_high_gap_pct": round(_pct(hp, hs), 4),
        "swing_low_gap_pct": round(_pct(lp, ls), 4),
    }


def summarize(rows):
    ok = [r for r in rows if r.get("ok")]
    if not ok:
        return {"n": 0, "why": "هیچ نمادی مقایسه نشد"}
    def med(k):
        v = [r[k] for r in ok if r.get(k) is not None]
        return round(statistics.median(v), 4) if v else None
    return {
        "n": len(ok), "no_perp": len(rows) - len(ok),
        "basis_med_pct": med("basis_med_pct"),
        "basis_p90_pct": med("basis_p90_pct"),
        "range_ratio_med": med("range_ratio"),
        "swing_high_gap_med_pct": med("swing_high_gap_pct"),
        "swing_low_gap_med_pct": med("swing_low_gap_pct"),
    }


def verdict(s, stop_pct_med=0.36):
    """آیا این تفاوت در مقیاسِ استاپِ ماست؟ — تنها سؤالی که اهمیت دارد.

    استاپِ میانهٔ ما ~۰.۳۶٪ است. اگر جابه‌جاییِ سقف/کف بین دو منبع در
    همان مقیاس باشد، یعنی استاپ روی نمودارِ اشتباه گذاشته می‌شود."""
    gap = max(s.get("swing_high_gap_med_pct") or 0,
              s.get("swing_low_gap_med_pct") or 0)
    if not s.get("n"):
        return "بی‌داده — حکمی نیست"
    ratio = gap / stop_pct_med if stop_pct_med else None
    if ratio is None:
        return "نامعلوم"
    if ratio >= 0.5:
        return (f"مهم: جابه‌جایی سقف/کف {gap:.3f}٪ ≈ {ratio:.0%} از استاپِ "
                f"میانهٔ ما — استاپ روی نمودار اشتباه می‌نشیند")
    if ratio >= 0.2:
        return (f"قابل‌توجه: {gap:.3f}٪ ≈ {ratio:.0%} از استاپِ میانه — "
                "روی ستاپ‌های تنگ اثر دارد")
    return (f"کوچک: {gap:.3f}٪ ≈ {ratio:.0%} از استاپِ میانه — "
            "در این نمونه تفاوت در مقیاس استاپ ما نیست")


def main(argv=()):
    import sources
    n_sym = 25
    tf = "15m"
    for i, a in enumerate(argv):
        if a == "--symbols" and i + 1 < len(argv):
            n_sym = int(argv[i + 1])
        if a == "--tf" and i + 1 < len(argv):
            tf = argv[i + 1]
    try:
        syms = sources.top_symbols(n_sym)
    except Exception:                                # noqa: BLE001
        syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"][:n_sym]
    rows = [compare(s, tf) for s in syms]
    s = summarize(rows)
    print(f"### اسپات در برابر قرارداد دائمی — {tf}")
    print(f"  {s.get('n')} نماد مقایسه شد · {s.get('no_perp')} نماد پرپ نداشت/نگرفت")
    print(f"  اختلاف قیمت (basis): میانه {s.get('basis_med_pct')}٪ · "
          f"صدک۹۰ {s.get('basis_p90_pct')}٪")
    print(f"  نسبت دامنهٔ کندل (پرپ ÷ اسپات): {s.get('range_ratio_med')}")
    print(f"  جابه‌جایی سقف {SWING_N} کندله: {s.get('swing_high_gap_med_pct')}٪ · "
          f"کف: {s.get('swing_low_gap_med_pct')}٪")
    print(f"\n  حکم: {verdict(s)}")
    print("\n  مرز: این فقط اندازه‌گیری است. سوییچِ منبعِ تحلیل به پرپ،")
    print("  تصمیم صریح حمید است — کل دفتر تاریخی روی اسپات ساخته شده.")
    if "--write" in argv:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(
            {"generated": int(time.time() * 1000), "tf": tf,
             "summary": s, "verdict": verdict(s), "rows": rows},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n  نوشته شد: {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
