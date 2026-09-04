"""پاسبان اتاق توزیع و تاکسونومی (۳ سپتامبر) — آفلاین، بدون شبکه.

قفل می‌کند: دسته‌بندی پیش از توزیع؛ استیبل/رپد از دفتر بیرون؛ سهام‌توکن
شناخته شود؛ ناشناخته حدس زده نشود؛ مسیر رویداد→اتاق درست باشد؛ حذف با
دلیل ثبت شود نه بی‌صدا؛ و برنامهٔ درسی این اتاق موجود باشد.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import router as R                         # noqa: E402
from hamid import taxonomy as TX                      # noqa: E402

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


# ── ۱. پایه و دسته ────────────────────────────────────────────────────────
check("پایهٔ نماد درست جدا می‌شود", TX.base_of("BTCUSDT") == "BTC" and TX.base_of("PEPEUSDT") == "PEPE")
check("جفتِ استیبل-به-استیبل هم درست خوانده می‌شود", TX.base_of("USDCUSDT") == "USDC")
check("نماد پرپ با پسوند .P هم همان پایه را می‌دهد", TX.base_of("ETHUSDT.P") == "ETH")
for sym, sec in [("BTCUSDT", "major"), ("ETHUSDT", "major"), ("SOLUSDT", "l1"),
                 ("ARBUSDT", "l2"), ("PEPEUSDT", "meme"), ("UNIUSDT", "defi"),
                 ("TAOUSDT", "ai"), ("ONDOUSDT", "rwa"), ("AXSUSDT", "gaming"),
                 ("LINKUSDT", "oracle"), ("USDCUSDT", "stable"), ("WBTCUSDT", "wrapped"),
                 ("NVDABUSDT", "stocktoken"), ("HNTUSDT", "depin")]:
    check(f"دستهٔ {sym} = {sec}", TX.sector(sym) == sec, TX.sector(sym))
check("پایهٔ ناشناخته حدس زده نمی‌شود (unknown، نه دستهٔ دلخواه)", TX.sector("ZZQQUSDT") == "unknown")
check("سهام‌توکنِ خارج از جدول از روی الگو شناخته می‌شود", TX.sector("NFLXBUSDT") == "stocktoken")

# ── ۲. کارت ارز ───────────────────────────────────────────────────────────
c = TX.classify("USDCUSDT", rank=5)
check("استیبل قابل‌معامله نیست و دلیلش نوشته می‌شود",
      c["tradable"] is False and any("استیبل" in n for n in c["notes"]))
check("رپد هم قابل‌معامله نیست", TX.classify("WBTCUSDT")["tradable"] is False)
c = TX.classify("NVDABUSDT", rank=120)
check("سهام‌توکن برچسب وابستگی به ساعت بازار می‌گیرد",
      c["session_bound"] is True and c["tier"] == "small", str(c["tier"]))
check("ردهٔ نقدشوندگی از رتبه می‌آید", TX.tier(3) == "core" and TX.tier(60) == "mid" and TX.tier(400) == "micro")
check("رتبهٔ ناموجود = unknown، نه صفر", TX.tier(None) == "unknown")
c = TX.classify("TRUMPUSDT", rank=50, sens={"TRUMPUSDT": {"class": "INDEPENDENT"}})
check("کلاس رفتاری مستقل از BTC روی کارت می‌نشیند و یادداشت می‌گیرد",
      c["btc_class"] == "INDEPENDENT" and any("مستقل از بیت‌کوین" in n for n in c["notes"]))
check("بی‌دادهٔ حساسیت = UNKNOWN، نه COUPLED فرضی", TX.classify("XUSDT")["btc_class"] == "UNKNOWN")
c = TX.classify("SOLUSDT", vol={"SOLUSDT": 4.2})
check("کلاس نوسان از عدد واقعی می‌آید", c["vol_class"] == "hot" and c["atr_pct"] == 4.2)

# ── ۳. پوشش ──────────────────────────────────────────────────────────────
cov = TX.coverage(["BTCUSDT", "PEPEUSDT", "ZZQQUSDT", "USDCUSDT"])
check("متر پوشش صادق است (۳ از ۴ شناخته)", cov["known"] == 3 and cov["pct"] == 75.0, str(cov))

# ── ۴. توزیع: اول دسته، بعد مسیر ─────────────────────────────────────────
r = R.route("PUMP", "PEPEUSDT")
check("پامپ روی میم به اتاق لید-لگ و خبر می‌رود", r["rooms"] == ["E12", "E14"], str(r))
r = R.route("PUMP", "USDCUSDT")
check("پامپ روی استیبل رد می‌شود — دِپگ است نه پامپ", r["rooms"] == [] and r["dropped"])
check("و دلیلِ ردش نوشته می‌شود، بی‌صدا نمی‌افتد", "دسته" in r["dropped"][0], str(r["dropped"]))
r = R.route("DEPEG", "USDCUSDT")
check("مسیر جدای دِپگ برای استیبل هست", r["rooms"] == ["E02", "E05"])
r = R.route("SESSION_EVENT", "NVDABUSDT")
check("رویداد ساعت بازار فقط برای سهام‌توکن مسیر دارد", r["rooms"] == ["E05", "E01"])
check("همان رویداد برای ارز عادی مسیر ندارد", R.route("SESSION_EVENT", "BTCUSDT")["rooms"] == [])
r = R.route("SETUP_READY", "NVDABUSDT")
check("ستاپ روی سهام‌توکن با هشدار ساعت بازار همراه می‌شود", r["rooms"] and r["dropped"])
r = R.route("HOKUS_POKUS", "BTCUSDT")
check("رویداد ناشناخته اتاق نمی‌گیرد و صریح می‌گوید چرا", r["rooms"] == [] and "ناشناخته" in r["dropped"][0])
check("هر مسیر دلیلِ وجودش را می‌نویسد", all(v.get("why") for v in R.ROUTES.values()))
check("هر اتاقِ نام‌برده در مسیرها اسم دارد",
      all(rm in R.ROOM_NAMES for v in R.ROUTES.values() for rm in v["rooms"]))

# ── ۵. صف‌بندی دسته‌ای ────────────────────────────────────────────────────
cm = {s: TX.classify(s) for s in ("PEPEUSDT", "USDCUSDT", "BTCUSDT")}
d = R.dispatch([{"event": "PUMP", "sym": "PEPEUSDT"},
                {"event": "PUMP", "sym": "USDCUSDT"},
                {"event": "BTC_SHOCK", "sym": "BTCUSDT"}], cm)
check("صف اتاق لید-لگ فقط میم را گرفت", [x["sym"] for x in d["queues"]["E12"]] == ["PEPEUSDT"])
check("شوک بیت‌کوین به چهار اتاق رفت", all(k in d["queues"] for k in ("E06", "E03", "E04", "E16")))
check("ردشده گم نشد، در فهرست حذف‌ها با دلیل نشست",
      len(d["dropped"]) == 1 and d["dropped"][0]["sym"] == "USDCUSDT")
check("کارت ارز همراه هر تحویل می‌رود (دستور: با دسته‌بندی مشخص)",
      d["queues"]["E12"][0]["card"]["sector"] == "meme")

# ── ۶. عکس‌فوری ───────────────────────────────────────────────────────────
tmp = Path(HERE / "_t_router.json")
lat = {"symbols": [{"symbol": s} for s in ("BTCUSDT", "PEPEUSDT", "USDCUSDT", "NVDABUSDT", "ZZQQUSDT")]}
tmp.write_text(json.dumps(lat), encoding="utf-8")
try:
    b = R.build(latest=tmp, watchlist=Path("/nonexistent"),
                coverage=Path("/nonexistent"), sens={})
    check("عکس‌فوری: شمار جهان، قابل‌معامله و کنارگذاشته درست است",
          b["counts"] == {"universe": 5, "tradable": 4, "excluded": 1}, str(b["counts"]))
    check("عکس‌فوری دسته‌ها و نمونهٔ ناشناخته‌ها را می‌آورد",
          "meme" in b["sector_sizes"] and b["unknown_examples"] == ["ZZQQUSDT"])
    check("عکس‌فوری جدول کامل مسیرها با نام فارسی اتاق دارد",
          b["routes"]["PUMP"]["room_names"] == ["لید-لگ و پامپ", "خبر و کاتالیزور"])
    check("عکس‌فوری مرزش را صریح می‌گوید", "تصمیم معاملاتی نمی‌گیرد" in b["boundary"])
finally:
    tmp.unlink(missing_ok=True)

# ── ۷. سیم‌کشی ────────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
check("برنامهٔ درسی اتاق توزیع موجود است (منابع دسته‌بندی)",
      (ROOT / "brain" / "library" / "curricula" / "E27-router.md").exists())
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("router.json ردیف قرارداد دارد (قانون ۱۳)",
      "router.json" in reg and reg["router.json"]["producer"] == "hamid/router.py")
wf = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
check("چرخهٔ حمید اتاق توزیع را می‌سازد", "hamid.router --write" in wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
