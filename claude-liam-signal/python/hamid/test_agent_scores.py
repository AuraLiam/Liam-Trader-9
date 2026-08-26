"""پاسبان امتیاز و وزن اتاق‌های ایجنت (دستور حمید، ۲۷ اوت).

خطرهایی که این آزمون می‌بندد:
۱. وزنی که از نمونهٔ کوچک ساخته شود (ده معامله حق ندارد تصمیم را بچرخاند).
۲. وزنی که از صفر رد نکرده ولی مثل قانونِ اثبات‌شده اثر بگذارد
   (باند اکتشافی ±۰.۱۵ در برابر باند کامل ±۰.۴۰ — مرز قانون ۰۳).
۳. **وتو**: هیچ اتاقی نباید بتواند با وزن، سیگنال را ببندد یا باز کند.
۴. کهنگی: وزنِ آموخته از گذشته، تلهٔ شناخته‌شدهٔ ادبیات پیش‌بینی گروهی
   است (وزن دقیقاً وقتی سنگین می‌شود که عضو دارد افت می‌کند) — نیم‌عمر
   و بازگشتِ اتاقِ ساکت به خنثی باید کار کند.
۵. بستر: امتیاز باید به تفکیک ریزش/صعود USDT.D شمرده شود — همان مثال
   خود حمید («اتاقی که در ریزش دامیننس تتر شورت را تأیید کرده»).
۶. هر اتاق باید قانون امتیازِ نوشته‌شده داشته باشد.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import agent_scores as A                  # noqa: E402
import liam9_strategy as S                           # noqa: E402

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


NOW = 1_700_000_000_000.0
DAY = 86_400_000
TMP = Path(tempfile.mkdtemp(prefix="agentscore-"))

# سری دامیننس ساختگی: USDT.D در نیمهٔ اول ریزشی، در نیمهٔ دوم صعودی
pts = []
for i in range(240):                                  # ۲۴۰ نقطه، هر ۱ ساعت
    t = NOW - (240 - i) * 3_600_000
    u = 7.0 - i * 0.02 if i < 210 else 2.8 + (i - 210) * 0.02
    pts.append({"t": t, "u": round(u, 3), "b": 59.0})

check("هر اتاق قانون امتیاز نوشته‌شده دارد (خواستهٔ صریح حمید)",
      all(r.get("rule") and r.get("fields") and r.get("engine")
          for r in A.ROOMS.values()), str(list(A.ROOMS)))

# ── بستر از سری واقعی خوانده می‌شود، حدس زده نمی‌شود ────────────────────
t_down = NOW - 50 * 3_600_000
t_up = NOW - 10 * 3_600_000
check("ریزش USDT.D درست تشخیص داده می‌شود",
      A.context_at(t_down, pts) == "usdtd_down", A.context_at(t_down, pts))
check("صعود USDT.D درست تشخیص داده می‌شود",
      A.context_at(t_up, pts) == "usdtd_up", A.context_at(t_up, pts))
check("بیرون از پوشش سری → unknown (عدد ساختگی ساخته نمی‌شود)",
      A.context_at(NOW - 900 * 3_600_000, pts) == "unknown")
check("بدون سری → unknown", A.context_at(t_up, []) == "unknown")

# ── رأی‌ها ───────────────────────────────────────────────────────────────
v = A.votes_of({"ob_align": "with", "pattern_align": "against",
                "exp_used": True, "fib_ratio": 0.5})
check("رأی هم‌جهت/مخالف/بولی/فیبوناچی درست خوانده می‌شود",
      v == {"smc": 1, "candles": -1, "experience": 1, "fib": 1}, str(v))
check("میدان خالی = سکوت، نه رأی منفی", A.votes_of({"ob_align": None}) == {})
check("فیبوناچی بیرون ناحیهٔ طلایی سکوت است، نه رأی مخالف",
      A.votes_of({"fib_ratio": 0.9}) == {})


def ledger(rows):
    p = TMP / f"closed-{len(list(TMP.glob('*.jsonl')))}.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    return p


def trade(ts, R, **why):
    return {"sym": "XUSDT", "R": R, "opened": ts, "outcome": "x", "why": why}


# ── نمونهٔ کوچک وزن را تکان نمی‌دهد ─────────────────────────────────────
small = ledger([trade(NOW - 3600_000, 3.0, ob_align="with") for _ in range(8)])
d = A.build(now_ms=NOW, closed_path=small, dom_points=pts)
w_small = d["rooms"]["smc"]["by_context"]["all"]["weight"]
check("زیر آستانهٔ نمونه، وزن دقیقاً ۱.۰ می‌ماند", w_small == 1.0,
      str(d["rooms"]["smc"]["by_context"]["all"]))

# ── نمونهٔ بزرگ و پرنوسان: CI صفر را در بر می‌گیرد → باند اکتشافی ────────
noisy = ledger([trade(NOW - (i + 1) * 3600_000, 5.0 if i % 2 else -4.6,
                      ob_align="with") for i in range(80)])
dn = A.build(now_ms=NOW, closed_path=noisy, dom_points=pts)
rec_n = dn["rooms"]["smc"]["by_context"]["all"]
check("CI شاملِ صفر → باند اکتشافی، وزن داخل ±۰.۱۵",
      abs(rec_n["weight"] - 1.0) <= A.BAND_EXPLORATORY + 1e-9
      and "اکتشافی" in rec_n["why"], str(rec_n))

# ── نمونهٔ بزرگ و یکدست: CI بالای صفر → باند کامل ────────────────────────
solid = ledger([trade(NOW - (i + 1) * 3600_000, 2.0, ob_align="with")
                for i in range(80)])
ds = A.build(now_ms=NOW, closed_path=solid, dom_points=pts)
rec_s = ds["rooms"]["smc"]["by_context"]["all"]
check("CI بالای صفر → باند کامل باز می‌شود",
      rec_s["weight"] > 1.0 + A.BAND_EXPLORATORY
      and "CI از صفر رد کرده" in rec_s["why"], str(rec_s))
check("وزن هرگز از باند کامل رد نمی‌شود (سقف سخت)",
      rec_s["weight"] <= 1.0 + A.BAND_CONFIRMED + 1e-9, str(rec_s["weight"]))

# ── اتاقی که مرتب اشتباه کرده وزنش کم می‌شود — مثال خود حمید ────────────
bad = ledger([trade(NOW - (i + 1) * 3600_000, -2.0, ob_align="with")
              for i in range(80)])
db = A.build(now_ms=NOW, closed_path=bad, dom_points=pts)
rec_b = db["rooms"]["smc"]["by_context"]["all"]
check("اتاقی که تأییدهایش به ضرر ختم شده، وزنش زیر ۱ می‌رود",
      rec_b["weight"] < 1.0 - A.BAND_EXPLORATORY, str(rec_b))
check("رأی مخالفِ درست (معامله ضرر داد) اعتبار مثبت می‌گیرد",
      A.build(now_ms=NOW, dom_points=pts, closed_path=ledger(
          [trade(NOW - (i + 1) * 3600_000, -2.0, ob_align="against")
           for i in range(80)]))["rooms"]["smc"]["by_context"]["all"]["weight"] > 1.0)

# ── تفکیک بستر: همان اتاق در دو بستر دو وزن ─────────────────────────────
mixed = ledger(
    [trade(NOW - 50 * 3_600_000 + i * 60_000, 2.0, ob_align="with")
     for i in range(60)]
    + [trade(NOW - 10 * 3_600_000 + i * 60_000, -2.0, ob_align="with")
       for i in range(60)])
dm = A.build(now_ms=NOW, closed_path=mixed, dom_points=pts)
by = dm["rooms"]["smc"]["by_context"]
check("امتیاز به تفکیک بستر شمرده می‌شود (ریزش ≠ صعود دامیننس)",
      by["usdtd_down"]["weight"] > 1.0 > by["usdtd_up"]["weight"],
      str({k: v["weight"] for k, v in by.items()}))

# ── کهنگی: اتاقی که مدت‌هاست رأی نداده به خنثی برمی‌گردد ────────────────
oldl = ledger([trade(NOW - 30 * DAY - i * 3600_000, 2.0, ob_align="with")
               for i in range(80)])
do = A.build(now_ms=NOW, closed_path=oldl, dom_points=pts)
rec_o = do["rooms"]["smc"]["by_context"]["all"]
check("اتاقِ ساکتِ کهنه وزنش به خنثی برمی‌گردد (ضدِ تلهٔ کهنگی)",
      rec_o["weight"] == 1.0 and "کهنه" in rec_o["why"], str(rec_o))

# ── قفسهٔ کهنه در مصرف‌کننده هم بی‌اثر است ───────────────────────────────
fresh_data = A.build(now_ms=NOW, closed_path=solid, dom_points=pts)
w_now = A.weights_for("all", data=fresh_data, now_ms=NOW)
check("مصرف‌کننده وزن تازه را می‌گیرد", w_now["smc"] > 1.0, str(w_now))
w_old = A.weights_for("all", data=fresh_data, now_ms=NOW + 100 * 3_600_000)
check("قفسهٔ کهنه‌تر از ۴۸ ساعت بی‌اثر است (همهٔ وزن‌ها ۱.۰)",
      all(abs(x - 1.0) < 1e-9 for x in w_old.values()), str(w_old))
check("بستر بی‌نمونه به `all` برمی‌گردد، نه به صفر",
      A.weights_for("usdtd_up", data=fresh_data, now_ms=NOW)["smc"] > 1.0)

# ── هیچ وتویی: وزن فقط سهم امتیاز را می‌چرخاند، سقف‌خورده ───────────────
S.ROOM_W.clear()
S.ROOM_W.update({"weights": {"candles": 0.6, "experience": 0.6, "smc": 0.6},
                 "stale": False, "ctx": "usdtd_down"})
d_all_bad, _, _ = S.apply_room_weights([("candles", 10), ("experience", 20),
                                        ("smc", 15)])
check("بدترین حالتِ همهٔ وزن‌ها هم فقط سقفِ ±۱۰ امتیاز اثر دارد",
      abs(d_all_bad) <= S.ROOM_W_CAP + 1e-9, str(d_all_bad))
S.ROOM_W.update({"weights": {"candles": 99.0}, "stale": False})
check("وزن پرت هم از سقف رد نمی‌شود (وتو/انفجار ممنوع)",
      S.apply_room_weights([("candles", 10)])[0] == S.ROOM_W_CAP)
S.ROOM_W.clear()
S.ROOM_W.update({"weights": {}, "stale": True, "ctx": "unknown"})
check("قفسهٔ کهنه در داشبورد = بی‌اثرِ کامل",
      S.apply_room_weights([("candles", 10), ("smc", 15)])[0] == 0.0)

# ── ردپا برای سنجش شبانه ────────────────────────────────────────────────
src = (PY / "liam9_strategy.py").read_text(encoding="utf-8")
check("ردپای وزن روی خروجی سیگنال ثبت می‌شود (قانون انجینِ ردپادار)",
      '"room_weights": room_used' in src and '"room_delta": room_delta' in src)
check("وزن‌ها در sync_all کشیده می‌شوند",
      '"room_weights": sync_room_weights()' in src)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
