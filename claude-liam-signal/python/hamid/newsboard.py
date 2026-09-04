#!/usr/bin/env python3
"""بورد خبر — تابلوی مشترکِ همهٔ اتاق‌ها (دستور حمید، ۳ سپتامبر).

حمید: «یک بورد اطلاعاتی در پنل که همهٔ خبرهای مهم را داشته باشد و همهٔ
ایجنت‌ها و انجین‌ها ببینند؛ یک بخش از آن بورد برای گزارش هر واحد —
درسی که از یک اتفاق گرفته را خلاصه روی بورد بگذارد برای بقیه… فقط خبر
سیاسی نه، رویدادهای مهم کریپتو و نظر افراد مهم دربارهٔ یک ارز بر اساس
تاریخ آن خبر… و تاریخ رویدادهای آینده‌ای که می‌تواند روی یک ارز اثر
بگذارد از یک روز قبل روی بورد بیاید.»

## چهار بخشِ بورد

| بخش | چه چیزی | قاعده |
|---|---|---|
| `now` | خبرهای تازه، دسته‌بندی‌شده، با ارزهای نام‌برده‌شده | تاریخ اجباری؛ بی‌تاریخ جدا می‌نشیند |
| `voices` | نظر افراد مهم دربارهٔ یک ارز | فقط با نامِ گوینده و تاریخ |
| `upcoming` | رویداد آینده — **از یک روز قبل** | زودتر از ۲۴ ساعت روی بورد نمی‌آید |
| `lessons` | درسِ هر واحد از یک اتفاق، برای بقیه | تکرارِ همان درس ضریبش را بالا می‌برد |

## سه قاعده‌ای که این بورد را از «فید خبر» جدا می‌کند

**۱. تاریخ، جزوِ خبر است نه تزئینش.** خبری که تاریخش را ندهد در سطلِ
`undated` می‌نشیند و هرگز کنار خبر امروز چیده نمی‌شود. حمید صریح گفت
«بر اساس تاریخ آن خبر» — چون همان تیتر، یک هفته دیرتر، حرفِ دیگری است.

**۲. رویداد آینده از یک روز قبل، نه زودتر.** رویدادی که ۹ روز دیگر است
اگر امروز روی بورد بنشیند، ۹ روز بی‌اثر آن‌جا می‌ماند و چشمِ اتاق‌ها را
به بورد کور می‌کند. `POST_AHEAD_H = 24` همان دستور است، عددی‌شده.

**۳. بورد دروازه نیست (قانون ۱۵).** حمید ۱۰۰ بار گفت خبر فقط دیدگاه
است. این ماژول هیچ امتیازی نمی‌سازد، هیچ سیگنالی را رد یا تأیید نمی‌کند
و هیچ عددی روی تصمیم نمی‌گذارد. ورودش به تصمیم فقط از مسیر نظرسنجی
(`news_poll`) و قانون ۰۳.

    python3 -m hamid.newsboard --write
"""
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "newsboard.json"
NEWS = ROOT / "signals" / "news.json"
FOMO = ROOT / "signals" / "fomo.json"
PUMP = ROOT / "signals" / "pump-radar.json"
LESSONS = ROOT / "brain" / "newsboard" / "lessons.jsonl"

ENGINE = "E14"
PANEL = "لیام تریدر ۹"
POST_AHEAD_H = 24.0        # دستور حمید: از یک روز قبل
FRESH_H = 12.0             # بالای این، خبر «کهنه» برچسب می‌خورد (پنهان نمی‌شود)
MAX_NOW = 24
MAX_VOICES = 10
MAX_UPCOMING = 12
MAX_LESSONS = 20
TEHRAN_OFFSET_S = 3.5 * 3600

# افراد مهمی که حرفشان دربارهٔ یک ارز، خودش خبر است.
# فهرست دستی و بازبینی‌شده؛ نبودنِ یک نام یعنی «هنوز اضافه نشده»، نه
# «مهم نیست» — و هیچ نامی از روی حدسِ متن ساخته نمی‌شود.
PEOPLE = {
    "powell": "جروم پاول (فدرال رزرو)",
    "trump": "دونالد ترامپ",
    "musk": "ایلان ماسک",
    "saylor": "مایکل سیلر (استراتژی)",
    "vitalik": "ویتالیک بوترین (اتریوم)",
    "buterin": "ویتالیک بوترین (اتریوم)",
    "cz": "چانگ‌پنگ ژائو (بایننس)",
    "zhao": "چانگ‌پنگ ژائو (بایننس)",
    "armstrong": "برایان آرمسترانگ (کوین‌بیس)",
    "hayes": "آرتور هیز",
    "gensler": "گری گنسلر",
    "atkins": "پل اتکینز (SEC)",
    "yellen": "جنت یلن",
    "lagarde": "کریستین لاگارد (ECB)",
    "do kwon": "دو کوون",
    "sun": "جاستین سان",
}

# دستهٔ خبر — کلیدواژهٔ صریح، نه حدس. دستهٔ ناشناخته «عمومی» می‌ماند.
CATS = [
    ("هک و سوءاستفاده", ("hack", "exploit", "drain", "breach", "stolen", "rug")),
    ("قانون‌گذاری", ("sec ", "cftc", "lawsuit", "regulat", "ban ", "approv", "etf",
                     "court", "sue", "settle")),
    ("کلان و نرخ بهره", ("fed", "fomc", "rate cut", "rate hike", "cpi", "inflation",
                         "jobs", "payroll", "ecb", "tariff")),
    ("لیستینگ و صرافی", ("list", "delist", "launch", "perpetual", "futures")),
    ("آنلاک و عرضه", ("unlock", "vesting", "token release", "burn", "buyback")),
    ("پذیرش و شراکت", ("partner", "adopt", "integrat", "treasury", "invest")),
]

_SYM = re.compile(r"\b([A-Z]{2,10})\b")
# نمادهای پرتکرارِ متنِ انگلیسی که ارز نیستند — بی‌این فهرست، «CEO» ارز می‌شود.
_NOT_COIN = {"CEO", "CFO", "CTO", "USA", "US", "UK", "EU", "SEC", "CFTC", "ETF", "ETFS",
             "FED", "FOMC", "CPI", "GDP", "IPO", "AI", "API", "NFT", "DEFI", "DAO",
             "TVL", "OTC", "AML", "KYC", "ATH", "ATL", "YOY", "MOM", "Q1", "Q2", "Q3",
             "Q4", "NEW", "THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT", "SAYS",
             "WILL", "NOT", "ALL", "ITS", "MAY", "CAN", "HAS", "WAS", "ARE", "BUT",
             "NOW", "OUT", "OFF", "TOP", "BIG", "DAY", "END", "WEEK", "YEAR", "PLUS"}


def _j(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def _lines(p):
    out = []
    try:
        for ln in Path(p).read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:                    # noqa: BLE001
                    continue
    except Exception:                                # noqa: BLE001
        pass
    return out


def tehran(ms):
    t = time.gmtime(ms / 1000 + TEHRAN_OFFSET_S)
    return time.strftime("%Y-%m-%d %H:%M", t)


# ── دسته، ارز، گوینده ────────────────────────────────────────────────────
def category(title):
    t = (title or "").lower()
    for name, keys in CATS:
        if any(k in t for k in keys):
            return name
    return "عمومی"


def _known_bases():
    """پایه‌های شناخته‌شدهٔ تاکسونومی — تنها منبعِ مجازِ نامِ ارز."""
    try:
        from hamid import taxonomy as TX
        return set(TX._INDEX)
    except Exception:                                # noqa: BLE001
        return set()


def coins(title, known=None):
    """ارزهای نام‌برده‌شده در تیتر. فقط نمادهای شناخته‌شده — حدس ممنوع.

    نکتهٔ ریز ولی تعیین‌کننده: جست‌وجوی نماد روی **متن اصلی** انجام
    می‌شود نه روی upper()اش. اجرای اول upper() گرفت و چون تیترها
    Title Case‌اند، هر کلمه‌ای نماد شد — «LIVE، UPDATES، TAKE» به‌عنوان
    ارز روی بورد نشستند.
    """
    raw = title or ""
    t = raw.upper()
    known = _known_bases() if known is None else known
    out = []
    for m in _SYM.findall(raw):
        if m in _NOT_COIN or m in out:
            continue
        if known and m not in known:
            continue
        out.append(m)
    for word, sym in (("BITCOIN", "BTC"), ("ETHEREUM", "ETH"), ("SOLANA", "SOL"),
                      ("RIPPLE", "XRP"), ("DOGECOIN", "DOGE"), ("CARDANO", "ADA")):
        if word in t and sym not in out:
            out.append(sym)
    return out[:5]


def voice(title):
    """گویندهٔ مهم، اگر نامش صریح در تیتر باشد. وگرنه None — نه حدس."""
    t = (title or "").lower()
    for key, fa in PEOPLE.items():
        if key in t:
            return fa
    return None


# ── بخش ۱ و ۲: خبر تازه و صداها ─────────────────────────────────────────
def board_now(items, now_ms=None, known=None):
    """خبرها با تاریخ. بی‌تاریخ‌ها جدا می‌نشینند، نه کنار خبر امروز."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    dated, undated = [], []
    for it in items or []:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        ts = it.get("t") or it.get("ts") or it.get("published_ms")
        row = {"title": title, "cat": it.get("cat") or category(title),
               "coins": coins(title, known), "voice": voice(title),
               "url": it.get("url")}
        if isinstance(ts, (int, float)) and ts > 0:
            age_h = round((now_ms - ts) / 3_600_000, 2)
            row.update({"t": int(ts), "when": tehran(ts), "age_h": age_h,
                        "fresh": age_h <= FRESH_H})
            dated.append(row)
        else:
            row["why_undated"] = "منبع تاریخ نداد — کنار خبر امروز چیده نمی‌شود"
            undated.append(row)
    dated.sort(key=lambda r: -r["t"])
    return dated[:MAX_NOW], undated[:MAX_NOW]


def board_voices(rows):
    """نظر افراد مهم دربارهٔ یک ارز — با نام گوینده و تاریخ، وگرنه نمی‌آید."""
    out = [r for r in rows if r.get("voice")]
    return out[:MAX_VOICES]


# ── بخش ۳: رویداد آینده، از یک روز قبل ──────────────────────────────────
def board_upcoming(calendar=None, unlocks=None, ahead_h=POST_AHEAD_H, now_ms=None):
    """فقط رویدادهای داخل پنجرهٔ ۲۴ ساعت. زودتر = روی بورد نمی‌آید."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    out = []
    for c in calendar or []:
        h = c.get("in_hours")
        if not isinstance(h, (int, float)) or h < 0 or h > ahead_h:
            continue
        out.append({"kind": "calendar", "title": c.get("title"),
                    "scope": c.get("country") or "کلان", "in_hours": round(float(h), 2),
                    "when": tehran(now_ms + h * 3_600_000), "coins": []})
    for u in unlocks or []:
        h = u.get("in_hours")
        if not isinstance(h, (int, float)):
            ts = u.get("t") or u.get("date_ms")
            h = (ts - now_ms) / 3_600_000 if isinstance(ts, (int, float)) else None
        if not isinstance(h, (int, float)) or h < 0 or h > ahead_h:
            continue
        sym = (u.get("symbol") or u.get("sym") or "").upper()
        out.append({"kind": "unlock", "title": u.get("title") or f"آنلاک {sym}",
                    "scope": sym or "?", "in_hours": round(float(h), 2),
                    "when": tehran(now_ms + h * 3_600_000),
                    "coins": [sym] if sym else []})
    out.sort(key=lambda r: r["in_hours"])
    return out[:MAX_UPCOMING]


# ── بخش ۴: درسِ هر واحد، برای بقیه ──────────────────────────────────────
def board_lessons(rows, now_ms=None):
    """درس‌ها با ضریبِ تکرار.

    دستور حمید: «مهارت و تجربهٔ تکراری فقط ضریب آن تجربه را بالا می‌برد».
    پس درسِ یکسان از یک واحد، ردیفِ دوم نمی‌سازد؛ `times` و آخرین تاریخش
    به‌روز می‌شود. بورد شلوغ نمی‌شود و در عین حال چیزی گم نمی‌شود.
    """
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    agg = {}
    for r in rows or []:
        unit = (r.get("unit") or "").strip()
        text = (r.get("lesson") or r.get("text") or "").strip()
        if not unit or not text:
            continue
        key = f"{unit}|{text.lower()}"
        ts = r.get("t") if isinstance(r.get("t"), (int, float)) else now_ms
        e = agg.get(key)
        if e is None:
            agg[key] = {"unit": unit, "lesson": text, "times": 1, "first_t": int(ts),
                        "last_t": int(ts), "event": r.get("event"),
                        "coins": r.get("coins") or []}
        else:
            e["times"] += 1
            e["last_t"] = max(e["last_t"], int(ts))
            e["first_t"] = min(e["first_t"], int(ts))
            for c in r.get("coins") or []:
                if c not in e["coins"]:
                    e["coins"].append(c)
    out = list(agg.values())
    for e in out:
        e["when"] = tehran(e["last_t"])
        e["weight"] = round(min(3.0, 1.0 + 0.25 * (e["times"] - 1)), 3)
    out.sort(key=lambda e: (-e["times"], -e["last_t"]))
    return out[:MAX_LESSONS]


def post_lesson(unit, lesson, event=None, coins_=None, path=None, now_ms=None):
    """ثبت درس روی دفترِ append-only. هیچ ردیفی بازنویسی نمی‌شود (قانون ضد-merge)."""
    p = Path(path or LESSONS)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"t": int(now_ms if now_ms is not None else time.time() * 1000),
           "unit": unit, "lesson": lesson, "event": event, "coins": coins_ or []}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ── ساخت بورد ────────────────────────────────────────────────────────────
def build(news=None, calendar=None, unlocks=None, lessons=None, pump=None,
          now_ms=None, known=None):
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    dated, undated = board_now(news, now_ms, known)
    up = board_upcoming(calendar, unlocks, POST_AHEAD_H, now_ms)
    les = board_lessons(lessons, now_ms)
    by_cat = {}
    for r in dated:
        by_cat[r["cat"]] = by_cat.get(r["cat"], 0) + 1
    return {
        "generated": now_ms,
        "engine": ENGINE,
        "panel": PANEL,
        "now": dated,
        "undated": undated,
        "voices": board_voices(dated),
        "upcoming": up,
        "lessons": les,
        "pump_notes": list(pump or [])[:8],
        "counts": {"now": len(dated), "undated": len(undated),
                   "voices": len(board_voices(dated)), "upcoming": len(up),
                   "lessons": len(les)},
        "by_cat": by_cat,
        "post_ahead_h": POST_AHEAD_H,
        "fresh_h": FRESH_H,
        "boundary": "بورد فقط دیدگاه است (قانون ۱۵): هیچ دروازه‌ای، امتیازی یا "
                    "عددی از این‌جا وارد تصمیم نمی‌شود. ورود فقط از مسیر نظرسنجی "
                    "خبر و قانون ۰۳.",
    }


def _from_disk(now_ms=None):
    n = _j(NEWS, {}) or {}
    items = n.get("classified") or []
    gen = n.get("generated")
    if isinstance(gen, (int, float)):
        for it in items:                             # تاریخِ خبر = تاریخِ همان برداشت
            it.setdefault("t", int(gen))
    pump = []
    pr = _j(PUMP, {}) or {}
    for row in (pr.get("alerts") or pr.get("candidates") or [])[:8]:
        if isinstance(row, dict) and row.get("sym"):
            pump.append({"sym": row["sym"], "why": row.get("why") or row.get("reason")})
    return {"news": items, "calendar": n.get("calendar") or [],
            "unlocks": n.get("unlocks") or [], "lessons": _lines(LESSONS),
            "pump": pump, "now_ms": now_ms}


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    b = build(**_from_disk())
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"بورد خبر نوشته شد: {OUT.relative_to(ROOT)}")
    c = b["counts"]
    print(f"بورد خبر — {c['now']} خبر تاریخ‌دار ({c['undated']} بی‌تاریخ) · "
          f"{c['voices']} نظر شخصیت · {c['upcoming']} رویداد تا ۲۴ ساعت · "
          f"{c['lessons']} درس واحدها")
    for r in b["now"][:5]:
        tag = "" if r["fresh"] else " [کهنه]"
        cs = (" · " + "،".join(r["coins"])) if r["coins"] else ""
        print(f"  • [{r['cat']}]{tag} {r['title'][:90]}{cs}")
    for r in b["upcoming"][:4]:
        print(f"  ⏳ {r['in_hours']}س دیگر · {r['scope']} · {r['title']}")
    for e in b["lessons"][:4]:
        print(f"  📌 {e['unit']} (×{e['times']}، ضریب {e['weight']}): {e['lesson'][:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
