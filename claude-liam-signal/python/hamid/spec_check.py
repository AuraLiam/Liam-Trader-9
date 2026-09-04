#!/usr/bin/env python3
"""بررسی‌کنندهٔ سازمان ققنوس — ادعای «انجام شد» را با خودِ مخزن می‌سنجد.

دستور حمید (۳ سپتامبر): «اول همهٔ این‌ها را به بهترین پرامپت کدنویسی تبدیل
کن و بده پایتون هم چک کند.»

پرامپت = `config/phoenix_org_spec.json` (بند-به-بندِ همان پیام، ماشین‌خوان).
این فایل همان پایتونی است که چکش می‌کند. قاعده‌اش سخت است چون کارِ نرمِ
یک سند این است که با گذشت زمان از کد جدا بیفتد و کسی نفهمد:

| وضعیت | چه چیزی اثبات می‌خواهد |
|---|---|
| DONE | ماژول روی دیسک هست · محافظ روی دیسک هست · محافظ در دروازهٔ یک ورک‌فلو می‌دود |
| PARTIAL | ماژول هست + `note` می‌گوید دقیقاً چه چیزی کم است |
| PLANNED | `note` می‌گوید چرا هنوز ساخته نشده |

هر تخلف = خروجی غیرصفر = چرخه سرخ. یعنی نمی‌شود بندی را DONE اعلام کرد و
محافظش را ننوشت؛ همان کلاسِ عیبی که این مخزن بارها از آن ضربه خورده.

    python3 -m hamid.spec_check            # گزارش خوانا
    python3 -m hamid.spec_check --json     # خروجی ماشین‌خوان
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
SPEC = ROOT / "config" / "phoenix_org_spec.json"
WORKFLOWS = ROOT / ".github" / "workflows"

OK_STATUS = ("DONE", "PARTIAL", "PLANNED")


def load(path=None):
    return json.loads(Path(path or SPEC).read_text(encoding="utf-8"))


def _gate_modules(wf_dir=None):
    """هر ماژول آزمونی که در دروازهٔ یک ورک‌فلو صدا زده می‌شود."""
    out = set()
    d = Path(wf_dir or WORKFLOWS)
    if not d.exists():
        return out
    for f in d.glob("*.yml"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if "python3 -m hamid.test_" in line:
                for part in line.split():
                    if part.startswith("hamid.test_"):
                        out.add(part.split(".", 1)[1])
    return out


def check(spec=None, root=None, wf_dir=None):
    spec = spec if spec is not None else load()
    root = Path(root or ROOT)
    gated = _gate_modules(wf_dir)
    rows, faults = [], []
    seen = set()
    for c in spec.get("clauses") or []:
        cid = c.get("id")
        st = c.get("status")
        r = {"id": cid, "room": c.get("room"), "status": st, "problems": []}
        if cid in seen:
            r["problems"].append("شناسهٔ تکراری")
        seen.add(cid)
        if st not in OK_STATUS:
            r["problems"].append(f"وضعیت ناشناخته: {st}")
        if not (c.get("text") or "").strip():
            r["problems"].append("متن بند خالی است")
        mod = c.get("module")
        mod_ok = bool(mod) and (root / mod).exists()
        guard = c.get("guard")
        guard_ok = bool(guard) and (root / guard).exists()
        guard_name = Path(guard).stem if guard else None
        if st == "DONE":
            if not mod_ok:
                r["problems"].append(f"ماژول نیست: {mod}")
            if not guard_ok:
                r["problems"].append(f"محافظ نیست: {guard}")
            elif guard_name not in gated:
                r["problems"].append(f"محافظ در دروازهٔ هیچ ورک‌فلویی نمی‌دود: {guard_name}")
        elif st == "PARTIAL":
            if not mod_ok:
                r["problems"].append(f"PARTIAL ولی ماژول نیست: {mod}")
            if not (c.get("note") or "").strip():
                r["problems"].append("PARTIAL بدون note — کمبود باید نوشته شود")
        elif st == "PLANNED":
            if not (c.get("note") or "").strip():
                r["problems"].append("PLANNED بدون note — دلیل باید نوشته شود")
        r["module_ok"], r["guard_ok"] = mod_ok, guard_ok
        r["gated"] = guard_name in gated if guard_name else False
        rows.append(r)
        faults.extend(f"{cid}: {p}" for p in r["problems"])
    n = len(rows)
    by = {s: sum(1 for r in rows if r["status"] == s) for s in OK_STATUS}
    return {"clauses": n, "by_status": by, "rows": rows, "faults": faults,
            "verdict": "GREEN" if not faults else "RED"}


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    # خروجی لوله‌شده به head نباید با BrokenPipe بترکد — گزارش ابزار است، نه دروازه
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception:                                # noqa: BLE001 - ویندوز SIGPIPE ندارد
        pass
    res = check()
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["verdict"] == "GREEN" else 1
    b = res["by_status"]
    print(f"سازمان ققنوس — {res['clauses']} بند: "
          f"{b['DONE']} انجام‌شده · {b['PARTIAL']} ناقص · {b['PLANNED']} در برنامه")
    room = None
    for r in res["rows"]:
        if r["room"] != room:
            room = r["room"]
            print(f"\n  ── {room}")
        mark = {"DONE": "✓", "PARTIAL": "◐", "PLANNED": "▢"}[r["status"]] if r["status"] in OK_STATUS else "?"
        print(f"    {mark} {r['id']}" + ("" if not r["problems"] else "  ✗ " + " · ".join(r["problems"])))
    if res["faults"]:
        print(f"\n{len(res['faults'])} تخلف — ادعای بی‌اثبات:")
        for f in res["faults"]:
            print(f"  ✗ {f}")
        return 1
    print("\nهر بند یا اثباتش را دارد یا کمبودش نوشته شده.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
