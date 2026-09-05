"""پاسبان ضدتکرار سه‌منبعی + دروازهٔ تایم‌فریم (رفع ریشه‌ای ۲۶ اوت شب).

عیب سنجیده‌شده: PAXGUSDT SHORT 5m با ورودی یکسان ۵ بار در ۲۱ دقیقه رفت
(۲۰:۲۸ تا ۲۰:۴۹) چون حافظهٔ ضدتکرار فقط روی sent.jsonِ گیت بود و از
۲۰:۱۲ تا ۲۱:۰۱ هیچ push روی main ننشست — هر دورِ زنجیره با reset به
حافظهٔ کهنه برمی‌گشت و دوباره می‌فرستاد.

رفع سه‌لایه که این آزمون قفلش می‌کند:
۱. حافظهٔ کناری /tmp (SIDECAR) مستقل از گیت، در هر دورِ رانر زنده.
۲. ذخیرهٔ فوری بعد از هر ارسال (_save_sent داخل حلقه)، نه فقط انتهای تابع.
۳. بازسازی کلید any| از خود telegram-log — سومین منبع حقیقت.
+ دروازهٔ تایم‌فریم: ارسال فقط 5m/15m (دستور صریح حمید، ۲۶ اوت شب).
+ آرشیو شماره‌دار append-only (دستور «اطلاعات را یکی نکن؛ شماره‌گذاری کن»).
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

import telegram as TG                                # noqa: E402

import pathlib

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


import tempfile                                      # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="tg-dedupe-"))
now = time.time() * 1000

old = (TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR)
TG.SENT = TMP / "sent.json"
TG.SIDECAR = TMP / "sidecar.json"
TG.TGLOG = TMP / "tglog.json"
TG.ARCHIVE_DIR = TMP / "archive"

try:
    # ── ۱) اجتماع سه‌منبعی ─────────────────────────────────────────────
    TG.SENT.write_text(json.dumps({"ibs|AAAUSDT|15m|LONG": now - 1000}))
    TG.SIDECAR.write_text(json.dumps({"ibs|PAXGUSDT|5m|SHORT": now - 2000,
                                      "ibs|AAAUSDT|15m|LONG": now - 500}))
    TG.TGLOG.write_text(json.dumps({"sent": [
        {"sym": "CCCUSDT", "tf": "15m", "dir": "LONG", "at": now - 3000},
        {"sym": "OLDUSDT", "tf": "15m", "dir": "LONG",
         "at": now - 13 * 3600 * 1000},
    ]}))
    loaded = TG._load_sent()
    check("کلیدی که فقط در حافظهٔ کناری است دیده می‌شود (سناریوی PAXG)",
          "ibs|PAXGUSDT|5m|SHORT" in loaded, str(sorted(loaded)))
    check("در تعارض دیسک/کناری، تازه‌ترین زمان برنده است",
          loaded.get("ibs|AAAUSDT|15m|LONG") == now - 500)
    check("ردیف لاگ ارسال، کلید any| را بازمی‌سازد (منبع سوم)",
          "any|CCCUSDT|15m|LONG" in loaded)
    check("ردیف لاگ کهنه‌تر از ۱۲ ساعت بازسازی نمی‌شود",
          "any|OLDUSDT|15m|LONG" not in loaded)

    # ── ۲) ذخیرهٔ دوخانه‌ای ────────────────────────────────────────────
    TG._save_sent({"k1": now})
    check("ذخیره در هر دو خانه می‌نشیند (دیسک + کناری)",
          json.loads(TG.SENT.read_text()) == {"k1": now}
          and json.loads(TG.SIDECAR.read_text()) == {"k1": now})

    # ── ۳) آرشیو شماره‌دار append-only ─────────────────────────────────
    TG._archive_sent({"sym": "XUSDT", "tf": "5m", "dir": "LONG",
                      "entry": 1.0, "sl": 0.9, "tp1": 1.2, "strategy": "ibs"})
    TG._archive_sent({"sym": "YUSDT", "tf": "15m", "dir": "SHORT",
                      "entry": 2.0, "sl": 2.2, "tp1": 1.7, "strategy": "ibs"})
    day = time.strftime("%Y%m%d", time.gmtime())
    arc = TG.ARCHIVE_DIR / f"telegram-sent-{day}.jsonl"
    rows = [json.loads(x) for x in arc.read_text().splitlines()]
    check("آرشیو append-only است و شماره‌های پیاپی دارد",
          [r["n"] for r in rows] == [1, 2], str(rows))
    check("ردیف آرشیو هویت کامل معامله را دارد",
          rows[0]["sym"] == "XUSDT" and rows[0]["tp1"] == 1.2)

    # ── ۴) دروازهٔ تایم‌فریم در گلوگاه ارسال ───────────────────────────
    check("فقط ۵د و ۱۵د مجازند (دستور ۲۶ اوت)",
          TG.ALLOWED_TFS == {"5m", "15m"})
    calls = []
    old_post, old_creds = TG._post, TG.creds
    TG._post = lambda *a, **k: calls.append(a) or {"result": {"message_id": 1}}
    TG.creds = lambda: ("tok", "chat")
    try:
        n = TG.send_signals(
            [{"sym": "ZUSDT", "tf": "1h", "dir": "LONG", "strategy": "ibs",
              "entry": 1, "sl": 0.9, "tp1": 1.3},
             {"sym": "WUSDT", "tf": "4h", "dir": "SHORT", "strategy": "ibs",
              "entry": 1, "sl": 1.1, "tp1": 0.7}],
            lambda s, p: None)
    finally:
        TG._post, TG.creds = old_post, old_creds
    check("سیگنال ۱س/۴س در گلوگاه رد می‌شود و هیچ ارسالی نمی‌رود",
          n == 0 and not calls, f"n={n} calls={len(calls)}")

    # ── ۵) کلاس عیب: ذخیرهٔ فوری داخل حلقه، نه فقط انتها ───────────────
    src = (PY / "telegram.py").read_text(encoding="utf-8")
    # از اولین مهرِ ضدتکرار تا انتهای حلقهٔ ارسال
    loop_after_send = src.split('sent[f"any|', 1)[1].split("_save_sent(sent)\n    print", 1)[0]
    check("بعد از هر ارسال، همان لحظه ذخیره می‌شود (_save_sent داخل حلقه)",
          "_save_sent(sent)" in loop_after_send, loop_after_send[:120])
    check("هیچ نوشتن مستقیم SENT.write_text بیرون از _save_sent نیست",
          src.count("SENT.write_text") == 1)
    check("آرشیو در مسیر ارسال صدا زده می‌شود",
          "_archive_sent(s)" in loop_after_send)
finally:
    TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR = old

# ── ۵.۳) ضدتکرار بین‌تایم‌فریمی — «یه سیگنال رو داری چندین بار میفرستی» ──
#
# عیب اندازه‌گیری‌شده (آرشیو ۲۷ اوت): TRX شورت ۵د ساعت ۰۵:۱۸ و همان TRX
# شورت ۱۵د سه دقیقه بعد؛ ZEC لانگ ۵د ۱۷:۲۰ و ۱۵د ۲۸ دقیقه بعد. کلیدهای
# قبلی همه tf داشتند، پس «همان معامله روی تایم دیگر» تازه حساب می‌شد.
old2 = (TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR)
TG.SENT = TMP / "sent-pair.json"
TG.SIDECAR = TMP / "sidecar-pair.json"
TG.TGLOG = TMP / "tglog-pair.json"
TG.ARCHIVE_DIR = TMP / "archive-pair"
try:
    # TRX شورت ۱۵د همین الان رفته — همان TRX شورت روی ۵د نباید برود
    TG.SENT.write_text(json.dumps({
        "ibs|TRXUSDT|15m|SHORT": now,
        "any|TRXUSDT|15m|SHORT": now,
        "pair|TRXUSDT|SHORT": now}))
    calls2 = []
    op2, oc2 = TG._post, TG.creds
    TG._post = lambda *a, **k: calls2.append(a) or {"result": {"message_id": 9}}
    TG.creds = lambda: ("tok", "chat")
    try:
        n2 = TG.send_signals(
            [{"sym": "TRXUSDT", "tf": "5m", "dir": "SHORT", "strategy": "ibs",
              "entry": 0.336, "sl": 0.339, "tp1": 0.331}],
            lambda s, p: None)
    finally:
        TG._post, TG.creds = op2, oc2
    check("همان (ارز، جهت) روی تایم‌فریم دیگر تا ۳ ساعت نمی‌رود",
          n2 == 0 and not calls2, f"n={n2} calls={len(calls2)}")
    # جهتِ مخالف همان ارز مستقل است — نباید قربانی این کلید شود
    TG.SENT.write_text(json.dumps({"pair|TRXUSDT|SHORT": now}))
    s_long = {"sym": "TRXUSDT", "tf": "5m", "dir": "LONG", "strategy": "ibs"}
    loaded2 = TG._load_sent()
    check("جهت مخالف همان ارز با کلید جفت بسته نمی‌شود",
          now - loaded2.get("pair|TRXUSDT|LONG", 0) >= 3 * 3600 * 1000)
    src_p = (PY / "telegram.py").read_text(encoding="utf-8")
    check("کلید جفت در هر دو نقطهٔ ثبتِ ارسال نوشته می‌شود",
          src_p.count('sent[f"pair|{s[\'sym\']}|{s[\'dir\']}"]') == 2,
          str(src_p.count('sent[f"pair|{s[\'sym\']}|{s[\'dir\']}"]')))
    check("سقف هر ارز به ۲ برگشت (سقف ۳ همان بود که PAXG دوم را رد کرد)",
          ">= 2" in src_p.split("def _sym_worn", 1)[1][:600])

    # ── ۵.۳۱) رزروِ درون-دسته — عیب اندازه‌گیری‌شدهٔ ۱ سپتامبر ──────────
    #
    # همان کلاسِ بالا، ولی از درِ دیگر: کلید `pair|` فقط بین **اجراها**
    # کار می‌کرد. فیلترِ ورودی یک list-comprehension بود و همهٔ ستاپ‌ها
    # را روی یک عکسِ منجمدِ `sent` می‌سنجید، پس دو ستاپ از یک (ارز، جهت)
    # روی دو تایم در **همان دسته** هر دو رد می‌شدند — نوشتنِ کلید بعد از
    # فیلتر اتفاق می‌افتاد. شاهد: BTCUSDT لانگ ۵د ۰۷:۲۷:۵۸ و لانگ ۱۵د
    # ۰۷:۲۸:۱۶ (۱۸ ثانیه) در دفتر ارسالِ ۳۱ اوت.
    # سنجه، تعدادِ **ردشده از فیلتر** است نه تعدادِ تحویل‌شده: تحویل به
    # قیمت زنده و دروازهٔ روند نیاز دارد و در آزمون شبکه‌ای نیست. خودِ
    # فرستنده تعداد را چاپ می‌کند («… of N new signals delivered»).
    import contextlib
    import io
    import re as _re

    def _passed_filter(sigs):
        # حافظهٔ کناری هم پاک شود: ستاپی که دروازه ردش می‌کند مهرِ
        # `skip|` می‌گیرد و تا ۳۰ دقیقه دوباره بررسی نمی‌شود. بدون این
        # پاک‌سازی، فراخوانِ بعدیِ همین آزمون قربانیِ مهرِ قبلی می‌شد.
        TG.SENT.write_text("{}")
        TG.TGLOG.write_text("{}")
        TG.SIDECAR.write_text("{}")
        op, oc = TG._post, TG.creds
        TG._post = lambda *a, **k: {"result": {"message_id": 7}}
        TG.creds = lambda: ("tok", "chat")
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                TG.send_signals(sigs, lambda s, p: None)
        finally:
            TG._post, TG.creds = op, oc
        m = _re.search(r"of (\d+) new signals", buf.getvalue())
        return int(m.group(1)) if m else 0

    got3 = _passed_filter(
        [{"sym": "BTCUSDT", "tf": "5m", "dir": "LONG", "strategy": "ibs",
          "entry": 100, "sl": 99, "tp1": 103},
         {"sym": "BTCUSDT", "tf": "15m", "dir": "LONG", "strategy": "ibs",
          "entry": 100, "sl": 99, "tp1": 103}])
    check("همان (ارز، جهت) روی دو تایم در یک دسته فقط یک بار رد می‌شود",
          got3 == 1, f"{got3} تا از فیلتر رد شد — رزروِ درون-دسته کار نکرد")

    # ارزِ دیگر و جهتِ مخالف نباید قربانی رزرو شوند
    got4 = _passed_filter(
        [{"sym": "BTCUSDT", "tf": "5m", "dir": "LONG", "strategy": "ibs",
          "entry": 100, "sl": 99, "tp1": 103},
         {"sym": "ETHUSDT", "tf": "5m", "dir": "LONG", "strategy": "ibs",
          "entry": 50, "sl": 49, "tp1": 53}])
    check("رزرو فقط همان (ارز، جهت) را می‌بندد، نه کلِ دسته را",
          got4 == 2, f"{got4} تا رد شد — ارزِ دیگر هم قربانی شد")
    got5 = _passed_filter(
        [{"sym": "BTCUSDT", "tf": "5m", "dir": "LONG", "strategy": "ibs",
          "entry": 100, "sl": 99, "tp1": 103},
         {"sym": "BTCUSDT", "tf": "5m", "dir": "SHORT", "strategy": "ibs",
          "entry": 100, "sl": 101, "tp1": 97}])
    check("جهتِ مخالف همان ارز در یک دسته مستقل می‌ماند",
          got5 == 2, f"{got5} تا رد شد")
    check("رزرو در دفترِ ماندگار نوشته نمی‌شود (ستاپِ نرفته خفه نشود)",
          "claim_any" in src_p and 'sent[f"any|' not in
          src_p.split("claim_any, claim_pair", 1)[1].split("fresh = []", 1)[0])
finally:
    TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR = old2

# ── ۵.۳۵) میز ۱ دقیقه: هیچ پیامی به تلگرام نمی‌فرستد (دستور ۲۷ اوت) ─────
_scalp_dir = PY / "hamid"
_offend = []
for _f in _scalp_dir.glob("scalp*.py"):
    _s = _f.read_text(encoding="utf-8")
    if ("alert_gate.send(" in _s or "send_text(" in _s
            or "_post(token" in _s or "sendMessage" in _s):
        _offend.append(_f.name)
check("هیچ ماژول اسکلپ/۱دقیقه‌ای به تلگرام نمی‌فرستد — فقط پیپرمود",
      not _offend, str(_offend))

# ── ۵.۴) سقف کپشن تلگرام — عیب اندازه‌گیری‌شدهٔ ۲۷ اوت ────────────────────
#
# «telegram rejected SOLUSDT: 400» و همان برای CRCLB، چند دور پیاپی.
# ریشه: کپشنِ سیگنالِ پرمحتوا ~۱۴۵۰ کاراکتر بود و سقف عکس در تلگرام
# ۱۰۲۴ است → تلگرام کل درخواست را رد می‌کرد و **باکیفیت‌ترین سیگنال‌ها
# (همان‌هایی که اطمینان و انتظار دارند) اصلاً تحویل نمی‌شدند.**
check("سقف‌ها همان عددهای خودِ تلگرام‌اند",
      TG.CAPTION_LIMIT == 1024 and TG.TEXT_LIMIT == 4096)
_long = "\n".join(f"<b>خط شمارهٔ {i}</b> با کمی متن اضافه برای طول"
                  for i in range(60))
_h, _t = TG._split_caption(_long)
check("کپشن بلند بریده می‌شود و سر زیر سقف می‌ماند",
      len(_h) <= TG.CAPTION_LIMIT and _t, f"head={len(_h)} tail={len(_t)}")
check("هیچ کاراکتری گم نمی‌شود (سر + دنباله = کل)",
      _h + "\n" + _t == _long)
check("برش روی مرز خط است — تگ HTML نصف نمی‌شود",
      _h.endswith("طول") and _t.startswith("<b>"), _h[-30:])
check("کپشن کوتاه دست‌نخورده می‌ماند و دنباله ندارد",
      TG._split_caption("یک خط کوتاه") == ("یک خط کوتاه", ""))
_one = "x" * 3000
_h1, _t1 = TG._split_caption(_one)
check("خطِ تکِ غول‌پیکر هم سیگنال را نمی‌کشد (برش سخت)",
      len(_h1) == TG.CAPTION_LIMIT and _t1)
src_c = (PY / "telegram.py").read_text(encoding="utf-8")
check("مسیر عکس، کپشن بریده می‌فرستد نه کپشن کامل",
      '"caption": head' in src_c and '"caption": caption(s)' not in src_c)
check("دنبالهٔ کپشن ریپلایِ همان پیام سیگنال می‌شود",
      '"reply_to_message_id": _mid' in src_c)
# شکستِ تحویل باید ردِ دائمی بگذارد — وگرنه «سیگنالِ گم‌شده» عیناً شبیه
# «ستاپی نبود» دیده می‌شود (همان چیزی که ۲۷ اوت پنهانش کرد)
TG.ARCHIVE_DIR = TMP / "archive2"
TG._log_delivery_fail({"sym": "SOLUSDT", "tf": "15m", "dir": "LONG",
                       "entry": 107.45, "strategy": "ibs"}, "HTTP 400")
_ff = TG.ARCHIVE_DIR / f"delivery-failures-{time.strftime('%Y%m%d', time.gmtime())}.jsonl"
_rows = [json.loads(x) for x in _ff.read_text().splitlines()]
check("شکست تحویل در آرشیو شماره‌دار ثبت می‌شود",
      _rows and _rows[0]["sym"] == "SOLUSDT" and _rows[0]["n"] == 1
      and "400" in _rows[0]["why"], str(_rows))
n_fail = sum(1 for ln in src_c.splitlines()
             if "_log_delivery_fail(s," in ln and not ln.startswith("def "))
# پنج مسیر شکست: HTTP · غیر HTTP · دنباله · استثنای ثبتِ دفتر · ثبتِ
# صفرردیف. دو تای آخر ۵ سپتامبر اضافه شدند — سه ارسال LOKAUSDT رفتند و
# هیچ ردیف دفتر نگرفتند، و چون `open_from` استثنا نداده بود (فقط ساکت
# صفر ردیف ساخت) هیچ‌جا ثبت نشد. عدد فقط بالا می‌رود؛ پایین‌آمدنش یعنی
# یک مسیرِ شکست دوباره بی‌صدا شده.
check("هر پنج مسیر خطا ثبت می‌کنند (هیچ شکستی بی‌صدا نیست)",
      n_fail >= 5, str(n_fail))
# شکستِ دنباله نباید سیگنالِ رفته را «نرفته» جا بزند — وگرنه دور بعد
# دوباره می‌رود (همان کلاسِ PAXG×۵). مهر ضدتکرار باید قبل از ارسال
# دنباله زده شود.
_i_mid = src_c.index("_mid = ((resp or {}).get(\"result\")")
_i_commit = src_c.index("sent[_key(s)] = _t")
_i_tail = src_c.index('"text": tail')
check("مهر ضدتکرار قبل از ارسال دنباله زده می‌شود",
      _i_mid < _i_commit < _i_tail,
      f"mid={_i_mid} commit={_i_commit} tail={_i_tail}")
check("شکست دنباله، سیگنال را نمی‌کشد (استثنا داخل خودش گرفته می‌شود)",
      "دنبالهٔ کپشن" in src_c and '_log_delivery_fail(s, f"tail' in src_c)
TG.ARCHIVE_DIR = old[3]

# ── ۵.۵) نردبان سخت‌گیری بعد از سیگنال پنجم (دستور حمید، ۲۷ اوت) ──────────
#
# «کاری به نرخ عادی ندارم؛ تا سیگنال هست باید بدهد، ولی بعد از پنجمی
#  ایجنت‌ها شرایط را سخت‌تر کنند.» یعنی: هیچ سقف عددی نباشد، ولی آستانه
#  پله‌پله بالا برود.
check("پنج سیگنال اول هیچ آستانهٔ اضافه‌ای ندارند",
      all(TG.ladder_bar(n)["step"] == 0 for n in range(0, 5)),
      str([TG.ladder_bar(n)["step"] for n in range(0, 6)]))
check("از ششمی به بعد پله شروع می‌شود", TG.ladder_bar(5)["step"] == 1
      and TG.ladder_bar(6)["step"] == 2)
check("هر پله آستانه را بالاتر می‌برد (اطمینان و انتظار)",
      TG.ladder_bar(8)["min_conf"] > TG.ladder_bar(6)["min_conf"]
      and TG.ladder_bar(8)["min_ev"] > TG.ladder_bar(6)["min_ev"])
check("آستانه سقف دارد — در هیچ پله‌ای کاملاً بسته نمی‌شود",
      TG.ladder_bar(999)["min_conf"] == TG.LADDER_CONF_MAX
      and TG.ladder_bar(999)["min_ev"] == TG.LADDER_EV_MAX)
_strong = {"conf": 80, "ev": 1.2}
check("ستاپ عالی حتی در بالاترین پله هم رد می‌شود (سقف عددی نداریم)",
      TG.passes_ladder(_strong, TG.ladder_bar(999)))
_weak = {"conf": 20, "ev": 0.10}
check("ستاپ ضعیف در پلهٔ صفر می‌رود ولی در پلهٔ بالا نگه داشته می‌شود",
      TG.passes_ladder(_weak, TG.ladder_bar(0))
      and not TG.passes_ladder(_weak, TG.ladder_bar(10)))
check("سیگنال بی‌عدد تا پلهٔ ۲ می‌رود، از پلهٔ ۳ نگه داشته می‌شود",
      TG.passes_ladder({}, TG.ladder_bar(6))
      and not TG.passes_ladder({}, TG.ladder_bar(7)))
src_t = (PY / "telegram.py").read_text(encoding="utf-8")
check("سهمیهٔ ثابت و تور ایمنی عددی برداشته شده‌اند (دستور ۲۷ اوت)",
      "n_sent_real >= 40" not in src_t and "n_sent_real >= 24" not in src_t)
check("ضدتکرار همچنان هست (پنجرهٔ ۶ ساعته، نه صفر)",
      3 * 3600 * 1000 <= TG.TTL_MS <= 12 * 3600 * 1000, str(TG.TTL_MS))

# ── ۶) reapply زنجیره: sent.json و دفترهای پیپر از reset جان به در می‌برند ──
from hamid import pump_radar as PR                   # noqa: E402
from hamid import paper as PAPER                     # noqa: E402

ROOT2 = Path(tempfile.mkdtemp(prefix="reapply-"))
BK = ROOT2 / "bk"
BK.mkdir()
(ROOT2 / "signals").mkdir()
(ROOT2 / "brain" / "paper").mkdir(parents=True)
(BK / "sent.json").write_text(json.dumps({"ibs|PAXGUSDT|5m|SHORT": now}))
(ROOT2 / "signals" / "sent.json").write_text(json.dumps({"k0": now - 9}))
open_row = {"sym": "PAXGUSDT", "dir": "SHORT", "tf": "5m", "entry": 4592.02,
            "opened": now - 100, "why": {"stage": "sig-ibs", "tg_msg_id": 77}}
closed_row = {"sym": "AUSDT", "dir": "LONG", "entry": 1.0, "opened": now - 500,
              "outcome": "stop", "R": -1.0, "why": {"stage": "sig-ibs"}}
gone_row = {"sym": "BUSDT", "dir": "LONG", "entry": 2.0, "opened": now - 900,
            "why": {"stage": "sig-ibs"}}
(BK / "open.jsonl").write_text(json.dumps(open_row) + "\n"
                               + json.dumps(gone_row) + "\n")
(BK / "closed.jsonl").write_text(json.dumps(closed_row) + "\n")
# BUSDT قبلاً در درخت بسته شده — نباید به دفتر باز برگردد
(ROOT2 / "brain" / "paper" / "closed.jsonl").write_text(
    json.dumps({**gone_row, "outcome": "target", "R": 3.0}) + "\n")
old_root = PR.ROOT
PR.ROOT = ROOT2
try:
    PR.reapply(BK)
finally:
    PR.ROOT = old_root
snt2 = json.loads((ROOT2 / "signals" / "sent.json").read_text())
check("reapply: کلید ضدتکرار بکاپ به درخت برمی‌گردد (اجتماع، نه بازنویسی)",
      "ibs|PAXGUSDT|5m|SHORT" in snt2 and "k0" in snt2, str(snt2))
op2 = [json.loads(x) for x in
       (ROOT2 / "brain" / "paper" / "open.jsonl").read_text().splitlines()]
check("reapply: پوزیسیون بازِ گم‌شده به دفتر برمی‌گردد (ریپلای نتیجه زنده می‌ماند)",
      any(r["sym"] == "PAXGUSDT" for r in op2), str(op2))
check("reapply: ردیفی که قبلاً بسته شده به دفتر باز برنمی‌گردد",
      not any(r["sym"] == "BUSDT" for r in op2))
cl2 = [json.loads(x) for x in
       (ROOT2 / "brain" / "paper" / "closed.jsonl").read_text().splitlines()]
check("reapply: تسویهٔ گم‌شدهٔ بکاپ به دفتر بسته اضافه می‌شود",
      any(r["sym"] == "AUSDT" for r in cl2))
# دوباره — نباید تکرار بسازد (هویت، نه متن)
PR.ROOT = ROOT2
try:
    PR.reapply(BK)
finally:
    PR.ROOT = old_root
op3 = [json.loads(x) for x in
       (ROOT2 / "brain" / "paper" / "open.jsonl").read_text().splitlines()]
cl3 = [json.loads(x) for x in
       (ROOT2 / "brain" / "paper" / "closed.jsonl").read_text().splitlines()]
check("reapply دوباره → هیچ ردیف تکراری (اجتماع بر هویت معامله)",
      len(op3) == len(op2) and len(cl3) == len(cl2),
      f"op {len(op2)}→{len(op3)} cl {len(cl2)}→{len(cl3)}")
# ورک‌فلو باید این سه را در بکاپ بین‌دوری بگیرد
wf = (PY.parents[1] / ".github" / "workflows" / "pump-radar.yml").read_text()
check("زنجیره sent.json و دفترهای پیپر را در بکاپ بین‌دوری می‌گیرد",
      'cp signals/sent.json "$BK/"' in wf
      and 'cp brain/paper/open.jsonl "$BK/"' in wf
      and 'cp brain/paper/closed.jsonl "$BK/"' in wf)

# ── کلاسِ عیبِ ۳۱ اوت: ارسالِ هم‌زمان روی دو رانرِ جدا ──────────────────
#
# ASTERUSDT دو بار در ۵ دقیقه رفت چون سه منبعِ حافظه هر سه **محلی** بودند
# و زنجیرهٔ دوم چک‌اوتش را قبل از کامیتِ زنجیرهٔ اول گرفته بود. منبعِ
# چهارم (ریموت) تنها چیزی است که هر سه زنجیره مشترک می‌بینند.
_src = pathlib.Path(__file__).resolve().parent.parent / "telegram.py"
_t = _src.read_text(encoding="utf-8")

check("منبع چهارمِ حافظه از ریموت می‌خواند (نه فقط دیسک/tmp/لاگ محلی)",
      "_remote_log_rows" in _t and "origin/main" in _t)
_body = _t.split("def _load_sent")[1].split("def _save_sent")[0]
check("منبع ریموت داخل خودِ _load_sent مصرف می‌شود",
      "_remote_log_rows()" in _body, _body[-400:])
check("ریموت هر دو کلیدِ ضدتکرار را بازمی‌سازد (any و pair)",
      'f"any|{r[\'sym\']}|{r[\'tf\']}|{r[\'dir\']}"' in _t
      and 'f"pair|{r[\'sym\']}|{r[\'dir\']}"' in _t)
check("شکستِ شبکه ارسال را متوقف نمی‌کند (خرابی نرم)",
      "return []" in _t.split("def _remote_log_rows")[1][:2600])
check("خواندنِ ریموت قابلِ خاموش‌کردن است (برای آزمون/سرویس محلی)",
      "LIAM9_NO_REMOTE_DEDUPE" in _t)

# رفتار: با خاموش‌کردن ریموت، تابع باید بی‌خطا فهرست خالی بدهد
import os as _os
import telegram as _tg
_os.environ["LIAM9_NO_REMOTE_DEDUPE"] = "1"
check("خاموش‌کردن ریموت، خطا نمی‌دهد و خالی برمی‌گرداند",
      _tg._remote_log_rows() == [])
_os.environ.pop("LIAM9_NO_REMOTE_DEDUPE")

# پارسِ لاگ باید در برابر فایلِ خراب مقاوم باشد — وگرنه یک فایلِ نیمه‌نوشته
# کلِ حافظه را صفر می‌کند و همان عیب برمی‌گردد.
check("لاگِ خراب حافظه را صفر نمی‌کند", _tg._log_rows("{ناقص") == []
      and _tg._log_rows('{"sent":[{"sym":"X"}]}') == [{"sym": "X"}])

check("سه ورک‌فلوی ارساله همچنان جدا می‌دوند (سریالی‌کردن ممنوع بود)",
      True, "مستندسازی: رفع از راه حافظهٔ مشترک است نه قفلِ سراسری")


# ── دروازهٔ ستاپ یخ‌زده (پروندهٔ LOKAUSDT، ۵ سپتامبر) ───────────────────
#
# LOKAUSDT از ۲۳ اوت نُه بار با ورودِ دقیقاً یکسان ۰.۱۲۳۶ فرستاده شد و هر
# نُه بار منقضی — قیمت هرگز نرسید. ضدتکرارِ ۳ و ۶ ساعته نمی‌گرفتش چون
# ارسال‌ها ۱۴+ ساعت فاصله داشتند.
import tempfile as _tf2                              # noqa: E402
import pathlib as _pl                                # noqa: E402

check("آستانه دو است، نه یک (لبهٔ یک‌بار-منقضی هنوز CI بالای صفر دارد)",
      _tg.FROZEN_MIN_EXPIRED == 2, str(_tg.FROZEN_MIN_EXPIRED))

with _tf2.TemporaryDirectory() as _td3:
    from hamid import paper as _P2
    _old_closed = _P2.CLOSED
    try:
        _P2.CLOSED = _pl.Path(_td3) / "closed.jsonl"
        def _exp(sym, entry, outcome="expired"):
            return json.dumps({"sym": sym, "entry": entry, "outcome": outcome,
                                "closed": 1, "why": {"stage": "sig-smc"}},
                               ensure_ascii=False)
        _P2.CLOSED.write_text("\n".join([
            _exp("LOKAUSDT", 0.1236), _exp("LOKAUSDT", 0.1236),
            _exp("LOKAUSDT", 0.1236),
            _exp("AAAUSDT", 1.0),                     # فقط یک انقضا
            _exp("BBBUSDT", 2.0, "stop"),             # اصلاً منقضی نبوده
            _exp("BBBUSDT", 2.0, "target"),
        ]) + "\n", encoding="utf-8")
        _fr = _tg._frozen_entries()
        check("شمارش انقضا فقط منقضی‌ها را می‌شمارد",
              _fr.get(("LOKAUSDT", 0.1236)) == 3
              and _fr.get(("BBBUSDT", 2.0)) is None, str(_fr))
        check("ورودِ یک‌بار منقضی زیر آستانه می‌ماند",
              _fr.get(("AAAUSDT", 1.0)) == 1
              and _fr.get(("AAAUSDT", 1.0)) < _tg.FROZEN_MIN_EXPIRED)
        check("ورودِ متفاوتِ همان ارز شمرده نمی‌شود (کلید شامل قیمت است)",
              _fr.get(("LOKAUSDT", 0.2)) is None)

        # اثبات رفتاری: همان ستاپِ LOKA از گلوگاه ارسال رد نمی‌شود.
        _o3 = (TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR)
        TG.SENT = TMP / "s-fr.json"
        TG.SIDECAR = TMP / "sc-fr.json"
        TG.TGLOG = TMP / "lg-fr.json"
        TG.ARCHIVE_DIR = TMP / "arc-fr"
        # آفلاین، دروازه‌های شبکه‌ای (هم‌زمانی/روند) هرچه باشد رد می‌کنند،
        # پس ملاک «رفت یا نرفت» نیست — ملاکْ **دلیلِ رد** است.
        import contextlib as _ctx
        import io as _io

        def _reject_reason(entry, d):
            _buf = _io.StringIO()
            _op3, _oc3 = TG._post, TG.creds
            TG._post = lambda *a, **k: {"result": {"message_id": 7}}
            TG.creds = lambda: ("tok", "chat")
            try:
                with _ctx.redirect_stdout(_buf):
                    TG.send_signals(
                        [{"sym": "LOKAUSDT", "tf": "5m", "dir": d,
                          "strategy": "smc", "entry": entry,
                          "sl": entry * 0.99, "tp1": entry * 1.02}],
                        lambda s, p: None)
            finally:
                TG._post, TG.creds = _op3, _oc3
            return _buf.getvalue()

        try:
            _out_frozen = _reject_reason(0.1236, "LONG")
            _out_fresh = _reject_reason(0.2, "SHORT")
        finally:
            TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR = _o3
        check("رفتاری: ستاپِ یخ‌زدهٔ LOKA با همین دروازه رد می‌شود",
              "دروازهٔ ستاپ یخ‌زده" in _out_frozen, _out_frozen[:200])
        check("و ورودِ تازهٔ همان ارز از این دروازه رد نمی‌شود "
              "(دروازه ارز را نمی‌بندد، ورودِ یخ‌زده را می‌بندد)",
              "دروازهٔ ستاپ یخ‌زده" not in _out_fresh, _out_fresh[:200])
    finally:
        _P2.CLOSED = _old_closed

# دفترِ ناخوانا نباید دروازه را سفت کند — «نمی‌دانم» یعنی نبند.
with _tf2.TemporaryDirectory() as _td4:
    from hamid import paper as _P3
    _old2 = _P3.CLOSED
    try:
        _P3.CLOSED = _pl.Path(_td4) / "nope.jsonl"    # وجود ندارد
        check("دفتر ناموجود → دروازهٔ خاموش، نه بستنِ کور",
              _tg._frozen_entries() == {})
    finally:
        _P3.CLOSED = _old2

_src_tg = (HERE.parent / "telegram.py").read_text(encoding="utf-8")
check("دروازهٔ یخ‌زده در همان حلقهٔ گلوگاه ارسال است",
      "_frozen_setup(s)" in _src_tg
      and _src_tg.index("_frozen_setup(s)") < _src_tg.index("fresh.append(s)"))
check("و دلیلش روی لاگ می‌رود (رد بی‌دلیل ممنوع)",
      "دروازهٔ ستاپ یخ‌زده" in _src_tg)
check("عددهای پشتوانه در خودِ کد مستند شده‌اند (نه فقط در گزارش)",
      "۸۴.۵٪" in _src_tg and "۸۵.۰٪" in _src_tg and "۴۸٬۷۳۲" in _src_tg)
check("ارسالِ بی‌ردیفِ دفتر دیگر بی‌صدا نیست",
      "ارسال شد ولی ردیف دفتر ساخته نشد" in _src_tg)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
