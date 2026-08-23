"""پاسبان کارنامهٔ اسکلپ — همراه اجباری scalp_report.py.

گزارشی که عدد را اشتباه جمع بزند بدتر از نبودنش است، چون تصمیم روی
همان عدد گرفته می‌شود. آنچه این‌جا قفل می‌شود: تفکیک دفترها، اینکه
حکم فقط از CI بیاید، اینکه trail با target قاطی نشود، و اینکه زیر کف
نمونه هیچ CIای گزارش نشود.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import scalp_report as SR                   # noqa: E402

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


def trade(stage="scalp", tf="1m", r=0.5, fee=0.2, outcome="target",
          sym="AAAUSDT", d="LONG", t=1_700_000_000_000):
    return {"sym": sym, "dir": d, "tf": tf, "opened": t, "filled": t,
            "closed": t + 60000, "outcome": outcome, "R": r, "fee_r": fee,
            "R_net": round(r - fee, 6), "why": {"stage": stage, "replay": 1,
                                                "tf": tf}}


def write(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                    encoding="utf-8")
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    f.close()
    return f.name


# ── تفکیک دفترها (قانون ۹: هر میز آمار جدا) ────────────────────────────
mixed = ([trade(stage="scalp") for _ in range(40)]
         + [trade(stage="shock", r=9.0) for _ in range(40)]
         + [trade(stage="scalp", tf="5m", r=9.0) for _ in range(40)])
p = write(mixed)
rows = SR.load(tf="1m", stage="scalp", ledger=p)
check("فقط میز خواسته‌شده برداشته می‌شود", len(rows) == 40, str(len(rows)))
check("میز دیگر با همان تایم‌فریم وارد نمی‌شود (قانون ۹)",
      all(r["why"]["stage"] == "scalp" for r in rows))
check("تایم‌فریم دیگرِ همان میز وارد نمی‌شود",
      all(r["tf"] == "1m" for r in rows))
check("میز shock جدا قابل خواندن است",
      len(SR.load(tf="1m", stage="shock", ledger=p)) == 40)
check("معامله‌ها بر زمان مرتب برمی‌گردند",
      [r["opened"] for r in rows] == sorted(r["opened"] for r in rows))

# ── حکم فقط از CI ───────────────────────────────────────────────────────
pos = [trade(r=1.0, fee=0.1) for _ in range(200)]        # خالص +0.9 پایدار
s = SR.summarize(pos)
check("لبهٔ مثبتِ پایدار: CI بالای صفر و حکم مثبت",
      s["ci95"][0] > 0 and "لبهٔ مثبت" in s["verdict"], s["verdict"])
neg = [trade(r=0.0, fee=0.2) for _ in range(200)]
s2 = SR.summarize(neg)
check("لبهٔ منفیِ پایدار: CI زیر صفر و حکم «ضرر می‌دهد»",
      s2["ci95"][1] < 0 and "ضرر می‌دهد" in s2["verdict"], s2["verdict"])
# نوسان زیاد حول صفر → باید «بی‌نتیجه» بدهد، نه حکم
noisy = [trade(r=(3.0 if i % 2 else -2.9), fee=0.05) for i in range(200)]
s3 = SR.summarize(noisy)
check("وقتی CI صفر را در بر می‌گیرد، حکم «بی‌نتیجه» است نه مثبت/منفی",
      "بی‌نتیجه" in s3["verdict"] and s3["ci95"][0] < 0 < s3["ci95"][1],
      s3["verdict"])

# ── کف نمونه ────────────────────────────────────────────────────────────
small = SR.summarize([trade(r=5.0, fee=0.0) for _ in range(10)])
check("زیر کف نمونه هیچ CI گزارش نمی‌شود",
      small["ci95"] is None and "نمونه کم" in small["verdict"],
      small["verdict"])
check("حتی با سود عظیم، کف نمونه دور زده نمی‌شود",
      SR.summarize([trade(r=99.0, fee=0.0) for _ in range(29)])["ci95"] is None)

# ── کارمزد ──────────────────────────────────────────────────────────────
s4 = SR.summarize([trade(r=1.0, fee=0.3) for _ in range(50)])
check("R ناخالص و خالص جدا گزارش می‌شوند",
      s4["R_gross_mean"] == 1.0 and abs(s4["R_net_mean"] - 0.7) < 1e-6)
check("سهم کارمزد از R صریح گزارش می‌شود", s4["fee_R_mean"] == 0.3)
check("R خالص هرگز بیشتر از ناخالص نیست",
      s4["R_net_mean"] <= s4["R_gross_mean"])

# ── trail برد نیست ──────────────────────────────────────────────────────
mix = ([trade(outcome="target", r=1.5, fee=0.2) for _ in range(20)]
       + [trade(outcome="trail", r=0.2, fee=0.2) for _ in range(30)]
       + [trade(outcome="stop", r=-1.0, fee=0.2) for _ in range(50)])
s5 = SR.summarize(mix)
check("نرخ تارگت و تریل جدا شمرده می‌شوند (تریل برد نیست)",
      s5["target_rate"] == 20.0 and s5["trail_rate"] == 30.0, str(s5))
check("«برد خالص» یعنی R خالص مثبت، نه صرفاً غیراستاپ",
      s5["win_rate_net"] == 20.0, str(s5["win_rate_net"]))
check("تریلِ سربه‌سرِ بعد از کارمزد برد حساب نمی‌شود",
      SR.summarize([trade(outcome="trail", r=0.2, fee=0.2)
                    for _ in range(40)])["win_rate_net"] == 0.0)

# ── تفکیک ───────────────────────────────────────────────────────────────
per = ([trade(sym="AAAUSDT", r=1.0, fee=0.1) for _ in range(40)]
       + [trade(sym="BBBUSDT", r=0.0, fee=0.1) for _ in range(40)]
       + [trade(sym="CCCUSDT", r=1.0, fee=0.1) for _ in range(5)])
top, total = SR.by_key(per, lambda r: r["sym"])
check("تفکیک نماد فقط دسته‌های به‌اندازه را می‌آورد",
      [t["key"] for t in top] == ["AAAUSDT", "BBBUSDT"], str(top))
check("دستهٔ کم‌نمونه حذف می‌شود ولی در شمارش کل می‌ماند", total == 3)
check("تفکیک بر بازدهی مرتب است",
      top[0]["R_net_mean"] >= top[-1]["R_net_mean"])

# ── پنجرهٔ اخیر ─────────────────────────────────────────────────────────
DAY = 86400000
old = [trade(t=1_700_000_000_000, r=5.0, fee=0.0) for _ in range(40)]
new = [trade(t=1_700_000_000_000 + 10 * DAY, r=0.0, fee=0.5) for _ in range(40)]
p2 = write(old + new)
allr = SR.run(ledger=p2, quiet=True)
recent = SR.run(ledger=p2, quiet=True, recent_days=2)
check("پنجرهٔ اخیر فقط معامله‌های تازه را می‌گیرد",
      recent["n"] == 40 and allr["n"] == 80, f"{recent['n']} / {allr['n']}")
check("پنجرهٔ اخیر می‌تواند حکم متفاوتی از کل بدهد (رژیم عوض می‌شود)",
      recent["R_net_mean"] < allr["R_net_mean"],
      f"{recent['R_net_mean']} vs {allr['R_net_mean']}")

# ── دفتر خالی ───────────────────────────────────────────────────────────
empty = SR.run(ledger=write([]), quiet=True)
check("دفتر خالی عدد جعلی نمی‌سازد",
      empty["n"] == 0 and empty.get("ci95") is None
      and "هیچ معامله" in empty["verdict"])

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان کارنامهٔ اسکلپ: هر {OK} بررسی سبز")
