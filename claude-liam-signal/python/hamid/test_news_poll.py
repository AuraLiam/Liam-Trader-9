"""پاسبان نظرسنجی خبر (۲ سپتامبر).

خطرهایی که این آزمون می‌بندد:
۱. خبر وارد دروازه/امتیاز تصمیم شود (دستور صریح حمید: فقط دیدگاه).
۲. برداشت تکراری ثبت شود یا افق ناقص نمره بگیرد.
۳. وزن بدون کارنامه یا بالای سقف ۵٪ داده شود.
۴. روش llm بی‌کلید چیزی جعل کند یا با کلید، پاسخ نامعتبر را قبول کند.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import news_poll as NP                     # noqa: E402

OK = 0
FAIL = []


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


now = int(time.time() * 1000)
H = 3600 * 1000
news = {"generated": now - 10 * 60000,
        "classified": [{"title": "Fed signals rate hike as inflation rises", "cat": "کلان/فدرال"},
                       {"title": "Lawsuit challenges Tether for freezing USDT", "cat": "قانون‌گذاری"},
                       {"title": "Bitcoin ETF inflows hit record high", "cat": "عمومی"},
                       {"title": "Bitcoin ETF inflows hit record high", "cat": "عمومی"}],   # تکراری
        "calendar": [{"title": "FOMC Statement", "country": "USD", "in_hours": 3.0},
                     {"title": "Far event", "country": "EUR", "in_hours": 40.0}]}
fomo = {"generated": now, "witness_recent": [{"sym": "TRUMPUSDT", "kind": "buy", "rank": 2, "at": now - 2 * H, "note": "x"}]}

# ── ۱. آیتم‌ها ────────────────────────────────────────────────────────────
items = NP.collect_items(news=news, fomo=fomo, now_ms=now)
kinds = [i["kind"] for i in items]
check("سه خبر یکتا + یک رویداد ۲۴س + یک شاهد فومو = ۵ آیتم (تکراری و رویداد دور حذف)",
      len(items) == 5 and kinds.count("news") == 3 and kinds.count("event") == 1 and kinds.count("fomo") == 1, str(kinds))
check("شناسه پایدار است (همان عنوان = همان id)", NP._iid("news", "A b") == NP._iid("news", " a B "))
check("آیتم فومو دامنهٔ نماد دارد، خبر دامنهٔ BTC", any(i["scope"] == "TRUMPUSDT" for i in items) and all(i["scope"] == "BTC" for i in items if i["kind"] == "news"))

# ── ۲. خواننده‌های قطعی: دامنهٔ خودشان، سکوت بیرون از آن ─────────────────
fed = next(i for i in items if "Fed" in i["title"])
r_fed = {r["agent"]: r for r in NP.rule_readings(fed)}
check("E05 خبر انقباضی فدرال را DOWN می‌خواند", r_fed.get("E05", {}).get("stance") == "DOWN", str(r_fed.get("E05")))
check("E12 دربارهٔ خبر فدرال سکوت می‌کند (بیرون از دامنه)", "E12" not in r_fed)
tether = next(i for i in items if "Tether" in i["title"])
r_t = {r["agent"]: r for r in NP.rule_readings(tether)}
check("E03 خبر منفی تتر را DOWN می‌خواند", r_t.get("E03", {}).get("stance") == "DOWN", str(r_t.get("E03")))
ev = next(i for i in items if i["kind"] == "event")
r_ev = {r["agent"]: r for r in NP.rule_readings(ev)}
check("رویداد تا ۶ ساعت: E16 و E05 هر دو FLAT (پنجرهٔ شلاق)", r_ev.get("E16", {}).get("stance") == "FLAT" and r_ev.get("E05", {}).get("stance") == "FLAT")
fw = next(i for i in items if i["kind"] == "fomo")
r_f = {r["agent"]: r for r in NP.rule_readings(fw)}
check("شاهد فومو: فقط E12 با دامنهٔ نماد", set(r_f) == {"E12"} and r_f["E12"]["scope"] == "TRUMPUSDT")
check("هر برداشت بسته‌ٔ کامل دارد (دلیل + ابطال‌کننده + اطمینان ≤۱)",
      all(r["reasons"] and r["falsifier"] and 0 <= r["confidence"] <= 1 for r in NP.rule_readings(fed) + NP.rule_readings(tether)))

# ── ۳. دفتر و نمره در پوشهٔ موقت ─────────────────────────────────────────
_tmp = Path(tempfile.mkdtemp(prefix="newspoll-"))
_saved = {k: getattr(NP, k) for k in ("BRAIN", "POLLS", "OUTCOMES", "OUT")}
NP.BRAIN = _tmp / "brain"; NP.POLLS = NP.BRAIN / "polls.jsonl"; NP.OUTCOMES = NP.BRAIN / "outcomes.jsonl"; NP.OUT = _tmp / "np.json"
try:
    new, note = NP.poll(items, {}, use_llm=False, now_ms=now)
    check("نظرسنجی قطعی برداشت‌ها را ثبت کرد", len(new) >= 5, str(len(new)))
    new2, _ = NP.poll(items, {}, use_llm=False, now_ms=now)
    check("نظرسنجی دوباره روی همان آیتم‌ها = صفر ردیف تازه (کلید یکتا)", new2 == [])

    # llm بی‌کلید
    import os
    saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        lr, lnote = NP.llm_readings(fed, {})
        check("روش llm بی‌کلید هیچ برداشتی جعل نمی‌کند و دلیل می‌دهد", lr == [] and "ANTHROPIC_API_KEY" in lnote, lnote)
    finally:
        if saved_key:
            os.environ["ANTHROPIC_API_KEY"] = saved_key

    class _Blk:
        def __init__(self, t): self.type = "text"; self.text = t

    class _Resp:
        def __init__(self, t, stop="end_turn"): self.content = [_Blk(t)]; self.stop_reason = stop

    class _Client:
        def __init__(self, t, stop="end_turn"): self.t = t; self.stop = stop; self.messages = self

        def create(self, **kw):
            self.kw = kw
            return _Resp(self.t, self.stop)

    good = json.dumps({"readings": [
        {"agent": "E05", "stance": "DOWN", "scope": "BTC", "horizon_h": 24, "confidence": 0.7, "reasons": ["hawkish"], "falsifier": "btc up"},
        {"agent": "E12", "stance": "ABSTAIN", "scope": "BTC", "horizon_h": 4, "confidence": 0, "reasons": [], "falsifier": ""},
        {"agent": "E99", "stance": "UP", "scope": "BTC", "horizon_h": 4, "confidence": 0.9, "reasons": [], "falsifier": ""},
        {"agent": "E06", "stance": "MOON", "scope": "BTC", "horizon_h": 4, "confidence": 0.9, "reasons": [], "falsifier": ""}]})
    c = _Client(good)
    lr, lnote = NP.llm_readings(fed, {"fear": 40}, client=c)
    check("llm: فقط ایجنتِ فهرست با جهت معتبر پذیرفته می‌شود (ABSTAIN/E99/MOON حذف)",
          [r["agent"] for r in lr] == ["E05"] and lr[0]["method"] == "llm" and lnote == "", str(lr))
    check("llm: خروجی ساخت‌یافته با اسکیمای json_schema خواسته می‌شود",
          c.kw.get("output_config", {}).get("format", {}).get("type") == "json_schema" and c.kw.get("model") == NP.LLM_MODEL)
    lr2, lnote2 = NP.llm_readings(fed, {}, client=_Client("not json"))
    check("llm: پاسخ نامعتبر = بی‌برداشت با دلیل، نه استثنا", lr2 == [] and lnote2)
    lr3, lnote3 = NP.llm_readings(fed, {}, client=_Client("{}", stop="refusal"))
    check("llm: refusal = بی‌برداشت با دلیل", lr3 == [] and "refusal" in lnote3)

    # نمره
    at = now
    def kl_btc(sym):
        base = 100.0 if sym == "BTCUSDT" else 1.0
        return [[at - 5 * H + i * H, base * (1 - 0.01 * i), base * (1 - 0.01 * i) + 0.1, base * (1 - 0.01 * i) - 0.1, base * (1 - 0.01 * (i + 1)), 1]
                for i in range(5 + 30)]                       # ریزش ۱٪ در ساعت → DOWN درست است
    check("افق ناقص نمره نمی‌گیرد", NP.forward_return(kl_btc("BTCUSDT")[:7], at, 24) is None)
    ret4 = NP.forward_return(kl_btc("BTCUSDT"), at, 4)
    check("بازده ۴س منفی محاسبه شد", ret4 is not None and ret4 < -0.03, str(ret4))
    check("داوری: DOWN با ریزش درست، UP غلط، FLAT غلط", NP.grade("DOWN", ret4, "BTC") and not NP.grade("UP", ret4, "BTC") and not NP.grade("FLAT", ret4, "BTC"))
    check("داوری: داخل باند = فقط FLAT درست", NP.grade("FLAT", 0.002, "BTC") and not NP.grade("UP", 0.002, "BTC"))
    n1 = NP.score(klines=kl_btc, now_ms=at + 5 * H)
    check("۵ ساعت بعد فقط برداشت‌های افق ۴س نمره گرفتند", n1 > 0 and all(int(r["horizon_h"]) == 4 for r in NP._rows(NP.OUTCOMES)), str(n1))
    n2 = NP.score(klines=kl_btc, now_ms=at + 5 * H)
    check("نمرهٔ دوباره = صفر (کلید یکتا)", n2 == 0)
    n3 = NP.score(klines=kl_btc, now_ms=at + 30 * H)
    check("۳۰ ساعت بعد افق ۲۴س هم نمره گرفت", n3 > 0)
    outs = NP._rows(NP.OUTCOMES)
    e05 = [o for o in outs if o["agent"] == "E05" and o["stance"] == "DOWN"]
    check("E05 که DOWN گفته بود در ریزش درست شمرده شد", e05 and all(o["hit"] for o in e05))

    # کارنامه و وزن
    board = NP.scoreboard()
    check("زیر ۲۰ نمونه: عدد نه، وزن صفر، دلیل بله", all(v["hit"] is None and v["weight"] == 0.0 and "n=" in v["why"] for v in board.values()))
    fake = [{"agent": "E05", "method": "rule", "hit": True, "cat": "x"}] * 30 + [{"agent": "E05", "method": "rule", "hit": False, "cat": "x"}] * 5
    b2 = NP.scoreboard(fake)["E05|rule"]
    check("۳۰ از ۳۵ درست: CI بالای ۰.۵ → وزن مثبت ولی ≤ سقف ۵٪", b2["hit"] > 0.8 and 0 < b2["weight"] <= NP.SOCIAL_CAP, str(b2))
    coin = [{"agent": "E06", "method": "rule", "hit": i % 2 == 0, "cat": "x"} for i in range(40)]
    b3 = NP.scoreboard(coin)["E06|rule"]
    check("۵۰٪ اصابت (سکه): وزن صفر", b3["weight"] == 0.0 and "سکه" in b3["why"])

    # اجماع
    polls = NP._rows(NP.POLLS)
    cons0 = NP.consensus(items, polls=polls, board=NP.scoreboard(), now_ms=now)
    check("اجماع بی‌کارنامه = بی‌وزن (bias None)، نه عدد ساختگی", cons0.get("BTC", {}).get("bias") is None and cons0["BTC"]["weight"] == 0.0)
    board_w = {"E05|rule": {"weight": 0.05}}
    cons1 = NP.consensus(items, polls=polls, board=board_w, now_ms=now)
    check("با وزنِ E05: اجماع BTC = DOWN با وزن ≤ ۰.۰۵", cons1["BTC"]["bias"] == "DOWN" and 0 < cons1["BTC"]["weight"] <= 0.05, str(cons1["BTC"]))

    snap = NP.build_snapshot(items, new, "", {"fear": 40}, now_ms=now)
    check("بستهٔ شواهد کامل است (قانون ۱۲)", snap["packet_faults"] == [], str(snap["packet_faults"]))
    snap["consensus"] = cons1
    tr = NP.trace_for("ETHUSDT", "LONG", snap)
    check("ردپای سیگنال: لانگ در برابر اجماع DOWN = against", tr["news_align"] == "against" and tr["news_bias_w"] > 0, str(tr))
    check("ردپای سیگنال: شورت هم‌جهت = with", NP.trace_for("ETHUSDT", "SHORT", snap)["news_align"] == "with")
    check("بی‌عکس‌فوری = None نه خطا", NP.trace_for("X", "LONG", "garbage") == {"news_align": None, "news_bias_w": None})
finally:
    for k, v in _saved.items():
        setattr(NP, k, v)

# ── ۴. مرز: خبر در هیچ دروازه/امتیازی نیست ────────────────────────────────
for mod in ("scan", "liam9_strategy", "liam9_h1_strategy"):
    src = (PY / f"{mod}.py").read_text(encoding="utf-8") if (PY / f"{mod}.py").exists() else ""
    check(f"{mod}.py نظرسنجی خبر را وارد تصمیم نمی‌کند", "news_poll" not in src and "news_align" not in src)
check("دروازهٔ روند خبر را نمی‌خواند", "news" not in (HERE / "trend_gate.py").read_text(encoding="utf-8").lower())
from hamid import paper as P                          # noqa: E402
names = [c[0] for c in P.CONDITIONS]
check("دو شرط شبانهٔ اجماع خبری در ماشین بونفرونی هست", sum(1 for n in names if "اجماع خبری" in n) == 2)
tg = (PY / "telegram.py").read_text(encoding="utf-8")
check("گلوگاه ارسال ردپای خبر را فقط از عکس‌فوری می‌نویسد", "_news_trace(" in tg and "news_align" in tg and "news_poll.poll(" not in tg)
reg = json.loads((PY.parents[1] / "config" / "state_registry.json").read_text(encoding="utf-8"))
check("signals/news-poll.json در قرارداد وضعیت ثبت است (قانون ۱۳)", reg["files"].get("news-poll.json", {}).get("owner") == NP.ENGINE)
wf = (PY.parents[1] / ".github" / "workflows" / "news-hunt.yml").read_text(encoding="utf-8")
check("شکار خبر نظرسنجی را می‌دواند و با ناشر مشترک منتشر می‌کند", "hamid.news_poll" in wf and "scripts/publish.sh" in wf and "HEAD:main" not in wf)
check("سقف وزن لایهٔ اجتماعی ۵٪ است (قانون ۱۱)", NP.SOCIAL_CAP == 0.05)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
