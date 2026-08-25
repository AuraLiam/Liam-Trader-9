"""پاسبان تحویل دادهٔ تاریخی — همراه اجباری history_ingest.py. آفلاین.

سه خطری که می‌بندد:
۱. **حدس قالب**: فایلی که از سنجش رد نشود باید UNKNOWN بماند، نه این‌که
   با نزدیک‌ترین قالب «یک‌جوری» خوانده شود و عدد غلط وارد تحلیل کند.
۲. **دادهٔ بزرگ در گیت**: اسکریپت فقط شناسنامه می‌نویسد.
۳. **درِ دسترسی دروغ نگوید**: load_klines باید عین همان بایت‌ها را پس بدهد.
"""
import gzip
import json
import struct
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import history_ingest as HI               # noqa: E402

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


T0 = 1_700_000_000_000                                # ms، نوامبر ۲۰۲۳


def make_bin(path, n=200, tf_min=15, fmt="<6d", t_ms=True, bad_px=False):
    rows = b""
    for i in range(n):
        t = T0 + i * tf_min * 60_000
        if not t_ms:
            t = t // 1000
        o, c = 100.0 + i * 0.1, 100.05 + i * 0.1
        h, lo = c + 0.5, o - 0.5
        if bad_px:
            h, lo = lo, h                             # high < low = بی‌معنا
        rows += struct.pack(fmt, float(t), o, h, lo, c, 1000.0 + i)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(rows)


with tempfile.TemporaryDirectory() as td:
    src = Path(td) / "research"
    make_bin(src / "klines" / "AAAUSDT_15m.bin", n=200, tf_min=15)
    make_bin(src / "klines" / "BBBUSDT_1h.bin", n=100, tf_min=60, t_ms=False)
    make_bin(src / "klines" / "CCCUSDT_5m.bin", n=50, tf_min=5, bad_px=True)
    (src / "klines" / "junk.bin").parent.mkdir(parents=True, exist_ok=True)
    (src / "klines" / "junk.bin").write_bytes(b"\x00" * 1000)
    meta = src / "meta"
    meta.mkdir(parents=True)
    (meta / "universe.json").write_text(json.dumps({"symbols": ["AAAUSDT"]}))
    (meta / "dominance.json.gz").write_bytes(
        gzip.compress(json.dumps({"points": [1, 2, 3]}).encode()))
    (meta / "broken.json.gz").write_bytes(b"not gzip at all")
    (meta / "venue").mkdir()
    (meta / "venue" / "AAAUSDT.json.gz").write_bytes(
        gzip.compress(b'{"maker": 0.0002}'))

    out = Path(td) / "inventory.json"
    inv = HI.ingest(src, out_path=out, quiet=True)

    print("— بررسی و بایگانی:")
    a = inv["klines"]["AAAUSDT_15m"]
    check("کندل ۱۵د با زمانِ میلی‌ثانیه شناخته شد",
          a["status"] == "OK" and a["rows"] == 200
          and abs(a["step_min"] - 15) < 0.1, str(a))
    check("بازهٔ تاریخ از خود داده درآمده (۲۰۲۳)", a["t0"].startswith("2023"))
    b = inv["klines"]["BBBUSDT_1h"]
    check("زمانِ ثانیه‌ای هم شناخته می‌شود (۱س)",
          b["status"] == "OK" and abs(b["step_min"] - 60) < 0.1, str(b))
    check("قیمتِ بی‌معنا (high<low) = UNKNOWN، نه پذیرش",
          inv["klines"]["CCCUSDT_5m"]["status"] == "UNKNOWN_FORMAT")
    check("بایتِ آشغال = UNKNOWN، نه crash",
          inv["klines"]["junk_?"]["status"] == "UNKNOWN_FORMAT")
    check("خلاصه درست می‌شمارد",
          inv["summary"]["klines_ok"] == 2
          and inv["summary"]["klines_unknown"] == 2, str(inv["summary"]))

    print("\n— متا:")
    check("universe.json خوانده شد", inv["meta"]["universe.json"]["ok"])
    check("gz فشرده باز و کلیدهایش ثبت شد",
          inv["meta"]["dominance.json.gz"]["ok"]
          and "points" in inv["meta"]["dominance.json.gz"]["keys"])
    check("فایل خراب صادقانه error می‌گیرد، نه سکوت",
          inv["meta"]["broken.json.gz"]["ok"] is False)
    check("پوشهٔ صرافی شمرده شد",
          inv["meta"]["venue/"]["files"] == 1
          and inv["meta"]["venue/"]["readable"] == 1)

    print("\n— قرارداد قانون ۰۳:")
    check("شناسنامه retrieved_at و UNVERIFIED دارد",
          inv["validation_status"] == "UNVERIFIED"
          and inv["retrieved_at"].endswith("Z"))
    check("مرز روی خود شناسنامه نوشته شده (قانون ۰۳)",
          "قانون ۰۳" in inv["note"])

    print("\n— درِ دسترسی اتاق تاریخچه:")
    ks = HI.load_klines("AAAUSDT", "15m", inventory_path=out, limit=5)
    check("کندل‌ها عین داده برمی‌گردند",
          len(ks) == 5 and ks[0]["t"] == T0
          and abs(ks[0]["o"] - 100.0) < 1e-9
          and abs(ks[4]["c"] - 100.45) < 1e-9, str(ks[:1]))
    check("گام زمانی درست است", ks[1]["t"] - ks[0]["t"] == 15 * 60_000)
    check("فایل UNKNOWN از این در رد نمی‌شود",
          HI.load_klines("CCCUSDT", "5m", inventory_path=out) is None)
    check("نمادِ ناموجود None است، نه خطا",
          HI.load_klines("XUSDT", "1m", inventory_path=out) is None)

    check("پوشهٔ ناموجود = error ثبت‌شده، نه crash",
          HI.ingest(Path(td) / "nope", out_path=Path(td) / "i2.json",
                    quiet=True)["errors"])

print("\n— مرزها روی کد:")
src_txt = (HERE / "history_ingest.py").read_text(encoding="utf-8")
check("اسکریپت هیچ git add/commit/push ندارد (داده در گیت نمی‌رود)",
      "git" not in src_txt.replace("گیت", ""))
check("هیچ تلگرامی نمی‌فرستد", "TELEGRAM" not in src_txt
      and "urlopen" not in src_txt)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان تحویل تاریخچه: هر {OK} بررسی سبز")
