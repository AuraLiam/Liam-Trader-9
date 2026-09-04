#!/usr/bin/env python3
"""دفتر مهارت — تجربهٔ تکراری ضریب می‌سازد، نه ردیف (دستور حمید، ۳ سپتامبر).

حمید: «در تمام مراحل اطلاعات ثبت شود و بعد از نتیجه‌گیری و مهارت و
تجربهٔ جدید، به حافظهٔ همه اضافه شود؛ **مهارت و تجربهٔ تکراری فقط ضریب
آن تجربه را بالا می‌برد** که در موارد مشابه بتوانند قوی‌تر استفاده
کنند» و «همهٔ اتفاقات با تاریخ و لحظهٔ وقوع ثبت شود».

## فرقش با `memory.remember`

`memory` دفترِ **رویداد** است: پنجرهٔ ۱۲ ساعته دارد، سقف ۳۰۰ ردیف، و
درسِ کهنه از تهش می‌افتد. آن برای «چه شد» درست است. این‌جا دفترِ
**مهارت** است: پنجره ندارد، حذف ندارد، و تکرار — هر وقت که باشد —
ضریبِ همان مهارت را بالا می‌برد. تجربه‌ای که شش ماه پیش ساخته شد و
امروز دوباره دیده شد، از تجربهٔ تازهٔ یک‌باره قوی‌تر است، نه ضعیف‌تر.

## سه قاعده

**۱. ضریب با بازده نزولی.** `1 + K·log2(times)` با سقف. صد بار دیدن یک
درس، صد برابرش نمی‌کند — وگرنه یک درسِ پرتکرارِ کم‌ارزش (مثل «داده دیر
رسید») همهٔ حافظه را می‌بلعد. همان عیبی که ۱۳ اوت با ۱۰۷ نسخه از یک
جمله دیده شد.

**۲. هیچ ردیفی حذف نمی‌شود** (قانون ۶). مهارتی که مدت‌هاست دیده نشده
`stale` برچسب می‌خورد و سنش گزارش می‌شود — پاک نمی‌شود.

**۳. هر رویداد با تاریخ و لحظه‌اش می‌ماند.** ادغام روی ردیفِ خلاصه است؛
دفترِ `events.jsonl` **append-only** است و هر بار دیده‌شدن با مهرِ زمانِ
خودش آن‌جا ثبت می‌شود. پس «ضریب بالا رفت» همیشه قابل بازشماری است.

## مرز

دفتر مهارت **حافظه** است، نه دروازه. ضریب هیچ آستانه‌ای را جابه‌جا
نمی‌کند و هیچ سیگنالی را رد یا تأیید نمی‌کند. ورودش به تصمیم فقط از
مسیر قانون ۰۳.

    python3 -m hamid.skill_ledger --write
"""
import json
import math
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parents[2]
BRAIN = ROOT / "brain" / "skills"
LEDGER = BRAIN / "ledger.json"
EVENTS = BRAIN / "events.jsonl"                      # append-only، هرگز بازنویسی
OUT = ROOT / "signals" / "skills.json"

ENGINE = "E21"                                       # نگهبان حافظه
PANEL = "لیام تریدر ۹"

K = 0.45                     # شیب ضریب
MAX_WEIGHT = 3.0             # سقف — تکرار بی‌نهایت وزن بی‌نهایت نمی‌سازد
STALE_DAYS = 45.0            # از این دیرتر دیده نشده = کهنه (نه حذف)
MAX_EVIDENCE = 8             # نمونهٔ نگه‌داشته از هر مهارت
TOP_N = 40                   # سقف ردیف روی تابلو
# نوعِ ردیفی که مهارت نیست — نتیجهٔ یک معاملهٔ مشخص با عددِ یکتای خودش.
SKIP_KINDS = ("نتیجه",)

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[.,;:!؟?،؛\-–—…\"'«»()\[\]]+")
# یکسان‌سازی حروفِ عربی/فارسی و نویسه‌های نامرئی: «كیفیت» و «کیفیت» یک
# درس‌اند، ولی بدون این، دو ردیف جدا می‌شوند و ضریب هرگز بالا نمی‌رود.
_MAP = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا",
                      "‌": " ", "‏": "", "‎": "", "ـ": ""})


def norm(text):
    """کلیدِ همانندی. آن‌قدر سخت‌گیر که دو درسِ متفاوت یکی نشوند."""
    t = (text or "").translate(_MAP).lower().strip()
    t = _PUNCT.sub(" ", t)
    return _WS.sub(" ", t).strip()


def key_of(unit, skill, scope=None):
    return "|".join((norm(unit), norm(scope or "*"), norm(skill)))


def weight_of(times):
    """۱ بار → ۱.۰ · ۲ بار → ۱.۴۵ · ۴ بار → ۱.۹ · ۱۶ بار → ۲.۸ · سقف ۳.۰"""
    if times <= 1:
        return 1.0
    return round(min(MAX_WEIGHT, 1.0 + K * math.log2(times)), 4)


def _load(path=None):
    try:
        d = json.loads(Path(path or LEDGER).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        d = {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("skills", {})
    return d


def _save(d, path=None):
    p = Path(path or LEDGER)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def learn(unit, skill, scope=None, evidence=None, now_ms=None,
          path=None, events=None):
    """یک مهارت/تجربه. تکراری بود → ضریب بالا می‌رود، ردیف تازه نمی‌سازد."""
    unit = (unit or "").strip()
    skill = (skill or "").strip()
    if not unit or not skill:
        return None
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    k = key_of(unit, skill, scope)
    d = _load(path)
    row = d["skills"].get(k)
    if row is None:
        row = {"unit": unit, "skill": skill, "scope": scope, "times": 1,
               "first_t": now, "last_t": now, "evidence": []}
        d["skills"][k] = row
    else:
        row["times"] += 1
        row["last_t"] = max(row.get("last_t") or now, now)
        row["first_t"] = min(row.get("first_t") or now, now)
        # متنِ نمایشیِ اولین ثبت می‌ماند — تغییرِ نگارشی نباید تاریخ را عوض کند
    if evidence:
        row["evidence"] = ([{"t": now, "note": str(evidence)}]
                           + list(row.get("evidence") or []))[:MAX_EVIDENCE]
    row["weight"] = weight_of(row["times"])
    d["updated"] = now
    _save(d, path)
    # دفتر رویداد: ادغام روی خلاصه است، ولی هر بارِ دیده‌شدن با لحظهٔ
    # خودش این‌جا می‌ماند — «ضریب بالا رفت» باید قابل بازشماری باشد.
    ep = Path(events or EVENTS)
    ep.parent.mkdir(parents=True, exist_ok=True)
    with ep.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now, "key": k, "unit": unit, "scope": scope,
                            "skill": skill, "times": row["times"],
                            "weight": row["weight"], "evidence": evidence},
                           ensure_ascii=False) + "\n")
    return row


def recall(unit=None, scope=None, min_weight=None, limit=10, now_ms=None, path=None):
    """قوی‌ترین مهارت‌های مرتبط، برای تصمیم بعدی. مرتب بر ضریب، بعد تازگی."""
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    out = []
    for k, r in (_load(path).get("skills") or {}).items():
        if unit and norm(r.get("unit")) != norm(unit):
            continue
        if scope and r.get("scope") and norm(r["scope"]) != norm(scope):
            continue
        w = r.get("weight") or weight_of(r.get("times") or 1)
        if min_weight is not None and w < min_weight:
            continue
        age_d = round((now - (r.get("last_t") or now)) / 86_400_000, 2)
        out.append({**r, "key": k, "weight": w, "age_days": age_d,
                    "stale": age_d > STALE_DAYS})
    out.sort(key=lambda r: (-r["weight"], -(r.get("last_t") or 0)))
    return out[:limit]


def snapshot(now_ms=None, path=None):
    """تابلوی حافظه — چه مهارتی چند بار دیده شده و چقدر ضریب گرفته."""
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    rows = recall(limit=10_000, now_ms=now, path=path)
    by_unit = {}
    for r in rows:
        u = by_unit.setdefault(r["unit"], {"n": 0, "repeats": 0, "top": None})
        u["n"] += 1
        u["repeats"] += max(0, r["times"] - 1)
        if u["top"] is None or r["weight"] > u["top"]["weight"]:
            u["top"] = {"skill": r["skill"], "weight": r["weight"], "times": r["times"]}
    return {"generated": now, "engine": ENGINE, "panel": PANEL,
            "counts": {"skills": len(rows),
                       "repeated": sum(1 for r in rows if r["times"] > 1),
                       "stale": sum(1 for r in rows if r["stale"]),
                       "units": len(by_unit)},
            "by_unit": by_unit,
            "top": rows[:TOP_N],
            "weight_rule": f"۱ + {K}·log2(تکرار)، سقف {MAX_WEIGHT} — بازده نزولی",
            "stale_days": STALE_DAYS,
            "boundary": "دفتر مهارت حافظه است نه دروازه: ضریب هیچ آستانه‌ای را "
                        "جابه‌جا نمی‌کند و هیچ سیگنالی را رد یا تأیید نمی‌کند. "
                        "ورود به تصمیم فقط از مسیر قانون ۰۳."}


def ingest_memory(lessons=None, path=None, events=None, now_ms=None, cursor_key="memory"):
    """درس‌های دفتر رویداد را به مهارت تبدیل می‌کند — **یک بار برای هر درس**.

    بی‌این نشانگر، هر چرخه همان درس‌ها را دوباره می‌خورد و ضریب‌ها هر
    ۱۵ دقیقه بالا می‌روند بی‌این‌که تجربهٔ تازه‌ای رخ داده باشد. همان
    کلاسِ عیبی که در دفتر پیپر با تسویهٔ دوباره دیده شد: عددی که از
    تکرارِ خواندن بزرگ می‌شود، تجربه نیست.
    """
    if lessons is None:
        try:
            from hamid import memory as _mem
            lessons = (_mem._load() or {}).get("lessons") or []
        except Exception:                            # noqa: BLE001
            lessons = []
    # ردیفِ «نتیجه» (نتیجهٔ یک معاملهٔ مشخص، با عدد یکتای همان معامله)
    # مهارت نیست: هرگز دو بار یکی نمی‌شود، پس ضریبش هیچ‌وقت بالا نمی‌رود
    # و فقط تابلو را با ۲۷۴ ردیفِ یک‌باره پر می‌کند. اندازه‌گیری ۴ سپتامبر:
    # از ۳۰۰ درسِ دفتر، ۲۷۴ تا از این نوع بودند و صفر تکرار ساختند.
    # آن ردیف‌ها سرِ جایشان در `memory` می‌مانند؛ این‌جا فقط درسِ
    # قابل‌تعمیم می‌آید.
    lessons = [l for l in lessons if (l.get("kind") or "") not in SKIP_KINDS]
    d = _load(path)
    seen_after = ((d.get("cursors") or {}).get(cursor_key)) or 0
    newest = seen_after
    n = 0
    for l in sorted(lessons, key=lambda x: x.get("at") or 0):
        at = l.get("at") or 0
        if at <= seen_after:
            continue
        text = (l.get("text") or "").strip()
        if not text:
            continue
        learn(l.get("kind") or "حافظه", text, scope=l.get("sym"),
              evidence=(l.get("data") or None) and json.dumps(l["data"], ensure_ascii=False),
              now_ms=at, path=path, events=events)
        newest = max(newest, at)
        n += 1
    d = _load(path)
    d.setdefault("cursors", {})[cursor_key] = newest
    d["updated"] = int(now_ms if now_ms is not None else time.time() * 1000)
    _save(d, path)
    return {"ingested": n, "cursor": newest}


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--ingest" in argv or "--write" in argv:
        r = ingest_memory()
        print(f"از دفتر رویداد: {r['ingested']} درس تازه وارد دفتر مهارت شد")
    s = snapshot()
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"تابلوی مهارت نوشته شد: {OUT.relative_to(ROOT)}")
    c = s["counts"]
    print(f"دفتر مهارت — {c['skills']} مهارت از {c['units']} واحد · "
          f"{c['repeated']} تکرارشده · {c['stale']} کهنه")
    for r in s["top"][:8]:
        tag = " [کهنه]" if r["stale"] else ""
        print(f"  ×{r['times']} ضریب {r['weight']}{tag} · {r['unit']}: {r['skill'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
