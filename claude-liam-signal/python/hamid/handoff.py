#!/usr/bin/env python3
"""نسخهٔ انتقال به چتِ تازه — `claude-liam-signal/HANDOFF.md` (دستور حمید،
۱۳ سپتامبر).

حمید: «بعد از چند روز که دیدی چت سنگین شده، یک نسخه با همان امکانات را
بگو که به چت جدید انتقال بدیم و اونو پین کنم و از اونجا ادامه بدیم.»

قاعده‌ها (CLAUDE.md و `.claude/rules/`) در هر چتِ تازه خودکار بار
می‌شوند — پس این سند آن‌ها را **تکرار نمی‌کند**. فقط چیزی را می‌آورد
که در ریپو نیست یا پیدا کردنش گران است: آخرین اعدادِ معتبر با n و
مرز، حکم‌های باز، رشته‌های نیمه‌کاره، و «چه چیزی را دوباره نساز». هر
چرخه بازساخته می‌شود تا هر وقت حمید خواست، همان لحظه آماده باشد.

    python3 -m hamid.handoff --write
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
SIG = ROOT / "signals"
OUT = ROOT / "claude-liam-signal" / "HANDOFF.md"
THREADS = ROOT / "claude-liam-signal" / "OPEN-THREADS.md"


def _j(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return None


def _age(ms):
    if not isinstance(ms, (int, float)):
        return "—"
    m = (time.time() * 1000 - ms) / 60000
    return f"{m:.0f}د" if m < 120 else f"{m/60:.1f}س"


def section_state():
    s = _j(SIG / "system-state.json") or {}
    L = [f"- گذرگاه وضعیت (قانون ۱۳): **{s.get('verdict', '?')}** — "
         f"{s.get('n_files', '?')} فایل، {s.get('n_faults', '?')} عیب (سن {_age(s.get('generated'))})"]
    for f in (s.get("faults") or [])[:6]:
        L.append(f"  - {f if isinstance(f, str) else json.dumps(f, ensure_ascii=False)[:120]}")
    return L


def section_geometry():
    v = _j(SIG / "geometry-verdict.json") or {}
    if v.get("status") != "OK":
        return ["- داور هندسه: بی‌داده"]
    L = [f"- داور هندسه/شورت (بک‌تست {v.get('backtest_at')}, {v.get('symbols')} نماد، "
         f"{v['n_cells']} خانه، شیداک {v['alpha_per_test']}):"]
    for k in sorted(v["rows"]):
        r = v["rows"][k]
        if r.get("verdict") in ("PROMOTE", "REJECT") and r.get("n"):
            ci = r.get("ci") or ["?", "?"]
            L.append(f"  - `{k}` n={r['n']} strict={r['strict']:+.3f}R CI=[{ci[0]},{ci[1]}] → **{r['verdict']}**")
    L.append("  - ترفیع = پیشنهاد؛ هیچ دروازه‌ای عوض نشده (قانون ۰۳/۱۲)")
    return L


def section_exam():
    e = _j(SIG / "guardian-exam.json") or {}
    rows = e.get("guardians") or e.get("rows") or {}
    if not rows:
        return ["- امتحان مهارت ۱۲ مراقب: بی‌داده"]
    L = [f"- امتحان مهارت ۱۲ مراقب (سن {_age(e.get('generated'))}):"]
    for gid, r in (rows.items() if isinstance(rows, dict) else []):
        if isinstance(r, dict) and r.get("verdict"):
            L.append(f"  - {gid}: {r['verdict']}" + (f" (n={r.get('n_scored')})" if r.get("n_scored") else ""))
    return L[:14]


def section_buckets():
    b = _j(SIG / "buckets.json") or {}
    if not b:
        return ["- سطل‌ها (قانون ۱۷): هنوز ساخته نشده"]
    return [f"- سطل‌ها (قانون ۱۷): {b.get('n_items')} آیتم، {b.get('n_changed')} تغییر از دورِ قبل، "
            f"{len(b.get('engines') or {})} سطل انجین (سن {_age(b.get('generated'))}) — "
            "`python3 -m hamid.dispatch --bucket E00`"]


def build():
    now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    threads = THREADS.read_text(encoding="utf-8").strip() if THREADS.exists() else "_(فایل OPEN-THREADS.md نیست)_"
    L = [
        f"# نسخهٔ انتقال — لیام تریدر ۹ (بازساخت {now})",
        "",
        "> این سند را در چتِ تازه پین کن و بگو: «از HANDOFF.md ادامه بده». قاعده‌ها",
        "> (CLAUDE.md، `.claude/rules/*`) خودکار بار می‌شوند و این‌جا تکرار نشده‌اند.",
        "",
        "## ۱. وضعیت زندهٔ سامانه (خودکار، هر چرخه)",
        *section_state(),
        *section_buckets(),
        "",
        "## ۲. آخرین حکم‌های سنجش (خودکار)",
        *section_geometry(),
        *section_exam(),
        "",
        "## ۳. رشته‌های باز و «دوباره نساز» (دستی — `claude-liam-signal/OPEN-THREADS.md`)",
        threads,
        "",
        "## ۴. سه چیزی که هر چتِ تازه اول باید بزند",
        "1. `python3 -m hamid.state_bus --packet` — قبل از هر ادعای وضعیت (قانون ۱۳).",
        "2. `python3 -m hamid.dispatch --bucket E00` — چه چیزی از دورِ قبل عوض شده (قانون ۱۷).",
        "3. `git ls-remote --heads origin 'refs/heads/backup/*'` — بک‌آپِ تأییدشده قبل از هر دستهٔ تغییر.",
        "",
        "_مرز صادقانه: بخش‌های ۱ و ۲ از فایل‌های وضعیت خوانده می‌شوند و همان‌قدر تازه‌اند که سنِ کنارشان می‌گوید؛ بخش ۳ دست‌نویس است و فقط وقتی به‌روز است که آخرین چت آن را نوشته باشد._",
    ]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    md = build()
    if a.write:
        try:
            import brain as _b
            if getattr(_b, "SANDBOX", False):
                print(md)
                return 0
        except Exception:                            # noqa: BLE001
            pass
        OUT.write_text(md, encoding="utf-8")
        print(f"handoff: {len(md.splitlines())} خط → {OUT.relative_to(ROOT)}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
