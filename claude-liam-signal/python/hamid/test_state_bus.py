"""پاسبان گذرگاه وضعیت — همراه اجباری state_bus.py (دستور حمید، ۲۸ اوت).

«هیچ چیز جدا فعالیت نکند.» این آزمون همان را اجرا می‌کند: هر فایل وضعیتِ
runtime باید در قرارداد ثبت باشد و سقف کهنگی اعلام‌شده داشته باشد. فایل
تازه‌ای که کسی ثبتش نکند — همان کلاسی که «دفتر تلگرام» را نامرئی کرد —
چرخه را سرخ می‌کند، نه این‌که ماه‌ها بی‌صدا بماند.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import state_bus as SB                     # noqa: E402

OK = 0
FAIL = []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}")
        if extra:
            print(f"      ↳ {extra}")


# ── قرارداد سالم است ──────────────────────────────────────────────────────
reg = SB.registry()
spec = reg["files"]
check("قرارداد وضعیت وجود دارد و پر است", len(spec) > 30, str(len(spec)))
check("هر ردیف مالک، تولیدکننده و مصرف‌کننده دارد",
      all(s.get("owner") and s.get("producer") and s.get("consumer")
          for s in spec.values()),
      str([k for k, s in spec.items() if not (s.get("owner") and s.get("producer"))][:3]))
check("هر ردیف لایهٔ شناخته‌شده دارد",
      all(s["layer"] in reg["_layers"] for s in spec.values()),
      str({s["layer"] for s in spec.values()} - set(reg["_layers"])))
check("هر ردیف نوعش اعلام شده (live/ledger/snapshot)",
      all(s.get("kind") in ("live", "ledger", "snapshot") for s in spec.values()),
      str([k for k, s in spec.items() if not s.get("kind")][:4]))
live = [k for k, s in spec.items()
        if s.get("kind") == "live" and s.get("max_age_min") is None]
check("هر فیدِ زنده سقف کهنگی اعلام‌شده دارد", not live, str(live))

# ── وضعیت واقعی ریپو: هیچ فایل یتیمی نباشد (کلاسِ عیب) ────────────────────
st = SB.scan()
orphans = [f["file"] for f in st["faults"] if f["kind"] == "orphan"]
check("هیچ فایل وضعیتی بی‌مالک نیست", not orphans,
      "ثبت‌نشده در config/state_registry.json: " + str(orphans))
missing = [f["file"] for f in st["faults"] if f["kind"] == "missing"]
check("فایل ثبت‌شدهٔ غیراختیاری گم نشده", not missing, str(missing))
check("حکم از سه حالت شناخته‌شده است",
      st["verdict"] in ("HEALTHY", "DEGRADED", "SICK"), st["verdict"])

# ── منطق داوری روی نمونهٔ ساختگی (بدون دست‌زدن به ریپو) ───────────────────
TMP = Path(tempfile.mkdtemp(prefix="statebus-"))
old_sig, old_reg = SB.SIGDIR, SB.REGISTRY
SB.SIGDIR = TMP
SB.REGISTRY = TMP.parent / (TMP.name + "-reg.json")
try:
    now = int(time.time() * 1000)
    SB.REGISTRY.write_text(json.dumps({
        "_layers": {"L4_decision": "تصمیم"},
        "files": {
            "fresh.json": {"layer": "L4_decision", "owner": "E17",
                           "producer": "x.py", "max_age_min": 30,
                           "consumer": "panel", "critical": True},
            "old.json": {"layer": "L4_decision", "owner": "E17",
                         "producer": "y.py", "max_age_min": 30,
                         "consumer": "panel", "critical": False},
            "gone.json": {"layer": "L4_decision", "owner": "E17",
                          "producer": "z.py", "max_age_min": 30,
                          "consumer": "panel", "critical": False},
            "onlywhen.json": {"layer": "L4_decision", "owner": "E17",
                              "producer": "w.py", "max_age_min": None,
                              "consumer": "panel", "critical": False,
                              "optional": True}}}, ensure_ascii=False))
    (TMP / "fresh.json").write_text(json.dumps({"generated": now}))
    (TMP / "old.json").write_text(json.dumps({"generated": now - 200 * 60000}))
    (TMP / "surprise.json").write_text(json.dumps({"generated": now}))

    s2 = SB.scan()
    kinds = {(f["kind"], f["file"]) for f in s2["faults"]}
    check("فایل تازه سالم شمرده می‌شود",
          next(r for r in s2["rows"] if r["file"] == "fresh.json")["status"] == "ok")
    check("کهنه‌تر از سقفِ خودش «stale» می‌شود", ("stale", "old.json") in kinds)
    check("ثبت‌شدهٔ نبوده «missing» می‌شود", ("missing", "gone.json") in kinds)
    check("اختیاریِ نبوده عیب نیست",
          not any(f["file"] == "onlywhen.json" for f in s2["faults"]))
    check("فایل ثبت‌نشده «orphan» می‌شود", ("orphan", "surprise.json") in kinds)
    check("عیبِ غیرحیاتی → DEGRADED نه SICK", s2["verdict"] == "DEGRADED",
          s2["verdict"])

    # حیاتیِ کهنه باید SICK کند — اثبات مثبت
    (TMP / "fresh.json").write_text(json.dumps({"generated": now - 200 * 60000}))
    check("کهنگیِ فایل حیاتی → SICK", SB.scan()["verdict"] == "SICK")

    # همه سالم → HEALTHY
    (TMP / "fresh.json").write_text(json.dumps({"generated": now}))
    (TMP / "old.json").write_text(json.dumps({"generated": now}))
    (TMP / "gone.json").write_text(json.dumps({"generated": now}))
    (TMP / "surprise.json").unlink()
    check("همه داخل قرارداد → HEALTHY", SB.scan()["verdict"] == "HEALTHY")

    # بستهٔ شواهد کامل است (قانون ۱۲)
    from hamid import evidence_packet as EP
    pk = SB.packet(SB.scan())
    check("خروجی گذرگاه بستهٔ شواهد کامل دارد", EP.validate(pk) == [],
          str(EP.validate(pk)))
finally:
    SB.SIGDIR, SB.REGISTRY = old_sig, old_reg

# ── قرارداد نباید دروغ بگوید: تولیدکنندهٔ هر ردیف واقعاً وجود دارد ─────────
# ممیزی ۲ سپتامبر: ۸ ردیف تولیدکننده‌ای را نام می‌بردند که فایلش وجود نداشت
# (ob_radar.py به‌جای ob_intel.py، experience.py به‌جای publish_experience.py…).
# قراردادی که مالک را غلط بگوید، در خرابی کسی را به جای غلط می‌فرستد.
_reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))
_py = ROOT / "claude-liam-signal" / "python"
_ghost = []
for _fn, _row in _reg["files"].items():
    _prod = str(_row.get("producer") or "")
    _first = _prod.split(" ")[0].split("(")[0]
    if _first.endswith(".py") and not _first.startswith("external"):
        if not (_py / _first).exists() and not (ROOT / _first).exists():
            _ghost.append((_fn, _first))
check("هر تولیدکنندهٔ قرارداد وضعیت فایلِ موجودی است", not _ghost, str(_ghost))

# ── اثباتِ یادگیری تولیدکنندهٔ اجراشونده دارد (۶ سپتامبر) ─────────────────
#
# علت، نه حادثه: این فایل تنها تولیدکننده‌اش `liam9d.py` بود — سرویس محلی
# لپ‌تاپ که مستقر نیست — پس ۲۴ ساعت کهنه ماند و گذرگاه DEGRADED داد.
# فایلی که پنل مصرفش می‌کند نباید تنها تولیدکننده‌اش چیزی باشد که اجرا
# نمی‌شود؛ تا استقرار آن سرویس، Actions مرجع عملیاتی است (CLAUDE.md).
_cyc = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
check("چرخه خودش اثباتِ یادگیری را تولید می‌کند",
      "hamid.learning_proof --write" in _cyc)

# ── پنل واقعاً همین نقشه را نشان می‌دهد ───────────────────────────────────
panel = (ROOT / "index.html").read_text(encoding="utf-8")
check("پنل نقشهٔ وضعیت سامانه را می‌خواند",
      "signals/system-state.json" in panel)
check("پنل کارت یکپارچگی سامانه دارد", 'id="sysStateBox"' in panel)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
