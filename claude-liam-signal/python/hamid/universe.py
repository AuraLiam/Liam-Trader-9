"""Universe Engine (E01) — سند AuraLiam369 §5، فاز ۱.

هر روز یک Snapshot مستقل از ۲۰۰ نماد برتر ساخته می‌شود:
· رتبه بر اساس حجم معاملات (نزدیک‌ترین معیار نقدشوندگیِ در دسترس؛
  Market Cap صرافی‌محور نداریم — همین صادقانه ثبت می‌شود)
· حذف استیبل‌کوین‌ها و Wrappedهای تکراری
· ثبت venue (کدام صرافی جواب داد)
· دیف با Snapshot قبلی: لیست‌شده‌ها و حذف‌شده‌ها
· فایل یکتای روزانه brain/universe/YYYY-MM-DD.json — append-only،
  ضد survivorship bias (اعضای همان روز برای همیشه می‌مانند) و ضد تصادم
  (دو ورک‌فلو هرگز روی یک فایل نمی‌نویسند؛ اولین نویسندهٔ روز برنده است)
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
UNI_DIR = ROOT / "brain" / "universe"

STABLES = {"USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDD", "PYUSD",
           "EUR", "EURI", "USDE", "FDUSD", "GUSD", "LUSD", "USD1", "XUSD",
           "RLUSD", "AEUR", "USDF", "USR", "USDX"}
WRAPPED = {"WBTC", "WETH", "WBNB", "WSOL", "STETH", "WSTETH", "CBBTC", "CBETH",
           "RETH", "WEETH"}

# ── شناسایی ارز: مشتق، نه فهرستِ دست‌نویس (دستور حمید، ۶ سپتامبر) ──────────
#
# حمید: «باید تو شناسایی ارزها دقت بیشتری بکنی.» علت، نه حادثه: دو فهرستِ
# بالا دست‌نویس‌اند، پس هر گونهٔ تازه باید یادِ کسی بماند. اندازه‌گیریِ همان
# روز روی ۴۴۰ سیگنالِ ارسالی نشان داد چه چیزی از لایشان رد شده:
#   WBETHUSDT×۱ — چون `WETH` در فهرست هست ولی `WBETH` نبود
#   USD1USDT×۱  — پیش از افزوده‌شدنِ USD1 به فهرست
#   XAUT×۱۴ + PAXG×۱۰ — طلای توکنی، در هیچ فهرستی نبود
#
# همان کلاسی که ۶ سپتامبر ثبت شد: «فهرستِ دست‌نویس، خودش یک علت است.»
# درمان، اضافه‌کردن سه ردیفِ دیگر نیست — مشتق‌کردنِ کلاس از خودِ نماد است.
# فهرست‌ها می‌مانند، ولی فقط به‌عنوان پشت‌بند.

_FIAT = {"EUR", "GBP", "JPY", "TRY", "BRL", "ARS", "AUD", "ZAR"}
_MAJORS = ("BTC", "ETH", "BNB", "SOL")
# پیشوندهای رپینگ/استیکینگ. عمداً کوتاه و بسته: پسوند باید **خودش** یکی از
# چهار مِیجر باشد، وگرنه هر نمادی که تصادفاً با B یا W شروع شود قربانی
# می‌شود. آزمون‌شده روی نمادهای واقعی: WIF · BCH · STX · RENDER · BONK ·
# WLD هیچ‌کدام نمی‌افتند، چون بعد از برداشتنِ پیشوند مِیجر نمی‌مانَد.
_WRAP_PREFIX = ("W", "B", "R", "S", "M", "L", "WB", "WST", "ST", "CB", "BN",
                "SOLV", "LS", "RS")


def is_stable(base):
    """استیبل/فیات — مشتق از خودِ نام، نه فهرست."""
    b = (base or "").upper()
    return b in STABLES or b in _FIAT or "USD" in b


def is_wrapped(base):
    """رپد یا استیکِ یکی از چهار مِیجر — یعنی تکرارِ همان دارایی."""
    b = (base or "").upper()
    if b in WRAPPED:
        return True
    if b in _MAJORS:                       # خودِ مِیجر رپد نیست
        return False
    for m in _MAJORS:
        if b.endswith(m) and b[: -len(m)] in _WRAP_PREFIX:
            return True
    return False


def is_commodity(base):
    """کالای توکنی (طلا/نقره). ممنوع نیست — فقط کلاسش فرق دارد."""
    b = (base or "").upper()
    return b in {"XAUT", "PAXG", "XAGX"} or b.startswith(("XAU", "XAG"))


def sym_class(sym):
    """کلاسِ نماد: crypto | stable | wrapped | commodity.

    روی هر سیگنال ثبت می‌شود تا ماشین شبانه بتواند بسنجد هر کلاس چقدر
    می‌ارزد — به‌جای این‌که کسی از روی حدس کلاسی را ببندد (قانون ۰۳).
    """
    b = _base(str(sym or "").upper())
    if is_stable(b):
        return "stable"
    if is_wrapped(b):
        return "wrapped"
    if is_commodity(b):
        return "commodity"
    return "crypto"


def structureless(sym):
    """نمادی که ساختارِ قابل‌معامله ندارد — استیبل یا تکرارِ یک مِیجر.

    کالا این‌جا نیست: طلا ساختار دارد؛ مسئله‌اش بسترِ BTC است نه ساختار.
    """
    return sym_class(sym) in ("stable", "wrapped")


def _base(sym):
    return sym[:-4] if sym.endswith("USDT") else sym


def build_snapshot(rows, venue, top=200):
    """از ردیف‌های تیکر، Snapshot امروز — خالص و تست‌پذیر."""
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: -float(x.get("quoteVolume") or 0)):
        s = str(r.get("symbol") or "")
        if not s.endswith("USDT"):
            continue
        b = _base(s)
        if b in STABLES or b in WRAPPED or b in seen:
            continue
        seen.add(b)
        out.append({"symbol": s, "quote_vol": round(float(r.get("quoteVolume") or 0))})
        if len(out) >= top:
            break
    return {"date": time.strftime("%Y-%m-%d", time.gmtime()),
            "generated": int(time.time() * 1000),
            "venue": venue,
            "rank_metric": "quoteVolume 24h (نه Market Cap — در دسترس نیست)",
            "n": len(out), "members": out}


def _latest_before(date):
    if not UNI_DIR.exists():
        return None
    older = sorted(p.stem for p in UNI_DIR.glob("*.json") if p.stem < date)
    if not older:
        return None
    try:
        return json.loads((UNI_DIR / f"{older[-1]}.json").read_text())
    except Exception:                                # noqa: BLE001
        return None


def daily(rows=None, venue=None, top=200):
    """Snapshot امروز را بساز اگر هنوز ساخته نشده — ایمن برای فراخوانی مکرر.

    برگشتی: (snapshot, created, diff) — diff فقط وقتی snapshot قبلی هست."""
    date = time.strftime("%Y-%m-%d", time.gmtime())
    path = UNI_DIR / f"{date}.json"
    if path.exists():                                # اولین نویسندهٔ روز برنده است
        try:
            return json.loads(path.read_text()), False, None
        except Exception:                            # noqa: BLE001
            return None, False, None
    if rows is None:
        import sources
        rows = sources.tickers()
        venue = venue or sources.used().get("tickers")
    snap = build_snapshot(rows, venue, top=top)
    prev = _latest_before(date)
    diff = None
    if prev:
        cur = {m["symbol"] for m in snap["members"]}
        old = {m["symbol"] for m in prev.get("members", [])}
        diff = {"listed": sorted(cur - old), "dropped": sorted(old - cur),
                "vs": prev.get("date")}
        snap["diff"] = diff
    UNI_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1))
    return snap, True, diff
