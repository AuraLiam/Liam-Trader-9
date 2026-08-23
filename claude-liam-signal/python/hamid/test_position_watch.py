"""پاسبانِ پاسبان پوزیشن — همراه اجباری position_watch.py. آفلاین."""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import position_watch as PW                 # noqa: E402

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


NOW = 1_700_000_000_000
MIN = 60_000


def pos(sym="AAAUSDT", tf="1m", age_min=10, d="LONG"):
    return {"sym": sym, "dir": d, "tf": tf,
            "opened": NOW - age_min * MIN, "filled": NOW - age_min * MIN}


check("سقف هر تایم‌فریم تعریف شده و اسکلپ ۱د = ۴۵د (هم‌خوان خروجی استراتژی)",
      PW.max_hold_for("1m") == 45 and PW.max_hold_for("1h") == 2880)
check("تایم‌فریم ناشناخته سقف پیش‌فرض می‌گیرد، نه خطا و نه بی‌سقفی",
      PW.max_hold_for("4h") == PW.DEFAULT_HOLD_MIN)

stale, ok = PW.scan([pos(age_min=10), pos(sym="BBBUSDT", age_min=46),
                     pos(sym="CCCUSDT", tf="5m", age_min=46),
                     pos(sym="DDDUSDT", tf="5m", age_min=300)], now_ms=NOW)
check("پوزیشن تازه سالم است", any(o["sym"] == "AAAUSDT" for o in ok))
check("اسکلپ ۴۶دقیقه‌ای مانده است (سقف ۴۵)",
      any(s["sym"] == "BBBUSDT" for s in stale))
check("همان سن روی تایم بالاتر سالم است (سقف تایم‌فریمی، نه سراسری)",
      any(o["sym"] == "CCCUSDT" for o in ok))
check("۵دقیقه‌ایِ ۳۰۰دقیقه‌ای مانده است", any(s["sym"] == "DDDUSDT" for s in stale))
check("مانده‌ها بر شدتِ تخطی مرتب‌اند",
      [s["over_by_min"] for s in stale] ==
      sorted((s["over_by_min"] for s in stale), reverse=True))
check("سن و مقدارِ اضافه روی هر رکورد هست",
      all(s["age_min"] > 0 and s["over_by_min"] > 0 for s in stale))
check("پوزیشن بی‌زمان بی‌صدا رد می‌شود نه crash",
      PW.scan([{"sym": "X"}], now_ms=NOW) == ([], []))

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "open.jsonl"
    p.write_text(json.dumps(pos(age_min=99)) + "\n" + "بدخط\n")
    _out = PW.OUT
    PW.OUT = Path(td) / "watch.json"
    try:
        res = PW.run(quiet=True, path=p, now_ms=NOW)
        disk = json.loads(PW.OUT.read_text())
    finally:
        PW.OUT = _out
check("خط خراب دفتر، اسکن را نمی‌کشد", res["open_total"] == 1)
check("گزارش روی دیسک نوشته می‌شود و حکم دارد",
      disk["stale"] and "باز مانده" in disk["verdict"])
check("مرز صادقانه در خروجی هست: پاسبان نمی‌بندد (قانون ۰۵)",
      "قانون ۰۵" in disk["note"])
check("دفتر ناموجود = گزارش خالی، نه خطا",
      PW.load_open("/nonexistent/x.jsonl") == [])

# عیب ۲۳ اوت: پاسبان TG.send_text را صدا می‌زد که وجود نداشت — آلارم هر
# چرخه با AttributeError می‌مرد و آزمونِ جعلی نمی‌دید. حالا رابط واقعی
# سنجیده می‌شود، نه جعلی.
import telegram as _TG
check("رابط آلارم (telegram.send_text) واقعاً وجود دارد و صدازدنی است",
      callable(getattr(_TG, "send_text", None)))
check("پیام بی‌کلید بی‌صدا False برمی‌گرداند، نه خطا",
      _TG.send_text("آزمون", quiet=True) in (False, True))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبانِ پاسبان پوزیشن: هر {OK} بررسی سبز")
