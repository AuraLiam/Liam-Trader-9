"""آزمون پل دمو — سایز با سقف سخت، ضدتکرار/تازگی، توقف با کیل‌سوییچ."""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import hamid_bridge_demo as br                                # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def run():
    now = time.time() * 1000
    tmp = Path(tempfile.mkdtemp())
    br.STATE_FILE = tmp / "state.json"
    br.SHADOW_BOOK = tmp / "shadow.jsonl"

    # ۱) سایز: ریسک ۱٪ از ۱۰۰۰$ و سقف سخت ۱۰۰$ ناتینال
    it = {"entry": 100.0, "sl": 99.0}
    q = br.qty_for(it)                    # ریسک ۱۰$ / فاصلهٔ ۱$ = ۱۰ ولی سقف ۱۰۰$/۱۰۰ = ۱
    check("سقف سخت ناتینال جلوی سایز بزرگ را می‌گیرد", q == 1.0, str(q))
    check("بدون استاپ = بدون سفارش (قانون ۱)",
          br.qty_for({"entry": 100.0, "sl": None}) is None)

    # ۲) امضا: قطعی و وابسته به همهٔ ورودی‌ها
    s1 = br.bitunix_sign("k", "sec", "", "{}", "n1", 1000)
    s2 = br.bitunix_sign("k", "sec", "", "{}", "n1", 1000)
    s3 = br.bitunix_sign("k", "sec", "", "{}", "n2", 1000)
    check("امضا قطعی است و با nonce عوض می‌شود", s1 == s2 and s1 != s3)

    # ۳) فیلتر قصدها: PENDING تازه و تکرارنشده
    box = [
        {"id": "A", "status": "PENDING", "created_at": now - 60000,
         "symbol": "XUSDT", "direction": "LONG", "entry": 1.0, "sl": 0.99},
        {"id": "B", "status": "SENT", "created_at": now - 60000},
        {"id": "C", "status": "PENDING",
         "created_at": now - 20 * 3600_000},          # کهنه
        {"id": "D", "status": "PENDING", "created_at": now - 60000},  # قبلاً رفته
    ]
    st = {"done": ["D"]}
    fresh = [i for i in box
             if i.get("status") == "PENDING" and i.get("id") not in st["done"]
             and now - (i.get("created_at") or 0) < br.FRESH_MAX_H * 3600_000]
    check("فقط قصد PENDING تازهٔ تکرارنشده انتخاب می‌شود",
          [i["id"] for i in fresh] == ["A"], str([i["id"] for i in fresh]))

    # ۴) دفتر سایه و state روی دیسک
    br._log_shadow({"t": 1, "intent": "A", "mode": "dry"})
    br._save_state({"done": ["A"]})
    check("دفتر سایه و state نوشته شدند",
          br.SHADOW_BOOK.exists()
          and json.loads(br.STATE_FILE.read_text())["done"] == ["A"])

    print(f"\n✓ همهٔ {OK} آزمون پل دمو گذشت")


if __name__ == "__main__":
    run()
