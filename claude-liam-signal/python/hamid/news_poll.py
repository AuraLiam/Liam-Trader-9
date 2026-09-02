"""نظرسنجی خبر — خبر فقط دیدگاه است، نه تصمیم (دستور حمید، ۲ سپتامبر).

حمید: «خبرها فقط برای تصمیم درست و دادن دیدگاه به تحلیلگران مجموعهٔ خودمان
استفاده می‌شود… نباید خبرها در تصمیم اصلی تأثیر داشته باشد… ولی حرف
بزرگان بازار می‌تواند بر مبنای اطلاعاتی باشد که زودتر از بقیه دارند. پس
خبرها و صحبت‌ها و سوشال را بین ایجنت‌ها به نظرسنجی می‌گذاریم و بررسی
می‌کنیم هر ایجنت چه برداشتی می‌کند؛ بر اساس میزان تشخیص درستِ هر ایجنت
وزن می‌دهیم و کم‌کم، بر اساس اهمیت و نوع خبر، کنار تصمیم‌های مهم
استفاده می‌کنیم.»

## چرخهٔ ماژول

۱. **آیتم**: هر تیتر دسته‌بندی‌شدهٔ signals/news.json، هر رویداد تقویم
   ۲۴ ساعت آینده، و هر شاهد فومو (اپ) — با شناسهٔ پایدار.
۲. **نظرسنجی**: هر ایجنتِ فهرست PANEL دربارهٔ هر آیتم برداشتش را می‌دهد:
   جهت (UP/DOWN/FLAT)، دامنه (BTC یا نماد)، افق، اطمینان، دلیل، ابطال‌کننده.
   دو روش، جدا نمره می‌گیرند:
   - `rule`: خوانندهٔ قطعی هر ایجنت (پایتون؛ همیشه هست).
   - `llm`: همان ایجنت‌ها با مدل زبانی (فقط وقتی ANTHROPIC_API_KEY هست؛
     یک فراخوانی برای هر آیتم، همهٔ ایجنت‌ها با هم — قانون ۰۶: نه روی
     تیک، نه روی هر نماد؛ فقط تفسیر خبر، هر ۳ ساعت).
   «چیزی نمی‌گویم» (None) جواب معتبر است و شمرده می‌شود.
۳. **نمره**: وقتی افق رسید، با کندل واقعی: UP درست است اگر بازده از باند
   نویز بالاتر رفت، DOWN قرینه، FLAT اگر داخل باند ماند.
۴. **کارنامه**: هر ایجنت × روش × دستهٔ خبر: n، اصابت، CI ویلسون. وزن
   پیشنهادی فقط وقتی کران پایین CI از ۰.۵ گذشت و سقف لایهٔ اجتماعی ۵٪
   (قانون ۱۱). زیر MIN_N عدد گزارش نمی‌شود.
۵. **ردپا**: روی هر سیگنال فقط `news_align` (اجماعِ وزن‌دار هم‌جهت/خلاف/
   بی‌وزن) ثبت می‌شود تا ماشین بونفرونی شبانه بسنجد. هیچ دروازه و امتیازی.

هیچ‌کدام از این‌ها وارد تصمیم نمی‌شود مگر از مسیر قانون ۰۳ (CI بالای
صفر + تأیید حمید).
"""
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRAIN = ROOT / "brain" / "news-poll"
POLLS = BRAIN / "polls.jsonl"              # append-only، کلید item|agent|method
OUTCOMES = BRAIN / "outcomes.jsonl"        # append-only، کلید item|agent|method|horizon
OUT = ROOT / "signals" / "news-poll.json"
NEWS = ROOT / "signals" / "news.json"
FOMO = ROOT / "signals" / "fomo.json"
PANEL = "لیام تریدر ۹"
ENGINE = "E14"

# ایجنت‌هایی که دربارهٔ خبر نظر می‌دهند (نه همهٔ ۲۷ تا — بقیه دامنه‌شان خبر نیست)
POLLED = {
    "E03": "USDT.D — دامیننس تتر؛ جریان به/از استیبل‌کوین",
    "E04": "BTC.D — دامیننس بیت‌کوین؛ چرخش بین بیت‌کوین و آلت",
    "E05": "رژیم کلان — فدرال، نرخ بهره، تورم، ریسک‌آن/آف",
    "E06": "تحلیل بیت‌کوین — ETF، ماینرها، جریان نهادی",
    "E10": "نقدینگی و مشتقه — فاندینگ، OI، لیکوییدیشن",
    "E12": "لید-لگ و زنجیرهٔ پامپ — خبر توکن‌محور، لیست‌شدن، آنلاک",
    "E14": "خبر و کاتالیزور — دسته‌بندی و قطبیت پایه",
    "E16": "ریسک — پنجرهٔ رویداد، سایز، اجتناب",
    "E26": "ناظر کل — اجماع وزن‌دار بقیه (فرا-ایجنت)",
}
HORIZONS_H = (4, 24)
BAND = {"BTC": 0.004, "ALT": 0.012}          # باند نویز: زیر این، «تخت» درست است
MIN_N = 20
SOCIAL_CAP = 0.05
LLM_MODEL = os.environ.get("NEWS_POLL_MODEL", "claude-opus-5")

_BULL = ("etf inflow", "inflow", "approv", "adopt", "partnership", "rate cut", "cuts rate",
         "buyback", "accumulat", "listing", "listed", "launch", "upgrade", "burn", "record high",
         "all-time high", "bullish", "rally", "surge")
_BEAR = ("hack", "exploit", "lawsuit", "ban", "banned", "outflow", "rate increase", "rate hike",
         "hike", "liquidat", "freez", "sell-off", "selloff", "dump", "crash", "plunge", "fall",
         "bearish", "delist", "unlock", "investigat", "charge", "fraud", "default", "warrant")
_HAWK = ("rate increase", "rate hike", "hike", "hawkish", "inflation rises", "hot cpi", "higher for longer")
_DOVE = ("rate cut", "cuts rate", "dovish", "inflation cools", "cooling", "pause", "easing")


# ── ۱. آیتم‌ها ────────────────────────────────────────────────────────────
def _iid(kind, title):
    return hashlib.sha1(f"{kind}|{(title or '').strip().lower()}".encode()).hexdigest()[:12]


def _load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def collect_items(news=None, fomo=None, now_ms=None):
    """آیتم‌های قابل‌نظرسنجی. هر آیتم: id, kind, title, cat, scope, at."""
    now_ms = now_ms or int(time.time() * 1000)
    news = news if news is not None else _load(NEWS, {})
    fomo = fomo if fomo is not None else _load(FOMO, {})
    items = []
    gen = int(news.get("generated") or now_ms) if isinstance(news, dict) else now_ms
    for n in (news.get("classified") or []) if isinstance(news, dict) else []:
        if not isinstance(n, dict) or not n.get("title"):
            continue
        items.append({"id": _iid("news", n["title"]), "kind": "news", "title": n["title"],
                      "cat": n.get("cat") or "عمومی", "scope": "BTC", "at": gen})
    for e in (news.get("calendar") or []) if isinstance(news, dict) else []:
        if not isinstance(e, dict) or not e.get("title"):
            continue
        hrs = e.get("in_hours")
        if not isinstance(hrs, (int, float)) or hrs < 0 or hrs > 24:
            continue
        items.append({"id": _iid("event", f"{e['title']}|{e.get('country')}"), "kind": "event",
                      "title": f"{e['title']} ({e.get('country', '')})", "cat": "رویداد کلان",
                      "scope": "BTC", "at": gen, "in_hours": hrs})
    for w in (fomo.get("witness_recent") or []) if isinstance(fomo, dict) else []:
        if not isinstance(w, dict) or not w.get("sym") or not w.get("at"):
            continue
        if now_ms - int(w["at"]) > 86400000:
            continue
        items.append({"id": _iid("fomo", f"{w['sym']}|{w.get('kind')}|{w['at']}"), "kind": "fomo",
                      "title": f"fomo: {w['sym']} {w.get('kind')}" + (f" #{w['rank']}" if w.get("rank") else "")
                      + (f" — {w['note']}" if w.get("note") else ""),
                      "cat": "شاهد فومو", "scope": w["sym"], "at": int(w["at"]), "fomo_kind": w.get("kind")})
    # یکتا بر شناسه
    seen, out = set(), []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        out.append(it)
    return out


# ── ۲. خواننده‌های قطعی ─────────────────────────────────────────────────
def _polarity(text, bull=_BULL, bear=_BEAR):
    t = (text or "").lower()
    b = sum(1 for k in bull if k in t)
    s = sum(1 for k in bear if k in t)
    if b > s:
        return "UP", b - s
    if s > b:
        return "DOWN", s - b
    return None, 0


def _reading(agent, stance, scope, horizon_h, conf, reasons, falsifier):
    return {"agent": agent, "method": "rule", "stance": stance, "scope": scope,
            "horizon_h": horizon_h, "confidence": round(float(conf), 2),
            "reasons": list(reasons)[:4], "falsifier": falsifier}


def _r_e14(it, ctx):
    st, k = _polarity(it["title"])
    if it["kind"] == "fomo":
        return None
    if st is None:
        return _reading("E14", "FLAT", it["scope"], 24, 0.3, ["قطبیت واژگانی خنثی"],
                        "حرکت بیش از باند نویز در ۲۴س = قطبیت پایه اشتباه بود")
    return _reading("E14", st, it["scope"], 24, min(0.6, 0.35 + 0.1 * k),
                    [f"قطبیت واژگانی {st} ({k} نشانه)", f"دستهٔ خبر: {it.get('cat')}"],
                    "حرکت خلاف قطبیت بیش از باند = خبر از قبل قیمت‌گذاری شده بود")


def _r_e05(it, ctx):
    if it["kind"] == "event":
        return _reading("E05", "FLAT", "BTC", 4, 0.4,
                        [f"پنجرهٔ رویداد کلان {it.get('in_hours')} ساعت دیگر — حکم جهتی معلق"],
                        "حرکت جهت‌دار بیش از باند در ۴س = پنجره کم‌اثر بود")
    if it.get("cat") != "کلان/فدرال":
        return None
    t = it["title"].lower()
    if any(k in t for k in _HAWK):
        return _reading("E05", "DOWN", "BTC", 24, 0.45, ["لحن انقباضی (نرخ بالاتر) = ریسک‌آف"],
                        "بیت‌کوین بالاتر از باند در ۲۴س = بازار انقباض را خورده بود")
    if any(k in t for k in _DOVE):
        return _reading("E05", "UP", "BTC", 24, 0.45, ["لحن انبساطی (کاهش نرخ) = ریسک‌آن"],
                        "بیت‌کوین پایین‌تر از باند در ۲۴س = بازار انبساط را خورده بود")
    return _reading("E05", "FLAT", "BTC", 24, 0.3, ["خبر کلان بدون لحن روشن"], "حرکت بیش از باند")


def _r_e03(it, ctx):
    t = it["title"].lower()
    if not any(k in t for k in ("tether", "usdt", "stablecoin", "usdc", "circle")):
        return None
    st, _ = _polarity(it["title"])
    if st == "DOWN":
        return _reading("E03", "DOWN", "BTC", 24, 0.4, ["خبر منفی استیبل‌کوین → گریز به تتر → USDT.D بالا"],
                        "USDT.D پایین/بازار بالا در ۲۴س")
    if st == "UP":
        return _reading("E03", "UP", "BTC", 24, 0.35, ["خبر مثبت استیبل‌کوین → نقدینگی ورودی"],
                        "بازار پایین‌تر از باند")
    return None


def _r_e06(it, ctx):
    t = it["title"].lower()
    if not any(k in t for k in ("bitcoin", "btc", "etf", "miner", "halving", "microstrategy", "strategy")):
        return None
    st, k = _polarity(it["title"])
    if st is None:
        return None
    return _reading("E06", st, "BTC", 24, min(0.55, 0.35 + 0.1 * k),
                    [f"خبر مستقیم بیت‌کوین با قطبیت {st}"], "حرکت خلاف بیش از باند در ۲۴س")


def _r_e12(it, ctx):
    if it["kind"] != "fomo":
        return None
    k = it.get("fomo_kind")
    st = "UP" if k in ("buy", "trend", "top", "alert") else "DOWN" if k == "sell" else None
    if not st:
        return None
    return _reading("E12", st, it["scope"], 4, 0.35, [f"شاهد اپ fomo از نوع {k}"],
                    "حرکت خلاف بیش از باند آلت در ۴س")


def _r_e16(it, ctx):
    if it["kind"] == "event" and isinstance(it.get("in_hours"), (int, float)) and it["in_hours"] <= 6:
        return _reading("E16", "FLAT", "BTC", 4, 0.5, ["رویداد تا ۶ ساعت: سایز کوچک/اجتناب — شلاق قیمت"],
                        "دامنهٔ ۴س کمتر از باند = پنجره بی‌خطر بود")
    return None


def _r_e10(it, ctx):
    t = it["title"].lower()
    if not any(k in t for k in ("liquidat", "funding", "open interest", "leverage", "short squeeze", "long squeeze")):
        return None
    st, _ = _polarity(it["title"])
    return _reading("E10", st or "FLAT", "BTC", 4, 0.35, ["خبر مشتقه/لیکوییدیشن"], "حرکت خلاف بیش از باند")


def _r_e04(it, ctx):
    t = it["title"].lower()
    if not any(k in t for k in ("altcoin", "alt season", "ethereum", "eth ", "solana", "xrp")):
        return None
    st, _ = _polarity(it["title"])
    if st is None:
        return None
    # خبر مثبت آلت → پول به آلت → BTC.D پایین؛ ولی دامنهٔ نمره‌دهی ما قیمت BTC است
    return _reading("E04", st, "BTC", 24, 0.3, [f"خبر آلت با قطبیت {st} — هم‌بستگی بازار"], "حرکت خلاف بیش از باند")


RULE_READERS = {"E14": _r_e14, "E05": _r_e05, "E03": _r_e03, "E06": _r_e06,
                "E12": _r_e12, "E16": _r_e16, "E10": _r_e10, "E04": _r_e04}


def rule_readings(item, ctx=None):
    out = []
    for agent, fn in RULE_READERS.items():
        try:
            r = fn(item, ctx or {})
        except Exception:                            # noqa: BLE001 - خوانندهٔ خراب = سکوت، نه خطا
            r = None
        if r:
            out.append(r)
    return out


# ── ۳. خوانندهٔ مدل زبانی (فقط با کلید) ─────────────────────────────────
_SCHEMA = {
    "type": "object",
    "properties": {
        "readings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string"},
                    "stance": {"type": "string", "enum": ["UP", "DOWN", "FLAT", "ABSTAIN"]},
                    "scope": {"type": "string"},
                    "horizon_h": {"type": "integer"},
                    "confidence": {"type": "number"},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                    "falsifier": {"type": "string"},
                },
                "required": ["agent", "stance", "scope", "horizon_h", "confidence", "reasons", "falsifier"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["readings"],
    "additionalProperties": False,
}


def _llm_prompt(item, ctx):
    agents = "\n".join(f"- {a}: {d}" for a, d in POLLED.items() if a != "E26")
    return (
        "You are polling the analyst engines of a crypto trading desk about ONE news item. "
        "Each engine answers ONLY from its own domain; if the item is outside its domain it answers ABSTAIN. "
        "Stances are about the price of the scope over the horizon: UP, DOWN, FLAT (inside noise band), ABSTAIN. "
        "Insiders may act on such news before the crowd, so consider whether it is already priced in. "
        "Return one reading per engine.\n\n"
        f"Engines:\n{agents}\n\n"
        f"Item kind: {item['kind']}\nCategory: {item.get('cat')}\nScope: {item['scope']}\n"
        f"Title: {item['title']}\n"
        f"Market context: fear/greed={ctx.get('fear')} funding_avg={ctx.get('funding_avg')} "
        f"crowd_heat={ctx.get('heat')}\n"
        "horizon_h must be 4 or 24. confidence in [0,1]. reasons: max 3 short strings. "
        "falsifier: what would prove the reading wrong."
    )


def llm_readings(item, ctx=None, client=None):
    """برداشت مدل زبانی برای همهٔ ایجنت‌ها در یک فراخوانی. بی‌کلید = [] با دلیل."""
    ctx = ctx or {}
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return [], "بدون ANTHROPIC_API_KEY — روش llm اجرا نشد"
        try:
            import anthropic                          # noqa: WPS433
            client = anthropic.Anthropic()
        except Exception as e:                       # noqa: BLE001
            return [], f"کتابخانهٔ anthropic در دسترس نیست ({type(e).__name__})"
    try:
        resp = client.messages.create(
            model=LLM_MODEL, max_tokens=2000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content": _llm_prompt(item, ctx)}])
        if getattr(resp, "stop_reason", None) == "refusal":
            return [], "پاسخ مدل رد شد (refusal)"
        text = next(b.text for b in resp.content if getattr(b, "type", "") == "text")
        data = json.loads(text)
    except Exception as e:                           # noqa: BLE001
        return [], f"فراخوانی مدل نشد ({type(e).__name__})"
    out = []
    for r in data.get("readings") or []:
        if not isinstance(r, dict) or r.get("agent") not in POLLED or r.get("stance") == "ABSTAIN":
            continue
        if r.get("stance") not in ("UP", "DOWN", "FLAT"):
            continue
        out.append({"agent": r["agent"], "method": "llm", "stance": r["stance"],
                    "scope": (r.get("scope") or item["scope"]).upper(),
                    "horizon_h": 4 if int(r.get("horizon_h") or 24) <= 4 else 24,
                    "confidence": round(max(0.0, min(1.0, float(r.get("confidence") or 0))), 2),
                    "reasons": [str(x)[:160] for x in (r.get("reasons") or [])][:3],
                    "falsifier": str(r.get("falsifier") or "")[:200]})
    return out, ""


# ── ۴. دفتر نظرسنجی ─────────────────────────────────────────────────────
def _rows(p):
    out = []
    if Path(p).exists():
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if isinstance(r, dict):
                    out.append(r)
            except Exception:                        # noqa: BLE001
                continue
    return out


def _append(p, rows):
    if not rows:
        return
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with Path(p).open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def poll(items, ctx=None, use_llm=True, client=None, now_ms=None):
    """نظرسنجی روی آیتم‌های تازه. برمی‌گرداند (ردیف‌های تازه، یادداشت llm)."""
    now_ms = now_ms or int(time.time() * 1000)
    have = {(r.get("item"), r.get("agent"), r.get("method")) for r in _rows(POLLS)}
    new, llm_note = [], ""
    for it in items:
        readings = rule_readings(it, ctx)
        if use_llm:
            lr, note = llm_readings(it, ctx, client=client)
            readings += lr
            llm_note = llm_note or note
        for r in readings:
            key = (it["id"], r["agent"], r["method"])
            if key in have:
                continue
            have.add(key)
            new.append({"item": it["id"], "kind": it["kind"], "cat": it.get("cat"), "title": it["title"][:160],
                        "at": now_ms, "item_at": it["at"], **r})
    _append(POLLS, new)
    return new, llm_note


# ── ۵. نمره با کندل واقعی ──────────────────────────────────────────────
def forward_return(candles, at_ms, horizon_h):
    after = [c for c in candles if c[0] >= at_ms]
    if not after:
        return None
    end_t = at_ms + horizon_h * 3600 * 1000
    win = [c for c in after if c[0] <= end_t]
    if not win:
        return None
    bar_ms = (after[1][0] - after[0][0]) if len(after) > 1 else 3600000
    if win[-1][0] < end_t - bar_ms:
        return None                                  # افق کامل نشده
    p0 = float(after[0][1])
    return round(float(win[-1][4]) / p0 - 1, 5) if p0 > 0 else None


def grade(stance, ret, scope):
    band = BAND["BTC"] if scope == "BTC" else BAND["ALT"]
    if stance == "UP":
        return ret > band
    if stance == "DOWN":
        return ret < -band
    return abs(ret) <= band


def score(klines=None, now_ms=None):
    now_ms = now_ms or int(time.time() * 1000)
    if klines is None:
        import sources                                # noqa: WPS433
        klines = lambda sym: sources.klines(sym, "1h", 200)   # noqa: E731
    done = {(r.get("item"), r.get("agent"), r.get("method")) for r in _rows(OUTCOMES)}
    new, cache = [], {}
    for r in _rows(POLLS):
        key = (r.get("item"), r.get("agent"), r.get("method"))
        if key in done or not r.get("stance"):
            continue
        h = int(r.get("horizon_h") or 24)
        if now_ms < int(r["at"]) + h * 3600 * 1000:
            continue
        sym = "BTCUSDT" if r.get("scope") in (None, "BTC", "MARKET") else r["scope"]
        if sym not in cache:
            try:
                cache[sym] = klines(sym) or []
            except Exception:                        # noqa: BLE001
                cache[sym] = []
        ret = forward_return(cache[sym], int(r["at"]), h)
        if ret is None:
            continue
        new.append({**{k: r.get(k) for k in ("item", "agent", "method", "stance", "scope", "cat", "kind", "horizon_h")},
                    "ret": ret, "hit": bool(grade(r["stance"], ret, "BTC" if sym == "BTCUSDT" else "ALT")),
                    "scored_at": now_ms})
    _append(OUTCOMES, new)
    return len(new)


# ── ۶. کارنامه و وزن ────────────────────────────────────────────────────
def _wilson(k, n, z=1.96):
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def scoreboard(rows=None):
    """{agent|method: {n, hit, ci, weight, why, by_cat: {...}}} — زیر MIN_N بی‌عدد."""
    rows = rows if rows is not None else _rows(OUTCOMES)
    acc = {}
    for r in rows:
        k = f"{r.get('agent')}|{r.get('method')}"
        a = acc.setdefault(k, {"n": 0, "k": 0, "by_cat": {}})
        a["n"] += 1
        a["k"] += 1 if r.get("hit") else 0
        c = a["by_cat"].setdefault(r.get("cat") or "—", {"n": 0, "k": 0})
        c["n"] += 1
        c["k"] += 1 if r.get("hit") else 0
    out = {}
    for k, a in acc.items():
        n, hits = a["n"], a["k"]
        if n < MIN_N:
            out[k] = {"n": n, "hit": None, "ci": None, "weight": 0.0,
                      "why": f"n={n} < {MIN_N} — کارنامه هنوز عدد ندارد", "by_cat": a["by_cat"]}
            continue
        ci = _wilson(hits, n)
        hit = round(hits / n, 3)
        if ci[0] > 0.5:
            w = round(min(SOCIAL_CAP, max(0.0, (hit - 0.5) * 2 * SOCIAL_CAP)), 4)
            why = "کران پایین CI بالای ۰.۵ — وزنِ سقف‌دار (لایهٔ اجتماعی ≤۵٪)"
        else:
            w, why = 0.0, "CI شامل ۰.۵ — از سکه بهتر نیست، وزن صفر"
        out[k] = {"n": n, "hit": hit, "ci": ci, "weight": w, "why": why, "by_cat": a["by_cat"]}
    return out


def consensus(items, polls=None, board=None, now_ms=None):
    """اجماع وزن‌دار روی آیتم‌های اخیر به تفکیک دامنه. بی‌وزن = «بی‌وزن»، نه ۰."""
    now_ms = now_ms or int(time.time() * 1000)
    polls = polls if polls is not None else _rows(POLLS)
    board = board if board is not None else scoreboard()
    ids = {it["id"] for it in items}
    by_scope = {}
    for r in polls:
        if r.get("item") not in ids or now_ms - int(r.get("at") or 0) > 24 * 3600 * 1000:
            continue
        w = (board.get(f"{r.get('agent')}|{r.get('method')}") or {}).get("weight") or 0.0
        s = by_scope.setdefault(r.get("scope") or "BTC", {"up": 0.0, "down": 0.0, "n": 0, "n_weighted": 0})
        s["n"] += 1
        if w <= 0:
            continue
        s["n_weighted"] += 1
        if r["stance"] == "UP":
            s["up"] += w * float(r.get("confidence") or 0)
        elif r["stance"] == "DOWN":
            s["down"] += w * float(r.get("confidence") or 0)
    out = {}
    for sc, s in by_scope.items():
        if s["n_weighted"] == 0:
            out[sc] = {"bias": None, "weight": 0.0, "n": s["n"], "why": "هیچ ایجنتِ نظرداده‌ای هنوز وزن ندارد"}
            continue
        net = s["up"] - s["down"]
        out[sc] = {"bias": "UP" if net > 0 else "DOWN" if net < 0 else "FLAT",
                   "weight": round(min(SOCIAL_CAP, abs(net)), 4), "n": s["n"], "why": ""}
    return out


# ── ۷. عکس‌فوری و ردپا ─────────────────────────────────────────────────
def build_snapshot(items, new_rows, llm_note, ctx, now_ms=None):
    from hamid import evidence_packet as EP           # noqa: WPS433
    now_ms = now_ms or int(time.time() * 1000)
    board = scoreboard()
    cons = consensus(items, board=board, now_ms=now_ms)
    polls = _rows(POLLS)
    recent = [r for r in polls if now_ms - int(r.get("at") or 0) <= 24 * 3600 * 1000]
    best = max(((k, v) for k, v in board.items() if v.get("hit") is not None),
               key=lambda kv: kv[1]["hit"], default=None)
    numbers = {"آیتم‌های این نوبت": len(items), "برداشت‌های تازه": len(new_rows),
               "برداشت‌های ۲۴س": len(recent), "کل نمره‌ها": sum(v["n"] for v in board.values()),
               "ایجنت‌های وزن‌دار": sum(1 for v in board.values() if v.get("weight", 0) > 0)}
    packet = EP.build(
        claim=(f"اجماع خبری BTC: {cons['BTC']['bias'] or 'بی‌وزن'} (وزن {cons['BTC']['weight']})"
               if "BTC" in cons else "این نوبت آیتم قابل‌نظرسنجی نداشت"),
        numbers=numbers,
        track_record=(f"بهترین کارنامه {best[0]}: اصابت {best[1]['hit']} CI {best[1]['ci']} n={best[1]['n']}"
                      if best else f"کارنامه: هیچ ایجنتی هنوز به {MIN_N} نمونه نرسیده"),
        scenario_up="اگر اجماع وزن‌دار UP و بازار بالا رفت → کارنامهٔ آن ایجنت‌ها بالا می‌رود و وزنشان (تا سقف ۵٪) بیشتر",
        scenario_down="اگر اجماع خلاف بازار بود → وزن صفر می‌شود؛ خبر همچنان فقط ثبت می‌شود",
        invalidator="ایجنتی که با n≥۲۰ کران پایین CI زیر ۰.۵ دارد از سکه بهتر نیست و وزن نمی‌گیرد",
        sources=["signals/news.json (RSS+تقویم)", "signals/fomo.json", "کندل ۱س واقعی برای نمره"]
                + (["مدل زبانی (روش llm)"] if not llm_note else []),
        limit=("خبر فقط دیدگاه است؛ هیچ دروازه/امتیازی از این فایل نمی‌آید (دستور حمید ۲ سپتامبر). "
               + (f"روش llm: {llm_note}" if llm_note else "روش llm فعال")))
    return {"generated": now_ms, "panel": PANEL, "engine": ENGINE,
            "items": items[:20], "recent": recent[-40:], "scoreboard": board, "consensus": cons,
            "llm": {"enabled": not llm_note, "note": llm_note, "model": LLM_MODEL if not llm_note else None},
            "packet": packet, "packet_faults": EP.validate(packet),
            "note": "نظرسنجی خبر بین ایجنت‌ها — برداشت، نمره با کندل واقعی، وزن فقط از کارنامه و با سقف ۵٪ (قانون ۱۱)."}


def trace_for(sym, direction, snap=None):
    """ردپای روی سیگنال: news_align (with/against/none) + وزن اجماع. بی‌عکس‌فوری = None."""
    snap = snap if snap is not None else _load(OUT, None)
    if not isinstance(snap, dict):
        return {"news_align": None, "news_bias_w": None}
    cons = snap.get("consensus") or {}
    c = cons.get(sym) or cons.get("BTC") or {}
    bias = c.get("bias")
    if bias in (None, "FLAT") or not c.get("weight"):
        return {"news_align": "none", "news_bias_w": c.get("weight") or 0.0}
    want = "UP" if str(direction).upper() == "LONG" else "DOWN"
    return {"news_align": "with" if bias == want else "against", "news_bias_w": c.get("weight")}


def run(quiet=False):
    BRAIN.mkdir(parents=True, exist_ok=True)
    keep = BRAIN / ".gitkeep"
    if not keep.exists():
        keep.write_text("")
    fomo = _load(FOMO, {})
    ctx = {"fear": (fomo.get("market") or {}).get("fear"), "funding_avg": (fomo.get("market") or {}).get("funding_avg"),
           "heat": (fomo.get("market") or {}).get("heat")} if isinstance(fomo, dict) else {}
    items = collect_items(fomo=fomo)
    new, llm_note = poll(items, ctx)
    scored = score()
    snap = build_snapshot(items, new, llm_note, ctx)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    if not quiet:
        print(f"نظرسنجی خبر: {len(items)} آیتم · {len(new)} برداشت تازه · {scored} نمرهٔ تازه · "
              f"اجماع BTC {snap['consensus'].get('BTC', {}).get('bias')} · llm: {llm_note or 'فعال'}")
    return snap


if __name__ == "__main__":
    run()
