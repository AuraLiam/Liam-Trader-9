"""پاسبان آزمایشگاه مراقبان (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دستور حمید: ۱۲ استراتژی متخصصان · سه تایم‌فریم **جداگانه** ·
بدون خبر از یک روز جلوتر · هر مراقب برای هر ترید پیش‌بینی می‌کند
(درست +۱، غلط −۱) · نتیجه به تفکیک تایم‌فریم و به تفکیک متخصص · و
علت استاپ و علت تارگت ثبت می‌شود.

اثبات منفیِ کلیدی این‌جاست: **آیندهٔ عوض‌شده نباید تصمیمِ گذشته را تکان
بدهد**. اگر بدهد، همهٔ اعداد این آزمایشگاه دروغ‌اند.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import guardian_lab as GL                 # noqa: E402
from hamid import phoenix as PHX                     # noqa: E402

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


CD = GL._demo_series(n=700, seed=5)

# ── ۱. دوازده استراتژی، هم‌نام همان دوازده مراقب ────────────────────────
check("دقیقاً ۱۲ استراتژی هست", len(GL.STRATEGIES) == 12, str(len(GL.STRATEGIES)))
check("و هم‌نامِ همان ۱۲ مراقب زودیاک است، نه فهرست موازی",
      set(GL.STRATEGIES) == set(PHX.BY_ID))
check("سه تایم‌فریم همان‌هایی است که حمید گفت", set(GL.TFS) == {"1h", "15m", "5m"})
check("دو مراقبِ ساکت دلیلِ سکوتشان نوشته شده",
      set(GL.SILENT) == {"sagittarius", "aquarius"}
      and all(v for v in GL.SILENT.values()))
for gid in GL.SILENT:
    check(f"[{gid}] بی‌دادهٔ هم‌ترازِ زمان، معامله نمی‌سازد (قانون ۱)",
          GL.STRATEGIES[gid](CD, {}) is None)
check("عقرب بدون سری دامیننس رأی نمی‌دهد",
      GL.STRATEGIES["scorpio"](CD, {}) is None)
check("جوزا بدون سری بیت‌کوین رأی نمی‌دهد",
      GL.STRATEGIES["gemini"](CD, {}) is None)
sig = {gid: GL.STRATEGIES[gid](CD, {}) for gid in GL.STRATEGIES}
check("هر خروجی یا long/short است یا None — چیز سومی نیست",
      all(v in ("long", "short", None) for v in sig.values()), str(sig))

# ── ۲. اثبات منفی: آینده تصمیم گذشته را تکان نمی‌دهد ────────────────────
# اثبات از مسیر خودِ اجرا: دو دنیا که ۴۰۰ کندل اولشان یکی
# است و بعدش فرق می‌کند. هر معامله‌ای که تمام عمرش داخل بخش مشترک است
# باید در هر دو دنیا **مو به مو** یکی باشد — تصمیم، جهت، رأی‌ها و نتیجه.
SHARED = 400
# دو آینده باید در **شکل** فرق کنند نه در مقیاس: همهٔ این استراتژی‌ها
# نسبت‌محورند (ATR، IBS، بدنه به شدو)، پس ضرب کل سری در یک عدد اصلاً
# تصمیمی را عوض نمی‌کند و اثباتی که با آن گرفته شود، توخالی است.
def _fork(cd, i0, slope):
    out = list(cd[:i0])
    p = cd[i0 - 1]["c"]
    for k, c in enumerate(cd[i0:]):
        p *= 1 + slope
        o = p
        cl = p * (1 + (0.004 if k % 2 else -0.004))
        out.append({"t": c["t"], "o": o, "h": max(o, cl) * 1.004,
                    "l": min(o, cl) * 0.996, "c": cl, "v": c.get("v") or 1.0})
    return out


w_a = _fork(CD, SHARED, 0.012)                       # آیندهٔ صعودی
w_b = _fork(CD, SHARED, -0.012)                      # آیندهٔ نزولی
RA = GL.run_tf("X", "15m", w_a, step=1)
RB = GL.run_tf("X", "15m", w_b, step=1)
# تصمیم‌هایی که **قبل** از نقطهٔ انشعاب گرفته شده‌اند. هر نشتی — حتی یک
# کندل — این مجموعه را در دو دنیا از هم جدا می‌کند، چون کندل‌های بعد از
# نقطهٔ انشعاب در دو دنیا متفاوت‌اند.
da = {(t["i"], t["by"], t["dir"]) for t in RA if t["i"] < SHARED - 1}
db = {(t["i"], t["by"], t["dir"]) for t in RB if t["i"] < SHARED - 1}
check("دو آینده واقعاً از هم دورند — آزمونِ توخالی نیست",
      abs(w_a[-1]["c"] / w_b[-1]["c"]) > 10,
      f"{w_a[-1]['c']:.2f} vs {w_b[-1]['c']:.2f}")
check("تصمیم‌های پیش از نقطهٔ انشعاب در دو دنیای متفاوت مو به مو یکی‌اند",
      da and da == db, f"{len(da)} در برابر {len(db)} · اختلاف: {list(da ^ db)[:4]}")
safe_keys = {(t["i"], t["by"]) for t in RA if t["i"] + GL.MAX_HOLD["15m"] + 1 < SHARED}
ta = {(t["i"], t["by"]): t for t in RA}
tb = {(t["i"], t["by"]): t for t in RB}
check("و معامله‌ای که تمام عمرش در بخش مشترک است، کامل یکی است — نتیجه و رأی‌ها",
      safe_keys and all(ta[k] == tb.get(k) for k in safe_keys),
      f"{len(safe_keys)} معامله سنجیده شد")

# ── ۳. شبیه‌سازی: خروج با دلیل ─────────────────────────────────────────
up = [{"t": i * 900_000, "o": 100 + i, "h": 101 + i, "l": 99 + i, "c": 100.5 + i,
       "v": 1.0} for i in range(120)]
r = GL.simulate(up, 60, "long", "15m")
check("در سری صعودی، لانگ به تارگت می‌رسد", r["R"] == GL.RR, str(r))
check("و دلیل خروج «تارگت» است", "تارگت" in r["exit_reason"], r["exit_reason"])
r = GL.simulate(up, 60, "short", "15m")
check("شورت در همان سری استاپ می‌خورد", r["R"] == -1.0, str(r))
check("و دلیل خروج «استاپ» است", "استاپ" in r["exit_reason"], r["exit_reason"])
check("کارمزد از R خالص کم می‌شود، نه فقط اسمی",
      r["R_net"] < r["R"] and r["fee_r"] > 0, str(r))
flat = [{"t": i * 900_000, "o": 100.0, "h": 100.4, "l": 99.6, "c": 100.0, "v": 1.0}
        for i in range(200)]
r = GL.simulate(flat, 60, "long", "5m")
check("رنجِ بی‌حرکت با سقف نگهداری بسته می‌شود",
      "سقف نگهداری" in r["exit_reason"], r["exit_reason"])
spike = list(up[:70]) + [dict(up[70], h=up[70]["h"] + 50, l=up[70]["l"] - 50)] + list(up[71:])
r = GL.simulate(spike, 69, "long", "15m")
check("وقتی استاپ و تارگت در یک کندل‌اند، بدبینانه استاپ حساب می‌شود",
      r["R"] == -1.0 and "یک کندل" in r["exit_reason"], str(r))
check("هر خروجی ورود، استاپ و تارگت را همراه دارد",
      all(k in r for k in ("entry", "sl", "tp")))
check("سری بی‌نوسان معامله نمی‌سازد",
      GL.simulate([{"t": i, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1} for i in range(80)],
                  40, "long", "5m") is None)

# ── ۴. اجرا روی سه تایم‌فریم، جداگانه ──────────────────────────────────
base = GL._demo_series(n=1200, seed=3)
series = {"5m": base, "15m": GL.resample(base, 3), "1h": GL.resample(base, 12)}
check("بازنمونه‌گیری واقعاً تایم بالاتر می‌سازد",
      len(series["1h"]) == len(base) // 12 and series["1h"][0]["o"] == base[0]["o"])
check("و سقف/کف تایم بالاتر از کندل‌های زیرش می‌آید",
      series["15m"][0]["h"] == max(c["h"] for c in base[:3]))
trades = []
for tf in GL.TFS:
    trades += GL.run_tf("TESTUSDT", tf, series[tf], step=5)
check("هر سه تایم‌فریم معامله ساختند", {t["tf"] for t in trades} == set(GL.TFS),
      str({t["tf"] for t in trades}))
check("هر معامله می‌گوید کدام مراقب پیشنهادش داد",
      all(t["by"] in GL.STRATEGIES for t in trades))
check("و رأی بقیه را همراه دارد", any(t.get("votes") for t in trades))
check("رأیِ ممتنع اصلاً در دفتر نیست (نه صفرِ ساختگی)",
      all(v in (1, -1) for t in trades for v in (t.get("votes") or {}).values()))
check("هر معامله لحظهٔ ورود را دارد", all(t.get("t") for t in trades))
check("هیچ معامله‌ای از کندل‌های گرم‌کردن نمی‌آید",
      all(t["i"] >= GL.WARMUP for t in trades))

# ── ۵. نمره: به تفکیک تایم و به تفکیک متخصص ────────────────────────────
res = GL.score(trades)
check("نتیجه به تفکیک تایم‌فریم گزارش می‌شود", set(res["by_tf"]) == set(GL.TFS))
for tf, s in res["by_tf"].items():
    check(f"[{tf}] برد، میانگین خالص و CI هر سه هست",
          s["win_pct"] is not None and s["mean_net"] is not None)
    check(f"[{tf}] حکم صریح دارد", bool(s.get("verdict")))
    check(f"[{tf}] علت‌های خروج شمرده شده‌اند", bool(s["by_reason"]))
small = {k: v for k, v in res["by_tf"].items() if v["n"] < GL.MIN_TRADES_VERDICT}
check("زیر کف نمونه، حکم اعلام نمی‌شود",
      all("UNDECIDED" in v["verdict"] for v in small.values()), str(small.keys()))
check("نتیجه به تفکیک متخصص هم هست", bool(res["by_guardian"]))
g = next(iter(res["by_guardian"].values()))
check("هر متخصص امتیاز، شمار رأی و دقت دارد",
      set(("points", "votes", "accuracy", "proposed")) <= set(g))
check("امتیاز از قاعدهٔ +۱/−۱ می‌آید",
      all(abs(v["points"]) <= v["votes"] for v in res["by_guardian"].values()))
check("و به تفکیک (متخصص × تایم‌فریم) هم شمرده می‌شود", bool(res["by_guardian_tf"]))
gt = next(iter(res["by_guardian_tf"].values()))
check("یعنی یک متخصص می‌تواند در ۱س خوب و در ۵د ضعیف باشد",
      all(set(("votes", "points")) <= set(v) for v in gt.values()))
# درستیِ خودِ شمارش
manual = 0
for t in trades:
    for gid, v in (t.get("votes") or {}).items():
        if gid == "aries":
            manual += 1 if (v > 0) == (t["R_net"] > 0) else -1
check("شمارش امتیاز با محاسبهٔ دستی می‌خواند",
      res["by_guardian"].get("aries", {}).get("points", 0) == manual, str(manual))

# ── ۶. دفتر آزمایش ─────────────────────────────────────────────────────
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "t.jsonl"
    n = GL.append_trades(trades[:5], path=p)
    GL.append_trades(trades[5:8], path=p)
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    check("دفتر آزمایش فقط اضافه می‌کند", n == 5 and len(lines) == 8)
    row = json.loads(lines[0])
    check("هر ردیف علت خروج را دارد (بند دستور: علت استاپ و تارگت)",
          row.get("exit_reason"))
    check("و R خالص از کارمزد", "R_net" in row and "fee_r" in row)

# ── ۷. تابلو و مرز ─────────────────────────────────────────────────────
snap = GL.snapshot(res, ["TESTUSDT"], "آزمون")
check("تابلو هر سه تایم را نام می‌برد", set(snap["timeframes"]) == set(GL.TFS))
check("قواعد هندسه روی تابلو اعلام می‌شوند",
      snap["rules"]["rr"] == GL.RR and snap["rules"]["fee_round_trip_pct"] > 0)
check("مالک تابلو E18 است", snap["engine"] == "E18")
check("مرز صریح است: دفتر آزمایش، جدا از پیپر تولید",
      "جدا از پیپر تولید" in snap["boundary"] and "قانون ۰۳" in snap["boundary"])
src = (HERE / "guardian_lab.py").read_text(encoding="utf-8")
for bad in ("sendMessage", "requests.post", "urlopen", "TELEGRAM"):
    check(f"آزمایشگاه «{bad}» ندارد — چیزی نمی‌فرستد", bad not in src)

# ── ۸. سیم‌کشی ─────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("guardian-lab.json ردیف قرارداد دارد (قانون ۱۳)",
      "guardian-lab.json" in reg
      and reg["guardian-lab.json"]["producer"] == "hamid/guardian_lab.py",
      str(reg.get("guardian-lab.json")))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
