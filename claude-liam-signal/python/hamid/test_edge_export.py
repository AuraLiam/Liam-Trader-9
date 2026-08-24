"""پاسبان انتقال مهارت — همراه اجباری edge_export و قفسهٔ لبهٔ داشبورد.

خطر این کانال دو چیز است: (۱) چیزی صادر شود که CI رد نکرده — یعنی حدس
با لباس مهارت وارد داشبورد شود؛ (۲) قفسهٔ کهنه اثر بگذارد — قانونی که
تِیپ دیگر پاداشش نمی‌دهد، هنوز امتیاز بدهد. هر دو این‌جا بسته می‌شوند.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PY))
from hamid import edge_export as EX                  # noqa: E402
import liam9_strategy as ST                          # noqa: E402
sys.path.insert(0, str(ROOT / "claude-liam-signal" / "python"))

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


NOW = int(time.time() * 1000)


def bt(rules, generated=None):
    return {"generated": generated if generated is not None else NOW,
            "reasons": rules}


print("— فقط CI-گذشته صادر می‌شود:")
r = EX.confirmed({"reasons": {"ibs": [
    {"condition": "الف", "delta": 0.2, "ci": [0.01, 0.4], "n": 100},
    {"condition": "ب", "delta": 0.9, "ci": [-0.1, 1.9], "n": 500},
    {"condition": "ج", "delta": -0.5, "ci": [-0.7, -0.3], "n": 200},
    {"condition": "بی‌شناسنامه", "delta": 0.5, "ci": [0.1, 0.9]},
    {"condition": "بی‌دلتا", "ci": [0.1, 0.9], "n": 50},
]}})
names = [x["condition"] for x in r.get("ibs", [])]
check("CI شاملِ صفر صادر نمی‌شود — حتی با دلتای بزرگ", "ب" not in names)
check("قانون منفی هم صادر می‌شود (فقط خبر خوش نه)", "ج" in names)
check("بدون n یا دلتا صادر نمی‌شود (شناسنامه اجباری)",
      "بی‌شناسنامه" not in names and "بی‌دلتا" not in names, str(names))
check("قانونِ سالم با شناسنامهٔ کامل می‌رود", "الف" in names)
check("همان فیلترِ scan.confirmed_rules است (دو تعریف واگرا نشود)",
      True)  # هم‌ارزی در بررسی بعدی با دادهٔ واقعی سنجیده می‌شود
sys.path.insert(0, str(PY))
import scan                                          # noqa: E402
real = json.loads((ROOT / "brain" / "backtests" / "latest.json")
                  .read_text(encoding="utf-8"))
mine = {k: [(r["condition"], r["delta"]) for r in v]
        for k, v in EX.confirmed(real).items()}
theirs = {k: [(r["condition"], r["delta"]) for r in v]
          for k, v in scan.confirmed_rules().items()}
check("روی بک‌تستِ واقعی، خروجی با scan.confirmed_rules مو‌به‌مو یکی است",
      mine == theirs, f"{mine} vs {theirs}")

print("\n— کهنگی:")
d = EX.build(bt({}, generated=NOW - 60 * 3_600_000), now_ms=NOW)
check("بک‌تستِ ۶۰ساعته stale علامت می‌خورد", d["stale"] is True)
d = EX.build(bt({}, generated=NOW - 3_600_000), now_ms=NOW)
check("بک‌تستِ ۱ساعته تازه است", d["stale"] is False and d["age_h"] == 1.0)
check("مهر زمان متنی «YYYY-MM-DD HH:MM UTC» خوانده می‌شود",
      EX._to_ms("2026-08-24 04:11 UTC") > 0)
check("مهرِ ناخوانا = صفر = stale (فرمت ناشناخته قانونِ کهنه را تازه جا نمی‌زند)",
      EX._to_ms("دیروز") == 0
      and EX.build(bt({}, generated="دیروز"), now_ms=NOW)["stale"])
check("نبودِ بک‌تست = قفسهٔ خالیِ stale، نه خطا",
      EX.build(bt={}, now_ms=NOW)["n_rules"] == 0)

print("\n— سمت داشبورد (liam9_strategy v2.8):")
_bak = dict(ST.EDGE)
try:
    ST.EDGE.clear()
    ST.EDGE.update({"stale": False, "rules": {"ibs": [
        {"condition": "لانگ همسو با بیت‌کوین", "delta": 0.2, "n": 231},
        {"condition": "بیت‌کوین نزولی", "delta": -0.33, "n": 354},
        {"condition": "شرط آزمون‌ناپذیر", "delta": 5.0, "n": 10}]}})
    pts, lines, rec = ST.edge_boost("ibs", {"dir": "LONG", "btc_up": True})
    check("قانون برقرار → امتیاز = دلتا × ۲۰", pts == 4, str(pts))
    check("و دلیلش با شناسنامه روی why می‌نشیند",
          lines and "n=231" in lines[0], str(lines))
    check("شرطِ آزمون‌ناپذیر بی‌صدا حذف نمی‌شود — شمرده می‌شود",
          rec["untested"] == 1, str(rec))
    pts, _, _ = ST.edge_boost("ibs", {"dir": "LONG", "btc_down": True})
    check("قانون منفی امتیاز کم می‌کند (بیت‌کوین نزولی)", pts == -7, str(pts))
    ST.EDGE["rules"]["ibs"][0]["delta"] = 9.0
    check("سقف ±۱۵ — لبه هرگز وتو یا تضمین نمی‌سازد",
          ST.edge_boost("ibs", {"dir": "LONG", "btc_up": True})[0] == ST.EDGE_CAP)
    ST.EDGE["stale"] = True
    check("قفسهٔ stale صفر اثر دارد",
          ST.edge_boost("ibs", {"dir": "LONG", "btc_up": True})[0] == 0)
    ST.EDGE.update({"stale": False, "rules": {}})
    check("قفسهٔ خالی صفر اثر دارد، نه خطا",
          ST.edge_boost("ibs", {"dir": "LONG", "btc_up": True})[0] == 0)
finally:
    ST.EDGE.clear()
    ST.EDGE.update(_bak)

src = (PY / "liam9_strategy.py").read_text(encoding="utf-8")
check("sync_all قفسهٔ لبه را هم می‌کشد", '"edge_rules": sync_edge()' in src)
check("ردپا روی خروجی ثبت می‌شود (edge_used) — انجین بی‌ردپا ناقص است",
      '"edge_used": bool(edge_pts)' in src)
check("نگاشتِ R→امتیاز صریح سند شده (انتخاب است نه اندازه‌گیری)",
      "یک انتخاب است نه اندازه‌گیری" in src)
check("و لبه فقط وزن است — روی هیچ دروازهٔ سختی ننشسته",
      "وتو نه" in src or "وتو نمی‌سازد" in src)

esrc = (PY / "hamid" / "edge_export.py").read_text(encoding="utf-8")
check("سند صادرکننده می‌گوید قفسهٔ خالی بهتر از آلوده است",
      "قفسهٔ آلوده بهتر است" in esrc)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان انتقال مهارت: هر {OK} بررسی سبز")
