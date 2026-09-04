#!/usr/bin/env python3
"""اتاق توزیع اطلاعات (E27) — دسته‌بندی پیش از توزیع (دستور حمید، ۳ سپتامبر).

حمید: «ایجنت این اتاق باید قبل از این‌که اطلاعات را بین اتاق‌ها توزیع کند
اول تمامی اطلاعات و نحوهٔ توزیع درست و حتی نوع ارز که جزو چه دسته‌ای از
ارزها هست را دسته‌بندی کند… و هر بار ارزها را با دسته‌بندی مشخص در اختیار
اتاق‌ها بگذارد.»

## دو کار، به همین ترتیب

**۱. دسته‌بندی (اول).** هر نماد کارت می‌گیرد: دستهٔ بنیادی، ردهٔ نقدشوندگی،
کلاس رفتاری نسبت به بیت‌کوین، قابل‌معامله بودن، و هشدارهای دسته‌ای
(`hamid/taxonomy.py`). نمادِ بی‌کارت به هیچ اتاقی تحویل نمی‌شود — این خودِ
دستورِ حمید است: «هر بار ارزها را با دسته‌بندی مشخص در اختیار اتاق‌ها بگذارد».

**۲. توزیع (بعد).** هر رویداد به اتاقِ صاحبش می‌رود. نگاشت `ROUTES` فرمالِ
همان جدولی است که تا امروز فقط در CLAUDE.md نثر بود؛ نثر مسیر نمی‌سازد.

## قاعده‌ای که این اتاق را از یک صفِ ساده جدا می‌کند

**فیلترِ دسته‌ای پیش از تحویل.** هر مسیر می‌گوید چه دسته‌ای برایش معنا
دارد. رویدادِ پامپ روی یک استیبل به اتاق پامپ نمی‌رود (دِپگ است، پامپ
نیست). ستاپ روی سهام‌توکن آخر هفته به اتاق ساختار نمی‌رود (بازارش بسته
است). این حذف‌ها **با دلیل ثبت می‌شوند** (`dropped`) نه بی‌صدا — چیزی که
بی‌صدا حذف شود، بعداً کسی نمی‌فهمد چرا نیامد.

## مرز

این اتاق تصمیم معاملاتی نمی‌گیرد و هیچ آستانه‌ای را عوض نمی‌کند. فقط
دسته می‌زند و مسیر می‌دهد. خروجی: `signals/router.json` (ردیف قرارداد E27).
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import taxonomy as TX                      # noqa: E402

OUT = ROOT / "signals" / "router.json"
LATEST = ROOT / "signals" / "latest.json"
WATCHLIST = ROOT / "signals" / "watchlist.json"
SENS = ROOT / "signals" / "btc-sensitivity.json"

# ── نگاشت رویداد → اتاق (فرمالِ جدول CLAUDE.md) ──────────────────────────
# rooms: صاحبان رویداد · sectors: دسته‌هایی که این مسیر برایشان معنا دارد
# (None = همه) · why: چرا این مسیر وجود دارد.
ROUTES = {
    "PRICE_WHERE": {"rooms": ["E07", "E08"], "sectors": None,
                    "why": "«قیمت کجاست» و اعتبار ستاپ — ساختار و SMC"},
    "BIG_WICK": {"rooms": ["E10", "E08"], "sectors": None,
                 "why": "ویک بزرگ پیش از سیگنال — نقدینگی و اردر بلاک"},
    "BTC_SHOCK": {"rooms": ["E06", "E03", "E04", "E16"], "sectors": None,
                  "why": "حرکت ناگهانی بیت‌کوین — بستر، دامیننس، ریسک"},
    "PUMP": {"rooms": ["E12", "E14"], "sectors": ["meme", "ai", "gaming", "l1", "l2",
                                                   "defi", "rwa", "depin", "unknown",
                                                   "major", "exchange", "oracle",
                                                   "storage", "privacy", "interop",
                                                   "payment", "lst"],
             "why": "پامپ/دامپ معنادار — لید-لگ و خبر. استیبل/رپد پامپ ندارند (دِپگ دارند)"},
    "DOMINANCE_SHIFT": {"rooms": ["E03", "E04", "E05", "E16"], "sectors": None,
                        "why": "چرخش دامیننس — بستر و ریسک"},
    "NEWS": {"rooms": ["E14", "E05"], "sectors": None,
             "why": "خبر و کاتالیزور — بورد خبر"},
    "OB_APPROACHING": {"rooms": ["E08"], "sectors": None,
                       "why": "نزدیک‌شدن به اردر بلاک — اتاق OB"},
    "BREAKER_DETECTED": {"rooms": ["E08", "E07"], "sectors": None,
                         "why": "بریکر — OB و ساختار"},
    "SETUP_READY": {"rooms": ["E17", "E16"], "sectors": None,
                    "why": "ستاپ آماده — کمیتهٔ سیگنال و ریسک"},
    "TRADE_CLOSED": {"rooms": ["E20", "E21"], "sectors": None,
                     "why": "تسویه — بازبینی پس از معامله و حافظه"},
    "DATA_ANOMALY": {"rooms": ["E02"], "sectors": None,
                     "why": "دادهٔ مشکوک/ناسازگار — کیفیت داده"},
    "REPEATED_FAILURE": {"rooms": ["E22", "E20"], "sectors": None,
                         "why": "۳+ شکست همان الگو — تحقیق و بازبینی"},
    "SESSION_EVENT": {"rooms": ["E05", "E01"], "sectors": ["stocktoken"],
                      "why": "باز/بستهٔ بازار امریکا — فقط سهام‌توکن‌ها"},
    "DEPEG": {"rooms": ["E02", "E05"], "sectors": ["stable"],
              "why": "دِپگ استیبل — کیفیت داده و کلان. مسیرِ جدا از پامپ"},
}

ROOM_NAMES = {
    "E01": "جهان نمادها", "E02": "کیفیت داده", "E03": "دامیننس تتر",
    "E04": "دامیننس بیت‌کوین", "E05": "رژیم کلان", "E06": "تحلیل بیت‌کوین",
    "E07": "ساختار", "E08": "SMC و اردر بلاک", "E10": "نقدینگی و مشتقه",
    "E12": "لید-لگ و پامپ", "E14": "خبر و کاتالیزور", "E16": "ریسک",
    "E17": "کمیتهٔ سیگنال", "E20": "بازبینی پس از معامله", "E21": "حافظه",
    "E22": "بهبود و تحقیق",
}


def _j(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def universe(latest=None, watchlist=None, coverage=None):
    """جهان نمادهای امروز — از هر سه منبعی که واقعاً نماد دارند.

    مرزِ شکل: در `latest.json` میدان `symbols` یک **عدد** است (شمار اسکن)،
    نه فهرست؛ فهرستِ واقعی در `signals`/`watch` و در دفتر پوششِ غلتان
    (`scan-coverage.seen`) است. کشفِ ۳ سپتامبر — اولین اجرا با فرضِ فهرست
    بودن ترکید. رتبه فقط وقتی داده می‌شود که منبعش ترتیب معنادار داشته باشد.
    """
    syms, rank = [], {}

    def add(s, r=None):
        if s and s not in rank:
            rank[s] = r
            syms.append(s)

    d = _j(latest or LATEST, {}) or {}
    raw = d.get("symbols")
    if isinstance(raw, list):                        # شکل قدیمی/آینده
        for i, r in enumerate(raw):
            add(r.get("symbol") if isinstance(r, dict) else r, i + 1)
    for row in (d.get("signals") or []) + (d.get("watch") or []):
        if isinstance(row, dict):
            add(row.get("sym"))
    cov = _j(coverage or (ROOT / "signals" / "scan-coverage.json"), {}) or {}
    for s in sorted((cov.get("seen") or {}).keys()):
        add(s)
    w = _j(watchlist or WATCHLIST, {}) or {}
    for r in (w.get("rows") or w.get("watchlist") or []):
        add(r.get("sym") if isinstance(r, dict) else r)
    return syms, rank


def cards(syms, rank=None, sens=None, vol=None):
    """کارت هر نماد — همان چیزی که با هر تحویل همراه می‌شود."""
    rank = rank or {}
    sens = sens if sens is not None else ((_j(SENS, {}) or {}).get("coins") or {})
    return {s: TX.classify(s, rank.get(s), sens, vol) for s in syms}


def route(event, sym=None, card=None, routes=None):
    """یک رویداد را به اتاق‌هایش می‌دهد — یا با دلیل رد می‌کند.

    خروجی: {"event", "sym", "sector", "rooms", "dropped": [...], "why"}
    """
    routes = routes or ROUTES
    spec = routes.get(event)
    if not spec:
        return {"event": event, "sym": sym, "rooms": [], "dropped": ["رویداد ناشناخته"],
                "why": "این رویداد در نگاشت توزیع نیست — اتاقی برایش تعریف نشده"}
    sec = (card or {}).get("sector") if card else (TX.sector(sym) if sym else None)
    if sym and card is None:
        card = TX.classify(sym)
        sec = card["sector"]
    ok_sectors = spec.get("sectors")
    if sym and ok_sectors is not None and sec not in ok_sectors:
        return {"event": event, "sym": sym, "sector": sec, "rooms": [],
                "dropped": [f"دستهٔ «{sec}» برای این مسیر معنا ندارد"],
                "why": spec["why"]}
    dropped = []
    if sym and card and card.get("session_bound") and event in ("SETUP_READY", "PRICE_WHERE"):
        dropped.append("سهام‌توکن — تحویل فقط در ساعت بازار امریکا معنا دارد")
    return {"event": event, "sym": sym, "sector": sec, "rooms": list(spec["rooms"]),
            "dropped": dropped, "why": spec["why"]}


def dispatch(events, cardmap=None):
    """دستهٔ رویداد → صفِ هر اتاق. رویدادِ ردشده گم نمی‌شود، ثبت می‌شود."""
    cardmap = cardmap or {}
    queues, drops = {}, []
    for ev in events or []:
        name = ev.get("event") if isinstance(ev, dict) else str(ev)
        sym = ev.get("sym") if isinstance(ev, dict) else None
        r = route(name, sym, cardmap.get(sym))
        if not r["rooms"]:
            drops.append(r)
            continue
        for room in r["rooms"]:
            queues.setdefault(room, []).append(
                {"event": name, "sym": sym, "sector": r.get("sector"),
                 "card": cardmap.get(sym), "dropped": r["dropped"]})
    return {"queues": queues, "dropped": drops}


def build(latest=None, watchlist=None, sens=None, now_ms=None, coverage=None):
    syms, rank = universe(latest, watchlist, coverage)
    cm = cards(syms, rank, sens)
    cov = TX.coverage(syms)
    tradable = [s for s, c in cm.items() if c["tradable"]]
    by_sector = {}
    for s, c in cm.items():
        by_sector.setdefault(c["sector"], []).append(s)
    return {
        "generated": int(now_ms or time.time() * 1000), "panel": "لیام تریدر ۹",
        "owner": "E27 — اتاق توزیع اطلاعات",
        "rule": "اول دسته‌بندی، بعد توزیع. نمادِ بی‌کارت به هیچ اتاقی نمی‌رود.",
        "coverage": cov,
        "counts": {"universe": len(syms), "tradable": len(tradable),
                   "excluded": len(syms) - len(tradable)},
        "by_sector": {k: sorted(v)[:40] for k, v in
                      sorted(by_sector.items(), key=lambda kv: -len(kv[1]))},
        "sector_sizes": {k: len(v) for k, v in
                         sorted(by_sector.items(), key=lambda kv: -len(kv[1]))},
        "routes": {k: {"rooms": v["rooms"], "room_names": [ROOM_NAMES.get(r, r) for r in v["rooms"]],
                       "sectors": v["sectors"], "why": v["why"]}
                   for k, v in ROUTES.items()},
        "rooms": ROOM_NAMES,
        "excluded_examples": sorted(s for s, c in cm.items() if not c["tradable"])[:20],
        "unknown_examples": sorted(s for s, c in cm.items() if c["sector"] == "unknown")[:20],
        "boundary": "این اتاق تصمیم معاملاتی نمی‌گیرد و آستانه‌ای را عوض نمی‌کند؛ "
                    "فقط دسته می‌زند و مسیر می‌دهد. حذف‌ها با دلیل ثبت می‌شوند.",
    }


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    d = build()
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"نوشته شد: {OUT.name}")
    c = d["counts"]
    print(f"اتاق توزیع: {c['universe']} نماد · {c['tradable']} قابل‌معامله · "
          f"{c['excluded']} کنارگذاشته · پوشش دسته {d['coverage']['pct']}٪")
    for sec, n in list(d["sector_sizes"].items())[:12]:
        print(f"  {sec:<12} {n}")
    if d["unknown_examples"]:
        print(f"  ناشناخته (نمونه): {'، '.join(d['unknown_examples'][:8])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
