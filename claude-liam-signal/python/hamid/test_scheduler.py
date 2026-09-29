"""پاسبان زمان‌بندِ داخلی (۲۹ سپتامبر) — خاصیت، نه شکل.

۱. کرون درست خوانده می‌شود (لیست، */N، بازه، روزِ هفته).
۲. سررسیدِ قبلی درست است و فاصلهٔ کرون از خودش مشتق می‌شود.
۳. تصمیم: در حال اجرا → دست نزن · از سررسید اجرا شده → on_time · تازه
   سررسید → grace · پادزهر · وگرنه due. هیچ عددی جعل نمی‌شود.
۴. پوشش: هر ورک‌فلوی کرون‌دار و dispatch‌پذیرِ ریپو managed است؛ استثناها
   فقط همان دو حلقهٔ خودگردان و با دلیلِ نوشته‌شده.
۵. بی توکن فقط طرح می‌دهد؛ بی --dispatch هیچ تماس نوشتنی نمی‌زند.
۶. سیم‌کشی: زنجیره و ضربان هر دو --dispatch می‌زنند؛ ردیف قرارداد هست.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import scheduler as S                                # noqa: E402

OK, BAD = [], []


def check(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  — {extra}" if extra and not cond else ""))


U = timezone.utc
T = lambda *a: datetime(*a, tzinfo=U)                            # noqa: E731

# ── ۱. کرون ──────────────────────────────────────────────────────────────
c = S.parse_cron("7,22,37,52 * * * *")
check("لیست دقیقه", c["min"] == {7, 22, 37, 52} and c["hour"] == set(range(24)))
c = S.parse_cron("*/15 * * * *")
check("*/N", c["min"] == {0, 15, 30, 45})
c = S.parse_cron("13 2,7,12,17,21 * * *")
check("لیست ساعت", c["hour"] == {2, 7, 12, 17, 21} and c["min"] == {13})
c = S.parse_cron("37 3 * * 0")
check("روزِ هفته (یکشنبه=۰)", c["dow"] == {0, 7} and not c["dow_any"])
c = S.parse_cron("0 1-3 * * *")
check("بازه", c["hour"] == {1, 2, 3})
try:
    S.parse_cron("1 2 3")
    check("کرونِ ناقص رد می‌شود", False)
except ValueError:
    check("کرونِ ناقص رد می‌شود", True)

# ── ۲. سررسید و فاصله ───────────────────────────────────────────────────
now = T(2026, 9, 29, 11, 47, 30)
check("سررسید قبلیِ ربع‌ساعتی", S.prev_due("7,22,37,52 * * * *", now) == T(2026, 9, 29, 11, 37))
check("فاصلهٔ ربع‌ساعتی = ۱۵", S.interval_min("7,22,37,52 * * * *", now) == 15)
check("سررسید قبلیِ ساعتی", S.prev_due("19 * * * *", now) == T(2026, 9, 29, 11, 19))
check("سررسیدِ دقیقاً روی now", S.prev_due("47 11 * * *", now) == T(2026, 9, 29, 11, 47))
check("پامپ ۵ نوبته: سررسید ۰۷:۱۳", S.prev_due("13 2,7,12,17,21 * * *", now) == T(2026, 9, 29, 7, 13))
check("فاصلهٔ ۵ نوبته از خودش (۰۲:۱۳→۰۷:۱۳ = ۳۰۰)", S.interval_min("13 2,7,12,17,21 * * *", now) == 300)
# ۲۹ سپتامبر ۲۰۲۶ سه‌شنبه است؛ یکشنبهٔ قبل ۲۷ سپتامبر
check("هفتگی یکشنبه", S.prev_due("37 3 * * 0", now) == T(2026, 9, 27, 3, 37))
check("فاصلهٔ هفتگی = ۱۰۰۸۰", S.interval_min("37 3 * * 0", now) == 10080)


# ── ۳. تصمیم (بی‌شبکه) ─────────────────────────────────────────────────
def row(cron="7,22,37,52 * * * *", mode="managed"):
    return {"workflow": "x.yml", "name": "x", "crons": [cron], "dispatchable": True, "mode": mode}


def run_at(ts, status="completed"):
    return {"created_at": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "status": status}


d = S.decide(row(), [run_at(T(2026, 9, 29, 11, 24)), run_at(T(2026, 9, 29, 11, 8))], now, None)
check("از سررسید ۱۱:۳۷ اجرا نشده و ۱۰ دقیقه گذشته → due", d["verdict"] == "due", str(d))
check("overdue_min ثبت می‌شود", d.get("overdue_min") == 10.5)
check("lag از آخرین اجرا", d["lag_min"] == 23.5)
d = S.decide(row(), [run_at(T(2026, 9, 29, 11, 38))], now, None)
check("اجرا بعد از سررسید → on_time", d["verdict"] == "on_time")
d = S.decide(row(), [run_at(T(2026, 9, 29, 11, 36, 30))], now, None)
check("اجرای ۳۰ ثانیه پیش از سررسید (کرونِ خودِ گیت‌هاب زودتر زد) → on_time", d["verdict"] == "on_time")
d = S.decide(row(), [run_at(T(2026, 9, 29, 11, 24)), run_at(T(2026, 9, 29, 11, 40), "in_progress")], now, None)
check("در حال اجرا → running، هرگز due", d["verdict"] == "running")
d = S.decide(row(), [run_at(T(2026, 9, 29, 11, 24)), run_at(T(2026, 9, 29, 11, 46), "queued")], now, None)
check("در صف → running", d["verdict"] == "running")
d = S.decide(row(), [run_at(T(2026, 9, 29, 11, 24))], T(2026, 9, 29, 11, 39), None)
check("۲ دقیقه بعد از سررسید → grace (فرصت به کرونِ گیت‌هاب)", d["verdict"] == "grace")
wake = int(T(2026, 9, 29, 11, 42).timestamp() * 1000)
d = S.decide(row(), [run_at(T(2026, 9, 29, 11, 24))], now, wake)
check("بیدارسازیِ ۵ دقیقه پیش → cooldown (کف ۱۰ د)", d["verdict"] == "cooldown", str(d))
d = S.decide(row(), [run_at(T(2026, 9, 29, 11, 24))], now, wake - 12 * 60000)
check("بیدارسازیِ ۱۷ دقیقه پیش → دوباره due", d["verdict"] == "due")
d = S.decide(row(), [], now, None)
check("هرگز اجرا نشده → due با «هرگز»", d["verdict"] == "due" and "هرگز" in d["why"])
d = S.decide(row(mode="self_driven"), [], now, None)
check("خطِ خودگردان تصمیم نمی‌گیرد", d["verdict"] == "self_driven")
d = S.decide(row(cron="37 3 * * 0"), [run_at(T(2026, 9, 27, 3, 40))], now, None)
check("هفتگیِ اجراشده → on_time", d["verdict"] == "on_time")

# ── ۴. پوشش از منبع حقیقت ───────────────────────────────────────────────
plan = S.plan()
WF = S.WF_DIR
cron_files = sorted(f.name for f in WF.glob("*.yml") if "cron:" in f.read_text(encoding="utf-8"))
check("هر ورک‌فلوی کرون‌دار در طرح هست", sorted(r["workflow"] for r in plan) == cron_files,
      str(set(cron_files) ^ {r["workflow"] for r in plan}))
managed = {r["workflow"] for r in plan if r["mode"] == "managed"}
excl = {r["workflow"]: r.get("why") for r in plan if r["mode"] != "managed"}
check("دست‌کم ۲۰ خط managed است", len(managed) >= 20, str(len(managed)))
check("استثناها فقط دو حلقهٔ خودگردان‌اند، هر کدام با دلیل",
      set(excl) <= set(S.SELF_DRIVEN) | {r["workflow"] for r in plan if not r["dispatchable"]}
      and all(excl.values()), str(excl))
check("زنجیره و ضربان خودگردان‌اند (زمان‌بند خودش را صدا نمی‌زند)",
      "pump-radar.yml" in excl and "heartbeat.yml" in excl)
for r in plan:
    if r["mode"] == "managed" and not all(len(c.split()) == 5 for c in r["crons"]):
        check(f"کرونِ {r['workflow']} پنج‌فیلدی است", False, str(r["crons"]))
check("هر کرونِ managed سررسید و فاصله دارد",
      all(S.prev_due(c, now) and S.interval_min(c, now) for r in plan if r["mode"] == "managed" for c in r["crons"]))

# ── ۵. بی توکن / بی dispatch ───────────────────────────────────────────
_env = {k: os.environ.pop(k) for k in ("GITHUB_TOKEN", "GH_TOKEN") if k in os.environ}
res = S.run(dispatch=True, write=False, now=now)
check("بی توکن: حالت plan_only، صفر تماس، صفر بیدارسازی",
      res["mode"] == "plan_only" and res["api_calls"] == 0 and res["n_dispatched"] == 0)
check("بی توکن: هر ردیف no_data با دلیل (عدد جعل نمی‌شود)",
      all(r["verdict"] == "no_data" and r.get("why") for r in res["rows"]))
os.environ.update(_env)
from hamid import evidence_packet as EP                         # noqa: E402
check("بستهٔ شواهد کامل است", not EP.validate(res["packet"]), str(EP.validate(res["packet"])))

# ── ۶. سیم‌کشی ─────────────────────────────────────────────────────────
root = HERE.parents[2]
chain = (root / ".github/workflows/pump-radar.yml").read_text(encoding="utf-8")
hb = (root / ".github/workflows/heartbeat.yml").read_text(encoding="utf-8")
check("زنجیره --dispatch می‌زند", "hamid.scheduler --dispatch" in chain)
check("ضربان --dispatch می‌زند", "hamid.scheduler --dispatch" in hb)
reg = json.loads((root / "config/state_registry.json").read_text(encoding="utf-8"))["files"]
check("ردیف قرارداد scheduler.json (مالک E23، live، سقف دارد)",
      reg.get("scheduler.json", {}).get("owner") == "E23"
      and reg["scheduler.json"].get("kind") == "live" and reg["scheduler.json"].get("max_age_min"))
check("پرستار انجین‌ها سرِ جایش است (مکملِ بر کهنگیِ فایل)",
      "engine_nurse --write" in chain)

print()
if BAD:
    print(f"✗ {len(BAD)} بررسی افتاد: {BAD}")
    sys.exit(1)
print(f"پاسبان زمان‌بند: هر {len(OK)} بررسی سبز")
