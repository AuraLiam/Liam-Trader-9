#!/usr/bin/env python3
"""گذرگاه وضعیت — یک سامانهٔ یکپارچه به‌جای ۵۴ جزیرهٔ جدا (دستور حمید، ۲۸ اوت).

حمید: «چرا باید این بی‌نظمی وجود داشته باشد؟ همه منظم و به هم مرتبط و
وصل باشند که هیچ چیز جدا فعالیت نکند و همه چیز به هم ربط داشته باشد اما
در کار هم دخالت نکند.»

ریشهٔ بی‌نظمی، اندازه‌گیری‌شده: هر ورک‌فلو فایل خودش را می‌نوشت و هیچ‌جا
اعلام نمی‌شد آن فایل **چقدر حق دارد کهنه باشد**. نتیجه: ۵۴ فایل با سنین
۳۱ دقیقه تا ۱۸ روز، همه با اعتبارِ ظاهراً برابر روی پنل. پنل نمی‌توانست
بین «تازه» و «باستانی» فرق بگذارد، چون هیچ‌کس قرارداد نداشت.

این ماژول همان قرارداد را اجرا می‌کند:

  * `config/state_registry.json` تنها منبع حقیقت است: هر فایل، لایه‌اش،
    مالکش، تولیدکننده‌اش، سقف کهنگی‌اش، مصرف‌کننده‌اش.
  * فایل ثبت‌نشده در signals/ = **یتیم** (کسی مالکش نیست) → عیب.
  * فایلِ ثبت‌شده که نیست = **گم‌شده** → عیب.
  * فایلِ کهنه‌تر از سقفِ خودش = **کهنه** → عیب (و اگر critical باشد،
    وضعِ کلِ سامانه degraded می‌شود).

خروجی `signals/system-state.json` است: نقشهٔ لایه‌به‌لایه برای پنل، به‌
اضافهٔ بستهٔ شواهد (قانون ۱۲) برای ایجنت اصلی — تا هر ادعایی دربارهٔ
سلامت سامانه عدد و دلیل داشته باشد، نه حدس.

جدایی بدون بی‌نظمی: این ماژول **هیچ فایلی جز خروجی خودش را نمی‌نویسد**.
فقط می‌خواند و داوری می‌کند — پس هیچ اتاقی در کار اتاق دیگر دخالت
نمی‌کند (قانون ۰۵: یک نویسنده برای هر دامنهٔ وضعیت).

    python3 -m hamid.state_bus            # گزارش متنی
    python3 -m hamid.state_bus --write    # + نوشتن signals/system-state.json
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

REGISTRY = ROOT / "config" / "state_registry.json"
SIGDIR = ROOT / "signals"
OUT = SIGDIR / "system-state.json"

LAYER_FA = {
    "L1_market": "بازار و جهان نمادها",
    "L2_context": "بستر: دامیننس، کلان، خبر",
    "L3_structure": "ساختار و SMC",
    "L4_decision": "تصمیم و کمیته",
    "L5_delivery": "تحویل و دفترها",
    "L6_learning": "یادگیری و کارنامه",
    "L7_health": "سلامت سامانه",
}


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _age_min(path):
    """سن از روی مهر `generated` داخل فایل؛ اگر نبود از mtime دیسک.

    mtime روی رانرِ اکشنز پس از checkout بازنویسی می‌شود، پس مهرِ داخلِ
    فایل معتبرتر است و اول امتحان می‌شود."""
    try:
        j = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        j = None
    now = time.time() * 1000
    if isinstance(j, dict):
        for k in ("generated", "at", "last_sent", "accepted_at"):
            v = j.get(k)
            if isinstance(v, (int, float)) and v > 1e12:
                return round((now - v) / 60000, 1), "generated"
    try:
        return round((now - path.stat().st_mtime * 1000) / 60000, 1), "mtime"
    except Exception:                                # noqa: BLE001
        return None, "unknown"


def scan():
    reg = registry()
    spec = reg["files"]
    on_disk = {p.name for p in SIGDIR.glob("*.json")} if SIGDIR.exists() else set()
    rows, faults = [], []

    for name, s in spec.items():
        p = SIGDIR / name
        row = {"file": name, "layer": s["layer"], "layer_fa": LAYER_FA.get(s["layer"], s["layer"]),
               "owner": s["owner"], "producer": s["producer"],
               "consumer": s["consumer"], "critical": bool(s.get("critical")),
               "max_age_min": s.get("max_age_min")}
        if name not in on_disk:
            # optional = فقط در صورت نیاز ساخته می‌شود (فرمان بیرونی، آلارم
            # تریدینگ‌ویو، شکل ناشناس آنلاک). نبودنش عیب نیست، سکوت است.
            row["status"] = "absent_ok" if s.get("optional") else "missing"
            row["age_min"] = None
            if not s.get("optional"):
                faults.append({"kind": "missing", "file": name, "owner": s["owner"],
                               "critical": row["critical"]})
        else:
            age, src = _age_min(p)
            row["age_min"], row["age_src"] = age, src
            cap = s.get("max_age_min")
            if cap is None:
                row["status"] = "ok"          # آرشیو/تشخیصی — کهنگی معنا ندارد
            elif age is None:
                row["status"] = "unknown"
                faults.append({"kind": "no_timestamp", "file": name,
                               "owner": s["owner"], "critical": row["critical"]})
            elif age > cap:
                row["status"] = "stale"
                faults.append({"kind": "stale", "file": name, "owner": s["owner"],
                               "age_min": age, "max_age_min": cap,
                               "critical": row["critical"]})
            else:
                row["status"] = "ok"
        rows.append(row)

    for name in sorted(on_disk - set(spec)):
        rows.append({"file": name, "layer": "?", "layer_fa": "ثبت‌نشده",
                     "owner": None, "producer": None, "consumer": None,
                     "critical": False, "status": "orphan", "age_min": None})
        faults.append({"kind": "orphan", "file": name, "critical": False})

    crit_bad = [f for f in faults if f.get("critical")]
    verdict = "SICK" if crit_bad else ("DEGRADED" if faults else "HEALTHY")
    by_layer = {}
    for r in rows:
        b = by_layer.setdefault(r["layer"], {"ok": 0, "bad": 0, "fa": r["layer_fa"]})
        b["ok" if r["status"] in ("ok", "absent_ok") else "bad"] += 1
    return {"generated": int(time.time() * 1000), "verdict": verdict,
            "n_files": len(rows), "n_faults": len(faults),
            "layers": by_layer, "rows": rows, "faults": faults}


def packet(st):
    """بستهٔ شواهد (قانون ۱۲) — ایجنت اصلی از همین می‌خواند، نه از حدس."""
    from hamid import evidence_packet as EP
    bad = st["faults"]
    worst = sorted([f for f in bad if f.get("kind") == "stale"],
                   key=lambda f: -(f.get("age_min") or 0))[:3]
    claim = {"HEALTHY": "همهٔ لایه‌ها داخل قرارداد کهنگی خودشان‌اند",
             "DEGRADED": "سامانه کار می‌کند ولی چند لایه از قرارداد بیرون‌اند",
             "SICK": "یک لایهٔ حیاتی از قرارداد بیرون است"}[st["verdict"]]
    nums = {"فایل": st["n_files"], "عیب": st["n_faults"],
            "حکم": st["verdict"]}
    for f in worst:
        nums[f["file"]] = f"{f['age_min']:.0f}د (سقف {f['max_age_min']})"
    return EP.build(
        claim=claim,
        numbers=nums,
        track_record=(f"{sum(1 for r in st['rows'] if r['status'] in ('ok', 'absent_ok'))} از "
                      f"{st['n_files']} فایل داخل قرارداد"),
        scenario_up=("عیب‌ها رفع شوند → همهٔ لایه‌ها HEALTHY و تصمیم‌ها روی "
                     "دادهٔ داخل‌قرارداد گرفته می‌شوند"),
        scenario_down=("عیب پابرجا بماند → لایهٔ کهنه در تصمیم شرکت می‌کند و "
                       "همان چیزی می‌شود که قانون ۱ منع کرده (دادهٔ کهنه = NO_SIGNAL)"),
        invalidator="اجرای تازهٔ تولیدکنندهٔ همان فایل، این حکم را باطل می‌کند",
        sources=["config/state_registry.json", "signals/*.json"],
        limit=("این گذرگاه فقط می‌خواند و داوری می‌کند؛ خودش هیچ لایه‌ای را "
               "تعمیر یا بازنویسی نمی‌کند (قانون ۰۵: یک نویسنده برای هر دامنه)"))


def main(argv):
    st = scan()
    pk = packet(st)
    print(f"حکم سامانه: {st['verdict']} — {st['n_files']} فایل، {st['n_faults']} عیب")
    for lay, b in sorted(st["layers"].items()):
        print(f"  {lay} {b['fa']}: {b['ok']} سالم / {b['bad']} عیب")
    for f in st["faults"][:12]:
        extra = (f" {f.get('age_min'):.0f}د > {f.get('max_age_min')}د"
                 if f.get("kind") == "stale" else "")
        print(f"  ✗ {f['kind']}: {f['file']}{extra}"
              + ("  [حیاتی]" if f.get("critical") else ""))
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({**st, "packet": pk}, ensure_ascii=False),
                       encoding="utf-8")
        print(f"نوشته شد: {OUT.relative_to(ROOT)}")
    if "--packet" in argv:
        from hamid import evidence_packet as EP
        print("\n" + EP.render(pk))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
