"""پاسبانِ کاوش اسناد — همراه اجباری docs_probe.py. کاملاً آفلاین.

نکتهٔ اصلیِ این پاسبان: شکستِ شبکه نباید به «موفقیتِ خاموش» ترجمه شود.
سند نیامده باید UNREACHABLE بماند و صفحهٔ توخالی باید THIN بخورد — چون
خطر واقعیِ این ماژول این است که یک پوستهٔ جاوااسکریپتیِ ۴۰۰ کاراکتری را
«دریافت شد» بشماریم و بعد ادعا کنیم سند راستی‌آزمایی شده است.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import docs_probe as DP                      # noqa: E402

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


check("هر شش سند حمید ثبت شده", len(DP.DOCS) == 6)
check("هر سند انجین، موضوع و پرسش دارد",
      all(d.get("engine") and d.get("topic") and d.get("question")
          for d in DP.DOCS))
check("شناسه‌ها یکتاست", len({d["id"] for d in DP.DOCS}) == 6)
check("سند لیکوییدیشن پرسشِ درست را می‌پرسد (سمت پوزیشن یا سفارش)",
      any("side" in d["question"] or "سمت" in d["question"]
          for d in DP.DOCS if d["id"] == "bybit-ws-liquidation"))

html_doc = """<html><head><style>.x{color:red}</style>
<script>var a=1;</script></head><body>
<p>The confirm field is true when the candle is closed.</p>
<li>interval: 1,3,5,15 minutes</li>
<h2>Order&nbsp;book</h2></body></html>"""
txt = DP.to_text(html_doc)
check("اسکریپت و استایل از متن حذف می‌شوند",
      "var a=1" not in txt and "color:red" not in txt, txt[:120])
check("موجودیت HTML باز می‌شود (nbsp → فاصله)", "Order book" in txt, txt)
check("متن واقعی می‌ماند", "confirm field is true" in txt, txt[:200])

ex = DP.excerpts(txt, ["confirm", "interval", "غایب"])
check("کلیدواژهٔ موجود، تکهٔ شاهد می‌گیرد",
      "confirm" in ex and "confirm" in ex["confirm"][0])
check("کلیدواژهٔ غایب اصلاً کلید نمی‌سازد (نه تکهٔ خالی)", "غایب" not in ex)

_pad = "متن پرکننده برای عبور از آستانهٔ نازکی. " * 60
big = "<html><body><p>" + _pad + " barstate.isconfirmed تعریف </p></body></html>"

with tempfile.TemporaryDirectory() as td:
    _out, _fetch = DP.OUT, DP.fetch
    DP.OUT = Path(td) / "docs.json"
    try:
        DP.fetch = lambda u, timeout=25: (None, 403, "HTTPError 403")
        r_block = DP.probe(quiet=True)
        DP.fetch = lambda u, timeout=25: ("<html><body>hi</body></html>", 200, None)
        r_thin = DP.probe(quiet=True)
        DP.fetch = lambda u, timeout=25: (big, 200, None)
        r_ok = DP.probe(quiet=True)
        disk = json.loads(DP.OUT.read_text())
    finally:
        DP.OUT, DP.fetch = _out, _fetch

check("انسداد ۴۰۳ → UNREACHABLE، نه دریافت‌شده",
      all(d["status"] == "UNREACHABLE" for d in r_block["docs"])
      and r_block["ok"] == 0)
check("انسداد، کد HTTP و دلیل را نگه می‌دارد",
      all(d["http"] == 403 and d["error"] for d in r_block["docs"]))
check("انسداد صریح می‌گوید ادعا UNVERIFIED می‌ماند",
      all("UNVERIFIED" in d["note"] for d in r_block["docs"]))
check("صفحهٔ توخالی THIN می‌شود، نه FETCHED — خطر «موفقیتِ خاموش»",
      all(d["status"] == "THIN" for d in r_thin["docs"]) and r_thin["ok"] == 0,
      str(r_thin["docs"][0])[:200])
check("صفحهٔ پرمحتوا FETCHED می‌شود", r_ok["ok"] == 6)
check("سند دریافت‌شده فهرست یافته/غایب دارد",
      all("found" in d and "missing" in d for d in r_ok["docs"]))
check("گزارش روی دیسک نوشته می‌شود", disk["total"] == 6 and disk["docs"])
check("هیچ حالتی بدون status نمی‌ماند",
      all(d.get("status") for r in (r_block, r_thin, r_ok) for d in r["docs"]))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبانِ کاوش اسناد: هر {OK} بررسی سبز")
