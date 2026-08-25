#!/usr/bin/env python3
"""ایجنت «عیب‌یاب و تعمیرکار» — نام قبلی: پزشک/نگهبان (تغییر نام: دستور حمید ۱۴ اوت).

مأموریت، به زبان خود حمید: «فقط دنبال این باشد که در پنل و روند کار دنبال
ایراد گرفتن و سؤال پرسیدن باشد؛ و البته خودش سریعاً بعد از اینکه به جوابی
نرسید سریعاً عیب را پیدا و عیب‌یابی انجام دهد و به‌عنوان تجربه در حافظهٔ
دائمی ذخیره کند.»

چرخه: هر ۱۵ دقیقه سؤال‌های بدبینانه می‌پرسد (معاینه‌ها)؛ هر سؤال بی‌جواب
یک عیب است؛ عیبِ تعمیرشدنی همان لحظه تعمیر می‌شود (بیدار کردن ورک‌فلوی
خوابیده)؛ و هر عیب/تعمیر با memory.remember به حافظهٔ دائمی می‌رود تا
دفعهٔ بعد سریع‌تر تشخیص داده شود.

چرا از بیرون معاینه می‌کند: تجربهٔ این مخزن بارها نشان داد سرور می‌تواند سبز
باشد و پنل کهنه — چرخه فقط به main منتشر می‌شد و gh-pages دو روز عقب بود.
پس ملاک، فایل‌هایی است که مرورگر حمید واقعاً می‌خواند، نه لاگ سرور.

معاینه‌ها:
  ۱. hamid-latest.json روی gh-pages تازه است (<۴۵ دقیقه) و شکل درست دارد
     (setups و paper و reads>0) — یعنی خط تولید سیگنال زنده است.
  ۲. latest.json (اسکن استراتژی‌های قبلی) تازه است (<۶۰ دقیقه).
  ۳. خود صفحهٔ پنل با HTTP 200 می‌آید.
  ۴. تلگرام آماده هست یا نه (فقط گزارش — راهش ثبت دو Secret است).

درمان: اگر خط تولید کهنه بود و REVIVE=1 و GITHUB_TOKEN موجود، ورک‌فلوی
Heartbeat را dispatch می‌کند. این همان کاری است که تا امروز دست آدم می‌خواست.

خروجی: brain/medic.json — فقط وقتی وضعیت «عوض شود» نوشته می‌شود (سالم→خراب یا
برعکس، یا متن یافته‌ها تغییر کند)، که تاریخچهٔ گیت پر از کامیت تکراری نشود.
کد خروج: 0 سالم، 1 خراب — تا ورک‌فلو بتواند روی خرابی رفتار متفاوت کند.

اجرای دستی:  python3 claude-liam-signal/python/medic.py
"""
import json, os, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "brain" / "medic.json"

PAGES = "https://auraliam.github.io/Liam-Trader-9"
HAMID_MAX_MIN = 45      # ضربان هر ۲۰ دقیقه می‌زند؛ دو چرخهٔ ازدست‌رفته یعنی مشکل
SCAN_MAX_MIN = 60
# قانون ۰۷: مرور پامپ ۵ نوبت در روز تهران (کرون UTC ساعت‌های ۲/۷/۱۲/۱۷/۲۱)؛
# بزرگ‌ترین فاصلهٔ سالم ۵ ساعت است + جای اجرا/لغزش.
PUMP_RADAR_MAX_MIN = 380


def fetch(url, timeout=25):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + f"t={int(time.time())}",
                                 headers={"User-Agent": "medic/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def age_min(j):
    g = j.get("generated")
    return None if not g else (time.time() * 1000 - g) / 60000


def github_health(runs):
    """وضعِ فعلی هر ورک‌فلو از فهرست اجراهای اخیر → (faults, infos, sick, wake).

    قاعده (درس ۲۵ اوت): خرابی یعنی «الان قرمز است» — آخرین اجرای کاملِ
    ورک‌فلو failure باشد. شکستی که بعدش سبز آمده رفع شده و فقط یک خط
    خبرِ سلامتی می‌ارزد، نه آلارم. ≥۲ شکستِ پیاپی در انتها = sick
    (یک قرمزِ تک می‌تواند نوسان زیرساخت باشد؛ دومی یعنی الگو).
    cancelled/skipped نه سبزند نه قرمز — در شمارش پیاپی رد می‌شوند."""
    from collections import defaultdict
    by = defaultdict(list)
    for x in runs or []:
        if x.get("status") == "completed":
            by[str(x.get("name") or "؟")].append(x)
    faults, infos, wake, sick = [], [], [], False
    # درس ۱۴ اوت: ورک‌فلوی نامعتبر (مثلاً کلید if تکراری) با صفر job
    # می‌میرد و در API به‌جای نامش «مسیر فایل» می‌آید — اصلاً اجرا نشده.
    broken = sorted(n for n in by if n.startswith(".github/workflows/"))
    if broken:
        sick = True
        faults.append("⛔ ورک‌فلوی نامعتبر (اصلاً اجرا نشده — احتمالاً کلید "
                      "تکراری در YAML): " + "، ".join(broken[:4]))
    for name, rs in sorted(by.items()):
        if name.startswith(".github/workflows/"):
            continue
        rs.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        n_fail = sum(1 for x in rs if x.get("conclusion") == "failure")
        if not n_fail:
            continue
        consec = 0
        for x in rs:
            c = x.get("conclusion")
            if c == "failure":
                consec += 1
            elif c == "success":
                break
        if consec:
            faults.append(f"⚠️ «{name}» الان قرمز است — {consec} شکستِ "
                          "پیاپی در انتهای ۶ ساعت اخیر")
            if consec >= 2:
                sick = True
                if name.lower().startswith("hamid"):
                    wake.append("heartbeat.yml")
        else:
            infos.append(f"گیت‌هاب: «{name}» در ۶ ساعت اخیر {n_fail} شکست "
                         "داشت و برطرف شده — آخرین اجرا سبز")
    if not faults and not infos:
        infos.append("گیت‌هاب: هیچ اجرای قرمزی در ۶ ساعت اخیر")
    return faults, infos, sick, wake


def examine():
    """برمی‌گرداند: (خراب؟، یافته‌ها، بیدارشونده‌ها، total، خرابی‌ها).

    درس ۲۵ اوت: آلارم قبلاً خطِ خرابی را با کلمه‌گردی («ناموفق» در متن)
    پیدا می‌کرد؛ نتیجه این شد که علتِ واقعیِ sick (رادار کهنه) در پیام
    نبود و یک خبرِ تاریخیِ رفع‌شده به‌جایش نشسته بود. حالا هر یافته‌ای
    که sick می‌کند همان لحظه در فهرست جداگانهٔ faults هم ثبت می‌شود و
    پیام آلارم فقط از همین فهرست ساخته می‌شود — علت و پیام دیگر نمی‌توانند
    از هم جدا بیفتند."""
    finds, faults, sick, wake = [], [], False, []

    def bad(msg, *wf):
        nonlocal sick
        sick = True
        finds.append(msg)
        faults.append(msg)
        for w in wf:
            if w not in wake:
                wake.append(w)

    try:
        st, body = fetch(f"{PAGES}/signals/hamid-latest.json")
        j = json.loads(body)
        a = age_min(j)
        setups, paper, reads = j.get("setups"), j.get("paper"), j.get("reads", 0)
        quiet = j.get("mode") == "quiet"
        if a is None or a > HAMID_MAX_MIN:
            bad(f"خط تولید سیگنال کهنه است — آخرین چرخه {round(a) if a else '؟'} دقیقه پیش (آستانه {HAMID_MAX_MIN})",
                "heartbeat.yml")
        elif quiet:
            # حالت سکوت طبق طرح خود حمید اسکن کامل نمی‌کند (بازار آرام یا تعطیل)
            # و reads=0 طبیعی آن است — یک بار همین‌جا هشدار الکی داده شد.
            finds.append(f"چرخه سالم (حالت سکوت): {round(a)} دقیقه پیش — {j.get('why', 'بازار آرام')}")
        elif not isinstance(setups, list) or not isinstance(paper, dict) or reads < 10:
            bad(f"فایل چرخه شکل درست ندارد (reads={reads}) — چرخه می‌دود ولی چیزی که پنل لازم دارد نمی‌سازد",
                "heartbeat.yml")
        else:
            ready = sum(1 for s in setups if not s.get("waiting"))
            finds.append(f"چرخه سالم: {round(a)} دقیقه پیش، {reads} ارز، {ready} سیگنال آماده، {len(setups) - ready} منتظر، دفتر {paper.get('balance')}$")
    except Exception as e:                            # noqa: BLE001 - unreachable is itself the finding
        bad(f"hamid-latest.json در دسترس نیست: {type(e).__name__}", "heartbeat.yml")

    try:
        st, body = fetch(f"{PAGES}/signals/latest.json")
        j = json.loads(body)
        a = age_min(j)
        if a is None or a > SCAN_MAX_MIN:
            bad(f"اسکن استراتژی‌های قبلی کهنه است — {round(a) if a else '؟'} دقیقه (آستانه {SCAN_MAX_MIN})",
                "live-scan.yml")
        else:
            finds.append(f"اسکن قبلی سالم: {round(a)} دقیقه پیش، {len(j.get('signals', []))} سیگنال")
    except Exception as e:                            # noqa: BLE001
        bad(f"latest.json در دسترس نیست: {type(e).__name__}", "live-scan.yml")

    try:
        st, body = fetch(f"{PAGES}/signals/pump-radar.json")
        j = json.loads(body)
        a = age_min(j)
        # قانون ۰۷ (۲۰ اوت): مرور پامپ ۵ نوبت در روز است، نه ۱۵دقیقه‌ای.
        # آستانهٔ ۵۰ دقیقهٔ قدیمی یادگارِ دورهٔ قبل بود و ۹۰٪ روز «کهنه»
        # می‌گفت — دکترین پاسبان باید با کادنس واقعی هم‌قدم بماند.
        if a is None or a > PUMP_RADAR_MAX_MIN:
            bad(f"رادار پامپ کهنه است — {round(a) if a else '؟'} دقیقه پیش "
                f"(سقف {PUMP_RADAR_MAX_MIN}د — ۵ نوبت روزانه، قانون ۰۷)",
                "pump-review.yml")
        else:
            picks = len(j.get("recommendation") or [])
            finds.append(f"رادار پامپ سالم: {round(a)} دقیقه پیش، {picks} پیشنهاد فعال")
    except Exception as e:                            # noqa: BLE001
        bad(f"pump-radar.json در دسترس نیست: {type(e).__name__}", "pump-review.yml")

    try:
        st, body = fetch(f"{PAGES}/signals/news.json")
        j = json.loads(body)
        a = age_min(j)
        if a is None or a > 260:                      # کرون ۳ساعته + لغزش
            bad(f"شکار خبر کهنه است — {round(a) if a else '؟'} دقیقه پیش",
                "news-hunt.yml")
        else:
            finds.append(f"شکار خبر سالم: {round(a)} دقیقه پیش")
    except Exception:                                 # noqa: BLE001 - اولین اجرا هنوز نیامده
        wake.append("news-hunt.yml")
        finds.append("news.json هنوز منتشر نشده — شکار خبر بیدار می‌شود")

    try:
        st, body = fetch(f"{PAGES}/index.html")
        # ۱۷ اوت: هر سه نشانهٔ قبلی اسم‌های قدیمی بودند که با تغییر برند از
        # HTML رفته‌اند — نگهبان با HTTP 200 سالم هم «سرو نمی‌شود» می‌گفت.
        # نشانه‌های امروز: نام هر دو پنل + مهر نسخهٔ چرخه.
        if st != 200 or all(n.encode() not in body for n in
                            ("لیام تریدر ۹", "aura liam mAx", "cycle v")):
            bad(f"صفحهٔ پنل درست سرو نمی‌شود (HTTP {st})")
        else:
            finds.append("صفحهٔ پنل بالا است")
    except Exception as e:                            # noqa: BLE001
        bad(f"صفحهٔ پنل در دسترس نیست: {type(e).__name__}")

    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        finds.append("تلگرام آماده است")
    else:
        finds.append("تلگرام وصل نیست — دو Secret هنوز ثبت نشده (سیگنال فقط روی پنل می‌ماند)")

    # ── سرزدن به گیت‌هاب (دستور حمید، ۱۴ اوت): «هر از گاهی سر به گیت‌هاب
    # هم بزنه که گیت‌هاب مشکلی نداشته باشه» ────────────────────────────────
    # درس ۲۵ اوت: «۲ اجرای ناموفق در ۶ ساعت اخیر» تا ۶ ساعت بعد از رفعِ
    # ریشه‌ای هم پیام می‌شد، چون پنجرهٔ گذشته‌نگر بود. ملاکِ درست وضعِ
    # فعلی است: آخرین اجرای کاملِ هر ورک‌فلو. قرمزِ رفع‌شده تاریخ است،
    # نه خرابی — فقط یک خط خبرِ «برطرف شده» می‌ارزد.
    try:
        tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        hdr = {"User-Agent": "medic/2",
               **({"Authorization": f"Bearer {tok}"} if tok else {})}
        since = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                              time.gmtime(time.time() - 6 * 3600))
        req = urllib.request.Request(
            "https://api.github.com/repos/Auraliam/Liam-Trader-9/actions/runs"
            f"?per_page=80&created=%3E{since}", headers=hdr)
        with urllib.request.urlopen(req, timeout=25) as r:
            runs = json.load(r).get("workflow_runs", [])
        gh_faults, gh_infos, gh_sick, gh_wake = github_health(runs)
        for f_ in gh_faults:
            finds.append(f_)
            faults.append(f_)
        finds.extend(gh_infos)
        if gh_sick:
            sick = True
        for w in gh_wake:
            if w not in wake:
                wake.append(w)
        with urllib.request.urlopen(urllib.request.Request(
                "https://api.github.com/repos/Auraliam/Liam-Trader-9",
                headers=hdr), timeout=20) as r:
            repo = json.load(r)
        if not repo.get("private"):
            finds.append("مخزن عمومی است — خصوصی‌کردن باعث می‌شود پنل gh-pages "
                         "بدون اکانت Pro از دسترس خارج شود؛ تصمیم با حمید")
    except Exception as e:                            # noqa: BLE001 - گیت‌هاب نباید معاینه را بکشد
        finds.append(f"گیت‌هاب: بررسی نشد ({type(e).__name__})")

    # ── گشت میان کل ایجنت‌ها (دستور حمید، ۱۴ اوت): «با گردش میان مجموعهٔ
    # ایجنت‌ها و با سؤال پرسیدن در مورد هر چیز خودش دنبال جواب برود» ──────
    # هر اتاق در brain/rooms یک ایجنت است و _saved آخرین ضربانش. سؤال از
    # هرکدام: «آخرین بار کی کار کردی؟» — جوابِ کهنه‌تر از ۶ ساعت یعنی آن
    # ایجنت خوابیده؛ سؤال و جوابش در دفتر پرسش‌ها ثبت می‌شود.
    try:
        rooms_dir = Path(__file__).resolve().parent.parent.parent.parent / "brain" / "rooms"
        questions = []
        stale_rooms = []
        for d in sorted(rooms_dir.iterdir() if rooms_dir.is_dir() else []):
            if not d.is_dir():
                continue
            q = {"q": f"اتاق {d.name}: آخرین بار کی کار کردی؟", "room": d.name}
            try:
                stj = json.loads((d / "state.json").read_text())
                saved = stj.get("_saved") or stj.get("at") or 0
                age_h = (time.time() * 1000 - saved) / 3600000 if saved else None
                q["a"] = f"{age_h:.1f} ساعت پیش" if age_h is not None else "هرگز"
                if age_h is None or age_h > 6:
                    stale_rooms.append(d.name)
                    q["fault"] = True
            except Exception as e:                    # noqa: BLE001
                q["a"] = f"جواب نداد ({type(e).__name__})"
                q["fault"] = True
                stale_rooms.append(d.name)
            questions.append(q)
        if stale_rooms:
            # اتاق خوابیده معمولاً یعنی چرخهٔ مادرش خوابیده — همان درمان
            if len(stale_rooms) >= 3:
                bad("گشت ایجنت‌ها: این اتاق‌ها ۶+ ساعت است کار نکرده‌اند یا "
                    "جواب نمی‌دهند: " + "، ".join(stale_rooms[:6]),
                    "heartbeat.yml")
            else:
                finds.append("گشت ایجنت‌ها: این اتاق‌ها ۶+ ساعت است کار نکرده‌اند یا "
                             "جواب نمی‌دهند: " + "، ".join(stale_rooms[:6]))
        elif questions:
            finds.append(f"گشت ایجنت‌ها: هر {len(questions)} اتاق در ۶ ساعت اخیر کار کرده‌اند")
        # دفتر پرسش‌های عیب‌یاب — append، برای بازخوانی خودش و حمید
        qp = Path(__file__).resolve().parent.parent.parent.parent / "brain" / "medic-questions.jsonl"
        with open(qp, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": int(time.time() * 1000),
                                "questions": questions}, ensure_ascii=False) + "\n")
    except Exception:                                 # noqa: BLE001 - گشت نباید معاینه را بکشد
        pass

    # ── سؤال جدید عیب‌یاب (ترس حمید، ۱۴ اوت): «حافظه کوچک نشده؟» ──────────
    # جمع کل معاملات بسته فقط باید بالا برود. اگر نسبت به آخرین معاینه
    # پایین آمد، یعنی دفتر واقعاً از دست رفته — همان اتفاقی که حمید فکر
    # کرد افتاده. آن روز نمایش گمراه بود نه داده؛ این سؤال فرقشان را
    # از این به بعد خودکار می‌گیرد.
    total = None
    try:
        st, body = fetch(f"{PAGES}/signals/hamid-latest.json")
        total = ((json.loads(body).get("paper") or {}).get("total_closed"))
        prev_total = None
        if OUT.exists():
            prev_total = (json.loads(OUT.read_text()) or {}).get("total_closed")
        if total is not None:
            if prev_total is not None and total < prev_total:
                bad(f"⚠️ حافظهٔ انباشته کوچک شد: {prev_total} → {total} — "
                    "این دیگر خطای نمایش نیست، دفتر واقعاً از دست رفته")
            else:
                finds.append(f"حافظهٔ انباشته سالم: {total} معاملهٔ بسته"
                             + (f" (قبلی {prev_total})" if prev_total else ""))
    except Exception:                                 # noqa: BLE001 - قبل از استقرار فیلد، ساکت
        pass

    return sick, finds, wake, total, faults


def _runs(workflow, tok, status):
    req = urllib.request.Request(
        f"https://api.github.com/repos/Auraliam/Liam-Trader-9/actions/workflows/{workflow}"
        f"/runs?status={status}&per_page=5",
        headers={"Authorization": f"Bearer {tok}",
                 "Accept": "application/vnd.github+json", "User-Agent": "medic/1"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return len(json.load(r).get("workflow_runs") or [])


def revive(workflow):
    """همان کاری که دکمهٔ Run workflow می‌کند — برای هر خطی که خوابیده.

    اول نگاه می‌کند خط واقعاً خوابیده باشد: dispatch روی خطی که همین حالا
    در حال اجرا یا در صف است فقط صف را پر می‌کرد و هر جایگزینی صف، یک اجرای
    «cancelled» قرمز در اینباکس حمید می‌کاشت — ۴ تا در ۷۵ دقیقه شمرده شد."""
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok or os.environ.get("REVIVE") != "1":
        return "درمان غیرفعال است (REVIVE=1 و GITHUB_TOKEN لازم دارد)"
    try:
        if _runs(workflow, tok, "in_progress") > 0:
            return f"{workflow} همین حالا در حال اجراست — دست نمی‌زنم"
        if _runs(workflow, tok, "queued") > 0:
            return f"{workflow} در صف است — dispatch دوباره لازم نیست"
    except Exception:                                 # noqa: BLE001 - چک ناموفق مانع درمان نمی‌شود
        pass
    req = urllib.request.Request(
        f"https://api.github.com/repos/Auraliam/Liam-Trader-9/actions/workflows/{workflow}/dispatches",
        data=json.dumps({"ref": "main"}).encode(),
        headers={"Authorization": f"Bearer {tok}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "medic/1"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return f"{workflow} دوباره روشن شد (HTTP {r.status})"
    except Exception as e:                            # noqa: BLE001 - the failure text is the report
        return f"روشن کردن {workflow} شکست خورد: {type(e).__name__}"


# ── آلارم: چه چیزی فرستاده شود و کِی ────────────────────────────────────
# درس ۲۳ اوت: زنجیرهٔ سیگنال ۸ ساعت مرده بود. عیب‌یاب **درست تشخیص داده
# بود** (sick=True از ۰۲:۴۸ به بعد) و آلارم هم شرطش برقرار بود، ولی
# پیامی که می‌رفت ۱۰ خط بود که شش خطش «سالم» بود و خبر واقعی خط هشتم —
# و همان پیام هر ۱۵ دقیقه تکرار می‌شد. آلارمی که هر ربع ساعت یک‌شکل
# بیاید دیگر آلارم نیست، نویز است؛ قانون E23 هم صریح همین را منع کرده
# («routine still-alive spam ممنوع»).
FAULT_MARKS = ("⚠️", "⛔", "❌")
# ۲۳ اوت: هم‌واژه با بقیهٔ پاسبان‌ها (hamid/alert_gate.REPEAT_H = ۶ ساعت).
# قبلاً ساعتی بود و حمید همان یک خبر را دوباره گرفت در حالی که خودش
# می‌دانست خراب است. یادآوریِ زودتر از این، اطلاعات تازه‌ای نمی‌دهد و
# فقط باعث می‌شود آلارمِ بعدی خوانده نشود.
ESCALATE_MS = 6 * 3600_000    # تا وقتی خراب است، یادآوری هر ۶ ساعت


def fault_lines(findings):
    """فقط خطوطی که واقعاً خبرِ خرابی‌اند — «سالم»ها کنار می‌روند."""
    return [f for f in (findings or [])
            if any(m in f for m in FAULT_MARKS)
            or ("ناموفق" in f or "شکست خورده" in f)]


def alert_decision(state, prev, now_ms=None):
    """→ (بفرست؟, دلیل). سه حالت می‌ارزد به پیام، بقیه سکوت.

    ۱. تازه خراب شد (سالم → خراب)
    ۲. هنوز خراب است ولی از آخرین یادآوری بیش از یک ساعت گذشته
    ۳. تازه خوب شد (خراب → سالم) — بهبود هم خبر است
    """
    now = now_ms or int(time.time() * 1000)
    was, is_ = bool(prev.get("sick")), bool(state.get("sick"))
    if is_ and not was:
        return True, "new"
    if not is_ and was:
        return True, "recovered"
    if is_ and was:
        last = prev.get("alerted_at") or 0
        if now - last >= ESCALATE_MS:
            return True, "still"
        return False, "duplicate"
    return False, "healthy"


def alert_text(state, reason):
    """پیام کوتاه و خبرمحور — خرابی اول، سالم‌ها فقط شمرده.

    منبع خطوط خرابی از ۲۵ اوت ساختاری است (state["faults"] — همان
    یافته‌هایی که sick را روشن کردند)، نه کلمه‌گردی در متن؛ کلمه‌گردی
    یک بار علتِ واقعی را از پیام انداخت و یک خبرِ تاریخی را جایش گذاشت.
    fault_lines فقط برای وضعیت‌های قدیمیِ روی دیسک مانده است."""
    finds = state.get("findings") or []
    faults = state.get("faults")
    if faults is None:
        faults = fault_lines(finds)
    if reason == "recovered":
        return ("✅ لیام تریدر ۹ — خرابی رفع شد.\n"
                f"همهٔ {len(finds)} بررسی سالم است.")
    head = {"new": "⛔ لیام تریدر ۹ — خرابی تازه:",
            "still": "⛔ لیام تریدر ۹ — خرابی هنوز پابرجاست:"}[reason]
    body = "\n".join(f"• {f}" for f in faults) or "• (جزئیات در brain/medic.json)"
    ok = len(finds) - len(faults)
    tail = f"\n\n{ok} بررسی دیگر سالم است."
    if state.get("treated"):
        tail += f"\n🔧 {state['treated']}"
    return f"{head}\n{body}{tail}"


def main():
    sick, finds, wake, total, faults = examine()
    treated = "؛ ".join(revive(w) for w in dict.fromkeys(wake)) or None
    state = {"at": int(time.time() * 1000),
             "atText": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
             "sick": sick, "findings": finds, "faults": faults,
             "treated": treated, "total_closed": total}

    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
        except Exception:                             # noqa: BLE001
            prev = {}
    if total is None:
        state["total_closed"] = prev.get("total_closed")
    # تصمیم آلارم پیش از نوشتن وضعیت گرفته می‌شود — بعدش prev دیگر
    # همان قبلی نیست و «تازه خراب شد» قابل تشخیص نخواهد بود.
    send, why_alert = alert_decision(state, prev)
    state["alerted_at"] = (state["at"] if send
                           else prev.get("alerted_at") or 0)
    state["alert_reason"] = why_alert
    if send:
        # مسیر آلارم داخل خود medic است تا آزمون‌پذیر باشد؛ ورک‌فلو فقط
        # همین متن را می‌فرستد. متن خالی = چیزی برای گفتن نیست.
        (ROOT / "signals").mkdir(parents=True, exist_ok=True)
        (ROOT / "signals" / "medic-alert.txt").write_text(
            alert_text(state, why_alert), encoding="utf-8")
    changed = prev.get("sick") != sick or prev.get("findings") != finds \
        or prev.get("total_closed") != state["total_closed"] or send
    if changed:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1))

    # ── درس به حافظهٔ دائمی (دستور حمید ۱۴ اوت) — عیب و تعمیر، هر دو ─────
    # فقط سرِ «تغییر وضعیت»، نه هر ۱۵ دقیقه: remember خودش تکراری ۱۲ساعته
    # را شمارنده می‌کند، ولی سالمِ پایدار اصلاً درس نیست.
    try:
        sys.path.insert(0, str(HERE))
        from hamid import memory as _mem
        faults = [f for f in finds if any(k in f for k in ("کهنه", "در دسترس نیست",
                                                           "شکل درست ندارد", "کوچک شد"))]
        if sick and not prev.get("sick") and faults:
            _mem.remember("عیب", "SYSTEM",
                          "عیب‌یاب: " + "؛ ".join(faults[:3])
                          + (f" — تعمیر: {treated}" if treated else " — تعمیر خودکار نداشت"),
                          data={"treated": treated})
        elif prev.get("sick") and not sick:
            _mem.remember("عیب", "SYSTEM",
                          "عیب‌یاب: خرابی قبلی رفع شد — "
                          + "؛ ".join((prev.get("findings") or [])[:2]))
    except Exception as e:                            # noqa: BLE001 - حافظه نباید معاینه را بکشد
        print(f"(حافظه ثبت نشد: {type(e).__name__})")

    for f in finds:
        print(("⛔ " if sick else "✓ ") + f)
    if treated:
        print("🔧 " + treated)
    print("state changed" if changed else "state unchanged")
    sys.exit(1 if sick else 0)


if __name__ == "__main__":
    main()
