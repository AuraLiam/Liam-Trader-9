#!/usr/bin/env python3
"""شورا روی هر انجین — رأی ۱۲ متخصص، وزنِ جدا برای هر انجین (دستور حمید، ۳ سپتامبر).

حمید: «هر کدام از این ۱۲ نفر می‌توانند برای هر انجین حاضر باشند و
نظارت کنند و رأی تأیید یا رد بدهند؛ رأی بیشتر که تأیید کند ادامه
می‌دهد… هر استادی از نتیجهٔ رأی‌هایش امتیاز می‌گیرد؛ آن‌که درست گفته در
همان زمینه وزن بیشتری می‌گیرد و آن‌که اشتباه کرده امتیاز کم می‌کند…
همین روش برای هر انجین — ایجنتی که در رویدادها خوب است ممکن است در
دامیننس اشتباه کند و برای دامیننس وزن کمتری بگیرد.»

## چهار چیزی که این ماژول از `phoenix.judge` جدا می‌کند

**۱. کارنامه به تفکیک انجین.** ققنوس یک کارنامهٔ سراسری دارد؛ شورا برای
هر جفتِ (انجین، مراقب) کارنامهٔ جداگانه نگه می‌دارد. همان چیزی که حمید
خواست: خوب بودن در دامیننس، وزنِ ریسک را بالا نمی‌برد.

**۲. رأی از شواهدِ خودِ انجین می‌آید، نه از حدس.** هر انجین «کارت
شواهد» می‌دهد: در هر میدان، عددی در [−۱,+۱] با دلیل. مراقب فقط میدانِ
تخصص خودش را می‌خواند. میدانی که انجین نداده = **ممتنع** با دلیل
(قانون ۱) — نه صفرِ خنثی، چون صفر یعنی «دیدم و بی‌نظرم» و آن دروغ است.

**۳. دو حکم، نه یکی.** حمید گفت «رأی بیشتر». وزن هم مهم است. پس هر دو
گزارش می‌شوند: اکثریتِ سرشماری و امتیاز وزنی — و اگر این دو با هم
نخوانند، همان اختلاف روی خروجی می‌نشیند تا دیده شود، نه این‌که یکی
دیگری را بپوشاند.

**۴. خودِ انجین هم کارنامه دارد.** حمید: «خود انجین‌ها و ایجنت‌هایشان
هم می‌توانند بعد از نتیجه و ریشه‌یابی امتیاز کمتری بگیرند.» پس کنارِ
کارنامهٔ مراقب‌ها، اعتمادِ هر انجین هم شمرده می‌شود.

## مرز (قانون ۰۳/۱۲ — تغییرناپذیر بی‌دستور صریح حمید)

شورا **مشاوره‌ای** است: هیچ سیگنالی حذف نمی‌شود، هیچ عددی (ورود/استاپ/
تارگت/اهرم) عوض نمی‌شود، و هیچ دروازه‌ای شل یا سفت نمی‌شود. ورودِ حکم
به دروازه یا سایز فقط وقتی ماشین شبانه CI بالای صفر بدهد و حمید تأیید کند.

    python3 -m hamid.council --score --write
"""
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import phoenix as PHX                     # noqa: E402

ROOT = HERE.parents[2]
BRAIN = ROOT / "brain" / "council"
SCORES = BRAIN / "scores.json"
VOTES = BRAIN / "votes.jsonl"                        # append-only
OUTCOMES = BRAIN / "outcomes.jsonl"                  # append-only
OUT = ROOT / "signals" / "council.json"

ENGINE_ID = "E00"
PANEL = "لیام تریدر ۹"

MIN_N = 12                       # زیر این نمونه، وزن تکان نمی‌خورد
BAND_EXPLORATORY = 0.15
BAND_CONFIRMED = 0.40
SOCIAL_CAP = 0.05                # سهم مشترک قوس+دلو (قانون ۱۱/۱۵)
MIN_VOTERS = 4                   # کمتر از این، شورا حکم نمی‌دهد
PASS_SCORE = 0.15                # آستانهٔ «ادامه بده» روی امتیاز وزنی
MAX_KEEP = 200                   # سقف ردیف روی تابلو

# انجین‌هایی که شورا رویشان می‌نشیند. کلید = شناسهٔ کوتاه، مقدار = نام فارسی.
ENGINES = {
    "structure": "اتاق ساختار (روند/کندل/OB/ستاپ)",
    "dominance": "اتاق دامیننس",
    "news": "بورد خبر و کاتالیزور",
    "pump": "انجین پامپ",
    "risk": "ریسک و ورود",
    "signal": "صدور سیگنال",
    "paper": "پیپر و آزمایش",
    "scalp": "میز اسکلپ",
}

# میدانِ تخصص هر مراقب. انجین هر کدام از این کلیدها را داشته باشد، آن
# مراقب رأی می‌دهد؛ نداشته باشد، ممتنع می‌شود — نه صفر.
FIELDS = {
    "scorpio":     ("dominance", "usdtd", "btcd", "usdcd"),
    "gemini":      ("btc_context", "lead_lag", "correlation"),
    "taurus":      ("trend_4h", "trend_1h", "trend"),
    "aries":       ("impulse", "bos", "pullback"),
    "leo":         ("order_block", "fvg"),
    "cancer":      ("liquidity", "sweep"),
    "pisces":      ("candle", "quality"),
    "libra":       ("risk", "fee", "rr"),
    "capricorn":   ("memory", "record"),
    "virgo":       ("data_quality", "candle_src", "freshness"),
    "sagittarius": ("news",),
    "aquarius":    ("crowd", "fomo"),
}
CAPPED = PHX.CAPPED                                  # قوس و دلو — لایهٔ اجتماعی


# ── کمکی ─────────────────────────────────────────────────────────────────
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


def _append(p, row):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _clamp(v):
    return max(-1.0, min(1.0, float(v)))


# ── وزن به تفکیک انجین ───────────────────────────────────────────────────
def load_scores(path=None):
    d = _j(path or SCORES, None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("engines", {})
    d.setdefault("engine_trust", {})
    return d


def weight_of(engine, gid, scores):
    """وزن این مراقب **در همین انجین**. زیر MIN_N، وزن پایه."""
    base = PHX.BY_ID[gid]["base"]
    rec = ((scores.get("engines") or {}).get(engine) or {}).get(gid) or {}
    n, k = rec.get("n") or 0, rec.get("correct") or 0
    if n < MIN_N:
        return base, f"n={n} < {MIN_N} در {engine} — وزن پایه"
    acc = k / n
    ci = rec.get("ci95") or PHX._wilson(k, n)
    confirmed = ci is not None and (ci[0] > 0.5 or ci[1] < 0.5)
    band = BAND_CONFIRMED if confirmed else BAND_EXPLORATORY
    adj = max(-band, min(band, (acc - 0.5) * 2))
    tag = "باند کامل" if confirmed else "باند اکتشافی"
    return round(base * (1 + adj), 4), f"در {engine}: دقت {acc*100:.0f}٪ n={n} CI {ci} — {tag}"


def weights(engine, scores=None):
    scores = load_scores() if scores is None else scores
    w = {gid: weight_of(engine, gid, scores) for gid in PHX.BY_ID}
    total = sum(v for v, _ in w.values())
    capped = sum(w[g][0] for g in CAPPED)
    if total > 0 and capped / total > SOCIAL_CAP:
        k = (SOCIAL_CAP * (total - capped)) / ((1 - SOCIAL_CAP) * capped)
        for g in CAPPED:
            # گردکردن به پایین — سقف ۵٪ سقف است، نه «تقریباً ۵٪»
            w[g] = (math.floor(w[g][0] * k * 10000) / 10000,
                    w[g][1] + " · سقف لایهٔ اجتماعی ۵٪")
    return w


# ── رأی یک مراقب روی یک کارت شواهد ──────────────────────────────────────
def guardian_vote(gid, evidence):
    """میانگین میدان‌های تخصص همین مراقب. میدانِ نبوده = ممتنع، نه صفر."""
    seen = []
    for key in FIELDS[gid]:
        e = (evidence or {}).get(key)
        if e is None:
            continue
        if isinstance(e, dict):
            v, why = e.get("v"), e.get("why") or key
        else:
            v, why = e, key
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        seen.append((key, _clamp(v), str(why)))
    if not seen:
        have = ", ".join(FIELDS[gid])
        return None, f"میدانِ تخصص ({have}) روی کارت شواهد نبود — ممتنع (قانون ۱)"
    val = round(sum(v for _, v, _ in seen) / len(seen), 4)
    why = " · ".join(f"{w}" for _, _, w in seen[:3])
    return val, why


# ── جلسهٔ شورا ───────────────────────────────────────────────────────────
def session(engine, proposal, scores=None, now_ms=None):
    """یک نوبتِ نظارت روی یک انجین. `proposal.evidence` کارت شواهد است."""
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    if engine not in ENGINES:
        return {"ok": False, "engine": engine,
                "why": f"انجین ناشناخته: {engine} — شورا روی چیزی که ثبت نشده نمی‌نشیند"}
    scores = load_scores() if scores is None else scores
    w = weights(engine, scores)
    ev = (proposal or {}).get("evidence") or {}
    votes, num, den = [], 0.0, 0.0
    n_for = n_against = n_abs = 0
    for g in PHX.GUARDIANS:
        gid = g["id"]
        v, why = guardian_vote(gid, ev)
        wt, wwhy = w[gid]
        row = {"id": gid, "name": g["name"], "sign": g["sign"],
               "specialty": g["specialty"], "weight": wt, "weight_why": wwhy,
               "vote": v, "why": why}
        votes.append(row)
        if v is None:
            n_abs += 1
            continue
        num += wt * v
        den += wt
        if v > 0:
            n_for += 1
        elif v < 0:
            n_against += 1
    score = round(num / den, 4) if den else 0.0
    n_voters = n_for + n_against + sum(1 for r in votes if r["vote"] == 0)
    majority = "تأیید" if n_for > n_against else ("رد" if n_against > n_for else "برابر")
    if n_voters < MIN_VOTERS:
        decision, why = "HOLD", f"فقط {n_voters} رأی‌دهنده — کمتر از {MIN_VOTERS}، شورا حکم نمی‌دهد"
    elif score >= PASS_SCORE and n_for > n_against:
        decision, why = "PROCEED", "هم اکثریت تأیید کرد هم امتیاز وزنی از آستانه گذشت"
    elif score <= -PASS_SCORE and n_against > n_for:
        decision, why = "REJECT", "هم اکثریت رد کرد هم امتیاز وزنی زیر آستانه است"
    else:
        decision, why = "HOLD", "اکثریت و وزن هم‌داستان نیستند — تصمیم معلق می‌ماند"
    split = (majority == "تأیید" and score < 0) or (majority == "رد" and score > 0)
    trust = (scores.get("engine_trust") or {}).get(engine) or {}
    return {"ok": True, "t": now_ms, "engine": engine, "engine_fa": ENGINES[engine],
            "subject": (proposal or {}).get("subject"),
            "decision": decision, "why": why,
            "score": score, "majority": majority,
            "n_for": n_for, "n_against": n_against, "n_abstain": n_abs,
            "split_warning": split,
            "split_why": ("اکثریت و وزن مخالف هم‌اند — همین اختلاف گزارش می‌شود، "
                          "پوشانده نمی‌شود") if split else None,
            "engine_trust": trust or None,
            "votes": votes,
            "boundary": "مشاوره‌ای: هیچ سیگنالی حذف و هیچ عددی عوض نمی‌شود "
                        "(قانون ۰۳/۱۲)"}


def record_vote(sess, path=None):
    """ثبت جلسه روی دفتر append-only — پایهٔ کارنامهٔ بعدی."""
    if not sess.get("ok"):
        return None
    row = {"t": sess["t"], "engine": sess["engine"], "subject": sess.get("subject"),
           "decision": sess["decision"], "score": sess["score"],
           "votes": {v["id"]: v["vote"] for v in sess["votes"] if v["vote"] is not None}}
    return _append(path or VOTES, row)


def record_outcome(engine, subject, good, root_cause=None, path=None, now_ms=None):
    """نتیجهٔ واقعی همان موضوع. `good=True` یعنی جهتِ مثبت درست از آب درآمد."""
    return _append(path or OUTCOMES,
                   {"t": int(now_ms if now_ms is not None else time.time() * 1000),
                    "engine": engine, "subject": subject, "good": bool(good),
                    "root_cause": root_cause})


# ── کارنامه: هر مراقب × هر انجین، و خودِ انجین ──────────────────────────
def score_all(votes=None, outcomes=None, now_ms=None):
    """درست/غلط هر رأی را با نتیجهٔ همان موضوع می‌سنجد.

    «درست» یعنی علامت رأی با نتیجه یکی بود: رأی مثبت و نتیجهٔ خوب، یا
    رأی منفی و نتیجهٔ بد. رأی صفر شمرده نمی‌شود — بی‌نظری نه درست است
    نه غلط، و شمردنش کارنامه را به سمت ۵۰٪ رقیق می‌کند.
    """
    votes = _lines(VOTES) if votes is None else votes
    outcomes = _lines(OUTCOMES) if outcomes is None else outcomes
    res = {}
    for o in outcomes:
        key = (o.get("engine"), o.get("subject"))
        if key[0] and key[1] is not None:
            res[key] = bool(o.get("good"))
    eng, trust = {}, {}
    for v in votes:
        key = (v.get("engine"), v.get("subject"))
        if key not in res:
            continue
        good = res[key]
        e = eng.setdefault(v["engine"], {})
        for gid, val in (v.get("votes") or {}).items():
            if not isinstance(val, (int, float)) or val == 0:
                continue
            r = e.setdefault(gid, {"n": 0, "correct": 0})
            r["n"] += 1
            if (val > 0) == good:
                r["correct"] += 1
        t = trust.setdefault(v["engine"], {"n": 0, "correct": 0})
        t["n"] += 1
        if (v.get("decision") == "PROCEED") == good:
            t["correct"] += 1
    for e in eng.values():
        for r in e.values():
            r["acc"] = round(r["correct"] / r["n"], 4) if r["n"] else None
            r["ci95"] = PHX._wilson(r["correct"], r["n"])
    for r in trust.values():
        r["acc"] = round(r["correct"] / r["n"], 4) if r["n"] else None
        r["ci95"] = PHX._wilson(r["correct"], r["n"])
    return {"generated": int(now_ms if now_ms is not None else time.time() * 1000),
            "engines": eng, "engine_trust": trust,
            "judged": sum(1 for v in votes if (v.get("engine"), v.get("subject")) in res),
            "votes_seen": len(votes), "outcomes_seen": len(outcomes)}


def snapshot(scores=None, votes=None, now_ms=None):
    """تابلوی شورا برای پنل — وزن هر مراقب در هر انجین، کنار هم."""
    scores = load_scores() if scores is None else scores
    votes = _lines(VOTES) if votes is None else votes
    table = {}
    for e in ENGINES:
        w = weights(e, scores)
        table[e] = {"name": ENGINES[e],
                    "trust": (scores.get("engine_trust") or {}).get(e),
                    "guardians": [{"id": gid, "name": PHX.BY_ID[gid]["name"],
                                   "sign": PHX.BY_ID[gid]["sign"],
                                   "weight": w[gid][0], "why": w[gid][1],
                                   "record": ((scores.get("engines") or {}).get(e) or {}).get(gid)}
                                  for gid in PHX.BY_ID]}
    return {"generated": int(now_ms if now_ms is not None else time.time() * 1000),
            "engine": ENGINE_ID, "panel": PANEL,
            "engines": table,
            "recent": votes[-MAX_KEEP:][-12:],
            "min_n": MIN_N, "pass_score": PASS_SCORE, "min_voters": MIN_VOTERS,
            "social_cap": SOCIAL_CAP,
            "boundary": "شورا مشاوره‌ای است: هیچ سیگنالی حذف و هیچ عددی عوض "
                        "نمی‌شود. ورود به دروازه فقط با CI بالای صفر و تأیید حمید "
                        "(قانون ۰۳/۱۲)."}


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--score" in argv:
        s = score_all()
        BRAIN.mkdir(parents=True, exist_ok=True)
        SCORES.write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"کارنامهٔ شورا: {s['judged']} رأی سنجیده از {s['votes_seen']} "
              f"(نتیجهٔ ثبت‌شده: {s['outcomes_seen']})")
    snap = snapshot()
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"تابلوی شورا نوشته شد: {OUT.relative_to(ROOT)}")
    for e, row in snap["engines"].items():
        t = row["trust"]
        tt = f" · اعتماد انجین {round((t.get('acc') or 0)*100)}٪ n={t.get('n')}" if t else ""
        print(f"  {row['name']}{tt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
