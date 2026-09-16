"""پاسبان دو بازوی ۱۶ سپتامبر — «فقط ۱۵د» و «هندسهٔ ×۲ روی ۵د».

چهار راه خرابی که قفل می‌شود: (۱) بازو وارد آمار سیگنال شود، (۲) آینه
جفت نباشد (هندسه غلط یا کارمزد بازمحاسبه نشود)، (۳) نمونه‌گیر سیل بسازد
یا ستاپ غیر۱۵د بگیرد، (۴) قاعدهٔ توقف یا سیم‌کشی گم شود.

    python3 -m hamid.test_tf_geo_arms
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import paper as P                         # noqa: E402
from hamid import tf_geo_arms as G                   # noqa: E402

ROOT = HERE.parents[2]
OK, FAIL = 0, []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


# ۱) جداسازی از آمار سیگنال — منبع واحد
check("هر دو برچسب در EXPERIMENT_STAGES هستند", {G.TF15_TAG, G.GEO_TAG} <= set(P.EXPERIMENT_STAGES))
check("و در _NOT_SIGNAL (وارد کارنامهٔ ارسالی نمی‌شوند)", {G.TF15_TAG, G.GEO_TAG} <= set(P._NOT_SIGNAL))
from hamid import work_report as WR                  # noqa: E402
check("گزارش کار آن‌ها را عملکرد نمی‌شمارد", {G.TF15_TAG, G.GEO_TAG} <= WR.NOT_PERFORMANCE)

# ۲) آینهٔ هندسه روی دفتر موقت
NOW = 1_789_600_000_000
with tempfile.TemporaryDirectory() as td:
    op = Path(td) / "open.jsonl"
    rows = [
        {"sym": "AUSDT", "dir": "LONG", "tf": "5m", "entry": 100.0, "sl": 99.0, "tp1": 102.0, "tp2": 104.0,
         "opened": NOW, "filled": None, "fee_r": 0.15, "why": {"stage": "sig-ibs"}},
        {"sym": "BUSDT", "dir": "SHORT", "tf": "5m", "entry": 50.0, "sl": 51.0, "tp1": 48.0, "tp2": None,
         "opened": NOW, "filled": NOW, "fee_r": 0.075, "why": {"stage": "sig-smc"}},
        {"sym": "CUSDT", "dir": "LONG", "tf": "15m", "entry": 10.0, "sl": 9.9, "tp1": 10.2,
         "opened": NOW, "filled": None, "why": {"stage": "sig-ibs"}},
        {"sym": "DUSDT", "dir": "LONG", "tf": "5m", "entry": 10.0, "sl": 9.9, "tp1": 10.2,
         "opened": NOW, "filled": None, "why": {"stage": "practice"}},
    ]
    op.write_text("".join(json.dumps(r) + "\n" for r in rows))
    old = P.OPEN
    P.OPEN = op
    try:
        n1 = P.mirror_geo_arm()
        n2 = P.mirror_geo_arm()
    finally:
        P.OPEN = old
    out = [json.loads(l) for l in op.read_text().splitlines() if l.strip()]
    mirrors = {r["sym"]: r for r in out if (r.get("why") or {}).get("stage") == G.GEO_TAG}
    check("فقط سیگنال‌های ارسالیِ ۵د آینه می‌شوند (نه ۱۵د، نه تمرین)", set(mirrors) == {"AUSDT", "BUSDT"}, str(set(mirrors)))
    check("آینه‌سازیِ دوباره چیزی اضافه نمی‌کند (idempotent)", n1 == 2 and n2 == 0, f"{n1}/{n2}")
    a, b = mirrors["AUSDT"], mirrors["BUSDT"]
    check("LONG: استاپ و تارگت ×۲ با همان ورود", a["entry"] == 100.0 and a["sl"] == 98.0 and a["tp1"] == 104.0 and a["tp2"] == 108.0,
          f"{a['sl']}/{a['tp1']}/{a['tp2']}")
    check("SHORT: قرینه", b["entry"] == 50.0 and b["sl"] == 52.0 and b["tp1"] == 46.0, f"{b['sl']}/{b['tp1']}")
    rr_base = (102.0 - 100.0) / (100.0 - 99.0)
    rr_arm = (a["tp1"] - a["entry"]) / (a["entry"] - a["sl"])
    check("RR ثابت می‌ماند", abs(rr_base - rr_arm) < 1e-9, f"{rr_base} vs {rr_arm}")
    check("کارمزد به R برای استاپِ گشادتر نصف می‌شود", abs(a["fee_r"] * 2 - P._fee_pct(a) / 1.0) < 1e-6 and a["fee_r"] < 0.15,
          str(a["fee_r"]))
    check("ردپای mirror_of و geo_mult روی آینه هست", a["why"]["mirror_of"] == "sig-ibs" and a["why"]["geo_mult"] == 2.0)
    check("لحظهٔ باز شدن و وضعیت فیل کپی می‌شود (جفتی)", b["opened"] == NOW and b["filled"] == NOW)

# ۳) نمونه‌گیر ۱۵د روی دفتر موقت
with tempfile.TemporaryDirectory() as td:
    op = Path(td) / "open.jsonl"
    op.write_text("")
    old = P.OPEN
    P.OPEN = op
    setups = ([{"sym": f"S{i}USDT", "dir": "LONG", "tf": "15m", "stage": "SIGNAL", "entry": 10.0, "sl": 9.8, "tp1": 10.4} for i in range(15)]
              + [{"sym": "X5USDT", "dir": "LONG", "tf": "5m", "stage": "SIGNAL", "entry": 10.0, "sl": 9.8, "tp1": 10.4},
                 {"sym": "ARMUSDT", "dir": "LONG", "tf": "15m", "stage": "ARMED", "entry": 10.0, "sl": 9.8, "tp1": 10.4}])
    try:
        r1 = G.sample_tf15(setups)
        r2 = G.sample_tf15(setups)
    finally:
        P.OPEN = old
    out = [json.loads(l) for l in op.read_text().splitlines() if l.strip()]
    tags = {(r.get("why") or {}).get("stage") for r in out}
    syms = {r["sym"] for r in out}
    check("فقط SIGNALِ ۱۵د نمونه می‌شود (نه ۵د، نه ARMED)", "X5USDT" not in syms and "ARMUSDT" not in syms and tags == {G.TF15_TAG}, str(tags))
    check(f"سقف {G.TF15_CAP} در هر اسکن رعایت می‌شود", r1["opened"] == G.TF15_CAP, str(r1))
    check("اسکن دوم فقط باقی‌مانده‌ها را باز می‌کند، نه تکراری‌ها",
          r2["opened"] == 3 and len(out) == 15 and len(syms) == 15, f"{r2} / {len(out)}")
    check("ردیف نمونه tf و برچسب دارد", all(r.get("tf") == "15m" for r in out))

# ۴) داور روی ردیف‌های ساختگی
def _row(stage, tf, R, fee, sym, opened, k=None):
    return {"sym": sym, "tf": tf, "entry": 1.0, "opened": opened, "R": R, "fee_r": fee,
            "outcome": "target" if R > 0 else "stop", "why": {"stage": stage}}

base = [_row("sig-ibs", "5m", (0.4 if i % 2 else -1.0), 0.15, f"P{i}", G.ARM_START_MS + i) for i in range(300)]
geo = [_row(G.GEO_TAG, "5m", (0.9 if i % 2 else -1.0), 0.075, f"P{i}", G.ARM_START_MS + i) for i in range(300)]
tf15 = [_row(G.TF15_TAG, "15m", (0.6 if i % 2 else -1.0), 0.05, f"T{i}", G.ARM_START_MS + i) for i in range(300)]
s = G.study(base + geo + tf15)
a1, a2 = s["arms"][G.TF15_TAG], s["arms"][G.GEO_TAG]
check("جفت‌ها بر نماد+ورود+لحظه ساخته می‌شوند", a2["n_pairs"] == 300, str(a2["n_pairs"]))
check("بازوی جفتیِ بهتر با n≥۲۰۰ → PROMOTE (فقط پیشنهاد)", a2["verdict"] == "PROMOTE" and "پیشنهاد" in a2["why"], a2["why"])
# فرد: (۰.۹−۰.۰۷۵)−(۰.۴−۰.۱۵)=۰.۵۷۵ · زوج: (−۱−۰.۰۷۵)−(−۱−۰.۱۵)=+۰.۰۷۵ → میانگین ۰.۳۲۵
check("اختلاف جفتی خالص از کارمزد است", abs(a2["mean_diff"] - 0.325) < 1e-6, str(a2["mean_diff"]))
check("بازوی ناجفت: n هر دو گروه گزارش می‌شود", a1["n_arm"] == 300 and a1["n_base"] == 300, f"{a1['n_arm']}/{a1['n_base']}")
check("بازوی ناجفتِ بهتر → PROMOTE", a1["verdict"] == "PROMOTE", a1["why"])
small = G.study(base[:30] + geo[:30] + tf15[:30])
check("نمونهٔ کم → UNDECIDED با برآورد نمونهٔ لازم", all(small["arms"][t]["verdict"] == "UNDECIDED" for t in small["arms"])
      and "نمونهٔ دیگر" in small["arms"][G.GEO_TAG]["why"], str({t: small["arms"][t]["why"] for t in small["arms"]}))
worse = [_row(G.GEO_TAG, "5m", (-0.2 if i % 2 else -1.0), 0.075, f"P{i}", G.ARM_START_MS + i) for i in range(450)]
base2 = [_row("sig-ibs", "5m", (0.4 if i % 2 else -1.0), 0.15, f"P{i}", G.ARM_START_MS + i) for i in range(450)]
check("بازوی جفتیِ بدتر با n≥۴۰۰ → REJECT", G.study(base2 + worse)["arms"][G.GEO_TAG]["verdict"] == "REJECT")
check("منقضی‌ها وارد سنجش نمی‌شوند",
      G.study([dict(base[0], outcome="expired", R=None), dict(geo[0], outcome="expired", R=None)])["arms"][G.GEO_TAG]["n_pairs"] == 0)
check("اثرانگشت ضریب هندسه و کارمزد را ثبت می‌کند", s["fingerprint"]["geo_mult"] == 2.0 and "fee_round_trip_pct" in s["fingerprint"])
check("قاعدهٔ توقف و مرز روی خروجی است", "PROMOTE" in s["stopping_rule"] and "پیپر" in s["boundary"])
check("Šidák برای دو بازو (z=۲.۲۴)", abs(G.Z - 2.2414) < 1e-6)

# ۵) سیم‌کشی
scan_src = (HERE.parent / "scan.py").read_text(encoding="utf-8")
cyc_src = (HERE / "cycle.py").read_text(encoding="utf-8")
check("اسکن بعد از دروازه‌ها نمونه‌گیر ۱۵د را صدا می‌زند",
      "from hamid import tf_geo_arms" in scan_src and ".sample_tf15(setups)" in scan_src)
check("چرخهٔ حمید آینهٔ هندسه را کنار آینهٔ تریل می‌زند", "paper.mirror_geo_arm()" in cyc_src)
wr = (ROOT / ".github" / "workflows" / "work-report.yml").read_text(encoding="utf-8")
check("گزارش کار داور را می‌دواند و می‌نویسد", "hamid.tf_geo_arms --write" in wr)
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("tf-geo-arms.json ردیف قرارداد دارد (قانون ۱۳)", "tf-geo-arms.json" in reg and reg["tf-geo-arms.json"].get("owner") == "E18")
check("دروازهٔ چرخه این محافظ را می‌زند",
      "hamid.test_tf_geo_arms" in (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8"))
from hamid import classify as C                      # noqa: E402
check("طبقه‌بند نام فارسی هر دو بازو را دارد", G.TF15_TAG in C.FA_STAGE and G.GEO_TAG in C.FA_STAGE)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}: {FAIL}")
    sys.exit(1)
print(f"پاسبان بازوهای ۱۵د/هندسه: هر {OK} بررسی سبز")
