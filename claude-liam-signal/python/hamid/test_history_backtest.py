"""پاسبان بک‌تست ۳ ساله — همراه اجباری history_backtest.py. آفلاین.

سه خطری که می‌بندد:
۱. **نگاه به آینده در بازسازی تایم بالا**: کندل ۱س/۴سِ ساخته‌شده از ۱۵د
   اگر با برچسب شروع سطل وارد پنجره شود، تا ۴۵د/۳:۴۵س دادهٔ آینده را به
   موتور می‌دهد و لبهٔ اندازه‌گیری‌شده دروغ می‌شود.
۲. **پنجرهٔ ناهمسنجه با زنده**: موتور زنده ۴۰۰ کندل تایم بالا می‌بیند؛
   اگر بک‌تست سه سال کامل بدهد، عدد قابل مقایسه با داشبورد نیست.
۳. **ادغام غلط تکه‌ها**: جمع معامله‌ها/قیف باید عین جمع اجزا باشد.
"""
import json
import struct
import sys
import tempfile
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import history_backtest as HB              # noqa: E402
from hamid.dash_backtest import _cut                  # noqa: E402

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


T0 = 1_700_000_000_000                                # ms، سرِ ساعت UTC


def mk15(n, t0=T0, dt=900_000, px=100.0):
    out = []
    for i in range(n):
        o = px + (i % 40) * 0.05
        out.append({"t": t0 + i * dt, "o": o, "h": o + 0.4, "l": o - 0.4,
                    "c": o + 0.1, "v": 10.0 + i % 7})
    return out


# ── ۱. بازسازی تایم بالا ─────────────────────────────────────────────
c15 = mk15(16)                                        # ۴ سطل کامل ۱س
h1 = HB.resample(c15, 60)
check("resample: 16×15د → 4×1س", len(h1) == 4, f"{len(h1)}")
check("resample: باز = بازِ اولین سازنده", h1[0]["o"] == c15[0]["o"])
check("resample: بسته = بستهٔ آخرین سازنده", h1[0]["c"] == c15[3]["c"])
check("resample: سقف = بیشینهٔ سازنده‌ها",
      h1[0]["h"] == max(k["h"] for k in c15[:4]))
check("resample: کف = کمینهٔ سازنده‌ها",
      h1[0]["l"] == min(k["l"] for k in c15[:4]))
check("resample: حجم = جمع سازنده‌ها",
      abs(h1[0]["v"] - sum(k["v"] for k in c15[:4])) < 1e-9)
check("resample: برچسب = بازشدنِ آخرین سازنده (نه شروع سطل)",
      h1[0]["t"] == c15[3]["t"], f"{h1[0]['t']} vs {c15[3]['t']}")

# خاصیت بی‌آیندگی: در هر لحظهٔ t_now، کندل واردشده به پنجره فقط از
# سازنده‌های t ≤ t_now ساخته شده باشد.
lookahead = False
for i, k in enumerate(c15):
    t_now = k["t"]
    w = h1[:_cut(h1, t_now)]
    for hc in w:
        parts = [x for x in c15 if x["t"] // 3_600_000 == hc["t"] // 3_600_000]
        if any(p["t"] > t_now for p in parts):
            lookahead = True
check("بی‌آیندگی: هیچ کندل ۱سِ داخل پنجره سازندهٔ آینده ندارد",
      not lookahead)
# سطل نیمه‌کاره (شکاف داده) هم آینده وارد نمی‌کند
c15_gap = mk15(6)                                     # سطل دوم فقط ۲ سازنده
h1_gap = HB.resample(c15_gap, 60)
check("resample با شکاف: برچسب سطل ناقص = آخرین سازندهٔ موجود",
      h1_gap[1]["t"] == c15_gap[5]["t"] and len(h1_gap) == 2)
T0_4H = (T0 // 14_400_000) * 14_400_000               # سرِ سطل ۴س
h4 = HB.resample(mk15(64, t0=T0_4H), 240)
check("resample: 64×15د همتراز → 4×4س", len(h4) == 4, f"{len(h4)}")
h4u = HB.resample(mk15(64), 240)                      # T0 وسط سطل ۴س است
check("resample: شروع ناهمتراز → سطل لبه‌ای اضافه (۵)", len(h4u) == 5,
      f"{len(h4u)}")

# ── ۲. پنجرهٔ لغزان و شبیه‌سازی معامله (موتور بدلی) ──────────────────
seen = {"future": False, "w15_max": 0, "whtf_max": 0, "calls": 0}
FIRE_AT = HB.WARMUP + 10


def stub_analyze(sym, w4, w1, ls, btc4h=None, btc1h=None):
    seen["calls"] += 1
    t_now = ls[-1]["t"]
    for series in (w4, w1, ls, btc4h or [], btc1h or []):
        if series and series[-1]["t"] > t_now:
            seen["future"] = True
    seen["w15_max"] = max(seen["w15_max"], len(ls))
    seen["whtf_max"] = max(seen["whtf_max"], len(w4), len(w1))
    if seen["calls"] == FIRE_AT - HB.WARMUP + 1:      # یک سیگنال کنترل‌شده
        e = ls[-1]["c"]
        return {"action": "LONG", "entry": e, "sl": e - 1.0, "tp1": e + 2.0,
                "quality": 70, "stop_pct": 1.0}
    return {"action": "NO_SIGNAL", "why": "بدلی — فقط آزمون"}


_real_ST = HB.ST
HB.ST = types.SimpleNamespace(analyze=stub_analyze)
n15 = HB.WARMUP + 4000
big15 = mk15(n15)
# قیمت را بعد از سیگنال به تارگت برسان
fire_i = FIRE_AT
for j in range(fire_i + 1, fire_i + 4):
    big15[j]["h"] = big15[fire_i]["c"] + 5.0
b1, b4 = HB.resample(big15, 60), HB.resample(big15, 240)
trades, reasons = HB.replay_windowed("XXXUSDT", big15, b1, b4,
                                     btc1h=b1, btc4h=b4)
HB.ST = _real_ST
check("پنجره: analyze هرگز کندلی جلوتر از t_now ندید", not seen["future"])
check("پنجره: سقف ۱۵د = W15", seen["w15_max"] <= HB.W15,
      f"{seen['w15_max']}")
check("پنجره: سقف تایم بالا = WHTF", seen["whtf_max"] <= HB.WHTF,
      f"{seen['whtf_max']}")
check("شبیه‌سازی: یک معاملهٔ تارگت ثبت شد",
      len(trades) == 1 and trades[0]["outcome"] == "target",
      json.dumps(trades[:1]))
if trades:
    t = trades[0]
    check("R ناخالص = فاصلهٔ تارگت/ریسک", abs(t["R"] - 2.0) < 1e-6)
    check("R خالص < R ناخالص (کارمزد کم شد)", t["R_net"] < t["R"])
    check("زمان بازشدن روی معامله هست", t["opened"] > T0)
check("قیف رد: علت بدلی شمرده شد",
      any("بدلی" in k for k in reasons) and sum(reasons.values()) > 100)

# ── ۳. تکه‌بندی و ادغام ──────────────────────────────────────────────
inv = {"klines": {
    "AAAUSDT_15m": {"status": "OK"}, "BBBUSDT_15m": {"status": "OK"},
    "CCCUSDT_15m": {"status": "UNKNOWN_FORMAT"},
    "DDDUSDT_1h": {"status": "OK"}, "BTCUSDT_15m": {"status": "OK"}}}
syms = HB.ok_symbols(inv)
check("ok_symbols: فقط ۱۵دِ سالم، مرتب",
      syms == ["AAAUSDT", "BBBUSDT", "BTCUSDT"], str(syms))
sh = [syms[k::3] for k in range(3)]
flat = sorted(s for part in sh for s in part)
check("تکه‌ها: بی‌هم‌پوشان و کامل", flat == syms)

check("_year: میلی‌ثانیه → سال درست", HB._year(T0) == 2023)

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    tr1 = [{"sym": "A", "dir": "LONG", "outcome": "target", "R": 2.0,
            "R_net": 1.9, "quality": 70, "stop_pct": 1.0, "bars": 5,
            "opened": T0}] * 20
    tr2 = [{"sym": "B", "dir": "SHORT", "outcome": "stop", "R": -1.0,
            "R_net": -1.1, "quality": 60, "stop_pct": 1.0, "bars": 3,
            "opened": T0 + 400 * 86_400_000}] * 15
    (td / "s0.json").write_text(json.dumps(
        {"shard": 0, "symbols": 2, "skipped": 1, "engine": "e",
         "trades": tr1, "rejections": {"الف": 5}}), encoding="utf-8")
    (td / "s1.json").write_text(json.dumps(
        {"shard": 1, "symbols": 3, "skipped": 0, "engine": "e",
         "trades": tr2, "rejections": {"الف": 2, "ب": 7}}), encoding="utf-8")
    (td / "noise.json").write_text("{}", encoding="utf-8")
    res = HB.merge(td, out=td / "merged.json")
    check("ادغام: جمع معامله‌ها درست", res["overall"]["n"] == 35)
    check("ادغام: جمع نماد/ردشده", res["symbols"] == 5 and res["skipped"] == 1)
    check("ادغام: قیف جمع شد", res["rejection_funnel"] == {"ب": 7, "الف": 7})
    check("ادغام: تفکیک جهت", res["per_direction"]["LONG"]["n"] == 20
          and res["per_direction"]["SHORT"]["n"] == 15)
    check("ادغام: تفکیک سال (۲۰۲۳/۲۰۲۴)",
          set(res["per_year"]) == {"2023", "2024"}
          and res["per_year"]["2024"]["n"] == 15, str(res.get("per_year")))
    check("ادغام: بازهٔ زمانی معامله‌ها",
          res["trade_span"] == ["2023-11-14", "2024-12-18"],
          str(res["trade_span"]))
    check("ادغام: n<30 → CI ندارد (بی‌ادعا)",
          res["per_direction"]["SHORT"].get("ci95") is None)
    check("ادغام: تفکیک درون/برون‌نمونه (IS≤2025 / OOS=2026)",
          res["is_2023_2025"]["n"] == 35 and res["oos_2026"]["n"] == 0)
    # تکه‌های ناهم‌پیکربندی ادغام نمی‌شوند — ادغامشان دروغ است
    (td / "s2.json").write_text(json.dumps(
        {"shard": 2, "symbols": 1, "skipped": 0, "engine": "e",
         "overrides": {"rr_target": 3.0}, "hold": 192,
         "trades": tr1[:5], "rejections": {}}), encoding="utf-8")
    mixed_refused = False
    try:
        HB.merge(td, out=td / "m2.json")
    except SystemExit:
        mixed_refused = True
    check("ادغام: پیکربندی قاطی → رد صریح", mixed_refused)

# ── ۴. دود: موتور واقعی روی دادهٔ کوتاه مصنوعی (فقط مسیر، نه لبه) ────
def mkbin(path, n, t0=T0):
    rows = b""
    for i in range(n):
        o = 100.0 + (i % 40) * 0.05
        rows += struct.pack("<6d", float(t0 + i * 900_000),
                            o, o + 0.4, o - 0.4, o + 0.1, 10.0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(rows)


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    src = td / "research"
    # ۲۶۰ کندل ۴س لازم است (۴۱۶۰×۱۵د) تا موتور واقعاً صدا زده شود
    mkbin(src / "klines" / "BTCUSDT_15m.bin", 4300)
    mkbin(src / "klines" / "AAAUSDT_15m.bin", 4300)
    mkbin(src / "klines" / "SHRTUSDT_15m.bin", 900)   # تایم بالا کوتاه → رد
    t0 = time.time()
    res = HB.run(src, shard=0, shards=1, out=td / "shard0.json", quiet=True)
    check("دود: موتور واقعی روی هر دو نماد بلند اجرا شد",
          res["symbols"] == 2 and "trades" in res,
          f"symbols={res['symbols']} skipped={res['skipped']}")
    check("دود: سری با تایم بالای کوتاه رد شد، بی‌صدا نه",
          res["skipped"] == 1 and "تایم بالا کوتاه" in res["drop_reasons"])
    check("دود: قیف ردِ موتور واقعی خالی نیست (NO_SIGNALها شمرده شدند)",
          sum(res["rejections"].values()) > 0, str(res["rejections"])[:120])
    check("دود: خروجی تکه روی دیسک", (td / "shard0.json").is_file())
    check("دود: سرعت قابل برنامه‌ریزی (<180ث)", time.time() - t0 < 180)
    # sweep هندسه: override اعمال و ثبت می‌شود، بعدش برمی‌گردد
    import liam9_strategy as ST
    rr0 = ST.PARAMS["rr_target"]
    res2 = HB.run(src, shard=0, shards=1, out=td / "shard0b.json",
                  overrides={"rr_target": 3.0}, hold=192, quiet=True)
    check("sweep: اثرانگشت پیکربندی روی خروجی تکه",
          res2["overrides"] == {"rr_target": 3.0} and res2["hold"] == 192)
    check("sweep: override واقعاً روی موتور نشست",
          ST.PARAMS["rr_target"] == 3.0)
    ST.PARAMS["rr_target"] = rr0
    bad_refused = False
    try:
        HB.run(src, shard=0, shards=1, out=td / "shard0c.json",
               overrides={"no_such_param": 1.0}, quiet=True)
    except SystemExit:
        bad_refused = True
    check("sweep: پارامتر ناشناخته رد می‌شود", bad_refused)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
