"""پالی‌مارکت — بازار پیش‌بینی به‌عنوان منبع شواهد، با ردیابی پول بزرگ.

دستور حمید (۲۴ اوت): «سایت پالی‌مارکت را حتماً داشته باش و بر اساس
پیش‌بینی‌هایی که می‌شود با تحلیل‌هایت مقایسه کن... ایجنت را جوری کد
می‌دهی که دنبال ردِ پول‌های بزرگ نسبت به بقیه باشد... این چرخهٔ
جمع‌آوری باید با اثباتِ داده همراه باشد.»

## چه چیزی خوانده می‌شود

- بازارهای بازِ کریپتو از Gamma API (پرحجم‌ترین‌ها): سؤال بازار، قیمت
  YES (= احتمالِ ضمنی‌ای که پولِ واقعی رویش نشسته)، حجم ۲۴س، نقدینگی.
- معاملات اخیر هر بازار از Data API: اندازهٔ دلاری هر معامله → تفکیک
  **پول بزرگ** (≥ BIG_USD) از پول خرد، و «کجِ نهنگی»: احتمالِ وزنیِ
  معاملات بزرگ منهای احتمالِ وزنیِ معاملات خرد. مثبت یعنی پول بزرگ
  خوش‌بین‌تر از جمعیت است.

## مقایسه با تحلیل خودمان

جهتِ ضمنیِ بازارهای BTC با رژیم دامیننس خودمان (`signals/dominance.json`)
کنار هم گذاشته و توافق/تعارض صریح ثبت می‌شود.

## مرزهای صادقانه (تغییرشان فقط با دستور صریح حمید)

۱. **شاهد است، نه دروازه.** هیچ خروجی این ماژول امتیازی را بالا نمی‌برد
   و دروازه‌ای را باز نمی‌کند — «کانکتورها حامل کارند، تصمیم نمی‌گیرند»
   (CLAUDE.md). فرضیهٔ «کجِ نهنگی سیگنال است» طبق قانون ۰۳ اول باید از
   بک‌تست و CI رد شود؛ تا آن روز فقط ثبت و نمایش.
۲. **اثباتِ بازدید.** هر اجرا یک ردیف در
   `brain/research/polymarket/visits.jsonl` می‌گذارد: retrieved_at،
   URLها، چند بازار و چند معامله خوانده شد، و خلاصهٔ یافته — تا حمید
   ببیند ایجنت واقعاً رفته، نه ادعا کرده (قانون ۰۳: هر claim منبع و
   retrieved_at دارد).
۳. **عدد ساخته نمی‌شود.** API نیامد = خروجی با `ok=false` و شمارش خطا؛
   کجِ نهنگی زیر MIN_BIG_TRADES معامله اعلام نمی‌شود.

اجرا:  python3 -m hamid.polymarket
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "polymarket.json"
VISITS = ROOT / "brain" / "research" / "polymarket" / "visits.jsonl"
DOM = ROOT / "signals" / "dominance.json"

GAMMA = "https://gamma-api.polymarket.com/markets"
TRADES = "https://data-api.polymarket.com/trades"

BIG_USD = 5_000.0            # آستانهٔ «پول بزرگ» — یک معامله، نه کل حجم
MIN_BIG_TRADES = 5           # زیر این، «کجِ نهنگی» اصلاً اعلام نمی‌شود
MAX_MARKETS = 12             # پرحجم‌ترین بازارهای کریپتو
TRADES_PER_MARKET = 300
TIMEOUT = 20

CRYPTO_PAT = re.compile(
    r"\b(bitcoin|btc|ethereum|eth|solana|sol|xrp|ripple|doge|bnb|crypto)\b",
    re.IGNORECASE)
UP_PAT = re.compile(r"\b(above|reach|hit|higher|exceed|\$\d[\d,]*k?\s*or more)\b",
                    re.IGNORECASE)
DOWN_PAT = re.compile(r"\b(below|under|lower|dip to|drop)\b", re.IGNORECASE)


def _get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "liam9/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _floats(v):
    """outcomePrices در Gamma رشتهٔ JSON است: '["0.65","0.35"]'."""
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except json.JSONDecodeError:
            return []
    try:
        return [float(x) for x in (v or [])]
    except (TypeError, ValueError):
        return []


def crypto_direction(question):
    """→ ('BTC'|'ETH'|...|None, 'up'|'down'|None). نامفهوم = None، نه حدس."""
    q = question or ""
    m = CRYPTO_PAT.search(q)
    if not m:
        return None, None
    asset = {"bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH",
             "solana": "SOL", "sol": "SOL", "xrp": "XRP", "ripple": "XRP",
             "doge": "DOGE", "bnb": "BNB"}.get(m.group(1).lower(), "CRYPTO")
    if UP_PAT.search(q) and not DOWN_PAT.search(q):
        return asset, "up"
    if DOWN_PAT.search(q) and not UP_PAT.search(q):
        return asset, "down"
    return asset, None


def parse_market(m):
    """بازار خام Gamma → رکورد تمیز، یا None اگر کریپتو/سالم نیست."""
    q = m.get("question") or m.get("title") or ""
    asset, direction = crypto_direction(q)
    if asset is None:
        return None
    prices = _floats(m.get("outcomePrices"))
    if not prices or not (0.0 <= prices[0] <= 1.0):
        return None
    return {"question": q[:160], "asset": asset, "direction": direction,
            "implied_yes": round(prices[0], 4),
            "volume24h": round(float(m.get("volume24hr") or 0), 0),
            "liquidity": round(float(m.get("liquidity") or 0), 0),
            "end_date": m.get("endDate"),
            "condition_id": m.get("conditionId"),
            "slug": m.get("slug")}


def whale_split(trades, big_usd=BIG_USD):
    """معاملات → کجِ نهنگی. نمونهٔ کم = None با دلیل، نه عدد قانع‌کننده.

    «موضع» هر معامله دوحالته است: پول روی وقوع (YES=۱) یا علیه وقوع
    (NO=۰) — خریدِ YES یا فروشِ NO یعنی روی وقوع؛ خریدِ NO یا فروشِ YES
    یعنی علیه. وزن، دلارِ واقعیِ همان معامله است (size×price).
    «کج» = سهمِ دلاریِ YES در پول بزرگ منهای همان در پول خرد — مثبت
    یعنی پول بزرگ بیشتر از جمعیت روی وقوع نشسته.
    """
    big, small = [], []
    for t in trades or []:
        try:
            size = float(t.get("size") or 0)
            price = float(t.get("price") or 0)
        except (TypeError, ValueError):
            continue
        usd = size * price
        if usd <= 0 or not (0.0 < price < 1.0):
            continue
        sell = str(t.get("side") or "").upper() == "SELL"
        on_no = str(t.get("outcome") or "").lower() == "no"
        p_yes = 0.0 if (on_no != sell) else 1.0     # XOR: نه-فروشِ نه = روی وقوع
        (big if usd >= big_usd else small).append((usd, p_yes))
    def wavg(rows):
        tot = sum(u for u, _ in rows)
        return (sum(u * p for u, p in rows) / tot) if tot else None
    res = {"n_big": len(big), "n_small": len(small),
           "big_usd_total": round(sum(u for u, _ in big), 0),
           "small_usd_total": round(sum(u for u, _ in small), 0),
           "p_big": None, "p_small": None, "skew": None,
           "note": ""}
    if len(big) < MIN_BIG_TRADES:
        res["note"] = (f"فقط {len(big)} معاملهٔ ≥${int(big_usd)} — کجِ نهنگی "
                       f"اعلام نمی‌شود (کف {MIN_BIG_TRADES})")
        return res
    pb, ps = wavg(big), wavg(small)
    res["p_big"] = round(pb, 4) if pb is not None else None
    if ps is not None:
        res["p_small"] = round(ps, 4)
        res["skew"] = round(pb - ps, 4)
        res["note"] = ("پول بزرگ خوش‌بین‌تر از خرد" if res["skew"] > 0.02 else
                       "پول بزرگ بدبین‌تر از خرد" if res["skew"] < -0.02 else
                       "پول بزرگ و خرد هم‌نظرند")
    else:
        res["note"] = "معاملهٔ خرد کافی برای مقایسه نیست"
    return res


def our_view():
    """رژیم دامیننس خودمان — برای مقایسه، نه داوری."""
    try:
        d = json.loads(DOM.read_text(encoding="utf-8"))
        return ((d.get("structural") or {}).get("regime")
                or d.get("regime") or "UNKNOWN")
    except (OSError, json.JSONDecodeError):
        return "UNKNOWN"


def compare(markets, regime):
    """پیش‌بینی پالی‌مارکت در برابر تحلیل ما — توافق/تعارض صریح."""
    out = []
    for m in markets:
        if m["asset"] != "BTC" or m["direction"] is None:
            continue
        # احتمالِ ضمنیِ «بالا رفتن»: بازار جهت‌دار up همان YES است، down برعکسش
        p_up = m["implied_yes"] if m["direction"] == "up" else 1 - m["implied_yes"]
        pm_view = "BULLISH" if p_up >= 0.55 else "BEARISH" if p_up <= 0.45 else "NEUTRAL"
        agree = ("توافق" if pm_view == regime else
                 "قابل‌مقایسه نیست" if regime in ("UNKNOWN", "INSUFFICIENT",
                                                  "RANGE", "TRANSITION",
                                                  "UNSAFE") or pm_view == "NEUTRAL"
                 else "تعارض")
        out.append({"question": m["question"], "p_up": round(p_up, 3),
                    "polymarket_view": pm_view, "our_regime": regime,
                    "verdict": agree})
    return out


def fetch(max_markets=MAX_MARKETS):
    """→ (بازارهای کریپتو با نهنگ‌سنجی، urlهای رفته، خطاها)."""
    urls, errors, markets = [], [], []
    url = (f"{GAMMA}?closed=false&active=true&order=volume24hr"
           f"&ascending=false&limit=60")
    urls.append(url)
    try:
        raw = _get(url)
    except Exception as e:                           # noqa: BLE001
        errors.append(f"gamma: {type(e).__name__}")
        return [], urls, errors
    for m in raw if isinstance(raw, list) else []:
        rec = parse_market(m)
        if rec:
            markets.append(rec)
        if len(markets) >= max_markets:
            break
    for rec in markets:
        if not rec.get("condition_id"):
            rec["whales"] = {"note": "بدون شناسهٔ بازار — معاملات خواندنی نیست"}
            continue
        turl = f"{TRADES}?market={rec['condition_id']}&limit={TRADES_PER_MARKET}"
        urls.append(turl)
        try:
            rec["whales"] = whale_split(_get(turl))
        except Exception as e:                       # noqa: BLE001
            errors.append(f"trades({rec['asset']}): {type(e).__name__}")
            rec["whales"] = {"note": f"خواندنی نبود ({type(e).__name__})"}
    return markets, urls, errors


def prove_visit(urls, n_markets, n_trades, summary, errors):
    """اثباتِ بازدید — قانون ۰۳: منبع + retrieved_at + یافته، append-only."""
    VISITS.parent.mkdir(parents=True, exist_ok=True)
    row = {"retrieved_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "agent": "E14/polymarket",
           "source": "polymarket.com (Gamma + Data API)",
           "urls_visited": len(urls), "sample_urls": urls[:3],
           "markets_read": n_markets, "trades_read": n_trades,
           "summary": summary[:400], "errors": errors,
           "validation_status": "UNVERIFIED",
           "note": ("شاهد است نه دروازه؛ ارتقا فقط از مسیر قانون ۰۳ "
                    "(بک‌تست → CI بالای صفر → تأیید حمید)")}
    with VISITS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def run(quiet=False):
    markets, urls, errors = fetch()
    regime = our_view()
    comp = compare(markets, regime)
    n_trades = sum((m.get("whales") or {}).get("n_big", 0)
                   + (m.get("whales") or {}).get("n_small", 0) for m in markets)
    whale_notes = [f"{m['asset']}: {m['whales'].get('note', '')}"
                   for m in markets if (m.get("whales") or {}).get("skew") is not None]
    summary = (f"{len(markets)} بازار کریپتو · {n_trades} معامله · "
               + (" | ".join(whale_notes[:3]) if whale_notes
                  else "نهنگ‌سنجیِ قابل‌اعلام نبود"))
    proof = prove_visit(urls, len(markets), n_trades, summary, errors)
    res = {"at": proof["retrieved_at"], "panel": "لیام تریدر ۹",
           "ok": bool(markets), "markets": markets,
           "comparison_vs_our_analysis": comp,
           "our_regime": regime, "errors": errors,
           "big_usd_threshold": BIG_USD,
           "boundary": ("احتمالِ ضمنیِ پولِ واقعی + ردِ پول بزرگ — شاهد "
                        "است، نه دروازه؛ هیچ امتیازی را بالا نمی‌برد "
                        "(قانون ۰۳/۱۱). اثبات بازدید: "
                        "brain/research/polymarket/visits.jsonl")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    if not quiet:
        print(f"پالی‌مارکت: {summary}")
        for c in comp[:4]:
            print(f"  BTC↑ {c['p_up']:.0%} ({c['polymarket_view']}) در برابر "
                  f"رژیم ما ({c['our_regime']}) → {c['verdict']}")
        if errors:
            print(f"  خطاها: {errors}")
    return res


if __name__ == "__main__":
    run()
