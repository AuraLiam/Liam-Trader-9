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


# ── سفارش‌های لیمیتِ پرنشده (دستور حمید، ۲۴ اوت) ────────────────────────
print("\n— لیمیتِ منتظر و لیمیتِ منقضی:")
NOW = 1_700_000_000_000
MIN = 60_000


def pend(tf, age_min, filled=None, sym="X"):
    return {"sym": sym, "dir": "LONG", "tf": tf, "entry": 100.0, "sl": 99.0,
            "opened": NOW - age_min * MIN, "filled": filled}


exp, wait = PW.scan_pending([pend("1m", 10), pend("1m", 60)], now_ms=NOW)
check("لیمیت ۱د بعد از ۴۵ دقیقه منقضی است", len(exp) == 1 and exp[0]["over_by_min"] == 15,
      str(exp))
check("و لیمیتِ ۱۰ دقیقه‌ای هنوز معتبر است", len(wait) == 1)

exp, wait = PW.scan_pending([pend("15m", 100), pend("15m", 800)], now_ms=NOW)
check("مهلت لیمیت با تایم‌فریم بزرگ‌تر می‌شود (۱۵د = ۷۲۰د)",
      len(exp) == 1 and len(wait) == 1, str(exp))

from hamid import paper as P                                # noqa: E402
check("سقف مطلق از paper.FILL_HOURS می‌آید، نه عددِ جادوییِ تازه",
      PW._fill_cap_min("1h") == min(PW.max_hold_for("1h"), P.FILL_HOURS * 60),
      f"{PW._fill_cap_min('1h')}")

# مرزِ بین دو پاسبان — همان عیبی که ۲۴ اوت بسته شد
rows = [pend("1m", 500, filled=NOW - 500 * MIN, sym="FILLED"),
        pend("1m", 500, sym="PENDING")]
stale, _ = PW.scan(rows, now_ms=NOW)
exp, _ = PW.scan_pending(rows, now_ms=NOW)
check("پوزیشنِ پرشده فقط در scan شمرده می‌شود",
      [s["sym"] for s in stale] == ["FILLED"], str(stale))
check("و لیمیتِ پرنشده فقط در scan_pending — نه در هر دو",
      [e["sym"] for e in exp] == ["PENDING"], str(exp))
check("لیمیتِ پرنشده دیگر «پوزیشن باز» جا زده نمی‌شود",
      all(s["sym"] != "PENDING" for s in stale))
check("ردیف بدون opened نادیده گرفته می‌شود، نه خطا",
      PW.scan_pending([{"sym": "Y", "tf": "1m"}], now_ms=NOW) == ([], []))

# خروجی و آلارم
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "open.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    _out = PW.OUT
    PW.OUT = Path(td) / "position-watch.json"
    try:
        res = PW.run(quiet=True, path=str(p), now_ms=NOW)
        disk = json.loads(PW.OUT.read_text(encoding="utf-8"))
        empty = Path(td) / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        clean = PW.run(quiet=True, path=str(empty), now_ms=NOW)
    finally:
        PW.OUT = _out
check("خروجی هر دو مشکل را جدا گزارش می‌کند",
      res["expired_pending"] and res["stale"], str(res["verdict"]))
check("و حکمش هر دو را نام می‌برد",
      "پوزیشن" in res["verdict"] and "لیمیت" in res["verdict"], res["verdict"])
check("فایل روی دیسک همان را دارد", disk["pending_total"] == 1)
check("دفتر خالی حکمِ سلامت می‌گیرد، نه آلارمِ الکی",
      "نداریم" in clean["verdict"] and not clean["expired_pending"],
      clean["verdict"])
check("مرز اجرای زنده روی خروجی نوشته شده",
      "اجرای زنده" in res["note"] and "لغو سفارش" in res["note"])

src = (Path(__file__).resolve().parent / "position_watch.py").read_text(encoding="utf-8")
check("آلارم لیمیت کلیدِ جدا دارد (رفعِ یکی، سلامتیِ دیگری را اعلام نکند)",
      '"pending_limits"' in src and "limit:" in src)
check("و مثل بقیه از دروازهٔ alert_gate رد می‌شود",
      src.count("alert_gate.send") == 2, str(src.count("alert_gate.send")))

# ── سیل ۱۲۴پیامیِ ۲۴ اوت — کلاسِ عیب: پیامِ بی‌مخاطب ───────────────────
print("\n— فقط سفارشِ فرستاده‌شده برای حمید پیام می‌گیرد:")


def pend2(stage, sym="X", age_min=5000):
    return {"sym": sym, "dir": "LONG", "tf": "1m", "entry": 1.0, "sl": 0.9,
            "opened": NOW - age_min * MIN, "filled": None,
            "why": {"stage": stage}}


exp, _ = PW.scan_pending([pend2("sig-ibs", "A"), pend2("practice", "B"),
                          pend2("first", "C"), pend2("vetoed", "D")],
                         now_ms=NOW)
check("همه در خروجی JSON شمرده می‌شوند (پنهان‌کاری نه)", len(exp) == 4)
check("ولی فقط sig-* برچسب «فرستاده برای حمید» دارد",
      [e["sym"] for e in exp if e["sent_to_hamid"]] == ["A"], str(exp))
check("و آلارم فقط همان‌ها را می‌فرستد (فیلتر در کد)",
      'd_.get("sent_to_hamid")' in src)
dup_rows = [pend2("practice", "E"), pend2("practice", "E")]
check("نسخهٔ تکراریِ همان سفارش یک بار شمرده می‌شود",
      len(PW.scan_pending(dup_rows, now_ms=NOW)[0]) == 1)
f1 = pend2("practice", "F")
f1["filled"] = NOW - 5000 * MIN
check("پوزیشنِ پرشدهٔ تکراری هم در scan یک بار می‌آید",
      len(PW.scan([f1, dict(f1)], now_ms=NOW)[0]) == 1)
check("مهلت لیمیت همان قاعدهٔ خودِ دفتر است (paper.pending_valid_min)",
      all(PW._fill_cap_min(tf) == P.pending_valid_min(tf)
          for tf in ("1m", "5m", "15m", "1h", None)))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبانِ پاسبان پوزیشن: هر {OK} بررسی سبز")
