"""ایجنت گشت صرافی‌ها — همان کاری که حمید اول هر نشست می‌کند (۲۶ اوت).

«یک ایجنت می‌خوام که بره توی صرافی‌های مختلف بگرده لحظه‌ای... تاپ گینرها،
تاپ لوزرها... صد ارز برتر صرافی‌ها رو میانگین بگیره و در اختیار من بذاره.»

از چند صرافی (بایننس، MEXC، کوکوین، گیت، OKX) و کوین‌گکو، تیکر ۲۴ساعته
می‌گیرد: تغییر٪ و حجم دلاری. بعد برای هر ارز:
- **میانگین رتبهٔ حجم** بین منابعی که آن را دارند (خواستهٔ صریح: میانگین).
- برچسب گینر/لوزر برتر در هر منبع.
- شرط اعتبار: حداقل ۲ منبع مستقل — عددِ تک‌منبعی وارد واچ‌لیست نمی‌شود.

خروجی: signals/watchlist.json — واچ‌لیست روز با دلیلِ هر ردیف. تلگرام
نمی‌فرستد؛ خوراکِ اتاق‌هاست (اسکن/رادار/تحلیل) نه پیام.

مرز صادقانه: خبر/هایلایت (توکن‌سوزی، آزادسازی، لانچ) API کلیددار
می‌خواهد؛ تا کلیدش نیامده ستون خبر ادعا نمی‌شود (قانون ۱).

اجرا:  python3 -m hamid.scout
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

OUT = ROOT / "signals" / "watchlist.json"
STABLES = ("USDC", "FDUSD", "TUSD", "DAI", "BUSD", "USDE", "USD1", "USDP")
MIN_SOURCES = 2
TOP_N = 100
GAINER_TOP = 20


def _json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "liam9-scout/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _row(sym, chg, vol):
    sym = (sym or "").upper()
    if not sym.endswith("USDT") or any(sym.startswith(s) for s in STABLES):
        return None
    if vol is None:
        return None
    return {"sym": sym, "chg": chg, "vol": vol}


def _src_binance():
    return [_row(x.get("symbol"), _f(x.get("priceChangePercent")),
                 _f(x.get("quoteVolume")))
            for x in _json("https://api.binance.com/api/v3/ticker/24hr")]


def _src_mexc():
    # مستندات MEXC: priceChangePercent کسری است (0.05 = ۵٪) — بی‌حدس ×۱۰۰
    out = []
    for x in _json("https://api.mexc.com/api/v3/ticker/24hr"):
        c = _f(x.get("priceChangePercent"))
        out.append(_row(x.get("symbol"), c * 100 if c is not None else None,
                        _f(x.get("quoteVolume"))))
    return out


def _src_kucoin():
    d = _json("https://api.kucoin.com/api/v1/market/allTickers")
    rows = (d.get("data") or {}).get("ticker") or []
    return [_row(x.get("symbol", "").replace("-", ""),
                 (_f(x.get("changeRate")) or 0) * 100, _f(x.get("volValue")))
            for x in rows]


def _src_gate():
    return [_row(x.get("currency_pair", "").replace("_", ""),
                 _f(x.get("change_percentage")), _f(x.get("quote_volume")))
            for x in _json("https://api.gateio.ws/api/v4/spot/tickers")]


def _src_okx():
    d = _json("https://www.okx.com/api/v5/market/tickers?instType=SPOT")
    out = []
    for x in d.get("data") or []:
        last, opn = _f(x.get("last")), _f(x.get("open24h"))
        chg = ((last - opn) / opn * 100) if last and opn else None
        out.append(_row(x.get("instId", "").replace("-", ""), chg,
                        _f(x.get("volCcy24h"))))
    return out


def _src_coingecko():
    rows = _json("https://api.coingecko.com/api/v3/coins/markets"
                 "?vs_currency=usd&order=market_cap_desc&per_page=250&page=1"
                 "&price_change_percentage=24h")
    return [_row((x.get("symbol") or "") + "USDT",
                 _f(x.get("price_change_percentage_24h")),
                 _f(x.get("total_volume"))) for x in rows]


SOURCES = [("binance", _src_binance), ("mexc", _src_mexc),
           ("kucoin", _src_kucoin), ("gate", _src_gate),
           ("okx", _src_okx), ("coingecko", _src_coingecko)]


def build(per_source):
    """{src: [row,...]} → واچ‌لیست میانگین‌گیری‌شده. خالص و آزمون‌پذیر."""
    book = {}
    for src, rows in per_source.items():
        rows = [r for r in rows if r]
        by_vol = sorted(rows, key=lambda r: -r["vol"])
        vol_rank = {r["sym"]: i + 1 for i, r in enumerate(by_vol)}
        with_chg = [r for r in rows if r["chg"] is not None]
        gain_rank = {r["sym"]: i + 1 for i, r in enumerate(
            sorted(with_chg, key=lambda r: -r["chg"]))}
        lose_rank = {r["sym"]: i + 1 for i, r in enumerate(
            sorted(with_chg, key=lambda r: r["chg"]))}
        for r in rows:
            e = book.setdefault(r["sym"], {"sym": r["sym"], "srcs": [],
                                           "vol_ranks": [], "chgs": [],
                                           "tags": []})
            e["srcs"].append(src)
            e["vol_ranks"].append(vol_rank[r["sym"]])
            if r["chg"] is not None:
                e["chgs"].append(r["chg"])
            g, l = gain_rank.get(r["sym"]), lose_rank.get(r["sym"])
            if g and g <= GAINER_TOP:
                e["tags"].append(f"گینر#{g}@{src}")
            if l and l <= GAINER_TOP:
                e["tags"].append(f"لوزر#{l}@{src}")
    rows = []
    for e in book.values():
        if len(e["srcs"]) < MIN_SOURCES:
            continue                       # عدد تک‌منبعی اعتبار ندارد
        avg_vol_rank = sum(e["vol_ranks"]) / len(e["vol_ranks"])
        chg = (sorted(e["chgs"])[len(e["chgs"]) // 2] if e["chgs"] else None)
        best_g = min((int(t.split("#")[1].split("@")[0])
                      for t in e["tags"] if t.startswith("گینر")), default=None)
        best_l = min((int(t.split("#")[1].split("@")[0])
                      for t in e["tags"] if t.startswith("لوزر")), default=None)
        score = (len(e["srcs"]) * 10
                 + max(0.0, (300 - avg_vol_rank)) / 10
                 + (max(0, GAINER_TOP + 1 - best_g) * 2 if best_g else 0)
                 + (max(0, GAINER_TOP + 1 - best_l) if best_l else 0))
        rows.append({"sym": e["sym"], "score": round(score, 1),
                     "sources": len(e["srcs"]), "avg_vol_rank":
                     round(avg_vol_rank, 1), "chg24_med":
                     (round(chg, 2) if chg is not None else None),
                     "tags": e["tags"][:6]})
    rows.sort(key=lambda r: (-r["score"], r["avg_vol_rank"]))
    return rows[:TOP_N]


def run(quiet=False):
    per, errs = {}, {}
    for name, fn in SOURCES:
        try:
            rows = [r for r in fn() if r]
            if len(rows) >= 50:
                per[name] = rows
            else:
                errs[name] = f"فقط {len(rows)} جفت"
        except Exception as e:                       # noqa: BLE001
            errs[name] = type(e).__name__
    if len(per) < MIN_SOURCES:
        raise SystemExit(f"گشت: فقط {len(per)} منبع جواب داد — {errs}")
    rows = build(per)
    out = {"generated": int(time.time() * 1000),
           "sources_ok": sorted(per), "sources_err": errs,
           "universe": sum(len(v) for v in per.values()),
           "rows": rows,
           "note": ("واچ‌لیست گشت چندصرافی — میانگین رتبهٔ حجم و برچسب "
                    "گینر/لوزر؛ حداقل ۲ منبع بر هر ردیف. خوراک اتاق‌هاست، "
                    "سیگنال نیست. ستون خبر تا آمدن منبع کلیددار ادعا "
                    "نمی‌شود (قانون ۱).")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    if not quiet:
        print(f"گشت: {len(per)} منبع، {len(rows)} ردیف → {OUT}")
        for r in rows[:8]:
            print(f"  {r['sym']}: امتیاز {r['score']} · منابع {r['sources']} "
                  f"· رتبهٔ حجم {r['avg_vol_rank']} · {r['chg24_med']}٪ "
                  f"· {', '.join(r['tags'][:2])}")
    return out


if __name__ == "__main__":
    run()
