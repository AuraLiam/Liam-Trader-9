"""پاسبان انتشار لایهٔ نقدشوندگی — همراه اجباری publish_top_liquidity.py.

دو چیز باید همیشه درست باشد: (۱) وقتی sources.top_symbols هست از همان
مسیر استفاده شود، (۲) وقتی نیست (مثل رانر ۲۰ اوت که با AttributeError
مرد) مسیر جایگزین hamid.trainer.top_symbols بی‌صدا کار را ادامه بدهد —
همان کلاس عیبی که dash_backtest از قبل با تست جدا بسته است.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import sources                                      # noqa: E402
from hamid import trainer                            # noqa: E402
from hamid import publish_top_liquidity as PUB        # noqa: E402

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


old_top = getattr(sources, "top_symbols", None)
old_trainer_top = trainer.top_symbols
tmp = Path(PUB.OUT.parent) / "top-liquidity-test.json"

sources.top_symbols = lambda n: [f"SYM{i}USDT" for i in range(n)]
try:
    d = PUB.run(quiet=True, out=tmp)
    check("مسیر اصلی sources.top_symbols: n و symbols برابرند",
          d["n"] == 60 and len(d["symbols"]) == 60, str(d["n"]))
    check("خروجی برند و بنیانِ یافته دارد",
          d.get("panel") == "لیام تریدر ۹" and "CI" in d.get("source_finding", ""))
    check("فایل روی دیسک JSON معتبر است",
          json.loads(tmp.read_text())["symbols"][0] == "SYM0USDT")
finally:
    if old_top is not None:
        sources.top_symbols = old_top
    else:
        del sources.top_symbols

# مسیر جایگزین: sources.top_symbols نیست (کلاس عیب ۲۰ اوت)
had_attr = hasattr(sources, "top_symbols")
if had_attr:
    del sources.top_symbols
trainer.top_symbols = lambda n: [f"ALT{i}USDT" for i in range(n)]
try:
    d2 = PUB.run(quiet=True, out=tmp)
    check("بدون sources.top_symbols هم از مسیر جایگزین (trainer) رد می‌شود",
          not hasattr(sources, "top_symbols") and d2["symbols"][0] == "ALT0USDT",
          str(d2.get("symbols", [])[:2]))
finally:
    trainer.top_symbols = old_trainer_top
    if old_top is not None:
        sources.top_symbols = old_top
    tmp.unlink(missing_ok=True)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان انتشار لایهٔ نقدشوندگی: هر {OK} بررسی سبز")
