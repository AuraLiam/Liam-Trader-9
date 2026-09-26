"""پاسبان قانون ۱۷ — اسکن‌بردار، دسته‌بند، و این‌که هیچ ایجنتی بی‌سطل نماند.

کلاسِ عیبی که می‌گیرد: ابزاری که ساخته شده ولی (الف) به زنجیره/سرویس محلی
وصل نیست، (ب) ردیف قرارداد ندارد، یا (ج) ایجنت‌ها از وجودش خبر ندارند —
سه راهی که یک ابزار می‌تواند «وجود داشته باشد» و هیچ توکنی صرفه نکند.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PY))

OK = 0
FAIL = []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


# ۱) خودآزمایی هر دو ابزار
for m in ("intake", "dispatch"):
    r = subprocess.run([sys.executable, "-m", f"hamid.{m}", "--selftest"],
                       capture_output=True, text=True, timeout=300, cwd=str(PY),
                       env={**__import__("os").environ, "LIAM9_SANDBOX": "1"})
    check(f"خودآزمایی {m} سبز است", r.returncode == 0, (r.stdout + r.stderr)[-300:])

# ۲) ردیف قرارداد (قانون ۱۳) — فایلِ بی‌مالک یتیم است و چرخه را سرخ می‌کند
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
for f in ("intake.json", "buckets.json"):
    check(f"{f} ردیف قرارداد دارد با سقف کهنگی", f in reg and reg[f].get("max_age_min"))

# ۳) اتصال به زنجیرهٔ سیگنال و سرویس محلی (قانون ۰۲)
chain = (ROOT / ".github" / "workflows" / "pump-radar.yml").read_text(encoding="utf-8")
check("زنجیرهٔ سیگنال اسکن‌بردار را می‌زند", "hamid.intake --write" in chain)
check("و بعدش دسته‌بند را", "hamid.dispatch --write" in chain
      and chain.index("hamid.intake --write") < chain.index("hamid.dispatch --write"))
from hamid import liam9d as D                        # noqa: E402
keys = {j["key"]: j for j in D.JOBS}
check("سرویس محلی intake را هر ۵ دقیقه دارد", "intake" in keys and keys["intake"]["every"] == 300)
check("و dispatch را", "dispatch" in keys and keys["dispatch"]["every"] == 300)

# ۴) هر ایجنت سطل خودش را می‌شناسد — ایجنتی که بلوک ندارد، سطل را نمی‌خواند
agents = sorted((ROOT / ".claude" / "agents").glob("*.md"))
missing = [p.name for p in agents if "<!-- bucket-rule -->" not in p.read_text(encoding="utf-8")]
check(f"هر {len(agents)} ایجنت بلوکِ «سطلِ من» دارد", not missing, str(missing))
from hamid import dispatch as DP                     # noqa: E402
ops = [p.stem for p in agents if not re.match(r"e\d\d-", p.name)]
check("هر ایجنت عملیاتی در نگاشت دسته‌بند هست", set(ops) == set(DP.AGENT_ENGINES), str(set(ops) ^ set(DP.AGENT_ENGINES)))
# کلید داخل بلوک با نگاشت می‌خواند
bad = []
for p in agents:
    txt = p.read_text(encoding="utf-8")
    m = re.search(r"dispatch --bucket (\S+)`", txt)
    key = m.group(1) if m else None
    want = f"E{p.name[1:3]}" if re.match(r"e\d\d-", p.name) else p.stem
    if key != want:
        bad.append((p.name, key, want))
check("کلیدِ سطل داخل هر ایجنت با نامش می‌خواند", not bad, str(bad[:4]))

# ۴ب) هیچ ایجنت عملیاتی سطلِ خالی نمی‌گیرد — روی قراردادِ واقعی، نه نمونهٔ دستی.
# عیبِ ۲۶ سپتامبر: market-structure فقط به E07 وصل بود که فایلی ندارد، پس
# سطلش همیشه خالی بود و قاعدهٔ «read_next خالی = چیزی نخوان» کورش می‌کرد.
from hamid import dispatch as _D                                 # noqa: E402
_items = [{"id": f"state:{f}", "family": "state", "owner": r.get("owner"),
           "consumer": r.get("consumer"), "ok": True, "at": 1, "digest": {}}
          for f, r in reg.items()]
_eng = set()
for _it in _items:
    _eng |= _D._engines_for(_it)
_empty = {a: e for a, e in _D.AGENT_ENGINES.items() if not (set(e) & _eng)}
check("هر ایجنت عملیاتی دست‌کم یک فایلِ قرارداد در سطلش دارد", not _empty, str(_empty))
check("مصرف‌کنندهٔ ترکیبیِ قرارداد («E18/E22 + MCP»، «panel+telegram») مسیر می‌گیرد",
      {"E22", "E11"} <= _D._engines_for({"family": "state", "owner": "E18",
                                         "consumer": "E18/E22/E11 + MCP"})
      and "E25" in _D._engines_for({"family": "state", "owner": "E17", "consumer": "panel+telegram"}))

# ۵) قانون ۱۷ مکتوب است و به محافظ اشاره می‌کند
rule = ROOT / ".claude" / "rules" / "17-intake-buckets.md"
check("قانون ۱۷ وجود دارد", rule.exists())
check("و همین محافظ را نام می‌برد", rule.exists() and "test_intake" in rule.read_text(encoding="utf-8"))

# ۶) تزریق idempotent است — دوباره زدنش چیزی اضافه نمی‌کند
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "inject_bucket_rule.py")],
                   capture_output=True, text=True, timeout=60)
check("تزریقِ دوباره چیزی اضافه نمی‌کند", "تزریق شد: 0" in r.stdout, r.stdout[-120:])

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
