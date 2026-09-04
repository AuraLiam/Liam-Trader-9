#!/usr/bin/env python3
"""تاکسونومی ارزها — «هر ارز جزو چه دسته‌ای از ارزهاست» (دستور حمید، ۳ سپتامبر).

حمید: «اول تمامی اطلاعات و نحوهٔ توزیع درست و حتی نوع ارز که جزو چه دسته‌ای
از ارزها هست را دسته‌بندی کند… و هر بار ارزها را با دسته‌بندی مشخص در
اختیار اتاق‌ها بگذارد.»

## چرا دسته‌بندی، تصمیم را عوض می‌کند (نه فقط تزئین گزارش)

سه چیز که در همین مخزن اندازه گرفته شده و همه‌شان به دسته گره خورده‌اند:

۱. **استیبل و رپد باید از دفتر بیرون بمانند** — ۱۲ اوت: USD1/USDE با استاپِ
   ذره‌ای R نجومیِ قلابی ساختند (+۵۸R) و آمار دفتر را بی‌معنا کردند.
   (`paper.open_from` همین حالا هم ردشان می‌کند؛ این‌جا دسته‌اش رسمی می‌شود.)
۲. **ارز مستقل از بیت‌کوین حکم دیگری دارد** — ۲۹ اوت، کلاس حساسیت تاریخی:
   نمادِ INDEPENDENT سهمِ بسترِ BTC را نصف می‌گیرد. دسته‌بندی رفتاری همان
   است که این‌جا کنار دستهٔ بنیادی می‌نشیند.
۳. **سهام‌توکن‌ها به ساعت بازار امریکا وابسته‌اند** — قانون ۱۶ اوت. اگر
   ندانیم NVDAB سهام‌توکن است، آخر هفته رویش ستاپ می‌سازیم و بازارِ بسته
   را نمی‌بینیم.

## مرز صادقانه

جدول زیر **دستی و قابل‌بازبینی** است، نه خروجی یک API. هر نمادی که در جدول
نباشد دستهٔ `unknown` می‌گیرد — نه حدس. `unknown` عیب نیست؛ نبودِ ادعاست
(قانون ۱). دسته‌بندی بنیادی از این جدول می‌آید و دسته‌بندی رفتاری
(هم‌بستگی با BTC، نوسان) از اندازه‌گیری — دو چیزِ جدا که عمداً قاطی نمی‌شوند.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

# ── دسته‌های بنیادی ───────────────────────────────────────────────────────
# کلید = دسته، مقدار = پایه‌نمادها. منبع: صفحهٔ رسمی هر پروژه/دسته‌بندی
# کوین‌گکو؛ هر ردیف با بازبینی دستی. تغییر دسته = تغییر سند، نه حدسِ کد.
SECTORS = {
    "stable": ["USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDD",
               "PYUSD", "USDE", "USD1", "RLUSD", "EURI", "EURC", "XUSD", "USDS",
               "USDG", "BFUSD", "AEUR", "USDF"],
    "wrapped": ["WBTC", "WETH", "WBNB", "WSOL", "STETH", "WSTETH", "CBBTC",
                "CBETH", "RETH", "WEETH", "METH", "SOLVBTC", "LBTC"],
    "major": ["BTC", "ETH"],
    "l1": ["SOL", "BNB", "ADA", "AVAX", "DOT", "ATOM", "NEAR", "APT", "SUI",
           "SEI", "TIA", "INJ", "TON", "TRX", "XRP", "LTC", "BCH", "ETC",
           "ALGO", "EGLD", "FTM", "HBAR", "ICP", "KAS", "XLM", "XMR", "ZEC",
           "FIL", "VET", "THETA", "FLOW", "MINA", "ROSE", "CFX", "KAVA",
           "CELO", "ONE", "QTUM", "IOTA", "NEO", "WAVES", "ZIL", "SOMI",
           "BERA", "MON", "PLUME", "S", "HYPE", "ENSO"],
    "l2": ["ARB", "OP", "MATIC", "POL", "STRK", "ZK", "MANTA", "METIS", "BLAST",
           "LRC", "IMX", "SCR", "TAIKO", "MODE", "LINEA", "BASE"],
    "defi": ["UNI", "AAVE", "MKR", "SKY", "CRV", "COMP", "SNX", "LDO", "RPL",
             "SUSHI", "1INCH", "BAL", "YFI", "DYDX", "GMX", "PENDLE", "ENA",
             "ETHFI", "EIGEN", "JTO", "JUP", "RAY", "CAKE", "MORPHO", "FLUID",
             "SPK", "RESOLV", "USUAL", "DOLO", "AERO", "VELO", "SYRUP"],
    "meme": ["DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI", "MEME", "BOME",
             "MEW", "POPCAT", "NEIRO", "TURBO", "BRETT", "MOG", "SPX", "GOAT",
             "PNUT", "ACT", "CHILLGUY", "FARTCOIN", "AI16Z", "TRUMP", "MELANIA",
             "PONS", "USELESS", "TROLL", "PUMP", "BANK", "HOME", "TUT", "BMT"],
    "ai": ["FET", "AGIX", "OCEAN", "RNDR", "RENDER", "TAO", "AKT", "ARKM",
           "WLD", "IO", "GRASS", "AIXBT", "VIRTUAL", "CGPT", "PHA", "NMR",
           "OPEN", "CHIP", "NEAR-AI"],
    "rwa": ["ONDO", "OM", "POLYX", "CFG", "RIO", "TRU", "MPL", "PAXG", "XAUT",
            "GOLD", "PLUME-RWA"],
    "gaming": ["AXS", "SAND", "MANA", "GALA", "ENJ", "ILV", "YGG", "PIXEL",
               "BIGTIME", "PRIME", "RONIN", "RON", "APE", "MAGIC", "GMT",
               "NOT", "HMSTR", "CATI", "DOGS", "LOKA", "ALICE", "TLM"],
    "exchange": ["BNB", "OKB", "CRO", "KCS", "HT", "GT", "MX", "BGB", "WBT",
                 "LEO", "FTT", "ASTER"],
    "oracle": ["LINK", "PYTH", "BAND", "API3", "TRB", "UMA", "RED"],
    "storage": ["FIL", "AR", "STORJ", "SC", "BTT", "WAL"],
    "privacy": ["XMR", "ZEC", "DASH", "SCRT", "ROSE", "ZEN"],
    "interop": ["ATOM", "DOT", "AXL", "W", "ZRO", "STG", "SYN", "ACROSS",
                "OSMO", "RUNE", "KSM"],
    "payment": ["XRP", "XLM", "LTC", "BCH", "DASH", "NANO", "COTI", "PUNDIX"],
    "depin": ["HNT", "MOBILE", "IOT", "IOTX", "DIMO", "PEAQ", "GEOD", "XNET"],
    "stocktoken": ["NVDAB", "TSLAON", "AAPLB", "MSFTB", "METAB", "AMZNB",
                   "GOOGLB", "COINB", "MSTRB", "SPYB", "QQQB", "CRCLB", "SNDKB",
                   "HOODB", "PLTRB"],
    "lst": ["LDO", "RPL", "SWISE", "ANKR", "JITO", "MNDE", "SD"],
    "infra": ["ENS", "SAFE", "GAL", "GPS", "PARTI", "LIT", "BICO", "ZAMA",
              "EDEN", "T", "NIL", "LA", "OMNI", "PROM", "ZKC", "SKY-INFRA"],
}

# ── تکمیل جدول از جهانِ واقعیِ ۲۳۳ نمادی (۳ سپتامبر) ─────────────────────
# فقط پایه‌هایی که دسته‌شان با بازبینی دستی روشن بود. هر چه مبهم ماند
# عمداً `unknown` رها شد — دستهٔ حدسی از دستهٔ نداشته بدتر است.
_MORE = {
    "l1": ["BTG", "ELF", "EOS", "HIVE", "KLAY", "LUNC", "ONG", "STX", "TOMO",
           "VANRY", "XPL", "0G", "MEGA"],
    "l2": ["HEMI", "SOPH", "OMG"],
    "defi": ["BAKE", "BOND", "CVX", "DEXE", "DODO", "HFT", "HIFI", "JST",
             "MITO", "OOKI", "WLFI", "YFII", "BIO"],
    "gaming": ["ACE", "BEAM", "BEAMX", "BNX", "COCOS", "DAR", "DNT", "ERN",
               "MC", "PLA", "PORTAL", "TVK"],
    "ai": ["AI", "KAITO", "NFP", "DGAI"],
    "meme": ["CASHCAT", "MUBARAK", "ORDI", "PENGU", "TST", "GIGGLE", "MARSCOIN",
             "BULLA", "ANTFUN"],
    "depin": ["JASMY"],
    "storage": ["BLZ"],
    "privacy": ["XVG"],
    "exchange": ["TWT"],
    "stocktoken": ["AVGOB", "SOXLB", "SPCXB", "MUB", "KORUB", "SNXXB", "SKHYB",
                   "SUT", "HEI"],
}
for _s, _lst in _MORE.items():
    SECTORS.setdefault(_s, [])
    SECTORS[_s].extend(x for x in _lst if x not in SECTORS[_s])

# نمادِ سهام‌توکن معمولاً با پسوند B/ON می‌آید؛ الگو فقط وقتی به کار می‌رود
# که نماد در جدول نباشد و شکلش صریح باشد (نه حدسِ آزاد).
_STOCK_RE = re.compile(r"^(NVDA|TSLA|AAPL|MSFT|META|AMZN|GOOGL|COIN|MSTR|SPY|QQQ|"
                       r"CRCL|SNDK|HOOD|PLTR|NFLX|AMD|INTC|BABA|NKE|DIS)(B|ON|X)$")

# هر پایه به دستهٔ اصلی‌اش (اولین دسته‌ای که نامش را دارد، با اولویت جدول)
_PRIORITY = ["stable", "wrapped", "stocktoken", "major", "meme", "ai", "rwa",
             "gaming", "depin", "lst", "defi", "l2", "l1", "exchange", "oracle",
             "storage", "privacy", "interop", "payment", "infra"]
_INDEX = {}
for _sec in _PRIORITY:
    for _b in SECTORS.get(_sec, []):
        _INDEX.setdefault(_b.upper(), _sec)

QUOTES = ("USDT", "USDC", "USD", "USD1", "FDUSD", "TUSD", "BUSD", "PERP")


def base_of(sym):
    """پایهٔ نماد: BTCUSDT → BTC. جفتِ استیبل-به-استیبل هم درست جدا می‌شود."""
    s = (sym or "").upper().replace("-", "").replace("_", "").replace(".P", "")
    for q in sorted(QUOTES, key=len, reverse=True):
        if s.endswith(q) and len(s) > len(q):
            return s[: -len(q)]
    return s


def sector(sym):
    """دستهٔ بنیادی. ناشناخته = `unknown`، نه حدس (قانون ۱)."""
    b = base_of(sym)
    if b in _INDEX:
        return _INDEX[b]
    if _STOCK_RE.match(b):
        return "stocktoken"
    return "unknown"


def is_stable_pair(sym):
    """جفتِ استیبل-به-استیبل (USDCUSDT): دفترِ معامله حق ورودش را ندارد."""
    return sector(sym) == "stable"


# ── دسته‌بندی رفتاری (اندازه‌گیری‌شده، نه جدول) ────────────────────────────
def behaviour(sym, sens=None, vol=None):
    """کلاس رفتاری از سنجه‌ها: هم‌بستگی با BTC و نوسان. نبودِ داده = unknown."""
    out = {"btc_class": "UNKNOWN", "vol_class": "unknown"}
    rec = (sens or {}).get(sym) or (sens or {}).get(base_of(sym) + "USDT") or {}
    if rec.get("class"):
        out["btc_class"] = rec["class"]
    v = (vol or {}).get(sym)
    if isinstance(v, (int, float)):
        out["vol_class"] = ("calm" if v < 1.5 else "normal" if v < 3.0
                            else "hot" if v < 6.0 else "wild")
        out["atr_pct"] = round(float(v), 3)
    return out


def tier(rank):
    """ردهٔ نقدشوندگی از رتبهٔ حجم — کوچک‌ترها لغزش بیشتری دارند."""
    if rank is None:
        return "unknown"
    r = int(rank)
    return ("core" if r <= 10 else "large" if r <= 40 else
            "mid" if r <= 100 else "small" if r <= 200 else "micro")


def classify(sym, rank=None, sens=None, vol=None):
    """کارتِ کاملِ یک ارز — همان چیزی که با هر نماد به اتاق‌ها تحویل می‌شود."""
    sec = sector(sym)
    card = {"sym": sym, "base": base_of(sym), "sector": sec, "tier": tier(rank),
            "rank": rank, **behaviour(sym, sens, vol)}
    card["tradable"] = sec not in ("stable", "wrapped")
    card["session_bound"] = sec == "stocktoken"      # وابسته به ساعت بازار امریکا
    card["notes"] = []
    if sec == "stable":
        card["notes"].append("استیبل — وارد دفتر معامله نمی‌شود (درس ۱۲ اوت: R قلابی)")
    if sec == "wrapped":
        card["notes"].append("رپد — تکرارِ دارایی پایه، جدا معامله نمی‌شود")
    if card["session_bound"]:
        card["notes"].append("سهام‌توکن — به ساعت بازار امریکا وابسته است")
    if card["btc_class"] == "INDEPENDENT":
        card["notes"].append("مستقل از بیت‌کوین — سهم بسترِ BTC نصف (۲۹ اوت)")
    if sec == "meme":
        card["notes"].append("میم — حرکتش خبر/جمعیت‌محور است، نه بنیادی")
    if sec == "unknown":
        card["notes"].append("دستهٔ بنیادی ناشناخته — جدول تاکسونومی این پایه را ندارد")
    return card


def coverage(symbols):
    """چند درصد از یک فهرست دسته دارند — متر صادقانهٔ خودِ جدول."""
    syms = list(symbols or [])
    known = [s for s in syms if sector(s) != "unknown"]
    by = {}
    for s in syms:
        by[sector(s)] = by.get(sector(s), 0) + 1
    return {"n": len(syms), "known": len(known),
            "pct": round(100.0 * len(known) / len(syms), 1) if syms else None,
            "by_sector": dict(sorted(by.items(), key=lambda kv: -kv[1]))}


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    syms = [a for a in argv if not a.startswith("-")]
    if not syms:
        try:
            syms = [r["symbol"] for r in json.loads(
                (ROOT / "signals" / "latest.json").read_text(encoding="utf-8")
            ).get("symbols") or []][:200]
        except Exception:                            # noqa: BLE001
            syms = ["BTCUSDT", "ETHUSDT", "PEPEUSDT", "USDCUSDT", "NVDABUSDT", "ZZZUSDT"]
    cov = coverage(syms)
    print(f"تاکسونومی: {cov['known']}/{cov['n']} نماد دسته دارند ({cov['pct']}٪)")
    for sec, n in cov["by_sector"].items():
        print(f"  {sec:<12} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
