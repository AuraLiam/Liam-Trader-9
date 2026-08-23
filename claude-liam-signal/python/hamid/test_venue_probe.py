"""پاسبان کاوش صرافی نامزد — همراه اجباری venue_probe.py. کاملاً آفلاین.

آنچه قفل می‌شود همان چیزهایی است که اگر خراب باشند مقایسهٔ صرافی بی‌صدا
دروغ می‌گوید: پاسخ ۲۰۰ با خطای داخلی موفقیت حساب نشود، شکل ناشناخته
حدس زده نشود، دفتر متقاطع رد شود، و کارمزدِ نایافته None بماند نه صفر.
"""
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import venue_probe as VP                   # noqa: E402

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


# ── ok_payload: ۲۰۰ با خطای داخلی موفقیت نیست ──────────────────────────
check("پاسخ سالم موفق است",
      VP.ok_payload({"code": 0, "data": [{"symbol": "BTC_USDT"}]})[0])
check("code=200 هم پذیرفته می‌شود (قرارداد بعضی صرافی‌ها)",
      VP.ok_payload({"code": 200, "data": [1]})[0])
for label, bad in (
        ("کد خطای داخلی", {"code": 10007, "msg": "not found", "data": None}),
        ("success=false", {"success": False, "message": "bad symbol"}),
        ("دادهٔ خالی", {"code": 0, "data": []}),
        ("data=None", {"code": 0, "data": None})):
    good, why = VP.ok_payload(bad)
    check(f"«{label}» با HTTP 200 هم موفقیت نیست", not good, str(why))
check("دلیل رد در پیام می‌آید، نه فقط False",
      "10007" in str(VP.ok_payload({"code": 10007, "msg": "x", "data": None})[1]))
check("لیست لخت و پر، معتبر است", VP.ok_payload([{"a": 1}])[0])
check("لیست خالی معتبر نیست", not VP.ok_payload([])[0])

# ── book_stats: ریاضی و ردِ دادهٔ خراب ─────────────────────────────────
BOOK = {"data": {"bids": [["100.0", "5"], ["99.9", "3"], ["99.8", "2"],
                          ["99.7", "1"], ["99.6", "1"], ["99.5", "9"]],
                 "asks": [["100.1", "4"], ["100.2", "6"], ["100.3", "1"],
                          ["100.4", "1"], ["100.5", "1"], ["100.6", "9"]]}}
st = VP.book_stats(BOOK)
check("اسپرد به bps درست حساب می‌شود",
      abs(st["spread_bps"] - (0.1 / 100.05 * 10000)) < 1e-3, str(st))
check("عمق پنج سطح جمع می‌شود، نه بیشتر",
      st["depth_bid_5"] == 12.0 and st["depth_ask_5"] == 13.0, str(st))
check("دفتر نامرتب هم درست مرتب می‌شود",
      VP.book_stats({"data": {"bids": [["99.9", "3"], ["100.0", "5"]],
                              "asks": [["100.2", "6"], ["100.1", "4"]]}}
                    )["spread_bps"] == st["spread_bps"])
check("دفتر متقاطع رد می‌شود (دادهٔ خراب، نه ویژگی)",
      VP.book_stats({"data": {"bids": [["100.0", "1"]],
                              "asks": [["99.0", "1"]]}}) is None)
for label, bad in (("خالی", {}), ("بدون asks", {"data": {"bids": [["1", "1"]]}}),
                   ("رشته", "nope"), ("عدد به‌جای ردیف",
                                      {"data": {"bids": [1], "asks": [2]}})):
    check(f"شکل ناشناخته «{label}» = None، نه حدس",
          VP.book_stats(bad) is None)

# ── کارمزد: نایافته یعنی None، نه صفر ──────────────────────────────────
check("کارمزد از پاسخ شناخته‌شده خوانده می‌شود",
      VP.fee_from_contract({"data": [{"symbol": "BTC_USDT",
                                      "makerFeeRate": "0",
                                      "takerFeeRate": "0.0001"}]})
      == {"makerFeeRate": "0", "takerFeeRate": "0.0001"})
check("کلید ناشناخته کارمزدِ صفر نمی‌سازد (صفرِ جعلی خطرناک‌ترین است)",
      VP.fee_from_contract({"data": [{"symbol": "X", "commission": "0.01"}]})
      is None)
check("پاسخ بی‌داده None می‌دهد", VP.fee_from_contract({"data": []}) is None)

# ── _get: خطا هرگز بی‌جزئیات نیست ──────────────────────────────────────
old = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=None: (_ for _ in ()).throw(
    urllib.error.HTTPError(req.full_url, 403, "Forbidden", {},
                           io.BytesIO(b'{"msg":"blocked"}')))
try:
    data, err = VP._get("https://api.kcex.com/x")
finally:
    urllib.request.urlopen = old
check("خطای HTTP کد و بدنه را حمل می‌کند",
      data is None and "403" in err and "blocked" in err, str(err))


class _Resp:
    status = 200

    def __init__(self, body):
        self._b = body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


urllib.request.urlopen = lambda req, timeout=None: _Resp(b"<html>nope</html>")
try:
    data2, err2 = VP._get("https://api.kcex.com/y")
finally:
    urllib.request.urlopen = old
check("پاسخ غیرJSON خطا می‌دهد نه crash (صفحهٔ HTML به‌جای API)",
      data2 is None and "JSON نبود" in err2, str(err2))

# ── مقایسه بدون مسیر کشف‌شده چیزی نمی‌سازد ─────────────────────────────
from hamid import depth_collector as DC               # noqa: E402
_s = DC.snapshot
DC.snapshot = lambda s, path=None, prev=None: (
    {"spread_bps": 1.0, "depth_bid_5": 10.0, "depth_ask_5": 11.0}, None)
_out = VP.OUT
VP.OUT = Path("/tmp/venue-compare-test.json")
try:
    res = VP.compare(["BTCUSDT"], kcex_depth_url=None, quiet=True)
finally:
    DC.snapshot = _s
    VP.OUT = _out
check("بدون مسیر KCEX، مقایسه عدد جعلی نمی‌سازد",
      "error" in res["symbols"][0]["kcex"]
      and "median_spread_bps" not in res, json.dumps(res, ensure_ascii=False))
check("طرف بیت‌یونیکس با همان جمع‌آورندهٔ موجود خوانده می‌شود",
      res["symbols"][0]["bitunix"]["spread_bps"] == 1.0)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان کاوش صرافی: هر {OK} بررسی سبز")
