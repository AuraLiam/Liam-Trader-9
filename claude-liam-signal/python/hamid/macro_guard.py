"""محافظ رویداد کلان برای داشبورد — «در ساعت خبر مواظب باش» (دستور حمید، ۱۶ سپتامبر شب).

## شکافی که این فایل می‌بندد

حمید: «ساعت ۹:۳۰ امشب تایم خبری بود، نرخ بهره بود، و باید این را در مسیر
ارتباطی کدی که به داشبورد دادی می‌گذاشتی که در آن ساعت‌ها مواظب باشد.»

ممیزی همان شب: `intel.calendar()` از ۲۷ اوت تقویم اقتصادی را می‌کشد، ولی
مصرف‌کننده‌اش فقط `dominance.py` و `health.py` بودند. **هیچ‌کدام از سه فایل
داشبورد (`liam9_strategy` · `liam9_h1_strategy` · `liam9_shock_strategy`)
حتی یک ارجاع به تقویم نداشتند** (شمارش: صفر). یعنی موتوری که روی بیت‌یونیکس
معامله می‌کند، لحظهٔ اعلام نرخ بهره را از لحظهٔ آرام تشخیص نمی‌داد.

این یک عیبِ کلاس بود نه یک قلم افتاده: هر خوراکی که فقط در ریپو تولید شود و
به `sync_all` وصل نشود، به داشبورد نمی‌رسد. مسیر ارتباطی داشبورد **کشیدنِ
فایل‌های `signals/` است**، پس هر محافظ تازه باید یک فایل قرارداد داشته باشد.

## خروجی

`signals/macro-guard.json` — رویدادهای پراهمیتِ پیشِ رو با ساعت UTC و تهران،
و پنجرهٔ احتیاط. داشبورد با `sync_macro_guard()` می‌کشدش و `macro_window()`
می‌گوید همین حالا داخل پنجره‌ایم یا نه.

## پنجره و اثر (عدد صریح، نه سلیقه)

| قید | مقدار | چرا |
|---|---|---|
| اهمیت | فقط `high` (منبع faireconomy/TradingView) | متوسط و پایین بازار کریپتو را تکان نمی‌دهند |
| شروع پنجره | ۱۲۰ دقیقه پیش از رویداد | همان ≤۲ ساعتی که رأی دامیننس را UNSAFE می‌کند (قانون ۱۵) — یک عدد، دو جا |
| پایان پنجره | ۶۰ دقیقه پس از رویداد | تکانهٔ اعلام معمولاً در همان ساعت اول تخلیه می‌شود |
| اثر بر سایز | ضرب در ۰.۵ | «مواظب باش» = نصف سایز، نه توقف کامل؛ توقف کامل تصمیم حمید است نه این محافظ |
| اثر بر اهرم | بدون تغییر | محافظ لیکویید و سقف داشبورد حاکم مطلق‌اند (قانون ۱۹ اوت بند ۳) |
| کهنگی | فایل کهنه‌تر از ۳ ساعت = بی‌اثر | تقویمِ کهنه بدتر از نبودنش است؛ کهنه شد، محافظ ساکت می‌شود |

## مرز صادقانه

این محافظِ **نوسان** است، نه تفسیر خبر — دقیقاً همان استثنای از-پیش-ثبت‌شدهٔ
قانون ۱۵ («پنجرهٔ رویداد کلان ≤۲س که رأی دامیننس را UNSAFE می‌کند؛ این
محافظِ نوسان است نه تفسیر خبر»). جهت هیچ سیگنالی را عوض نمی‌کند، هیچ خبری
را نمی‌خواند، و هیچ ادعایی دربارهٔ نتیجهٔ رویداد ندارد. ردپای `macro_window`
روی هر خروجی می‌نشیند تا ماشین بونفرونی شبانه بسنجد این احتیاط سود داشت یا
نه — اگر نداشت، با همان CI برداشته می‌شود.

اجرا:  python3 -m hamid.macro_guard [--write] [--json]
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "macro-guard.json"

# همان کلیدهای اتاق دامیننس — یک فهرست، دو مصرف‌کننده (وگرنه دو تعریف از
# «رویداد کلان» داریم و یکی‌شان بی‌صدا کهنه می‌شود).
try:
    from hamid.dominance import MACRO_KEYS
except Exception:                                    # noqa: BLE001
    MACRO_KEYS = ("cpi", "inflation", "unemployment", "nonfarm", "payroll",
                  "fomc", "fed", "rate", "gdp", "ppi")

BEFORE_MIN = 120           # شروع احتیاط پیش از رویداد
AFTER_MIN = 60             # پایان احتیاط پس از رویداد
SIZE_MULT = 0.5            # «مواظب باش» = نصف سایز
MAX_AGE_MIN = 180          # فایل کهنه‌تر از این بی‌اثر است
HORIZON_H = 36             # چند ساعت جلوتر را منتشر کنیم
TEHRAN_OFFSET_MIN = 210    # ایران DST ندارد (UTC+3:30)


def _tehran(ms):
    t = time.gmtime(ms / 1000 + TEHRAN_OFFSET_MIN * 60)
    return time.strftime("%Y-%m-%d %H:%M", t)


def _events(now_ms=None, cal=None):
    """رویدادهای پراهمیت در افق — از همان `intel.calendar()` که اتاق دامیننس
    می‌خواند (یک منبع، دو مصرف‌کننده؛ قانون ۰۵).

    `next_48h` فقط `in_hours` دارد و مهر مطلق ندارد، پس زمانِ مطلق این‌جا از
    `generated + in_hours` ساخته می‌شود. دقتش ±۳ دقیقه است (گرد شدن به ۰.۱
    ساعت) — روی پنجرهٔ ۱۲۰ دقیقه‌ای بی‌اثر، و همین‌جا صریح گفته می‌شود.

    شکست منبع پنهان نمی‌شود: `ok=False` با دلیل برمی‌گردد و داشبورد محافظ را
    خاموش نگه می‌دارد (قانون ۱: بی‌داده، ادعا نه)."""
    now = now_ms or int(time.time() * 1000)
    if cal is None:
        try:
            from hamid import intel
            cal = intel.calendar()
        except Exception as e:                       # noqa: BLE001
            return [], {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    rows = cal.get("next_48h") if isinstance(cal, dict) else cal
    if not isinstance(rows, list):
        return [], {"ok": False, "error": "شکل تقویم ناشناخته — چیزی حدس زده نمی‌شود"}
    out = []
    for e in rows:
        hrs = e.get("in_hours")
        if not isinstance(hrs, (int, float)):
            continue                                 # بی‌زمان = بی‌رویداد (قانون ۱)
        ts = int(now + hrs * 3600_000)
        if hrs > HORIZON_H:
            continue
        title = (e.get("title") or "?")[:90]
        cur = (e.get("country") or e.get("currency") or "?").upper()
        movers = cur == "USD" or any(k in title.lower() for k in MACRO_KEYS)
        out.append({"title": title, "currency": cur, "at": ts,
                    "utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts / 1000)),
                    "tehran": _tehran(ts), "starts_in_min": round(hrs * 60, 1),
                    "market_mover": movers})
    out.sort(key=lambda x: x["at"])
    meta = {"ok": True, "ts_precision_min": 3,
            "ts_note": "زمان مطلق از in_hours ساخته شده (گرد ۰.۱ ساعت)"}
    if isinstance(cal, dict):
        for k in ("cached", "cache_age_min", "source_error", "high_this_week"):
            if cal.get(k) is not None:
                meta[k] = cal[k]
    return out, meta


def window(events, now_ms=None, before=BEFORE_MIN, after=AFTER_MIN):
    """همین حالا داخل پنجرهٔ احتیاطیم؟ → (bool، نزدیک‌ترین رویداد یا None).

    فقط رویدادِ **بازارگردان** پنجره می‌سازد: دلار، یا تیتری که یکی از
    کلیدهای کلان (نرخ بهره، CPI، NFP، FOMC…) را دارد. CPI کانادا بازار
    کریپتو را نمی‌لرزاند و احتیاطِ بی‌دلیل، احتیاط را بی‌اعتبار می‌کند."""
    now = now_ms or int(time.time() * 1000)
    for e in events or []:
        if not e.get("market_mover"):
            continue
        d = (e["at"] - now) / 60000.0
        if -after <= d <= before:
            return True, dict(e, minutes_to_event=round(d, 1))
    return False, None


def build(now_ms=None):
    now = now_ms or int(time.time() * 1000)
    ev, meta = _events(now)
    inside, nearest = window(ev, now)
    return {"generated": now, "panel": "لیام تریدر ۹", "owner": "E05",
            "source_ok": meta.get("ok"), "source": meta,
            "before_min": BEFORE_MIN, "after_min": AFTER_MIN,
            "size_mult": SIZE_MULT, "max_age_min": MAX_AGE_MIN,
            "in_window": inside, "nearest": nearest,
            "events": ev[:12],
            "boundary": ("محافظِ نوسان است نه تفسیر خبر (قانون ۱۵): جهت هیچ "
                         "سیگنالی را عوض نمی‌کند، فقط در پنجرهٔ رویدادِ "
                         "پراهمیت سایز را نصف می‌کند و ردپا می‌گذارد. اهرم و "
                         "محافظ لیکویید دست‌نخورده‌اند. فایل کهنه‌تر از "
                         f"{MAX_AGE_MIN} دقیقه بی‌اثر است.")}


def render(d):
    L = [f"محافظ رویداد کلان — {time.strftime('%H:%M UTC', time.gmtime(d['generated'] / 1000))}"]
    if not d.get("source_ok"):
        L.append(f"  ✗ تقویم نرسید: {(d.get('source') or {}).get('error')} — محافظ خاموش")
        return "\n".join(L)
    if d["in_window"]:
        n = d["nearest"]
        L.append(f"  ⚠️ داخل پنجره: {n['title']} ({n['currency']}) — "
                 f"{n['minutes_to_event']:+.0f} دقیقه · تهران {n['tehran']} · سایز ×{d['size_mult']}")
    else:
        L.append("  ✓ بیرون از پنجره — سایز عادی")
    for e in d["events"][:4]:
        L.append(f"   · {e['tehran']} تهران ({e['utc']} UTC) — {e['title']} [{e['currency']}]")
    return "\n".join(L)


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(list(argv))
    d = build()
    print(json.dumps(d, ensure_ascii=False, indent=1) if a.json else render(d))
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
