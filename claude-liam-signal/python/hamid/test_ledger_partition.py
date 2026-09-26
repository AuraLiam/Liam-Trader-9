"""پاسبان دفترِ هفتگی‌پاره (hamid/ledger.py) — هیچ دفتری به دیوارِ ۱۰۰MB گیت‌هاب نمی‌رسد.

ریشه (۲۶ سپتامبر): `guardian-lab` سه هفته با GH001 شکست خورد و تابلویش ۲۲
روز کهنه ماند؛ `closed.jsonl` (۹۱.۷MB، +۴.۲MB/روز) دو روز تا همان دیوار
داشت — روزی که رد می‌شد، هر ناشرِ چرخه و زنجیره با آن می‌مرد.

این آزمون **خاصیت** را می‌سنجد نه شکل را:
  ۱. ردیفِ تازهٔ دفترِ منتشرشده هرگز به فایلِ یخ‌زده نمی‌رود.
  ۲. پاره قطعی است (دو رانر برای یک ردیف یک فایل را می‌گزینند).
  ۳. خواننده همه را می‌خواند و هم‌پوشانیِ یخ‌زده/پاره دوبار شمرده نمی‌شود.
  ۴. هویتِ دفترِ رأی متنِ کامل است، نه trade_key (که همهٔ رأی‌های یک نماد را یکی می‌کرد).
  ۵. دفترِ موقت (خارج از brain/ و signals/) رفتارِ قبلی را دارد.
  ۶. هیچ کدِ تولیدی به دفترِ یخ‌زده (ledger.FROZEN) مستقیم append نمی‌کند.
  ۷. با --runway، روی مخزنِ واقعی: هیچ jsonl کمتر از RUNWAY_DAYS تا دیوار ندارد.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import ledger                                       # noqa: E402

OK, BAD = [], []


def check(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  — {extra}" if extra and not cond else ""))


W38 = 1758240000000   # 2025-09-19 → ISO 2025-W38
W39 = W38 + 7 * 86400000

tmp = Path(tempfile.mkdtemp())
old_pub = ledger.PUBLISHED
ledger.PUBLISHED = [tmp]                   # این پوشهٔ موقت «منتشرشده» حساب شود
try:
    base = tmp / "paper" / "closed.jsonl"
    base.parent.mkdir(parents=True)
    frozen_row = {"sym": "AAA", "opened": 1, "entry": 1.0, "why": {"stage": "sig"}, "closed": W38}
    base.write_text(json.dumps(frozen_row) + "\n")
    size0 = base.stat().st_size

    # ۱ و ۲
    p1 = ledger.append(base, {"sym": "BBB", "opened": 2, "entry": 2.0, "why": {"stage": "sig"}, "closed": W38})
    p2 = ledger.append(base, {"sym": "CCC", "opened": 3, "entry": 3.0, "why": {"stage": "sig"}, "closed": W39})
    check("ردیفِ تازه به فایلِ یخ‌زده نمی‌رود", base.stat().st_size == size0)
    check("پاره از زمانِ خودِ ردیف می‌آید (قطعی)",
          p1.name == "closed-2025-W38.jsonl" and p2.name == "closed-2025-W39.jsonl", f"{p1.name} {p2.name}")
    check("پارهٔ یک ردیف همیشه همان است",
          ledger.part_for(base, W38 + 1000) == ledger.part_for(base, W38 + 2000))

    # ۳ — رانرِ هنوز-قدیمی همان معامله را با تسویهٔ دیگر در یخ‌زده نوشته
    dup = dict(frozen_row, closed=W38 + 5, sym="BBB", opened=2, entry=2.0)
    with base.open("a") as f:
        f.write(json.dumps(dup) + "\n")
    rows = ledger.read(base)
    syms = sorted(r["sym"] for r in rows)
    check("خواننده همه را می‌خواند و تکرارِ هویت یک بار", syms == ["AAA", "BBB", "CCC"], syms)
    check("text_lines همان یکتاسازی را دارد", len(ledger.text_lines(base)) == 3)
    check("tail فقط انتهای تازه‌ترین پاره", [r["sym"] for r in ledger.read(base, key=None, tail=1)] == ["CCC"])

    # ۴ — دفتر رأی: دو رأیِ متفاوتِ یک نماد نباید یکی شوند
    votes = tmp / "guardians" / "live-votes.jsonl"
    votes.parent.mkdir()
    votes.write_text(json.dumps({"sym": "AAA", "g": "leo", "v": 1, "at": W38}) + "\n")
    ledger.append(votes, {"sym": "AAA", "g": "virgo", "v": -1, "at": W38}, "at")
    ledger.append(votes, {"sym": "AAA", "g": "virgo", "v": -1, "at": W38}, "at")   # تکرارِ عینی
    check("رأی‌های یک نماد یکی نمی‌شوند؛ فقط تکرارِ عینی", len(ledger.read(votes)) == 2,
          len(ledger.read(votes)))

    # ۵ — دفترِ موقتِ بیرون از قلمرو
    ledger.PUBLISHED = [tmp / "nowhere"]
    plain = tmp / "plain" / "closed.jsonl"
    ledger.append(plain, {"sym": "X", "closed": W38})
    check("دفترِ بیرون از brain/signals روی همان فایل append می‌شود",
          plain.exists() and not ledger.parts(plain))
    check("تک‌فایل: خواندن بی‌یکتاسازی (رفتار پیشین)",
          len(ledger.read(plain)) == 1)
finally:
    ledger.PUBLISHED = old_pub

# ۶ — نویسندهٔ مستقیمِ دفترِ یخ‌زده (کلاسِ عیب): هر ثابتی که به یکی از
# FROZEN اشاره کند نباید با open("a") نوشته شود — فقط ledger.append.
check("قلمروِ پاره‌سازی همان brain/ و signals/ مخزن است",
      ledger._published(ledger.REPO / "brain" / "paper" / "closed.jsonl")
      and not ledger._published("/tmp/x/closed.jsonl"))
SRC = Path(__file__).resolve().parent
direct = []
for p in SRC.glob("*.py"):
    if p.name.startswith("test_") or p.name == "ledger.py":
        continue
    src = p.read_text(encoding="utf-8")
    for fz in ledger.FROZEN:
        bn = Path(fz).name
        if bn not in src:
            continue
        consts = re.findall(r"^(\w+)\s*=.*[\"']" + re.escape(bn), src, re.M)
        for c in consts:
            if re.search(re.escape(c) + r"\.open\(\s*[\"']a|open\(\s*" + re.escape(c) + r"\s*,\s*[\"']a", src):
                direct.append(f"{p.name}:{c}")
check("هیچ ماژولی مستقیم به دفترِ یخ‌زده append نمی‌کند", not direct, direct)

# ۶ب — رفتاری: دو نویسنده‌ای که ۲۶ سپتامبر فایلِ یخ‌زده را پر کردند/پاک می‌کنند.
from hamid import receipts_guard as _RG, dedupe_closed as _DC      # noqa: E402
_t = Path(tempfile.mkdtemp())
_old = (ledger.PUBLISHED, _RG.ROOT, _DC.CLOSED, _RG.ARCHIVE)
try:
    ledger.PUBLISHED = [_t / "brain"]
    _RG.ROOT, _RG.ARCHIVE = _t, _t / "signals" / "archive"
    _cl = _t / "brain" / "paper" / "closed.jsonl"
    _cl.parent.mkdir(parents=True)
    _fz = {"sym": "OLD", "opened": 1, "entry": 1.0, "why": {"stage": "sig"}, "closed": W38}
    _cl.write_text(json.dumps(_fz) + "\n")
    _p = {"sym": "NEW", "opened": 2, "entry": 2.0, "why": {"stage": "sig"}, "closed": W39}
    ledger.append(_cl, _p, "closed")
    _bk = _t / "bk" / "receipts"
    _bk.mkdir(parents=True)
    _lost = {"sym": "LOST", "opened": 3, "entry": 3.0, "why": {"stage": "sig"}, "closed": W39}
    (_bk / "closed.jsonl").write_text("\n".join(json.dumps(x) for x in (_fz, _p, _lost)) + "\n")
    _size = _cl.stat().st_size
    _RG.restore(_t / "bk")
    check("restore فایلِ یخ‌زده را بازنویسی نمی‌کند (ردیفِ پاره به آن برنمی‌گردد)",
          _cl.stat().st_size == _size, f"{_size} → {_cl.stat().st_size}")
    check("و ردیفِ گم‌شده به پارهٔ هفتهٔ خودش برمی‌گردد",
          sorted(r["sym"] for r in ledger.read(_cl)) == ["LOST", "NEW", "OLD"])
    # حالت خرابِ ۲۶ سپتامبر را دستی می‌سازیم: ردیفِ پاره در یخ‌زده هم هست
    with _cl.open("a") as _f:
        _f.write(json.dumps(_p) + "\n")
    _DC.CLOSED = _cl
    _res = _DC._cross(True, ledger.files(_cl), True)
    check("پاک‌سازی بین‌فایلی فقط تکرارِ هفتهٔ پاره را از یخ‌زده برمی‌دارد",
          _res["dropped"] == 1 and [json.loads(x)["sym"] for x in _cl.read_text().splitlines()] == ["OLD"],
          str(_res))
    check("و هیچ معامله‌ای گم نمی‌شود", sorted(r["sym"] for r in ledger.read(_cl)) == ["LOST", "NEW", "OLD"])
finally:
    ledger.PUBLISHED, _RG.ROOT, _DC.CLOSED, _RG.ARCHIVE = _old

# ۶ج — ناشر پاک‌سازی را پس نمی‌زند: اجتماعِ سادهٔ نسخهٔ origin (با تکرار) و
# نسخهٔ ما (پاک‌شده) همان ۴٬۷۳۵ ردیف را برگرداند (۲۶ سپتامبر، روی محصول).
import importlib.util as _ilu                                    # noqa: E402
_spec = _ilu.spec_from_file_location("rbc_l", ledger.REPO / "scripts" / "resolve_brain_conflicts.py")
_rbc = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_rbc)
_r = Path(tempfile.mkdtemp())
(_r / "brain" / "paper").mkdir(parents=True)
_a = {"sym": "OLD", "opened": 1, "entry": 1.0, "why": {"stage": "sig"}, "closed": W38}
_b = {"sym": "NEW", "opened": 2, "entry": 2.0, "why": {"stage": "sig"}, "closed": W39}
(_r / "brain/paper/closed-2025-W39.jsonl").write_text(json.dumps(_b) + "\n")
_ours = json.dumps(_a) + "\n"
_theirs = json.dumps(_a) + "\n" + json.dumps(_b) + "\n"
_old_root, _old_stage = _rbc.ROOT, _rbc._stage
try:
    _rbc.ROOT = _r
    _rbc._stage = lambda st, p: ({2: _ours, 3: _theirs}.get(st)
                                 if p == "brain/paper/closed.jsonl" else None)
    check("ادغامِ ناشر برای دفتر یخ‌زده همان handlerِ منهای‌پاره است",
          _rbc.handler_for("brain/paper/closed.jsonl") is _rbc.merge_frozen_closed)
    _rbc.merge_frozen_closed("brain/paper/closed.jsonl")
    _got = [json.loads(x)["sym"] for x in (_r / "brain/paper/closed.jsonl").read_text().splitlines() if x]
    check("اجتماع با origin تکرارِ پاره را به یخ‌زده برنمی‌گرداند", _got == ["OLD"], str(_got))
finally:
    _rbc.ROOT, _rbc._stage = _old_root, _old_stage

# ۷ — روی مخزنِ واقعی (فقط با --runway): به داده بسته است نه به کد، پس در
# دروازهٔ سخت نیست — درسِ ۶ سپتامبر: آزمونِ وابسته به داده در دروازهٔ سخت
# چرخه را می‌خواباند. در گامِ «آزمون ابزارها» دیده می‌شود، و watchdog هم.
if "--runway" in sys.argv:
    rw = ledger.runway(ledger.REPO)
    short = [r for r in rw if r["days_left"] is not None and r["days_left"] < ledger.RUNWAY_DAYS]
    check(f"هیچ دفتری کمتر از {ledger.RUNWAY_DAYS} روز تا دیوارِ ۱۰۰MB ندارد", not short, short)
    over = [r for r in rw if r["mb"] * 1e6 >= ledger.LIMIT_BYTES]
    check("هیچ فایلی از ۱۰۰MB نگذشته", not over, over)
    for r in rw[:5]:
        print(f"      {r['path']}: {r['mb']}MB · {r['kind']} · +{r['mb_per_day']}MB/روز · "
              f"{'∞' if r['days_left'] is None else r['days_left']} روز")

wf = (ledger.REPO / ".github" / "workflows")
check("پاسبان در دروازهٔ هر دو زنجیره",
      all("hamid.test_ledger_partition" in (wf / f).read_text() for f in ("hamid-cycle.yml", "pump-radar.yml")))

print()
if BAD:
    print(f"✗ {len(BAD)} بررسی افتاد: {BAD}")
    sys.exit(1)
print(f"پاسبان دفتر هفتگی‌پاره: هر {len(OK)} بررسی سبز")
