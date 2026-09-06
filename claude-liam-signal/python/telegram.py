#!/usr/bin/env python3
"""Sends a signal to Telegram as a chart with the numbers written on it.

The panel already sends signals from the browser when it is open and can reach
the exchange. This is the other path: the scan runs on a GitHub runner every ten
minutes whether anything is open or not, and this delivers what it finds.

Two rules that matter more than the formatting.

A signal is sent once. The scan re-runs every ten minutes and the same setup
will still be there on the next pass, so without a memory of what has gone out
the same trade would arrive six times an hour. `signals/sent.json` is that
memory, keyed on symbol, timeframe, direction and the entry price rounded, and
it forgets an entry after twelve hours so a genuinely new setup on the same pair
can still arrive.

Nothing is sent without credentials. No token means no delivery and a printed
line saying so — never a silent success.

    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 scan.py --telegram
"""
import json, os, time, urllib.error, urllib.request, uuid
from pathlib import Path

API = "https://api.telegram.org"
SENT = Path(__file__).resolve().parent.parent.parent / "signals" / "sent.json"
TGLOG = Path(__file__).resolve().parent.parent.parent / "signals" / "telegram-log.json"
# ضدتکرار: همان ستاپ دوباره نرود — ولی «ستاپِ تازهٔ همان جفت» بعد از
# چند ساعت، سیگنالِ تازه است. دستور ۲۷ اوت («تا سیگنال هست باید بدهد»)
# پنجره را از ۱۲ به ۶ ساعت آورد؛ تکرارِ دقیقه‌ایِ PAXG با حافظهٔ
# سه‌منبعی و ذخیرهٔ فوری بسته شده، نه با طولِ این پنجره.
TTL_MS = 6 * 3600 * 1000
# ردِ موقت ≠ ممنوعیت نیم‌روزه (عیب ۲۰ اوت — توضیح در _load_sent)
SKIP_TTL_MS = 30 * 60 * 1000
# حافظهٔ کناری ضدتکرار — مستقل از گیت (عیب ۲۶ اوت: PAXG پنج بار در ۲۱
# دقیقه رفت چون sent.json فقط با push روی main دوام می‌آورد؛ از ۲۰:۱۲ تا
# ۲۱:۰۱ هیچ push ای ننشست و هر دورِ زنجیره با reset به حافظهٔ کهنه
# برمی‌گشت). /tmp روی رانر بین همهٔ دورهای یک اجرا زنده می‌ماند، پس
# ارسال‌شده حتی با شکستِ کامل push دوباره نمی‌رود. قابل‌جابه‌جایی با env
# برای سرویس محلی.
SIDECAR = Path(os.environ.get("LIAM9_SENT_SIDECAR", "/tmp/liam9-sent-sidecar.json"))
# آرشیو شماره‌دار append-only — دستور حمید (۲۶ اوت شب): «اطلاعات را یکی
# نکن؛ کنار هم نگه دار و شماره‌گذاری کن.» هر ارسال یک ردیف با شمارهٔ
# پیاپی؛ هیچ ادغام/بازنویسی‌ای روی این فایل‌ها انجام نمی‌شود.
ARCHIVE_DIR = Path(__file__).resolve().parent.parent.parent / "signals" / "archive"
# دستور صریح حمید (۲۶ اوت شب): «ارسال سیگنال فقط توی تایم‌فریم‌های ۱۵ و
# ۵ دقیقه باشه.» هر tf دیگری در گلوگاه ارسال بلند رد می‌شود.
ALLOWED_TFS = {"5m", "15m"}


# سقف‌های خودِ تلگرام — نه انتخاب ما (منبع: Bot API، فیلد caption/text)
CAPTION_LIMIT = 1024
TEXT_LIMIT = 4096


def _split_caption(text, limit=None):
    """کپشن بلند را به «سرِ زیر سقف» + «دنبالهٔ ریپلای» تقسیم می‌کند.

    برش فقط روی مرز خط انجام می‌شود تا تگ HTML نصف نشود (کپشن‌های ما
    خط‌به‌خط تگ‌بسته‌اند). اگر یک خط تنها از سقف بلندتر بود، همان خط
    سخت بریده می‌شود — چون گم‌شدنِ کل سیگنال بدتر از یک خطِ بریده است.
    """
    limit = limit or CAPTION_LIMIT
    if len(text) <= limit:
        return text, ""
    head, n = [], 0
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        add = len(ln) + (1 if head else 0)
        if n + add > limit:
            if not head:                      # حتی خط اول جا نمی‌شود
                return text[:limit], text[limit:limit + TEXT_LIMIT]
            tail = "\n".join(lines[i:])
            return "\n".join(head), tail[:TEXT_LIMIT]
        head.append(ln)
        n += add
    return text, ""


def _counter_note(s):
    return ("\n" + s["counter_trend_note"]) if s.get("counter_trend_note") else ""


def _log_final(s):
    """«سیگنال نهایی» — هر چه واقعاً به تلگرام رفت، برای نمایش در پنل هم ثبت
    می‌شود. یک فایل مشترک با tg_batch، که پنل یک منبع حقیقت داشته باشد.

    محافظ قرارداد اجرا (درس ۲۶ اوت): سیگنال بی‌استاپ/بی‌تارگت باطل است.
    گزارش/واچ‌لیست (مثل رادار پامپ) قبلاً ردیف tp1=None این‌جا می‌نوشت و
    حمید در تلگرام «سیگنالِ ناقص» می‌دید و همان ردیف به پل اجرا هم هل
    داده می‌شد. حالا ردیف بی‌tp1/sl نه ثبت می‌شود نه به اجرا می‌رود —
    بلند رد می‌شود تا فرستنده‌اش در لاگ معلوم باشد."""
    try:
        ok_lvls = float(s.get("tp1") or 0) > 0 and float(s.get("sl") or 0) > 0
    except (TypeError, ValueError):
        ok_lvls = False
    if not ok_lvls:
        print(f"دفتر سیگنال: ردِ ردیف بی‌تارگت/بی‌استاپ "
              f"({s.get('sym')} · {s.get('strategyName') or s.get('name')}) — "
              "قرارداد اجرا: این سیگنال نیست، ثبت و اجرا نشد", flush=True)
        return
    try:
        log = json.loads(TGLOG.read_text()).get("sent", []) if TGLOG.exists() else []
    except Exception:                                  # noqa: BLE001
        log = []
    # پل داشبورد (۱۷ اوت): سیگنال ارسال‌شده اگر از زنجیرهٔ اجرا
    # (کیل‌سوییچ/کارمزد/سایز) هم بگذرد، قصد اجرا در exec-outbox می‌نشیند.
    try:
        from hamid import execution_gate
        execution_gate.push(s)
    except Exception:                                  # noqa: BLE001
        pass
    log.insert(0, {"at": int(time.time() * 1000),
                   "sym": s.get("sym"), "dir": s.get("dir"), "tf": s.get("tf"),
                   "trend4": s.get("trend4"), "trend1": s.get("trend1"),
                   "entry": s.get("entry"), "sl": s.get("sl"),
                   "tp1": s.get("tp1"), "tp2": s.get("tp2"),
                   "name": s.get("strategyName") or s.get("name") or "",
                   "elite": bool(s.get("elite"))})
    TGLOG.parent.mkdir(parents=True, exist_ok=True)
    TGLOG.write_text(json.dumps({"generated": int(time.time() * 1000),
                                 "sent": log[:40]}, ensure_ascii=False, indent=1))


def creds():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return (tok, chat) if tok and chat else (None, None)


def scrub(text):
    """Remove the bot token from anything about to be printed.

    urllib puts the request URL into its exception text, and the Telegram URL is
    https://api.telegram.org/bot<TOKEN>/sendMessage — so a plain network failure
    printed the full token. Inside GitHub Actions the registered secret gets
    masked, which is why this was survivable; but the same code runs from a
    laptop, from n8n, from anywhere, and there the token would land in the
    output in the clear. Relying on someone else's masking for a secret we
    already hold is not a safety property, it is luck.
    """
    out = str(text)
    for tok in (os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),):
        if not tok:
            continue
        out = out.replace(tok, "***")
        # the numeric prefix alone identifies the bot, so hide bot<id>: too
        head = tok.split(":")[0]
        if head:
            out = out.replace(f"bot{head}", "bot***")
    return out


def _log_rows(text):
    try:
        return json.loads(text).get("sent") or []
    except Exception:                                # noqa: BLE001
        return []


def _remote_log_rows():
    """منبع چهارم — دفترِ ارسالِ روی **ریموت**، نه روی این ماشین.

    عیبِ اندازه‌گیری‌شدهٔ ۳۱ اوت (ASTERUSDT دو بار در ۵ دقیقه، ۰۱:۰۱ و
    ۰۱:۰۶): سه منبعِ قبلی — دیسک، /tmp، بازسازی از لاگ — **هر سه محلیِ
    همان رانر**اند. سه ورک‌فلو حق ارسال دارند (hamid-cycle، pump-radar،
    live-scan) و هر کدام گروه هم‌زمانیِ جدا دارد، پس با هم می‌دوند و هر
    کدام چک‌اوتِ خودش را دارد. زنجیره‌ای که چک‌اوتش را قبل از کامیتِ
    زنجیرهٔ دیگر گرفته باشد، ارسالِ چند دقیقه پیش را **اصلاً نمی‌بیند** —
    حافظه‌اش واقعاً خالی است و دروازهٔ ۳ ساعته چیزی برای دیدن ندارد.

    همان کلاسِ PAXG×۵ است: رفعِ ۲۶ اوت درست بود ولی هر سه منبعش داخلِ
    یک ماشین می‌ماند. تنها چیزی که هر سه زنجیره **مشترک** می‌بینند
    ریموت است، پس درست قبل از دروازه یک بار از آن‌جا خوانده می‌شود.

    مرز: شکستِ شبکه نباید ارسال را متوقف کند، پس خطا = فهرست خالی و
    همان سه منبعِ قبلی سرِ جایشان‌اند (خرابیِ نرم، نه سخت). و چون فقط
    **می‌خواند**، هیچ حالتِ گیتی را عوض نمی‌کند."""
    if os.environ.get("LIAM9_NO_REMOTE_DEDUPE"):
        return []
    import subprocess
    for ref in ("origin/main", "main"):
        try:
            if ref.startswith("origin/"):
                subprocess.run(["git", "fetch", "-q", "--depth=1", "origin", "main"],
                               cwd=str(SENT.parent.parent), timeout=25,
                               capture_output=True, check=False)
            out = subprocess.run(["git", "show", f"{ref}:signals/telegram-log.json"],
                                 cwd=str(SENT.parent.parent), timeout=20,
                                 capture_output=True, text=True, check=False)
            if out.returncode == 0 and out.stdout.strip():
                rows = _log_rows(out.stdout)
                if rows:
                    return rows
        except Exception:                            # noqa: BLE001
            continue
    return []


def _load_sent():
    """ارسال‌شده ۱۲ ساعت یادش می‌ماند؛ ردشدهٔ موقت فقط ۳۰ دقیقه.

    عیب سنجیده‌شدهٔ ۲۰ اوت (شکایت حمید «سیگنال کم می‌آید»): هر ردِ لحظه‌ای
    — قیمت ۲.۶٪ دور بود، روند همان دقیقه مخالف بود، بازجویی همان لحظه
    con>pro داد — کلید `skip|` می‌نوشت و آن کلید هم ۱۲ ساعت زنده می‌ماند.
    یعنی یک شرطِ گذرا به ممنوعیت نیم‌روزه تبدیل می‌شد: ۱۳۹ skip در برابر
    ۳۶ ارسال در ۲۴ ساعت. حالا ردِ موقت بعد از ۳۰ دقیقه (≈ دو کندل ۱۵د)
    دوباره بررسی می‌شود و باید **همهٔ** دروازه‌ها را از نو پاس کند —
    هیچ دروازه‌ای شل نشده، فقط حکمِ لحظه‌ای دیگر ابدی نیست.

    ضدتکرار سه‌منبعی (رفع ریشه‌ای ۲۶ اوت — PAXG×۵): اجتماعِ دیسک +
    حافظهٔ کناری /tmp + بازسازی از خود لاگ ارسال. حافظه فقط وقتی خالی
    است که هر سه منبع خالی باشند — گم‌شدنِ push دیگر به معنی فراموشی
    نیست."""
    merged = {}
    for p in (SENT, SIDECAR):
        try:
            for k, v in json.loads(p.read_text()).items():
                if isinstance(v, (int, float)) and v > merged.get(k, 0):
                    merged[k] = v
        except Exception:                            # noqa: BLE001 - a missing or torn file is an empty memory
            pass
    # منبع سوم: هر ردیفی که واقعاً به تلگرام رفته (telegram-log) دست‌کم
    # کلید بین‌استراتژی any| را بازمی‌سازد — حتی اگر sent.json کامل گم شود.
    for rows in (_log_rows(TGLOG.read_text() if TGLOG.exists() else ""),
                 _remote_log_rows()):
        for r in rows:
            if r.get("sym") and r.get("tf") and r.get("dir") and r.get("at"):
                for k in (f"any|{r['sym']}|{r['tf']}|{r['dir']}",
                          f"pair|{r['sym']}|{r['dir']}"):
                    if float(r["at"]) > merged.get(k, 0):
                        merged[k] = float(r["at"])
    now = time.time() * 1000
    return {k: v for k, v in merged.items()
            if now - v < (SKIP_TTL_MS if k.startswith("skip|") else TTL_MS)}


def _save_sent(sent):
    """ذخیرهٔ فوری در هر دو خانه — دیسک (گیت) و کناری (/tmp).

    قبلاً فقط در انتهای send_signals یک بار نوشته می‌شد؛ سقوط وسط حلقه یا
    شکست push یعنی فراموشیِ ارسال‌های همان حلقه. حالا بعد از هر ارسال
    صدا زده می‌شود."""
    try:
        SENT.parent.mkdir(parents=True, exist_ok=True)
        SENT.write_text(json.dumps(sent, indent=1))
    except Exception as e:                           # noqa: BLE001
        print(f"telegram: ذخیرهٔ sent.json نشد ({type(e).__name__})", flush=True)
    try:
        SIDECAR.parent.mkdir(parents=True, exist_ok=True)
        SIDECAR.write_text(json.dumps(sent, indent=1))
    except Exception as e:                           # noqa: BLE001
        print(f"telegram: ذخیرهٔ حافظهٔ کناری نشد ({type(e).__name__})", flush=True)


def _log_delivery_fail(s, why):
    """شکستِ تحویل باید ردِ دائمی بگذارد، نه فقط یک خط چاپ.

    درسِ ۲۷ اوت: SOL و CRCLB از همهٔ دروازه‌ها رد شده بودند و بعد تلگرام
    ۴۰۰ داد؛ تنها ردش یک خط در لاگ رانر بود که با پایان اجرا محو می‌شد.
    از بیرون، «سیگنالِ گم‌شده» عیناً شبیه «ستاپی نبود» دیده می‌شد. حالا
    هر شکست در آرشیو شماره‌دار می‌نشیند تا قابل شمارش باشد."""
    try:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        f = ARCHIVE_DIR / f"delivery-failures-{time.strftime('%Y%m%d', time.gmtime())}.jsonl"
        n = sum(1 for _ in f.open()) if f.exists() else 0
        with f.open("a") as fh:
            fh.write(json.dumps({
                "n": n + 1, "at": int(time.time() * 1000),
                "sym": s.get("sym"), "tf": s.get("tf"), "dir": s.get("dir"),
                "entry": s.get("entry"), "strategy": s.get("strategy"),
                "why": str(why)[:300]}, ensure_ascii=False) + "\n")
    except Exception as e:                           # noqa: BLE001
        print(f"telegram: ثبت شکست تحویل نشد ({type(e).__name__})", flush=True)


def _archive_sent(s):
    """آرشیو شماره‌دار append-only — هر ارسال یک ردیف، هرگز ادغام/بازنویسی.

    دستور حمید (۲۶ اوت شب): اطلاعات کنار هم و شماره‌گذاری‌شده نگه داشته
    شود. شمارهٔ ردیف = شمار ردیف‌های موجودِ همان روز + ۱."""
    try:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        day = time.strftime("%Y%m%d", time.gmtime())
        f = ARCHIVE_DIR / f"telegram-sent-{day}.jsonl"
        n = sum(1 for _ in f.open()) if f.exists() else 0
        row = {"n": n + 1, "at": int(time.time() * 1000),
               "sym": s.get("sym"), "tf": s.get("tf"), "dir": s.get("dir"),
               "entry": s.get("entry"), "sl": s.get("sl"),
               "tp1": s.get("tp1"), "strategy": s.get("strategy"),
               "tg_msg_id": s.get("tg_msg_id")}
        with f.open("a") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:                           # noqa: BLE001 - آرشیو نباید ارسال را بکشد
        print(f"telegram: آرشیو ثبت نشد ({type(e).__name__})", flush=True)


FEED = Path(__file__).resolve().parent.parent.parent / "signals" / "telegram-feed.json"
FEED_CAP = 200


def record_out(kind, title, extra=None, msg_id=None):
    """دفترِ واحدِ «چه چیزی به تلگرام رفت» — برای پنل (دستور حمید، ۲۸ اوت).

    تا امروز فقط سیگنال‌ها ثبت می‌شدند (telegram-log). گزارش دامیننس،
    گزارش کار، گزارش پامپ و نتیجه‌ها هیچ ردی روی پنل نداشتند: حمید در
    تلگرام می‌دیدشان و پنل از وجودشان بی‌خبر بود. حالا هر ارسال دو رد
    می‌گذارد: حلقهٔ ۲۰۰تایی برای پنل + آرشیو شماره‌دار append-only
    (قانون ضد-merge: کنار هم و شماره‌دار، نه ادغام).
    """
    row = {"at": int(time.time() * 1000), "kind": kind,
           "title": str(title)[:200], "msg_id": msg_id}
    if extra:
        row["extra"] = extra
    try:
        cur = json.loads(FEED.read_text()).get("rows") or []
    except Exception:                                # noqa: BLE001
        cur = []
    cur.append(row)
    cur = cur[-FEED_CAP:]
    try:
        FEED.parent.mkdir(parents=True, exist_ok=True)
        FEED.write_text(json.dumps(
            {"generated": row["at"], "rows": cur}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:                           # noqa: BLE001 - دفتر، ارسال را نمی‌کشد
        print(f"telegram: دفتر پنل نوشته نشد ({type(e).__name__})", flush=True)
    try:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        f = ARCHIVE_DIR / f"telegram-feed-{time.strftime('%Y%m%d', time.gmtime())}.jsonl"
        n = sum(1 for _ in f.open()) if f.exists() else 0
        with f.open("a") as fh:
            fh.write(json.dumps({"n": n + 1, **row}, ensure_ascii=False) + "\n")
    except Exception as e:                           # noqa: BLE001
        print(f"telegram: آرشیو دفتر پنل نشد ({type(e).__name__})", flush=True)
    return row


def _key(s):
    """بدون قیمت ورود. قیمت دقیق در کلید بود و بین دو چرخه چند دهم درصد
    جابه‌جا می‌شد (TAO: ‏205.3 → 206.6) — کلید عوض می‌شد و همان سیگنال دوباره
    می‌رفت؛ حمید سه تکرار را دید. حالا همان ارز/تایم‌فریم/جهت/استراتژی تا
    ۱۲ ساعت فقط یک بار می‌رود — نرسیدنِ یک ستاپ تازهٔ همان جفت در همان روز،
    ارزان‌تر از پیام تکراری است."""
    return f"{s.get('strategy','?')}|{s['sym']}|{s['tf']}|{s['dir']}"


# ── تک‌مقصدی، بدون استثنا (دستور حمید، ۲۰ اوت) ────────────────────────────
#
# «سیگنال‌ها فقط روی یک بات: @LiamTrader9_Bot». آینهٔ مقصد دوم (که ۱۴ اوت
# اضافه شده بود) کامل برداشته شد و متغیرهای TELEGRAM_*_2 از همهٔ ورک‌فلوها
# پاک شدند. پاسبان test_single_bot برگشتشان را ناممکن می‌کند.


def _post(token, method, fields, files=None):
    """ارسال — فقط و فقط به یک مقصد: @LiamTrader9_Bot.

    هیچ آینه، هیچ مقصد دوم، هیچ کپی. اگر روزی کسی خواست مقصد دیگری اضافه
    کند، باید این تابع را عوض کند و آزمون test_single_bot سرخ می‌شود.
    """
    return _post_once(token, method, fields, files)


# ── خوددرمانی chat_id (دستور حمید، ۱۸ اوت) ─────────────────────────────────
#
# سه اجرای مستقل نشان داد TELEGRAM_CHAT_ID اشتباهاً شناسهٔ خود ربات است و
# تلگرام «bot can't send messages to the bot» می‌دهد. به‌جای سکوت تا اصلاح
# دستی Secret: اگر ارسال با همین کلاس خطا رد شد، چت واقعی از getUpdates
# کشف می‌شود (کسی که به ربات پیام داده)، ارسال همان‌جا تکرار می‌شود و یک
# پیام یک‌بارمصرف با شناسهٔ درست به همان چت می‌رود تا Secret اصلاح شود.
# شناسهٔ کشف‌شده فقط در حافظهٔ همین اجرا می‌ماند — ریپو عمومی است و
# chat_id روی دیسک/لاگ کامل نمی‌نشیند (در لاگ فقط پوشیده).
_HEALED_CHAT = None
_HEAL_NOTICED = False
_BAD_CHAT_ERRS = ("can't send messages to the bot", "chat not found",
                  "can't initiate conversation")


def _discover_chat(token):
    global _HEALED_CHAT
    if _HEALED_CHAT:
        return _HEALED_CHAT
    try:
        req = urllib.request.Request(f"{API}/bot{token}/getUpdates")
        with urllib.request.urlopen(req, timeout=20) as r:
            ups = json.load(r).get("result") or []
    except Exception:                                # noqa: BLE001
        return None
    for up in reversed(ups):
        m = up.get("message") or up.get("edited_message") or {}
        c = m.get("chat") or {}
        if c.get("id") and c.get("type") == "private":
            _HEALED_CHAT = str(c["id"])
            print("تلگرام: chat_id تنظیم‌شده غلط بود؛ چت واقعی از getUpdates "
                  f"پیدا شد ({_HEALED_CHAT[:2]}…{_HEALED_CHAT[-2:]})", flush=True)
            return _HEALED_CHAT
    return None


def _heal_notice(token, chat):
    """یک بار در هر اجرا: شناسهٔ درست به چت خود حمید — نه به لاگ عمومی."""
    global _HEAL_NOTICED
    if _HEAL_NOTICED:
        return
    _HEAL_NOTICED = True
    try:
        _post_once(token, "sendMessage", {
            "chat_id": chat, "parse_mode": "HTML",
            "text": (f"{BRAND}\n⚠️ مقدار TELEGRAM_CHAT_ID در Secrets غلط است "
                     "(شناسهٔ خود ربات). مقدار درست این چت:\n"
                     f"<code>{chat}</code>\n"
                     "Settings → Secrets → Actions → TELEGRAM_CHAT_ID را با "
                     "همین عدد به‌روز کن. تا آن موقع ارسال‌ها خوددرمان می‌شوند.")})
    except Exception:                                # noqa: BLE001
        pass


def _post_once(token, method, fields, files=None):
    """multipart/form-data by hand — sendPhoto needs it and stdlib has no helper."""
    boundary = uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                 f"{v}\r\n").encode()
    for k, (name, blob) in (files or {}).items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; "
                 f"filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode()
        body += blob + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}/bot{token}/{method}", data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())
        except Exception:                            # noqa: BLE001
            raise e from None
        desc = (err.get("description") or "").lower()
        bad_chat = str(fields.get("chat_id") or "")
        if bad_chat and any(x in desc for x in _BAD_CHAT_ERRS):
            healed = _discover_chat(token)
            if healed and healed != bad_chat:
                f2 = dict(fields)
                f2["chat_id"] = healed
                resp = _post_once(token, method, f2, files)
                if resp.get("ok"):
                    _heal_notice(token, healed)
                return resp
        raise e from None


# نام منبع، بالای هر پیام — و عمداً از **محیط** خوانده می‌شود، نه ثابت.
#
# ۱۶ اوت: دو پنل به یک کانال می‌فرستند و حمید خواست بداند هر سیگنال از
# کدام است. به این پنل گفت «aura liam mAx»، به آن یکی «لیام تریدر ۹».
# ولی هر دو همین یک فایل را روی main دارند، پس وقتی هرکدام نام خودش را
# این‌جا ثابت می‌نوشت، پوشِ بعدی آن یکی را پاک می‌کرد — و نتیجه‌اش دقیقاً
# ضدِ چیزی بود که حمید خواست: هیچ‌کدام پایدار نمی‌ماند.
#
# حالا هر خط تولید نامش را با متغیر محیطی PANEL_NAME می‌دهد. پیش‌فرض
# دست‌نخورده می‌ماند تا خط تولیدی که این متغیر را ست نکرده، رفتارش عوض
# نشود.
PANEL_NAME = os.getenv("PANEL_NAME") or "لیام تریدر ۹"

# ۱۶ اوت — حمید دید: «هنوز با اسم کلود مکس سیگنال می‌فرستی؟» درست دیده بود.
# دفعهٔ قبل فقط **نام پنل** متغیر شد، ولی یک برچسب دومِ هاردکد («کلود مکس»)
# در نُه جای دیگر مانده بود و هر پیام دو اسم داشت:
#   🏷 aura liam mAx · 🤖 سیگنال کلود مکس
# «کلود مکس» نام سازنده بود نه نام پنل، و کنار نام پنل نشستنش یعنی حمید
# نمی‌تواند از روی برچسب بفهمد سیگنال از کدام خط تولید آمده — دقیقاً همان
# چیزی که خواسته بود حل شود.
#
# پس یک منبع حقیقت: هر پیامی که از هر فایلی بیرون می‌رود سرش را از این‌جا
# می‌گیرد. اگر روزی برند عوض شود، یک جا عوض می‌شود.
BRAND = f"🏷 <b>{PANEL_NAME}</b>"


def _panel_code(name=None):
    """کد کوتاه پنل برای شناسهٔ سیگنال — تا دو پنل شناسهٔ قابل تفکیک بدهند.

    شناسه‌ها با `CM-` شروع می‌شدند («کلود مکس») و هر دو خط تولید یک پیشوند
    داشتند؛ یعنی حتی از روی شناسه هم معلوم نبود سیگنال از کجاست. حروف اول
    بخش‌های لاتینِ نام پنل برداشته می‌شود («aura liam mAx» → `ALM`). نام
    تمام‌فارسی حرف لاتین ندارد، پس به `LIAM` برمی‌گردد — یک پیش‌فرضِ
    آشکار، نه حدسِ خاموش.
    """
    parts = [w for w in (name or PANEL_NAME).split()
             if w[:1].isascii() and w[:1].isalpha()]
    code = "".join(w[0].upper() for w in parts)[:4]
    return code or "LIAM"


PANEL_CODE = os.getenv("PANEL_CODE") or _panel_code()


def tehran(ms=None):
    """ساعت تهران (UTC+3:30) — حمید باید ببیند بین تحلیل و ارسال تأخیری نبوده."""
    t = time.gmtime(((ms if ms else time.time() * 1000) / 1000) + 3.5 * 3600)
    return time.strftime("%H:%M", t)


def caption(s):
    dir_fa = "🟢 خرید (LONG)" if s["dir"] == "LONG" else "🔴 فروش (SHORT)"
    # نام پنل بالای هر پیام — چند هوش مصنوعی دیگر هم سیگنال می‌فرستند و حمید
    # باید بداند هر سیگنال از کدام است تا ضعیف‌ها را حذف کند.
    # شناسهٔ یکتای سیگنال (دستور حمید ۱۳ اوت) — قابل ارجاع در نتیجه/گفتگو
    sid = time.strftime(f"{PANEL_CODE}-%m%d-%H%M",
                        time.gmtime(time.time() + 3.5 * 3600))
    L = [f"{BRAND} · 🆔 <code>{sid}-{s['sym'].replace('USDT','')}</code>",
         f"<b>{dir_fa} — {s['sym']}</b>  <code>{s['tf']}</code>"]
    # Which strategy produced this. Two strategies run side by side and a signal
    # that does not say which one it came from cannot be judged or learned from.
    if s.get("strategyName"):
        L.append(f"استراتژی: <b>{s['strategyName']}</b>")
    # حافظهٔ ایجنت — «اگر شباهت قوی با گذشته پیدا کردی صریح ذکر کن»: جملهٔ
    # عددی حافظه دربارهٔ همین ارز/جهت، روی خود پیام، تا تصمیم با تجربه باشد.
    if s.get("memory"):
        L.append(f"🧠 <i>{s['memory']}</i>")
    if s.get("liq_note"):
        L.append(f"💧 <i>{s['liq_note']}</i>")
    # نقشهٔ لیکوییدیشن — خوشه‌های تخمینی از کندل واقعی، سبک نقشهٔ kCEX
    if s.get("liqmap_note"):
        L.append(f"<i>{s['liqmap_note']}</i>")
    # بازجویی پیش از صدور — سیگنال فقط با دلایلِ تارگتِ بیشتر رسیده اینجا
    pm = s.get("premortem")
    if pm:
        # انجین الگوهای کلاسیک — الگوهای زندهٔ ۱۵د/۱س/۴س روی خود پیام
        if (pm.get("patterns") or {}).get("note"):
            L.append(f"🧩 <i>الگو: {pm['patterns']['note']}</i>")
        # انجین اردر بلاک — باکس معتبر با شمارش واکنش/هانت روی خود پیام
        if (pm.get("ob_ctx") or {}).get("note"):
            L.append(f"🧱 <i>{pm['ob_ctx']['note']}</i>")
        L.append(f"⚖️ <i>{len(pm['pro'])} دلیل تارگت / {len(pm['con'])} دلیل استاپ"
                 + (f" — مهم‌ترین: {pm['pro'][0]}" if pm["pro"] else "") + "</i>")
        if pm["con"]:
            L.append(f"⚠️ <i>ریسک شمرده‌شده: {pm['con'][0]}</i>")
        # منشور LIAM بند ۱۹: هر سیگنال باید بگوید چه چیزی باطلش می‌کند
        L.append(f"⛔ <i>باطل‌کننده: بسته‌شدن {s.get('tf','15m')} "
                 f"{'زیر' if s['dir'] == 'LONG' else 'بالای'} "
                 f"<code>{s['sl']:.10g}</code> — فرضیه شکست خورده، نه بدشانسی</i>")
    # قانون تریل حمید — روی خود پیام، تا مو به مو همان اجرا شود.
    #
    # ارتقای ۶ سپتامبر: رَجِ قبلی («⅓ مسیر → استاپ روی سربه‌سرِ کارمزددار»)
    # طبق تعریف هر برگشتی را در خالصِ صفر می‌بست — ۸۳.۲٪ از تریل‌های
    # سیگنال‌گرید ≈صفر شدند. جایگزینش همان قاعده‌ای است که بازوی g80 روی
    # همین معامله‌ها سنجید و PROMOTE گرفت (+۰.۲۱۹۹R، CI [+۰.۱۱۹,+۰.۳۲۱]،
    # n=۲۲۱؛ صفرشده ۳۶.۷٪ → ۱۴.۹٪).
    #
    # این متن و `paper.PROD_TRAIL_FRAC` باید همیشه یکی بمانند — پیام
    # صریحاً می‌گوید «دفتر کاغذی همین را حساب می‌کند»، پس واگرایی‌شان
    # یعنی دفتر چیزی را می‌سنجد که حمید اجرا نمی‌کند. محافظ:
    # `test_trail_arms` سهم را از خودِ همین دو جا می‌خواند.
    if s.get("tp1") and s.get("entry"):
        try:
            from hamid.paper import PROD_TRAIL_FRAC as _F
        except Exception:                            # noqa: BLE001
            _F = 0.80
        at_tp1 = s["entry"] + (s["tp1"] - s["entry"]) * _F
        L.append(f"🪜 <i>قانون تریل: تا وقتی سود از کارمزد نگذشته، استاپ "
                 f"دست نمی‌خورد. بعد از آن، استاپ را روی "
                 f"<b>{_F:.0%} بهترین سودی که تا حالا دیده شده</b> بگذار و "
                 f"فقط بالاتر ببر، هرگز پایین‌تر. نمونه: اگر قیمت تا تارگت۱ "
                 f"برود، استاپ می‌شود <code>{at_tp1:.10g}</code>. "
                 f"دفتر کاغذی همین را خودکار حساب می‌کند.</i>")
    # هم‌زمانی — قیمت لحظهٔ ارسال از کندل ۵ دقیقه، تا حمید ببیند ورود نگذشته
    sy = s.get("sync")
    if sy:
        L.append(f"⏱ <i>قیمت لحظهٔ ارسال <code>{sy['price']:.10g}</code> — "
                 f"فاصله تا ورود {sy['dist_pct']:+}٪</i>")
    # ساعت تحلیل و ساعت ارسال، به وقت ایران — تا تأخیر قابل راستی‌آزمایی باشد
    an = s.get("analyzed_at")
    L.append((f"🕐 تحلیل <code>{tehran(an)}</code> · " if an else "🕐 ")
             + f"ارسال <code>{tehran()}</code> — به وقت ایران")
    # حکم شورای ققنوس — مشاوره‌ای؛ اعداد سیگنال همان‌اند که دروازه‌ها دادند
    if s.get("phoenix"):
        try:
            from hamid import phoenix as _phx
            L += _phx.caption_lines(s["phoenix"])
        except Exception:                            # noqa: BLE001
            pass
    L.append("")
    L.append(f"ورود    <code>{s['entry']:.10g}</code>")
    L.append(f"استاپ   <code>{s['sl']:.10g}</code>")
    L.append(f"تارگت۱  <code>{s['tp1']:.10g}</code>")
    if s.get("tp2") is not None:
        L.append(f"تارگت۲  <code>{s['tp2']:.10g}</code>")
    line = f"ریسک/ریوارد <b>{s['rr']}</b>"
    if s.get("conf") is not None:
        line += f" · اعتماد <b>{s['conf']}%</b>"
    if s.get("ev") is not None:
        line += f" · انتظار <b>{s['ev']:.2f}R</b>"
    if s.get("quality") is not None:
        line += f" · کیفیت <b>{s['quality']}</b>"
    L += ["", line]
    if s.get("ob"):
        L.append(f"اردر بلاک <code>{s['ob']['low']:.10g} — {s['ob']['high']:.10g}</code>")
    if s.get("channel"):
        L.append(f"کانال {s['channel']['dir']} ({s['channel']['drift']}%)")
    bits = []
    if s.get("fvg"):
        bits.append("FVG هم‌جهت ✓")
    if s.get("level"):
        bits.append(f"روی {'مقاومت' if s['level']['type']=='R' else 'حمایت'} "
                    f"({s['level']['touches']} برخورد)")
    if s.get("swept"):
        bits.append(f"نقدینگی جمع شد ({s['swept']['n']} برخورد)")
    if s.get("adx") is not None:
        bits.append(f"ADX {s['adx']}")
    if bits:
        L.append(" · ".join(bits))
    # بلوک سفارشِ آماده‌کپی (دستور حمید ۲۴ اوت) — همین پیام باید بدون
    # حساب‌کردنِ دستی به یک سفارش لیمیت تبدیل شود. نبودِ بلوک یعنی یکی از
    # دروازه‌ها (هندسهٔ استاپ، محافظ لیکویید، دام کارمزد) عبور نکرده؛
    # سیگنال هنوز خبر است، ولی دستورِ سفارش نیست.
    try:
        from hamid import order_ticket as OT
        L += OT.lines(OT.ticket(s))
    except Exception as e:                       # noqa: BLE001
        # هیچ خطایی حق ندارد جلوی خودِ سیگنال را بگیرد (دستور «بدون تأخیر»).
        print(f"telegram: بلوک سفارش ساخته نشد — {e}", flush=True)
    # منبع کندل و نماد چارت (دستور حمید ۲ سپتامبر: «در تریدینگ‌ویو صرافی
    # بیت‌یونیکس و ارز پرپچوال را انتخاب کن»). نماد پرپ بیت‌یونیکس در
    # تریدینگ‌ویو به شکل BITUNIX:<SYM>.P است؛ منبعِ واقعیِ کندل هم چاپ می‌شود
    # تا اگر پشتیبان (MEXC/اسپات) جای بیت‌یونیکس نشسته بود، حمید ببیند.
    src = s.get("candle_src") or _candle_trace().get("candle_src") or "نامعلوم"
    L += ["", f"📈 <i>چارت: <code>BITUNIX:{s['sym']}.P</code> (تریدینگ‌ویو، پرپچوال) · "
              f"کندل تحلیل: <code>{src}</code> — قبل از ورود خودت هم چارت را ببین.</i>"]
    # Each strategy carries its own measured record. Attaching one strategy's
    # win rate to another's signal would be worse than attaching none: it reads
    # as evidence and is not. A signal that supplies no footer gets the figure
    # measured for the original engine, which is the only one it can be.
    L.append(s.get("footer") or
             "<i>وین‌ریت اندازه‌گیری‌شدهٔ این استراتژی روی کندل واقعی ۲۲.۷٪ با انتظار +۰.۰۶۹R "
             "است: بردها بزرگ‌اند و بیشتر تریدها استاپ می‌خورند. سایز را ثابت نگه دار.</i>")
    return "\n".join(L)


def send_text(text, quiet=True):
    """یک پیام متنی با امضای پنل — برای پاسبان‌ها و آلارم‌های غیرسیگنالی.

    عیب ۲۳ اوت: پاسبان پوزیشنِ مانده `TG.send_text` را صدا می‌زد که اصلاً
    وجود نداشت؛ آلارمش هر چرخه با AttributeError بی‌صدا می‌مرد و آزمونش هم
    نمی‌گرفت چون تلگرام را جعلی کرده بود. حالا رابط واقعی این‌جاست و آزمون،
    وجودِ همین تابع را روی ماژول واقعی می‌سنجد.

    امضای پنل (دستور ۱۶ اوت) اگر در متن نبود، اضافه می‌شود."""
    token, chat = creds()
    if not token:
        if not quiet:
            print("telegram: بدون کلید — پیام نرفت")
        return False
    if PANEL_NAME not in text:
        text = f"{text}\n{BRAND}"
    r = _post(token, "sendMessage",
              {"chat_id": chat, "text": text, "parse_mode": "HTML"})
    return bool(r)


# ── نردبان سخت‌گیری بعد از سیگنال پنجم (دستور حمید، ۲۷ اوت) ─────────────
#
# پنج سیگنال اول: هیچ آستانهٔ اضافه‌ای — همان دروازه‌های سخت همیشگی
# (روند، بازجویی، هم‌زمانی، ضدتکرار، کارمزد) کافی‌اند.
# از ششم به بعد هر ارسال یک پله: اطمینان و انتظارِ لازم بالا می‌رود.
LADDER_FREE = 5          # تا این تعداد، بی‌آستانهٔ اضافه
# بازکالیبرهٔ ۲۹ اوت — دستور حمید: «ارسال سیگنال در روز را به روزی ۲۴
# سیگنال افزایش بده، با همین روشی که الان داری انجام می‌دهی.»
#
# روشِ نردبان دست‌نخورده ماند (همان دستور ۲۷ اوت: از ششم به بعد سخت‌تر)؛
# فقط شیبش با هدفِ تازه هم‌قد شد. حساب: ۲۴ سیگنال در روز یعنی میانگین ۶
# در هر پنجرهٔ ۶ ساعتهٔ ضدتکرار. با شیب قبلی (۶٪ و ۰.۰۸R به‌ازای هر پله)
# در ارسال دوازدهمِ یک پنجره کفِ اطمینان به ۴۸٪ و انتظار به ۰.۶۴R می‌رسید
# — یعنی نردبان قبل از رسیدن به هدفِ روزانه عملاً می‌بست. اندازه‌گیری:
# دفتر ۷۲ ساعت اخیر ۴۰ ارسال داشت (~۱۳ در روز)، نه ۲۴.
#
# شیب نصف شد تا مسیرِ نردبان تا حدود ۲۴ کشیده شود، نه ۱۲. سقف‌ها همان
# ماندند، چون کارشان «در بسته نشود» است نه تعیین نرخ.
LADDER_CONF_STEP = 3     # هر پله چند درصد به کف اطمینان اضافه کند
LADDER_EV_STEP = 0.04    # هر پله چند R به کف انتظار اضافه کند
LADDER_CONF_MAX = 72     # سقف کف اطمینان — در بسته نمی‌شود
LADDER_EV_MAX = 0.80

# سقف سختِ روزانه (دستور ۲۹ اوت). نردبان نرخ را می‌سازد؛ این فقط
# پشت‌بندِ عددی است تا در یک روزِ پرنوسان از خواستهٔ حمید رد نشود.
DAILY_CAP = 24


def _sent_in(sent, hours):
    """شمار ارسال‌های واقعی در پنجرهٔ گذشته (کلیدهای کمکی حساب نمی‌شوند)."""
    lo = time.time() * 1000 - hours * 3600 * 1000
    return sum(1 for k, t in sent.items()
               if not k.startswith(("any|", "skip|", "pair|")) and t >= lo)


def _archive_sent_in(hours, now_ms=None):
    """شمار ارسال‌های واقعیِ پنجرهٔ گذشته از آرشیو شماره‌دار (append-only).

    عیبِ اندازه‌گیری‌شدهٔ ۲ سپتامبر: حافظهٔ ضدتکرار (`sent`) هر کلید را
    فقط `TTL_MS` (۶ ساعت) نگه می‌دارد، پس `_sent_in(sent, 24)` هرگز بیش از
    ۶ ساعت را نمی‌دید و «سقف ۲۴ در ۲۴ ساعت» عملاً «۲۴ در ۶ ساعت» بود —
    یعنی هیچ‌وقت نمی‌بست. شمارش: ۳۳ ارسال یکتا (tg_msg_id) در ۲۴ ساعتِ
    منتهی به ۱۰:۰۴ UTC، در برابر سقف ۲۴. آرشیو روزانه تنها دفتری است که
    ۲۴ ساعت را کامل دارد؛ ردیف یکتا با tg_msg_id (یا at+sym) شمرده
    می‌شود تا ثبتِ دوباره سقف را ساختگی پر نکند."""
    now_ms = now_ms or time.time() * 1000
    lo = now_ms - hours * 3600 * 1000
    days = {time.strftime("%Y%m%d", time.gmtime(t / 1000))
            for t in (lo, now_ms, (lo + now_ms) / 2)}
    seen = set()
    for day in sorted(days):
        f = ARCHIVE_DIR / f"telegram-sent-{day}.jsonl"
        if not f.exists():
            continue
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except Exception:                    # noqa: BLE001
                    continue
                if not isinstance(r, dict):
                    continue
                at = r.get("at")
                if not isinstance(at, (int, float)) or at < lo or at > now_ms:
                    continue
                seen.add(r.get("tg_msg_id") or (int(at), r.get("sym")))
        except Exception:                            # noqa: BLE001 - آرشیو ناخوانا = شمارش صفر از این منبع
            continue
    return len(seen)


def _sent_in_24h(sent):
    """شمارِ سقف روزانه = بیشینهٔ حافظهٔ ۶ساعته و آرشیو ۲۴ساعته.

    هیچ‌کدام تنها کافی نیست: حافظه ۶ ساعت بیشتر یادش نمی‌ماند، و آرشیوِ
    چک‌اوتِ رانر می‌تواند چند دقیقه از ریموت عقب باشد. بیشینه یعنی
    هیچ ارسالِ دیده‌شده‌ای از شمارش نمی‌افتد."""
    return max(_sent_in(sent, 24), _archive_sent_in(24))


def ladder_bar(n_sent):
    """آستانهٔ لازم برای سیگنال بعدی، بر پایهٔ تعداد ارسالِ پنجرهٔ ۱۲ ساعته."""
    step = max(0, int(n_sent) - LADDER_FREE + 1) if n_sent >= LADDER_FREE else 0
    return {"step": step,
            "min_conf": min(LADDER_CONF_MAX, step * LADDER_CONF_STEP),
            "min_ev": min(LADDER_EV_MAX, round(step * LADDER_EV_STEP, 3))}


def passes_ladder(s, bar):
    """آیا این سیگنال از پلهٔ فعلی رد می‌شود؟

    نکتهٔ صداقت: سیگنالی که اصلاً `conf`/`ev` ندارد (مسیر آلارم/رادار)
    عددی برای سنجش ندارد؛ از پلهٔ سوم به بعد چنین سیگنالی نگه داشته
    می‌شود، چون در ازدحام، «نمی‌دانم» به‌اندازهٔ «ضعیف» است."""
    if bar["step"] <= 0:
        return True
    conf, ev = s.get("conf"), s.get("ev")
    if conf is None and ev is None:
        return bar["step"] < 3
    if conf is not None and conf < bar["min_conf"]:
        return False
    if ev is not None and ev < bar["min_ev"]:
        return False
    return True


def _fomo_trace(sym):
    """ردپای اتاق فومو روی دفتر سیگنال (۲ سپتامبر) — فقط از عکس‌فوری، بدون شبکه.

    دو فیلد: fomo_heat (داغی جمعیت ۰–۱۰۰) و fomo_witness (شاهد اپ fomo در
    ۲۴ ساعت اخیر برای همین نماد). هیچ‌کدام در امتیاز یا دروازه نیست؛ ماشین
    بونفرونی شبانه (paper.CONDITIONS) اثرشان را می‌سنجد. نبودِ عکس‌فوری =
    None، نه صفر (قانون ۱)."""
    try:
        from hamid import fomo as _fomo
        return _fomo.snapshot_for(sym)
    except Exception:                                # noqa: BLE001 - ردپا هرگز ارسال را نمی‌کشد
        return {"fomo_heat": None, "fomo_witness": None}


def _candle_trace():
    """منبع کندلی که این سیگنال رویش ساخته شد (۲ سپتامبر، سوییچ پرپ).

    `candle_src`: شناسهٔ صرافی از `sources.used()` — مثلاً bitunix-perp یا
    mexc (اسپات). دفتر تاریخی روی اسپات است؛ بدون این ردپا، ماشین شبانه دو
    بازار را در یک نمونه قاطی می‌کرد (کلاسِ عیبِ «دو تعریف در یک نمونه»)."""
    try:
        import sources as _src
        return {"candle_src": _src.used().get("klines")}
    except Exception:                                # noqa: BLE001 - ردپا هرگز ارسال را نمی‌کشد
        return {"candle_src": None}


def _sym_class(sym):
    """کلاسِ نماد برای ردپای دفتر — خطایش هرگز ارسال را نمی‌خواباند."""
    try:
        from hamid.universe import sym_class
        return sym_class(sym)
    except Exception:                                # noqa: BLE001
        return None


def _phoenix_trace(s):
    """ردپای شورای ققنوس روی دفتر (۲ سپتامبر شب): امتیاز، برچسب، رأی ۱۲ مراقب.

    مشاوره‌ای است (قانون ۰۳): ماشین شبانه اثرش را می‌سنجد؛ دروازه نیست."""
    try:
        from hamid import phoenix as _phx
        return _phx.trace(s.get("phoenix"))
    except Exception:                                # noqa: BLE001 - ردپا هرگز ارسال را نمی‌کشد
        return {"phoenix_score": None, "phoenix_label": None, "phoenix_votes": None}


def _news_trace(sym, direction):
    """ردپای نظرسنجی خبر روی دفتر سیگنال (۲ سپتامبر) — فقط از عکس‌فوری، بدون شبکه.

    news_align = with/against/none نسبت به اجماعِ وزن‌دارِ ایجنت‌ها. دستور
    حمید: خبر فقط دیدگاه است؛ این‌جا هیچ امتیاز/دروازه‌ای نمی‌سازد، فقط
    ماشین شبانه (paper.CONDITIONS) اثرش را می‌سنجد."""
    try:
        from hamid import news_poll as _np
        return _np.trace_for(sym, direction)
    except Exception:                                # noqa: BLE001 - ردپا هرگز ارسال را نمی‌کشد
        return {"news_align": None, "news_bias_w": None}


FROZEN_MIN_EXPIRED = 2    # آستانه — پایین‌تر توضیح داده و اندازه گرفته شده


def _frozen_entries():
    """(ارز، ورود) → چند بار همان ورودِ دقیق منقضی شده (پر نشده).

    پروندهٔ LOKAUSDT (۵ سپتامبر، شکایت حمید «اصلاً منطقی نیست»): از ۲۳
    اوت **نُه بار** سیگنال شد، هر بار با ورودِ دقیقاً یکسان ۰.۱۲۳۶، و هر
    نُه بار `expired` — یعنی قیمت هرگز به ورود نرسید. ضدتکرارِ موجود
    نمی‌گرفتش چون پنجره‌هایش ۳ و ۶ ساعت است و این ارسال‌ها ۱۴+ ساعت
    فاصله داشتند.

    ### چرا آستانه ۲ است، نه ۱ و نه ۳ — با شمارش، نه سلیقه

    روی کل دفتر بسته (n=۴۸٬۷۳۲ ردیفِ دارای ورودِ عددی)، هر معامله بر
    اساس «چند بار همین (ارز، ورود) **قبلاً** منقضی شده» دسته شد:

    | منقضیِ قبلی | n | نرخ انقضا | R پرشده‌ها (CI95) |
    |---|---|---|---|
    | ۰ | ۴۶٬۰۸۳ | **۶.۳٪** | +۰.۰۶۳ [+۰.۰۵۱, +۰.۰۷۴] |
    | ۱ | ۱٬۲۸۸ | **۸۴.۵٪** | +۰.۲۳۵ [+۰.۰۸۱, +۰.۳۹۰] |
    | ۲ | ۶۳۳ | **۸۵.۰٪** | +۰.۱۵۳ [−۰.۰۳۰, +۰.۳۳۷] |
    | ۳+ | ۷۲۸ | **۸۸.۳٪** | +۰.۰۹۷ [−۰.۱۳۱, +۰.۳۲۴] |

    دو چیز را با هم می‌گوید:

    ۱. ورودِ تکرارشده ~۱۳ برابرِ ورودِ تازه احتمال دارد اصلاً پر نشود.
    ۲. ولی آن‌هایی که **با یک انقضای قبلی** پر می‌شوند هنوز لبهٔ واقعی
       دارند (CI کاملاً بالای صفر). پس بستنِ آستانه روی ۱، لبهٔ مثبت را
       دور می‌ریزد.

    از ۲ به بعد CI صفر را در بر می‌گیرد — یعنی ۸۵٪ نویز دیگر چیزی
    نمی‌خرد. **آستانه دقیقاً همان‌جا گذاشته شد که داده گفت.**

    ### مرزِ این دروازه

    این دروازهٔ **تحویل** است نه استراتژی: ستاپ ساخته و ارزیابی و در دفتر
    ثبت می‌شود؛ فقط دوباره برای حمید فرستاده نمی‌شود. هم‌خانوادهٔ
    ضدتکرارِ ۳ و ۶ ساعته، که آن‌ها هم دروازهٔ تحویل‌اند. هیچ آستانهٔ
    تصمیمی عوض نشد (قانون ۰۳).
    """
    counts = {}
    try:
        from hamid import paper as _p
        for t in _p._read(_p.CLOSED):
            if t.get("outcome") != "expired":
                continue
            e = t.get("entry")
            if isinstance(e, (int, float)):
                k = (t.get("sym"), round(float(e), 10))
                counts[k] = counts.get(k, 0) + 1
    except Exception as e:                           # noqa: BLE001 - دفتر ناخوانا = دروازهٔ خاموش
        print(f"telegram: دفتر ستاپ یخ‌زده خوانده نشد ({type(e).__name__}) — "
              "دروازه خاموش می‌ماند", flush=True)
    return counts


def send_signals(signals, render_chart, limit=8):
    """render_chart(setup, path) -> path, or None when a chart cannot be drawn."""
    token, chat = creds()
    if not token:
        print("telegram: no TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID — nothing sent", flush=True)
        return 0
    sent = _load_sent()
    now_ms = time.time() * 1000
    # ضدتکرار بین‌استراتژی — شکایت حمید: همان ستاپ یک بار با برچسب اسکن و
    # یک بار با برچسب آلارم می‌رسید؛ کلید بدون استراتژی با پنجرهٔ ۳ ساعته.
    def _dup_any(s):
        return now_ms - sent.get(f"any|{s['sym']}|{s['tf']}|{s['dir']}", 0) < 3 * 3600 * 1000

    def _dup_pair(s):
        # ضدتکرارِ بین‌تایم‌فریمی — عیب اندازه‌گیری‌شدهٔ ۲۷ اوت: TRX شورت
        # ۵د ساعت ۰۵:۱۸ و همان TRX شورت ۱۵د سه دقیقه بعد؛ ZEC لانگ ۵د و
        # ۲۸ دقیقه بعد ۱۵د. کلیدهای قبلی همه tf را داخل خود داشتند، پس
        # «همان معامله روی تایم دیگر» سیگنال تازه حساب می‌شد و حمید یک
        # ستاپ را دو بار می‌گرفت. حالا همان (ارز، جهت) — با هر تایم و هر
        # استراتژی — تا ۳ ساعت فقط یک بار می‌رود.
        return now_ms - sent.get(f"pair|{s['sym']}|{s['dir']}", 0) < 3 * 3600 * 1000

    def _sym_worn(s):
        # تنوع (شکایت حمید): یک ارز حداکثر ۲ بار در پنجره — کانال باید
        # بازار را بگردد، نه دور یک ارز بچرخد. (سقف ۳ که امروز صبح
        # امتحان شد همان چیزی بود که PAXGِ دوم را رد کرد — برگشت به ۲.)
        return sum(1 for k in sent if k.startswith(f"any|{s['sym']}|")) >= 2
    def _stable(s):
        # استیبل/رپد سیگنال نمی‌شود — کشف ۱۲ اوت: RLUSD دو جای سهمیهٔ ۱۶تایی
        # را سوزاند. حرکت استیبل چند صدم درصد است؛ «سیگنال» رویش یعنی سهمیهٔ
        # کمتر برای ارز واقعی. همان فیلتر دفتر کاغذی، این‌جا در گلوگاه ارسال.
        #
        # ۶ سپتامبر: از فهرستِ دست‌نویس به کلاسِ مشتق منتقل شد. فهرست
        # `WETH` را داشت ولی `WBETH` را نه، و WBETHUSDT رد شد. حالا
        # `universe.structureless` کلاس را از خودِ نماد درمی‌آورد
        # (اثبات: ۸۷۹ نماد واقعی، ۱۵ غیرکریپتو، صفر مثبتِ کاذب).
        try:
            from hamid.universe import structureless
            return structureless(s["sym"])
        except Exception:                            # noqa: BLE001
            return False

    _frozen = _frozen_entries()

    def _frozen_setup(s):
        """ستاپِ یخ‌زده: همین ورودِ دقیق قبلاً ۲+ بار منقضی شده."""
        try:
            return _frozen.get((s["sym"], round(float(s["entry"]), 10)), 0) \
                >= FROZEN_MIN_EXPIRED
        except Exception:                            # noqa: BLE001
            return False
    # دروازهٔ تایم‌فریم — دستور صریح حمید (۲۶ اوت شب): فقط ۱۵د و ۵د.
    off_tf = [s for s in signals if s.get("tf") not in ALLOWED_TFS]
    for s in off_tf:
        print(f"  دروازهٔ تایم‌فریم: {s.get('sym')} {s.get('tf')} رد شد — "
              f"ارسال فقط در ۵د/۱۵د (دستور ۲۶ اوت)", flush=True)
    signals = [s for s in signals if s.get("tf") in ALLOWED_TFS]
    # ── رزروِ درون-دسته (عیب اندازه‌گیری‌شدهٔ ۱ سپتامبر) ──────────────────
    #
    # تا امشب این یک list-comprehension بود و **همهٔ** شرط‌ها را روی یک
    # عکسِ منجمدِ `sent` می‌سنجید. یعنی دو ستاپ از یک (ارز، جهت) روی دو
    # تایم مختلف، هر دو رد می‌شدند چون هیچ‌کدام هنوز در `sent` نبود —
    # نوشتنِ کلیدها در حلقهٔ ارسال (پایین‌تر) اتفاق می‌افتد، بعد از این
    # فیلتر. پس `pair|` فقط بین **اجراها** محافظت می‌کرد، نه داخل یک دسته.
    #
    # همان چیزی که این کلید ۲۷ اوت برایش ساخته شد (TRX ۵د و ۱۵د با سه
    # دقیقه فاصله) دوباره اتفاق افتاد: BTCUSDT لانگ ۵د ساعت ۰۷:۲۷:۵۸ و
    # BTCUSDT لانگ ۱۵د ساعت ۰۷:۲۸:۱۶ — ۱۸ ثانیه، همان دسته.
    #
    # حالا هر ستاپِ پذیرفته‌شده کلیدهایش را **همان لحظه برای بقیهٔ دسته**
    # رزرو می‌کند. رزرو در `sent` نوشته نمی‌شود: اگر ستاپ بعداً با نردبان
    # یا سقف روزانه بیفتد، رزرو با همین دسته می‌میرد و سیگنالی که نرفته
    # خفه نمی‌شود.
    claim_any, claim_pair, claim_sym = set(), set(), {}

    def _claimed(s):
        if f"{s['sym']}|{s['tf']}|{s['dir']}" in claim_any:
            return True
        if f"{s['sym']}|{s['dir']}" in claim_pair:
            return True
        prior = sum(1 for k in sent if k.startswith(f"any|{s['sym']}|"))
        return prior + claim_sym.get(s["sym"], 0) >= 2

    fresh = []
    for s in signals:
        if _frozen_setup(s):
            n_fr = _frozen.get((s["sym"], round(float(s["entry"]), 10)), 0)
            print(f"  دروازهٔ ستاپ یخ‌زده: {s['sym']} @ {s['entry']} رد شد — "
                  f"همین ورود قبلاً {n_fr}× منقضی شده (نرخ انقضا ۸۵٪ روی "
                  f"n=۱۳۶۱؛ پروندهٔ LOKA ۵ سپتامبر)", flush=True)
            continue
        if (_key(s) in sent or f"skip|{_key(s)}" in sent
                or _dup_any(s) or _dup_pair(s)
                or _sym_worn(s) or _stable(s) or _claimed(s)):
            continue
        fresh.append(s)
        claim_any.add(f"{s['sym']}|{s['tf']}|{s['dir']}")
        claim_pair.add(f"{s['sym']}|{s['dir']}")
        claim_sym[s["sym"]] = claim_sym.get(s["sym"], 0) + 1
        if len(fresh) >= limit:
            break
    if not fresh:
        print(f"telegram: {len(signals)} signals, all already sent", flush=True)
        return 0
    # نردبان سخت‌گیری — دستور صریح حمید (۲۷ اوت):
    #
    #   «کاری به نرخ عادی ندارم. تا زمانی که سیگنال هست باید سیگنال بده،
    #    ولی بعد از ارسال سیگنال پنجم یک‌کمی ایجنت‌ها شرایط را برای
    #    سیگنال‌های بعدی سخت‌تر می‌کنند.»
    #
    # پس دیگر «سهمیهٔ روز» و «تور ایمنی ۴۰» وجود ندارد — هیچ سقف عددی
    # جلوی سیگنالِ واجدشرایط را نمی‌گیرد. به جایش از سیگنال ششم به بعد،
    # هر سیگنالِ اضافه آستانه را یک پله بالا می‌برد: اطمینان و انتظار
    # (ev) بیشتری لازم می‌شود. پله‌ها خطی‌اند و سقف دارند تا از یک جایی
    # به بعد عملاً فقط ستاپ‌های عالی رد شوند — نه اینکه در بسته شود.
    # سقف سختِ روزانه — دستور ۲۹ اوت: روزی ۲۴ سیگنال
    # شمارش از آرشیو ۲۴ساعته هم می‌آید، نه فقط از حافظهٔ ۶ساعته (رفع ۲ سپتامبر)
    n_day = _sent_in_24h(sent)
    if n_day >= DAILY_CAP:
        print(f"telegram: سقف روزانه پر است ({n_day}/{DAILY_CAP} در ۲۴ ساعت) — "
              f"{len(fresh)} سیگنال تا بازشدن پنجره نگه داشته شد", flush=True)
        return 0
    room = DAILY_CAP - n_day
    if len(fresh) > room:
        print(f"telegram: {len(fresh) - room} سیگنال به سقف روزانه نخورد "
              f"({n_day}/{DAILY_CAP} رفته)", flush=True)
        fresh = fresh[:room]

    n_sent_real = len([k for k in sent if not k.startswith(("any|", "skip|", "pair|"))])
    bar = ladder_bar(n_sent_real)
    if bar["step"] > 0:
        keep = [s for s in fresh if passes_ladder(s, bar)]
        if len(keep) < len(fresh):
            print(f"telegram: نردبان سخت‌گیری پلهٔ {bar['step']} "
                  f"({n_sent_real} ارسال در ۱۲ ساعت · اطمینان ≥{bar['min_conf']}٪ "
                  f"· انتظار ≥{bar['min_ev']:.2f}R) — "
                  f"{len(fresh) - len(keep)} سیگنالِ ضعیف‌تر نگه داشته شد", flush=True)
        fresh = keep
        if not fresh:
            return 0

    ok = 0
    tmp = Path(__file__).resolve().parent / ".charts"
    tmp.mkdir(exist_ok=True)
    for s in fresh:
        # هم‌زمانی با نقطهٔ ورود — شکایت حمید: سیگنال یا از ورود رد شده بود
        # یا فاصلهٔ زیادی داشت. همین لحظه آخرین کندل ۵ دقیقه خوانده می‌شود؛
        # ردشده یا دورتر از حد → ارسال نمی‌شود، بی‌استثنا.
        try:
            import sources as _src0
            _k5 = _src0.klines(s["sym"], "5m", 3)
            _px = float(_k5[-1][4])
        except Exception as e:                        # noqa: BLE001
            _px = None
            print(f"  قیمت لحظهٔ {s['sym']} در دسترس نبود ({type(e).__name__}) — "
                  f"دروازهٔ هم‌زمانی رد شد", flush=True)
        # دروازهٔ روند (دستور حمید ۱۷ اوت): سیگنال خلاف چارت ممنوع.
        # هر دو تایم بالا مخالف → وتو؛ یکی مخالف → فقط با تمام تأییدیه‌ها.
        try:
            import sources as _src_t
            from hamid import trend_gate as _tg_gate
            _ta = _tg_gate.assess(
                s["sym"], s["dir"],
                lambda sym, tf, n: [
                    {"t": k[0], "o": float(k[1]), "h": float(k[2]),
                     "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                    for k in _src_t.klines(sym, tf, n)],
                evidence=s)
            s["trend4"], s["trend1"] = _ta["t4"], _ta["t1"]
            s["trend_mode"] = _ta["mode"]
            if not _ta["ok"]:
                print(f"  دروازهٔ روند {s['sym']} {s['dir']}: {_ta['reason']}",
                      flush=True)
                sent[f"skip|{_key(s)}"] = now_ms
                continue
            _cl = _tg_gate.caption_line(_ta)
            if _cl:
                s["counter_trend_note"] = _cl
        except Exception as _e:                      # noqa: BLE001
            # دادهٔ روند در دسترس نیست = قانون ۱: NO_SIGNAL، نه عبورِ کور
            print(f"  دروازهٔ روند {s['sym']}: {type(_e).__name__} — "
                  f"دادهٔ ناقص، ارسال نشد", flush=True)
            continue
        if _px is not None and s.get("entry") and s.get("sl"):
            _stop_frac = abs(s["entry"] - s["sl"]) / s["entry"]
            _signed = ((_px - s["entry"]) / s["entry"] if s["dir"] == "LONG"
                       else (s["entry"] - _px) / s["entry"])
            if _signed < -0.5 * _stop_frac:
                print(f"  ⏱ {s['sym']} صادر نشد — قیمت از نقطهٔ ورود رد شده "
                      f"({_signed*100:+.2f}٪ به سمت استاپ)؛ سیگنالِ دیر نمی‌فرستیم", flush=True)
                sent[f"skip|{_key(s)}"] = now_ms
                continue
            if _signed > 0.025:
                print(f"  ⏱ {s['sym']} صادر نشد — فاصله تا ورود {_signed*100:.2f}٪ "
                      f"است؛ سیگنال ناهم‌زمان نمی‌فرستیم", flush=True)
                sent[f"skip|{_key(s)}"] = now_ms
                continue
            s["sync"] = {"price": _px, "dist_pct": round(_signed * 100, 2)}
        # بازجویی پیش از صدور — قانون حمید: اول در ۱۵ دقیقه ببین چه چیزهایی
        # می‌تواند استاپت کند؛ فقط با دلایلِ تارگتِ بیشتر صادر کن. سیگنالِ
        # ردشده به دفتر vetoed می‌رود تا خود دروازه نمره بگیرد. خطای زیرساخت
        # (شبکه/ایمپورت) جلوی ارسال را نمی‌گیرد — دروازه تحلیل است نه بهانه.
        try:
            import sources as _src
            from hamid import premortem as _pm
            _c15 = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
                    for k in _src.klines(s["sym"], "15m", 120)]
            pm = _pm.review(s, _c15) if len(_c15) >= 40 else None
        except Exception as e:                        # noqa: BLE001
            pm = None
            print(f"  بازجویی {s['sym']} در دسترس نبود ({type(e).__name__}) — "
                  f"سیگنال بدون دروازه می‌رود", flush=True)
        if pm:
            s["premortem"] = pm
            if not pm["issue"]:
                print(f"  ⚖️ {s['sym']} صادر نشد — {len(pm['con'])} دلیل استاپ در برابر "
                      f"{len(pm['pro'])} دلیل تارگت: {pm['con'][0] if pm['con'] else ''}",
                      flush=True)
                sent[f"skip|{_key(s)}"] = time.time() * 1000  # ضدتکرار بازجویی، بدون خوردن سهمیه
                try:
                    from hamid import paper as _paper
                    _paper.open_from([{"symbol": s["sym"], "dir": s["dir"],
                                       "entry": s["entry"], "sl": s["sl"],
                                       "tp1": s.get("tp1") or s["entry"],
                                       "tp2": s.get("tp2"), "stage_tag": "vetoed",
                                       # دفتر کنترل هم بی‌تایم‌فریم بود — گروه
                                       # کنترلی که تایم‌فریمش را نداند، با گروه
                                       # آزمایش قابل‌مقایسه نیست (۳۰ اوت)
                                       "tf": s.get("tf")}],
                                     {"veto_why": "premortem", "pm_con": pm["con"][:3],
                                      "pm_pro": pm["pro"][:3],
                                      "pattern_align": (pm.get("patterns") or {}).get("align"),
                                      "patterns": (pm.get("patterns") or {}).get("by_tf"),
                                      "fib_ratio": pm.get("fib"),
                                      # ردپای اتاق فومو (۲ سپتامبر) — فقط ثبت برای
                                      # سنجش شبانه؛ از عکس‌فوری، بدون شبکه
                                      **_fomo_trace(s["sym"]),
                                      **_news_trace(s["sym"], s["dir"]), **_candle_trace(), **_phoenix_trace(s),
                                  # کلاسِ نماد (۶ سپتامبر — «در شناسایی
                                  # ارزها دقت بیشتری بکن»). فقط ردپا: طلای
                                  # توکنی (XAUT/PAXG) بسته نمی‌شود چون n=۲۴
                                  # و میانگین +۰.۰۱۶R هیچ‌چیز را اثبات
                                  # نمی‌کند. ماشین شبانه با همین فیلد
                                  # می‌سنجدش؛ بستنش فقط با CI و تأیید حمید.
                                  "sym_class": _sym_class(s["sym"]),
                                      **(pm.get("tv") or {})})
                    from hamid import memory as _mem
                    _mem.remember("بررسی", s["sym"],
                                  f"بازجویی ۱۵د جلوی {s['sym']} {s['dir']} را گرفت: "
                                  + "؛ ".join(pm["con"][:2]))
                except Exception:                     # noqa: BLE001
                    pass
                continue
        # شورای ققنوس (دستور حمید، ۲ سپتامبر شب): ۱۲ مراقب زودیاک سیگنال را
        # می‌بینند و ققنوس حکم وزنی می‌دهد. حکم روی کپشن و دفتر می‌نشیند و
        # شبانه سنجیده می‌شود؛ هیچ سیگنالی را حذف و هیچ عددی را عوض نمی‌کند
        # (قانون ۰۳/۱۲). خطای شورا جلوی ارسال را نمی‌گیرد.
        try:
            from hamid import phoenix as _phx
            s["phoenix"] = _phx.judge(s, write=True)
            print(f"  🔥 ققنوس {s['sym']}: {s['phoenix']['label']} ({s['phoenix']['score']:+.2f}) — "
                  f"{s['phoenix']['posture']}", flush=True)
        except Exception as e:                        # noqa: BLE001
            s["phoenix"] = None
            print(f"  ققنوس {s['sym']} رأی نداد ({type(e).__name__}) — سیگنال بی‌حکم می‌رود", flush=True)
        png = None
        try:
            png = render_chart(s, str(tmp / f"{s['sym']}-{s['tf']}.png"))
        except Exception as e:                        # noqa: BLE001 - a chart failure must not lose the signal
            print(f"  chart failed for {s['sym']}: {e}", flush=True)
        try:
            cap_full = caption(s)
            if png:
                # سقف کپشن عکس در تلگرام ۱۰۲۴ کاراکتر است. کپشن سیگنالِ
                # پرمحتوا (اطمینان، انتظار، دلایل بازجویی، نردبان خروج،
                # نقشهٔ نقدینگی) به ~۱۵۰۰ می‌رسد و تلگرام کل درخواست را
                # ۴۰۰ می‌کرد — یعنی **باکیفیت‌ترین سیگنال‌ها اصلاً تحویل
                # نمی‌شدند** (عیب اندازه‌گیری‌شدهٔ ۲۷ اوت: SOL و CRCLB در
                # چند دور پیاپی). حالا سرِ کپشن با عکس می‌رود و بقیه‌اش
                # ریپلای همان پیام می‌شود — هیچ خطی از سیگنال گم نمی‌شود.
                head, tail = _split_caption(cap_full)
                with open(png, "rb") as f:
                    blob = f.read()
                resp = _post(token, "sendPhoto",
                             {"chat_id": chat, "caption": head, "parse_mode": "HTML"},
                             {"photo": (f"{s['sym']}.png", blob)})
                _mid = ((resp or {}).get("result") or {}).get("message_id")
                # مهرِ ضدتکرار **همین‌جا** زده می‌شود، نه بعد از دنباله.
                # وگرنه: عکس در کانال نشسته ولی اگر ارسالِ دنباله بیفتد،
                # استثنا به except بیرونی می‌پرد، کلید نوشته نمی‌شود و
                # چرخهٔ بعد همان سیگنال را دوباره می‌فرستد — عیناً همان
                # کلاسِ PAXG×۵ (یافتهٔ ممیزی ساختار، ۲۷ اوت).
                if _mid:
                    s["tg_msg_id"] = _mid
                    _t = time.time() * 1000
                    sent[_key(s)] = _t
                    sent[f"any|{s['sym']}|{s['tf']}|{s['dir']}"] = _t
                    sent[f"pair|{s['sym']}|{s['dir']}"] = _t
                    _save_sent(sent)
                if tail and _mid:
                    try:
                        _post(token, "sendMessage",
                              {"chat_id": chat, "text": tail, "parse_mode": "HTML",
                               "reply_to_message_id": _mid,
                               "allow_sending_without_reply": "true",
                               "disable_web_page_preview": "true"})
                    except Exception as _e:          # noqa: BLE001
                        # دنباله نرفت ≠ سیگنال نرفت. عکس با اعداد ورود/
                        # استاپ/تارگت از قبل رسیده؛ فقط توضیح‌ها کم است.
                        print(f"  دنبالهٔ کپشن {s['sym']} نرفت "
                              f"({type(_e).__name__}) — سیگنال رفته است",
                              flush=True)
                        _log_delivery_fail(s, f"tail {type(_e).__name__}")
            else:
                resp = _post(token, "sendMessage",
                             {"chat_id": chat, "text": cap_full[:TEXT_LIMIT],
                              "parse_mode": "HTML",
                              "disable_web_page_preview": "true"})
            # شناسهٔ پیام — خواست حمید: اعلام نتیجه باید «ریپلایِ» همین پیام
            # باشد تا با سیگنال دیگری اشتباه نشود. روی خود دیکشنری سیگنال هم
            # می‌نشیند تا فراخوان (مثل مسیر آلارم در چرخه) در دفتر خودش ثبت
            # کند — درس TAO: دفتر آلارم شناسه نداشت و نتیجه ریپلای نشد.
            tg_mid = ((resp or {}).get("result") or {}).get("message_id")
            s["tg_msg_id"] = tg_mid
            _t2 = time.time() * 1000
            sent[_key(s)] = _t2
            sent[f"any|{s['sym']}|{s['tf']}|{s['dir']}"] = _t2
            sent[f"pair|{s['sym']}|{s['dir']}"] = _t2
            # ذخیرهٔ فوری — قبل از هر کار دیگری، تا سقوط/شکست push حافظهٔ
            # همین ارسال را نبرد (رفع ریشه‌ای PAXG×۵، ۲۶ اوت)
            _save_sent(sent)
            _archive_sent(s)
            record_out("signal", f"{s['sym']} {s['tf']} {s['dir']}",
                       {"entry": s.get("entry"), "sl": s.get("sl"),
                        "tp1": s.get("tp1"), "strategy": s.get("strategy"),
                        "sym": s.get("sym"), "dir": s.get("dir"),
                        "tf": s.get("tf")}, s.get("tg_msg_id"))
            ok += 1
            print(f"  sent {s['sym']} {s['tf']} {s['dir']}{'' if png else ' (text only)'}", flush=True)
            _log_final(s)
            # هر سیگنالِ رفته باید درس هم بشود — استاپ زاما در هیچ دفتری نبود
            # چون ارسالی‌های اسکن کاغذی نمی‌شدند. حالا هر ارسال، اگر قبلاً در
            # دفتر نیست، با برچسب sig-<استراتژی> ثبت و تا نتیجه دنبال می‌شود.
            try:
                from hamid import paper as _paper
                _n_open = _paper.open_from([{"symbol": s["sym"], "dir": s["dir"],
                                   "entry": s["entry"], "sl": s["sl"],
                                   "tp1": s.get("tp1") or s["entry"], "tp2": s.get("tp2"),
                                   "stage_tag": f"sig-{s.get('strategy', '?')}",
                                   # تایم‌فریم تا امشب اصلاً منتقل نمی‌شد: هر ۲۳۵
                                   # سیگنالِ بستهٔ دفتر `tf: null` داشت. دو زیان
                                   # اندازه‌گیری‌شده (۳۰ اوت): ۱) اعتبار لیمیت
                                   # به‌جای ۲۴۰ دقیقهٔ ۵د، پیش‌فرض ۷۲۰ می‌گرفت —
                                   # ۳۱ ردیف دیرتر از ۴ ساعت پر شدند (−۰.۲۶R در
                                   # برابر −۰.۰۹R زودپرها). ۲) هیچ سنجشی
                                   # نمی‌توانست تایم‌فریم را تفکیک کند.
                                   "tf": s.get("tf"),
                                   "tg_msg_id": tg_mid}],
                                 {"sent_at": int(time.time() * 1000),
                                  "tg_msg_id": tg_mid,
                                  "pattern_align": ((s.get("premortem") or {}).get("patterns") or {}).get("align"),
                                  "patterns": ((s.get("premortem") or {}).get("patterns") or {}).get("by_tf"),
                                  "ob_align": ((s.get("premortem") or {}).get("ob_ctx") or {}).get("align"),
                                  "ob_hunts": ((s.get("premortem") or {}).get("ob_ctx") or {}).get("hunts"),
                                  "fib_ratio": (s.get("premortem") or {}).get("fib"),
                                  # ردپای اتاق فومو (۲ سپتامبر): داغی جمعیت +
                                  # شاهد اپ fomo — ثبت برای ماشین شبانه، نه امتیاز
                                  **_fomo_trace(s["sym"]),
                                  # اجماع خبری ایجنت‌ها (۲ سپتامبر): فقط ردپا — خبر دیدگاه است، نه تصمیم
                                  **_news_trace(s["sym"], s["dir"]), **_candle_trace(), **_phoenix_trace(s),
                                  # کلاسِ نماد (۶ سپتامبر — «در شناسایی
                                  # ارزها دقت بیشتری بکن»). فقط ردپا: طلای
                                  # توکنی (XAUT/PAXG) بسته نمی‌شود چون n=۲۴
                                  # و میانگین +۰.۰۱۶R هیچ‌چیز را اثبات
                                  # نمی‌کند. ماشین شبانه با همین فیلد
                                  # می‌سنجدش؛ بستنش فقط با CI و تأیید حمید.
                                  "sym_class": _sym_class(s["sym"]),
                                  # شاهد دامیننسِ هم‌ترازِ تایم‌فریم — ثبت برای
                                  # سنجش شبانه، نه دروازه (۳۰ اوت)
                                  "dom_tf_aligned": ((s.get("premortem") or {}).get("dom_tf") or {}).get("aligned"),
                                  "dom_tf_regime": ((s.get("premortem") or {}).get("dom_tf") or {}).get("regime"),
                                  "dom_tf_used": ((s.get("premortem") or {}).get("dom_tf") or {}).get("tf_used"),
                                  "dom_tf_basis": ((s.get("premortem") or {}).get("dom_tf") or {}).get("basis"),
                                  **((s.get("premortem") or {}).get("tv") or {}),
                                  # دستور حمید: تی‌پی‌های تجربه‌محور باید قابل شمارش باشند —
                                  # دلایل صدور روی پرونده می‌ماند تا «با تجربه» اثبات‌پذیر باشد
                                  "pm_pro": (s.get("premortem") or {}).get("pro", [])[:3],
                                  "exp_used": any(("تمرین تاریخی" in x or "حافظه" in x
                                                   or "قانون تأییدشده" in x)
                                                  for x in (s.get("premortem") or {}).get("pro", []))})
                # سیگنالی که ردیف دفتر نگیرد، هرگز نتیجه نمی‌گیرد: نه
                # ریپلای نتیجه می‌خورد، نه هضم می‌شود، نه در کارنامه
                # می‌آید. تا امشب این حالت **بی‌صدا** بود — فقط وقتی
                # `open_from` استثنا می‌داد چیزی چاپ می‌شد، نه وقتی
                # ساکت صفر ردیف می‌ساخت (کلید تکراری در دفتر باز).
                # سه ارسال LOKAUSDT در ۵ سپتامبر دقیقاً همین‌طور گم شدند.
                if not _n_open:
                    print(f"  ثبت نشد: {s['sym']} ارسال شد ولی ردیف دفتر "
                          "نگرفت (کلید تکراری در دفتر باز؟)", flush=True)
                    _log_delivery_fail(s, "ارسال شد ولی ردیف دفتر ساخته نشد")
            except Exception as e:                    # noqa: BLE001 - ثبت نشدن، ارسال را نمی‌کشد
                print(f"  paper log failed for {s['sym']}: {type(e).__name__}", flush=True)
                _log_delivery_fail(s, f"paper.open_from: {type(e).__name__}")
        except urllib.error.HTTPError as e:
            body = scrub(e.read()[:200])
            print(f"  telegram rejected {s['sym']}: {e.code} {body}", flush=True)
            _log_delivery_fail(s, f"HTTP {e.code} {body}")
        except Exception as e:                        # noqa: BLE001 - one failure must not stop the rest
            print(f"  telegram failed for {s['sym']}: {scrub(e)}", flush=True)
            _log_delivery_fail(s, f"{type(e).__name__}: {scrub(e)}")

    _save_sent(sent)
    print(f"telegram: {ok} of {len(fresh)} new signals delivered", flush=True)
    return ok
