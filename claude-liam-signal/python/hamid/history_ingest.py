"""تحویل دادهٔ تاریخی لپ‌تاپ به اتاق تاریخچه (E13) — دستور حمید، ۲۵ اوت.

حمید ۵۶۷ مگابایت دادهٔ چندسالهٔ ارزها را در C:\\AuraLiamData\\research دارد:
  klines/BTCUSDT_15m.bin ... (~۲۹۸ فایل کندل باینری)
  meta/notebook.json.gz · dominance.json.gz · universe.json
  meta/venue/BTCUSDT.json.gz ... (~۲۷۸ فایل)

این اسکریپت روی **لپ‌تاپ خود حمید** اجرا می‌شود (کلود ابری به C:\\ دسترسی
ندارد) و سه کار می‌کند:

۱. **بررسی**: هر فایل کندل را با چند قالب باینری استاندارد می‌سنجد
   (زمانِ صعودی، بازهٔ تاریخ معقول، قیمت مثبت). قالبی که از سنجش رد
   نشود «UNKNOWN_FORMAT» می‌ماند — حدس ممنوع (قانون ۱).
۲. **بایگانی**: فهرست کامل با اندازه، بازهٔ زمانی، تعداد ردیف و قالبِ
   تشخیص‌داده‌شده در brain/research/history/inventory.json نوشته می‌شود
   (خودِ داده در گیت نمی‌رود — بزرگ است و runtime؛ فقط شناسنامه‌اش).
۳. **در دسترس بودن**: load_klines(symbol, tf) با همان شناسنامه فایل را
   می‌خواند و کندل‌ها را برمی‌گرداند — اتاق تاریخچه از همین در استفاده
   می‌کند.

اجرا روی لپ‌تاپ (ویندوز، از پوشهٔ ریپو):
  cd claude-liam-signal\\python
  python -m hamid.history_ingest --src "C:\\AuraLiamData\\research"

مرز صادقانه: این فقط شناسنامه و درِ دسترسی است. هر «یافته» از این داده
(الگو، قاعده، لبه) بعداً از مسیر قانون ۰۳ می‌رود: بک‌تست → CI بالای
صفر → تأیید حمید. خودِ بایگانی هیچ تصمیمی را عوض نمی‌کند.
"""
import argparse
import gzip
import json
import struct
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
INVENTORY = ROOT / "brain" / "research" / "history" / "inventory.json"

# بازهٔ زمانی معقول برای دادهٔ کریپتو (میلی‌ثانیه و ثانیهٔ یونیکس)
T_MIN_S, T_MAX_S = 1_262_304_000, 1_925_000_000          # 2010..2031
TF_MIN = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
          "1h": 60, "2h": 120, "4h": 240, "1d": 1440}

# قالب‌های نامزد برای هر ردیف کندل: (نام، struct، اندیس زمان)
# t,o,h,l,c,v — رایج‌ترین چیدمان؛ f8=float64، f4=float32، q=int64
CANDIDATES = [
    ("t8_ohlcv8", "<6d", 0),      # ۶×float64 = ۴۸ بایت
    ("q_ohlcv8", "<q5d", 0),      # int64 زمان + ۵×float64 = ۴۸ بایت
    ("t8_ohlcv4", "<d5f", 0),     # float64 زمان + ۵×float32 = ۲۸ بایت
    ("q_ohlcv4", "<q5f", 0),      # int64 زمان + ۵×float32 = ۲۸ بایت
]


def _t_seconds(v):
    """زمان را (اگر معقول باشد) به ثانیه برمی‌گرداند؛ وگرنه None."""
    try:
        v = float(v)
    except Exception:                                # noqa: BLE001
        return None
    if T_MIN_S <= v <= T_MAX_S:
        return v
    if T_MIN_S * 1000 <= v <= T_MAX_S * 1000:
        return v / 1000.0
    return None


def probe_bin(path, tf=None, sample_rows=64):
    """قالب فایل کندل باینری را با سنجش پیدا می‌کند — نه با حدس.

    شرط قبولی: اندازهٔ فایل مضرب اندازهٔ ردیف، زمان‌های نمونه معقول و
    اکیداً صعودی با گام سازگار با تایم‌فریم، و قیمت‌ها مثبت با high>=low.
    → dict شناسنامه یا None."""
    size = path.stat().st_size
    raw = path.read_bytes() if size <= 4096 * 64 else None
    with open(path, "rb") as fh:
        head = raw if raw is not None else fh.read(4096 * 64)
    for name, fmt, ti in CANDIDATES:
        rec = struct.calcsize(fmt)
        if size < rec * 3 or size % rec:
            continue
        n = min(sample_rows, size // rec)
        try:
            rows = [struct.unpack_from(fmt, head, i * rec) for i in range(n)]
        except struct.error:
            continue
        ts = [_t_seconds(r[ti]) for r in rows]
        if any(t is None for t in ts):
            continue
        steps = [b - a for a, b in zip(ts, ts[1:])]
        if not steps or any(s <= 0 for s in steps):
            continue
        step_min = min(steps) / 60.0
        if tf and tf in TF_MIN and abs(step_min - TF_MIN[tf]) > 0.01:
            continue
        ok_px = all(
            row[ti + 1] > 0 and row[ti + 2] > 0 and row[ti + 3] > 0
            and row[ti + 4] > 0 and row[ti + 2] >= row[ti + 3]
            for row in rows)
        if not ok_px:
            continue
        return {"format": name, "record_bytes": rec,
                "rows": size // rec, "t_index": ti,
                "t0_s": ts[0], "step_min": round(step_min, 3)}
    return None


def _read_last_t(path, spec):
    fmt = dict((c[0], c[1]) for c in CANDIDATES)[spec["format"]]
    rec = spec["record_bytes"]
    with open(path, "rb") as fh:
        fh.seek((spec["rows"] - 1) * rec)
        row = struct.unpack(fmt, fh.read(rec))
    return _t_seconds(row[spec["t_index"]])


def _name_parts(path):
    """BTCUSDT_15m.bin → (BTCUSDT, 15m)؛ ناجور → (نام، None)."""
    stem = path.stem
    if "_" in stem:
        sym, tf = stem.rsplit("_", 1)
        return sym, (tf if tf in TF_MIN else None)
    return stem, None


def _read_meta(path):
    try:
        raw = (gzip.decompress(path.read_bytes())
               if path.suffix == ".gz" else path.read_bytes())
        j = json.loads(raw)
        top = (sorted(j.keys())[:12] if isinstance(j, dict)
               else [f"list[{len(j)}]"])
        return {"ok": True, "bytes": path.stat().st_size, "keys": top}
    except Exception as e:                           # noqa: BLE001
        return {"ok": False, "bytes": path.stat().st_size,
                "error": type(e).__name__}


def ingest(src, out_path=None, quiet=False):
    """بررسی + بایگانی. برمی‌گرداند شناسنامهٔ کامل (و روی دیسک می‌نویسد)."""
    src = Path(src)
    out_path = Path(out_path) if out_path else INVENTORY
    inv = {"retrieved_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
           "source_dir": str(src), "klines": {}, "meta": {}, "errors": [],
           "validation_status": "UNVERIFIED",
           "note": ("شناسنامهٔ دادهٔ تاریخی لپ‌تاپ برای اتاق تاریخچه (E13). "
                    "خودِ داده در گیت نیست؛ خواندنش با history_ingest."
                    "load_klines. هر یافته فقط از مسیر قانون ۰۳ (بک‌تست→CI) "
                    "وارد تصمیم می‌شود.")}
    if not src.is_dir():
        inv["errors"].append(f"پوشهٔ منبع پیدا نشد: {src}")
    kdir = src / "klines"
    for p in sorted(kdir.glob("*.bin")) if kdir.is_dir() else []:
        sym, tf = _name_parts(p)
        try:
            spec = probe_bin(p, tf)
        except Exception as e:                       # noqa: BLE001
            spec, _err = None, inv["errors"].append(f"{p.name}: {type(e).__name__}")
        ent = {"bytes": p.stat().st_size, "tf": tf, "path": str(p)}
        if spec:
            t1 = _read_last_t(p, spec)
            ent.update(spec)
            ent["t0"] = time.strftime("%Y-%m-%d", time.gmtime(spec["t0_s"]))
            ent["t1"] = (time.strftime("%Y-%m-%d", time.gmtime(t1))
                         if t1 else "?")
            ent["status"] = "OK"
        else:
            ent["status"] = "UNKNOWN_FORMAT"         # حدس نمی‌زنیم
        inv["klines"][f"{sym}_{tf or '?'}"] = ent
    mdir = src / "meta"
    if mdir.is_dir():
        for p in sorted(mdir.iterdir()):
            if p.is_file():
                inv["meta"][p.name] = _read_meta(p)
        vdir = mdir / "venue"
        if vdir.is_dir():
            vs = sorted(vdir.glob("*.json*"))
            ok = sum(1 for p in vs if _read_meta(p)["ok"])
            inv["meta"]["venue/"] = {"files": len(vs), "readable": ok}
    ok_k = sum(1 for e in inv["klines"].values() if e["status"] == "OK")
    bad_k = len(inv["klines"]) - ok_k
    inv["summary"] = {"klines_ok": ok_k, "klines_unknown": bad_k,
                      "meta_files": len(inv["meta"]),
                      "total_bytes": sum(e["bytes"]
                                         for e in inv["klines"].values())}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inv, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    if not quiet:
        print(f"بایگانی شد: {ok_k} فایل کندل سالم، {bad_k} قالب‌ناشناخته، "
              f"{len(inv['meta'])} فایل متا → {out_path}")
        if bad_k:
            print("قالب‌ناشناخته‌ها حدس زده نشدند — نمونه‌شان را بفرست تا "
                  "قالب دقیقشان اضافه شود.")
    return inv


def load_klines(symbol, tf, inventory_path=None, limit=None):
    """درِ دسترسی اتاق تاریخچه: کندل‌های (t_ms,o,h,l,c,v) از روی شناسنامه.

    فقط فایلی که در بررسی OK شده خوانده می‌شود؛ UNKNOWN هرگز."""
    inv = json.loads(Path(inventory_path or INVENTORY).read_text(
        encoding="utf-8"))
    ent = inv["klines"].get(f"{symbol}_{tf}")
    if not ent or ent.get("status") != "OK":
        return None
    fmt = dict((c[0], c[1]) for c in CANDIDATES)[ent["format"]]
    rec, ti = ent["record_bytes"], ent["t_index"]
    out = []
    with open(ent["path"], "rb") as fh:
        data = fh.read((limit or ent["rows"]) * rec)
    for i in range(len(data) // rec):
        row = struct.unpack_from(fmt, data, i * rec)
        t = _t_seconds(row[ti])
        out.append({"t": int((t or 0) * 1000), "o": row[ti + 1],
                    "h": row[ti + 2], "l": row[ti + 3],
                    "c": row[ti + 4], "v": row[ti + 5]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=r"C:\AuraLiamData\research",
                    help="پوشهٔ داده روی لپ‌تاپ")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ingest(a.src, a.out)


if __name__ == "__main__":
    main()
