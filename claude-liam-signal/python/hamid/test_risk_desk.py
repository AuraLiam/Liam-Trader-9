"""پاسبان میز ریسک و ورود (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دستور حمید: «آیا این پوزیشن در این شرایط ارزش ورود دارد؟» ·
«پول و اهرمی که ارزشش را دارد، طبق مدیریت ریسک و سرمایه» · «ورودی
تصمیم: دامیننس + رویدادها + رأی ۱۲ متخصص».

و مرزهای تغییرناپذیر: محافظ لیکویید حاکم مطلق · سایز از قانون ریسک نه
از اهرم · شاهدِ نبوده اطمینان را پایین می‌آورد نه خنثی · و هیچ سفارشی
از این‌جا نمی‌رود (قانون ۰۵).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import risk_desk as RD                    # noqa: E402

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


GOOD = {"symbol": "BTCUSDT", "direction": "long", "entry": 100.0, "sl": 97.0, "tp": 108.0}
FULL_EV = {"structure": 0.6, "dominance": 0.4, "council": 0.5,
           "memory": 0.3, "events": 0.2}

# ── ۱. هندسهٔ اجباری ────────────────────────────────────────────────────
r = RD.assess({"symbol": "X", "direction": "long", "entry": 100.0, "sl": 97.0}, FULL_EV)
check("سیگنال بی‌تارگت باطل است (قرارداد اجرا ۲۰ اوت)",
      r["verdict"] == "NO_ENTRY" and any("tp" in x for x in r["rejects"]), str(r["rejects"]))
r = RD.assess({"symbol": "X", "direction": "long", "entry": 100.0, "tp": 108.0}, FULL_EV)
check("سیگنال بی‌استاپ هم باطل است", r["verdict"] == "NO_ENTRY")
r = RD.assess({**GOOD, "direction": ""}, FULL_EV)
check("بی‌جهت، حکم نمی‌گیرد", r["verdict"] == "NO_ENTRY" and any("جهت" in x for x in r["rejects"]))
r = RD.assess({**GOOD, "sl": 103.0}, FULL_EV)
check("لانگ با استاپ بالای ورود = ستاپ خراب، نه ریسکِ زیاد",
      r["verdict"] == "NO_ENTRY" and any("ستاپ خراب" in x for x in r["rejects"]), str(r["rejects"]))
r = RD.assess({"symbol": "X", "direction": "short", "entry": 100.0, "sl": 103.0, "tp": 92.0},
              FULL_EV)
check("شورتِ درست از دروازهٔ هندسه رد می‌شود", not r["rejects"], str(r["rejects"]))
r = RD.assess({"symbol": "X", "direction": "short", "entry": 100.0, "sl": 97.0, "tp": 92.0},
              FULL_EV)
check("شورت با استاپ زیر ورود رد می‌شود", r["verdict"] == "NO_ENTRY")

# ── ۲. کارمزد و RR خالص ─────────────────────────────────────────────────
check("کارمزد در واحد R محاسبه می‌شود", RD.fee_in_r(100.0, 97.0) == 0.05,
      str(RD.fee_in_r(100.0, 97.0)))
check("استاپ تنگ سهم کارمزد را چند برابر می‌کند (دام اسکالپ)",
      RD.fee_in_r(100.0, 99.8) > RD.fee_in_r(100.0, 95.0))
r = RD.assess({"symbol": "X", "direction": "long", "entry": 100.0, "sl": 99.7, "tp": 101.0},
              FULL_EV)
check("کارمزد ≥۰.۲۵R رد می‌شود — دامِ اسکالپ (قانون ۱۶)",
      any("دامِ اسکالپ" in x for x in r["rejects"]), str(r["rejects"]))
check("RR خالص، کارمزد را کم می‌کند نه فقط اسمی را بگوید",
      RD.net_rr(100.0, 97.0, 106.0) == round(2.0 - 0.05, 3),
      str(RD.net_rr(100.0, 97.0, 106.0)))
r = RD.assess({"symbol": "X", "direction": "long", "entry": 100.0, "sl": 97.0, "tp": 103.0},
              FULL_EV)
check("RR خالص زیر کف رد می‌شود",
      any("زیر کف" in x for x in r["rejects"]), str(r["rejects"]))

# ── ۳. محافظ لیکویید حاکم مطلق ──────────────────────────────────────────
cap, why = RD.leverage_cap(100.0, 97.0)
check("اهرم از ۵۰÷استاپ٪ رد نمی‌کند", cap == 16, f"{cap} — {why}")
cap, _ = RD.leverage_cap(100.0, 99.0)
check("استاپ تنگ هم از سقف داشبورد رد نمی‌کند",
      cap == RD.MAX_LEVERAGE, str(cap))
cap, _ = RD.leverage_cap(100.0, 80.0)
check("استاپ گشاد اهرم را واقعاً پایین می‌آورد", cap == 2, str(cap))
r = RD.assess(GOOD, FULL_EV, equity=1000.0)
check("اطمینان بالا هم اهرم را از سقف رد نمی‌کند",
      r["leverage"] <= r["leverage_cap"] <= RD.MAX_LEVERAGE, str(r["leverage"]))
check("دلیل سقف اهرم عددی است، نه ادعا",
      "محافظ لیکویید" in r["leverage_why"] and "٪" in r["leverage_why"])

# ── ۴. اطمینان: شاهدِ نبوده سهمش را می‌سوزاند ───────────────────────────
c_full, parts, missing = RD.confidence({k: 1.0 for k in RD.EVIDENCE_W})
check("همهٔ شواهدِ کاملاً مثبت = اطمینان ۱", c_full == 1.0 and missing == [], str(c_full))
c_half, _, missing = RD.confidence({"structure": 1.0})
check("یک شاهدِ خوب، اطمینان کامل نمی‌سازد",
      c_half == RD.EVIDENCE_W["structure"] and len(missing) == 4, str(c_half))
check("و نام شواهدِ نیامده صریح گزارش می‌شود", "dominance" in missing)
c_neg, _, _ = RD.confidence({k: -1.0 for k in RD.EVIDENCE_W})
check("شواهد کاملاً منفی = اطمینان صفر", c_neg == 0.0, str(c_neg))
c_zero, _, _ = RD.confidence({})
check("بی‌هیچ شاهدی، اطمینان صفر است نه ۵۰٪", c_zero == 0.0, str(c_zero))
check("جمع وزن شواهد دقیقاً ۱ است", abs(sum(RD.EVIDENCE_W.values()) - 1.0) < 1e-9)
r = RD.assess(GOOD, {}, equity=1000.0)
check("بی‌شاهد، ورود ندارد", r["verdict"] == "NO_ENTRY" and r["size_share"] == 0.0)
check("و دلیل روشِ اطمینان روی خروجی نوشته می‌شود",
      "سهمش را می‌سوزاند" in r["confidence_note"])

# ── ۵. سایز از قانون ریسک، نه از اهرم ──────────────────────────────────
r = RD.assess(GOOD, {k: 1.0 for k in RD.EVIDENCE_W}, equity=1000.0)
check("اطمینان بالا = سایز کامل", r["size_share"] == 1.0 and r["verdict"] == "ENTER")
check("نامی از قانون ریسک می‌آید: ۲٪ از ۱۰۰۰ روی استاپ ۳٪ = ۶۶۶.۶۷",
      r["notional_usd"] == 666.67, str(r["notional_usd"]))
check("مارجین = نامی ÷ اهرم", r["margin_usd"] == round(666.67 / r["leverage"], 2),
      f"{r['margin_usd']} vs {round(666.67/r['leverage'],2)}")
r2 = RD.assess({**GOOD, "sl": 99.0}, {k: 1.0 for k in RD.EVIDENCE_W}, equity=1000.0)
check("استاپ تنگ‌تر → نامی بزرگ‌تر، ولی ریسک همان ۲٪ می‌ماند",
      r2["notional_usd"] > r["notional_usd"] and r2["risk_pct"] == r["risk_pct"])
check("و همین تفکیک روی خروجی توضیح داده می‌شود",
      "اهرم فقط مارجین" in r["size_note"])
mid = RD.assess(GOOD, {"structure": 1.0, "dominance": 1.0, "council": 0.2}, equity=1000.0)
check("اطمینان متوسط = نصف سایز", mid["size_share"] == 0.5, str(mid["size_share"]))
check("بی‌سرمایه، عدد پول ساخته نمی‌شود",
      RD.assess(GOOD, {k: 1.0 for k in RD.EVIDENCE_W})["notional_usd"] is None)

# ── ۶. سقف پوزیشن هم‌زمان ───────────────────────────────────────────────
r = RD.assess(GOOD, {k: 1.0 for k in RD.EVIDENCE_W}, equity=1000.0, open_positions=3)
check("سقف ۳ پوزیشن هم‌زمان رعایت می‌شود (قانون ۱۰)",
      r["verdict"] == "NO_ENTRY" and any("سقف هم‌زمان" in x for x in r["rejects"]))
check("زیر سقف مانعی نیست",
      RD.assess(GOOD, {k: 1.0 for k in RD.EVIDENCE_W}, equity=1000.0,
                open_positions=2)["verdict"] == "ENTER")

# ── ۷. رأی شورا ورودی است، نه وتو ──────────────────────────────────────
prop = {"subject": "BTCUSDT",
        "evidence": {"trend_4h": 0.8, "risk": 0.7, "dominance": 0.6,
                     "data_quality": 0.9, "order_block": 0.5}}
r = RD.from_council(setup=GOOD, evidence={"structure": 0.8, "dominance": 0.6,
                                          "memory": 0.4, "events": 0.3},
                    proposal=prop, equity=1000.0)
check("رأی شورا وارد شواهد می‌شود", any(p["key"] == "council" for p in r["confidence_parts"]))
check("و کارنامهٔ جلسه هم روی خروجی می‌آید", r["council"] and r["council"]["decision"])
bad_geom = RD.from_council(setup={**GOOD, "sl": 103.0}, evidence={"structure": 1.0},
                           proposal=prop, equity=1000.0)
check("رأی مثبت شورا، ستاپِ خرابِ هندسه را نجات نمی‌دهد — دروازه بالاتر از رأی است",
      bad_geom["verdict"] == "NO_ENTRY", str(bad_geom["rejects"]))
check("سهم شورا در اطمینان محدود است، نه تعیین‌کننده",
      RD.EVIDENCE_W["council"] <= 0.25)

# ── ۸. مرز ──────────────────────────────────────────────────────────────
check("مرز روی هر حکم نوشته می‌شود",
      "LIVE_EXECUTION خاموش" in r["boundary"] and "پیشنهاد" in r["boundary"])
src = (HERE / "risk_desk.py").read_text(encoding="utf-8")
for bad in ("requests.post", "urlopen", "send_order", "place_order", "LIVE_EXECUTION = True"):
    check(f"میز ریسک «{bad}» ندارد — هیچ سفارشی از این‌جا نمی‌رود (قانون ۰۵)",
          bad not in src)
check("سقف اهرم با عدد داشبورد یکی است", RD.MAX_LEVERAGE == 20)
check("محافظ لیکویید همان ۵۰÷استاپ٪ است", RD.LIQ_GUARD == 50.0)
check("ریسک هر معامله ۲٪ است", RD.RISK_PCT == 2.0)

# ── ۹. سیم‌کشی ──────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
wf = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
check("پاسبان میز ریسک در دروازهٔ چرخه می‌دود", "hamid.test_risk_desk" in wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
