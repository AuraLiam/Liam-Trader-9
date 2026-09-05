#!/usr/bin/env python3
"""حل تعارضِ فایل‌های تولیدشدهٔ brain/ با معنای درستِ هرکدام.

چرا لازم شد: ورک‌فلوهای ابری (چرخه، رادار، میز تمرین) هم‌زمان با کار
دستی به همین مسیرها می‌نویسند، و هر merge روی این فایل‌ها تعارض می‌دهد.
دو راه‌حلِ رایج هر دو غلط‌اند:

  · `--ours` → درس‌ها و معامله‌های سمت دیگر پاک می‌شوند. دستور صریح
    حمید: «هیچ‌وقت نباید اطلاعات از پنل پاک شود.»
  · `--theirs` → همان خسارت، در جهت عکس.

پس هر فایل با **معنای خودش** حل می‌شود:

  closed.jsonl      append-only → اجتماع خطوط یکتا، مرتب بر زمان بسته‌شدن
  lessons.json      فهرست درس → اجتماع بر (زمان، نوع، نماد، متن)، سقفِ خودش
  learning/index.json  مشتق‌شده → **بازساخته** می‌شود، نه merge؛ ادغام دو
                    شمارنده عدد بی‌معنا می‌سازد که شبیه عدد درست است.

استفاده:  python3 scripts/resolve_brain_conflicts.py
خروج ۰ یعنی همه حل شد؛ هر مسیر ناشناخته دست‌نخورده و گزارش می‌شود.
"""
from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _stage(stage, path):
    r = subprocess.run(["git", "show", f":{stage}:{path}"],
                       capture_output=True, text=True, cwd=ROOT)
    return r.stdout if r.returncode == 0 else None


def _stage_bytes(stage, path):
    """نسخهٔ باینریِ همان — فایل فشرده با text=True خراب خوانده می‌شود."""
    r = subprocess.run(["git", "show", f":{stage}:{path}"],
                       capture_output=True, cwd=ROOT)
    return r.stdout if r.returncode == 0 else None


def unresolved():
    # core.quotepath=false ضروری است، نه سلیقه. گیت به‌طور پیش‌فرض نام
    # غیر-ASCII را escape می‌کند و در گیومه می‌گذارد:
    #   "brain/patterns/hamid-reason-\330\247..."
    # رشته با «"» شروع می‌شود، startswith("brain/") شکست می‌خورد، handler
    # پیدا نمی‌شود و job با «دستی بماند» می‌میرد. دقیقاً همین در اجرای
    # ۱۰:۱۶ روز ۱۷ اوت رخ داد: ۲۵ فایل حل شد و دو فایلِ نام-فارسیِ
    # brain/patterns/hamid-reason-*.json کل انتشار را کشتند.
    r = subprocess.run(["git", "-c", "core.quotepath=false",
                        "diff", "--name-only", "--diff-filter=U"],
                       capture_output=True, text=True, cwd=ROOT)
    return [p for p in r.stdout.split("\n") if p.strip()]


def trade_key(rec):
    """هویتِ یک معامله — نه متنِ خطش.

    عیبِ کشف‌شدهٔ ۲۴ اوت (بزرگ‌ترین تحریفِ آماریِ این ریپو تا امروز):
    یکتاسازی روی **متنِ خط** بود. دو رانرِ هم‌زمان همان معاملهٔ باز را
    جدا تسویه می‌کنند و هر کدام ردیفی با `closed` (و گاهی mfe/mae) کمی
    متفاوت می‌سازد — یعنی دو خطِ *متفاوت* برای *یک* معامله. اجتماعِ
    متنی هر دو را نگه می‌داشت. نتیجه: ۴۸.۶٪ از ۴۵٬۳۴۵ ردیف دفتر
    تکراری بود، و روی دفتر سیگنال وین‌ریت را از ۷۱.۳٪ به ۷۸.۸٪ و
    انتظار را از +۰.۱۲۸R به +۰.۲۵۱R باد کرده بود.

    کلید عمداً از میدان‌هایی ساخته می‌شود که در لحظهٔ **باز شدن** قطعی
    شده‌اند و تسویه عوضشان نمی‌کند. `closed` داخل کلید نیست — همان چیزی
    است که بین دو نسخه فرق می‌کند.
    """
    return (rec.get("sym"), rec.get("opened"), rec.get("entry"),
            (rec.get("why") or {}).get("stage"))


def merge_jsonl(path):
    """اجتماع بر **هویت معامله**، نه بر متن خط.

    وقتی یک معامله دو تسویه دارد، **زودترین** نگه داشته می‌شود: آن یکی
    لحظهٔ واقعیِ برخورد به استاپ/تارگت را دیده؛ تسویه‌های بعدی
    بازمحاسبه‌اند و فقط دیرتر ثبت شده‌اند.
    """
    best, order, dropped = {}, [], 0
    for st in (2, 3):
        for line in (_stage(st, path) or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:                        # noqa: BLE001 - خط خراب رد
                continue
            if not isinstance(rec, dict):            # ردیفِ غیرشیء (رشته/عدد/لیست)
                rec = {}                             # ۲ سپتامبر: brain/events یک
                #                                   # رشتهٔ خام داشت و .get می‌ترکید
            k = trade_key(rec)
            # ردیفی که هویتِ **معامله** ندارد → اجتماعِ متنی، مثل قبل.
            #
            # عیبِ اندازه‌گیری‌شدهٔ ۵ سپتامبر: شرط قبلی `k[1] is None and
            # k[0] is None` بود، یعنی هم `sym` هم `opened` باید غایب
            # می‌بودند. ولی `brain/learning/experiences.jsonl` — که هر
            # معاملهٔ هضم‌شده در آن می‌نشیند — `sym` دارد و `opened`/
            # `entry` ندارد. پس کلیدش می‌شد `(BTCUSDT, None, None, None)`
            # و **همهٔ تجربه‌های یک نماد به یک ردیف کوبیده می‌شدند**.
            #
            # اثر واقعی، از تاریخچهٔ خودِ مخزن: اجرای «Mined the past»
            # فایل را به ۲۵٬۱۵۱ ردیف رساند و چرخهٔ بعدی به ۲۱٬۷۷۸
            # برگرداند — ۱٬۵۱۷ ردیفِ یکتا در یک کامیت. تطبیقِ دقیقِ
            # معامله‌های بستهٔ ۷۲ ساعت با دفتر تجربه: **۱.۴٪**.
            #
            # ملاک `opened` است و این با شمارش انتخاب شد، نه با سلیقه:
            # در دفتر بسته **هر ۴۸٬۱۵۶ ردیف** `opened` دارد، و در دفتر
            # تجربه **هیچ‌کدام از ۲۱٬۷۷۸ ردیف**. یعنی `opened` دقیقاً
            # همان چیزی است که «ردیفِ معامله» را از بقیه جدا می‌کند.
            #
            # `entry` کافی نیست: نسخهٔ اولِ همین رفع شرط را روی
            # «نه opened و نه entry» گذاشت و روی دادهٔ واقعی **هیچ چیز
            # عوض نشد** — چون ردیف‌های قدیمیِ تجربه `entry` دارند و باز
            # کلیدِ هویتی می‌گرفتند. قیمتِ ورود، شناسهٔ نمونه نیست؛
            # همان قیمت بارها تکرار می‌شود. اجرا شد، نشد، درست شد.
            #
            # محافظِ ۲۴ اوت (ضدِ تسویهٔ دوباره) دست‌نخورده می‌ماند، چون
            # هر ردیفِ معاملهٔ واقعی `opened` دارد.
            if k[1] is None:                         # `opened` ندارد
                k = ("__raw__", line)                # → اجتماعِ متنی
            closed = rec.get("closed") or 0
            if k in best:
                dropped += 1
                if closed < best[k][0]:              # زودترین تسویه برنده
                    best[k] = (closed, line)
                continue
            best[k] = (closed, line)
            order.append(k)
    rows = sorted((best[k] for k in order), key=lambda x: x[0])
    (ROOT / path).write_text("\n".join(l for _, l in rows) + "\n", encoding="utf-8")
    extra = f" ({dropped} تسویهٔ تکراری حذف شد)" if dropped else ""
    return f"{len(rows)} معاملهٔ یکتا{extra}"


def merge_archive_jsonl(path):
    """آرشیو شماره‌دارِ `signals/archive/*.jsonl` → اجتماع بر هویت ردیف.

    عیبِ اندازه‌گیری‌شدهٔ ۵ سپتامبر: مسیرِ `signals/` یک‌جا به `take_ours`
    می‌رفت، یعنی «عکس‌فوریِ بازتولیدشدنی». برای `signals/latest.json` درست
    است؛ برای `signals/archive/telegram-sent-<روز>.jsonl` فاجعه — این دفتر
    **append-only شماره‌دار** است (قانون ضد-merge، ۲۶ اوت) و هر بار که دو
    اجرا در یک روز روی همان فایل بنویسند، نسخهٔ کاملِ یکی روی دیگری
    می‌نشیند و ردیف‌های اضافیِ آن یکی **بی‌صدا گم می‌شوند**.

    اثبات با شمارش، نه با حدس (۵ سپتامبر، پنجرهٔ ۲۴ ساعته):
    `signals/telegram-log.json` ۲۴ ارسال داشت و آرشیو ۲۳؛ ردیفِ گم‌شده
    DOGEUSDT ساعت ۲۱:۲۴:۳۵ UTC بود. شمارهٔ ردیف‌های همان روز هیچ حفره‌ای
    نداشت (۱..۲۳ پیوسته) — یعنی ردیف بعد از نوشتن پاک نشده، بلکه نسخهٔ
    کاملِ فایل جایگزین شده.

    چرا مهم است: شمارندهٔ سقف روزانه (`telegram._archive_sent_in`) دقیقاً
    از همین فایل می‌خواند. هر ردیفِ گم‌شده یعنی سقف `DAILY_CAP=24` کمتر از
    واقعیت می‌شمارد و بیشتر از سقف سیگنال می‌رود.

    هویت ردیف: `tg_msg_id` (یکتای پیام تلگرام) وگرنه `(at, sym, dir)`
    وگرنه خودِ متن. `n` بعد از اجتماع بر پایهٔ `at` از نو پیاپی می‌شود —
    چون هر اجرا `n` را از شمارِ فایلِ خودش می‌سازد و بعد از اجتماع دو
    ردیف می‌توانند `n` یکسان داشته باشند؛ شمارهٔ تکراری یعنی شماره‌گذاری
    از کار افتاده.
    """
    best, order = {}, []
    for st in (2, 3):
        for line in (_stage(st, path) or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:                        # noqa: BLE001 - خط خراب رد
                rec = None
            if isinstance(rec, dict):
                k = (("mid", rec["tg_msg_id"]) if rec.get("tg_msg_id")
                     else ("row", rec.get("at"), rec.get("sym"), rec.get("dir")))
            else:
                rec, k = None, ("__raw__", line)
            if k in best:
                continue
            best[k] = (rec, line)
            order.append(k)
    rows = [best[k] for k in order]
    dated = [r for r in rows if r[0] is not None
             and isinstance(r[0].get("at"), (int, float))]
    rest = [r for r in rows if r not in dated]
    dated.sort(key=lambda r: r[0]["at"])
    out = []
    for i, (rec, _line) in enumerate(dated, 1):
        rec = dict(rec)
        rec["n"] = i
        out.append(json.dumps(rec, ensure_ascii=False))
    out += [line for _rec, line in rest]
    (ROOT / path).write_text("\n".join(out) + "\n", encoding="utf-8")
    return f"{len(out)} ردیف آرشیو (شماره‌گذاری از نو)"


def merge_gz_minutes(path):
    """دفتر دقیقه‌ایِ gzip (عمق دفتر) → اجتماع بر مهر زمان سطل.

    عیب ۲۳ اوت: برداشت عمق ~۵۳ دقیقه طول می‌کشد و کرون ساعتی است، پس دو
    اجرا تقریباً به هم می‌رسند و هر دو روی فایلِ **همان روز** می‌نویسند.
    گیت فایل باینری را merge نمی‌کند و این‌جا handler نبود → «دستی بماند»
    → exit 1 → کلِ ۵۳ دقیقه دادهٔ برداشت‌شده دور ریخته می‌شد. دو بار امروز.

    اجتماع این‌جا دقیق و بی‌اتلاف است چون هر سطر یک سطلِ دقیقه است با
    کلید یکتای `t`: دو اجرا دقیقه‌های متفاوتِ همان روز را دارند، پس
    اتحادشان همان چیزی است که یک اجرای پیوسته می‌ساخت. اگر یک `t` در هر
    دو طرف بود، سطرِ با نمونهٔ بیشتر (`n`) نگه داشته می‌شود — همان دقیقه
    است، ولی یکی کامل‌تر دیده شده."""
    best = {}
    for st in (2, 3):
        blob = _stage_bytes(st, path)
        if not blob:
            continue
        try:
            text = gzip.decompress(blob).decode("utf-8", "replace")
        except Exception:                            # noqa: BLE001 - طرفِ خراب رد
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                t = int(row["t"])
            except Exception:                        # noqa: BLE001
                continue
            old = best.get(t)
            if old is None or (row.get("n") or 0) > (old.get("n") or 0):
                best[t] = row
    out = [best[t] for t in sorted(best)]
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return f"{len(out)} سطل دقیقه (اجتماع)"


def merge_lessons(path):
    o, t = _stage(2, path), _stage(3, path)
    o, t = json.loads(o), json.loads(t)
    seen, out = set(), []
    for L in (o.get("lessons") or [], t.get("lessons") or []):
        for e in L:
            k = (e.get("at"), e.get("kind"), e.get("sym"), (e.get("text") or "")[:120])
            if k in seen:
                continue
            seen.add(k)
            out.append(e)
    out.sort(key=lambda e: e.get("at") or 0)
    # سقف را از خودِ فایل بردار، نه از یک عدد ثابت اینجا — اگر memory.py
    # سقفش را عوض کند، این اسکریپت نباید با آن اختلاف پیدا کند.
    cap = max(len(o.get("lessons") or []), len(t.get("lessons") or [])) or len(out)
    (ROOT / path).write_text(
        json.dumps({"lessons": out[-cap:],
                    "updated": max(o.get("updated") or 0, t.get("updated") or 0)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return f"اجتماع {len(out)} درس → {min(len(out), cap)} نگه داشته شد"


def rebuild_index(path):
    sys.path.insert(0, str(ROOT / "claude-liam-signal" / "python"))
    import brain                                     # noqa: PLC0415
    j = brain.build_index()
    return (f"بازساخته شد: {len(j.get('by_symbol') or {})} نماد"
            if isinstance(j, dict) else "بازساخته شد")


def merge_frontier(path):
    """پرونده‌های «مرز پیشروی»: {نماد: زمان}. بزرگ‌ترین برنده است.

    این فایل‌ها فقط جلو می‌روند — می‌گویند تا کجای تاریخ هر ارز بازپخش شده.
    گرفتنِ max نه چیزی را از دست می‌دهد و نه تکراری می‌سازد؛ گرفتنِ min
    باعث می‌شد همان بازه دوباره ترید شود و نمونهٔ متورمِ تکراری بسازد.

    ۱۵ اوت: نبودِ همین handler کل job را قرمز کرد و ~۳۸ معاملهٔ تازه را
    از بین برد. «دستی بماند» برای آدم درست است؛ داخل ورک‌فلو آدمی نیست."""
    a, b = json.loads(_stage(2, path) or "{}"), json.loads(_stage(3, path) or "{}")
    out = dict(a)
    for k, v in b.items():
        cur = out.get(k)
        try:
            out[k] = max(cur, v) if cur is not None else v
        except TypeError:                             # نوع ناسازگار → تازه‌تر
            out[k] = v
    (ROOT / path).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    return f"{len(out)} نماد، مرز جلوتر برنده"


def merge_key_list(path):
    """فهرست کلیدهای ضدتکرار (مثل brain/telegram-sent.json): اجتماع.

    این عکس‌فوری **نیست** — دفترِ «چه چیزی قبلاً فرستاده شده» است. اگر
    کلیدی از یک طرف بیفتد، همان سیگنال دوباره به تلگرام می‌رود و قانون
    ضدتکرار حمید نقض می‌شود. پس اجتماع، با همان سقف ۵۰۰تایی که خودِ
    tg_batch نگه می‌دارد و تازه‌ترین‌ها را می‌ماند."""
    a = json.loads(_stage(2, path) or "[]")
    b = json.loads(_stage(3, path) or "[]")
    seen, out = set(), []
    for k in list(a) + list(b):
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    out = out[-500:]
    (ROOT / path).write_text(json.dumps(out, ensure_ascii=False),
                             encoding="utf-8")
    return f"{len(out)} کلید ضدتکرار (اجتماع)"


def merge_newest_date(path):
    """نشانگرهای «آخرین بار کِی» (مثل brain/memory/.revalidated): تاریخ
    تازه‌تر برنده است.

    ۲ سپتامبر: چرخهٔ حمید اولین اجرای روزِ تازه، این فایل را از ۰۹-۰۱ به
    ۰۹-۰۲ برد؛ ضربانِ ۰۰:۰۱ (که معمولاً زودتر همین کار را می‌کند) به‌خاطر
    گاردِ هم‌زمانی چیزی commit نکرده بود. در merge انتشار، فایل بدون
    handler ماند → «دستی بماند» → exit 1 → merge --abort → push هرگز موفق
    نشد → **۱۸ اجرای پیاپی، ۸ ساعت، هیچ انتشاری**. محتوای فایل فقط یک
    تاریخ است؛ بزرگ‌تر گرفتن نه چیزی گم می‌کند نه تکرار می‌سازد."""
    a = (_stage(2, path) or "").strip()
    b = (_stage(3, path) or "").strip()
    win = max(a, b)
    (ROOT / path).write_text(win + "\n", encoding="utf-8")
    return f"تاریخ تازه‌تر برنده: {win}"


def take_theirs(path):
    """برای سندهای دست‌نوشتهٔ زیر brain/ (README، یافته‌های تحقیق): نسخهٔ
    origin/main برنده است — رانرِ بی‌ناظر سندی را عوض نمی‌کند؛ اگر متفاوت
    است، نسخهٔ منتشرشده حقیقت است، نه چک‌اوتِ کهنهٔ رانر."""
    subprocess.run(["git", "checkout", "--theirs", "--", path], cwd=ROOT, check=False)
    return "نسخهٔ منتشرشدهٔ origin/main"


def take_ours(path):
    """برای عکس‌فوری‌های تولیدشده: نسخهٔ همین اجرا تازه‌تر است و برنده.

    این فقط برای signals/ درست است — آن‌جا فایل یک **عکس کاملِ لحظه** است،
    نه دفتر انباشته. اگر همین منطق روی brain/ اعمال شود، دفتر معاملهٔ اجرای
    دیگر پاک می‌شود؛ دقیقاً همان اتفاقی که ۱۵ اوت افتاد و ۳۹۰ ردیف برد."""
    subprocess.run(["git", "checkout", "--ours", "--", path], cwd=ROOT, check=False)
    return "عکس‌فوری تازهٔ همین اجرا"


EXACT = {
    "brain/memory/lessons.json": merge_lessons,
    "brain/learning/index.json": rebuild_index,
}

# ── دفترِ انباشته در برابر عکس‌فوریِ مشتق‌شده ─────────────────────────────
#
# این تمایز، تمام ماجرای ۱۵ اوت است و باید دقیق بماند:
#
#   · **دفتر انباشته** (closed.jsonl، lessons) تاریخِ منحصربه‌فرد دارد. هر
#     طرف می‌تواند ردیف‌هایی داشته باشد که طرف دیگر ندارد، پس `--ours`
#     یعنی نابودیِ آن‌ها. این‌ها **اجتماع** می‌شوند.
#
#   · **عکس‌فوری مشتق‌شده** (سلامت، ترازو، دلایل، سری دامیننس) تاریخِ
#     منحصربه‌فرد **ندارد** — تابعی از همان دفترهاست و اجرای بعدی از نو
#     می‌سازدش. این‌جا تازه‌ترین محاسبه برنده است و چیزی از دست نمی‌رود.
#
# فهرست صریح است، نه قاعدهٔ فراگیر: قاعدهٔ فراگیرِ «هر json زیر brain مالِ
# ماست» همان چیزی است که ۳۹۰ ردیف را برد. هر فایل تازه باید آگاهانه
# این‌جا اضافه شود، وگرنه آزمونِ ساختاری صدایش را درمی‌آورد.
DERIVED_SNAPSHOTS = {
    "brain/analysis-btc.json",
    "brain/dominance-series.json",
    "brain/health.json",
    "brain/history-stats.json",
    "brain/medic.json",
    "brain/paper/equity.json",       # از closed.jsonl ساخته می‌شود
    "brain/paper/reasons.json",      # خروجی ماشین بونفرونی، از همان دفتر
    "brain/paper/bridge.json",       # پل تمرین→سیگنال، هر اجرا از closed.jsonl
                                     # از نو ساخته می‌شود — تاریخِ انباشته ندارد
    "brain/sources-probe.json",      # نتیجهٔ کاوش منابع، هر اجرا از نو
}


def handler_for(path):
    """کدام معنا برای کدام مسیر — ترتیب مهم است."""
    if path in EXACT:
        return EXACT[path]
    if path == "brain/telegram-sent.json":
        return merge_key_list                         # دفتر ضدتکرار، نه عکس‌فوری
    if path in DERIVED_SNAPSHOTS:
        return take_ours                              # مشتق‌شده، تاریخ ندارد
    if path.startswith("brain/") and path.endswith(".jsonl.gz"):
        return merge_gz_minutes                       # دفتر دقیقه‌ای فشرده
    if path.startswith("brain/") and path.endswith(".jsonl"):
        return merge_jsonl                            # هر دفتر append-only
    if path.startswith("brain/") and path.endswith("-state.json"):
        return merge_frontier                         # مرز پیشروی هر انجین
    if path.startswith("brain/research/") and path.endswith("last-seen.json"):
        return merge_frontier                         # {url: وضعیت} — کلیدها جمع
    # آرشیو شماره‌دار **قبل از** قاعدهٔ فراگیرِ signals/ — دفتر است نه
    # عکس‌فوری؛ take_ours روی آن یعنی گم‌شدنِ بی‌صدای ردیف (درس ۵ سپتامبر).
    if path.startswith("signals/archive/") and path.endswith(".jsonl"):
        return merge_archive_jsonl
    if path.startswith("signals/"):
        return take_ours
    # آرشیو بک‌تست — ۱۷ اوت: heartbeat و hamid-backtest هر دو این پوشه را
    # commit می‌کنند ولی resolver برایش handler نداشت؛ اولین تصادم واقعی
    # None گرفت، exit 1 شد و **کل استپ ضربان** را کشت (سه شکست Heartbeat
    # و یک Publish to main در همان صبح). فایل‌های تاریخ‌دار
    # (backtest-<date>.json) دو محتوای متفاوت با یک نام نمی‌گیرند مگر دو
    # رانر هم‌زمان — آن‌جا هم هر دو از یک ورودی ساخته شده‌اند و تازه‌تر
    # کافی است؛ latest.json هم عکس‌فوریِ بازتولیدشدنی است.
    if path.startswith("claude-liam-signal/backtests/") and path.endswith(".json"):
        return take_ours
    if path.startswith("claude-liam-signal/backtests/") and path.endswith(".jsonl"):
        return merge_jsonl                            # اگر روزی دفتر شد، اجتماع
    # ── واپسین پناه برای هر json تولیدشدهٔ ناشناخته زیر brain/ ──────────────
    #
    # قبلاً این‌جا None برمی‌گشت یعنی «دستی بماند». برای یک آدم درست است؛
    # داخل ورک‌فلوی بی‌ناظر یعنی exit 1، merge --abort، و کارِ آن اجرا نابود.
    # دو بار همین اتفاق افتاد: یک‌بار با fill-state، یک‌بار با fill-status.
    #
    # این پناه امنِ ماجرای ۱۵ اوت را تکرار نمی‌کند، چون هر نوعِ خطرناکی
    # قبلاً handler صریح دارد و بالاتر گرفته می‌شود: دفتر jsonl (اجتماع)،
    # درس‌ها (اجتماع)، کلیدهای ضدتکرار (اجتماع)، مرز پیشروی (max). چیزی که
    # به این‌جا می‌رسد یک عکس‌فوری مشتق‌شده است و اجرای بعد از نو می‌سازدش.
    #
    # بلند اعلام می‌شود تا اگر روزی یک **دفتر انباشتهٔ تازه** از این‌جا رد
    # شد، در لاگ دیده شود و handler صریحش نوشته شود.
    if path.startswith("brain/") and path.endswith(".json"):
        print(f"⚠ handler صریح ندارد، عکس‌فوری فرض شد: {path} — "
              "اگر این فایل تاریخِ انباشته دارد، handler برایش بنویس")
        return take_ours
    # ── هیچ فایلی زیر brain/ نباید job بی‌ناظر را بکشد (درس ۲ سپتامبر) ─────
    #
    # پناهِ بالا فقط «.json» را می‌گرفت. فایلِ بی‌پسوندِ
    # brain/memory/.revalidated از آن رد شد، None گرفت و ۸ ساعت انتشارِ
    # چرخه را خواباند. کلاسِ عیب: «هر پسوندِ تازه = یک مرگِ تازه». پس
    # قاعده حالا بر **معنا**ی فایل است نه پسوندش:
    #   · نشانگر تاریخ            → تاریخ تازه‌تر
    #   · .gitkeep (خالی)         → هر کدام؛ محتوایی ندارد
    #   · سند دست‌نوشته (.md)     → نسخهٔ منتشرشده (رانر سند نمی‌نویسد)
    #   · هر چیز دیگر زیر brain/  → عکس‌فوریِ همین اجرا، با اعلامِ بلند
    if path == "brain/memory/.revalidated":
        return merge_newest_date
    if path.startswith("brain/") and path.endswith(".gitkeep"):
        return take_ours
    if path.startswith("brain/") and path.endswith(".md"):
        return take_theirs
    if path.startswith("brain/"):
        print(f"⚠ نوعِ ناشناخته زیر brain/، عکس‌فوری فرض شد: {path} — "
              "اگر انباشته است، handler صریح بنویس")
        return take_ours
    return None                                       # بیرون از brain/ = دستی


def main():
    files = unresolved()
    if not files:
        print("تعارضی نیست")
        return 0
    left = []
    for p in files:
        fn = handler_for(p)
        if fn is None:
            left.append(p)
            continue
        try:
            print(f"✓ {p}: {fn(p)}")
        except Exception as e:                       # noqa: BLE001
            print(f"✗ {p}: {type(e).__name__}: {e}")
            left.append(p)
            continue
        subprocess.run(["git", "add", "--", p], cwd=ROOT, check=False)
    if left:
        print(f"\n⚠ دستی بماند ({len(left)}): {left}")
        return 1
    # هرگز فایلی با مارکر تعارض ثبت نشود — یک بار index.json با مارکر
    # کامیت شد و یادگیری ساعت‌ها بی‌صدا خاموش ماند.
    g = subprocess.run(["git", "grep", "-lE", "^(<<<<<<< |>>>>>>> )",
                        "--", "brain", "signals"],
                       capture_output=True, text=True, cwd=ROOT)
    if g.stdout.strip():
        print(f"✗ مارکر تعارض باقی مانده: {g.stdout.split()}")
        return 1
    print("همهٔ تعارض‌ها با معنای خودشان حل شد")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
