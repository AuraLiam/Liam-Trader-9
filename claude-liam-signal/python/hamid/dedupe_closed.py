"""پاک‌سازی یک‌بارهٔ دفتر بسته از تسویه‌های تکراری (۲۴ اوت).

رفعِ ریشه‌ای در دو جای دیگر نشسته — `resolve_brain_conflicts.merge_jsonl`
(هویتِ معامله به‌جای متنِ خط) و `paper.mark` (پوزیشنِ از-قبل-بسته دوباره
تسویه نمی‌شود). ولی دفترِ **موجود** ۲۲٬۰۵۴ ردیفِ اضافه دارد که آن دو
خودشان پاک نمی‌کنند؛ کارِ این فایل همان است.

قاعدهٔ نگه‌داشتن: از هر معامله، **زودترین تسویه** می‌ماند. آن یکی لحظهٔ
واقعیِ برخورد را دیده؛ بقیه بازمحاسبه‌اند.

قانون ۰۵ (بدون پشتیبان و تأیید، بازنویسیِ دادهٔ runtime ممنوع):
پیش‌فرض این ابزار **فقط گزارش** است. نوشتن با `--apply` و همیشه بعد از
ساختن پشتیبان کنارِ فایل.

    python3 -m hamid.dedupe_closed              # فقط گزارش
    python3 -m hamid.dedupe_closed --apply      # پشتیبان + بازنویسی
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"


def key(rec):
    from hamid.paper import trade_key
    return trade_key(rec)


def scan(path=None):
    """→ (خطوطِ نگه‌داشتنی به ترتیب زمان، شمار حذف‌شده، شمار خطِ خراب)."""
    p = Path(path) if path else CLOSED
    best, order, dropped, broken = {}, [], 0, 0
    with p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                broken += 1
                continue
            k = key(rec)
            if k[0] is None and k[1] is None:       # ردیفِ بی‌هویت
                k = ("__raw__", line)
            c = rec.get("closed") or 0
            if k in best:
                dropped += 1
                if c < best[k][0]:
                    best[k] = (c, line)
                continue
            best[k] = (c, line)
            order.append(k)
    rows = sorted((best[k] for k in order), key=lambda x: x[0])
    return [l for _, l in rows], dropped, broken


def run(apply=False, path=None, quiet=False):
    p = Path(path) if path else CLOSED
    if not p.exists():
        print("دفتر بسته وجود ندارد")
        return {"kept": 0, "dropped": 0}
    keep, dropped, broken = scan(p)
    res = {"kept": len(keep), "dropped": dropped, "broken": broken,
           "total": len(keep) + dropped,
           "dup_pct": round(dropped / max(1, len(keep) + dropped) * 100, 1)}
    if not quiet:
        print(f"کل {res['total']} ردیف → {res['kept']} معاملهٔ یکتا · "
              f"{dropped} تسویهٔ تکراری ({res['dup_pct']}٪)"
              + (f" · {broken} خط خراب" if broken else ""))
    if not apply:
        if not quiet:
            print("فقط گزارش — برای نوشتن --apply بده (پشتیبان خودکار ساخته می‌شود)")
        return res
    if not dropped:
        return res
    bak = p.with_suffix(f".jsonl.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(p, bak)                            # پشتیبان قبل از هر نوشتن
    tmp = p.with_suffix(".jsonl.tmp")
    tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
    tmp.replace(p)                                  # جایگزینی اتمیک
    res["backup"] = bak.name
    if not quiet:
        print(f"نوشته شد. پشتیبان: {bak.name}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    run(apply=ap.parse_args().apply)
