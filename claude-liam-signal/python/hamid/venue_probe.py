"""کاوش عمومی یک صرافی نامزد — بدون کلید، بدون حدس.

## پرسش حمید (۲۳ اوت)

«کارمزد KCEX را ببین، شاید جابه‌جا شویم؛ برای اسکلپ منطقی است.» و بعد:
«می‌خوای API بگیرم؟»

**کلید لازم نیست.** آنچه تصمیم را عوض می‌کند عمومی است: مشخصات قرارداد
(کارمزد پیش‌فرض، tick size، حداقل سایز) و عمق دفتر. کلید فقط برای
معامله و موجودی است و `LIVE_EXECUTION=false` است. کلیدِ لازم‌نداشته
نگرفتن، خودش یک اقدام امنیتی است (قانون ۰۵: secret فقط در محیط امن).

## چیزی که واقعاً باید سنجیده شود

کارمزدِ کمتر نصف ماجراست. نصف دیگر **لغزش** است، و لغزش با عوض کردن
صرافی کم نمی‌شود — صرافی کوچک‌تر معمولاً عمق کمتری دارد، پس ممکن است
کارمزدِ کمتر را کامل خنثی کند. تنها راه صادقانه، مقایسهٔ **اسپرد و عمق
واقعی روی همان نمادها در همان لحظه** است. این فایل همان را می‌گیرد.

## حدس ممنوع (درس ۲۲ اوت)

مسیر API از سند رسمی تأیید نشده. `--probe` چند مسیر نامزد را می‌زند و
**کد وضعیت و بدنهٔ واقعی** هرکدام را چاپ می‌کند. همان درسِ probe عمق:
پاسخ ۲۰۰ با کد خطای داخلی موفقیت نیست.

اجرا:  python3 -m hamid.venue_probe --probe
       python3 -m hamid.venue_probe --compare BTCUSDT,ETHUSDT,SOLUSDT
"""
import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "venue-compare.json"

UA = {"User-Agent": "liam9-venue/1.0", "Accept": "application/json"}

# نامزدهای مسیر — KCEX از خانوادهٔ رابط‌های MEXC-مانند است، ولی هیچ‌کدام
# فرض نمی‌شود؛ probe واقعیت را چاپ می‌کند.
KCEX_HOSTS = ["https://api.kcex.com", "https://contract.kcex.com",
              "https://www.kcex.com"]
KCEX_CONTRACT_PATHS = [
    "/api/v1/contract/detail",
    "/api/platform/asset/futures/contract/list",
    "/open/api/v1/contract/detail",
    "/api/v1/contract/ticker",
]
KCEX_DEPTH_PATHS = [
    "/api/v1/contract/depth/{s}",
    "/api/v1/contract/depth?symbol={s}",
    "/open/api/v1/contract/depth/{s}",
]


def _get(url, timeout=15):
    """خطا هرگز بی‌جزئیات نیست — کد وضعیت و بدنه به پیام می‌چسبند."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return json.loads(raw), None
            except json.JSONDecodeError:
                return None, f"HTTP {r.status} ولی JSON نبود: {raw[:160]!r}"
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:                              # noqa: BLE001
            pass
        return None, f"HTTP {e.code} {e.reason} — {body!r}"
    except Exception as e:                             # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def ok_payload(p):
    """پاسخ ۲۰۰ با کد خطای داخلی موفقیت نیست (درس probe عمق بیت‌یونیکس)."""
    if not isinstance(p, dict):
        return isinstance(p, list) and bool(p), None
    if p.get("success") is False:
        return False, f"success=false msg={p.get('message') or p.get('msg')!r}"
    code = p.get("code")
    if code not in (0, 200, "0", "200", None):
        return False, f"code={code} msg={p.get('msg') or p.get('message')!r}"
    if p.get("data") in (None, [], {}) and "bids" not in p and "asks" not in p:
        return False, "بدنه خالی است"
    return True, None


def probe(symbol="BTC_USDT"):
    """هر ترکیب میزبان×مسیر را می‌زند و واقعیت را چاپ می‌کند."""
    found = {"contract": [], "depth": []}
    print("── مشخصات قرارداد ──")
    for host in KCEX_HOSTS:
        for path in KCEX_CONTRACT_PATHS:
            url = host + path
            data, err = _get(url)
            if err:
                print(f"  ✗ {url}\n      {err}")
                continue
            good, why = ok_payload(data)
            if not good:
                print(f"  ✗ {url}\n      پاسخ آمد ولی: {why}")
                continue
            print(f"  ✓ {url}")
            print(f"      {json.dumps(data, ensure_ascii=False)[:300]}")
            found["contract"].append(url)
    print("\n── عمق دفتر ──")
    for host in KCEX_HOSTS:
        for path in KCEX_DEPTH_PATHS:
            url = host + path.format(s=symbol)
            data, err = _get(url)
            if err:
                print(f"  ✗ {url}\n      {err}")
                continue
            good, why = ok_payload(data)
            if not good:
                print(f"  ✗ {url}\n      پاسخ آمد ولی: {why}")
                continue
            print(f"  ✓ {url}")
            print(f"      {json.dumps(data, ensure_ascii=False)[:300]}")
            found["depth"].append(url)
    if not any(found.values()):
        print("\nهیچ مسیری جواب نداد — بدنهٔ خطاها بالاست. حدس زده نمی‌شود.")
    return found


def fee_from_contract(payload):
    """کارمزد پیش‌فرض را از پاسخ مشخصات قرارداد بیرون می‌کشد، اگر باشد.

    هر صرافی اسم دیگری می‌گذارد؛ فقط کلیدهای شناخته‌شده خوانده می‌شوند و
    شکل ناشناخته None برمی‌گرداند — کارمزدِ حدسی بدتر از نداشتنش است."""
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(rows, dict):
        rows = rows.get("list") or rows.get("contracts") or [rows]
    if not isinstance(rows, list) or not rows:
        return None
    mk = ("makerFeeRate", "maker_fee_rate", "makerFee", "takerFeeRate",
          "taker_fee_rate", "takerFee")
    out = {}
    for r in rows[:1] if isinstance(rows[0], dict) else []:
        for k in mk:
            if k in r:
                out[k] = r[k]
    return out or None


def book_stats(payload):
    """(اسپرد bps، عمق ۵ سطح بید، عمق ۵ سطح اسک) یا None."""
    d = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(d, dict):
        bids, asks = d.get("bids") or d.get("b"), d.get("asks") or d.get("a")
    else:
        return None
    if not isinstance(bids, list) or not isinstance(asks, list) \
            or not bids or not asks:
        return None

    def norm(rows):
        out = []
        for r in rows:
            if isinstance(r, (list, tuple)) and len(r) >= 2:
                try:
                    out.append((float(r[0]), float(r[1])))
                except (TypeError, ValueError):
                    continue
        return out
    b, a = norm(bids), norm(asks)
    if not b or not a:
        return None
    b.sort(key=lambda x: -x[0])
    a.sort(key=lambda x: x[0])
    if a[0][0] <= b[0][0]:
        return None                                   # دفتر متقاطع = خراب
    mid = (b[0][0] + a[0][0]) / 2
    return {"spread_bps": round((a[0][0] - b[0][0]) / mid * 10000, 4),
            "mid": mid,
            "depth_bid_5": round(sum(q for _, q in b[:5]), 6),
            "depth_ask_5": round(sum(q for _, q in a[:5]), 6)}


def compare(symbols, kcex_depth_url=None, quiet=False):
    """اسپرد و عمق بیت‌یونیکس در برابر KCEX، همان نمادها، همان لحظه.

    چرا هم‌زمان: اسپرد در طول روز عوض می‌شود؛ مقایسهٔ دو عکس در دو زمان
    مختلف چیزی ثابت نمی‌کند."""
    from hamid import depth_collector as DC
    rows = []
    for s in symbols:
        rec = {"symbol": s, "at": int(time.time() * 1000)}
        f, why = DC.snapshot(s)
        rec["bitunix"] = ({"spread_bps": f["spread_bps"],
                           "depth_bid_5": f["depth_bid_5"],
                           "depth_ask_5": f["depth_ask_5"]} if f
                          else {"error": why})
        if kcex_depth_url:
            ks = s if "_" in s else s.replace("USDT", "_USDT")
            data, err = _get(kcex_depth_url.format(s=ks))
            rec["kcex"] = {"error": err} if err else (
                book_stats(data) or {"error": "شکل دفتر ناشناخته"})
        else:
            rec["kcex"] = {"error": "مسیر عمق هنوز کشف نشده — اول --probe"}
        rows.append(rec)
    res = {"at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "symbols": rows}
    both = [r for r in rows
            if "spread_bps" in r.get("bitunix", {})
            and "spread_bps" in r.get("kcex", {})]
    if both:
        res["median_spread_bps"] = {
            "bitunix": round(statistics.median(
                r["bitunix"]["spread_bps"] for r in both), 3),
            "kcex": round(statistics.median(
                r["kcex"]["spread_bps"] for r in both), 3)}
        res["note"] = ("اسپردِ بیشتر یعنی لغزشِ بیشتر — اگر KCEX اسپرد "
                       "بازتری داشته باشد، کارمزدِ کمترش خنثی می‌شود.")
    else:
        res["note"] = "مقایسهٔ معنادار انجام نشد — یک طرف داده نداد."
    if not quiet:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--compare", default="")
    ap.add_argument("--depth-url", default=None)
    a = ap.parse_args()
    if a.probe:
        probe()
    elif a.compare:
        compare([s.strip() for s in a.compare.split(",") if s.strip()],
                kcex_depth_url=a.depth_url)
    else:
        ap.print_help()
