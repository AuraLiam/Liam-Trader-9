"""درخواست دادهٔ ایجنت‌ها — ایجنت می‌گوید چه می‌خواهد، پایتون جمع می‌کند (قانون ۱۹).

حمید (۱۴ سپتامبر): «ایجنت‌ها بتوانند سریع داده‌های مهم با توجه به نوع
کارشان را خودشان به پایتون بدهند که پایتون یا تولز برایشان لحظه‌ای
اطلاعات جمع‌آوری کند که همه هر لحظه آپدیت بشوند.»

قرارداد: config/agent_data_requests.yaml — هر ایجنت زیر کلید خودش (Exx یا
نام ایجنت عملیاتی) فهرست درخواست‌هایش را دارد. سه نوع: kline / feed /
state. این ماژول هر دورِ زنجیره (~۵ دقیقه) و در سرویس محلی اجرا می‌شود و
signals/data-requests.json می‌نویسد؛ ایجنت با `--for <کلید>` می‌خواند.

مرزها (قانون ۱ و ۰۵): چیزی که نرسید «برآورده نشد» با دلیل می‌ماند —
عددی ساخته نمی‌شود. خوراک بیرونی و فایل وضعیت **دوباره** گرفته نمی‌شود؛
از signals/intake.json خوانده می‌شود (یک نویسنده برای هر دامنه). فقط
کندل‌ها این‌جا کشیده می‌شوند و هر (نماد،تایم) یک بار در هر دور.

اجرا:  python3 -m hamid.data_requests --write
       python3 -m hamid.data_requests --for E14
       python3 -m hamid.data_requests --check          (فقط اعتبارسنجی قرارداد)
       python3 -m hamid.data_requests --add E14 feed feed=news why="…" max_age_min=120
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent
CONTRACT = ROOT / "config" / "agent_data_requests.yaml"
INTAKE = ROOT / "signals" / "intake.json"
REGISTRY = ROOT / "config" / "state_registry.json"
OUT = ROOT / "signals" / "data-requests.json"

KINDS = {"kline", "feed", "state"}
FEEDS = {"fear_greed", "funding", "calendar", "news", "trending", "unlocks"}
TFS = {"5m", "15m", "1h", "4h", "1d"}
TF_MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
MAX_KLINE_N = 400
MAX_REQ_PER_OWNER = 12          # سقف — بودجهٔ توکن/شبکه یک قید طراحی است (قانون ۱۸)


def _yaml():
    import yaml
    return yaml


def load_contract(path=None):
    p = path or CONTRACT
    try:
        doc = _yaml().safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:                           # noqa: BLE001
        return {}, [f"قرارداد خواندنی نیست: {type(e).__name__}: {e}"]
    return (doc.get("requests") or {}), []


def owners_known():
    from hamid import dispatch
    eng = set()
    try:
        reg = _yaml().safe_load((ROOT / "config" / "engine_registry.yaml").read_text(encoding="utf-8"))
        for e in reg.get("engines") or []:
            eng.add(e.get("id"))
    except Exception:                                # noqa: BLE001
        eng = {f"E{i:02d}" for i in range(27)}
    return eng | set(dispatch.AGENT_ENGINES)


def validate(requests, registry_files=None):
    """فهرست خطاها؛ خالی = معتبر. هر خطا می‌گوید کدام مالک/شناسه."""
    errs = []
    known = owners_known()
    reg = registry_files
    if reg is None:
        try:
            reg = json.loads(REGISTRY.read_text(encoding="utf-8"))["files"]
        except Exception:                            # noqa: BLE001
            reg = {}
    for owner, items in (requests or {}).items():
        if owner not in known:
            errs.append(f"{owner}: مالک ناشناخته (Exx یا ایجنت عملیاتی)")
        if not isinstance(items, list):
            errs.append(f"{owner}: فهرست نیست")
            continue
        if len(items) > MAX_REQ_PER_OWNER:
            errs.append(f"{owner}: بیش از {MAX_REQ_PER_OWNER} درخواست")
        seen = set()
        for r in items:
            rid, kind = r.get("id"), r.get("kind")
            tag = f"{owner}/{rid}"
            if not rid or rid in seen:
                errs.append(f"{owner}: شناسهٔ خالی یا تکراری ({rid})")
            seen.add(rid)
            if kind not in KINDS:
                errs.append(f"{tag}: نوع ناشناخته {kind!r}")
                continue
            if not r.get("why"):
                errs.append(f"{tag}: بدون why")
            if not isinstance(r.get("max_age_min"), (int, float)) or r["max_age_min"] <= 0:
                errs.append(f"{tag}: max_age_min نامعتبر")
            if kind == "kline":
                if not str(r.get("symbol", "")).endswith("USDT"):
                    errs.append(f"{tag}: symbol باید …USDT باشد")
                if r.get("tf") not in TFS:
                    errs.append(f"{tag}: tf باید یکی از {sorted(TFS)} باشد")
                if not (20 <= int(r.get("n") or 0) <= MAX_KLINE_N):
                    errs.append(f"{tag}: n باید بین ۲۰ و {MAX_KLINE_N} باشد")
                tfm = TF_MS.get(r.get("tf"), 0) / 60000
                if isinstance(r.get("max_age_min"), (int, float)) and 0 < r["max_age_min"] < tfm:
                    errs.append(f"{tag}: max_age_min ({r['max_age_min']:.0f}) کمتر از یک کندل {r.get('tf')} ({tfm:.0f}د) است — همیشه «کهنه» می‌شود")
            elif kind == "feed" and r.get("feed") not in FEEDS:
                errs.append(f"{tag}: خوراک ناشناخته {r.get('feed')!r}")
            elif kind == "state" and r.get("file") not in reg:
                errs.append(f"{tag}: فایل وضعیت {r.get('file')!r} ردیف قرارداد ندارد (قانون ۱۳)")
    return errs


def _kget_default(sym, tf, n):
    import sources
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in sources.klines(sym, tf, n)]


def _intake_items(intake):
    return {i.get("id"): i for i in (intake or {}).get("items") or []}


def fulfill(requests, kget=_kget_default, intake=None, now_ms=None):
    """هر درخواست → آیتم با ok/age/summary یا why_not. کندل هر (نماد،تایم) یک بار."""
    now_ms = now_ms or int(time.time() * 1000)
    if intake is None:
        try:
            intake = json.loads(INTAKE.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            intake = {}
    items = _intake_items(intake)
    intake_age = (now_ms - (intake.get("generated") or 0)) / 60000 if intake.get("generated") else None
    kcache, out = {}, {}
    for owner, reqs in (requests or {}).items():
        rows = []
        for r in reqs or []:
            row = {"id": r.get("id"), "kind": r.get("kind"), "why": r.get("why"),
                   "ok": False, "age_min": None, "summary": None, "why_not": None}
            cap = float(r.get("max_age_min") or 0)
            try:
                if r["kind"] == "kline":
                    key = (r["symbol"], r["tf"])
                    if key not in kcache:
                        kcache[key] = kget(r["symbol"], r["tf"], int(r.get("n") or 220))
                    cd = kcache[key]
                    if len(cd) < 20:
                        raise ValueError("کندل کافی نیست")
                    from hamid.structure import trend
                    # سن = دقیقه از «بسته‌شدنِ» آخرین کندل، نه از بازشدنش —
                    # اثبات ۱۵ سپتامبر روی Actions: کندل ۴س سالم «۳۴۶د کهنه»
                    # خوانده شد چون از open سنجیده می‌شد. کندلِ هنوز باز = ۰.
                    age = max(0.0, (now_ms - (cd[-1]["t"] + TF_MS[r["tf"]])) / 60000)
                    row["age_min"] = round(age, 1)
                    row["summary"] = {"close": cd[-1]["c"],
                                      "chg_pct_20": round((cd[-1]["c"] / cd[-21]["c"] - 1) * 100, 2)
                                      if len(cd) > 21 else None,
                                      "trend": trend(cd), "bars": len(cd), "source": "sources.klines"}
                    row["ok"] = age <= cap
                    if not row["ok"]:
                        row["why_not"] = f"کندل کهنه ({age:.0f}د > {cap:.0f})"
                elif r["kind"] == "feed":
                    it = items.get(f"ext:{r['feed']}")
                    if not it:
                        row["why_not"] = "خوراک در intake نیست"
                    else:
                        age = intake_age if it.get("age_min") is None else it.get("age_min")
                        row["age_min"] = None if age is None else round(age, 1)
                        # intake خوراکِ بیرونی را زیر `payload` می‌گذارد، نه `digest` —
                        # ۲۶ سپتامبر: خلاصهٔ خبر/تقویم خالی می‌رسید و قوس (E14) کور بود.
                        row["summary"] = (it.get("payload") if it.get("payload") is not None
                                          else it.get("digest")) or {
                            k: it.get(k) for k in ("ok", "note", "error", "err") if k in it}
                        row["ok"] = bool(it.get("ok")) and age is not None and age <= cap
                        if not row["ok"]:
                            row["why_not"] = ("خوراک ناموفق" if not it.get("ok")
                                              else f"کهنه ({age:.0f}د > {cap:.0f})")
                else:                                # state
                    it = items.get(f"state:{r['file']}")
                    if not it:
                        row["why_not"] = "فایل وضعیت در intake نیست"
                    else:
                        age = it.get("age_min")
                        row["age_min"] = age
                        row["summary"] = it.get("digest")
                        row["ok"] = bool(it.get("ok")) and age is not None and age <= cap
                        if not row["ok"]:
                            row["why_not"] = ("فایل غایب/خراب" if not it.get("ok")
                                              else f"کهنه ({age:.0f}د > {cap:.0f})")
            except Exception as e:                   # noqa: BLE001
                row["why_not"] = f"{type(e).__name__}: {str(e)[:120]}"
            rows.append(row)
        out[owner] = {"items": rows, "n_ok": sum(1 for x in rows if x["ok"]),
                      "n": len(rows)}
    return {"generated": now_ms, "owners": out,
            "boundary": "برآورده‌نشده با دلیل می‌ماند؛ عددی ساخته نمی‌شود (قانون ۱). "
                        "خوراک/وضعیت از intake، فقط کندل مستقیم."}


def add_request(owner, kind, fields, path=None):
    yaml = _yaml()
    p = path or CONTRACT
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    reqs = doc.setdefault("requests", {})
    row = {"id": fields.get("id") or fields.get("feed") or fields.get("file")
           or f"{fields.get('symbol','')}_{fields.get('tf','')}".lower(), "kind": kind}
    row.update(fields)
    if "max_age_min" in row:
        row["max_age_min"] = float(row["max_age_min"])
    if "n" in row:
        row["n"] = int(row["n"])
    reqs.setdefault(owner, []).append(row)
    errs = validate(reqs)
    if errs:
        return errs
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--for", dest="owner")
    ap.add_argument("--add", nargs="+", metavar="OWNER KIND k=v")
    a = ap.parse_args()
    if a.add:
        owner, kind, *kv = a.add
        fields = dict(x.split("=", 1) for x in kv)
        errs = add_request(owner, kind, fields)
        print("ثبت شد" if not errs else "رد شد: " + "; ".join(errs))
        return 1 if errs else 0
    requests, errs = load_contract()
    errs += validate(requests)
    if a.check or errs:
        print("قرارداد معتبر است" if not errs else "خطاهای قرارداد:\n  " + "\n  ".join(errs))
        if errs:
            return 1
        if a.check:
            return 0
    if a.owner:
        try:
            doc = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            doc = fulfill({a.owner: requests.get(a.owner, [])})
        print(json.dumps(doc["owners"].get(a.owner) or {"items": [], "note": "درخواستی ثبت نشده"},
                         ensure_ascii=False, indent=1))
        return 0
    doc = fulfill(requests)
    if a.write:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = sum(v["n"] for v in doc["owners"].values())
    ok = sum(v["n_ok"] for v in doc["owners"].values())
    print(f"درخواست داده: {ok}/{tot} برآورده · {len(doc['owners'])} مالک")
    return 0


if __name__ == "__main__":
    sys.exit(main())
