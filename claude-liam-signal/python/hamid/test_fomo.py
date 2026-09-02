"""پاسبان اتاق فومو (۲ سپتامبر).

سه خطر که این آزمون می‌بندد:
۱. پیامی از غیرِ حمید (چت دیگر) وارد دفتر شاهد شود.
۲. شاهد/نمره تکراری ثبت شود یا افقِ ناقص نمره بگیرد (CI ساختگی).
۳. فومو دروازه یا امتیازِ مثبت شود — فقط ثبت، فقط شرط شبانه.
"""
import inspect
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import fomo as F                           # noqa: E402

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


# ── ۱. دستور زبان ─────────────────────────────────────────────────────────
p = F.parse("fomo TRUMP buy 3 top trader long")
check("پارس انگلیسی: نماد/نوع/رتبه/یادداشت", p == {"sym": "TRUMPUSDT", "kind": "buy", "rank": 3, "note": "top trader long"}, str(p))
p2 = F.parse("فومو doge ترند")
check("پارس فارسی: نوع ترند، بی‌رتبه", p2 and p2["sym"] == "DOGEUSDT" and p2["kind"] == "trend" and p2["rank"] is None, str(p2))
check("نمادِ با USDT دوباره USDT نمی‌گیرد", F.parse("fomo ETHUSDT sell")["sym"] == "ETHUSDT")
check("متن آزاد پارس نمی‌شود (حدس ممنوع)", F.parse("سلام امروز چطوری") is None and F.parse("fomo") is None)
check("نوعِ ناشناخته رد می‌شود", F.parse("fomo BTC moon") is None)
check("پیام غیررشته‌ای None", F.parse(None) is None and F.parse(123) is None)

# ── ۲. خواندن فقط از چت حمید + یکتایی + offset ────────────────────────────
_tmp = Path(tempfile.mkdtemp(prefix="fomo-"))
_saved = {k: getattr(F, k) for k in ("BRAIN", "WITNESS", "OUTCOMES", "OFFSET", "OUT")}
F.BRAIN = _tmp / "brain"
F.WITNESS = F.BRAIN / "witness.jsonl"
F.OUTCOMES = F.BRAIN / "outcomes.jsonl"
F.OFFSET = F.BRAIN / "offset.json"
F.OUT = _tmp / "fomo.json"
try:
    now = int(time.time() * 1000)
    ups = [
        {"update_id": 101, "message": {"chat": {"id": 555}, "date": now // 1000 - 60, "text": "fomo TRUMP buy 2"}},
        {"update_id": 102, "message": {"chat": {"id": 999}, "date": now // 1000 - 50, "text": "fomo BTC buy"}},   # چت غریبه
        {"update_id": 103, "message": {"chat": {"id": 555}, "date": now // 1000 - 40, "text": "حالت چطوره"}},      # بی‌دستور
        {"update_id": 104, "message": {"chat": {"id": 555}, "date": now // 1000 - 30, "text": "فومو PEPE فروش 1 ریزش"}},
    ]
    calls = []

    def fetch(off):
        calls.append(off)
        return [u for u in ups if u["update_id"] >= off]

    r = F.ingest(fetch=fetch, token="t", chat_id="555", now_ms=now)
    check("فقط دو پیامِ معتبرِ حمید ثبت شد", [x["update_id"] for x in r["rows"]] == [101, 104], str(r))
    check("پیام چت غریبه رد و شمرده شد", r["rejected"] == 1)
    check("offset روی آخرین update_id نشست", json.loads(F.OFFSET.read_text())["offset"] == 104)
    r2 = F.ingest(fetch=fetch, token="t", chat_id="555", now_ms=now)
    check("اجرای دوم از offset+1 می‌خواند و چیزی دوباره ثبت نمی‌کند", calls[-1] == 105 and r2["rows"] == [])
    check("دفتر شاهد دقیقاً ۲ ردیف دارد (append-only، بی‌تکرار)", len(F.witnesses()) == 2)
    r3 = F.ingest(fetch=fetch, token="", chat_id="555", now_ms=now)
    check("بی‌توکن = چیزی خوانده نمی‌شود، با دلیل", r3["rows"] == [] and "توکن" in r3["why"])

    def boom(off):
        raise OSError("net")
    r4 = F.ingest(fetch=boom, token="t", chat_id="555", now_ms=now)
    check("شبکهٔ خراب = بی‌ردیف، بی‌استثنا، با دلیل", r4["rows"] == [] and "getUpdates" in r4["why"])

    # ── ۳. نمرهٔ شاهد فقط با افقِ کامل ─────────────────────────────────
    at = F.witnesses()[0]["at"]
    bar = 300000

    def kl_full(sym):
        # ۵د از یک ساعت قبل تا ۲۵ ساعت بعد؛ صعودی ملایم
        return [[at - 12 * bar + i * bar, 100 + i * 0.01, 100 + i * 0.01 + 0.5, 100 + i * 0.01 - 0.5, 100 + i * 0.01 + 0.005, 1]
                for i in range(12 + 300)]

    def kl_short(sym):
        return [[at + i * bar, 100, 101, 99, 100.2, 1] for i in range(6)]     # فقط ۳۰ دقیقه

    st = F.forward_stats(kl_short("x"), at, 3600)
    check("افق ۱س با ۳۰ دقیقه داده = None (نمرهٔ نیمه‌کاره نه)", st is None)
    st1 = F.forward_stats(kl_full("x"), at, 3600)
    check("افق کامل: بازده و MFE/MAE محاسبه می‌شود", st1 and st1["ret"] > 0 and st1["mfe"] >= st1["ret"] and st1["mae"] <= 0, str(st1))
    n1 = F.score_outcomes(klines=kl_full, now_ms=at + 2 * 3600 * 1000)
    check("دو ساعت بعد: فقط افق ۱س برای هر دو شاهد نمره گرفت (۲ ردیف)", n1 == 2, str(n1))
    n2 = F.score_outcomes(klines=kl_full, now_ms=at + 2 * 3600 * 1000)
    check("اجرای دوبارهٔ همان لحظه = صفر ردیف تازه (کلید یکتا)", n2 == 0)
    n3 = F.score_outcomes(klines=kl_full, now_ms=at + 26 * 3600 * 1000)
    check("۲۶ ساعت بعد: افق‌های ۴س و ۲۴س هم نمره گرفتند (۴ ردیف)", n3 == 4, str(n3))
    tr = F.track_record()
    check("کارنامه زیر ۲۰ نمونه عدد نمی‌دهد، دلیل می‌دهد", tr["1h"]["hit"] is None and "n=" in tr["1h"]["why"])

    # ── ۴. داغی جمعیت ──────────────────────────────────────────────────
    h = F.crowd_heat(fear=80, funding_pct=0.05, trend_rank=1)
    check("همه داغ → ≥۹۰ و برچسب داغ", h["heat"] >= 90 and h["label"] == "داغ", str(h))
    c = F.crowd_heat(fear=10, funding_pct=-0.05, trend_rank=None)
    check("ترس + فاندینگ منفی، بی‌ترند → ≤۱۰ (جزء غایب از مخرج حذف)", c["heat"] <= 10 and "trending" not in c["components"], str(c))
    e = F.crowd_heat()
    check("بی‌داده = heat None با دلیل، نه عدد ساختگی", e["heat"] is None and e["why"])
    mid = F.crowd_heat(fear=50, funding_pct=0.0, trend_rank=None)
    check("خنثی = ۵۰", mid["heat"] == 50.0)

    # ── ۵. عکس‌فوری و ردپای سیگنال ───────────────────────────────────
    market = {"fear": 75, "funding_avg": 0.02, "trending": [{"sym": "TRUMPUSDT", "rank": 1, "name": "T"},
                                                            {"sym": "ZZZUSDT", "rank": 2, "name": "Z"}], "errors": {}}
    snap = F.build_snapshot(market, tradable=lambda s: (s == "TRUMPUSDT", "" if s == "TRUMPUSDT" else "نیست"), now_ms=now)
    check("بستهٔ شواهد کامل است (قانون ۱۲)", snap["packet_faults"] == [], str(snap["packet_faults"]))
    check("ترند غیرقابل‌معامله برچسب می‌خورد، حذف نمی‌شود", any(r["sym"] == "ZZZUSDT" and r["tradable"] is False for r in snap["trending"]))
    sf = F.snapshot_for("TRUMPUSDT", snap)
    check("ردپای سیگنال: داغی نماد + شاهد ۲۴ساعته", sf["fomo_witness"] is True and sf["fomo_heat"] is not None, str(sf))
    sf2 = F.snapshot_for("ETHUSDT", snap)
    check("نماد بی‌شاهد: witness=False، داغیِ بازار", sf2["fomo_witness"] is False and sf2["fomo_heat"] == snap["market"]["heat"], str(sf2))
    check("عکس‌فوری غایب = None نه خطا", F.snapshot_for("X", None) == {"fomo_heat": None, "fomo_witness": None}
          or F.OUT.exists() is False)
finally:
    for k, v in _saved.items():
        setattr(F, k, v)

# ── ۶. مرز: فقط ثبت و شرط شبانه؛ نه دروازه، نه امتیاز مثبت ───────────────
for mod in ("scan", "liam9_strategy", "liam9_h1_strategy", "trend_gate"):
    p_ = PY / f"{mod}.py" if (PY / f"{mod}.py").exists() else HERE / f"{mod}.py"
    src = p_.read_text(encoding="utf-8") if p_.exists() else ""
    check(f"{mod}.py فومو را وارد امتیاز/دروازه نمی‌کند", "fomo" not in src.lower())
from hamid import paper as P                          # noqa: E402
names = [c[0] for c in P.CONDITIONS] if hasattr(P, "CONDITIONS") else []
check("دو شرط شبانهٔ فومو در ماشین بونفرونی هست",
      any("داغی" in n for n in names) and any("فومو" in n for n in names), str([n for n in names if "فومو" in n or "داغی" in n]))
tg = (PY / "telegram.py").read_text(encoding="utf-8")
check("گلوگاه ارسال ردپای فومو را روی دفتر سیگنال می‌نویسد", "fomo_heat" in tg and "fomo_witness" in tg)
check("ردپا فقط از عکس‌فوری خوانده می‌شود (بدون شبکه در گلوگاه)", "snapshot_for(" in tg and "market_inputs(" not in tg)
reg = json.loads((PY.parents[1] / "config" / "state_registry.json").read_text(encoding="utf-8"))
check("signals/fomo.json در قرارداد وضعیت ثبت است (قانون ۱۳)", "fomo.json" in reg["files"] and reg["files"]["fomo.json"].get("owner") == F.ENGINE)
wf = (PY.parents[1] / ".github" / "workflows" / "fomo.yml").read_text(encoding="utf-8")
check("ورک‌فلو فومو ناشر مشترک و محیط مشترک دارد (قانون ۱۴)", "scripts/publish.sh" in wf and "requirements-ci.txt" in wf and "HEAD:main" not in wf)
check("ورک‌فلو فومو تنها مصرف‌کنندهٔ getUpdates با offset است",
      sum(1 for f in (PY.parents[1] / ".github" / "workflows").glob("*.yml") if "hamid.fomo" in f.read_text(encoding="utf-8")) == 1)
src = inspect.getsource(F)
check("ماژول هیچ‌جا به تلگرام نمی‌فرستد (فقط می‌خواند)", "sendMessage" not in src and "sendPhoto" not in src)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
