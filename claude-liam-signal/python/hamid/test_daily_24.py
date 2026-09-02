"""پاسبان سقف ۲۴ سیگنال در روز + حساسیت تاریخی به بیت‌کوین (۲۹ اوت).

دستور حمید: «ارسال سیگنال در روز را به روزی ۲۴ سیگنال افزایش بده، با
همین روشی که الان داری انجام می‌دهی. فقط هیچ تغییری در روش تحلیل ایجاد
نشود… ارزها حتماً با گذشتهٔ بیت‌کوین لگ-کورولیشن شوند… اگر نسبت به رفتار
بیت‌کوین بی‌تفاوت بوده، در امتیازی که برای سیگنال‌شدنش می‌دهی تجدید نظر
کن… تاریخچه باید یکی از چندین پارامتری باشد که تحلیل را تأیید یا رد
می‌کند.»

دو خطر که این آزمون می‌بندد:
۱. نردبان آن‌قدر تند باشد که قبل از ۲۴ عملاً ببندد (عیبِ اندازه‌گیری‌شده:
   با شیب قبلی، ارسال دوازدهم کفِ اطمینان ۴۸٪ می‌خواست).
۲. حساسیت به BTC تبدیل به دروازه شود یا نبودِ داده «مستقل» خوانده شود.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

import telegram as tg                                 # noqa: E402
import liam9_strategy as S                            # noqa: E402
from hamid import btc_sensitivity as BS               # noqa: E402

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


# ── ۱. سقف روزانه واقعاً ۲۴ است ───────────────────────────────────────────
check("سقف روزانه ۲۴ اعلام شده", tg.DAILY_CAP == 24, str(tg.DAILY_CAP))

now = time.time() * 1000
sent23 = {f"ibs|C{i}USDT|15m|LONG": now - i * 60000 for i in range(23)}
check("۲۳ ارسال در ۲۴ ساعت درست شمرده می‌شود",
      tg._sent_in(sent23, 24) == 23, str(tg._sent_in(sent23, 24)))
noise = dict(sent23, **{"any|X|15m|LONG": now, "skip|y": now, "pair|Z|LONG": now})
check("کلیدهای کمکی در شمارش سقف حساب نمی‌شوند",
      tg._sent_in(noise, 24) == 23, str(tg._sent_in(noise, 24)))
old = {f"ibs|D{i}USDT|5m|SHORT": now - (25 + i) * 3600 * 1000 for i in range(9)}
check("ارسال‌های کهنه‌تر از ۲۴ ساعت سقف امروز را نمی‌بندند",
      tg._sent_in(old, 24) == 0, str(tg._sent_in(old, 24)))

# ── ۱ب. سقف باید ۲۴ ساعتِ کامل را ببیند، نه فقط حافظهٔ ۶ساعته ────────────
# عیبِ اندازه‌گیری‌شدهٔ ۲ سپتامبر: ۳۳ ارسال یکتا در ۲۴ ساعت با سقف ۲۴.
# حافظهٔ ضدتکرار هر کلید را TTL_MS (۶ ساعت) نگه می‌دارد؛ سقفی که از آن
# می‌شمرد، هر ۶ ساعت از نو ۲۴ می‌داد. این بخش همان مسیر واقعی را می‌رود:
# دیسک → _load_sent (هرس) → شمارش، در کنار آرشیو ۲۴ساعته.
import inspect                                        # noqa: E402

H = 3600 * 1000
_tmp = Path(tempfile.mkdtemp(prefix="daily24-"))
_saved = {k: getattr(tg, k) for k in ("ARCHIVE_DIR", "SENT", "SIDECAR", "TGLOG", "_remote_log_rows")}
try:
    tg.ARCHIVE_DIR = _tmp / "archive"
    tg.SENT = _tmp / "sent.json"
    tg.SIDECAR = _tmp / "sidecar.json"
    tg.TGLOG = _tmp / "telegram-log.json"
    tg._remote_log_rows = lambda: []
    tg.ARCHIVE_DIR.mkdir()

    def _day(ms):
        return time.strftime("%Y%m%d", time.gmtime(ms / 1000))

    def _row(i, at):
        return json.dumps({"n": i, "at": int(at), "sym": f"C{i}USDT", "tf": "5m",
                           "dir": "LONG", "tg_msg_id": 5000 + i}) + "\n"

    rows = {}
    # ۲۰ ارسال بین ۲۰ تا ۸ ساعت پیش (بیرون از حافظهٔ ۶ساعته، داخل ۲۴ ساعت)
    for i in range(20):
        at = now - (20 - i * 0.6) * H
        rows.setdefault(_day(at), []).append(_row(i, at))
    # ۱۲ ارسال در ۵ ساعت اخیر (داخل حافظه)
    for i in range(20, 32):
        at = now - (5 - (i - 20) * 0.3) * H
        rows.setdefault(_day(at), []).append(_row(i, at))
    # یک ردیفِ تکراری (همان tg_msg_id) و یک ردیفِ ۳۰ساعته — هیچ‌کدام نباید بشمرد
    rows.setdefault(_day(now - 1 * H), []).append(_row(31, now - 1 * H))
    rows.setdefault(_day(now - 30 * H), []).append(_row(99, now - 30 * H))
    for day, lines in rows.items():
        (tg.ARCHIVE_DIR / f"telegram-sent-{day}.jsonl").write_text("".join(lines))

    # حافظهٔ روی دیسک: همان ۳۲ ارسال به شکل کلید واقعی
    disk = {f"ibs|C{i}USDT|5m|LONG": now - (20 - i * 0.6) * H for i in range(20)}
    disk.update({f"ibs|C{i}USDT|5m|LONG": now - (5 - (i - 20) * 0.3) * H for i in range(20, 32)})
    tg.SENT.write_text(json.dumps(disk))

    loaded = tg._load_sent()
    check("حافظهٔ ضدتکرار بعد از بارگذاری فقط ۶ ساعت را نگه می‌دارد (عیبِ ریشه، مستند)",
          tg._sent_in(loaded, 24) == 12, str(tg._sent_in(loaded, 24)))
    check("آرشیو ۲۴ساعته هر ۳۲ ارسال یکتا را می‌شمرد (تکراری و ۳۰ساعته نه)",
          tg._archive_sent_in(24, now) == 32, str(tg._archive_sent_in(24, now)))
    check("شمارِ سقف روزانه = ۳۲ → سقف ۲۴ واقعاً می‌بندد",
          tg._sent_in_24h(loaded) >= tg.DAILY_CAP, str(tg._sent_in_24h(loaded)))
    check("آرشیو خالی → شمارش صفر، نه خطا",
          (lambda d: (setattr(tg, "ARCHIVE_DIR", d), tg._archive_sent_in(24))[1])(_tmp / "none") == 0)
    src = inspect.getsource(tg.send_signals)
    check("گلوگاه ارسال از شمارندهٔ ۲۴ساعته می‌خواند، نه از حافظهٔ هرس‌شده",
          "_sent_in_24h(" in src and "_sent_in(sent, 24)" not in src)
    check("تا وقتی حافظه کمتر از ۲۴ ساعت یاد دارد، منبعِ دوم اجباری است",
          tg.TTL_MS >= 24 * H or "_archive_sent_in" in inspect.getsource(tg._sent_in_24h))
finally:
    for k, v in _saved.items():
        setattr(tg, k, v)

# ── ۲. نردبان تا ۲۴ باز می‌ماند، نه اینکه وسط راه ببندد ──────────────────
b12 = tg.ladder_bar(12)
b24 = tg.ladder_bar(24)
check("در ارسال دوازدهم کف اطمینان زیر ۳۰٪ است (قبلاً ۴۸٪ بود)",
      b12["min_conf"] < 30, f"min_conf={b12['min_conf']}")
check("در ارسال دوازدهم کف انتظار زیر ۰.۳۵R است",
      b12["min_ev"] < 0.35, f"min_ev={b12['min_ev']}")
check("نردبان در ۲۴ هنوز سقفِ خودش را نزده (در بسته نمی‌شود)",
      b24["min_conf"] <= tg.LADDER_CONF_MAX and b24["min_conf"] < 72,
      f"min_conf={b24['min_conf']}")
check("پنج سیگنال اول بی‌آستانه می‌مانند (روش ۲۷ اوت دست‌نخورده)",
      tg.ladder_bar(4)["step"] == 0 and tg.ladder_bar(5)["step"] == 1)
strong = {"conf": 40, "ev": 0.5}
check("ستاپ قوی در پلهٔ دوازدهم هنوز رد می‌شود", tg.passes_ladder(strong, b12))

# ── ۳. حساسیت BTC: کلاس از اجماع چند تایم می‌آید ─────────────────────────
mk = lambda tf, r, n=300: {"tf": tf, "r": r, "abs_r": abs(r), "lag_bars": 1, "n": n}
check("دو تایمِ قوی → COUPLED",
      BS.classify([mk("15m", 0.31), mk("1h", 0.27), mk("4h", 0.05)])["klass"] == "COUPLED")
check("همهٔ تایم‌ها ضعیف → INDEPENDENT (موردِ ترامپ)",
      BS.classify([mk("15m", 0.04), mk("1h", -0.06), mk("4h", 0.02)])["klass"] == "INDEPENDENT")
check("یک تایمِ تنها حکم نمی‌دهد → UNKNOWN",
      BS.classify([mk("1h", 0.9)])["klass"] == "UNKNOWN")
check("شواهد ناهمخوان → UNKNOWN، نه حدس",
      BS.classify([mk("15m", 0.35), mk("1h", 0.12), mk("4h", 0.14)])["klass"] == "UNKNOWN")
check("همبستگیِ منفیِ قوی هم «واکنش» است، نه بی‌تفاوتی",
      BS.classify([mk("15m", -0.33), mk("1h", -0.29)])["klass"] == "COUPLED")

# ── ۴. اثرِ کلاس روی امتیاز: کاهش وزن، نه وتو ────────────────────────────
old_book = S.BTC_SENS
try:
    S.BTC_SENS = {"generated": int(now), "coins": {
        "TRUMPUSDT": {"klass": "INDEPENDENT", "at": int(now)},
        "ETHUSDT": {"klass": "COUPLED", "at": int(now)},
        "OLDUSDT": {"klass": "INDEPENDENT", "at": int(now - 40 * 3600 * 1000)}}}
    check("نمادِ مستقل سهمِ بسترِ BTC را نصف می‌گیرد",
          S.btc_ctx_weight("TRUMPUSDT") == 0.5, str(S.btc_ctx_weight("TRUMPUSDT")))
    check("نمادِ همبسته وزن کامل دارد", S.btc_ctx_weight("ETHUSDT") == 1.0)
    check("نمادِ ناشناس وزن کامل دارد — «نمی‌دانم» تنبیه نمی‌شود",
          S.btc_ctx_weight("SOMENEWUSDT") == 1.0)
    check("کلاسِ کهنه‌تر از ۲۴ ساعت بی‌اثر می‌شود",
          S.btc_klass("OLDUSDT") == "UNKNOWN" and S.btc_ctx_weight("OLDUSDT") == 1.0)
    check("ضریب هرگز صفر نیست — این شاهد است نه دروازه",
          all(S.btc_ctx_weight(x) > 0 for x in
              ("TRUMPUSDT", "ETHUSDT", "OLDUSDT", "ZZZUSDT")))
finally:
    S.BTC_SENS = old_book

# ── ۵. سیم‌کشی و قرارداد (قانون ۱۳) ──────────────────────────────────────
reg = json.loads((PY.parents[1] / "config" / "state_registry.json").read_text(encoding="utf-8"))
check("btc-sensitivity.json در قرارداد وضعیت ثبت است",
      "btc-sensitivity.json" in reg["files"])
check("داشبورد حساسیت را در sync_all می‌کشد",
      "btc_sensitivity" in (PY / "liam9_strategy.py").read_text(encoding="utf-8"))
check("خروجی موتور بستهٔ شواهد کامل دارد (قانون ۱۲)",
      __import__("hamid.evidence_packet", fromlist=["x"]).validate(
          BS.packet({"coins": {"A": {"klass": "COUPLED"}}})) == [])

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
