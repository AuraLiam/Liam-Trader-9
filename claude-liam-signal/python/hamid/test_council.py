"""پاسبان شورای هر انجین (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دستور حمید: هر ۱۲ متخصص روی هر انجین حاضرند · رأی بیشتر
ادامه می‌دهد · امتیاز و وزن **به تفکیک همان انجین** · نتیجه به ققنوس
می‌رسد · و مرز: شورا مشاوره‌ای است، دروازه نیست.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import council as C                       # noqa: E402
from hamid import phoenix as PHX                     # noqa: E402

OK = 0
FAIL = []
NOW = 1_800_000_000_000


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}")
        if extra:
            print(f"      ↳ {extra}")


EMPTY = {"engines": {}, "engine_trust": {}}

# ── ۱. حضور همهٔ ۱۲ روی هر انجین ────────────────────────────────────────
check("همان ۱۲ مراقب زودیاک شورا را می‌سازند، نه فهرست موازی",
      set(C.FIELDS) == set(PHX.BY_ID) and len(C.FIELDS) == 12)
check("هر مراقب میدان تخصص دارد", all(C.FIELDS[g] for g in C.FIELDS))
check("شورا روی چند انجین می‌نشیند، نه فقط سیگنال", len(C.ENGINES) >= 6)
for e in ("structure", "dominance", "news", "pump", "risk", "signal", "paper"):
    check(f"انجین «{e}» ثبت شده", e in C.ENGINES)
s = C.session("risk", {"subject": "X", "evidence": {"risk": 0.5}}, scores=EMPTY, now_ms=NOW)
check("هر ۱۲ نفر در جلسه حاضرند (حتی ممتنع‌ها)", len(s["votes"]) == 12)
check("انجین ناشناخته جلسه نمی‌گیرد",
      C.session("hokus", {}, scores=EMPTY)["ok"] is False)
check("و دلیلش نوشته می‌شود", "ناشناخته" in C.session("hokus", {}, scores=EMPTY)["why"])

# ── ۲. رأی از شواهد می‌آید، نبودِ شاهد = ممتنع نه صفر ───────────────────
v, why = C.guardian_vote("scorpio", {"dominance": {"v": -0.8, "why": "USDT.D صعودی"}})
check("مراقب میدان خودش را می‌خواند", v == -0.8 and "USDT.D" in why)
v, why = C.guardian_vote("scorpio", {"order_block": {"v": 0.9}})
check("میدانِ دیگری رأیش را نمی‌سازد", v is None)
check("و ممتنع دلیل دارد (قانون ۱)", "ممتنع" in why and "قانون ۱" in why)
v, _ = C.guardian_vote("libra", {"risk": 0.6, "fee": 0.2})
check("چند میدانِ یک مراقب میانگین می‌شوند", v == 0.4, str(v))
v, _ = C.guardian_vote("libra", {"risk": 5.0})
check("مقدار بیرون از بازه بریده می‌شود، نه رد", v == 1.0, str(v))
v, _ = C.guardian_vote("libra", {"risk": "خیلی خوب"})
check("مقدار غیرعددی رأی نمی‌سازد", v is None)
v, _ = C.guardian_vote("libra", {"risk": True})
check("True هم عدد حساب نمی‌شود", v is None)

# ── ۳. اکثریت و وزن، هر دو گزارش می‌شوند ────────────────────────────────
ev = {"dominance": 0.8, "trend_4h": 0.7, "order_block": 0.6, "risk": 0.5,
      "data_quality": 0.9}
s = C.session("signal", {"subject": "A", "evidence": ev}, scores=EMPTY, now_ms=NOW)
check("رأی هم‌جهت → PROCEED", s["decision"] == "PROCEED", str(s["decision"]))
check("اکثریت جدا از امتیاز وزنی گزارش می‌شود",
      s["majority"] == "تأیید" and isinstance(s["score"], float))
check("شمار موافق/مخالف/ممتنع کامل است",
      s["n_for"] + s["n_against"] + s["n_abstain"] +
      sum(1 for r in s["votes"] if r["vote"] == 0) == 12)
neg = {k: -x for k, x in ev.items()}
s2 = C.session("signal", {"subject": "B", "evidence": neg}, scores=EMPTY, now_ms=NOW)
check("رأی خلاف → REJECT", s2["decision"] == "REJECT", str(s2["decision"]))
s3 = C.session("signal", {"subject": "C", "evidence": {"risk": 0.5}}, scores=EMPTY, now_ms=NOW)
check("کمتر از ۴ رأی‌دهنده = HOLD، نه حکمِ زوری",
      s3["decision"] == "HOLD" and "کمتر از" in s3["why"], str(s3))
mixed = {"dominance": 0.05, "trend_4h": 0.05, "order_block": 0.05, "risk": -0.9,
         "data_quality": -0.9}
s4 = C.session("signal", {"subject": "D", "evidence": mixed}, scores=EMPTY, now_ms=NOW)
check("وقتی اکثریت و وزن نمی‌خوانند، حکم معلق می‌ماند",
      s4["decision"] == "HOLD", f"{s4['decision']} score={s4['score']} maj={s4['majority']}")
check("و همان اختلاف روی خروجی علامت می‌خورد، پوشانده نمی‌شود",
      s4["split_warning"] is True and s4["split_why"], str(s4["split_warning"]))

# ── ۴. وزن به تفکیک انجین — قلبِ دستور حمید ─────────────────────────────
sc = {"engines": {
        "dominance": {"scorpio": {"n": 40, "correct": 34}},
        "risk": {"scorpio": {"n": 40, "correct": 8}}},
      "engine_trust": {}}
w_dom, why_dom = C.weight_of("dominance", "scorpio", sc)
w_risk, why_risk = C.weight_of("risk", "scorpio", sc)
check("همان مراقب در انجینِ قوی وزن بیشتری می‌گیرد", w_dom > 1.0, str(w_dom))
check("و در انجینِ ضعیف وزن کمتری — دقیقاً دستور حمید", w_risk < 1.0, str(w_risk))
check("دلیل وزن نام انجین را می‌برد", "dominance" in why_dom and "risk" in why_risk)
w_new, why_new = C.weight_of("news", "scorpio", sc)
check("در انجینِ بی‌سابقه وزن پایه می‌ماند", w_new == 1.0 and "وزن پایه" in why_new)
check("زیر ۱۲ نمونه هیچ حرکتی نمی‌کند",
      C.weight_of("news", "scorpio", {"engines": {"news": {"scorpio": {"n": 11, "correct": 11}}}})[0] == 1.0)
check("باند اکتشافی از باند کامل کوچک‌تر است", C.BAND_EXPLORATORY < C.BAND_CONFIRMED)
check("هیچ وزنی صفر نمی‌شود (وتو وجود ندارد)",
      all(v > 0 for v, _ in C.weights("risk", sc).values()))

# سقف لایهٔ اجتماعی
w = C.weights("risk", EMPTY)
tot = sum(v for v, _ in w.values())
cap = sum(w[g][0] for g in C.CAPPED)
check("سهم قوس+دلو از سقف ۵٪ رد نمی‌کند (قانون ۱۱/۱۵)",
      cap / tot <= C.SOCIAL_CAP + 1e-9, str(round(cap / tot, 6)))
check("و سقف واقعاً اعمال شده، نه اتفاقی زیر سقف",
      abs(cap / tot - C.SOCIAL_CAP) < 1e-4, str(round(cap / tot, 6)))

# ── ۵. کارنامه از نتیجهٔ واقعی ساخته می‌شود ─────────────────────────────
votes = [
    {"t": NOW, "engine": "dominance", "subject": "d1", "decision": "PROCEED",
     "score": 0.5, "votes": {"scorpio": 0.8, "libra": -0.4, "taurus": 0.0}},
    {"t": NOW, "engine": "dominance", "subject": "d2", "decision": "REJECT",
     "score": -0.5, "votes": {"scorpio": -0.8, "libra": 0.4}},
    {"t": NOW, "engine": "risk", "subject": "r1", "decision": "PROCEED",
     "score": 0.3, "votes": {"scorpio": 0.5}},
    {"t": NOW, "engine": "dominance", "subject": "d9", "decision": "PROCEED",
     "score": 0.2, "votes": {"scorpio": 0.5}},          # بی‌نتیجه — نباید شمرده شود
]
outs = [{"engine": "dominance", "subject": "d1", "good": True},
        {"engine": "dominance", "subject": "d2", "good": False},
        {"engine": "risk", "subject": "r1", "good": False}]
sc2 = C.score_all(votes, outs, now_ms=NOW)
dom = sc2["engines"]["dominance"]
check("رأی درست در همان انجین شمرده می‌شود",
      dom["scorpio"]["n"] == 2 and dom["scorpio"]["correct"] == 2, str(dom["scorpio"]))
check("رأی غلط هم شمرده می‌شود", dom["libra"]["correct"] == 0 and dom["libra"]["n"] == 2)
check("رأی صفر شمرده نمی‌شود — بی‌نظری نه درست است نه غلط", "taurus" not in dom)
check("کارنامهٔ همان مراقب در انجین دیگر جداست",
      sc2["engines"]["risk"]["scorpio"]["n"] == 1
      and sc2["engines"]["risk"]["scorpio"]["correct"] == 0)
check("رأیِ بی‌نتیجه اصلاً وارد کارنامه نمی‌شود", dom["scorpio"]["n"] == 2)
check("بازهٔ اطمینان ویلسون روی هر ردیف هست", dom["scorpio"]["ci95"] is not None)
check("اعتماد خودِ انجین هم شمرده می‌شود (دستور: انجین‌ها هم امتیاز کم می‌کنند)",
      sc2["engine_trust"]["dominance"]["n"] == 2
      and sc2["engine_trust"]["risk"]["correct"] == 0, str(sc2["engine_trust"]))
check("شمارِ سنجیده صادق است", sc2["judged"] == 3 and sc2["votes_seen"] == 4)

# ── ۶. دفترها append-only ───────────────────────────────────────────────
with tempfile.TemporaryDirectory() as td:
    vp, op = Path(td) / "v.jsonl", Path(td) / "o.jsonl"
    sess = C.session("news", {"subject": "n1", "evidence": ev}, scores=EMPTY, now_ms=NOW)
    C.record_vote(sess, path=vp)
    C.record_vote(sess, path=vp)
    C.record_outcome("news", "n1", True, root_cause="تیتر درست خوانده شد",
                     path=op, now_ms=NOW)
    check("دفتر رأی فقط اضافه می‌کند", len(vp.read_text(encoding="utf-8").strip().splitlines()) == 2)
    row = json.loads(vp.read_text(encoding="utf-8").splitlines()[0])
    check("ردیف رأی انجین، موضوع، حکم و رأی هر مراقب را دارد",
          row["engine"] == "news" and row["subject"] == "n1" and row["votes"])
    check("رأی ممتنع در دفتر ثبت نمی‌شود (چیزی که نبوده، ثبت نمی‌شود)",
          all(v is not None for v in row["votes"].values()))
    o = json.loads(op.read_text(encoding="utf-8").strip())
    check("نتیجه با ریشه‌یابی ثبت می‌شود (دستور: ریشه‌یابی و تجربه)",
          o["good"] is True and o["root_cause"])
    check("جلسهٔ ناموفق روی دفتر نمی‌نشیند",
          C.record_vote({"ok": False}, path=vp) is None)

# ── ۷. تابلو ────────────────────────────────────────────────────────────
snap = C.snapshot(scores=sc, votes=votes, now_ms=NOW)
check("تابلو همهٔ انجین‌ها را دارد", set(snap["engines"]) == set(C.ENGINES))
check("و در هر انجین وزن هر ۱۲ مراقب را",
      all(len(v["guardians"]) == 12 for v in snap["engines"].values()))
check("وزن عقرب در تابلوی دامیننس و ریسک فرق دارد",
      next(g for g in snap["engines"]["dominance"]["guardians"] if g["id"] == "scorpio")["weight"] !=
      next(g for g in snap["engines"]["risk"]["guardians"] if g["id"] == "scorpio")["weight"])
check("آستانه‌ها روی تابلو اعلام می‌شوند",
      snap["min_n"] == C.MIN_N and snap["pass_score"] == C.PASS_SCORE)
check("مالک تابلو E00 (ققنوس) است", snap["engine"] == "E00")

# ── ۸. مرز ──────────────────────────────────────────────────────────────
check("مرز مشاوره‌ای روی هر جلسه نوشته می‌شود",
      "عوض نمی‌شود" in s["boundary"] and "قانون ۰۳" in s["boundary"])
check("و روی تابلو هم", "CI بالای صفر" in snap["boundary"])
src = (HERE / "council.py").read_text(encoding="utf-8")
for bad in ("veto", "LIVE_EXECUTION = True", "send_message", "requests.post"):
    check(f"شورا «{bad}» ندارد — نه وتو، نه ارسال، نه اجرا", bad not in src)

# ── ۹. سیم‌کشی ──────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
check("برنامهٔ درسی مراقب‌ها موجود است",
      (ROOT / "brain" / "library" / "curricula" / "phoenix-guardians.md").exists())
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("council.json ردیف قرارداد دارد (قانون ۱۳)",
      "council.json" in reg and reg["council.json"]["producer"] == "hamid/council.py",
      str(reg.get("council.json")))
wf = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
check("چرخهٔ حمید شورا را می‌سازد و کارنامه می‌گیرد",
      "hamid.council --score --write" in wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
