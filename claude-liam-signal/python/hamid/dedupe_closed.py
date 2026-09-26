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
    """یک فایل (path) یا — پیش‌فرض — همهٔ فایل‌های دفتر بسته.

    دفتر بسته از ۲۶ سپتامبر هفتگی‌پاره است (hamid/ledger.py): فایلِ یخ‌زده و
    پاره‌های هفتگی هر کدام جدا تمیز می‌شوند. تکرارِ **بین** فایل‌ها را
    خواننده (`ledger.read`) بر هویت یکتا می‌کند — این‌جا هیچ ردیفی از یک
    فایل به فایلِ دیگر جابه‌جا نمی‌شود (قانون ضد-merge).
    """
    if path is not None:
        return _run_one(apply, Path(path), quiet)
    from hamid import ledger as _ledger
    fs = _ledger.files(CLOSED)
    if not fs:
        print("دفتر بسته وجود ندارد")
        return {"kept": 0, "dropped": 0}
    tot = {"kept": 0, "dropped": 0, "broken": 0, "total": 0, "files": []}
    for f in fs:
        r = _run_one(apply, f, quiet)
        for k in ("kept", "dropped", "broken", "total"):
            tot[k] += r.get(k, 0)
        tot["files"].append({"file": f.name, **{k: r.get(k) for k in ("kept", "dropped")}})
    tot["dup_pct"] = round(tot["dropped"] / max(1, tot["total"]) * 100, 1)
    tot["cross"] = _cross(apply, fs, quiet)
    return tot


def _cross(apply, fs, quiet):
    """ردیفِ فایلِ یخ‌زده که هویتش در پارهٔ **هفتهٔ خودش** هست — تکرارِ بین‌فایلی.

    ریشه (۲۶ سپتامبر): `receipts_guard.restore` کلِ دفتر (یخ‌زده + پاره) را در
    فایلِ یخ‌زده بازنویسی کرد و ۴٬۷۳۵ ردیفِ پارهٔ W39 دوباره آن‌جا نشست (رفع
    ریشه در همان ماژول). این پاک‌سازی همان کلاس را برای هر تکرارِ بعدی هم
    می‌گیرد. فقط از فایلِ یخ‌زده حذف می‌شود و فقط وقتی پارهٔ همان هفته همان
    هویت را دارد — پس هیچ معامله‌ای گم نمی‌شود؛ خانهٔ طبیعی‌اش پاره است.
    """
    from hamid import ledger as _ledger
    base = CLOSED
    parts = _ledger.parts(base)
    if not base.exists() or not parts:
        return {"dropped": 0}
    wk = {}
    for pp in parts:
        tag = pp.stem[len(base.stem) + 1:]
        keys = set()
        for ln in _ledger._lines(pp):
            try:
                keys.add(key(json.loads(ln)))
            except Exception:                        # noqa: BLE001
                pass
        wk[tag] = keys
    keep, dropped = [], 0
    for ln in _ledger._lines(base):
        try:
            r = json.loads(ln)
            ms = r.get("closed")
            tag = _ledger.week_tag(ms) if isinstance(ms, (int, float)) and ms > 1e12 else None
            if tag in wk and key(r) in wk[tag]:
                dropped += 1
                continue
        except Exception:                            # noqa: BLE001
            pass
        keep.append(ln)
    if not quiet:
        print(f"تکرارِ بین‌فایلی (یخ‌زده ∩ پارهٔ هفتهٔ خودش): {dropped}")
    if apply and dropped:
        bak = base.with_suffix(f".jsonl.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(base, bak)
        tmp = base.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
        tmp.replace(base)
    return {"dropped": dropped}


def _run_one(apply, p, quiet):
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
