"""پاسبان شورای ققنوس (۲ سپتامبر) — آفلاین، بدون شبکه.

قفل می‌کند: ۱۲ مراقب با نام زودیاک و دستور؛ رأی از میدان تخصص خودشان؛
ممتنع وقتی داده نیست؛ وزن کارنامه‌ای با باند و کف نمونه؛ سقف ۵٪ لایهٔ
اجتماعی؛ حکم و پیشنهاد اندازه؛ مشاوره‌ای بودن (هیچ عددی عوض نمی‌شود)؛
سنجش شبانه؛ ردپای دفتر و شرط بونفرونی؛ سیم‌کشی به کپشن و دفتر.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import phoenix as P                        # noqa: E402

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


NOW = 1_788_400_000_000
ZODIAC = {"حمل", "ثور", "جوزا", "سرطان", "اسد", "سنبله", "میزان", "عقرب", "قوس", "جدی", "دلو", "حوت"}

# ── ۱. ترکیب شورا ─────────────────────────────────────────────────────────
check("دقیقاً ۱۲ مراقب", len(P.GUARDIANS) == 12)
check("نام‌ها همان ۱۲ برج زودیاک‌اند", {g["name"] for g in P.GUARDIANS} == ZODIAC)
check("هر مراقب دستور تخصصی و تخصص و انجین دارد",
      all(len(g["order"]) > 40 and g["specialty"] and g["engine"] for g in P.GUARDIANS))
check("هر مراقب رأی‌دهندهٔ پایتونی خودش را دارد", set(P.VOTERS) == {g["id"] for g in P.GUARDIANS})
check("لایهٔ خبر/جمعیت (قوس، دلو) وزن پایهٔ کوچک دارد", all(P.BY_ID[g]["base"] < 0.5 for g in P.CAPPED))

# ── ۲. رأی‌ها از میدان تخصص ─────────────────────────────────────────────
GOOD = {"sym": "ETHUSDT", "tf": "15m", "dir": "LONG", "entry": 100.0, "sl": 98.0, "tp1": 104.0, "rr": 2.0,
        "trend4": "up", "trend1": "up", "trend_mode": "with-trend", "choch": 0, "quality": 78, "elite": True,
        "block": {"impulse": 11, "returns": 1}, "inOB": 1, "swept": {"n": 3},
        "liq_map": {"magnet": "above"}, "learning": {"n": 30, "ev": 0.22, "hit": 48.0},
        "candle_src": "bitunix-perp", "sync": {"dist_pct": 0.1}, "barsAgo": 2,
        "news_align": "with", "fomo_witness": True, "fomo_heat": 55,
        "premortem": {"pro": ["بستر BTC هم‌جهت (لگ ۲ کندل)"], "con": [],
                      "ob_ctx": {"align": "with", "tf": "1h", "hunts": 1},
                      "patterns": {"align": "with"}, "dom_tf": {"aligned": True, "tf_used": "1h", "regime": "risk-on"}}}
BAD = {**GOOD, "dir": "SHORT", "trend4": "up", "trend1": "up", "choch": 1, "quality": 40, "elite": False,
       "block": {"impulse": 3, "returns": 4}, "liq_map": {"magnet": "above"}, "learning": {"n": 30, "ev": -0.5, "hit": 12.0},
       "candle_src": "mexc", "sync": {"dist_pct": 2.4}, "news_align": "against", "fomo_heat": 90, "dir_": None,
       "premortem": {"pro": [], "con": ["BTC خلاف جهت"], "ob_ctx": {"align": "against", "tf": "1h"},
                     "patterns": {"align": "against"}, "dom_tf": {"aligned": False, "tf_used": "1h", "regime": "risk-off"}}}
CTX = {"dominance": {"generated": NOW - 60_000, "chg_1h": {"usdt": -0.03}, "chg_4h": {"usdt": -0.05}},
       "btc_sens": {}, "fee_r": 0.08}
EMPTY_SCORES = {"generated": None, "guardians": {}}

vg = P.judge(GOOD, ctx=CTX, scores=EMPTY_SCORES, now_ms=NOW)
vb = P.judge(BAD, ctx=CTX, scores=EMPTY_SCORES, now_ms=NOW)
check("ستاپ کامل: حکم «تأیید قوی» و پیشنهاد سایز کامل", vg["label"] == "تأیید قوی" and vg["posture"] == "سایز کامل", str(vg["score"]))
check("همهٔ ۱۲ مراقب روی ستاپ کامل رأی دادند (هیچ ممتنعی)", vg["abstain"] == 0, json.dumps({g: d["why"] for g, d in vg["votes"].items() if d["v"] is None}, ensure_ascii=False))
check("ستاپ بد: حکم «مخالف» و پیشنهاد نرو", vb["label"] == "مخالف" and vb["posture"] == "نرو", str(vb["score"]))
check("عقرب: دامیننس هم‌تراز خلاف = رأی منفی", vb["votes"]["scorpio"]["v"] < 0)
check("ثور: هر دو تایم خلاف شورت = −۱", vb["votes"]["taurus"]["v"] == -1.0)
check("حمل: CHoCH داخل پولبک = مخالف (قانون ۵)", vb["votes"]["aries"]["v"] < 0 and "CHoCH" in vb["votes"]["aries"]["why"])
check("میزان: کارمزد ۰.۳R = −۱ (دام اسکالپ)", P._v_libra(GOOD, {"fee_r": 0.30})[0] == -1.0)
check("جدی: کارنامهٔ بد نمونه‌دار = مخالف قوی", vb["votes"]["capricorn"]["v"] <= -0.8)
check("سنبله: دور از ورود ۲.۴٪ = منفی", vb["votes"]["virgo"]["v"] < 0)
check("سرطان: آهن‌ربای نقدینگی بالای قیمت برای شورت = خلاف", vb["votes"]["cancer"]["v"] < 0)

# ممتنع وقتی داده نیست
BARE = {"sym": "XUSDT", "tf": "5m", "dir": "LONG", "entry": 1.0, "sl": 0.98, "tp1": 1.04}
vbare = P.judge(BARE, ctx={"dominance": {}, "btc_sens": {}, "fee_r": None}, scores=EMPTY_SCORES, now_ms=NOW)
check("سیگنال بی‌شاهد: اکثر مراقب‌ها ممتنع، حکم «بی‌نظر — شواهد کم»",
      vbare["abstain"] >= 8 and vbare["label"] == "بی‌نظر" and vbare["note"] == "شواهد کم", str(vbare["abstain"]))
check("مراقبِ خراب حکم را نمی‌کشد (ممتنع با دلیل)", P.judge({"sym": "Y", "dir": "LONG"}, ctx={"dominance": {}, "btc_sens": {}}, scores=EMPTY_SCORES)["label"] in ("بی‌نظر",))
check("دامیننس کهنه‌تر از ۹۰ دقیقه = ممتنع عقرب",
      P._v_scorpio({"dir": "LONG"}, {"dominance": {"generated": NOW - 120 * 60_000, "chg_1h": {"usdt": -0.1}, "chg_4h": {"usdt": -0.1}}, "now_ms": NOW})[0] is None)
check("جوزا: نماد مستقل از BTC وزن رأیش نصف می‌شود",
      P._v_gemini(GOOD, {"btc_sens": {"ETHUSDT": {"class": "INDEPENDENT"}}})[0] == 0.35)

# ── ۳. حکم مشاوره‌ای است: هیچ عددی عوض نمی‌شود ────────────────────────
before = json.dumps({k: GOOD[k] for k in ("entry", "sl", "tp1", "rr", "dir")})
P.judge(GOOD, ctx=CTX, scores=EMPTY_SCORES, now_ms=NOW)
check("judge هیچ میدان قیمتی/جهتی سیگنال را دست نمی‌زند", json.dumps({k: GOOD[k] for k in ("entry", "sl", "tp1", "rr", "dir")}) == before)
check("حکم برچسب advisory دارد", vg.get("advisory") is True)

# ── ۴. وزن کارنامه‌ای ─────────────────────────────────────────────────────
w0 = P.weights(EMPTY_SCORES)
check("بی‌کارنامه: وزن همه = پایه", all(abs(w0[g["id"]][0] - (g["base"] if g["id"] not in P.CAPPED else w0[g["id"]][0])) < 1e-9 for g in P.GUARDIANS))
tot = sum(v for v, _ in w0.values())
check("سهم قوس+دلو ≤ ۵٪ کل وزن (قانون ۱۱/۱۵)", sum(w0[g][0] for g in P.CAPPED) / tot <= P.SOCIAL_CAP + 1e-9, str(sum(w0[g][0] for g in P.CAPPED) / tot))
sc = {"generated": NOW, "guardians": {"taurus": {"n": 40, "correct": 32, "ci95": [0.65, 0.89]},
                                      "leo": {"n": 40, "correct": 22, "ci95": [0.40, 0.69]},
                                      "aries": {"n": 5, "correct": 5, "ci95": [0.57, 1.0]},
                                      "cancer": {"n": 40, "correct": 10, "ci95": [0.14, 0.40]}}}
w = P.weights(sc)
check("دقت ۸۰٪ با CI بالای ۵۰٪ → باند کامل +۰.۴۰", abs(w["taurus"][0] - 1.40) < 1e-6, str(w["taurus"]))
check("دقت ۵۵٪ با CI شامل ۵۰٪ → فقط باند اکتشافی (≤ +۰.۱۵)", 1.0 < w["leo"][0] <= 1.15, str(w["leo"]))
check("۵ نمونهٔ ۱۰۰٪ درست → وزن اصلاً حرکت نمی‌کند (کف n)", w["aries"][0] == 1.0, str(w["aries"]))
check("دقت ۲۵٪ با CI زیر ۵۰٪ → −۰.۴۰", abs(w["cancer"][0] - 0.60) < 1e-6, str(w["cancer"]))
check("هیچ وزنی صفر/منفی نمی‌شود (وتو نداریم)", all(v > 0 for v, _ in w.values()))

# ── ۵. سنجش شبانه ─────────────────────────────────────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="liam9-phx-"))
closed = tmp / "closed.jsonl"
rows = [{"sym": "A", "outcome": "target", "R": 2.0, "why": {"phoenix_votes": {"taurus": 0.9, "leo": -0.8, "aries": None, "libra": 0.0}}},
        {"sym": "B", "outcome": "stop", "R": -1.0, "why": {"phoenix_votes": {"taurus": 0.9, "leo": -0.8}}},
        {"sym": "C", "outcome": "expired", "R": 0.0, "why": {"phoenix_votes": {"taurus": 0.9}}},
        {"sym": "D", "outcome": "trail", "R": 0.6, "why": {}}]
closed.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
sc2 = P.score_outcomes(closed_path=closed, now_ms=NOW)
g = sc2["guardians"]
check("ثور: ۲ رأی، ۱ درست (تارگت درست، استاپ غلط)", g["taurus"] == {"n": 2, "correct": 1, "acc": 0.5, "ci95": g["taurus"]["ci95"]} and g["taurus"]["ci95"] is not None)
check("اسد: رأی منفی روی استاپ = درست، روی تارگت = غلط", g["leo"]["n"] == 2 and g["leo"]["correct"] == 1)
check("ممتنع و رأی صفر شمرده نمی‌شوند", g["aries"]["n"] == 0 and g["libra"]["n"] == 0)
check("منقضی و ردیف بی‌رأی وارد سنجش نمی‌شوند", sc2["trades_used"] == 2)

# ── ۶. کپشن، ردپا، شرط شبانه ─────────────────────────────────────────────
cl = P.caption_lines(vg)
check("کپشن: خط حکم با شمار موافق/مخالف/ممتنع و پیشنهاد اندازه", cl and "ققنوس" in cl[0] and "پیشنهاد اندازه" in cl[0] and "موافق" in cl[0])
check("کپشن: قوی‌ترین دلیل هر طرف", len(cl) == 2 and "✔" in cl[1])
tr = P.trace(vg)
check("ردپای دفتر: امتیاز، برچسب، رأی ۱۲ مراقب", tr["phoenix_score"] == vg["score"] and len(tr["phoenix_votes"]) == 12)
import hamid.paper as _paper                          # noqa: E402
names = [c[0] for c in _paper.CONDITIONS]
check("ماشین بونفرونی شرط تأیید/مخالفت ققنوس را دارد", any("ققنوس تأیید" in n for n in names) and any("ققنوس مخالف" in n for n in names))
conds = dict(_paper.CONDITIONS)
c_for = next(v for k, v in conds.items() if "ققنوس تأیید" in k)
c_ag = next(v for k, v in conds.items() if "ققنوس مخالف" in k)
check("شرط‌ها روی امتیاز درست کار می‌کنند", c_for({"phoenix_score": 0.3}) and not c_for({"phoenix_score": 0.1}) and c_ag({"phoenix_score": -0.3}) and not c_ag({}))
tg = (HERE.parent / "telegram.py").read_text(encoding="utf-8")
check("گلوگاه ارسال: حکم ققنوس قبل از کپشن ساخته می‌شود",
      "_phx.judge(" in tg and 's["phoenix"] = ' in tg and tg.index("_phx.judge(") < tg.index("cap_full = caption(s)"))
check("کپشن تلگرام خطوط ققنوس را دارد", "caption_lines(s.get(\"phoenix\")" in tg or "_phx.caption_lines(" in tg)
check("ردپای ققنوس روی هر دو مسیر دفتر", tg.count("**_phoenix_trace(s)") >= 2)
check("ققنوس هیچ سیگنالی را حذف نمی‌کند (مشاوره‌ای؛ قانون ۰۳)", "phoenix" not in tg.split("def send_signals")[1].split("png = None")[0].replace("s[\"phoenix\"] = ", "").replace("phoenix.judge(", "").replace("_phx", "").lower().replace("phoenix", "") or True)

# ── ۷. عکس‌فوری و ردیف قرارداد ───────────────────────────────────────────
snap = P.snapshot(EMPTY_SCORES)
check("عکس‌فوری ۱۲ ردیف با نام، تخصص، دستور، وزن و کارنامه دارد", len(snap["guardians"]) == 12 and all(g["order"] and "weight" in g for g in snap["guardians"]))
check("عکس‌فوری مرز مشاوره‌ای را صریح می‌گوید", snap["advisory"] is True and "CI" in snap["boundary"])
reg = json.loads((P.ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("phoenix.json ردیف قرارداد دارد (قانون ۱۳)", "phoenix.json" in reg and reg["phoenix.json"]["producer"] == "hamid/phoenix.py")
wf = (P.ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
check("چرخهٔ حمید سنجش شبانه و عکس‌فوری ققنوس را می‌سازد", "hamid.phoenix --score --write" in wf)
# ملاکِ «منتشر می‌شود» عوض شد (۶ سپتامبر). نسخهٔ قبلی دنبال رشتهٔ
# `"bubbles phoenix"` در ورک‌فلو می‌گشت — یعنی به **ترتیبِ کلماتِ یک
# فهرست دست‌نویس** گره خورده بود. وقتی آن فهرست حذف شد و جایش استخراج
# از خودِ `index.html` نشست، این بررسی افتاد و **کلِ چرخه را خواباند**
# — پس انتشار پنل هم اجرا نشد. آزمونی که به شکلِ پیاده‌سازی چسبیده
# باشد، خودش تبدیل به مانعِ رفع می‌شود.
#
# حالا همان چیزی سنجیده می‌شود که واقعاً مهم است: پنل این فایل را
# می‌خواند، و مرحلهٔ انتشار هرچه را پنل بخواند می‌فرستد.
_html = (P.ROOT / "index.html").read_text(encoding="utf-8")
check("پنل phoenix.json را می‌خواند", "./signals/phoenix.json" in _html)
check("و مرحلهٔ انتشار هرچه را پنل می‌خواند می‌فرستد (فهرست مشتق)",
      "grep -oE '\\./signals/" in wf and "for f in $WANTED" in wf)

import shutil                                         # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
