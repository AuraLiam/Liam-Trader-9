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

# ── جمع‌بندی دقیقه‌ای ───────────────────────────────────────────────────
# چرا این لایه اضافه شد: گام ۳ثانیه‌ای ۶ نماد = ~۵۵ مگابایت در روز، که در
# گیت قابل نگهداری نیست؛ و سؤالی که این داده باید جواب بدهد روی کندل
# ۱ دقیقه پرسیده می‌شود. پس واحد ذخیره دقیقه است. آنچه این‌جا قفل می‌شود
# همان چیزهایی است که اگر خراب باشند سطر دقیقه‌ای بی‌صدا دروغ می‌گوید.
import json                                              # noqa: E402
import tempfile                                          # noqa: E402

# ۱۷۰۰۰۰۰۰۴۰۰۰۰ مضرب دقیق ۶۰۰۰۰ است (۱.۷e۱۲ نیست — این را همین آزمون
# اولین بار گرفت: مرزِ فرضیِ من مرز نبود).
B0 = 1_700_000_040_000
check("مرز سطل دقیقاً روی مضرب ۶۰ هزار است",
      DC.bucket_of(B0) == B0 and DC.bucket_of(B0 + 60_000) == B0 + 60_000,
      f"{DC.bucket_of(B0)}")
check("هر زمانی داخل یک دقیقه به یک سطل می‌رود",
      {DC.bucket_of(B0 + k) for k in (0, 1, 59_999)} == {B0})
check("یک میلی‌ثانیه بعد از مرز، سطل عوض می‌شود",
      DC.bucket_of(B0 + 60_000) != B0)
agg = DC.MinuteAgg(B0)
prev_f = None
# سه عکس با عمق بید صعودی و mid بالارونده — هم آمار پایه، هم up/dn
for k, (bq, aq, px) in enumerate(((5.0, 4.0, 100.0), (7.0, 3.0, 100.2),
                                  (6.0, 9.0, 100.1))):
    ff = DC.features([(px, bq), (px - 0.1, 1)], [(px + 0.1, aq), (px + 0.2, 1)],
                     prev=prev_f, now_ms=B0 + k * 3000)
    agg.add(ff)
    prev_f = ff
agg.miss()
row = agg.close()

check("سطر دقیقه‌ای زمان سطل را می‌گیرد نه زمان نمونه", row["t"] == B0)
check("تعداد نمونه‌ها ثبت می‌شود", row["n"] == 3, str(row["n"]))
check("نمونهٔ ازدست‌رفته پنهان نمی‌شود (miss روی سطر)", row["miss"] == 1)
check("span_ms فاصلهٔ اولین تا آخرین نمونه است", row["span_ms"] == 6000,
      str(row["span_ms"]))
check("mid_o اولین و mid_c آخرین است",
      row["mid_o"] == 100.05 and abs(row["mid_c"] - 100.15) < 1e-9,
      f"{row['mid_o']} {row['mid_c']}")
check("mid_h و mid_l سقف و کف دقیقه‌اند",
      abs(row["mid_h"] - 100.25) < 1e-9 and abs(row["mid_l"] - 100.05) < 1e-9,
      f"{row['mid_h']} {row['mid_l']}")
check("میانگین عدم‌تعادل از همان سه نمونه حساب می‌شود",
      abs(row["imb_mean_1"] - (1/9 + 0.4 + (-0.2)) / 3) < 1e-5,
      str(row["imb_mean_1"]))
check("imb_last آخرین نمونه است نه میانگین",
      abs(row["imb_last_1"] - (-0.2)) < 1e-5, str(row["imb_last_1"]))
check("کمینه و بیشینهٔ عدم‌تعادل جدا نگه داشته می‌شوند",
      row["imb_min_1"] <= row["imb_mean_1"] <= row["imb_max_1"]
      and abs(row["imb_max_1"] - 0.4) < 1e-5,
      f"{row['imb_min_1']}..{row['imb_max_1']}")
# میانگینِ تنها، جهشِ لحظه‌ای را پنهان می‌کند — دلیل وجود min/max:
flat = DC.MinuteAgg(B0)
spiky = DC.MinuteAgg(B0)
for q in (3.0, 3.0, 3.0):
    flat.add(DC.features([(100.0, q)], [(100.1, 3.0)], now_ms=B0))
for q in (1.0, 100.0, 1.0):
    spiky.add(DC.features([(100.0, q)], [(100.1, 3.0)], now_ms=B0))
fr, sr = flat.close(), spiky.close()
check("سطلِ آرام و سطلِ جهش‌دار با min/max از هم جدا می‌شوند",
      sr["imb_max_1"] - sr["imb_min_1"] > fr["imb_max_1"] - fr["imb_min_1"] + 0.5,
      f"جهش {sr['imb_min_1']}..{sr['imb_max_1']} / آرام {fr['imb_min_1']}..{fr['imb_max_1']}")
# up/dn: بید از ۵ به ۷ (+۲) و از ۷ به ۶ (−۱)
check("جمع تغییرهای مثبت و منفی جدا ثبت می‌شود، نه فقط برایند",
      abs(row["up_bid_1"] - 2.0) < 1e-6 and abs(row["dn_bid_1"] - (-1.0)) < 1e-6,
      f"up={row['up_bid_1']} dn={row['dn_bid_1']}")
check("نام فیلد up/dn است نه add/cancel (تفکیک‌ناپذیرند — قانون ۰۸)",
      not any(k.startswith(("add_", "cxl_", "cancel_")) for k in row))
check("سطل بی‌نمونه سطر نمی‌سازد (داده ساخته نمی‌شود)",
      DC.MinuteAgg(B0).close() is None)

# ── نوشتن/خواندن روزانهٔ فشرده ──────────────────────────────────────────
with tempfile.TemporaryDirectory() as td:
    _saved_out = DC.OUTDIR
    DC.OUTDIR = Path(td)
    try:
        p1 = DC.write_minute("TESTUSDT", row)
        # اجرای دوم، سطل بعدی: باید به همان فایل append شود (gzip چندعضوی)
        row2 = dict(row, t=B0 + 60_000)
        p2 = DC.write_minute("TESTUSDT", row2)
        # روز بعد: فایل جدا
        p3 = DC.write_minute("TESTUSDT", dict(row, t=B0 + 86_400_000))
        back = DC.read_minutes("TESTUSDT", outdir=td)
        size = p1.stat().st_size
    finally:
        DC.OUTDIR = _saved_out

check("فایل روزانه است و نامش تاریخ دارد", p1 == p2 and p1 != p3,
      f"{p1.name} / {p3.name}")
check("فایل فشرده است (.gz)", p1.name.endswith(".m1.jsonl.gz"), p1.name)
check("append دوم گم نمی‌شود (gzip چندعضوی درست خوانده می‌شود)",
      len(back) == 3, str(len(back)))
check("سطرها بر زمان مرتب برمی‌گردند",
      [r["t"] for r in back] == sorted(r["t"] for r in back))
check("محتوای سطر بعد از رفت‌وبرگشت دست‌نخورده است", back[0] == row)
check("فشرده‌سازی واقعاً کوچک‌تر از خام است",
      size < len(json.dumps(row)) , f"gz={size} خام={len(json.dumps(row))}")

# ── حلقه: مسیر جمع‌بندی، بدون شبکه ─────────────────────────────────────
# snapshot جعلی می‌شود تا خودِ حلقه سنجیده شود نه API.
_saved_snap = DC.snapshot
_tick = {"i": 0}


def _fake_snapshot(sym, path=None, prev=None):
    i = _tick["i"]
    _tick["i"] += 1
    if i == 2:
        return None, "خطای ساختگی"          # یک نمونهٔ ازدست‌رفته
    t = B0 + i * 30_000                      # هر گام نیم دقیقه → چند سطل
    return DC.features([(100.0 + i * 0.01, 5)], [(100.1 + i * 0.01, 4)],
                       prev=prev, now_ms=t), None


with tempfile.TemporaryDirectory() as td:
    _saved_out = DC.OUTDIR
    DC.OUTDIR = Path(td)
    DC.snapshot = _fake_snapshot
    try:
        res = DC.collect(["TESTUSDT"], minutes=0.02, interval_s=0.001,
                         quiet=True, agg=True)
        rows = DC.read_minutes("TESTUSDT", outdir=td)
    finally:
        DC.snapshot = _saved_snap
        DC.OUTDIR = _saved_out

check("حلقه در حالت جمع‌بندی سطر دقیقه‌ای می‌نویسد", len(rows) >= 2,
      f"{len(rows)} سطر")
check("سطل نیمه‌تمام آخر هم نوشته می‌شود (داده دور ریخته نمی‌شود)",
      res["wrote"].get("TESTUSDT", 0) == len(rows),
      f"{res['wrote']} vs {len(rows)}")
check("هر سطر روی مرز دقیقه نشسته است",
      all(r["t"] % DC.BUCKET_MS == 0 for r in rows))
check("سطل‌ها یکتا و صعودی‌اند (سطل دوباره باز نمی‌شود)",
      [r["t"] for r in rows] == sorted({r["t"] for r in rows}),
      str([r["t"] for r in rows]))
check("خطای برداشت در شمارش خطاها می‌آید", res["errors"].get("خطای ساختگی") == 1,
      str(res["errors"]))
# منهای دو: یکی برای عکسِ اعتبارسنجیِ ابتدای collect (که سطر نمی‌سازد)،
# یکی برای نمونهٔ ازدست‌رفتهٔ ساختگی.
check("مجموع n سطرها = نمونه‌های موفقِ داخل حلقه",
      sum(r["n"] for r in rows) == _tick["i"] - 2,
      f"{sum(r['n'] for r in rows)} vs {_tick['i'] - 2}")

# ── گزارش انباشت ────────────────────────────────────────────────────────
with tempfile.TemporaryDirectory() as td:
    _saved_out = DC.OUTDIR
    DC.OUTDIR = Path(td)
    try:
        for t in (B0, B0 + 60_000, B0 + 86_400_000):
            DC.write_minute("AAAUSDT", dict(row, t=t))
        DC.write_minute("BBBUSDT", dict(row, t=B0))
        syms = DC.symbols_on_disk(td)
        txt, tot = DC.stats(td)
    finally:
        DC.OUTDIR = _saved_out

check("نماد از نام فایل روزانه درست بیرون کشیده می‌شود",
      syms == ["AAAUSDT", "BBBUSDT"], str(syms))
check("گزارش انباشت مجموع درست می‌دهد", tot == 4, str(tot))
check("هر نماد یک سطر در گزارش دارد",
      txt.count("| AAAUSDT |") == 1 and txt.count("| BBBUSDT |") == 1)
check("ستون ازدست‌رفته در گزارش هست (سکوت ≠ سلامت)", "ازدست‌رفته" in txt)

# ── فایل سلامت: دلیلِ رد باید منتشر شود، نه فقط در لاگ بماند ────────────
# دو بار امشب دلیل نبودن یک نماد فقط داخل لاگ جاب ماند و از API لاگ
# قابل بازیابی نبود (خروجی با فهرست فایل‌های کامیت پر می‌شود).
with tempfile.TemporaryDirectory() as td:
    _saved_out = DC.OUTDIR
    _saved_h = DC.HEALTH
    DC.OUTDIR = Path(td)
    DC.HEALTH = Path(td) / "depth-health.json"
    try:
        DC.write_minute("HHHUSDT", dict(row, t=B0))
        h = DC.write_health({"rejected": {"ZECUSDT": "CONTRACT_NOT_FOUND"},
                             "errors": {"timeout": 3}}, outdir=td)
        on_disk = json.loads(DC.HEALTH.read_text())
    finally:
        DC.OUTDIR, DC.HEALTH = _saved_out, _saved_h

check("فایل سلامت روی دیسک نوشته می‌شود", on_disk == h)
check("دلیل ردِ نماد در فایل منتشرشده هست (نه فقط لاگ)",
      on_disk["rejected"]["ZECUSDT"] == "CONTRACT_NOT_FOUND")
check("خطاهای حین برداشت هم منتشر می‌شوند", on_disk["errors"]["timeout"] == 3)
check("فایل سلامت انباشت هر نماد را دارد",
      on_disk["symbols"][0]["symbol"] == "HHHUSDT"
      and on_disk["total_minutes"] == 1)
check("فایل سلامت پیکربندی برداشت را ثبت می‌کند (مسیر/عمق/سطوح)",
      "market/depth" in on_disk["endpoint"]
      and on_disk["depth_limit"] == DC.DEPTH_LIMIT
      and on_disk["levels"] == list(DC.LEVELS))

# ── اعتبارسنجی نماد پیش از شروع ─────────────────────────────────────────
# درس ۲۲ اوت: برداشت با ۶ نماد شروع شد و ۴ فایل ساخت. دو نمادِ باقی فقط
# **غایب** بودند — نه خطا، نه دلیل. غیبتِ بی‌دلیل شبیه «داده نبود» است
# در حالی که خرابی پیکربندی بود.
_saved_snap2 = DC.snapshot
DC.snapshot = lambda s, path=None, prev=None: (
    (None, "CONTRACT_NOT_FOUND") if s.startswith("BAD")
    else (DC.features([(100.0, 5)], [(100.1, 4)], now_ms=B0), None))
try:
    good, bad = DC.verify_symbols(["OKUSDT", "BADUSDT", "BAD2USDT"], quiet=True)
finally:
    DC.snapshot = _saved_snap2
check("نماد سالم از ناسالم جدا می‌شود", good == ["OKUSDT"], str(good))
check("نماد ردشده دلیل واقعی را حمل می‌کند (نه فقط غیبت)",
      bad == {"BADUSDT": "CONTRACT_NOT_FOUND",
              "BAD2USDT": "CONTRACT_NOT_FOUND"}, str(bad))

DC.snapshot = lambda s, path=None, prev=None: (None, "همه خرابند")
try:
    DC.collect(["BADUSDT"], minutes=0.001, quiet=True)
    raised2 = False
except RuntimeError as e:
    raised2 = "هیچ نماد سالمی" in str(e)
finally:
    DC.snapshot = _saved_snap2
check("اگر هیچ نمادی سالم نباشد، برداشت با خطا می‌ایستد (نه سکوت)", raised2)

# ── تا زدن عکس خام قدیمی ────────────────────────────────────────────────
# برداشت‌های پیش از لایهٔ جمع‌بندی خام نوشته شدند؛ آن داده باید به همان
# شکل دقیقه‌ای بیاید، نه اینکه به‌عنوان فرمت دوم رها شود.
with tempfile.TemporaryDirectory() as td:
    raw = Path(td) / "CCCUSDT.jsonl"
    pf = None
    with raw.open("w") as fh:
        # ۵۰ عکس با گام ۳ثانیه = ۱۵۰ ثانیه = بخشی از ۳ دقیقه
        for k in range(50):
            ff = DC.features([(100.0 + k * 0.01, 5)], [(100.1 + k * 0.01, 4)],
                             prev=pf, now_ms=B0 + k * 3000)
            pf = ff
            fh.write(json.dumps(ff) + "\n")
    made = DC.fold_raw("CCCUSDT", outdir=td, remove=True)
    folded = DC.read_minutes("CCCUSDT", outdir=td)
    gone = not raw.exists()

check("خام به سطر دقیقه‌ای تا می‌شود", made == len(folded) == 3,
      f"made={made} rows={len(folded)}")
check("هیچ عکسی در تا زدن گم نمی‌شود",
      sum(r["n"] for r in folded) == 50, str(sum(r["n"] for r in folded)))
check("سطرهای تاشده هم روی مرز دقیقه‌اند",
      all(r["t"] % DC.BUCKET_MS == 0 for r in folded))
check("فایل خام بعد از تا شدن حذف می‌شود (دو فرمت هم‌زمان نمی‌ماند)", gone)
check("OUTDIR بعد از تا زدن به جای خودش برمی‌گردد",
      DC.OUTDIR == _saved_out, str(DC.OUTDIR))

# ── دلیلِ «شکل ناشناخته» باید بدنه را نشان بدهد ─────────────────────────
# ۲۳ اوت: ZEC و DASH فقط «شکل دفتر ناشناخته» دادند و بدون دیدن پاسخ
# نمی‌شد فهمید دفتر خالی است یا شکلش فرق دارد. دلیلِ بی‌نمونه یعنی
# یک دور عیب‌یابیِ دیگر.
_saved_get = DC._get
DC._get = lambda url, timeout=12: ({"code": 0, "data": {"bids": [],
                                                        "asks": []}}, None)
try:
    _f, _why = DC.snapshot("ZECUSDT")
finally:
    DC._get = _saved_get
check("دلیلِ شکل ناشناخته نمونهٔ خودِ پاسخ را حمل می‌کند",
      _f is None and "شکل دفتر ناشناخته" in _why and "bids" in _why, str(_why))
check("نمونهٔ پاسخ کوتاه نگه داشته می‌شود (لاگ را پر نکند)",
      len(_why) < 220, str(len(_why)))



# ── بودجهٔ زمان: پنجرهٔ برداشت باید از زمانِ باقی‌مانده بیاید ──────────
#
# عیبِ اندازه‌گیری‌شدهٔ ۶ سپتامبر: `depth-health.json` ۲۳ ساعت کهنه بود و
# سه اجرای پیاپی (۱۴۵، ۱۴۶، ۱۴۷) **cancelled** شدند — هر سه حوالی دقیقهٔ
# ۵۹. حساب: `fetch-depth: 0` روی مخزنِ ۴.۴ گیگابایتی ~۹ دقیقه + ۵۰ دقیقه
# برداشت = ۵۹ > سقف ۵۸ → کنسل، **درست قبل از مرحلهٔ انتشار**. یعنی هر
# ساعت ۵۰ دقیقه برداشتِ واقعی انجام و بعد دور ریخته می‌شد.
#
# دو چیز قفل می‌شود تا برنگردد: تاریخچهٔ کامل کشیده نشود، و پنجرهٔ
# برداشت عددِ ثابت نباشد.
import re as _re                                     # noqa: E402
_wf_p = HERE.parent.parent.parent / ".github" / "workflows" / "depth-collect.yml"
_wf = _wf_p.read_text(encoding="utf-8")
_cmds = [l.strip() for l in _wf.splitlines()
         if l.strip() and not l.strip().lstrip("-").strip().startswith("#")]
check("تاریخچهٔ کامل کشیده نمی‌شود (۹ دقیقه از بودجه برمی‌گردد)",
      not any("fetch-depth: 0" in c for c in _cmds), "fetch-depth: 0 برگشته")
check("ساعت شروع قبل از checkout ثبت می‌شود",
      _wf.index("JOB_T0=$(date +%s)") < _wf.index("actions/checkout"))
check("پنجرهٔ برداشت از زمانِ باقی‌مانده مشتق می‌شود، نه عددِ ثابت",
      "LEFT=$(( JOB_BUDGET_MIN - ELAPSED - PUBLISH_RESERVE_MIN ))" in _wf
      and '--minutes "$MIN"' in _wf)
check("و رزروِ انتشار از پنجره کم می‌شود", "PUBLISH_RESERVE_MIN" in _wf)
check("زمانِ خیلی کم = برداشت نکن (بهتر از برداشتِ کنسل‌شده)",
      '[ "$MIN" -lt 5 ]' in _wf and "exit 0" in _wf)
_m_to = _re.search(r"timeout-minutes:\s*(\d+)", _wf)
_m_bg = _re.search(r'JOB_BUDGET_MIN:\s*"(\d+)"', _wf)
check("بودجهٔ داخل شل با سقفِ واقعیِ job یکی است (سند و کد جدا نیفتند)",
      bool(_m_to and _m_bg) and _m_to.group(1) == _m_bg.group(1),
      f"timeout={_m_to and _m_to.group(1)} budget={_m_bg and _m_bg.group(1)}")

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان جمع‌آورندهٔ عمق: هر {OK} بررسی سبز")
