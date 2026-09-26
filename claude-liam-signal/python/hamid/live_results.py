#!/usr/bin/env python3
"""دفتر نتایج لایو بیت‌یونیکس — تطبیق دقیق با سیگنال‌های ارسالی (قانون ۱۸ بند ۵).

حمید: «نتایج ترید لایو در بیت‌یونیکس خیلی برام مهمه.»

مرز صادقانه: این ریپو کلید API بیت‌یونیکس ندارد و نباید داشته باشد (قانون
۰۵: سکرت فقط در محیط امن). پس نتایج از **فایلی** می‌آیند که داشبورد یا
صرافی صادر می‌کند و در `brain/holding/inbox/` گذاشته می‌شود
(`bitunix*.csv` یا `bitunix*.json`). ستون‌ها با نگاشتِ نرم شناخته
می‌شوند (symbol/side/open/close/pnl/time با املاهای رایج)؛ ستونی که
پیدا نشد، `None` می‌ماند — حدس زده نمی‌شود.

تطبیق به سیگنالِ ارسالی (دفتر بسته/باز با `why.tg_msg_id`): همان نماد،
همان جهت، ورود در ±۰.۶٪ و زمانِ باز شدن در ±۹۰ دقیقه. ردیفی که تطبیق
نخورد «بی‌تطبیق» می‌ماند و جدا شمرده می‌شود.

خروجی: `signals/live-results.json` + دفتر append-only
`brain/live/bitunix.jsonl` (هویت = هشِ ردیف؛ تکرار نوشته نمی‌شود).

    python3 -m hamid.live_results --write
    python3 -m hamid.live_results --selftest
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import statistics
import sys
import time
from pathlib import Path
from hamid import ledger as _ledger                   # noqa: E402 - دفتر هفتگی‌پاره

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
INBOX = ROOT / "brain" / "holding" / "inbox"
LEDGER = ROOT / "brain" / "live" / "bitunix.jsonl"
OUT = ROOT / "signals" / "live-results.json"
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OPEN = ROOT / "brain" / "paper" / "open.jsonl"

COLS = {
    "symbol": ("symbol", "pair", "market", "نماد", "contract"),
    "side": ("side", "direction", "position side", "جهت", "type"),
    "entry": ("open price", "entry price", "entry", "avg entry", "open", "ورود"),
    "exit": ("close price", "exit price", "exit", "avg close", "close", "خروج"),
    "pnl": ("realized pnl", "pnl", "profit", "closed pnl", "realized", "سود"),
    "qty": ("qty", "quantity", "size", "amount", "حجم"),
    "opened": ("open time", "opened", "entry time", "created", "زمان باز"),
    "closed": ("close time", "closed", "exit time", "updated", "زمان بسته"),
}


def _norm(h):
    return str(h or "").strip().lower().replace("_", " ")


def map_columns(headers):
    m = {}
    hs = [_norm(h) for h in headers]
    for key, names in COLS.items():
        for cand in names:
            for i, h in enumerate(hs):
                if h == cand or (cand in h and key not in m):
                    m[key] = headers[i]
                    break
            if key in m:
                break
    return m


def _f(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _t(x):
    if x in (None, ""):
        return None
    try:
        v = float(x)
        return int(v if v > 1e11 else v * 1000)
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return int((time.mktime(time.strptime(str(x)[:19], fmt)) - time.timezone) * 1000)
        except ValueError:
            continue
    return None


def parse(text: str, name="x.csv"):
    rows = []
    if name.lower().endswith(".json"):
        try:
            data = json.loads(text)
        except Exception:                            # noqa: BLE001
            return []
        if isinstance(data, dict):
            data = data.get("data") or data.get("rows") or data.get("list") or []
        if not isinstance(data, list) or not data:
            return []
        headers = list(data[0].keys())
        recs = data
    else:
        rd = csv.DictReader(io.StringIO(text))
        headers = rd.fieldnames or []
        recs = list(rd)
    cm = map_columns(headers)
    for r in recs:
        g = lambda k: r.get(cm[k]) if k in cm else None       # noqa: E731
        side = str(g("side") or "").lower()
        rows.append({"sym": str(g("symbol") or "").upper().replace("/", "").replace("-", "") or None,
                     "dir": ("LONG" if any(w in side for w in ("long", "buy", "خرید")) else
                             "SHORT" if any(w in side for w in ("short", "sell", "فروش")) else None),
                     "entry": _f(g("entry")), "exit": _f(g("exit")), "pnl": _f(g("pnl")),
                     "qty": _f(g("qty")), "opened": _t(g("opened")), "closed": _t(g("closed"))})
    return rows


def _sent_signals():
    out = []
    for p in (CLOSED, OPEN):
        if not _ledger.exists(p):
            continue
        for ln in _ledger.text_lines(p):
            try:
                r = json.loads(ln)
            except Exception:                        # noqa: BLE001
                continue
            if (r.get("why") or {}).get("tg_msg_id"):
                out.append(r)
    return out


def match(row, signals, px_tol=0.006, t_tol_ms=90 * 60000):
    best = None
    for s in signals:
        if s.get("sym") != row["sym"] or s.get("dir") != row["dir"]:
            continue
        if row["entry"] and s.get("entry") and abs(row["entry"] - s["entry"]) / s["entry"] > px_tol:
            continue
        if row["opened"] and s.get("opened") and abs(row["opened"] - s["opened"]) > t_tol_ms:
            continue
        if best is None or abs((row["opened"] or 0) - (s.get("opened") or 0)) < abs((row["opened"] or 0) - (best.get("opened") or 0)):
            best = s
    return best


def _hash(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def run(now_ms=None, inbox=None, ledger=None, signals=None):
    now = int(now_ms or time.time() * 1000)
    inbox = Path(inbox or INBOX)
    ledger = Path(ledger or LEDGER)
    sigs = signals if signals is not None else _sent_signals()
    seen = set()
    if ledger.exists():
        for ln in ledger.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(ln)["hash"])
            except Exception:                        # noqa: BLE001
                continue
    new = []
    files = sorted(p for p in inbox.glob("bitunix*") if p.suffix.lower() in (".csv", ".json")) if inbox.exists() else []
    for p in files:
        for row in parse(p.read_text(encoding="utf-8", errors="replace"), p.name):
            h = _hash(row)
            if h in seen or not row["sym"]:
                continue
            seen.add(h)
            m = match(row, sigs)
            new.append({**row, "hash": h, "file": p.name, "ingested": now,
                        "matched": bool(m), "tg_msg_id": (m or {}).get("why", {}).get("tg_msg_id")})
    if new:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as f:
            for r in new:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    allrows = []
    if ledger.exists():
        for ln in ledger.read_text(encoding="utf-8").splitlines():
            try:
                allrows.append(json.loads(ln))
            except Exception:                        # noqa: BLE001
                continue
    pn = [r["pnl"] for r in allrows if isinstance(r.get("pnl"), (int, float))]
    mt = [r for r in allrows if r.get("matched")]
    return {"generated": now, "n_files": len(files), "n_new": len(new), "n_total": len(allrows),
            "n_matched": len(mt), "n_unmatched": len(allrows) - len(mt),
            "pnl_sum": round(sum(pn), 4) if pn else None,
            "win_pct": round(100 * sum(1 for x in pn if x > 0) / len(pn), 1) if pn else None,
            "pnl_mean": round(statistics.fmean(pn), 4) if pn else None,
            "recent": [{k: r.get(k) for k in ("sym", "dir", "entry", "exit", "pnl", "closed", "matched")} for r in allrows[-10:]],
            "boundary": ("نتایج از فایلِ صادرشده می‌آیند نه از API (کلیدی در ریپو نیست). ردیفِ "
                         "بی‌تطبیق حدس زده نمی‌شود. n و روش روی خروجی است")}


def write(doc):
    try:
        import brain as _b
        if getattr(_b, "SANDBOX", False):
            return False
    except Exception:                                # noqa: BLE001
        pass
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def _selftest():
    import tempfile
    ok, fail = 0, []

    def check(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1; print(f"  ✓ {name}")
        else:
            fail.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))

    csv_txt = ("Symbol,Position Side,Open Price,Close Price,Realized PnL,Qty,Open Time,Close Time\n"
               "BTC/USDT,Long,100.0,103.0,12.5,0.1,2026-09-13 10:00:00,2026-09-13 12:00:00\n"
               "ETHUSDT,Short,50.0,49.0,3.0,1,2026-09-13 11:00:00,2026-09-13 11:30:00\n"
               "XYZUSDT,Long,,,-1.0,1,,\n")
    rows = parse(csv_txt, "bitunix-history.csv")
    check("سه ردیف پارس شد و نماد نرمال شد", len(rows) == 3 and rows[0]["sym"] == "BTCUSDT")
    check("جهت از Long/Short خوانده شد", rows[0]["dir"] == "LONG" and rows[1]["dir"] == "SHORT")
    check("ستونِ خالی None می‌ماند نه صفرِ ساختگی", rows[2]["entry"] is None and rows[2]["opened"] is None)
    check("زمان به میلی‌ثانیه رفت", rows[0]["opened"] and rows[0]["closed"] > rows[0]["opened"])
    jrows = parse(json.dumps({"data": [{"symbol": "SOLUSDT", "side": "buy", "openPrice": "20", "closePrice": "21", "realizedPnl": "1"}]}), "bitunix.json")
    check("JSON با کلیدهای camelCase هم پارس می‌شود", jrows and jrows[0]["sym"] == "SOLUSDT" and jrows[0]["entry"] == 20.0 and jrows[0]["dir"] == "LONG")
    t0 = rows[0]["opened"]
    sigs = [{"sym": "BTCUSDT", "dir": "LONG", "entry": 100.3, "opened": t0 - 20 * 60000, "why": {"tg_msg_id": 777}},
            {"sym": "BTCUSDT", "dir": "LONG", "entry": 100.0, "opened": t0 - 10 * 3600 * 1000, "why": {"tg_msg_id": 1}},
            {"sym": "ETHUSDT", "dir": "LONG", "entry": 50.0, "opened": rows[1]["opened"], "why": {"tg_msg_id": 2}}]
    m = match(rows[0], sigs)
    check("تطبیق: نزدیک‌ترین در زمان، داخل ±۰.۶٪ و ±۹۰د", m and m["why"]["tg_msg_id"] == 777)
    check("جهتِ مخالف تطبیق نمی‌خورد", match(rows[1], sigs) is None)
    tmp = Path(tempfile.mkdtemp(prefix="live-"))
    (tmp / "bitunix-history.csv").write_text(csv_txt, encoding="utf-8")
    d = run(now_ms=1_800_000_000_000, inbox=tmp, ledger=tmp / "l.jsonl", signals=sigs)
    check("سه ردیف تازه، یکی تطبیق‌خورده، بی‌تطبیق جدا شمرده شد", d["n_new"] == 3 and d["n_matched"] == 1 and d["n_unmatched"] == 2, str((d["n_new"], d["n_matched"], d["n_unmatched"])))
    check("سود جمع و نرخ برد از ستون pnl", d["pnl_sum"] == 14.5 and d["win_pct"] == round(100 * 2 / 3, 1))
    d2 = run(now_ms=1_800_000_000_001, inbox=tmp, ledger=tmp / "l.jsonl", signals=sigs)
    check("دورِ دوم تکرار نمی‌نویسد (هویت = هشِ ردیف)", d2["n_new"] == 0 and d2["n_total"] == 3)
    check("مرزِ «فایل نه API» روی خروجی", "API" in d["boundary"])
    import brain as _b
    old = getattr(_b, "SANDBOX", False); _b.SANDBOX = True
    try:
        check("در حالت شنی نمی‌نویسد", write(d) is False)
    finally:
        _b.SANDBOX = old
    print(f"\nlive_results: {ok} بررسی سبز" + (f" · {len(fail)} قرمز: {fail}" if fail else ""))
    return 1 if fail else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    d = run()
    print(f"live: {d['n_files']} فایل · {d['n_new']} تازه · {d['n_total']} کل · تطبیق {d['n_matched']} · بی‌تطبیق {d['n_unmatched']} · pnl {d['pnl_sum']}")
    if a.write:
        write(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
