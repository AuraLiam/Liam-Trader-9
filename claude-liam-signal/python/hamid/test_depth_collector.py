"""پاسبان جمع‌آورندهٔ عمق — همراه اجباری depth_collector.py.

کاملاً آفلاین. آنچه قفل می‌شود، همان چیزهایی است که اگر خراب باشند
دادهٔ عمق بی‌صدا بی‌ارزش می‌شود: پارس درست دفتر با پوشش‌های مختلف،
ردِ دفتر متقاطع، درستیِ ریاضیِ عدم‌تعادل و میکروپرایس، و اینکه شکل
ناشناخته به‌جای حدس‌زدن None برگردد.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import depth_collector as DC                # noqa: E402

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


# ── parse_book: پوشش‌های رایج ───────────────────────────────────────────
BOOK = {"bids": [["100.0", "5"], ["99.9", "3"], ["99.8", "2"]],
        "asks": [["100.1", "4"], ["100.2", "6"], ["100.3", "1"]]}
for label, payload in (
        ("لخت", BOOK),
        ("زیر data", {"data": BOOK}),
        ("زیر result", {"result": BOOK}),
        ("کلید کوتاه b/a", {"b": BOOK["bids"], "a": BOOK["asks"]}),
        ("ردیف dict", {"bids": [{"price": "100.0", "qty": "5"}],
                       "asks": [{"price": "100.1", "qty": "4"}]}),
):
    b, a = DC.parse_book(payload)
    check(f"دفتر با پوشش «{label}» پارس می‌شود", b and a, f"{b} {a}")

b, a = DC.parse_book(BOOK)
check("بیدها نزولی و اسک‌ها صعودی مرتب می‌شوند",
      b[0][0] > b[-1][0] and a[0][0] < a[-1][0])
check("بهترین بید و اسک درست‌اند", b[0][0] == 100.0 and a[0][0] == 100.1)

for label, bad in (("خالی", {}), ("بدون asks", {"bids": BOOK["bids"]}),
                   ("لیست ساده", [1, 2, 3]), ("رشته", "nope")):
    bb, aa = DC.parse_book(bad)
    check(f"شکل ناشناخته «{label}» = None، نه حدس", bb is None and aa is None)

# ── features: ریاضی ─────────────────────────────────────────────────────
f = DC.features(b, a, now_ms=1000)
check("mid درست حساب می‌شود", abs(f["mid"] - 100.05) < 1e-9, str(f["mid"]))
check("اسپرد به bps درست است",
      abs(f["spread_bps"] - (0.1 / 100.05 * 10000)) < 1e-3, str(f["spread_bps"]))
check("عمق تجمعی سطح ۱ = بهترین سطح",
      f["depth_bid_1"] == 5.0 and f["depth_ask_1"] == 4.0)
check("عمق تجمعی سطح ۳ جمع می‌شود",
      abs(f["depth_bid_5"] - 10.0) < 1e-9 and abs(f["depth_ask_5"] - 11.0) < 1e-9,
      f"{f['depth_bid_5']} {f['depth_ask_5']}")
check("عدم‌تعادل سطح ۱ = (۵−۴)/۹",
      abs(f["imb_1"] - (1 / 9)) < 1e-4, str(f["imb_1"]))
check("عدم‌تعادل همیشه بین ۱− و ۱+ است",
      all(-1 <= f[f"imb_{n}"] <= 1 for n in DC.LEVELS))
# میکروپرایس: با بید سنگین‌تر باید بالای mid برود
heavy_bid = DC.features([(100.0, 50.0), (99.9, 1)], [(100.1, 1.0), (100.2, 1)],
                        now_ms=1)
check("بیدِ سنگین میکروپرایس را بالای mid می‌برد",
      heavy_bid["microprice_dev_bps"] > 0, str(heavy_bid["microprice_dev_bps"]))
heavy_ask = DC.features([(100.0, 1.0), (99.9, 1)], [(100.1, 50.0), (100.2, 1)],
                        now_ms=1)
check("اسکِ سنگین میکروپرایس را زیر mid می‌برد",
      heavy_ask["microprice_dev_bps"] < 0, str(heavy_ask["microprice_dev_bps"]))

# دفتر متقاطع = دادهٔ خراب، نه ویژگی
check("دفتر متقاطع رد می‌شود (اسک زیر بید)",
      DC.features([(100.0, 1)], [(99.0, 1)], now_ms=1) is None)

# ── تغییرها بین دو عکس ──────────────────────────────────────────────────
f2 = DC.features([(100.2, 7.0), (100.1, 1)], [(100.3, 2.0), (100.4, 1)],
                 prev=f, now_ms=4000)
check("dt_ms از اختلاف زمان دو عکس می‌آید", f2["dt_ms"] == 3000)
check("تغییر عمق بید ثبت می‌شود", abs(f2["d_bid_1"] - (7.0 - 5.0)) < 1e-9,
      str(f2["d_bid_1"]))
check("تغییر mid به bps ثبت می‌شود و علامتش درست است",
      f2["d_mid_bps"] > 0, str(f2["d_mid_bps"]))
check("عکس اول تغییر ندارد (چیزی برای مقایسه نبوده)", "d_mid_bps" not in f)
check("نام فیلدها d_ است نه ofi (این OFI واقعی نیست — قانون ۰۸)",
      not any(k.startswith("ofi") for k in f2))

# ── api_ok: پاسخ ۲۰۰ با کد خطای داخلی موفقیت نیست ──────────────────────
# درس probe اول (۲۲ اوت): هر پنج مسیر HTTP 200 دادند ولی چهارتا داخلشان
# code=404 و یکی code=10008 داشت. اگر فقط کد HTTP دیده می‌شد، probe
# می‌گفت «همه جواب دادند» و مسیر غلط ثابت می‌شد.
ok, why = DC.api_ok({"code": 0, "data": {"bids": [], "asks": []}})
check("پاسخ سالم (code=0 و data پر) موفق است", ok and why is None)
for label, bad in (
        ("۴۰۴ داخلی", {"code": 404, "data": None, "msg": "Not Found"}),
        ("پارامتر نامعتبر", {"code": 10008, "data": None,
                             "msg": "Parameter 20 does not match"}),
        ("data خالی", {"code": 0, "data": None, "msg": "ok"})):
    ok2, why2 = DC.api_ok(bad)
    check(f"«{label}» با کد ۲۰۰ هم موفقیت حساب نمی‌شود", not ok2, str(why2))
check("پیام خطای داخلی در دلیل می‌آید (نه فقط False)",
      "10008" in str(DC.api_ok({"code": 10008, "data": None, "msg": "x"})[1]))

# مقدار limit باید از فهرستی باشد که خودِ API اعلام کرد
check("limit پیش‌فرض از مقادیر مجاز API است",
      str(DC.DEPTH_LIMIT) in DC.VALID_LIMITS,
      f"{DC.DEPTH_LIMIT} not in {DC.VALID_LIMITS}")
check("مسیر عمق بعد از کشف ثابت شده است",
      DC.DEPTH_PATH and "market/depth" in DC.DEPTH_PATH)
check("سطوح گزارش‌شده از عمق درخواستی بیشتر نیست",
      max(DC.LEVELS) <= DC.DEPTH_LIMIT)

# ── _get: خطا هرگز بی‌جزئیات نیست ───────────────────────────────────────
import io                                              # noqa: E402
import urllib.error                                    # noqa: E402
import urllib.request                                  # noqa: E402

old = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=None: (_ for _ in ()).throw(
    urllib.error.HTTPError(req.full_url, 404, "Not Found", {},
                           io.BytesIO(b'{"msg":"path not found"}')))
try:
    data, err = DC._get("https://fapi.bitunix.com/x")
finally:
    urllib.request.urlopen = old
check("خطای HTTP کد وضعیت و بدنه را حمل می‌کند",
      data is None and "404" in err and "path not found" in err, str(err))

# collect بدون مسیر کشف‌شده نباید چیزی حدس بزند
_saved = DC.DEPTH_PATH
DC.DEPTH_PATH = None
try:
    DC.collect(["BTCUSDT"], minutes=0.001, depth_path=None)
    raised = False
except RuntimeError as e:
    raised = "probe" in str(e)
finally:
    DC.DEPTH_PATH = _saved
check("بدون مسیر کشف‌شده، برداشت شروع نمی‌شود (حدس ممنوع)", raised)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان جمع‌آورندهٔ عمق: هر {OK} بررسی سبز")
