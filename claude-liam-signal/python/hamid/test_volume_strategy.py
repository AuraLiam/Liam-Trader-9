"""پاسبان مشترک اثر حجم + دو استراتژی — آفلاین.

خطرها: سنجهٔ حجمی که آینده ببیند، پیوت ۴سی که قبل از تأیید عمل کند،
محافظ لیکویید اهرم ۱۵ که رد نکند، و دام کارمزد که رد نشود.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import strategy_duo as SD                  # noqa: E402
from hamid import volume_impact as VI                 # noqa: E402

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


T0 = (1_700_000_000_000 // 14_400_000) * 14_400_000   # سرِ سطل ۴س


def mk15(n, t0=T0, base=100.0, drift=0.0, vol=10.0):
    out = []
    px = base
    for i in range(n):
        px += drift
        out.append({"t": t0 + i * 900_000, "o": px, "h": px + 0.4,
                    "l": px - 0.4, "c": px + 0.1, "v": vol})
    return out


# ── سنجه‌های حجم ─────────────────────────────────────────────────────
c = mk15(400)
c[200]["v"] = 100.0                                   # جهش
f = VI.features_at(c, 200)
check("rvol جهش را می‌بیند (۱۰×)", abs(f["rvol"] - 10.0) < 1e-6,
      str(f["rvol"]))
f_next = VI.features_at(c, 201)
check("rvol فقط از گذشته است (کندل بعدی جهش را در میانه ندارد ~۱×)",
      f_next["rvol"] is not None and f_next["rvol"] < 1.5)
check("features_at روی کندل زودتر از ۶۰ → None", VI.features_at(c, 30) is None)
k = dict(c[210])
k["c"] = k["h"]                                       # کلوز روی سقف
c[210] = k
check("clv کلوزِ سقف = +1", abs(VI.features_at(c, 210)["clv"] - 1.0) < 1e-9)
check("tod_rvol با ۲۰ روز داده معنادار یا None بی‌ادعا",
      f["tod_rvol"] is None or f["tod_rvol"] > 0)
check("سطل‌بندی: 10× → جهش ≥3×",
      VI._bin_name(10.0, VI.RVOL_BINS) == "جهش ≥3×")
check("سطل‌بندی: None → بی‌داده", VI._bin_name(None, VI.RVOL_BINS) == "بی‌داده")

# study: وصل معامله به سنجه و سطل «پول هم‌جهت»
c_up = mk15(400)
kk = dict(c_up[300])
kk["c"] = kk["h"]
c_up[300] = kk
tr = [{"sym": "AAA", "dir": "LONG", "outcome": "target", "R": 3.0,
       "R_net": 2.9, "quality": None, "stop_pct": 1.0, "bars": 4,
       "opened": c_up[300]["t"]}] * 40
res = VI.study({"AAA": tr, "GONE": tr[:3]},
               lambda s: c_up if s == "AAA" else None)
check("study: وصل‌شده/بی‌داده درست", res["matched"] == 40 and res["missed"] == 3)
check("study: کلوز سقف + لانگ = «پول هم‌جهت»",
      res["clv_dir"].get("پول هم‌جهت", {}).get("n") == 40,
      json.dumps({k: v.get("n") for k, v in res["clv_dir"].items()},
                 ensure_ascii=False))

# ── بستر روند و پیوت ۴س ──────────────────────────────────────────────
up15 = mk15(SD.WARMUP + 4200, drift=0.02)
u1, u4 = SD.resample(up15, 60), SD.resample(up15, 240)
check("روند صعودی یکنواخت → LONG", SD.trend_dir(u4[-400:], u1[-400:]) == "LONG")
dn15 = mk15(SD.WARMUP + 4200, drift=-0.02)
d1, d4 = SD.resample(dn15, 60), SD.resample(dn15, 240)
check("روند نزولی یکنواخت → SHORT",
      SD.trend_dir(d4[-400:], d1[-400:]) == "SHORT")

w4 = [{"t": i, "o": 10, "h": 10.5, "l": 9.5, "c": 10} for i in range(30)]
w4[10] = {"t": 10, "o": 10, "h": 20.0, "l": 9.5, "c": 10}   # سقف سوینگ
w4[20] = {"t": 20, "o": 10, "h": 10.5, "l": 5.0, "c": 10}   # کف سوینگ
hi, lo = SD.confirmed_swings(w4)
check("پیوت: سقف/کف سوینگ پیدا شد", hi == 20.0 and lo == 5.0)
w4_edge = w4[:12]                                     # سقف در ۲ کندل آخر
hi2, _ = SD.confirmed_swings(w4_edge)
check("پیوت لبهٔ پنجره (تأییدنشده) شمرده نمی‌شود — بی‌آینده", hi2 != 20.0)

# کراس شکست: فقط لحظهٔ عبور، نه ادامهٔ ردشده
ls = mk15(700, base=100.0)
ls[-2]["c"] = 19.9
ls[-1]["c"] = 20.5
sig = SD.sig_break4h("LONG", w4, ls, a15=0.4)
check("break4h: کراس سقف ۴س → سیگنال با استاپ زیر سطح",
      sig is not None and sig["sl"] < 20.0)
ls[-2]["c"] = 20.4                                    # از قبل بالای سطح
check("break4h: ادامهٔ ردشده (بی‌کراس) → هیچ",
      SD.sig_break4h("LONG", w4, ls, a15=0.4) is None)

# ── حلقهٔ ریپلی: محافظ‌ها ────────────────────────────────────────────
tr_b, rj_b = SD.replay("break4h", "XXX", up15, u1, u4)
guard_keys = [k for k in rj_b if "لیکویید" in k or "کارمزد" in k]
check("ریپلی break4h اجرا شد و قیف رد دارد", sum(rj_b.values()) > 100,
      str(list(rj_b)[:3]))
tr_o, rj_o = SD.replay("ob3", "XXX", up15, u1, u4)
check("ریپلی ob3 اجرا شد", sum(rj_o.values()) > 100)
for t in tr_b + tr_o:
    if t["stop_pct"] > SD.MAX_STOP_PCT + 1e-9:
        check("محافظ لیکویید اهرم ۱۵ روی همهٔ معامله‌ها", False,
              str(t))
        break
else:
    check(f"محافظ لیکویید اهرم ۱۵: هیچ استاپی >{SD.MAX_STOP_PCT:.2f}٪ نیست",
          True)
for t in tr_b + tr_o:
    fee_r = t["R"] - t["R_net"]
    if fee_r > SD.MAX_FEE_R + 1e-9:
        check("دام کارمزد: سهم کارمزد ≤0.3R روی همه", False, str(t))
        break
else:
    check("دام کارمزد: سهم کارمزد ≤0.3R روی همه", True)
check("ثابت‌ها: RR=3 و اهرم=۱۵ (دستور حمید)", SD.RR == 3.0 and SD.LEV == 15.0)

# خروجی تکه با اسکیمای ادغام history_backtest سازگار است
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    import struct
    def mkbin(path, n, drift):
        rows, px = b"", 100.0
        for i in range(n):
            px += drift
            rows += struct.pack("<6d", float(T0 + i * 900_000),
                                px, px + 0.4, px - 0.4, px + 0.1, 10.0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rows)
    src = td / "research"
    mkbin(src / "klines" / "AAAUSDT_15m.bin", 4300, 0.02)
    r = SD.run(src, "break4h", out=td / "s0.json", quiet=True)
    check("دود: run کامل با اثرانگشت استراتژی",
          r["overrides"]["strategy"] == "break4h" and r["symbols"] == 1)
    from hamid import history_backtest as HB
    m = HB.merge(td, out=td / "m.json")
    check("ادغام با ماشین موجود کار می‌کند",
          m["config"]["overrides"]["strategy"] == "break4h")

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
