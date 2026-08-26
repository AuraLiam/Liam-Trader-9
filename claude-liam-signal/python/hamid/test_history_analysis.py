"""پاسبان تحلیل دفتر ۳ ساله — همراه اجباری history_analysis.py. آفلاین.

خطرهایی که می‌بندد: سطل‌بندی غلط (معاملهٔ گم/دوباره)، ادعای CI روی نمونهٔ
کوچک، و دفتر فشرده‌ای که با ورودی یکی نیست.
"""
import gzip
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import history_analysis as HA              # noqa: E402

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


T23 = 1_700_000_000_000                               # نوامبر ۲۰۲۳


def mktr(sym, d, out, r, rn, q, sp, opened):
    return {"sym": sym, "dir": d, "outcome": out, "R": r, "R_net": rn,
            "quality": q, "stop_pct": sp, "bars": 5, "opened": opened}


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    tr_a = [mktr("AAAUSDT", "LONG", "target", 2.0, 1.9, 75, 0.8, T23)] * 60
    tr_b = [mktr("BBBUSDT", "SHORT", "stop", -1.0, -1.1, 55, 2.5,
                 T23 + 400 * 86_400_000)] * 40
    (td / "s0.json").write_text(json.dumps(
        {"shard": 0, "trades": tr_a}), encoding="utf-8")
    (td / "s1.json").write_text(json.dumps(
        {"shard": 1, "trades": tr_b}), encoding="utf-8")
    (td / "junk.json").write_text("[]", encoding="utf-8")
    uni = td / "universe.json"
    uni.write_text(json.dumps({"symbols": [
        {"symbol": "AAAUSDT", "rank": 5},
        {"symbol": "BBBUSDT", "rank": 200}]}), encoding="utf-8")
    res = HA.run(td, out_analysis=td / "a.json", out_trades=td / "t.json.gz",
                 universe_path=uni)

    o = res["overall"]
    check("جمع معامله‌ها", o["n"] == 100)
    check("ناخالص و خالص هر دو با CI",
          o["ci95_gross"] is not None and o["ci95_net"] is not None)
    check("میانگین کارمزد = ناخالص − خالص",
          abs(o["mean_fee_r"] - 0.1) < 1e-9, str(o["mean_fee_r"]))
    check("سطل کیفیت: 70-79 فقط لانگ‌ها",
          res["per_quality"]["70-79"]["n"] == 60)
    check("سطل کیفیت: 0-59 فقط شورت‌ها",
          res["per_quality"]["0-59"]["n"] == 40)
    check("جمع سطل‌های کیفیت = کل (نه گم نه دوباره)",
          sum(v.get("n", 0) for v in res["per_quality"].values()) == 100)
    check("سطل استاپ: 0.5-1.0٪ شصت‌تا",
          res["per_stop_pct"]["0.5-1.0%"]["n"] == 60)
    check("جمع سطل‌های استاپ = کل",
          sum(v.get("n", 0) for v in res["per_stop_pct"].values()) == 100)
    check("سال×جهت", res["per_year_direction"]["2023_LONG"]["n"] == 60
          and res["per_year_direction"]["2024_SHORT"]["n"] == 40)
    check("ماهانه: دو ماه", len(res["monthly"]) == 2)
    check("ردهٔ نقدشوندگی از universe",
          res["per_liquidity"]["rank1_60"]["n"] == 60
          and res["per_liquidity"]["rank61plus"]["n"] == 40)
    check("پراکندگی نماد: n>=100 لازم است (هیچ‌کدام نرسید)",
          res["symbols_best"] == [], str(res["symbols_best"])[:80])
    back = json.loads(gzip.decompress((td / "t.json.gz").read_bytes()))
    check("دفتر فشرده عین ورودی", len(back) == 100
          and back[0] == tr_a[0] and back[-1] == tr_b[0])

    # سطل کوچک CI ادعا نمی‌کند
    small = HA.agg2([mktr("C", "LONG", "target", 1.0, 0.9, 70, 1.0, T23)] * 10)
    check("n<30 → CI ندارد", small["ci95_net"] is None)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
