#!/usr/bin/env python3
"""لیام‌۹ محلی — کل سامانه روی لپ‌تاپ حمید، بدون گیت‌هاب در مسیر سیگنال.

دستور حمید (۴ سپتامبر): «اگه می‌بینی می‌تونیم بدون گیتهاب کار کنیم و همه
کارارو با همین لپ‌تاپ انجام بدیم همین کارو بکن، که ما دیگه تاخیری در
دریافت و ارسال دیتا نداشته باشیم… بارها در سایکل‌های گیتهاب دچار مشکل
شده‌ایم و هر بار میگی برطرف کردم اما تغییری صورت نگرفته.»

## چرا این فایل، و نه یک وصلهٔ دیگر روی Actions

حق با حمید است و ریشه‌اش ساختاری است، نه یک باگ. GitHub Actions یک
زمان‌بندِ مشترک و بهترین-تلاش است؛ ما داشتیم از آن یک حلقهٔ بازار
می‌ساختیم. سه چیزِ **اندازه‌گیری‌شده** در همین ریپو:

| چه چیزی سنجیده شد | نتیجه |
|---|---|
| کرون `*/5` زنجیره (۱۰ اوت) | یک شکاف **۷۳ دقیقه‌ای** — اصلاً شلیک نشد |
| کرون ساعتی گزارش دامیننس (۱ سپتامبر) | در ۶ روز **۲۲ بار** به‌جای ۱۴۴ — شکاف تا ۸ ساعت |
| اجرای هفتگی آزمایشگاه (۴ سپتامبر) | ۸۰ دقیقه محاسبه، **خروجی صفر** (تایم‌اوت job) |

و برای اینکه دفترها بین رانرهای هم‌زمان گم نشوند، زنجیره مجبور شد این
را در حلقه‌اش داشته باشد: `git reset --hard origin/main` + بکاپ ۸ فایل
+ `--reapply` + `receipts_guard --restore` + `merge_sent`. **هیچ‌کدام از
این‌ها کارِ ترید نیست؛ همه‌اش هزینهٔ اجرا روی ماشینِ غریبه است.** روی یک
لپ‌تاپ، دفتر فقط روی دیسک می‌نشیند و تمام.

## چه چیزی این‌جا حذف می‌شود (نه ساده‌سازی — حذفِ کامل)

`reapply` · `receipts_guard --restore` · `merge_sent` · `reset --hard` ·
بکاپ/بازگردانی · تلاش‌های پیاپیِ push · self-dispatch · «فقط یک حلقه» ·
انتشار جدا روی gh-pages. صفر خط از این‌ها در مسیر سیگنال باقی می‌ماند.

## مرزِ صادقانه — چیزی که ادعا نمی‌کنم

- این فایل **جای موتور را نمی‌گیرد**. همان `scan.py` و همان ماژول‌های
  `hamid.*` تولید را صدا می‌زند، با همان پرچم‌ها. هیچ دروازه‌ای شل
  نشد، هیچ آستانه‌ای عوض نشد، هیچ استراتژی‌ای بازنویسی نشد.
- تأخیر **صفر** نمی‌شود؛ از «۱۵ تا ۳۵ دقیقه» به «یک تیک» می‌رسد
  (پیش‌فرض ۶۰ ثانیه، قابل تنظیم). ثانیه‌ایِ واقعی کارِ وب‌سوکت است که
  در `hamid/ws_feed.py` جدا آمده و تا وقتی روی خودِ ماشین راستی‌آزمایی
  نشده، ادعا نمی‌شود.
- `LIVE_EXECUTION` همچنان false. این سرویس سیگنال می‌فرستد، سفارش نه.

## اجرا

    python3 -m hamid.liam9d --doctor     # قبل از هر چیز: آیا این ماشین آماده است؟
    python3 -m hamid.liam9d              # سرویس + پنل روی http://127.0.0.1:9009
    python3 -m hamid.liam9d --once       # یک دور کامل، برای آزمایش
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent                                     # claude-liam-signal/python
sys.path.insert(0, str(PY))
ROOT = PY.parent.parent

STATE = ROOT / "signals" / "liam9d.json"
LOG = ROOT / "signals" / "liam9d-log.jsonl"

TICK_S = float(os.environ.get("LIAM9D_TICK", "60"))  # ضربان لِینِ سیگنال
PORT = int(os.environ.get("LIAM9D_PORT", "9009"))
HOST = os.environ.get("LIAM9D_HOST", "127.0.0.1")
MAX_LOG = 4000                                       # خطِ لاگِ نگه‌داشته


# ── جدول کار ───────────────────────────────────────────────────────────
#
# هر ردیف عیناً همان فرمانی است که ورک‌فلوی متناظر اجرا می‌کند. `wf`
# اسمِ همان فایل است و بی‌دلیل آن‌جا نیست: `test_liam9d` جدول را با
# خودِ ورک‌فلوها می‌سنجد، پس اگر روزی فرمانی به Actions اضافه شود و
# این‌جا نیاید، چرخه سرخ می‌شود. واگرایی بی‌صدا — همان چیزی که باعث شد
# «برطرف شد»های قبلی واقعی نباشند — این‌جا ممکن نیست.
#
# `every` از کادنسِ **واقعیِ** همان ورک‌فلو می‌آید نه از آرزو: جایی که
# کرون `7,22,37,52` است یعنی هر ۱۵ دقیقه، و جایی که `*/15` بود ولی خودِ
# job هشت دور می‌چرخید یعنی عملاً هر ~۳ دقیقه.
JOBS = [
    # ── لِینِ سیگنال: محصول. اول از همه، هر تیک. ──────────────────────
    dict(key="scan", every=TICK_S, wf="pump-radar.yml", tg=True, timeout=300,
         desc="اسکن استراتژی روی ۶۰ نماد + چرخش ۲۰۰ (محصول)",
         cmd=["python3", "scan.py", "--symbols", "60", "--rotate", "200",
              "--core", "30", "--telegram"]),
    # پاسبان خوراک — «اصلاً قطع نشود» فقط وقتی معنا دارد که شمرده شود.
    # قبل از بقیه، چون اگر همهٔ منابع خاموش باشند بقیهٔ کارها بی‌معنایند.
    dict(key="feed_watch", every=300, wf="pump-radar.yml", tg=True, timeout=180,
         desc="پایش ۱۳ منبع کندل + حکم HEALTHY/THIN/DEGRADED/DARK",
         cmd=["python3", "-m", "hamid.feed_watch", "--write", "--alert",
              "--quiet"]),
    dict(key="dominance", every=180, wf="dominance.yml", timeout=180,
         desc="نقطهٔ دامیننس USDT.D/BTC.D",
         cmd=["python3", "-m", "hamid.dominance"]),
    dict(key="dominance_desk", every=180, wf="pump-radar.yml", timeout=180,
         desc="اتاق دامیننس — رأی وزنی تایم‌فریم‌ها + USDC.D",
         cmd=["python3", "-m", "hamid.dominance_desk", "--write"]),
    dict(key="btc_patterns", every=180, wf="pump-radar.yml", timeout=180,
         desc="الگوهای بیت‌کوین ۱س/۴س/روزانه",
         cmd=["python3", "-m", "hamid.btc_patterns"]),
    dict(key="state_bus", every=180, wf="pump-radar.yml", timeout=120,
         desc="گذرگاه وضعیت (قانون ۱۳)",
         cmd=["python3", "-m", "hamid.state_bus", "--write"]),
    dict(key="loop_audit", every=180, wf="pump-radar.yml", timeout=180,
         desc="ممیز حلقهٔ بسته — هر سیگنال رد پنل/یادگیری دارد؟",
         cmd=["python3", "-m", "hamid.loop_audit", "--write"]),
    dict(key="scorecard", every=180, wf="pump-radar.yml", timeout=180,
         desc="کارنامهٔ انجین‌ها",
         cmd=["python3", "-m", "hamid.scorecard", "--write"]),
    dict(key="gainer_radar", every=900, wf="pump-radar.yml", tg=True, timeout=240,
         desc="رادار گینرهای بیت‌یونیکس",
         cmd=["python3", "-m", "hamid.gainer_radar", "--write", "--telegram"]),
    dict(key="dominance_report", every=900, wf="dominance-report.yml", tg=True,
         timeout=300, desc="گزارش ساعتی دامیننس (ضدتکرار ۵۰د داخل خودش)",
         cmd=["python3", "-m", "hamid.dominance_report", "--send"]),
    dict(key="skeptic", every=180, wf="pump-radar.yml", tg=True, timeout=240,
         desc="بازجوی شکاک از E01 تا E25",
         cmd=["python3", "-m", "hamid.skeptic", "--write", "--telegram"]),
    dict(key="trail_alert", every=900, wf="live-scan.yml", tg=True, timeout=180,
         desc="آلارم تریل روی پوزیشن‌های باز",
         cmd=["python3", "-m", "hamid.trail_alert", "--alert"]),

    # ── چرخهٔ حمید ────────────────────────────────────────────────────
    dict(key="cycle", every=1800, wf="hamid-cycle.yml", tg=True, timeout=900,
         desc="چرخهٔ حمید — روش خودش، هضم معاملات بسته",
         cmd=["python3", "-m", "hamid.cycle"]),
    dict(key="phoenix", every=1800, wf="hamid-cycle.yml", timeout=300,
         desc="شورای ققنوس — کارنامهٔ ۱۲ مراقب",
         cmd=["python3", "-m", "hamid.phoenix", "--score", "--write"]),
    dict(key="council", every=1800, wf="hamid-cycle.yml", timeout=300,
         desc="شورا به تفکیک انجین",
         cmd=["python3", "-m", "hamid.council", "--score", "--write"]),
    dict(key="router", every=1800, wf="hamid-cycle.yml", timeout=300,
         desc="مسیریاب استراتژی",
         cmd=["python3", "-m", "hamid.router", "--write"]),
    dict(key="newsboard", every=1800, wf="hamid-cycle.yml", timeout=300,
         desc="تابلوی خبر (دیدگاه، نه دروازه — قانون ۱۵)",
         cmd=["python3", "-m", "hamid.newsboard", "--write"]),
    dict(key="skill_ledger", every=1800, wf="hamid-cycle.yml", timeout=300,
         desc="دفتر مهارت — ضریب تجربهٔ تکرارشده",
         cmd=["python3", "-m", "hamid.skill_ledger", "--write"]),
    dict(key="agent_scores", every=1800, wf="hamid-cycle.yml", timeout=300,
         desc="امتیاز ایجنت‌ها", cmd=["python3", "-m", "hamid.agent_scores"]),
    dict(key="position_watch", every=1800, wf="hamid-cycle.yml", tg=True,
         timeout=240, desc="پاسبان پوزیشن‌های مانده",
         cmd=["python3", "-m", "hamid.position_watch", "--alert"]),
    dict(key="ob_intel", every=1800, wf="hamid-cycle.yml", timeout=600,
         desc="هوش اردر بلاک روی ۴۰ نماد",
         cmd=["python3", "-m", "hamid.ob_intel", "--symbols", "40"]),
    dict(key="edge_export", every=1800, wf="hamid-cycle.yml", timeout=240,
         desc="قفسهٔ لبه برای داشبورد",
         cmd=["python3", "-m", "hamid.edge_export"]),
    dict(key="watchdog", every=1800, wf="hamid-cycle.yml", tg=True, timeout=240,
         desc="پاسبان سلامت", cmd=["python3", "-m", "hamid.watchdog", "--alert"]),
    dict(key="work_report_log", every=1800, wf="hamid-cycle.yml", timeout=300,
         desc="گزارش کار (فقط ثبت، ارسال جدا)",
         cmd=["python3", "-m", "hamid.work_report", "--hours", "24"]),

    # ── میز اسکلپ ۱ دقیقه (مسیر جدا — قانون ۱۰) ──────────────────────
    dict(key="scalp", every=900, wf="scalp.yml", timeout=600,
         desc="میز اسکلپ ۱ دقیقه", cmd=["python3", "-m", "hamid.scalp"]),
    dict(key="scalp_verdict", every=900, wf="scalp.yml", tg=True, timeout=180,
         desc="حکم توقف میز اسکلپ",
         cmd=["python3", "-m", "hamid.scalp_verdict", "--alert"]),

    # ── اتاق‌های نیم‌ساعته ────────────────────────────────────────────
    dict(key="scout", every=1800, wf="scout.yml", timeout=300,
         desc="گشت صرافی‌ها — دیده‌بان", cmd=["python3", "-m", "hamid.scout"]),
    dict(key="fomo", every=1800, wf="fomo.yml", timeout=300,
         desc="اتاق فومو — شاهد حمید + داغی جمعیت",
         cmd=["python3", "-m", "hamid.fomo"]),
    dict(key="trainer", every=1800, wf="trainer.yml", timeout=900,
         desc="میز تمرین", cmd=["python3", "-m", "hamid.trainer"]),

    # ── ساعتی و کندتر ────────────────────────────────────────────────
    dict(key="depth", every=3600, wf="depth-collect.yml", timeout=600,
         desc="جمع‌آوری عمق دفتر سفارش (Level 2)",
         cmd=["python3", "-m", "hamid.depth_collector", "--fold-raw"]),
    dict(key="news_poll", every=10800, wf="news-hunt.yml", timeout=900,
         desc="نظرسنجی خبر بین ایجنت‌ها (قانون ۱۵)",
         cmd=["python3", "-m", "hamid.news_poll"]),
    dict(key="intel", every=10800, wf="news-hunt.yml", timeout=900,
         desc="شکار خبر و تقویم",
         cmd=["python3", "-m", "hamid.intel", "--deep", "--quiet"]),
    dict(key="pump_desk", every=17280, wf="pump-review.yml", timeout=600,
         desc="میز پامپ — پنج نوبت در روز (قانون ۰۷)",
         cmd=["python3", "-m", "hamid.pump_desk", "--write"]),
    dict(key="work_report_send", every=28800, wf="work-report.yml", tg=True,
         timeout=600, desc="ارسال گزارش کار — سه نوبت در روز",
         cmd=["python3", "-m", "hamid.work_report", "--hours", "8", "--send"]),
    dict(key="curriculum", every=28800, wf="work-report.yml", timeout=300,
         desc="برنامهٔ درسی انجین‌ها",
         cmd=["python3", "-m", "hamid.curriculum", "--write"]),
    dict(key="bandit", every=28800, wf="work-report.yml", timeout=600,
         desc="ماشین چنددست (کاوش/بهره‌برداری)",
         cmd=["python3", "-m", "hamid.bandit", "--write"]),
    dict(key="btc_sensitivity", every=86400, wf="pump-radar.yml", timeout=900,
         desc="حساسیت تاریخی نمادها به بیت‌کوین",
         cmd=["python3", "-m", "hamid.btc_sensitivity", "--write"]),
]

BY_KEY = {j["key"]: j for j in JOBS}

# کارهایی که **فقط** هزینهٔ اجرا روی ماشینِ غریبه بودند و این‌جا اصلاً
# وجود ندارند. این فهرست تزئینی نیست: `test_liam9d` هر فرمانِ ورک‌فلو را
# یا در `JOBS` می‌خواهد یا در این‌جا با دلیلِ نوشته‌شده. پس اگر فردا
# فرمانی به Actions اضافه شود و به سرویس محلی نیاید، چرخه سرخ می‌شود —
# واگراییِ بی‌صدا، که ریشهٔ «گفتی برطرف شد ولی نشده بود» است، ممکن نیست.
GIT_ONLY = {
    "hamid.pump_radar --reapply":
        "نشاندن دوبارهٔ خروجی بعد از reset — روی دیسک محلی reset نداریم",
    "hamid.receipts_guard --restore":
        "برگرداندن رسیدهایی که reset پاک کرده بود — پاک‌کننده‌ای نیست",
    "hamid.receipts_guard --snapshot":
        "عکس‌فوری رسیدها قبل از reset — روی دیسک محلی چیزی پاکشان نمی‌کند",
    "hamid.merge_sent":
        "اجتماع دفتر ضدتکرارِ دو رانر — یک نویسنده بیشتر نداریم",
    "hamid.selfcheck":
        "خودآزمایی دروازهٔ CI — روی لپ‌تاپ کارِ دکتر است",
    "hamid.sentinel --alert":
        "پاسبان نویسندهٔ کامیت — وقتی کامیتی در مسیر سیگنال نیست، بی‌موضوع است",
    "hamid.escalation":
        "تشدید خرابیِ ورک‌فلو — موضوعش خودِ Actions است",
    "hamid.publish_experience": "انتشار به ریپو — پنل محلی مستقیم از دیسک می‌خواند",
    "hamid.publish_top_liquidity":
        "انتشار جدول نقدینگی به ریپو — پنل محلی مستقیم از دیسک می‌خواند",
    "hamid.dedupe_closed --apply":
        "پاک‌سازی ردیفِ تکراریِ دفتر — تکرار از دو رانرِ هم‌زمان می‌آمد",
    "hamid.experience_effect": "گزارش تحلیلی دوره‌ای، نه مسیر سیگنال",
    "hamid.polymarket": "منبع شاهد، در چرخهٔ کندتر",
    "hamid.work_report --hours 24": "همان کار با کلید work_report_log هست",
    "hamid.curriculum --verify": "همان کار با کلید curriculum هست",
    "hamid.trail_arms --write": "زیرمجموعهٔ گزارش کار",
    "hamid.trail_lab --bars --write": "زیرمجموعهٔ گزارش کار",
    "hamid.classify": "زیرمجموعهٔ میز تمرین",
    "hamid.bridge": "زیرمجموعهٔ میز تمرین",
    "hamid.improve": "زیرمجموعهٔ میز تمرین",
    "hamid.rule_ledger": "زیرمجموعهٔ میز تمرین",
    "hamid.levels_db": "زیرمجموعهٔ میز تمرین",
    "hamid.coin_history": "زیرمجموعهٔ میز تمرین",
    "hamid.fill_books": "زیرمجموعهٔ میز تمرین",
    "hamid.scalp_exec --mode demo": "زیرمجموعهٔ میز اسکلپ",
    "hamid.depth_collector --probe": "کاوش دستی",
    "hamid.depth_collector --stats": "گزارش خلاصه برای صفحهٔ Actions",
    "hamid.pump_radar --min-pct": "رادار پامپ داخل pump_desk صدا زده می‌شود",
}


# ── محیط ───────────────────────────────────────────────────────────────
def load_env():
    """`live.env` کنار ریپو — توکن از فایل، نه از ترمینال (قانون ۰۵).

    فایل در `.gitignore` است و هرگز کامیت نمی‌شود.
    """
    f = ROOT / "live.env"
    if not f.exists():
        return False
    for ln in f.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return True


def base_env():
    e = dict(os.environ)
    e.setdefault("LIAM9_CANDLES", "perp")            # دستور ۳۱ اوت
    e["LIVE_EXECUTION"] = "false"                    # قانون ۰۵ — قفل
    e["PYTHONUNBUFFERED"] = "1"
    return e


# ── اجرای یک کار ───────────────────────────────────────────────────────
def run_job(job, env=None, cwd=None):
    t0 = time.time()
    try:
        p = subprocess.run(job["cmd"], cwd=str(cwd or PY), env=env or base_env(),
                           capture_output=True, text=True,
                           timeout=job.get("timeout", 300))
        ok, code = p.returncode == 0, p.returncode
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-3:]
    except subprocess.TimeoutExpired:
        ok, code, tail = False, "timeout", [f"از {job.get('timeout')}s گذشت"]
    except Exception as e:                           # noqa: BLE001
        ok, code, tail = False, type(e).__name__, [str(e)[:200]]
    return {"key": job["key"], "ok": ok, "code": code,
            "secs": round(time.time() - t0, 1), "tail": tail,
            "ts": int(time.time() * 1000)}


def _sandboxed(path):
    """حالت شنی: پاسبان حق ندارد دفتر تولید را بنویسد (۴ سپتامبر).

    عیبِ واقعیِ همین ماژول: اجرای `test_liam9d` فایل
    `signals/liam9d.json` را در درختِ تولید ساخت — چون این‌جا مستقیم
    `write_text` صدا زده می‌شد و از `brain.blocked` رد نمی‌شد. دقیقاً
    همان کلاسی که همان روز برای `paper._write` و `liam9_link` بسته شده
    بود و این ماژولِ تازه دوباره بازش کرد. مرز از **مسیر** می‌آید، پس
    هر نویسندهٔ تازه باید از همین‌جا اجازه بگیرد.
    """
    try:
        import brain
        return brain.blocked(path)
    except Exception:                                # noqa: BLE001
        return False


def _append_log(rec):
    if _sandboxed(LOG):
        return
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # حلقهٔ همیشه‌روشن یعنی لاگ بی‌سقف دیسک را می‌خورد؛ هرس می‌شود.
        lines = LOG.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_LOG * 2:
            LOG.write_text("\n".join(lines[-MAX_LOG:]) + "\n", encoding="utf-8")
    except Exception:                                # noqa: BLE001
        pass


# ── دکتر: آیا این ماشین آماده است؟ ─────────────────────────────────────
#
# چرا این هست: «روی لپ‌تاپ من کار نکرد» بدترین حالتِ ممکن است، چون
# نمی‌شود از راه دور دیدش. دکتر همان لحظه می‌گوید کدام تکه غایب است، با
# جملهٔ فارسیِ کاری — نه ردِّ خطای پایتون.
def doctor(verbose=True):
    rows = []

    def add(name, ok, note=""):
        rows.append({"چه چیزی": name, "ok": bool(ok), "توضیح": note})

    add("پایتون ۳.۹ به بالا", sys.version_info >= (3, 9),
        ".".join(map(str, sys.version_info[:3])))
    for mod, why in (("requests", "گرفتن کندل"), ("matplotlib", "چارت سیگنال"),
                     ("arabic_reshaper", "فارسیِ چسبان روی چارت"),
                     ("bidi", "راست‌به‌چپ روی چارت"), ("yaml", "خواندن تنظیمات")):
        try:
            __import__(mod)
            add(f"کتابخانهٔ {mod}", True, why)
        except Exception:                            # noqa: BLE001
            add(f"کتابخانهٔ {mod}", False,
                f"{why} — نصب: pip install -r requirements-ci.txt")

    add("پوشهٔ ریپو", (ROOT / "index.html").exists(), str(ROOT))
    add("فضای دیسک ≥ ۲ گیگ",
        shutil.disk_usage(str(ROOT)).free > 2 * 1024**3,
        f"{shutil.disk_usage(str(ROOT)).free / 1024**3:.1f} گیگ آزاد")

    had_env = load_env()
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    add("توکن تلگرام", bool(tok),
        "از live.env" if had_env and tok else
        "نیست — فایل live.env بساز با TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID")
    add("شناسهٔ چت تلگرام", bool(chat), chat or "نیست")

    # شبکه — و عمداً **درخواست واقعی**، نه پینگ.
    #
    # نسخهٔ اولِ همین دکتر با `socket.create_connection` می‌سنجید و روی
    # همین ماشین سبزِ دروغین داد: پروکسی اتصال TCP را می‌پذیرفت و بعد
    # خودِ HTTP را رد می‌کرد، پس «دسترسی ✓» کنارِ «کندل نیامد ✗» چاپ شد.
    # دکتری که سبزِ دروغین بدهد از نبودنش بدتر است.
    for url, why in (("https://fapi.bitunix.com/api/v1/futures/market/kline"
                      "?symbol=BTCUSDT&interval=5m&limit=1", "کندل پرپ بیت‌یونیکس"),
                     ("https://api.telegram.org/", "ارسال سیگنال"),
                     ("https://api.coingecko.com/api/v3/ping", "قیمت/بازار")):
        host = url.split("/")[2]
        ok, note = _http_ok(url)
        add(f"دسترسی به {host}", ok, why if ok else f"{why} — {note}")

    # منبع کندل واقعاً کندل می‌دهد؟ این از پینگ محکم‌تر است.
    try:
        import sources
        k = sources.klines("BTCUSDT", "5m", 50, quiet=True)
        add("کندل واقعی می‌آید", bool(k) and len(k) >= 45,
            f"{len(k) if k else 0} کندل ۵د BTCUSDT")
    except Exception as e:                           # noqa: BLE001
        add("کندل واقعی می‌آید", False, f"{type(e).__name__}: {str(e)[:80]}")

    add("پورت پنل آزاد است", _port_free(HOST, PORT), f"{HOST}:{PORT}")

    if verbose:
        bad = [r for r in rows if not r["ok"]]
        print("\n  دکترِ لیام‌۹ — آمادگی این ماشین\n" + "  " + "─" * 52)
        for r in rows:
            print(f"  {'✓' if r['ok'] else '✗'} {r['چه چیزی']:<28} {r['توضیح']}")
        print("  " + "─" * 52)
        print(f"  {len(rows) - len(bad)} از {len(rows)} آماده"
              + (f" · {len(bad)} مانده" if bad else " · همه‌چیز آماده است"))
        if bad:
            print("\n  تا این‌ها درست نشوند سرویس کامل کار نمی‌کند:")
            for r in bad:
                print(f"    — {r['چه چیزی']}: {r['توضیح']}")
    return rows


def _http_ok(url, timeout=8):
    """درخواست واقعی. هر پاسخِ HTTP (حتی ۴۰۴) یعنی راه باز است؛ فقط
    نرسیدن به سرور شکست است."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "liam9d/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return True, f"HTTP {e.code} — سرور جواب داد، راه باز است"
    except Exception as e:                           # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:70]}"


def _port_free(host, port):
    s = socket.socket()
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


# ── پنل محلی ───────────────────────────────────────────────────────────
#
# چرا: پنل تا امروز از gh-pages خوانده می‌شد، یعنی هر عدد باید یک deploy
# صبر می‌کرد. این‌جا همان `index.html` مستقیم روی فایل‌های `signals/`
# می‌نشیند — چیزی که سرویس همین ثانیه نوشت، همین ثانیه دیده می‌شود.
DENY = (".git", "live.env", ".env", ".venv", "node_modules", ".ssh")


def serve(host=HOST, port=PORT):
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT), **kw)

        def translate_path(self, path):
            p = super().translate_path(path)
            # سکرت و تاریخچهٔ گیت هرگز سرو نمی‌شوند (قانون ۰۵)
            rel = Path(p).relative_to(ROOT) if str(p).startswith(str(ROOT)) else None
            if rel and any(part in DENY for part in rel.parts):
                return str(ROOT / "__denied__")
            return p

        def end_headers(self):
            # بی‌کش: پنل باید تازه‌ترین فایل روی دیسک را ببیند، نه نسخهٔ مرورگر
            self.send_header("Cache-Control", "no-store, must-revalidate")
            super().end_headers()

        def log_message(self, *a):                   # لاگِ هر GET لازم نیست
            pass

    class S(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, *a):
            # بستنِ تبِ مرورگر وسطِ دانلود، ConnectionReset می‌دهد. این
            # خرابی نیست و ردِّ خطای پایتون روی کنسولِ سرویسِ همیشه‌روشن
            # فقط آدم را می‌ترساند.
            pass

    srv = S((host, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ── حلقه ───────────────────────────────────────────────────────────────
def _due(job, last, now):
    return now - last.get(job["key"], 0.0) >= job["every"]


def loop(once=False, only=None, tick=TICK_S, quiet=False):
    """یک حلقهٔ سریال، به ترتیب جدول.

    عمداً تک‌رشته‌ای است: قانون ۰۵ می‌گوید هر دامنهٔ وضعیت یک نویسنده
    دارد، و دقیقاً همان چیزی که در Actions با دو رانرِ هم‌زمان شکست
    (دفتر پیپر، دفتر ضدتکرار) این‌جا با یک نویسنده اصلاً پیش نمی‌آید.
    اسکن — که محصول است — اولِ جدول است و هر تیک اول او سنجیده می‌شود.
    """
    jobs = [j for j in JOBS if not only or j["key"] in only]
    last = {}
    env = base_env()
    n = 0
    while True:
        n += 1
        t0 = time.time()
        ran = []
        for job in jobs:
            if not once and not _due(job, last, t0):
                continue
            if job.get("tg") and not os.environ.get("TELEGRAM_BOT_TOKEN"):
                # بی‌توکن، کارِ ارسالی اجرا نمی‌شود — نه اینکه بی‌صدا رد شود
                last[job["key"]] = t0
                ran.append({"key": job["key"], "ok": None, "code": "بی‌توکن",
                            "secs": 0.0, "tail": [], "ts": int(t0 * 1000)})
                continue
            r = run_job(job, env)
            last[job["key"]] = time.time()
            ran.append(r)
            _append_log(r)
            if not quiet:
                mark = "✓" if r["ok"] else ("·" if r["ok"] is None else "✗")
                print(f"  {mark} {job['key']:<18} {r['secs']:>6.1f}s  {job['desc']}",
                      flush=True)
                if not r["ok"] and r["ok"] is not None:
                    for ln in r["tail"]:
                        print(f"      ↳ {ln[:160]}", flush=True)
        write_state(n, ran, last, tick)
        if once:
            return ran
        time.sleep(max(1.0, tick - (time.time() - t0)))


def write_state(n, ran, last, tick):
    ok = [r for r in ran if r["ok"]]
    bad = [r for r in ran if r["ok"] is False]
    snap = {
        "generated": int(time.time() * 1000), "engine": "E23",
        "panel": "لیام تریدر ۹", "mode": "محلی — بدون گیت‌هاب",
        "tick_s": tick, "ticks": n,
        "ran": len(ran), "ok": len(ok), "failed": len(bad),
        "jobs": {k: {"last_ms": int(v * 1000),
                     "age_s": round(time.time() - v)} for k, v in last.items()},
        "last_failures": [{"key": r["key"], "code": r["code"], "tail": r["tail"]}
                          for r in bad][:8],
        "boundary": "این سرویس سیگنال می‌فرستد، سفارش نه. LIVE_EXECUTION=false "
                    "و هیچ دروازه‌ای نسبت به Actions شل نشده — همان فرمان‌ها، "
                    "همان پرچم‌ها، فقط بدون رقصِ گیت.",
    }
    if not _sandboxed(STATE):
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        except Exception:                            # noqa: BLE001
            pass
    return snap


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    load_env()
    if "--doctor" in argv:
        rows = doctor()
        return 0 if all(r["ok"] for r in rows) else 1
    only = None
    for a in argv:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
    tick = TICK_S
    for a in argv:
        if a.startswith("--tick="):
            tick = float(a.split("=", 1)[1])
    if "--once" in argv:
        ran = loop(once=True, only=only, tick=tick)
        bad = [r for r in ran if r["ok"] is False]
        print(f"\nیک دور کامل — {len(ran)} کار، {len(bad)} ناموفق")
        return 1 if bad else 0

    rows = doctor(verbose=False)
    bad = [r for r in rows if not r["ok"]]
    if bad:
        print("⚠ این ماشین کاملاً آماده نیست — سرویس بالا می‌آید ولی این‌ها لنگ‌اند:")
        for r in bad:
            print(f"    — {r['چه چیزی']}: {r['توضیح']}")
        print("  (فهرست کامل: python3 -m hamid.liam9d --doctor)\n")
    if "--no-panel" not in argv:
        try:
            serve()
            print(f"پنل محلی: http://{HOST}:{PORT}   ← همین را در مرورگر باز کن")
        except OSError as e:
            print(f"پنل بالا نیامد ({e}) — سرویس بدون پنل ادامه می‌دهد")
    print(f"لیام‌۹ محلی روشن شد · ضربان {tick:.0f}s · {len(JOBS)} کار · "
          f"بدون گیت‌هاب در مسیر سیگنال\nتوقف: Ctrl+C\n")
    try:
        loop(tick=tick, only=only)
    except KeyboardInterrupt:
        print("\nخاموش شد.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
