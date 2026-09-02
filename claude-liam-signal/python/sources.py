#!/usr/bin/env python3
"""The venues the panel reads, available to the Python side.

The browser stopped depending on Binance a while ago. Everything that runs on a
GitHub runner — the live scan, the miner, the backtest — did not, and still
asked api.binance.com and nothing else. That held only because the runners
happen to be somewhere Binance answers, and it already stopped being true once:
a runner got HTTP 451 from api.binance.com, and every scheduled job that hour
produced nothing. One venue deciding to refuse should not stop the pipeline any
more than it stops the panel.

So this is the panel's SOURCES table, in Python — ten of the twelve. Bitunix
is not here because its kline endpoint is futures-only and lists a different
set of symbols than the backtest ranks; Coinbase is not here because it quotes
USD, not USDT, and a USD close is not the same number. Both stay in the panel,
where one symbol is charted at a time and that does not matter. The field orders below are not
copied from documentation — they are the rows probe_sources.py actually
received, the same ones tests/sources-parse.mjs checks the JavaScript against,
and test_sources.py re-checks these against the identical rows. That matters
because a wrong field index still parses as a number: it just is not the price.

Two shapes come back out, both in Binance's own shape so no caller changes:

    klines(sym, tf, limit) -> [[open_ms, o, h, l, c, v, close_ms], ...]  oldest first
    tickers()             -> [{"symbol": "BTCUSDT", "quoteVolume": "..."}, ...]

A venue that answers with fewer candles than asked for is skipped rather than
used short. A scan run on 180 candles when the engine wants 420 is not a
degraded scan, it is a different one, and it would not announce itself.
"""
import json
import os
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; hamid-signal)"}
TIMEOUT = 12          # a venue slower than this is not usable at this cadence

# A venue that has just refused three times will refuse the fourth. Walking the
# full list for every one of a hundred-odd requests turns one rate-limited
# exchange into a cycle that takes minutes instead of seconds — which is exactly
# what happened: a run that normally finishes in forty seconds sat for over ten.
# So a failing venue is stood down briefly rather than asked again immediately.
_STOOD_DOWN = {}
_FAILS = {}
STAND_DOWN_SECONDS = 300
FAILS_BEFORE_STAND_DOWN = 3


def _available(vid):
    until = _STOOD_DOWN.get(vid, 0)
    return time.time() >= until


def _note_failure(vid):
    _FAILS[vid] = _FAILS.get(vid, 0) + 1
    if _FAILS[vid] >= FAILS_BEFORE_STAND_DOWN:
        _STOOD_DOWN[vid] = time.time() + STAND_DOWN_SECONDS
        _FAILS[vid] = 0


def _note_success(vid):
    _FAILS[vid] = 0
    _STOOD_DOWN.pop(vid, None)


def _json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _rows(payload, *keys):
    """Dig the array out of whichever envelope this venue wrapped it in."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for k in keys or ("data", "result"):
        v = payload.get(k)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for k2 in ("list", "klines", "candles", "ticker", "data"):
                if isinstance(v.get(k2), list):
                    return v[k2]
    return None


def _n(x):
    return float(x)


# ── candle adapters ────────────────────────────────────────────────────────
# Each returns rows oldest-first in Binance's shape. The comment on each is the
# row as observed, because that is the only thing that decides these indices.

def _dash(sym):      # BTCUSDT -> BTC-USDT
    return sym[:-4] + "-USDT" if sym.endswith("USDT") else sym


def _under(sym):     # BTCUSDT -> BTC_USDT
    return sym[:-4] + "_USDT" if sym.endswith("USDT") else sym


def _k(t, o, h, l, c, v):
    return [int(t), _n(o), _n(h), _n(l), _n(c), _n(v), int(t)]


VENUES = []


def venue(vid, label, url):
    """Register a venue. `url` builds the request, the decorated function turns
    whatever came back into Binance-shaped rows, oldest first. They are kept
    apart so test_sources.py can hand the parser a recorded reply and check the
    field order without touching the network."""
    def deco(fn):
        VENUES.append({"id": vid, "label": label, "url": url, "parse": fn})
        return fn
    return deco


@venue("mexc", "MEXC",
       lambda s, tf, n: f"https://api.mexc.com/api/v3/klines?symbol={s}"
                        f"&interval={ {'1m':'1m','5m':'5m','15m':'15m','1h':'60m','4h':'4h','1d':'1d'}[tf] }&limit={n}")
def _mexc(r):
    # [openTime_ms, o, h, l, c, vol, closeTime] — oldest first, Binance's own shape
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


@venue("kucoin", "KuCoin",
       lambda s, tf, n: f"https://api.kucoin.com/api/v1/market/candles"
                        f"?type={ {'1m':'1min','5m':'5min','15m':'15min','1h':'1hour','4h':'4hour','1d':'1day'}[tf] }"
                        f"&symbol={_dash(s)}")
def _kucoin(r):
    # [t_s, open, CLOSE, HIGH, LOW, vol, turnover] — newest first, seconds.
    # Close and high swap places against Binance; that is the trap here.
    return [_k(int(x[0]) * 1000, x[1], x[3], x[4], x[2], x[5]) for x in reversed(_rows(r))]


@venue("okx", "OKX",
       lambda s, tf, n: f"https://www.okx.com/api/v5/market/candles?instId={_dash(s)}"
                        f"&bar={ {'1m':'1m','5m':'5m','15m':'15m','1h':'1H','4h':'4H','1d':'1D'}[tf] }&limit=300")
def _okx(r):
    # [t_ms, o, h, l, c, vol, volCcy] — newest first
    return [_k(int(x[0]), x[1], x[2], x[3], x[4], x[5]) for x in reversed(_rows(r))]


@venue("bitget", "Bitget",
       lambda s, tf, n: f"https://api.bitget.com/api/v2/spot/market/candles?symbol={s}"
                        f"&granularity={ {'1m':'1min','5m':'5min','15m':'15min','1h':'1h','4h':'4h','1d':'1day'}[tf] }"
                        f"&limit={min(n, 1000)}")
def _bitget(r):
    # [t_ms, o, h, l, c, baseVol, quoteVol] — oldest first
    return [_k(int(x[0]), x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


@venue("gate", "Gate.io",
       lambda s, tf, n: f"https://api.gateio.ws/api/v4/spot/candlesticks"
                        f"?currency_pair={_under(s)}"
                        f"&interval={ {'1m':'1m','5m':'5m','15m':'15m','1h':'1h','4h':'4h','1d':'1d'}[tf] }"
                        f"&limit={min(n, 1000)}")
def _gate(r):
    # [t_s, QUOTEVOL, close, high, low, open, baseVol] — oldest first, seconds.
    # Volume is second and open is last; nothing else lays it out this way.
    return [_k(int(x[0]) * 1000, x[5], x[3], x[4], x[2],
               x[6] if len(x) > 6 else x[1]) for x in _rows(r)]


@venue("bingx", "BingX",
       lambda s, tf, n: f"https://open-api.bingx.com/openApi/spot/v2/market/kline"
                        f"?symbol={_dash(s)}"
                        f"&interval={ {'1m':'1m','5m':'5m','15m':'15m','1h':'1h','4h':'4h','1d':'1d'}[tf] }"
                        f"&limit={min(n, 1000)}")
def _bingx(r):
    # [t_ms, o, h, l, c, vol, closeTime] — newest first
    return [_k(int(x[0]), x[1], x[2], x[3], x[4], x[5]) for x in reversed(_rows(r))]


@venue("bitmart", "BitMart",
       lambda s, tf, n: f"https://api-cloud.bitmart.com/spot/quotation/v3/klines"
                        f"?symbol={_under(s)}"
                        f"&step={ {'1m':1,'5m':5,'15m':15,'1h':60,'4h':240,'1d':1440}[tf] }&limit={min(n, 500)}")
def _bitmart(r):
    # [t_s, o, h, l, c, baseVol, quoteVol] — oldest first, seconds
    return [_k(int(x[0]) * 1000, x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


@venue("htx", "HTX",
       lambda s, tf, n: f"https://api.huobi.pro/market/history/kline?symbol={s.lower()}"
                        f"&period={ {'1m':'1min','5m':'5min','15m':'15min','1h':'60min','4h':'4hour','1d':'1day'}[tf] }"
                        f"&size={min(n, 2000)}")
def _htx(r):
    # {id_s, open, close, low, high, amount} — newest first, seconds
    return [_k(int(x["id"]) * 1000, x["open"], x["high"], x["low"], x["close"],
               x.get("amount", 0)) for x in reversed(_rows(r))]


@venue("coinex", "CoinEx",
       lambda s, tf, n: f"https://api.coinex.com/v2/spot/kline?market={s}"
                        f"&period={ {'1m':'1min','5m':'5min','15m':'15min','1h':'1hour','4h':'4hour','1d':'1day'}[tf] }"
                        f"&limit={min(n, 1000)}")
def _coinex(r):
    # {created_at_ms, open, close, high, low, volume} — oldest first, already ms
    return [_k(int(x["created_at"]), x["open"], x["high"], x["low"], x["close"],
               x.get("volume", 0)) for x in _rows(r)]


@venue("binance", "Binance",
       lambda s, tf, n: f"https://data-api.binance.vision/api/v3/klines?symbol={s}"
                        f"&interval={tf}&limit={n}")
def _binance(r):
    # Last, not first. It is the reference shape and it still answers from a
    # runner most days — but it is the one venue already observed to refuse,
    # with HTTP 451, which is why nothing depends on it any more.
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


# ── the guard ──────────────────────────────────────────────────────────────

def sane_why(rows, want):
    """همان `sane` ولی با دلیلِ رد — برای کاوش منبع تازه (۲ سپتامبر: بیت‌یونیکس
    ۴۲۰ ردیف داد و «insane» شد بی‌آنکه کسی بداند کدام شرط افتاد)."""
    if not rows or len(rows) < min(want, 10):
        return f"کوتاه: {len(rows or [])} ردیف"
    if len(rows) < want * 0.9:
        return f"کمتر از ۹۰٪ خواسته: {len(rows)}/{want}"
    if rows[0][0] >= rows[-1][0]:
        return "ترتیب قدیمی→جدید نیست"
    for i, k in enumerate(rows):
        o, h, l, c = k[1], k[2], k[3], k[4]
        if not all(x == x for x in (o, h, l, c)):
            return f"NaN در ردیف {i}"
        if h < l or min(o, h, l, c) <= 0:
            return f"ردیف {i}: h<l یا عدد ≤۰ ({o},{h},{l},{c})"
        if h < max(o, c) or l > min(o, c):
            return f"ردیف {i}: بدنه بیرون از دامنه ({o},{h},{l},{c})"
    return ""


def sane(rows, want):
    """Same test the panel applies before it charts anything.

    A reply can be well-formed JSON, parse without error, and still be useless:
    reversed, short, or with two fields swapped. Each of those has happened.
    """
    if not rows or len(rows) < min(want, 10):
        return False
    if len(rows) < want * 0.9:
        return False                                 # short is a different scan
    if rows[0][0] >= rows[-1][0]:
        return False                                 # must run oldest -> newest
    for k in rows:
        o, h, l, c = k[1], k[2], k[3], k[4]
        if not all(x == x for x in (o, h, l, c)):    # NaN
            return False
        if h < l or min(o, h, l, c) <= 0:
            return False
        if h < max(o, c) or l > min(o, c):
            return False
    return True


# ── tickers ────────────────────────────────────────────────────────────────

def _t_mexc():
    r = _json("https://api.mexc.com/api/v3/ticker/24hr")
    return [{"symbol": x["symbol"], "quoteVolume": x.get("quoteVolume", 0)} for x in r]


def _t_okx():
    r = _rows(_json("https://www.okx.com/api/v5/market/tickers?instType=SPOT"))
    return [{"symbol": x["instId"].replace("-", ""), "quoteVolume": x.get("volCcy24h", 0)}
            for x in r]


def _t_gate():
    r = _json("https://api.gateio.ws/api/v4/spot/tickers")
    return [{"symbol": x["currency_pair"].replace("_", ""), "quoteVolume": x.get("quote_volume", 0)}
            for x in r]


def _t_bitget():
    r = _rows(_json("https://api.bitget.com/api/v2/spot/market/tickers"))
    return [{"symbol": x["symbol"], "quoteVolume": x.get("quoteVolume", 0)} for x in r]


def _t_kucoin():
    r = _rows(_json("https://api.kucoin.com/api/v1/market/allTickers"), "data")
    return [{"symbol": x["symbol"].replace("-", ""), "quoteVolume": x.get("volValue", 0)}
            for x in r]


def _t_binance():
    r = _json("https://api.binance.com/api/v3/ticker/24hr")
    return [{"symbol": x["symbol"], "quoteVolume": x.get("quoteVolume", 0)} for x in r]


TICKERS = [("mexc", _t_mexc), ("okx", _t_okx), ("gate", _t_gate),
           ("bitget", _t_bitget), ("kucoin", _t_kucoin), ("binance", _t_binance)]

_used = {"klines": None, "tickers": None}


def used():
    """Which venue actually served, so a report can say where its numbers came from."""
    return dict(_used)


PERP_VENUES = []


def perp_venue(vid, label, url, fetch=None):
    """صرافیِ **قرارداد دائمی** — همان قرارداد `venue`، دفتر جدا.

    `fetch(sym, tf, n)` اختیاری: صرافی‌ای که یک درخواستش کل پنجره را نمی‌دهد
    (سقف ۲۰۰ کندل بیت‌یونیکس) با همین تابع صفحه‌به‌صفحه می‌خواند."""
    def deco(fn):
        PERP_VENUES.append({"id": vid, "label": label, "url": url, "parse": fn,
                            "fetch": fetch})
        return fn
    return deco


# ── بیت‌یونیکس — صرافیِ اجرا (دستور مکرر حمید: «بیت‌یونیکس، پرپچوال») ──────
# دستور حمید (۲ سپتامبر، بار چندم): «صرافی بیت‌یونیکس رو انتخاب کن در
# تریدینگ‌ویو و ارز پرپچوال رو انتخاب کن که قیمتش درست و چارتش تمیز باشد.»
# کندلی که حمید روی چارت می‌بیند همین است؛ پس اول این، بعد بقیهٔ پرپ‌ها،
# و اسپات فقط پشتیبان («گزینهٔ جایگزین همیشه باشد»).
# API عمومی، بی‌کلید: GET /api/v1/futures/market/kline (سقف ۲۰۰ کندل در
# هر درخواست؛ startTime/endTime برای صفحه‌بندی). شکل ردیف طبق مستندات:
# {open, high, low, close, time(ms), baseVol, quoteVol}. پارسر هر دو شکل
# دیکشنری و لیست را می‌پذیرد و `sane()` پایین‌دست هر انحرافی را رد می‌کند —
# اثبات نهایی روی رانر است (venue-probe.yml)، نه این‌جا.
BITUNIX_KLINE = "https://fapi.bitunix.com/api/v1/futures/market/kline"
BITUNIX_PAGE = 200
_TF_MS = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
          "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "1d": 86_400_000}


def _bitunix_url(sym, tf, n, end_ms=None):
    q = f"?symbol={sym}&interval={tf}&limit={min(int(n), BITUNIX_PAGE)}&type=LAST_PRICE"
    if end_ms:
        q += f"&endTime={int(end_ms)}"
    return BITUNIX_KLINE + q


BITUNIX_CLAMP_TOL = 0.001    # ۰.۱٪ — سقفِ رواداری برای «سقف یک تیک زیر open»


def _bitunix_parse(r):
    """کندل بیت‌یونیکس → شکل بایننس. یافتهٔ رانر (کاوش ۵، ۲ سپتامبر): در بعضی
    ردیف‌ها high یک تیک زیر open است (77864.4 در برابر open 77864.5) — رُندِ
    خودِ صرافی، نه دادهٔ غلط. تا ۰.۱٪ به open/close چسبانده می‌شود و شمرده؛
    بزرگ‌تر از آن دست‌نخورده می‌ماند تا `sane()` ردش کند."""
    rows = _rows(r) or []
    out = []
    for x in rows:
        try:
            if isinstance(x, dict):
                t = x.get("time") or x.get("ts") or x.get("t") or x.get("openTime")
                k = _k(t, x.get("open", x.get("o")), x.get("high", x.get("h")),
                       x.get("low", x.get("l")), x.get("close", x.get("c")),
                       x.get("baseVol", x.get("vol", x.get("volume", x.get("v", 0)))) or 0)
            elif isinstance(x, (list, tuple)) and len(x) >= 5:
                k = _k(x[0], x[1], x[2], x[3], x[4], x[5] if len(x) > 5 else 0)
            else:
                continue
            body_hi, body_lo = max(k[1], k[4]), min(k[1], k[4])
            if k[2] < body_hi and body_hi - k[2] <= body_hi * BITUNIX_CLAMP_TOL:
                k[2] = body_hi
            if k[3] > body_lo and k[3] - body_lo <= body_lo * BITUNIX_CLAMP_TOL:
                k[3] = body_lo
            out.append(k)
        except Exception:                            # noqa: BLE001 - ردیف خراب = حذف، بقیه می‌مانند
            continue
    out.sort(key=lambda k: k[0])
    # ثانیه به‌جای میلی‌ثانیه؟ یکنواخت کن
    if out and out[-1][0] < 10_000_000_000:
        out = [[k[0] * 1000, *k[1:6], k[0] * 1000] for k in out]
    return out


def _bitunix_fetch(sym, tf, n, _json_fn=None):
    """صفحه‌به‌صفحه از جدیدترین به قدیمی‌ترین تا `n` کندل؛ یکتا بر زمان."""
    getj = _json_fn or _json
    got, end_ms = {}, None
    # یک صفحهٔ اضافه، چون با endTime=oldest ممکن است هر صفحه یک ردیفِ تکراری
    # (خودِ oldest) بیاورد و ۱۹۹ کندل تازه بدهد.
    for _ in range(2 + (int(n) - 1) // BITUNIX_PAGE + 1):
        rows = _bitunix_parse(getj(_bitunix_url(sym, tf, n, end_ms)))
        if not rows:
            break
        before = len(got)
        for k in rows:
            got[k[0]] = k
        oldest = rows[0][0]
        if len(got) >= n or len(got) == before:
            break                      # کافی است، یا صفحه هیچ کندل تازه‌ای نداشت
        if len(rows) < min(BITUNIX_PAGE, n) and end_ms is None:
            break                      # صرافی از اول کمتر از یک صفحه داشت
        # کاوش ۵ و ۶ روی رانر: هم `oldest - step` و هم `oldest - 1` در هر مرز
        # صفحه یک کندل جا می‌انداخت (فاصلهٔ ۳۰د در سری ۱۵د). یعنی بیت‌یونیکس
        # endTime را روی زمانِ «بسته‌شدن» کندل می‌سنجد (open+step ≤ endTime).
        # با endTime=oldest هر سه تفسیر درست جواب می‌دهد: بسته≤ → کندلِ قبلی؛
        # باز< → کندلِ قبلی؛ باز≤ → خودِ oldest که با کلیدِ زمان حذف می‌شود.
        end_ms = oldest
    return [got[t] for t in sorted(got)][-int(n):]


@perp_venue("bitunix-perp", "Bitunix Perpetual", _bitunix_url, fetch=_bitunix_fetch)
def _bitunix_perp(r):
    return _bitunix_parse(r)


@perp_venue("binance-perp", "Binance Perpetual",
            lambda s, tf, n: f"https://fapi.binance.com/fapi/v1/klines?symbol={s}"
                             f"&interval={tf}&limit={n}")
def _binance_perp(r):
    # شکل کندل فیوچرز بایننس عیناً همان اسپات است — پس هیچ‌چیز پایین‌دست
    # نمی‌فهمد کدام آمده، و همین باعث شده بود این تفاوت سال‌ها نامرئی بماند.
    return [_k(x[0], x[1], x[2], x[3], x[4], x[5]) for x in _rows(r)]


@perp_venue("mexc-perp", "MEXC Perpetual",
            lambda s, tf, n: "https://contract.mexc.com/api/v1/contract/kline/"
                             + s.replace("USDT", "_USDT")
                             + f"?interval={ {'1m':'Min1','5m':'Min5','15m':'Min15','1h':'Min60','4h':'Hour4','1d':'Day1'}[tf] }")
def _mexc_perp(r):
    # {data:{time:[],open:[],close:[],high:[],low:[],vol:[]}} — ستونی، ثانیه‌ای
    d = (r or {}).get("data") or {}
    t = d.get("time") or []
    return [_k(int(t[i]) * 1000, d["open"][i], d["high"][i], d["low"][i],
               d["close"][i], (d.get("vol") or [0] * len(t))[i])
            for i in range(len(t))]


def perp_klines(sym, tf, limit, quiet=True):
    """کندلِ **قرارداد دائمی** — همان چیزی که حمید واقعاً معامله می‌کند.

    دستور صریح حمید (۳۱ اوت): «برو توی تریدینگ‌ویو، کریپتو را انتخاب کن،
    و بعد ارز را به‌صورت پرپچوال انتخاب کن.» ممیزی نشان داد کل تحلیل
    زنده تا امروز روی کندلِ **اسپات** بود (`api/v3/klines` — سه صرافیِ
    اول همه اسپات‌اند)، در حالی که اجرا روی فیوچرز بیت‌یونیکس است.

    چرا نامرئی مانده بود: شکل کندلِ فیوچرز بایننس با اسپات یکی است، پس
    هیچ لایه‌ای پایین‌دست نمی‌توانست بفهمد کدام را گرفته.

    چرا مهم است — و چرا هنوز جایگزینِ خودکارِ اسپات نشده: قیمتِ پرپ با
    اسپات پایه (basis) دارد، ویک‌های لیکوییدیشن دارد که اسپات ندارد، و
    حجمش کلاً ابزار دیگری است. یعنی سطح‌ها، اردر بلاک‌ها و استاپ‌ها روی
    دو نمودار **جای متفاوتی** می‌افتند. اندازهٔ این تفاوت باید سنجیده
    شود نه حدس زده (`hamid/perp_vs_spot.py`)؛ کلِ دفترِ تاریخی هم روی
    اسپات ساخته شده و عوض‌کردنِ بی‌سنجشِ منبع، آن تاریخ را بی‌معنا
    می‌کند. پس فعلاً این تابع **در دسترس** است و مقایسه‌اش اجرا می‌شود؛
    سوییچِ منبعِ تحلیل تصمیم صریح حمید است (قانون ۰۳)."""
    errs = []
    for v in PERP_VENUES:
        try:
            if v.get("fetch"):
                rows = v["fetch"](sym, tf, limit)[-limit:]
            else:
                rows = v["parse"](_json(v["url"](sym, tf, limit)))[-limit:]
        except Exception as e:                       # noqa: BLE001 - صرافی بعدی
            errs.append(f"{v['id']}: {type(e).__name__}")
            continue
        if sane(rows, limit):
            _used["klines"] = v["id"]
            if not quiet:
                print(f"  perp klines {sym} {tf} ← {v['label']}", flush=True)
            return rows
        # دلیلِ رد همراه می‌آید (کاوش ۶: TRUMPUSDT روی دو صرافی «insane» بود
        # بی‌آنکه معلوم باشد چرا — عددِ بی‌دلیل قابل رفع نیست).
        errs.append(f"{v['id']}: insane({sane_why(rows, limit)})")
    raise RuntimeError(f"perp klines {sym} {tf}: " + " · ".join(errs))


CANDLE_SOURCE = os.environ.get("LIAM9_CANDLES", "spot").strip().lower()


def klines(sym, tf, limit, quiet=True):
    """کندل با ترجیحِ محیط — نقطهٔ واحدِ سوییچ منبع (دستور حمید، ۲ سپتامبر).

    `LIAM9_CANDLES=perp` → اول قرارداد دائمی (بیت‌یونیکس، بعد بقیهٔ پرپ‌ها)،
    اسپات فقط پشتیبان؛ پیش‌فرض همان اسپاتِ تاریخی. چون ۴۰+ مصرف‌کننده
    (چرخه، دفتر پیپر، سطوح، اردر بلاک…) همین تابع را صدا می‌زنند، سوییچ
    این‌جاست تا یک سیگنال از اول تا تسویه روی **یک** منبع بماند و هیچ
    مصرف‌کننده‌ای بی‌کندل نشود («گزینهٔ جایگزین همیشه باید وجود داشته باشد»).
    منبعِ واقعاً استفاده‌شده در `used()["klines"]` است و روی دفتر سیگنال
    (`candle_src`) ثبت می‌شود تا ماشین شبانه دو منبع را جدا بسنجد."""
    if CANDLE_SOURCE == "perp":
        try:
            return perp_klines(sym, tf, limit, quiet=quiet)
        except Exception as e:                       # noqa: BLE001 - پشتیبان اسپات
            if not quiet:
                print(f"  perp نشد ({e}) → اسپات", flush=True)
    return spot_klines(sym, tf, limit, quiet=quiet)


klines_pref = klines          # نام قدیمی (۲ سپتامبر صبح) — همان تابع


def spot_klines(sym, tf, limit, quiet=True):
    """Candles from the first **spot** venue that gives a full, sane series.

    مرز صادقانه (۳۱ اوت): این مسیر اسپات است. مسیر قرارداد دائمی
    `perp_klines` است — تفاوتشان و دلیلِ جدانگه‌داشتنشان آن‌جا نوشته شده.
    `perp_vs_spot` عمداً این را صدا می‌زند، نه `klines`، تا مقایسه با سوییچ
    روشن هم معنا داشته باشد."""
    errs = []
    order = [v for v in VENUES if _available(v["id"])] or VENUES
    for v in order:
        try:
            rows = v["parse"](_json(v["url"](sym, tf, limit)))[-limit:]
        except Exception as e:                       # noqa: BLE001 - next venue
            errs.append(f"{v['id']}: {type(e).__name__}")
            _note_failure(v["id"])
            continue
        if not sane(rows, limit):
            errs.append(f"{v['id']}: {len(rows)} rows, rejected")
            _note_failure(v["id"])
            continue
        _note_success(v["id"])
        if _used["klines"] != v["id"]:
            _used["klines"] = v["id"]
            if not quiet:
                print(f"candles from {v['label']}")
        return rows
    raise RuntimeError(f"{sym} {tf}: no venue answered — {'; '.join(errs[:8])}")


def tickers(quiet=True):
    """24h volume per pair, from the first venue that answers."""
    errs = []
    for vid, fn in TICKERS:
        try:
            rows = fn()
        except Exception as e:                       # noqa: BLE001 - next venue
            errs.append(f"{vid}: {type(e).__name__}")
            continue
        rows = [r for r in rows if r["symbol"].endswith("USDT")]
        if len(rows) < 50:
            errs.append(f"{vid}: only {len(rows)} pairs")
            continue
        if _used["tickers"] != vid:
            _used["tickers"] = vid
            if not quiet:
                print(f"tickers from {vid}")
        return rows
    raise RuntimeError("no venue served tickers — " + "; ".join(errs[:6]))


if __name__ == "__main__":
    t0 = time.time()
    ts = tickers(quiet=False)
    print(f"{len(ts)} USDT pairs")
    kl = klines("BTCUSDT", "15m", 420, quiet=False)
    print(f"{len(kl)} candles, last close {kl[-1][4]}, "
          f"{'oldest→newest' if kl[0][0] < kl[-1][0] else 'REVERSED'}")
    print(f"venues used: {used()}  in {time.time() - t0:.1f}s")
