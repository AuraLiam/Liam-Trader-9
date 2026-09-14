"""جمع‌آوری تدریجی کندل ۵ دقیقه — بستن شکاف ۵د بستهٔ تاریخی (دستور حمید، ۱۴ سپتامبر).

بستهٔ درایو فقط ۱۵د دارد؛ ۵د را نمی‌شود از ۱۵د ساخت و جعل هم نمی‌شود
(قانون ۱). این ماژول در Actions (نه لپ‌تاپ — مهارت signal-work) برای همان
جهان ۲۹۸ نمادیِ inventory کندل ۵د دو سال اخیر را تکه‌تکه می‌کشد:

  منبع (به ترتیب): data-api.binance.vision (آینهٔ عمومی دادهٔ اسپات) →
  api.binance.com → api.mexc.com. منبعِ هر نماد در مانیفست ثبت می‌شود.

  هر اجرا چند نماد را کامل می‌کند (بودجهٔ زمانی) و برای هر نماد:
  دریافت صفحه‌صفحه (۱۰۰۰تایی) → راستی‌آزمایی (زمان صعودی، بی‌تکرار،
  فاصلهٔ ۵د با ثبت شکاف‌ها، OHLC سالم) → فایل gzip JSONL → آپلود به
  GitHub Release با تگ history-5m-v1 (دادهٔ بزرگ در گیت نمی‌رود —
  قانون ۰۵) → ردیف مانیفست brain/research/history/5m-manifest.json.

  نمادی که راستی‌آزمایی را رد کند DONE نمی‌شود — FAILED با دلیل می‌ماند
  و اجرای بعد دوباره می‌کوشد. دادهٔ گمشده گمشده اعلام می‌شود، پر نمی‌شود.

اجرا (ورک‌فلوی candles-5m.yml):
  python3 -m hamid.candles5m --budget-min 12 --out-dir /tmp/c5m
"""
import argparse
import gzip
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
HIST = ROOT / "brain" / "research" / "history"
INVENTORY = HIST / "inventory.json"
MANIFEST = HIST / "5m-manifest.json"

TF_MS = 5 * 60 * 1000
TARGET_DAYS = 730                      # «دوساله» — لنگرِ ثابت در مانیفست
PAGE = 1000
PAUSE_S = 0.15                         # ادب نرخ؛ ~۲۱۰ صفحه بر نماد
MAX_GAP_RATIO = 0.05                   # بیش از ۵٪ ردیفِ گمشده = FAILED

SOURCES = [
    ("binance_vision", "https://data-api.binance.vision/api/v3/klines"),
    ("binance_spot", "https://api.binance.com/api/v3/klines"),
    ("mexc_spot", "https://api.mexc.com/api/v3/klines"),
]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "liam9-history"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch_symbol(sym, start_ms, end_ms, get=_get, pause=PAUSE_S):
    """کل بازه را از اولین منبعِ جواب‌گو می‌کشد؛ (منبع، ردیف‌ها) یا (None، دلیل)."""
    for name, base in SOURCES:
        rows, cur, dead = [], start_ms, False
        while cur < end_ms:
            url = (f"{base}?symbol={sym}&interval=5m&limit={PAGE}"
                   f"&startTime={cur}&endTime={end_ms}")
            try:
                page = get(url)
            except Exception:                        # noqa: BLE001
                dead = True
                break
            if not isinstance(page, list):
                dead = True
                break
            if not page:                             # قبل از لیست‌شدن نماد
                cur += PAGE * TF_MS
                continue
            rows += [[int(k[0]), float(k[1]), float(k[2]), float(k[3]),
                      float(k[4]), float(k[5])] for k in page]
            nxt = int(page[-1][0]) + TF_MS
            if nxt <= cur:                           # حلقهٔ بی‌پیشرفت (درس بیت‌یونیکس)
                dead = True
                break
            cur = nxt
            if len(page) < PAGE and cur < end_ms - TF_MS:
                cur = max(cur, int(page[-1][0]) + PAGE * TF_MS)
            time.sleep(pause)
        if not dead and rows:
            return name, rows
    return None, "هیچ منبعی جواب نداد"


def verify(rows, start_ms, end_ms):
    """راستی‌آزمایی به سبک venue-probe؛ (سالم؟، گزارش)."""
    if not rows:
        return False, {"why": "خالی"}
    seen, dups, bad_ohlc, gaps, missing = set(), 0, 0, 0, 0
    prev = None
    for t, o, h, l, c, v in rows:
        if t in seen:                                # زمان برابر = تکرار
            dups += 1
            continue
        seen.add(t)
        if prev is not None:
            if t < prev:
                return False, {"why": "زمان غیرصعودی"}
            d = t - prev
            if d > TF_MS:
                gaps += 1
                missing += d // TF_MS - 1
        prev = t
        if not (l <= min(o, c) <= max(o, c) <= h and l > 0 and v >= 0):
            bad_ohlc += 1
    expect = max(1, (rows[-1][0] - rows[0][0]) // TF_MS + 1)
    rep = {"rows": len(rows), "first_ms": rows[0][0], "last_ms": rows[-1][0],
           "dups": dups, "bad_ohlc": bad_ohlc, "gaps": gaps,
           "missing_rows": int(missing),
           "coverage_pct": round(100 * len(rows) / expect, 2)}
    ok = (dups == 0 and bad_ohlc == 0
          and missing / expect <= MAX_GAP_RATIO)
    if not ok:
        rep["why"] = ("تکراری" if dups else
                      "OHLC خراب" if bad_ohlc else
                      f"شکاف {rep['coverage_pct']}٪ پوشش")
    return ok, rep


def _load_manifest():
    try:
        return json.loads(MANIFEST.read_text())
    except Exception:                                # noqa: BLE001
        return None


def _universe():
    inv = json.loads(INVENTORY.read_text())
    return sorted({k.split("_")[0] for k in inv["klines"]})


def init_manifest(now_ms):
    """لنگر زمانی فقط بار اول ثبت می‌شود تا پیشرفت سنجش‌پذیر بماند."""
    m = _load_manifest()
    if m and isinstance(m.get("symbols"), dict):
        return m
    end = now_ms - now_ms % TF_MS
    return {"tf": "5m", "target_days": TARGET_DAYS,
            "start_ms": end - TARGET_DAYS * 86_400_000, "end_ms": end,
            "release_tag": "history-5m-v1",
            "symbols": {s: {"status": "PENDING"} for s in _universe()}}


def pending(m):
    return [s for s, v in sorted(m["symbols"].items())
            if v.get("status") != "DONE"]


def run(budget_min, out_dir, fetch=fetch_symbol, now_ms=None):
    now_ms = now_ms or int(time.time() * 1000)
    m = init_manifest(now_ms)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t_end = time.time() + budget_min * 60
    uploads = []
    for sym in pending(m):
        if time.time() > t_end:
            break
        src, rows = fetch(sym, m["start_ms"], m["end_ms"])
        row = m["symbols"][sym]
        row["fetched_at"] = int(time.time() * 1000)
        if src is None:
            row.update(status="FAILED", why=str(rows), source=None)
            continue
        ok, rep = verify(rows if isinstance(rows, list) else [],
                         m["start_ms"], m["end_ms"])
        row.update(rep)
        row["source"] = src
        if not ok:
            row["status"] = "FAILED"
            continue
        f = out / f"{sym}_5m.jsonl.gz"
        with gzip.open(f, "wt") as g:
            for r in rows:
                g.write(json.dumps(r) + "\n")
        row["sha256"] = hashlib.sha256(f.read_bytes()).hexdigest()
        row["bytes"] = f.stat().st_size
        row["status"] = "DONE"
        uploads.append(f)
    m["updated"] = int(time.time() * 1000)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1))
    done = sum(1 for v in m["symbols"].values() if v["status"] == "DONE")
    print(f"۵د: {done}/{len(m['symbols'])} نماد کامل · این اجرا "
          f"{len(uploads)} فایل ساخت")
    return uploads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-min", type=float, default=12)
    ap.add_argument("--out-dir", default="/tmp/c5m")
    a = ap.parse_args()
    ups = run(a.budget_min, a.out_dir)
    # فهرست فایل‌ها برای گام آپلود ورک‌فلو
    (Path(a.out_dir) / "_uploads.txt").write_text(
        "\n".join(str(u) for u in ups))


if __name__ == "__main__":
    main()
