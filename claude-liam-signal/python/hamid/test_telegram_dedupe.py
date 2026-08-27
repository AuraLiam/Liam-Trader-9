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
    loop_after_send = src.split('sent[f"any|', 1)[1][:400]
    check("بعد از هر ارسال، همان لحظه ذخیره می‌شود (_save_sent داخل حلقه)",
          "_save_sent(sent)" in loop_after_send, loop_after_send[:120])
    check("هیچ نوشتن مستقیم SENT.write_text بیرون از _save_sent نیست",
          src.count("SENT.write_text") == 1)
    check("آرشیو در مسیر ارسال صدا زده می‌شود",
          "_archive_sent(s)" in loop_after_send)
finally:
    TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR = old

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

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
