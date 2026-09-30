"""زمان‌بندِ داخلی — کرونِ گیت‌هاب را جایگزین می‌کند، نه تکمیل (۲۹ سپتامبر).

ریشهٔ اندازه‌گیری‌شده (۱۲۰۰ اجرای آخر، ۲۸–۲۹ سپتامبر): گیت‌هاب رویداد
`schedule` را در این ریپو تقریباً **۴ بار در روز** برای هر ورک‌فلو اجرا
می‌کند، فارغ از کرونش — live-scan (کرون ۹۶/روز) ۴.۲، medic (۹۶) ۴.۲،
scout (۴۸) ۳.۵، dominance (۴۸) ۴.۲، dominance-report (۲۴) ۳.۵. هیچ خطایی
ثبت نمی‌شود؛ اجراها فقط کم‌اند. تا امروز سه وصلهٔ جدا این را جبران
می‌کردند (زنجیرهٔ خودفراخوان، فهرست دست‌نویس WAKE در زنجیره، پرستار
انجین‌ها بر کهنگی فایل) و هر کدام فهرستِ خودش را داشت — همان کلاسِ
«فهرستِ دست‌نویس» که قانون علت پیش از حادثه منع می‌کند.

درمانِ کلاس: **یک زمان‌بند، مشتق از منبع حقیقت** — کرونِ خودِ هر ورک‌فلو.
هر چند دقیقه (از داخل حلقه‌های همیشه‌روشن: زنجیرهٔ سیگنال و ضربان) هر
ورک‌فلوی کرون‌دار سنجیده می‌شود: آخرین سررسیدِ کرونش کِی بود، آخرین
اجرایش کِی بود؛ اگر از سررسید گذشته و اجرایی در راه نیست، با
workflow_dispatch (که گیت‌هاب قابل‌اتکا اجرا می‌کند؛ صفِ p95 = ۰) بیدار
می‌شود. کرونِ گیت‌هاب هم‌چنان تور ایمنی است — اگر خودش زد، این‌جا چیزی
dispatch نمی‌شود.

مرزها:
  · فقط ورک‌فلویی که هم `cron` دارد هم `workflow_dispatch`؛ بقیه گزارش‌اند.
  · زنجیرهٔ سیگنال (pump-radar.yml) خودش را صدا می‌زند و ضربان نگهبانِ
    خودش را دارد — هر دو استثنا هستند و در خروجی صریح نوشته می‌شوند.
  · «در حال اجرا/در صف» = دست نزن (concurrency هر خط محترم است).
  · پادزهر: هر خط حداکثر یک بار در نصفِ فاصلهٔ کرونش (کف ۱۰ دقیقه).
  · بی GITHUB_TOKEN یا بی `--dispatch` فقط گزارش می‌دهد؛ هیچ عددی جعل
    نمی‌شود (قانون ۱).
  · یک تماس API برای همهٔ خط‌ها (فهرست ۱۰۰ اجرای آخر) + فقط برای خط‌هایی
    که در آن فهرست نبودند یک تماس جدا — بودجهٔ API قیدِ طراحی است.

خروجی: signals/scheduler.json (ردیف قرارداد، مالک E23).

    python3 -m hamid.scheduler                 # فقط گزارش
    python3 -m hamid.scheduler --dispatch      # بیدارسازیِ واقعی (توکن لازم)
    python3 -m hamid.scheduler --write         # نوشتن signals/scheduler.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))
WF_DIR = ROOT / ".github" / "workflows"
OUT = ROOT / "signals" / "scheduler.json"
REPO = "AuraLiam/Liam-Trader-9"
ENGINE = "E23"

# خط‌هایی که خودشان همیشه‌روشن‌اند و زمان‌بند نباید صدایشان بزند
SELF_DRIVEN = {
    "pump-radar.yml": "زنجیرهٔ خودفراخوان — هر ~۳۰د خودش دورِ بعد را dispatch می‌کند",
    "heartbeat.yml": "حلقهٔ ۵.۵ساعته با نگهبانِ «فقط یک ضربان»؛ کرونِ ساعتی‌اش همان تور ایمنی است",
}
GRACE_MIN = 4          # فرصت به کرونِ خودِ گیت‌هاب پیش از بیدارسازی
COOLDOWN_FLOOR_MIN = 10
RUNS_PAGE = 100


# ── کرون ─────────────────────────────────────────────────────────────────
def _field(spec: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = b = int(part)
        out.update(range(a, b + 1, step))
    return out


def parse_cron(expr: str) -> dict:
    """پنج فیلد استاندارد → مجموعه‌های مجاز. dow: 0 و 7 هر دو یکشنبه."""
    f = expr.split()
    if len(f) != 5:
        raise ValueError(f"cron نامعتبر: {expr!r}")
    dow = _field(f[4], 0, 7)
    if dow & {0, 7}:
        dow |= {0, 7}
    return {"min": _field(f[0], 0, 59), "hour": _field(f[1], 0, 23),
            "dom": _field(f[2], 1, 31), "mon": _field(f[3], 1, 12),
            "dow": dow, "dom_any": f[2] == "*", "dow_any": f[4] == "*"}


def _matches(c: dict, t: datetime) -> bool:
    if t.minute not in c["min"] or t.hour not in c["hour"] or t.month not in c["mon"]:
        return False
    py_dow = (t.weekday() + 1) % 7            # دوشنبه=0 در پایتون → یکشنبه=0 در کرون
    dom_ok, dow_ok = t.day in c["dom"], py_dow in c["dow"]
    if c["dom_any"] and c["dow_any"]:
        return True
    if c["dom_any"]:
        return dow_ok
    if c["dow_any"]:
        return dom_ok
    return dom_ok or dow_ok                   # قاعدهٔ vixie-cron


def prev_due(expr: str, now: datetime, max_days: int = 8) -> datetime | None:
    """آخرین سررسیدِ ≤ now (دقیقه‌ای، به عقب)."""
    c = parse_cron(expr)
    t = now.replace(second=0, microsecond=0)
    for _ in range(max_days * 1440):
        if _matches(c, t):
            return t
        t -= timedelta(minutes=1)
    return None


def interval_min(expr: str, now: datetime) -> int | None:
    a = prev_due(expr, now)
    if a is None:
        return None
    b = prev_due(expr, a - timedelta(minutes=1))
    return int((a - b).total_seconds() // 60) if b else None


# ── منبع حقیقت: خودِ ورک‌فلوها ───────────────────────────────────────────
def _crons_of(text: str) -> list[str]:
    m = re.search(r"^\s*schedule:\s*$(.*?)^\s*(?:workflow_dispatch|push|pull_request|[a-z_]+):", text, re.M | re.S)
    block = m.group(1) if m else text
    return re.findall(r"cron:\s*['\"]([^'\"]+)['\"]", block)


def plan() -> list[dict]:
    """هر ورک‌فلوی کرون‌دار با وضعیت زمان‌بندپذیری‌اش."""
    rows = []
    for wf in sorted(WF_DIR.glob("*.yml")):
        t = wf.read_text(encoding="utf-8")
        if "cron:" not in t:
            continue
        crons = _crons_of(t)
        name = re.search(r"^name:\s*(.+)$", t, re.M)
        row = {"workflow": wf.name, "name": (name.group(1).strip().strip("'\"") if name else wf.name),
               "crons": crons, "dispatchable": "workflow_dispatch:" in t}
        if wf.name in SELF_DRIVEN:
            row["mode"] = "self_driven"; row["why"] = SELF_DRIVEN[wf.name]
        elif not row["dispatchable"]:
            row["mode"] = "report_only"; row["why"] = "workflow_dispatch ندارد — قابل‌بیدارسازی نیست"
        elif not crons:
            row["mode"] = "report_only"; row["why"] = "کرونی خوانده نشد"
        else:
            row["mode"] = "managed"
        rows.append(row)
    return rows


# ── API ──────────────────────────────────────────────────────────────────
def _api(url: str, tok: str, method: str = "GET", data: dict | None = None):
    req = urllib.request.Request(
        url, method=method, data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "liam9-scheduler/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return r.status, (json.loads(body) if body else {})


def recent_runs(tok: str) -> list[dict]:
    _, j = _api(f"https://api.github.com/repos/{REPO}/actions/runs?per_page={RUNS_PAGE}", tok)
    return j.get("workflow_runs") or []


def runs_of(workflow: str, tok: str) -> list[dict]:
    _, j = _api(f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/runs?per_page=3", tok)
    return j.get("workflow_runs") or []


def _ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ── تصمیم (خالص، بی‌شبکه — آزمون‌پذیر) ───────────────────────────────────
def decide(row: dict, runs: list[dict], now: datetime, last_wake_ms: int | None) -> dict:
    """runs: اجراهای همین ورک‌فلو (هر رویدادی). خروجی: حکم + اعداد."""
    r = dict(row)
    if row["mode"] != "managed":
        r["verdict"] = row["mode"]
        return r
    due = max((d for d in (prev_due(c, now) for c in row["crons"]) if d), default=None)
    iv = min((i for i in (interval_min(c, now) for c in row["crons"]) if i), default=None) or 60
    r["prev_due"] = due.isoformat() if due else None
    r["interval_min"] = iv
    active = [x for x in runs if x.get("status") in ("in_progress", "queued", "waiting", "requested", "pending")]
    last = max((_ts(x["created_at"]) for x in runs if x.get("created_at")), default=None)
    r["last_run"] = last.isoformat() if last else None
    r["lag_min"] = round((now - last).total_seconds() / 60, 1) if last else None
    if active:
        r["verdict"] = "running"; r["why"] = f"{len(active)} اجرا در حال اجرا/صف — دست نمی‌زنم"
        return r
    if due is None:
        r["verdict"] = "no_due"; r["why"] = "سررسیدی در ۸ روز اخیر نیست"
        return r
    if last is not None and last >= due - timedelta(minutes=1):
        r["verdict"] = "on_time"; r["why"] = "از آخرین سررسید اجرا شده"
        return r
    # ۳۰ سپتامبر: کرونِ گیت‌هاب گاهی رویدادِ ساعت‌ها پیش را دیر می‌زند (work-report
    # ۱۸:۰۲ برای کرون ۱۲:۳۰)؛ اگر همین تازگی اجرا شده، سررسیدِ بعدی را دوباره
    # نزن — نصفِ فاصلهٔ کرون «تازه» است (۲ اجرای زائد در ۲۸ ساعت اندازه‌گیری شد).
    if last is not None and (now - last).total_seconds() < iv * 30:
        r["verdict"] = "on_time"; r["why"] = f"اجرای تازه ({r['lag_min']:.0f}د < نصفِ فاصلهٔ {iv}د)"
        return r
    if (now - due).total_seconds() < GRACE_MIN * 60:
        r["verdict"] = "grace"; r["why"] = f"سررسید تازه است (<{GRACE_MIN}د) — فرصت به کرونِ گیت‌هاب"
        return r
    cd = max(COOLDOWN_FLOOR_MIN, iv // 2)
    if last_wake_ms and (now.timestamp() * 1000 - last_wake_ms) < cd * 60000:
        since = (now.timestamp() * 1000 - last_wake_ms) / 60000
        r["verdict"] = "cooldown"; r["why"] = f"بیدارسازی قبلی {since:.0f}د پیش؛ پادزهر {cd}د"
        return r
    r["verdict"] = "due"
    r["overdue_min"] = round((now - due).total_seconds() / 60, 1)
    r["why"] = (f"سررسید {due.strftime('%H:%M')} گذشته، آخرین اجرا "
                f"{last.strftime('%m-%d %H:%M') if last else 'هرگز'}")
    return r


# ── اجرا ─────────────────────────────────────────────────────────────────
def _load_out() -> dict:
    try:
        j = json.loads(OUT.read_text(encoding="utf-8"))
        return j if isinstance(j, dict) else {}
    except Exception:                                 # noqa: BLE001
        return {}


def run(dispatch: bool = False, write: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    rows = plan()
    prev = _load_out()
    wakes = dict(prev.get("wakes") or {})
    by_wf: dict[str, list] = {}
    api_calls = 0
    err = None
    if tok:
        try:
            for x in recent_runs(tok):
                by_wf.setdefault(Path(x.get("path") or "").name, []).append(x)
            api_calls += 1
            for row in rows:
                if row["mode"] == "managed" and row["workflow"] not in by_wf:
                    by_wf[row["workflow"]] = runs_of(row["workflow"], tok)
                    api_calls += 1
        except Exception as e:                        # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:160]
    out_rows, dispatched = [], []
    for row in rows:
        if not tok or err:
            d = dict(row); d["verdict"] = "no_data"
            d["why"] = err or "بی GITHUB_TOKEN — فقط طرح"
            out_rows.append(d); continue
        d = decide(row, by_wf.get(row["workflow"], []), now, (wakes.get(row["workflow"]) or {}).get("t"))
        if d["verdict"] == "due" and dispatch:
            try:
                st, _ = _api(f"https://api.github.com/repos/{REPO}/actions/workflows/{row['workflow']}/dispatches",
                             tok, "POST", {"ref": "main"})
                api_calls += 1
                ok = st in (200, 204)
            except Exception as e:                    # noqa: BLE001
                ok, st = False, f"{type(e).__name__}"
            d["dispatched"] = ok
            d["http"] = st
            if ok:
                wakes[row["workflow"]] = {"t": int(now.timestamp() * 1000), "overdue_min": d.get("overdue_min")}
                dispatched.append(row["workflow"])
        elif d["verdict"] == "due":
            d["dispatched"] = False; d["http"] = "بدون --dispatch"
        out_rows.append(d)
    managed = [r for r in out_rows if r["mode"] == "managed"]
    n_due = sum(1 for r in managed if r["verdict"] == "due")
    lags = sorted(r["lag_min"] for r in managed if r.get("lag_min") is not None)
    from hamid import evidence_packet as EP
    res = {
        "generated": int(now.timestamp() * 1000), "owner": ENGINE, "producer": "hamid/scheduler.py",
        "mode": "dispatch" if (dispatch and tok) else ("report" if tok else "plan_only"),
        "n_workflows": len(out_rows), "n_managed": len(managed), "n_due": n_due,
        "n_dispatched": len(dispatched), "dispatched": dispatched, "api_calls": api_calls,
        "error": err, "rows": out_rows, "wakes": wakes,
        "packet": EP.build(
            claim=(f"{len(managed)} خطِ کرون‌دار زیر نظر است؛ {n_due} خط از سررسید گذشته بود"
                   + (f" و {len(dispatched)} خط بیدار شد" if dispatch else "")),
            numbers={"خط": len(managed), "سررسیدگذشته": n_due, "بیدارشده": len(dispatched),
                     "تماس API": api_calls,
                     **({"میانهٔ فاصله از آخرین اجرا (د)": lags[len(lags) // 2]} if lags else {})},
            track_record=(f"پیش از این زمان‌بند (۲۸–۲۹ سپتامبر): کرونِ گیت‌هاب هر خط را ~۳.۵–۴.۲ بار در روز "
                          f"اجرا می‌کرد، فارغ از کرونش (live-scan ۹۶→۴.۲، medic ۹۶→۴.۲، dominance ۴۸→۴.۲)"),
            scenario_up="هر خط در فاصلهٔ کرونش + چند دقیقه اجرا می‌شود → سنِ فایل‌های وضعیت داخل سقفِ قرارداد می‌ماند",
            scenario_down=("حلقه‌های حامل (زنجیره/ضربان) بخوابند → زمان‌بند هم می‌خوابد؛ آن‌وقت فقط کرونِ "
                           "خودِ گیت‌هاب (~۴/روز) و پرستارِ انجین‌ها (بر کهنگی) می‌مانند"),
            invalidator="اگر lag_min خطی چند برابرِ interval_min بماند در حالی که verdict=due و dispatched=false است، زمان‌بند کار نمی‌کند",
            sources=[".github/workflows/*.yml (کرون‌ها)", "GitHub Actions API (اجراها)"],
            limit=("فقط dispatch می‌کند؛ نه دروازه، نه عدد، نه ترتیبِ اجرا را عوض نمی‌کند. کفِ واقعی فاصله "
                   "همان ۳–۵ دقیقهٔ حلقهٔ حامل است، نه ثانیه‌ای (قانون ۰۲/۱۳)")),
    }
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def _print(res: dict) -> None:
    print(f"زمان‌بند [{res['mode']}] — {res['n_managed']} خط · سررسیدگذشته {res['n_due']} · "
          f"بیدارشده {res['n_dispatched']} · API {res['api_calls']}"
          + (f" · خطا: {res['error']}" if res.get("error") else ""))
    for r in res["rows"]:
        if r["mode"] != "managed":
            continue
        print(f"  {r['verdict']:9s} {r['workflow']:26s} lag={r.get('lag_min')!s:>7} "
              f"iv={r.get('interval_min')!s:>5}  {r.get('why', '')}")


if __name__ == "__main__":
    a = sys.argv[1:]
    res = run(dispatch="--dispatch" in a, write="--write" in a)
    _print(res)
