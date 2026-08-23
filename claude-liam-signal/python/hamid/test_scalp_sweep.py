"""پاسبان جستجوی هندسهٔ اسکلپ — همراه اجباری scalp_sweep.py.

مهم‌ترین چیزی که قفل می‌شود: نقشه هرگز کندلی را که نتیجه‌اش را می‌سازد
نمی‌بیند، و «جستجو» از «تأیید» جدا می‌ماند. جستجوی پارامتری بدون این دو،
همان چیزی است که ۲۲ اوت +۰.۱۲۶R «کشف» کرد و خارج از نمونه کاملاً رد شد.
"""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import scalp_sweep as SW                    # noqa: E402

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


def walk(n=1200, seed=5, vol=0.0012):
    rnd = random.Random(seed)
    cd, px = [], 100.0
    for i in range(n):
        px *= (1 + rnd.gauss(0, vol))
        cd.append({"t": i * 60000, "o": px,
                   "h": px * (1 + abs(rnd.gauss(0, vol))),
                   "l": px * (1 - abs(rnd.gauss(0, vol))),
                   "c": px, "v": 1.0})
    return cd


P = {"rr": 2.5, "max_fee_r": 0.30, "ibs_max": 0.30, "hold": 45}

# ── شبکه ────────────────────────────────────────────────────────────────
g = SW.cells()
check("شبکه همهٔ ترکیب‌ها را می‌سازد", len(g) == 54, str(len(g)))
check("افق ۱۵ دقیقه‌ای (خواستهٔ صریح حمید) در شبکه هست",
      any(c["hold"] == 15 for c in g))
check("هیچ خانهٔ تکراری نیست",
      len({tuple(sorted(c.items())) for c in g}) == len(g))

# ── ضد نگاه به آینده ────────────────────────────────────────────────────
seen = {"max": 0, "ok": True}
_orig = SW.decide


def spy(win, p, now_ms=None):
    seen["max"] = max(seen["max"], len(win))
    seen["ok"] = seen["ok"] and win[-1]["t"] == max(k["t"] for k in win)
    return _orig(win, p, now_ms)


CD = walk()
SW.decide = spy
try:
    tr = SW.replay(CD, P)
finally:
    SW.decide = _orig
check("جستجو معاملهٔ واقعی می‌سازد", len(tr) >= 5, str(len(tr)))
check("تصمیم فقط با کندل‌های گذشته گرفته می‌شود", seen["ok"])
check("نقشه هرگز تا انتهای سری را نمی‌بیند (کندل‌های نتیجه بیرون می‌مانند)",
      seen["max"] <= len(CD) - P["hold"] - 2,
      f"{seen['max']} / {len(CD)}")

# ── بدترین‌حالت درون‌کندلی ──────────────────────────────────────────────
sig = {"dir": "LONG", "entry": 100.0, "sl": 99.0, "tp1": 102.5, "risk": 1.0}
both = [{"t": 0, "o": 100, "h": 100, "l": 100, "c": 100, "v": 1},
        {"t": 60000, "o": 100, "h": 103.0, "l": 98.0, "c": 100, "v": 1}]
check("کندلی که هم استاپ هم تارگت را لمس کند = استاپ (فرض خوش‌بینانه ممنوع)",
      SW.simulate(both, 0, sig, P)[0] == "stop")
only_tp = [both[0], {"t": 60000, "o": 100, "h": 103.0, "l": 99.9,
                     "c": 103, "v": 1}]
check("رسیدن به تارگت دقیقاً rr می‌دهد",
      SW.simulate(only_tp, 0, sig, P) == ("target", P["rr"]))

# ── کارمزد و هندسه ──────────────────────────────────────────────────────
tight = SW.decide(walk(400, seed=9, vol=0.0004), dict(P, max_fee_r=0.30))
loose = SW.decide(walk(400, seed=9, vol=0.0004), dict(P, max_fee_r=0.05))
check("سقف کارمزدِ سخت‌گیرتر، ستاپ‌های تنگ را رد می‌کند",
      not (loose and not tight), f"tight={bool(tight)} loose={bool(loose)}")
check("R خالص هرگز از R ناخالص بیشتر نیست",
      all(t["R_net"] <= t["R"] for t in tr))
check("سهم کارمزد از R با کارمزد٪÷استاپ٪ می‌خواند",
      all(abs(t["fee_r"] - 0.15 / t["stop_pct"]) < 1e-6 for t in tr))
check("محافظ لیکویید رعایت می‌شود (اهرم ≤ ۵۰÷استاپ٪)",
      all(t["lev"] <= 50.0 / t["stop_pct"] + 1e-9 for t in tr))

# ── حکم فقط از CI + آستانه ──────────────────────────────────────────────
sm = SW.score(tr[:5])
check("زیر کف نمونه هیچ CI گزارش نمی‌شود", sm["ci95"] is None)
# واریانس لازم است: سری کاملاً یکنواخت t صفر می‌دهد (تقسیم‌برصفرِ
# مهارشده) — همین آزمون اول با دادهٔ بی‌واریانسِ من قرمز شد.
_r = random.Random(3)
fake = [{"R": 1.0, "R_net": _r.gauss(0.9, 0.3), "fee_r": 0.1,
         "stop_pct": 1.0, "lev": 45, "outcome": "target"} for _ in range(200)]
sc = SW.score(fake)
check("لبهٔ پایدار CI بالای صفر می‌دهد", sc["ci95"][0] > 0, str(sc["ci95"]))
check("t هم گزارش می‌شود (CI تنها برای آستانهٔ چندآزمونی کافی نیست)",
      sc["t"] > 3, str(sc["t"]))
check("سری بی‌واریانس t صفر می‌دهد نه بی‌نهایت (تقسیم‌برصفر مهار شده)",
      SW.score([{"R": 1.0, "R_net": 0.9, "fee_r": 0.1, "stop_pct": 1.0,
                 "lev": 45, "outcome": "target"} for _ in range(50)])["t"] == 0)

# ── ترجمهٔ دلاری: تعداد پوزیشن امید ریاضی را عوض نمی‌کند ────────────────
cfg = [{"label": "۸×۱۰$", "n": 8, "margin": 10, "lev": 45},
       {"label": "۳×۳۰$", "n": 3, "margin": 30, "lev": 45},
       {"label": "۳×۳۰$ اهرم ۳۰", "n": 3, "margin": 30, "lev": 30}]
pf = {r["label"]: r for r in SW.portfolio(-0.19, 0.685, cfg)}
check("ضرر یک استاپ = مارجین × اهرم × استاپ٪",
      abs(pf["۸×۱۰$"]["loss_per_stop"] - 10 * 45 * 0.00685) < 0.01,
      str(pf["۸×۱۰$"]))
check("۳×۳۰$ بدترین‌حالتش از ۸×۱۰$ **بیشتر** است، نه کمتر",
      pf["۳×۳۰$"]["worst_case_all_stop"]
      > pf["۸×۱۰$"]["worst_case_all_stop"],
      f"{pf['۳×۳۰$']['worst_case_all_stop']} vs "
      f"{pf['۸×۱۰$']['worst_case_all_stop']}")
check("چیزی که واقعاً ریسک را کم می‌کند اهرم است، نه تعداد پوزیشن",
      pf["۳×۳۰$ اهرم ۳۰"]["worst_case_all_stop"]
      < pf["۸×۱۰$"]["worst_case_all_stop"])
check("با R منفی، هر چیدمانی انتظارِ منفی می‌دهد (بزرگ‌کردن نجات نمی‌دهد)",
      all(r["expected_per_round"] < 0 for r in SW.portfolio(-0.19, 0.685, cfg)))
check("با R مثبت علامت برمی‌گردد (فرمول جهت‌دار درست است)",
      all(r["expected_per_round"] > 0
          for r in SW.portfolio(+0.19, 0.685, cfg)))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان جستجوی هندسهٔ اسکلپ: هر {OK} بررسی سبز")
