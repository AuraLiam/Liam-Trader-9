"""پاسبان میز رو-به-جلوی متخصصین — دستور حمید، ۱۷ سپتامبر («انجامش بده»).

این میز قرار است به یک پرسش جواب بدهد: «هر متخصص چقدر روی خودش اثر مثبت
گذاشت؟» — و تنها چیزی که آن جواب را معتبر می‌کند این است که پارامترها
**تکان نخورند** و نمره فقط از کندلِ دیده‌نشده بیاید. پس این آزمون دقیقاً
همان دو خاصیت را می‌سنجد، نه شکلِ پیاده‌سازی را.

    python3 -m hamid.test_specialist_forward
"""
from __future__ import annotations

import json
import math
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]

from hamid import specialist_forward as F                # noqa: E402

OK, FAIL = 0, []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


def series(n=600, t0=1_700_000_000_000, seed=7):
    rnd = random.Random(seed)
    cd, px = [], 100.0
    for i in range(n):
        px *= 1 + 0.004 * math.sin(i / 9.0) + rnd.gauss(0, 0.0015)
        o, c = px * (1 + rnd.gauss(0, 0.0004)), px
        cd.append({"t": t0 + i * 900_000, "o": o, "c": c,
                   "h": max(o, c) * (1 + abs(rnd.gauss(0, 0.0018))),
                   "l": min(o, c) * (1 - abs(rnd.gauss(0, 0.0018))),
                   "v": 100 * (1 + abs(rnd.gauss(0, 0.4)))})
    return cd


CD = series()
FREEZE_AT = CD[300]["t"]                 # وسطِ تاریخ: نیمی قبل، نیمی بعد
LAB = {"generated": 1, "desks": {
    "gemini": {"fa": "جوزا", "strategy_fa": "دنباله‌روِ پیشرو",
               "params_used": {"ema": 34, "stretch_atr": 1.6, "stop_atr": 1.8, "rr": 1.8},
               "params_base": {"ema": 34, "stretch_atr": 1.6, "stop_atr": 1.3, "rr": 1.8},
               "improvement": {"adopted": True}},
    "cancer": {"fa": "سرطان", "strategy_fa": "شکارِ استاپ",
               "params_used": {"look": 20, "wick_mult": 1.4, "stop_atr": 1.2, "rr": 2.0},
               "params_base": {"look": 20, "wick_mult": 1.4, "stop_atr": 1.2, "rr": 2.0},
               "improvement": {"adopted": False}}}}

td = Path(tempfile.mkdtemp(prefix="spf-"))
F.FROZEN = td / "frozen.json"
F.FWD_LEDGER = td / "forward.jsonl"
F.OUT = td / "specialist-forward.json"

print("── میز رو-به-جلوی متخصصین ──")

# ── ۱) قفل ساخته می‌شود و **تکان نمی‌خورد** ──────────────────────────────
r1 = F.freeze(now_ms=FREEZE_AT, lab=LAB, log=lambda *a, **k: None)
check("قفل اول ساخته شد", r1["ok"] and len(r1["frozen"]) == 2, str(r1))
first = json.loads(F.FROZEN.read_text(encoding="utf-8"))["specs"]["gemini"]

# اجرای بعدیِ آزمایشگاه ایدهٔ دیگری می‌پسندد — قفل نباید عوض شود.
LAB2 = json.loads(json.dumps(LAB))
LAB2["desks"]["gemini"]["params_used"]["stop_atr"] = 2.7
r2 = F.freeze(now_ms=FREEZE_AT + 10_000_000, lab=LAB2, log=lambda *a, **k: None)
again = json.loads(F.FROZEN.read_text(encoding="utf-8"))["specs"]["gemini"]
check("قفلِ موجود با اجرای بعدیِ آزمایشگاه عوض نمی‌شود",
      again["frozen_at"] == first["frozen_at"] and again["fp"] == first["fp"],
      f"{first['fp']} → {again['fp']}")
check("و اعلام می‌کند که دست‌نخورده ماند", set(r2["kept"]) == {"gemini", "cancer"}, str(r2))

# فقط تصمیم صریح قفل را عوض می‌کند، و قفلِ قبلی در تاریخچه می‌ماند.
F.freeze(now_ms=FREEZE_AT + 20_000_000, lab=LAB2, refreeze=True, log=lambda *a, **k: None)
cur = json.loads(F.FROZEN.read_text(encoding="utf-8"))
check("refreeze اثرانگشت را عوض می‌کند", cur["specs"]["gemini"]["fp"] != first["fp"])
check("و قفلِ قبلی پاک نمی‌شود، بازنشسته می‌شود",
      any(h["fp"] == first["fp"] and h.get("retired_at") for h in cur["history"]),
      str(cur["history"])[:200])

# برای بقیهٔ آزمون، قفلِ اصلی را برمی‌گردانیم
F.FROZEN.write_text(json.dumps({"specs": {"gemini": first,
                                          "cancer": {**first, "id": "cancer",
                                                     "fa": "سرطان",
                                                     "params": LAB["desks"]["cancer"]["params_used"],
                                                     "base": LAB["desks"]["cancer"]["params_base"]}},
                                "history": []}, ensure_ascii=False), encoding="utf-8")

# ── ۲) نمره فقط از کندلِ بعد از قفل ─────────────────────────────────────
uni = ["AAAUSDT", "BBBUSDT"]
res = F.score(now_ms=CD[-1]["t"], n_symbols=2, per_symbol=5,
              klines=lambda s: CD, universe=uni, log=lambda *a, **k: None)
check("خروجی ساخته شد و ok است", res.get("ok") and res.get("desks"), str(res)[:200])

opened = []
for sym, cd in [(s, CD) for s in uni]:
    lo = F._first_index_after(cd, FREEZE_AT)
    opened.append(cd[lo]["t"])
check("برشِ هر ارز از اولین کندلِ بعد از قفل شروع می‌شود",
      all(t > FREEZE_AT for t in opened), str(opened))

g = res["desks"]["gemini"]
check("جوزا روی پنجرهٔ رو-به-جلو معامله ساخت (آزمون تهی نیست)",
      (g["arm"] or {}).get("n", 0) > 0, str(g["arm"]))

# اثباتِ سخت: هیچ معامله‌ای نباید قبل از قفل باز شده باشد
from hamid.specialist_lab import BY_ID, replay                 # noqa: E402
lo = max(F._first_index_after(CD, FREEZE_AT), F.WARMUP)
tr = replay("AAAUSDT", CD, BY_ID["gemini"], first["params"], lo=lo, cap=5)
check("هیچ معامله‌ای پیش از لحظهٔ قفل باز نشده",
      all(t["opened"] > FREEZE_AT for t in tr), str([t["opened"] for t in tr][:3]))
check("و نتیجهٔ هر معامله بعد از بازشدنش خوانده شده (بی‌نگاه به آینده)",
      all(t["closed"] >= t["opened"] for t in tr))

# ── ۳) بازمحاسبه، نه انباشت ──────────────────────────────────────────────
res2 = F.score(now_ms=CD[-1]["t"], n_symbols=2, per_symbol=5,
               klines=lambda s: CD, universe=uni, log=lambda *a, **k: None)
check("اجرای دوباره روی همان داده همان n را می‌دهد (ردیف انباشته نمی‌شود)",
      (res2["desks"]["gemini"]["arm"] or {}).get("n") ==
      (g["arm"] or {}).get("n"),
      f"{(g['arm'] or {}).get('n')} → {(res2['desks']['gemini']['arm'] or {}).get('n')}")

# ── ۴) پنجرهٔ بزرگ‌تر = نمونهٔ بیشتر، نه نمونهٔ جابه‌جا ───────────────────
early = json.loads(json.dumps(first)); early["frozen_at"] = CD[200]["t"]
F.FROZEN.write_text(json.dumps({"specs": {"gemini": early}, "history": []},
                               ensure_ascii=False), encoding="utf-8")
res3 = F.score(now_ms=CD[-1]["t"], n_symbols=2, per_symbol=5,
               klines=lambda s: CD, universe=uni, log=lambda *a, **k: None)
check("قفلِ قدیمی‌تر پنجرهٔ بزرگ‌تر و نمونهٔ ≥ می‌دهد",
      (res3["desks"]["gemini"]["arm"] or {}).get("n", 0) >=
      (g["arm"] or {}).get("n", 0))

# ── ۵) حکم فقط با قاعدهٔ از پیش ثبت‌شده ─────────────────────────────────
check("قاعدهٔ توقف روی خروجی نوشته می‌شود",
      res["stop_rule"]["z"] == F.Z_SIDAK and res["stop_rule"]["tests"] == 12)
check("حکمِ نمونهٔ کم، UNDECIDED است",
      g["verdict"] in ("UNDECIDED", "IMPROVED", "NOT_IMPROVED")
      and (g["verdict"] == "UNDECIDED" or (g["arm"] or {}).get("n", 0) >= F.N_PROMOTE),
      f"{g['verdict']} n={(g['arm'] or {}).get('n')}")
check("مرز صادقانه روی خروجی هست و مشاوره‌ای بودن را می‌گوید",
      "پیشنهاد" in res["boundary"] and "دروازه" in res["boundary"])

# ── ۶) بی‌قفل، عددی ساخته نمی‌شود (قانون ۱) ─────────────────────────────
F.FROZEN.write_text(json.dumps({"specs": {}}, ensure_ascii=False), encoding="utf-8")
res4 = F.score(now_ms=CD[-1]["t"], n_symbols=2, klines=lambda s: CD,
               universe=uni, log=lambda *a, **k: None)
check("بی‌قفل: ok=False با دلیل، نه عددِ ساختگی",
      res4.get("ok") is False and "قفل" in res4.get("why", ""), str(res4))
check("آزمایشگاهِ نخوانده هم قفل نمی‌سازد",
      F.freeze(lab={}, log=lambda *a, **k: None)["ok"] is False)

# ── ۷) سیم‌کشی: ردیف قرارداد و ورک‌فلو ──────────────────────────────────
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))
rows = reg if isinstance(reg, list) else (reg.get("files") or list(reg.values()))
blob = json.dumps(rows, ensure_ascii=False)
check("specialist-forward.json ردیف قرارداد دارد (قانون ۱۳)",
      "specialist-forward.json" in blob)
wf = (ROOT / ".github" / "workflows" / "specialist-lab.yml").read_text(encoding="utf-8")
check("ورک‌فلو قفل را می‌زند", "specialist_forward --freeze" in wf, wf[-400:])
check("و بعدش نمرهٔ رو-به-جلو را می‌گیرد", "--score" in wf)
check("و با ناشر یگانه منتشر می‌کند (قانون ۱۴)", "scripts/publish.sh" in wf)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}: {FAIL}")
    sys.exit(1)
print(f"پاسبان میز رو-به-جلو: هر {OK} بررسی سبز")
