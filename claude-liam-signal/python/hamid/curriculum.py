"""برنامهٔ درسیِ روزانه — سه منبع برای هر انجین، هر روز (دستور حمید، ۱ سپتامبر).

حمید: «تو باید روزانه برای هر انجین با توجه به کاری که انجام می‌دهد سه
کتاب و مهارت پیدا کنی و در اختیار ایجنت مورد نظر بگذاری، و بک‌تست بگیری
که درست انجام شده باشد.»

## چرا فهرستِ ثابت جواب نمی‌دهد

اگر یک فهرستِ دستی بنویسم، روز دوم همان سه کتاب دوباره پیشنهاد می‌شوند و
«روزانه» بی‌معنا می‌شود. پس این ماژول:

۱. از **قفسهٔ راستی‌آزمایی‌شده** (`brain/library/index.jsonl`) و صفِ
   ورودی (`queue.jsonl`) می‌خواند — نه از حافظهٔ من. منبعی که در قفسه
   نباشد پیشنهاد نمی‌شود (قانون ۰۳: هر ادعا منبع دارد).
۲. **آنچه هر انجین قبلاً خوانده** را از `brain/research/<Exx>/reading.jsonl`
   کنار می‌گذارد، پس تکرار نمی‌شود.
۳. اولویت را از **کارنامهٔ همان انجین** می‌گیرد: انجینی که نمره‌اش قرمز
   است اول در صف است. برنامهٔ درسی باید به ضعف بچسبد نه به همه یکسان.

## اتصال به سنجش — «بک‌تست بگیر که درست انجام شده باشد»

خواندن، لبه نمی‌سازد. پس هر تخصیص یک `claim_id` می‌گیرد و انجین موظف
است یافته‌اش را در `brain/research/<Exx>/findings.jsonl` با همان شناسه
ثبت کند. `verify()` می‌شمارد چند تخصیصِ سررسیده یافته گرفته‌اند — و آن
عدد خودش کارنامهٔ همین ماژول است (نرخ پیگیری). تخصیصی که یافته نگیرد،
مطالعه نبوده.

## مرز صادقانه

هیچ منبعی از این‌جا وارد تولید نمی‌شود. مسیر همان قانون ۰۳ است:
مطالعه → فرضیه → بک‌تست بی‌آینده → CI بالای صفر → تأیید حمید. این ماژول
فقط **صف مطالعه** می‌سازد و پیگیری‌اش را می‌شمارد.

اجرا: `python3 -m hamid.curriculum [--write] [--verify]`
"""
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
ROOT = PY.parent.parent
LIB = ROOT / "brain" / "library" / "index.jsonl"
QUEUE = ROOT / "brain" / "library" / "queue.jsonl"
RESEARCH = ROOT / "brain" / "research"
OUT = ROOT / "signals" / "curriculum.json"

PER_ENGINE = 3            # دستور صریح: سه منبع برای هر انجین
DUE_H = 24                # تخصیص بعد از این مدت باید یافته داشته باشد

# موضوعِ هر انجین — برای تطبیق با برچسب منابع قفسه. از منشور و قوانین
# می‌آید، نه حدس؛ همان جمله‌ای که `engine_map.WATCHES` دارد، فشرده.
TOPICS = {
    "E00": ("orchestration", "process", "risk", "psychology"),
    "E01": ("universe", "screening", "liquidity", "market-structure"),
    "E02": ("data", "microstructure", "quality"),
    "E03": ("dominance", "macro", "regime", "intermarket"),
    "E04": ("dominance", "btc", "regime"),
    "E05": ("macro", "economics", "calendar", "rates"),
    "E06": ("btc", "patterns", "technical", "chart-patterns"),
    "E07": ("structure", "trendline", "support-resistance", "swing"),
    "E08": ("smc", "order-block", "fvg", "liquidity"),
    "E09": ("candlestick", "price-action", "indicator", "ibs"),
    "E10": ("order-flow", "level2", "derivatives", "microstructure"),
    "E11": ("strategy", "system-design", "regime"),
    "E12": ("lead-lag", "correlation", "pump", "cross-section"),
    "E13": ("analog", "historical", "pattern-statistics"),
    "E14": ("news", "catalyst", "event-study", "sentiment"),
    "E15": ("alert", "monitoring", "watchlist"),
    "E16": ("risk", "position-sizing", "portfolio", "kelly"),
    "E17": ("decision", "committee", "probability", "bayesian"),
    "E18": ("backtest", "walk-forward", "data-snooping", "statistics"),
    "E19": ("trade-management", "exit", "trailing", "mfe-mae"),
    "E20": ("post-trade", "review", "journaling", "attribution"),
    "E21": ("memory", "learning", "knowledge"),
    "E22": ("bandit", "optimization", "research-method", "experiment"),
    "E23": ("reliability", "sre", "monitoring", "observability"),
    "E24": ("ui", "contract", "qa"),
    "E25": ("delivery", "messaging", "idempotency"),
    "E26": ("management", "psychology", "economics", "leadership"),
    # E27 — اتاق توزیع اطلاعات (۳ سپتامبر): دسته‌بندی ارز و مسیر رویداد→اتاق.
    "E27": ("taxonomy", "classification", "routing", "market-structure"),
}


def _jsonl(p):
    out = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    out.append(json.loads(line))
                except Exception:                    # noqa: BLE001
                    pass
    except Exception:                                # noqa: BLE001
        pass
    return out


def shelf():
    """قفسه = راستی‌آزمایی‌شده‌ها اول، بعد صفِ ورودی.

    منبعِ VERIFIED مقدم است؛ صفِ QUEUED فقط وقتی می‌آید که قفسه برای آن
    موضوع خالی باشد — یعنی هرگز «هیچ‌چیز پیشنهاد نشد» نمی‌گیریم، ولی
    ترتیبِ اعتبار حفظ می‌شود."""
    # یکتاسازی بر **عنوان**: یک کتاب می‌تواند هم در قفسه باشد هم در صف
    # (یا دو بار در یکی). نسخهٔ اولِ همین تابع این را نمی‌گرفت و E00 دو
    # بار «Thinking, Fast and Slow» می‌گرفت — یعنی از سه تخصیصِ روز، دو
    # تا یک چیز بودند و برنامهٔ درسی عملاً دوسوم می‌شد.
    rows, by_title = [], {}
    for p, status in ((LIB, "VERIFIED"), (QUEUE, "QUEUED")):
        for r in _jsonl(p):
            t = r.get("title") or r.get("name") or r.get("source")
            if not t:
                continue
            key = str(t).strip().lower()
            if key in by_title:
                # برچسب‌ها ادغام می‌شوند تا تطبیقِ موضوع ضعیف‌تر نشود؛
                # وضعیت **بهترینِ** دو نسخه می‌ماند (VERIFIED > QUEUED).
                prev = by_title[key]
                prev["tags"] = sorted(set(prev["tags"]) | {
                    str(x).lower() for x in
                    (r.get("tags") or r.get("topics") or [])})
                if prev["status"] != "VERIFIED" and status == "VERIFIED":
                    prev["status"] = "VERIFIED"
                continue
            row = {
                "title": t,
                "tags": [str(x).lower() for x in
                         (r.get("tags") or r.get("topics") or [])],
                "text": " ".join(str(r.get(k) or "") for k in
                                 ("title", "name", "topic", "why", "note",
                                  "engine", "for")).lower(),
                "engine": r.get("engine") or r.get("for"),
                "url": r.get("url") or r.get("ref"),
                "status": r.get("status") or status,
            }
            by_title[key] = row
            rows.append(row)
    return rows


def read_already(eid):
    """چه چیزی این انجین قبلاً گرفته — از حلقهٔ مطالعه و تخصیص‌های قبلی."""
    seen = set()
    for name in ("reading.jsonl", "curriculum.jsonl"):
        for r in _jsonl(RESEARCH / eid / name):
            t = r.get("title") or r.get("source")
            if t:
                seen.add(str(t).strip().lower())
    return seen


def _score(row, eid):
    """تطبیقِ منبع با موضوعِ انجین — شمارشِ برچوردِ برچسب، نه حدس."""
    if row.get("engine") == eid:
        return 100
    topics = TOPICS.get(eid, ())
    s = sum(3 for t in topics if t in row["tags"])
    s += sum(1 for t in topics if t in row["text"])
    return s


def assign(now_ms=None, per=PER_ENGINE):
    """صفِ امروز — اولویت با انجینی که کارنامه‌اش قرمز است."""
    now = now_ms or int(time.time() * 1000)
    try:
        from hamid.scorecard import build as _sc
        grades = {c["id"]: c for c in _sc(now)["cards"]}
    except Exception:                                # noqa: BLE001
        grades = {}
    RED = ("FAULT", "NEGATIVE", "UNDER")
    rows = shelf()
    out = []
    for eid in sorted(TOPICS):
        g = grades.get(eid) or {}
        already = read_already(eid)
        cand = [r for r in rows
                if r["title"].strip().lower() not in already]
        cand.sort(key=lambda r: (-_score(r, eid),
                                 0 if r["status"] == "VERIFIED" else 1))
        picks = [r for r in cand if _score(r, eid) > 0][:per]
        out.append({
            "engine": eid,
            "priority": ("قرمز" if g.get("verdict") in RED else
                         "بی‌متر" if g.get("verdict") == "NO_METRIC" else "عادی"),
            "grade": g.get("verdict"),
            "topics": list(TOPICS.get(eid, ())),
            "assigned": [{
                "title": p["title"], "status": p["status"], "url": p["url"],
                "claim_id": "CUR-" + hashlib.sha1(
                    f"{eid}|{p['title']}".encode()).hexdigest()[:8],
            } for p in picks],
            "gap": (None if len(picks) >= per else
                    f"قفسه برای این موضوع فقط {len(picks)} منبعِ نخوانده دارد "
                    f"(لازم: {per}) — کمبود پنهان نمی‌شود"),
        })
    order = {"قرمز": 0, "بی‌متر": 1, "عادی": 2}
    out.sort(key=lambda r: (order.get(r["priority"], 3), r["engine"]))
    return {"generated": now, "per_engine": per, "rows": out,
            "n_assigned": sum(len(r["assigned"]) for r in out),
            "n_short": sum(1 for r in out if r["gap"]),
            "boundary": ("صفِ مطالعه است، نه لبه. هیچ منبعی بدون بک‌تست "
                         "بی‌آینده و CI بالای صفر وارد تولید نمی‌شود "
                         "(قانون ۰۳).")}


def verify(cur=None, now_ms=None):
    """«بک‌تست بگیر که درست انجام شده» — نرخِ پیگیریِ تخصیص‌ها.

    تخصیصی که سررسیدش گذشته و یافته‌ای با همان `claim_id` ثبت نکرده،
    مطالعه نبوده. این عدد کارنامهٔ خودِ برنامهٔ درسی است."""
    now = now_ms or int(time.time() * 1000)
    cur = cur or (json.loads(OUT.read_text(encoding="utf-8"))
                  if OUT.exists() else None)
    if not cur:
        return {"n": 0, "why": "هنوز تخصیصی ثبت نشده"}
    # `or now` نه — چون `generated` صفر (مهرِ معتبر) falsy است و آن‌وقت
    # اختلاف صفر می‌شود و هیچ تخصیصی هرگز «سررسیده» نمی‌شود. پاسبان
    # همین را گرفت.
    gen = cur.get("generated")
    gen = now if gen is None else gen
    due = now - gen >= DUE_H * 3_600_000
    ids, done = [], []
    for r in cur.get("rows") or []:
        found = {str(f.get("claim_id") or "")
                 for f in _jsonl(RESEARCH / r["engine"] / "findings.jsonl")}
        for a in r.get("assigned") or []:
            ids.append(a["claim_id"])
            if a["claim_id"] in found:
                done.append(a["claim_id"])
    return {"n": len(ids), "done": len(done), "due": due,
            "follow_rate_pct": round(100 * len(done) / len(ids), 1) if ids else None,
            "verdict": ("زود است — هنوز سررسید نشده" if not due else
                        "OK" if len(done) == len(ids) else "پیگیری ناقص")}


def main(argv=()):
    if "--verify" in argv:
        v = verify()
        print("### پیگیریِ برنامهٔ درسی")
        print(f"  {v.get('done', 0)} از {v.get('n', 0)} تخصیص یافته ثبت کرده"
              f" · {v.get('follow_rate_pct')}٪ → {v.get('verdict', v.get('why'))}")
        return 0
    cur = assign()
    print(f"### برنامهٔ درسی امروز — {cur['n_assigned']} تخصیص برای "
          f"{len(cur['rows'])} انجین · {cur['n_short']} انجین کمبود منبع\n")
    for r in cur["rows"]:
        print(f"{r['engine']}  [{r['priority']}"
              + (f" · {r['grade']}" if r["grade"] else "") + "]")
        for a in r["assigned"]:
            print(f"    · {a['title'][:74]}  ({a['status']})  {a['claim_id']}")
        if r["gap"]:
            print(f"    ⚠️ {r['gap']}")
    print(f"\n### مرز صادقانه\n  {cur['boundary']}")
    if "--write" in argv:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(cur, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"\n  نوشته شد: {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
