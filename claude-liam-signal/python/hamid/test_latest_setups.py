"""پاسبان خوانندهٔ واحد ستاپ‌ها — روی نمونهٔ هم‌شکلِ فایلِ واقعی (۱ اکتبر)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import latest_setups as LS                           # noqa: E402

OK, BAD = [], []


def check(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  — {extra}" if extra and not cond else ""))


# شکلِ واقعی: symbols=int (شمار)، فهرست‌ها زیر signals/alarms/watch
doc = {"generated": 1, "symbols": 100, "series": 200,
       "signals": [{"sym": "AUSDT", "tf": "5m", "stage": "SIGNAL", "dir": "LONG", "strategy": "smc"}],
       "alarms": [{"sym": "BUSDT", "tf": "15m", "stage": "ARMED", "dir": "SHORT"},
                  {"sym": "AUSDT", "tf": "5m", "stage": "PULLBACK_1", "dir": "LONG"}],
       "watch": [{"sym": "CUSDT", "tf": "5m", "stage": "WATCH", "dir": "LONG"},
                 {"sym": "BUSDT", "tf": "15m", "stage": "ARMED", "dir": "SHORT"}]}
s = LS.setups(doc=doc)
check("symbols=int خوانده نمی‌شود (TypeError رانر ۱۰:۵۶)", all(isinstance(x, dict) for x in s))
check("ترتیب: SIGNAL → ARMED → WATCH (PULLBACKِ همان ستاپ تکراری است)", [x["sym"] for x in s] == ["AUSDT", "BUSDT", "CUSDT"], str([x["sym"] for x in s]))
check("یکتا بر (نماد، جهت، تایم)", sum(1 for x in s if x["sym"] == "BUSDT") == 1)
check("فیلتر مرحله", [x["sym"] for x in LS.setups(stages=("SIGNAL",), doc=doc)] == ["AUSDT"])
check("نمادهای یکتا با سقف", LS.symbols(limit=2, doc=doc) == ["AUSDT", "BUSDT"])
check("فایل خراب/ناموجود → فهرست خالی، نه خطا", LS.setups(path=Path("/nonexistent.json")) == [])
# فایلِ واقعیِ ریپو هم همین شکل را دارد (اگر هست)
real = LS.load()
if real:
    check("latest.json واقعی: symbols عدد است و فهرست‌ها زیر signals/alarms/watch",
          not isinstance(real.get("symbols"), list) and any(isinstance(real.get(k), list) for k in LS.LIST_KEYS))
    n_real = sum(len(real.get(k) or []) for k in LS.LIST_KEYS if isinstance(real.get(k), list))
    check("از فایل واقعی ستاپ خوانده می‌شود (ریشهٔ مسیر درست است)", len(LS.setups()) > 0 or n_real == 0, f"real rows={n_real}, read={len(LS.setups())}")
for mod in ("structure_room", "risk_desk", "scalp1m"):
    src = (HERE / f"{mod}.py").read_text(encoding="utf-8")
    check(f"{mod} از خوانندهٔ واحد می‌خواند، نه حدسِ کلید", "latest_setups" in src and 'd.get("symbols")' not in src)
print()
if BAD:
    print(f"✗ {len(BAD)} بررسی افتاد: {BAD}"); sys.exit(1)
print(f"پاسبان خوانندهٔ ستاپ‌ها: هر {len(OK)} بررسی سبز")
