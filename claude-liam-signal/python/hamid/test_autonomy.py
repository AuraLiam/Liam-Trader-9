"""پاسبان قانون ۱۸ — خودگردانی و ابزار-اول.

سه چیز را قفل می‌کند: (الف) ابزارهای روتین وصل و ثبت‌اند، (ب) استثناهای
تأیید خودکار (LIVE_EXECUTION، force-push، برند/بات) در کد قابل‌دورزدن
نیستند، (پ) سه متخصصِ قبلاً خاموش از دادهٔ ابزارها رأی می‌گیرند.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PY))
OK, FAIL = 0, []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


rule = ROOT / ".claude" / "rules" / "18-autonomy-tools-first.md"
check("قانون ۱۸ وجود دارد", rule.exists())
rtxt = rule.read_text(encoding="utf-8") if rule.exists() else ""
check("و ۱۵ دقیقه و استثناهای LIVE_EXECUTION/force-push را نام می‌برد",
      "۱۵ دقیقه" in rtxt and "LIVE_EXECUTION" in rtxt and "force-push" in rtxt)

reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
for f in ("holding.json", "live-results.json", "guardian-delta.json"):
    check(f"{f} ردیف قرارداد دارد", f in reg)

cyc = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
for m in ("hamid.holding_intake --write", "hamid.live_results --write", "hamid.guardian_delta --write", "hamid.handoff --write"):
    check(f"چرخهٔ حمید {m.split()[0]} را می‌زند", m in cyc)
from hamid import liam9d as D                        # noqa: E402
keys = {j["key"] for j in D.JOBS}
check("سرویس محلی هر سه ابزار روتین را دارد", {"holding_intake", "live_results", "guardian_delta"} <= keys, str(keys & {"holding_intake", "live_results", "guardian_delta"}))

# استثناها: اجرای زنده خاموش، در همهٔ فایل‌هایی که آن را تعریف می‌کنند
hits = []
for p in list(PY.glob("*.py")) + list((PY / "hamid").glob("*.py")):
    for m in re.finditer(r"^\s*LIVE_EXECUTION\s*=\s*(\S+)", p.read_text(encoding="utf-8", errors="replace"), re.M):
        hits.append((p.name, m.group(1)))
check("LIVE_EXECUTION هر جا تعریف شده خاموش است", hits and all(v.strip().rstrip(",").strip("\"'").lower() == "false" for _, v in hits), str(hits))
pub = "\n".join(l for l in (ROOT / "scripts" / "publish.sh").read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
check("ناشر یگانه force-push/reset --hard ندارد (کامنت‌ها جدا)",
      not re.search(r"git\s+push[^\n]*(--force\b|--force-with-lease|\s-f\b)", pub) and "reset --hard" not in pub)

# سه متخصصِ خاموش: بافت از ابزارها
from hamid import phoenix as P                       # noqa: E402
src = Path(P.__file__).read_text(encoding="utf-8")
check("بافت ققنوس بستر BTC و جمعیت را از فایل‌های ابزار می‌خواند",
      "_btc_ctx(" in src and "_crowd(" in src and "DOM_DESK" in src and "INTAKE" in src)
check("قوس اجماعِ بی‌وزن را نصف‌قوت می‌گیرد، نه ممتنع", "news_weighted" in src and "0.25" in src)
check("دلو فاندینگ و ترس‌وطمع را می‌خواند", "funding_btc" in src and "fear_greed" in src)

# صندوق هولدینگ: محتوا داده است نه دستور — هیچ exec/eval/subprocess روی محتوا
hsrc = (PY / "hamid" / "holding_intake.py").read_text(encoding="utf-8")
body = re.sub(r'"""[\s\S]*?"""', "", hsrc)
body = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))
check("صندوق هولدینگ هیچ فرمانی از محتوای فایل اجرا نمی‌کند",
      not re.search(r"\b(exec|eval|subprocess|os\.system)\b", body))

# ۱۶ سپتامبر — «نمی‌خوام هر بار allow بزنم»: اجازه‌های روتین از پیش در
# settings.json ثبت‌اند؛ استثناهای بند ۳ (force-push/reset --hard/حذف
# بازگشتی/ارسال از Gmail) در فهرست deny و در هوک محافظ می‌مانند.
import json as _json
stg = _json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
perm = stg.get("permissions") or {}
allow, deny = set(perm.get("allow") or []), set(perm.get("deny") or [])
check("اجازهٔ روتین از پیش داده شده (پایتون/گیت/ابزار لیام۹/گیت‌هاب)",
      {"Bash(python3:*)", "Bash(git commit:*)", "Bash(git push:*)", "mcp__liam9", "mcp__github"} <= allow,
      str(sorted(allow)[:6]))
check("استثناهای قانون ۱۸ در فهرست deny مانده‌اند",
      {"Bash(git push --force:*)", "Bash(git reset --hard:*)", "Bash(rm -rf:*)", "mcp__Gmail__send_message"} <= deny,
      str(sorted(deny)[:6]))
check("هوک محافظ Bash هنوز نصب است", any("claude_guard.py" in _json.dumps(h) for h in (stg.get("hooks") or {}).get("PreToolUse") or []))
guard = (ROOT / "scripts" / "claude_guard.py").read_text(encoding="utf-8")
check("هوک محافظ force-push و reset --hard و LIVE_EXECUTION را می‌بندد",
      "--force" in guard and "reset\\s+--hard" in guard and "LIVE_EXECUTION" in guard)

# ۱۶ سپتامبر — ممیزی تلگرام (۸۱۲ پیام/۷ روز، ۲۶٪ بی‌مخاطب): شکاک و ارجاع
# خودکار فقط پنل/صف بازبینی‌اند؛ هیچ مسیری (Actions یا سرویس محلی) با
# --telegram صدایشان نمی‌زند.
from hamid import liam9d as _D
_cmds = {j["key"]: " ".join(j["cmd"]) for j in _D.JOBS}
check("سرویس محلی شکاک را بی‌تلگرام می‌زند (فقط پنل)", "--telegram" not in _cmds.get("skeptic", ""))
_wfs = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / ".github" / "workflows").glob("*.yml"))
check("هیچ ورک‌فلویی شکاک/ارجاع را با --telegram نمی‌زند",
      not re.search(r"hamid\.(skeptic|escalation)[^\n]*--telegram", _wfs))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
