"""اثر حجم و «ورود پول» بر نتیجهٔ معامله‌ها — روی دفتر ۳ ساله (حمید، ۲۶ اوت).

دستور: «بررسی حجم و نحوهٔ پیدا کردن ورود پول را بیشتر کنیم؛ حجم را با
جدیدترین متود دقیق اندازه بگیریم و با دیتای ۳ ساله تطبیق بدهیم و ببینیم
حجم در ترید چقدر تأثیر داشته.»

مرز صادقانه (قانون ۰۸): از کندل، حجمِ هر کندل را داریم؛ دلتای واقعی
خرید/فروش (CVD) فقط از استریم معاملات درمی‌آید و کار سرویس محلی است.
این‌جا چهار سنجهٔ قطعیِ استاندارد از OHLCV ساخته می‌شود — همه فقط از
گذشتهٔ همان لحظه:

- **rvol50**: حجم ÷ میانهٔ ۵۰ کندل قبل (حجم نسبی کلاسیک).
- **tod_rvol**: حجم ÷ میانهٔ همان ساعتِ روز در ۲۰ روز قبل — حجم شبانه‌روز
  کریپتو فصل درون‌روزی دارد؛ بدون این تعدیل «جهش» نیمه‌شب با ظهر
  قابل مقایسه نیست (روش رایج امروزی: seasonally-adjusted RVOL).
- **clv**: جای بسته‌شدن در دامنهٔ کندل ((c−l)−(h−c))÷(h−l) ∈ [−۱,+۱] —
  پروکسی «پول واردشونده» در همان کندل (نزدیک سقف = خریدار غالب).
- **obv20**: جهت انباشت OBV در ۲۰ کندل قبل — پروکسی جریان چندساعته.

هر معاملهٔ دفتر ۳ ساله به این سنجه‌ها در «کندل لحظهٔ ورود» وصل و نتیجهٔ
خالص هر سطل با CI۹۵ گزارش می‌شود. این گزارش است، نه قانون — ورودش به
موتور فقط از مسیر قانون ۰۳.

اجرا:  python3 -m hamid.volume_impact --src <klines root> \
         --trades <backtest3y_trades.json.gz> --out <json>
"""
import argparse
import gzip
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import history_ingest                       # noqa: E402
from hamid.dash_backtest import boot_ci                # noqa: E402
from hamid.history_analysis import agg2                # noqa: E402

OUT = ROOT / "brain" / "research" / "history" / "volume_impact.json"
SLOT_MS = 900_000
SLOTS_PER_DAY = 96
RVOL_BINS = [(0.0, 0.8, "خشک <0.8×"), (0.8, 1.5, "عادی 0.8-1.5×"),
             (1.5, 3.0, "بالا 1.5-3×"), (3.0, 1e9, "جهش ≥3×")]


def _median(vals):
    s = sorted(vals)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def features_at(c15, i):
    """سنجه‌های حجم در کندل i — فقط از کندل‌های ≤ i (بی‌آینده)."""
    if i < 60:
        return None
    k = c15[i]
    v = k.get("v") or 0.0
    past50 = [x.get("v") or 0.0 for x in c15[i - 50:i]]
    m50 = _median(past50)
    rvol = (v / m50) if m50 else None
    # فصل درون‌روزی: میانهٔ همان اسلات ۱۵د در ۲۰ روز قبل
    slot = (k["t"] // SLOT_MS) % SLOTS_PER_DAY
    same = [x.get("v") or 0.0 for x in c15[max(0, i - 20 * SLOTS_PER_DAY):i]
            if (x["t"] // SLOT_MS) % SLOTS_PER_DAY == slot]
    mt = _median(same) if len(same) >= 8 else None
    tod = (v / mt) if mt else None
    rng = k["h"] - k["l"]
    clv = (((k["c"] - k["l"]) - (k["h"] - k["c"])) / rng) if rng > 0 else 0.0
    obv = 0.0
    for j in range(i - 19, i + 1):
        d = c15[j]["c"] - c15[j - 1]["c"]
        obv += (c15[j].get("v") or 0.0) * (1 if d > 0 else -1 if d < 0 else 0)
    return {"rvol": rvol, "tod_rvol": tod, "clv": clv,
            "obv20": 1 if obv > 0 else -1 if obv < 0 else 0}


def _bin_name(x, bins):
    if x is None:
        return "بی‌داده"
    for lo, hi, name in bins:
        if lo <= x < hi:
            return name
    return "بی‌داده"


def study(trades_by_sym, load15):
    """trades_by_sym: {sym: [trade,...]} · load15(sym)→کندل‌ها یا None."""
    buckets = {"rvol": {}, "tod_rvol": {}, "clv_dir": {}, "obv_dir": {}}
    matched = missed = 0
    for sym, trs in trades_by_sym.items():
        c15 = load15(sym)
        if not c15:
            missed += len(trs)
            continue
        idx = {k["t"]: i for i, k in enumerate(c15)}
        for t in trs:
            i = idx.get(t["opened"])
            f = features_at(c15, i) if i is not None else None
            if not f:
                missed += 1
                continue
            matched += 1
            buckets["rvol"].setdefault(_bin_name(f["rvol"], RVOL_BINS),
                                       []).append(t)
            buckets["tod_rvol"].setdefault(
                _bin_name(f["tod_rvol"], RVOL_BINS), []).append(t)
            # ورود پول: جای کلوز هم‌جهت معامله بود یا خلافش؟
            aligned = (f["clv"] > 0.2 and t["dir"] == "LONG") or \
                      (f["clv"] < -0.2 and t["dir"] == "SHORT")
            against = (f["clv"] < -0.2 and t["dir"] == "LONG") or \
                      (f["clv"] > 0.2 and t["dir"] == "SHORT")
            key = ("پول هم‌جهت" if aligned
                   else "پول خلاف" if against else "خنثی")
            buckets["clv_dir"].setdefault(key, []).append(t)
            ob_al = (f["obv20"] > 0 and t["dir"] == "LONG") or \
                    (f["obv20"] < 0 and t["dir"] == "SHORT")
            buckets["obv_dir"].setdefault(
                "OBV هم‌جهت" if ob_al else "OBV خلاف/خنثی", []).append(t)
    out = {"matched": matched, "missed": missed}
    for fam, d in buckets.items():
        out[fam] = {name: agg2(trs) for name, trs in sorted(d.items())}
    return out


def run(src, trades_path, out=None):
    out = Path(out) if out else OUT
    inv_path = Path(out).parent / "inventory_volume.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    history_ingest.ingest(src, out_path=inv_path, quiet=True)
    raw = Path(trades_path).read_bytes()
    trades = json.loads(gzip.decompress(raw) if str(trades_path).endswith(".gz")
                        else raw)
    by_sym = {}
    for t in trades:
        by_sym.setdefault(t["sym"], []).append(t)
    res = study(by_sym,
                lambda s: history_ingest.load_klines(s, "15m", inv_path))
    res.update({"generated": int(time.time() * 1000),
                "n_trades": len(trades),
                "note": ("سنجه‌ها فقط از گذشتهٔ لحظهٔ ورود؛ CVD واقعی کار "
                         "سرویس محلی است (قانون ۰۸). گزارش است، نه قانون — "
                         "ورود به موتور فقط با CI بالای صفر (قانون ۰۳).")})
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"وصل‌شده {res['matched']} · بی‌داده {res['missed']} → {out}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--trades", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(a.src, a.trades, out=a.out)
