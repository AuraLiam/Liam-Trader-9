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

حتی همان ویژگی‌ها هم در گام ۳ ثانیه‌ای بیش از حد درشت‌اند: ۶ نماد ×
یک ساعت = ~۲.۳ مگابایت، یعنی ~۵۵ مگابایت در روز. سؤالی که این داده باید
جواب بدهد («عمق، شکست واقعی BOS/CHoCH را از کاذب جدا می‌کند؟») روی کندل
۱ و ۳ دقیقه پرسیده می‌شود، پس واحد ذخیره هم **یک دقیقه** است:
`--agg` نمونه‌ها را در سطل‌های دقیقه‌ای جمع می‌بندد و برای هر دقیقه یک
سطر می‌نویسد — قابل join مستقیم با کلاین ۱د. حجم: ~۱ مگابایت در روز
فشرده. نمونهٔ ۳ثانیه‌ای دور ریخته نمی‌شود بلکه **داخل** آمار سطل
می‌ماند (میانگین/کمینه/بیشینه/جمع تغییرها)، پس دینامیک درون-دقیقه هم
حفظ می‌شود.

فایل‌ها روزانه و gzip می‌شوند: `brain/depth/<SYMBOL>-<YYYYMMDD>.m1.jsonl.gz`.
gzip چندعضوی است — هر اجرا یک عضو تازه append می‌کند و خواندن یکپارچه
است (`read_minutes`).

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
import gzip
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

# کشف‌شده در probe روی Actions (۲۲ اوت): مسیر درست همین یکی است — بقیه
# ۴۰۴ واقعی برگرداندند. و خودِ API گفت limit فقط این مقادیر را می‌پذیرد:
#     {"code":10008, "msg":"Parameter 20 does not match,
#      alternative value [\"1\",\"5\",\"15\",\"50\",\"max\"]"}
# یعنی ۲۰ (حدس اولیهٔ من) نامعتبر بود. ۵۰ سطح انتخاب شد: عمیق‌ترین مقدار
# عددی، که برای عدم‌تعادل چندسطحی کافی است بی‌آنکه پاسخ را بی‌جهت بزرگ کند.
DEPTH_PATH = "/api/v1/futures/market/depth?symbol={s}&limit={n}"
DEPTH_LIMIT = 50
VALID_LIMITS = ("1", "5", "15", "50", "max")
LEVELS = (1, 5, 15)          # عمق تجمعی در این تعداد سطح گزارش می‌شود


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


def api_ok(payload):
    """پاسخ ۲۰۰ با کد خطای داخلی، **موفقیت نیست**.

    درس probe اول: هر پنج مسیر HTTP 200 دادند، ولی چهارتا داخلشان
    code=404 داشتند و یکی code=10008 (پارامتر نامعتبر). اگر فقط به کد
    HTTP نگاه می‌کردیم، «همه جواب دادند» گزارش می‌شد."""
    if not isinstance(payload, dict):
        return True, None
    code = payload.get("code")
    if code in (0, "0", None) and payload.get("data") is not None:
        return True, None
    return False, f"code={code} msg={payload.get('msg')!r}"


def probe(symbol="BTCUSDT", limit=DEPTH_LIMIT):
    """هر مسیر نامزد را می‌زند و واقعیت را چاپ می‌کند."""
    print(f"کاوش مسیر عمق روی {BASE} برای {symbol}:\n")
    found = []
    for tmpl in CANDIDATES:
        url = BASE + tmpl.format(s=symbol, n=limit)
        data, err = _get(url)
        if err:
            print(f"  ✗ {tmpl}\n      {err}")
            continue
        ok, why = api_ok(data)
        if not ok:
            print(f"  ✗ {tmpl}\n      پاسخ ۲۰۰ ولی خطای داخلی: {why}")
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


# ── جمع‌بندی دقیقه‌ای ────────────────────────────────────────────────────
BUCKET_MS = 60_000


def bucket_of(t_ms):
    """شروع سطل دقیقه‌ایِ یک زمان — مرز دقیقاً روی مضرب ۶۰ هزار."""
    return (int(t_ms) // BUCKET_MS) * BUCKET_MS


class MinuteAgg:
    """آمار یک دقیقه از عکس‌های ۳ثانیه‌ای یک نماد.

    چرا میانگین **و** کمینه/بیشینه: عدم‌تعادلی که یک لحظه به ۰.۹ می‌رود و
    برمی‌گردد با عدم‌تعادلی که تمام دقیقه ۰.۳ مانده، میانگین نزدیکی دارند
    ولی معنایشان یکی نیست. میانگینِ تنها همان اطلاعاتی را می‌کشد که برای
    جدا کردن شکست واقعی از کاذب لازم است.

    چرا up/dn به‌جای add/cancel: بین دو عکس، لغو از اجرا قابل‌تفکیک نیست
    (قانون ۰۸). اسم فیلد همین را می‌گوید و ادعای بیشتری نمی‌کند.
    """

    def __init__(self, start_ms):
        self.t = start_ms
        self.mid = []
        self.spread = []
        self.micro = []
        self.imb = {n: [] for n in LEVELS}
        self.dbid = {n: [] for n in LEVELS}
        self.dask = {n: [] for n in LEVELS}
        self.depth_b = {n: [] for n in LEVELS}
        self.depth_a = {n: [] for n in LEVELS}
        self.first_t = None
        self.last_t = None
        self.errors = 0

    def add(self, f):
        self.mid.append(f["mid"])
        self.spread.append(f["spread_bps"])
        self.micro.append(f["microprice_dev_bps"])
        for n in LEVELS:
            self.imb[n].append(f[f"imb_{n}"])
            self.depth_b[n].append(f[f"depth_bid_{n}"])
            self.depth_a[n].append(f[f"depth_ask_{n}"])
            if f"d_bid_{n}" in f:
                self.dbid[n].append(f[f"d_bid_{n}"])
                self.dask[n].append(f[f"d_ask_{n}"])
        if self.first_t is None:
            self.first_t = f["t"]
        self.last_t = f["t"]

    def miss(self):
        """یک نمونهٔ ازدست‌رفته در همین سطل (خطای شبکه/API/دفتر خراب)."""
        self.errors += 1

    def close(self):
        """سطل بسته → یک سطر. سطل بی‌نمونه سطر نمی‌سازد (داده‌سازی ممنوع)."""
        if not self.mid:
            return None

        def mean(xs):
            return round(sum(xs) / len(xs), 6) if xs else None
        row = {
            "t": self.t, "n": len(self.mid), "miss": self.errors,
            "span_ms": (self.last_t - self.first_t) if self.first_t else 0,
            "mid_o": self.mid[0], "mid_c": self.mid[-1],
            "mid_h": max(self.mid), "mid_l": min(self.mid),
            "spread_bps_mean": mean(self.spread),
            "spread_bps_max": round(max(self.spread), 4),
            "micro_dev_mean": mean(self.micro),
            "micro_dev_last": self.micro[-1],
        }
        for n in LEVELS:
            v = self.imb[n]
            row[f"imb_mean_{n}"] = mean(v)
            row[f"imb_last_{n}"] = v[-1]
            row[f"imb_min_{n}"] = round(min(v), 5)
            row[f"imb_max_{n}"] = round(max(v), 5)
            row[f"depth_bid_mean_{n}"] = mean(self.depth_b[n])
            row[f"depth_ask_mean_{n}"] = mean(self.depth_a[n])
            # جمع تغییرهای مثبت و منفی جدا — «چقدر آمد» و «چقدر رفت»،
            # نه فقط برایندشان که هر دو را پنهان می‌کند.
            for lab, src in (("bid", self.dbid[n]), ("ask", self.dask[n])):
                row[f"up_{lab}_{n}"] = round(sum(x for x in src if x > 0), 6)
                row[f"dn_{lab}_{n}"] = round(sum(x for x in src if x < 0), 6)
        return row


def _daily_path(symbol, t_ms):
    day = time.strftime("%Y%m%d", time.gmtime(t_ms / 1000))
    return OUTDIR / f"{symbol}-{day}.m1.jsonl.gz"


def write_minute(symbol, row):
    """یک سطر دقیقه‌ای را به فایل روزِ همان سطل append می‌کند.

    gzip چندعضوی: هر باز و بستهٔ فایل یک عضو تازه می‌سازد و خواندن
    یکپارچه باقی می‌ماند — پس اجراهای جدا روی هم انباشته می‌شوند بدون
    اینکه لازم باشد فایل قبلی باز و دوباره فشرده شود."""
    OUTDIR.mkdir(parents=True, exist_ok=True)
    p = _daily_path(symbol, row["t"])
    with gzip.open(p, "at", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def read_minutes(symbol, outdir=None):
    """همهٔ سطرهای دقیقه‌ای یک نماد از تمام روزها، مرتب بر زمان."""
    d = Path(outdir) if outdir else OUTDIR
    rows = []
    for p in sorted(d.glob(f"{symbol}-*.m1.jsonl.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    rows.sort(key=lambda r: r["t"])
    return rows


def snapshot(symbol, path=None, prev=None):
    """یک عکس از دفتر → ویژگی‌ها، یا (None, دلیل). حلقه از این استفاده می‌کند."""
    url = BASE + (path or DEPTH_PATH).format(s=symbol, n=DEPTH_LIMIT)
    data, err = _get(url)
    if err:
        return None, err[:60]
    ok, why = api_ok(data)
    if not ok:
        return None, f"خطای API: {why}"[:60]
    b, a = parse_book(data)
    if not b:
        # «ناشناخته» برای عیب‌یابی بی‌فایده است. ۲۳ اوت ZEC و DASH دقیقاً
        # همین را دادند و بدون دیدن بدنه نمی‌شد فهمید دفتر خالی است یا
        # شکلش فرق دارد. نمونهٔ کوتاهِ خودِ پاسخ به دلیل می‌چسبد.
        raw = json.dumps(data, ensure_ascii=False)[:140]
        return None, f"شکل دفتر ناشناخته — {raw}"
    f = features(b, a, prev)
    if f is None:
        return None, "دفتر متقاطع"
    return f, None


def fold_raw(symbol, outdir=None, remove=False):
    """عکس‌های خامِ `<SYMBOL>.jsonl` را به سطر دقیقه‌ای تا می‌زند.

    برداشت‌های قبل از لایهٔ جمع‌بندی خام نوشته شدند. دادهٔ برداشته‌شده
    دور ریخته نمی‌شود — همان الگوریتم سطلِ حلقه روی فایل اجرا می‌شود تا
    هر دو منبع یک شکل داشته باشند."""
    d = Path(outdir) if outdir else OUTDIR
    src = d / f"{symbol}.jsonl"
    if not src.exists():
        return 0
    rows = []
    with src.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r["t"])
    cur, made = None, 0
    saved, globals()["OUTDIR"] = OUTDIR, d
    try:
        for f in rows:
            b = bucket_of(f["t"])
            if cur is not None and cur.t != b:
                r = cur.close()
                if r:
                    write_minute(symbol, r)
                    made += 1
                cur = None
            if cur is None:
                cur = MinuteAgg(b)
            cur.add(f)
        if cur is not None:
            r = cur.close()
            if r:
                write_minute(symbol, r)
                made += 1
    finally:
        globals()["OUTDIR"] = saved
    if remove:
        src.unlink()
    return made


HEALTH = ROOT / "signals" / "depth-health.json"


def write_health(result, outdir=None):
    """وضعیت برداشت را به‌عنوان **خروجی منتشرشده** می‌نویسد، نه لاگ.

    دو بار امشب دلیلِ نبودن یک نماد فقط داخل لاگ جاب ماند و بازیابی‌اش
    از API لاگ به مشکل خورد (خروجی با فهرست فایل‌های کامیت پر می‌شود).
    چیزی که برای عیب‌یابی لازم است نباید در لاگ زندگی کند — این فایل در
    ریپو می‌نشیند و همیشه در دسترس است."""
    rows = []
    for s in symbols_on_disk(outdir):
        r = read_minutes(s, outdir=outdir)
        if r:
            rows.append({"symbol": s, "minutes": len(r),
                         "first": r[0]["t"], "last": r[-1]["t"],
                         "samples_per_min": round(
                             sum(x["n"] for x in r) / len(r), 2),
                         "missed": sum(x.get("miss", 0) for x in r)})
    payload = {
        "at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "symbols": rows,
        "total_minutes": sum(r["minutes"] for r in rows),
        # همان چیزی که دو بار در لاگ گم شد:
        "rejected": (result or {}).get("rejected", {}),
        "errors": (result or {}).get("errors", {}),
        "endpoint": BASE + DEPTH_PATH, "depth_limit": DEPTH_LIMIT,
        "levels": list(LEVELS)}
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def symbols_on_disk(outdir=None):
    """نمادهایی که فایل دقیقه‌ای دارند — نام نماد خودش خط تیره ندارد."""
    d = Path(outdir) if outdir else OUTDIR
    return sorted({p.name.rsplit("-", 1)[0] for p in d.glob("*.m1.jsonl.gz")})


def stats(outdir=None):
    """گزارش انباشت — چند دقیقه روی هر نماد، از کی تا کی، چگالی نمونه.

    فرضِ «دارد جمع می‌شود» کافی نیست؛ اگر یک نماد از اجرای دوم به بعد
    عقب مانده باشد فقط همین جدول لوش می‌دهد."""
    def fmt(ms):
        return time.strftime("%m-%d %H:%M", time.gmtime(ms / 1000))
    lines = ["| نماد | دقیقه | از | تا | نمونه/دقیقه | ازدست‌رفته |",
             "|---|---|---|---|---|---|"]
    tot = 0
    for s in symbols_on_disk(outdir):
        r = read_minutes(s, outdir=outdir)
        if not r:
            continue
        tot += len(r)
        lines.append(
            f"| {s} | {len(r)} | {fmt(r[0]['t'])} | {fmt(r[-1]['t'])} | "
            f"{sum(x['n'] for x in r) / len(r):.1f} | "
            f"{sum(x.get('miss', 0) for x in r)} |")
    lines.append(f"\nمجموع سطر دقیقه‌ای: **{tot}**")
    return "\n".join(lines), tot


def verify_symbols(symbols, path=None, quiet=False):
    """قبل از شروع حلقه، هر نماد یک بار زده می‌شود → (سالم‌ها، دلیلِ ردها).

    برداشت ۲۲ اوت با ۶ نماد شروع شد و ۴ فایل ساخت. دو نماد **هیچ فایلی
    نساختند** و در گزارش پایانی هم فقط غایب بودند — نه خطایی، نه دلیلی.
    غیبت بی‌دلیل بدترین شکل خرابی است: شبیه «نبود داده» است، در حالی که
    خرابی پیکربندی است. حالا هر نماد اول اعتبارسنجی می‌شود و دلیل ردش
    عیناً چاپ."""
    good, bad = [], {}
    for s in symbols:
        f, why = snapshot(s, path)
        if f is None:
            bad[s] = why
        else:
            good.append(s)
    if not quiet and bad:
        print(f"نمادهای غیرقابل‌برداشت ({len(bad)}) — با دلیل، نه سکوت:")
        for s, why in bad.items():
            print(f"  ✗ {s}: {why}")
    return good, bad


def collect(symbols, minutes=20, interval_s=3.0, depth_path=None, quiet=False,
            agg=True):
    """حلقهٔ برداشت — دفتر خام دور ریخته می‌شود.

    agg=True (پیش‌فرض): یک سطر در هر دقیقه، فشرده و روزانه — همان واحدی
    که تست BOS/CHoCH مصرف می‌کند. agg=False: هر عکس یک سطر خام در
    `<SYMBOL>.jsonl` — فقط برای عیب‌یابی کوتاه، چون در گیت رشد می‌کند."""
    path = depth_path or DEPTH_PATH
    if not path:
        raise RuntimeError("مسیر عمق معلوم نیست — اول --probe را اجرا کن")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    symbols, rejected = verify_symbols(symbols, path, quiet=quiet)
    if not symbols:
        raise RuntimeError(f"هیچ نماد سالمی نماند — دلایل: {rejected}")
    prev, wrote, errs, bins = {}, {}, {}, {}
    end = time.time() + minutes * 60
    while time.time() < end:
        for s in symbols:
            f, why = snapshot(s, path, prev.get(s))
            if f is None:
                errs[why] = errs.get(why, 0) + 1
                if s in bins:
                    bins[s].miss()
                continue
            prev[s] = f
            if not agg:
                with (OUTDIR / f"{s}.jsonl").open("a") as fh:
                    fh.write(json.dumps(f, ensure_ascii=False) + "\n")
                wrote[s] = wrote.get(s, 0) + 1
                continue
            b = bucket_of(f["t"])
            cur = bins.get(s)
            if cur is not None and cur.t != b:
                row = cur.close()
                if row:
                    write_minute(s, row)
                    wrote[s] = wrote.get(s, 0) + 1
                cur = None
            if cur is None:
                cur = bins[s] = MinuteAgg(b)
            cur.add(f)
        time.sleep(interval_s)
    # سطل نیمه‌تمام آخر هم نوشته می‌شود — با n کمتر، که خودش روی سطر پیداست.
    if agg:
        for s, cur in bins.items():
            row = cur.close()
            if row:
                write_minute(s, row)
                wrote[s] = wrote.get(s, 0) + 1
    if not quiet:
        unit = "دقیقه" if agg else "عکس"
        print(f"برداشت تمام شد: {sum(wrote.values())} {unit} روی {len(wrote)} نماد")
        for s, n in sorted(wrote.items(), key=lambda x: -x[1])[:10]:
            print(f"  {s}: {n}")
        if errs:
            print(f"خطاها: {dict(list(errs.items())[:5])}")
        if rejected:
            print(f"نمادهای ردشده پیش از شروع: {rejected}")
    return {"wrote": wrote, "errors": errs, "rejected": rejected}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--minutes", type=float, default=20)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--path", default=None, help="مسیر عمق بعد از کشف")
    ap.add_argument("--raw", action="store_true",
                    help="عکسِ خام به‌جای جمع‌بندی دقیقه‌ای (فقط عیب‌یابی)")
    ap.add_argument("--stats", action="store_true", help="گزارش انباشت")
    ap.add_argument("--fold-raw", action="store_true",
                    help="عکس‌های خام قدیمی را به سطر دقیقه‌ای تا بزن")
    a = ap.parse_args()
    if a.fold_raw:
        for p in sorted(OUTDIR.glob("*.jsonl")):
            n = fold_raw(p.stem, remove=True)
            print(f"  {p.stem}: {n} دقیقه از خام")
        print(stats()[0])
    elif a.stats:
        print(stats()[0])
    elif a.probe:
        probe()
    else:
        res = collect([s.strip() for s in a.symbols.split(",") if s.strip()],
                      minutes=a.minutes, interval_s=a.interval,
                      depth_path=a.path, agg=not a.raw)
        h = write_health(res)
        print(f"سلامت برداشت نوشته شد: {HEALTH.relative_to(ROOT)} "
              f"({h['total_minutes']} دقیقه، {len(h['rejected'])} نماد ردشده)")
