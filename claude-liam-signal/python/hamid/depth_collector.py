"""جمع‌آوری عمق دفتر سفارش بیت‌یونیکس — پیش‌نیاز فعال‌شدن E10.

دستور حمید (۲۲ اوت): «همین دیتای عمق بیت‌یونیکس رو هم راه بنداز.»

## چرا این فایل وجود دارد

سه بک‌تست ۲۲ اوت نشان دادند BOS/CHoCH روی ۱-۳ دقیقه **با کندلِ تنها**
شکست واقعی را از کاذب جدا نمی‌کند (تأیید خارج از نمونه: هر ۱۲ خانه CI
کاملاً زیر صفر). چیزی که این دو را جدا می‌کند در کندل نیست — در عمق دفتر
و جریان سفارش است. قانون ۰۸ هم صریح گفته بود: «با کندل نمی‌شود cancel،
صف، پایداری دیوار و سوییپ را اعتبارسنجی کرد.» پس تا این داده جمع نشود،
E10 حق ندارد ادعایی بکند — و همان‌طور هم خاموش نگه داشته شده بود.

## چه چیزی ذخیره می‌شود (و چه چیزی نه)

دفترِ خام ذخیره **نمی‌شود** — حجمش در گیت غیرقابل‌مدیریت است و قانون ۰۵
هم دادهٔ runtime را در commit نمی‌خواهد. به‌جایش، در همان لحظهٔ برداشت
**ویژگی‌های E10** حساب و فقط آن‌ها نگه داشته می‌شوند: اسپرد، میدپرایس،
میکروپرایس، عمق تجمعی چند سطح، عدم‌تعادل صف، و بین دو عکس متوالی
تغییرات (پایهٔ OFI) و بازپرشدن.

## مرزهای صادقانه — بخوان قبل از اینکه به این داده تکیه کنی

۱. **این نمونه‌برداری REST است، نه استریم tick.** OFI واقعی به جریان
   رویدادِ دفتر نیاز دارد. آنچه این‌جا حساب می‌شود «تغییر بین دو عکس»
   است که تقریبِ درشتِ OFI است. اسمش را هم عوض نکردم تا کسی اشتباه
   نگیرد: فیلدها `d_*` نام دارند نه `ofi`.
۲. **cancel و replace دیده نمی‌شوند.** بین دو عکس، لغو و اجرا از هم
   قابل‌تفکیک نیستند. هر ادعایی دربارهٔ spoofing با این داده ناممکن است
   (قانون ۰۸: `SPOOF_LIKE_RISK`، نه «اثبات شد»).
۳. تا وقتی حجم داده به اندازهٔ کافی نرسیده، هیچ ویژگی‌ای وارد دروازهٔ
   سیگنال نمی‌شود — همان چرخهٔ قانون ۰۳.

## کشف مسیر API

مسیر دقیق endpoint عمق از سند رسمی تأیید نشده. به‌جای حدس‌زدن، حالت
`--probe` چند مسیر نامزد را می‌زند و **کد وضعیت و بدنهٔ واقعی** هر کدام
را چاپ می‌کند (درس ۲۲ اوت: خطای بی‌جزئیات یعنی هیچ). اولین اجرا روی
Actions شکل واقعی را معلوم می‌کند، بعد مسیر درست ثابت می‌شود.

خروجی: brain/depth/<SYMBOL>.jsonl  (ویژگی‌ها، append-only)
اجرا:  python3 -m hamid.depth_collector --probe
       python3 -m hamid.depth_collector --symbols BTCUSDT,ETHUSDT --minutes 20
"""
import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTDIR = ROOT / "brain" / "depth"
BASE = "https://fapi.bitunix.com"
UA = {"User-Agent": "liam9-depth/1.0", "Accept": "application/json"}

# نامزدهای مسیر عمق — حالت probe واقعیت را معلوم می‌کند، نه حدس.
CANDIDATES = [
    "/api/v1/futures/market/depth?symbol={s}&limit={n}",
    "/api/v1/futures/market/depth?symbol={s}&precision=0&limit={n}",
    "/api/v1/futures/market/order_book?symbol={s}&limit={n}",
    "/api/v1/futures/market/books?symbol={s}&limit={n}",
    "/api/v1/futures/market/depth/{s}?limit={n}",
]
DEPTH_PATH = None            # بعد از probe این‌جا ثابت می‌شود
LEVELS = (1, 5, 10)          # عمق تجمعی در این تعداد سطح گزارش می‌شود


def _get(url, timeout=12):
    """خطا هرگز بی‌جزئیات نیست — کد وضعیت و بدنه به پیام می‌چسبند."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:                              # noqa: BLE001
            pass
        return None, f"HTTP {e.code} {e.reason} — {body!r}"
    except Exception as e:                             # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def probe(symbol="BTCUSDT", limit=20):
    """هر مسیر نامزد را می‌زند و واقعیت را چاپ می‌کند."""
    print(f"کاوش مسیر عمق روی {BASE} برای {symbol}:\n")
    found = []
    for tmpl in CANDIDATES:
        url = BASE + tmpl.format(s=symbol, n=limit)
        data, err = _get(url)
        if err:
            print(f"  ✗ {tmpl}\n      {err}")
            continue
        keys = list(data)[:8] if isinstance(data, dict) else f"list[{len(data)}]"
        print(f"  ✓ {tmpl}\n      کلیدها: {keys}")
        print(f"      نمونه: {json.dumps(data, ensure_ascii=False)[:400]}")
        found.append((tmpl, data))
    if not found:
        print("\nهیچ مسیری جواب نداد — یا مسدودیت شبکه، یا هیچ‌کدام از "
              "نامزدها درست نیست. بدنهٔ خطاها بالا هست.")
    return found


def parse_book(payload):
    """دفتر را از هر پوششی که آمده بیرون می‌کشد → (bids, asks) نزولی/صعودی.

    شکل واقعی بعد از probe قطعی می‌شود؛ فعلاً پوشش‌های رایج پوشش داده
    شده‌اند و هر شکل ناشناخته صریحاً None برمی‌گرداند، نه حدس."""
    d = payload
    for k in ("data", "result"):
        if isinstance(d, dict) and isinstance(d.get(k), (dict, list)):
            d = d[k]
    if not isinstance(d, dict):
        return None, None
    bids = d.get("bids") or d.get("b") or d.get("buy")
    asks = d.get("asks") or d.get("a") or d.get("sell")
    if not isinstance(bids, list) or not isinstance(asks, list):
        return None, None

    def norm(rows):
        out = []
        for r in rows:
            if isinstance(r, dict):
                p, q = r.get("price") or r.get("p"), r.get("qty") or r.get("q")
            elif isinstance(r, (list, tuple)) and len(r) >= 2:
                p, q = r[0], r[1]
            else:
                continue
            try:
                out.append((float(p), float(q)))
            except (TypeError, ValueError):
                continue
        return out
    b, a = norm(bids), norm(asks)
    if not b or not a:
        return None, None
    b.sort(key=lambda x: -x[0])
    a.sort(key=lambda x: x[0])
    return b, a


def features(bids, asks, prev=None, now_ms=None):
    """ویژگی‌های E10 از یک عکس دفتر — و در صورت وجود عکس قبلی، تغییرها.

    هیچ‌کدام از این‌ها OFI واقعی نیست (به جریان رویداد نیاز دارد)؛ نام
    فیلدها با d_ شروع می‌شود تا همین تمایز در خودِ داده بماند."""
    best_bid, best_ask = bids[0][0], asks[0][0]
    if best_ask <= best_bid:
        return None                        # دفتر متقاطع = دادهٔ خراب
    mid = (best_bid + best_ask) / 2
    spread = best_ask - best_bid
    qb, qa = bids[0][1], asks[0][1]
    micro = (best_bid * qa + best_ask * qb) / (qa + qb) if (qa + qb) > 0 else mid
    f = {"t": now_ms or int(time.time() * 1000),
         "mid": round(mid, 10), "spread_bps": round(spread / mid * 10000, 4),
         "microprice_dev_bps": round((micro - mid) / mid * 10000, 4)}
    for n in LEVELS:
        sb = sum(q for _, q in bids[:n])
        sa = sum(q for _, q in asks[:n])
        tot = sb + sa
        f[f"depth_bid_{n}"] = round(sb, 6)
        f[f"depth_ask_{n}"] = round(sa, 6)
        f[f"imb_{n}"] = round((sb - sa) / tot, 5) if tot > 0 else 0.0
    if prev:
        dt = max(1, f["t"] - prev["t"])
        f["dt_ms"] = dt
        for n in LEVELS:
            f[f"d_bid_{n}"] = round(f[f"depth_bid_{n}"] - prev.get(f"depth_bid_{n}", 0), 6)
            f[f"d_ask_{n}"] = round(f[f"depth_ask_{n}"] - prev.get(f"depth_ask_{n}", 0), 6)
        f["d_mid_bps"] = round((f["mid"] - prev["mid"]) / prev["mid"] * 10000, 4)
    return f


def collect(symbols, minutes=20, interval_s=3.0, depth_path=None, quiet=False):
    """حلقهٔ برداشت — ویژگی‌ها را append می‌کند، دفتر خام را دور می‌ریزد."""
    path = depth_path or DEPTH_PATH
    if not path:
        raise RuntimeError("مسیر عمق معلوم نیست — اول --probe را اجرا کن")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    prev, wrote, errs = {}, {}, {}
    end = time.time() + minutes * 60
    while time.time() < end:
        for s in symbols:
            url = BASE + path.format(s=s, n=20)
            data, err = _get(url)
            if err:
                errs[err[:60]] = errs.get(err[:60], 0) + 1
                continue
            b, a = parse_book(data)
            if not b:
                errs["شکل دفتر ناشناخته"] = errs.get("شکل دفتر ناشناخته", 0) + 1
                continue
            f = features(b, a, prev.get(s))
            if f is None:
                errs["دفتر متقاطع"] = errs.get("دفتر متقاطع", 0) + 1
                continue
            prev[s] = f
            with (OUTDIR / f"{s}.jsonl").open("a") as fh:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
            wrote[s] = wrote.get(s, 0) + 1
        time.sleep(interval_s)
    if not quiet:
        print(f"برداشت تمام شد: {sum(wrote.values())} عکس روی {len(wrote)} نماد")
        for s, n in sorted(wrote.items(), key=lambda x: -x[1])[:10]:
            print(f"  {s}: {n}")
        if errs:
            print(f"خطاها: {dict(list(errs.items())[:5])}")
    return {"wrote": wrote, "errors": errs}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--minutes", type=float, default=20)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--path", default=None, help="مسیر عمق بعد از کشف")
    a = ap.parse_args()
    if a.probe:
        probe()
    else:
        collect([s.strip() for s in a.symbols.split(",") if s.strip()],
                minutes=a.minutes, interval_s=a.interval, depth_path=a.path)
