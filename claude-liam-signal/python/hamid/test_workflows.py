"""آزمون سلامت ورک‌فلوها — درس ۱۴ اوت: live-scan روزها بی‌صدا مرده بود.

عیب واقعی: یک گام دو کلید `if` داشت. پایتون YAML را می‌خواند (آخری برنده)
و همهٔ بررسی‌های ما سبز می‌شد، ولی **گیت‌هاب کل فایل را رد می‌کرد** —
run با صفر job، وضعیت failure، و در API به‌جای «Live scan» مسیر فایل
نشان داده می‌شد. یعنی اسکن زنده اصلاً اجرا نمی‌شد و فقط ایمیل
«Run failed» می‌آمد.

این آزمون همان چیزی را می‌سنجد که گیت‌هاب سخت‌گیرانه می‌سنجد:
  ۱. هیچ کلید تکراری در هیچ سطحی (چیزی که SafeLoader بی‌صدا می‌بلعد)
  ۲. name/on/jobs موجود باشد
  ۳. هر گام حداکثر یک if داشته باشد و هر job حداقل یک گام
  ۴. هر uses نسخهٔ پین‌شده داشته باشد
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WF = ROOT / ".github" / "workflows"

ok = 0
fail = []


def check(name, cond):
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail.append(name)
        print(f"  ✗ {name}")


class StrictLoader(yaml.SafeLoader):
    """مثل گیت‌هاب: کلید تکراری خطاست، نه «آخری برنده»."""


def _no_dup(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise ValueError(f"کلید تکراری: {key!r}")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dup)


def _raw_dup_if(text):
    """کلید if تکراری داخل یک گام، حتی اگر YAML آن را بپذیرد."""
    bad, cur = [], None
    for i, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s.startswith(("- name:", "- uses:", "- if:")):
            cur = {"ifs": 1 if s.startswith("- if:") else 0}
        elif cur is not None and s.startswith("if:"):
            cur["ifs"] += 1
            if cur["ifs"] > 1:
                bad.append(i)
    return bad


print("── سلامت ورک‌فلوها ──")

files = sorted(WF.glob("*.yml")) + sorted(WF.glob("*.yaml"))
check(f"ورک‌فلو پیدا شد ({len(files)})", len(files) > 0)

dup, missing, many_if, unpinned, empty = [], [], [], [], []
for f in files:
    text = f.read_text(encoding="utf-8")
    try:
        j = yaml.load(text, StrictLoader)
    except Exception as e:                            # noqa: BLE001
        dup.append(f"{f.name}: {e}")
        continue
    if not j or "name" not in j or "jobs" not in j or not (True in j or "on" in j):
        missing.append(f.name)
        continue
    for ln in _raw_dup_if(text):
        many_if.append(f"{f.name}:{ln}")
    for jid, job in (j.get("jobs") or {}).items():
        steps = job.get("steps") or []
        if not steps:
            empty.append(f"{f.name}:{jid}")
        for s in steps:
            u = s.get("uses")
            if u and "@" not in str(u):
                unpinned.append(f"{f.name}: {u}")

check("هیچ کلید تکراری در هیچ ورک‌فلو (همان چیزی که گیت‌هاب رد می‌کند)", not dup)
for d in dup:
    print(f"      ↳ {d}")
check("همهٔ ورک‌فلوها name/on/jobs دارند", not missing)
if missing:
    print(f"      ↳ {missing}")
check("هیچ گامی دو if ندارد", not many_if)
if many_if:
    print(f"      ↳ {many_if}")
check("هر job حداقل یک گام دارد", not empty)
if empty:
    print(f"      ↳ {empty}")
check("همهٔ uses نسخهٔ پین‌شده دارند", not unpinned)
if unpinned:
    print(f"      ↳ {unpinned}")

# بلاک ساختاریِ خالی (مثل «env:» بی‌مقدار) = Invalid workflow file در گیت‌هاب؛
# ۱۷ اوت سه ورک‌فلو را همین‌طور از کار انداخت — این محافظ برگشتش را می‌بندد.
_STRUCT = {"env", "permissions", "jobs", "steps", "with", "defaults",
           "concurrency", "strategy", "container", "services"}
hollow = []
def _walk(node, path, fname):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _STRUCT and v is None:
                hollow.append(f"{fname}: {path}{k}")
            _walk(v, f"{path}{k}.", fname)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, f"{path}{i}.", fname)
for f in files:
    try:
        _walk(yaml.safe_load(f.read_text()), "", f.name)
    except yaml.YAMLError:
        pass  # خطای پارس را چک‌های قبلی می‌گیرند
check("هیچ بلاک ساختاری خالی نیست (env:/jobs:/steps: بی‌مقدار)", not hollow)
if hollow:
    print(f"      ↳ {hollow}")

# لولهٔ بی‌محافظ: در بش، کد خروجِ یک لوله همان کد خروج *آخرین* دستور است.
# پس `python3 -m X | tee log` وقتی پایتون کرش می‌کند هم صفر برمی‌گرداند و
# مرحله سبز می‌شود. ۱۹ اوت همین اتفاق افتاد: بک‌تست ۱ساعته با KeyError مرد،
# ورک‌فلو «موفق» شد، و هیچ خروجی‌ای تولید نشد بدون آن‌که کسی خبردار شود —
# در ده ورک‌فلو همین الگو بود. هر لوله باید `set -o pipefail` داشته باشد.
leaky = []
for f in files:
    try:
        doc = yaml.safe_load(f.read_text())
    except yaml.YAMLError:
        continue
    for job in (doc.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for st in (job.get("steps") or []):
            if not isinstance(st, dict):
                continue
            body = st.get("run") or ""
            if "|" not in body:
                continue
            piped = [ln for ln in body.splitlines()
                     if re.search(r"\|\s*(tee|grep|head|tail|jq|python)", ln)
                     and "||" not in ln]
            if piped and "pipefail" not in body:
                leaky.append(f"{f.name}: {st.get('name') or 'بی‌نام'}")
check("هیچ لولهٔ بی‌محافظی نیست (هر `| tee` با set -o pipefail)", not leaky)
if leaky:
    print(f"      ↳ {leaky}")

# `git add <فایل مشخص>` وقتی آن فایل هنوز ساخته نشده، exit 128 می‌دهد و کل
# مرحلهٔ انتشار می‌خوابد. ۱۹ اوت همین اتفاق افتاد: فایل فرمان‌ها هنوز وجود
# نداشت، `git add signals/link-commands.json` شکست، و میز اسکلپ و میز شوک
# شش ساعت هیچ داده‌ای منتشر نکردند. افزودن **پوشه** هرگز این‌طور نمی‌شکند.
addfile = []
for f in files:
    try:
        doc = yaml.safe_load(f.read_text())
    except yaml.YAMLError:
        continue
    for job in (doc.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for st in (job.get("steps") or []):
            if not isinstance(st, dict):
                continue
            for ln in (st.get("run") or "").splitlines():
                m = re.search(r"git add\s+(.+)", ln.strip())
                if not m or "-f " in ln:
                    continue
                for tok in m.group(1).split():
                    if tok.startswith("-"):
                        continue
                    if re.search(r"\.(json|jsonl|txt|html|js)$", tok) \
                            and "[ -f" not in ln and "$(" not in ln:
                        addfile.append(f"{f.name}: git add {tok}")
check("هیچ `git add` روی فایل تکیِ ممکن‌الغیاب نیست (پوشه اضافه شود)",
      not addfile)
if addfile:
    print(f"      ↳ {addfile}")

# ── عقب‌گرد در برابر کرش‌لوپ (درس ۲۳ اوت) ───────────────────────────────
# زنجیرهٔ سیگنال خودش را dispatch می‌کند. شرطش `always()` بود، پس حتی
# وقتی دروازهٔ خودآزماییِ خودش شکسته بود اجرای بعدی را صدا می‌زد. یک خط
# اشتباه در ورک‌فلوی عمق آن دروازه را قرمز کرد و نتیجه ~۵۵۰ اجرای
# شکست‌خورده در ۸ ساعت شد — یک بار در دقیقه — که ظرفیت رانر را بلعید و
# live-scan و scalp و shock-desk را هم از ۴ اجرا در ساعت به ۱ رساند.
# سیگنال ۸ ساعت قطع بود.
#
# قاعده: هر گامی که ورک‌فلوی خودش را dispatch می‌کند، حق ندارد بعد از
# شکستِ گامِ خودآزمایی اجرا شود. کرون و مدیک تور ایمنی‌اند (۴ تلاش در
# ساعت به‌جای ۶۰).
selfdispatch = []
for f in files:
    try:
        doc = yaml.safe_load(f.read_text())
    except yaml.YAMLError:
        continue
    for job in (doc.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        steps = [s for s in (job.get("steps") or []) if isinstance(s, dict)]
        # id گام‌هایی که آزمون/خودآزمایی‌اند
        gates = [s.get("id") for s in steps if s.get("id")
                 and re.search(r"test|selftest|خودآزمایی|آزمون",
                               f"{s.get('id','')} {s.get('name','')}")]
        for st in steps:
            run = st.get("run") or ""
            if f"workflows/{f.name}/dispatches" not in run:
                continue
            cond = str(st.get("if") or "")
            if "always()" not in cond:
                continue          # بدون always() اصلاً بعد از شکست اجرا نمی‌شود
            if not any(g and f"steps.{g}.outcome" in cond for g in gates):
                selfdispatch.append(f"{f.name}: «{st.get('name')}»")
check("هیچ زنجیرهٔ خوددعوتی بعد از شکستِ دروازهٔ خودش دوباره صدا نمی‌شود",
      not selfdispatch)
if selfdispatch:
    print(f"      ↳ {selfdispatch}")

# ── بودجهٔ تلاشِ پوش (عیب ۲۳ اوت) ──────────────────────────────────────
#
# main امروز ۶۴۶ پوش خورد — یعنی هر ~۲ دقیقه یکی. حلقهٔ قدیمی ۵ تلاش با
# sleep=attempt*3 داشت: مجموعاً ۳۰ ثانیه پنجره، و بدون jitter دو رانر
# دقیقاً هم‌گام تلاش می‌کردند. نتیجه: «cannot lock ref … is at X but
# expected Y» و یک اجرای سرخ که هیچ عیب واقعی‌ای نداشت.
import re as _re
_weak_loop, _no_jitter = [], []
for f in files:
    src = f.read_text(encoding="utf-8", errors="ignore")
    if "git push" not in src:
        continue
    for m in _re.finditer(r"for (?:attempt|a|i) in ([\d ]+); do", src):
        if len(m.group(1).split()) < 8:
            _weak_loop.append(f"{f.name}:{m.group(1).strip()}")
    for m in _re.finditer(r"sleep \$\(\(([^)]*)\)\)", src):
        body = m.group(1)
        if ("attempt" in body or _re.search(r"\ba\b|\bi\b", body)) \
                and "RANDOM" not in body:
            _no_jitter.append(f"{f.name}:{body.strip()}")

check(f"هر حلقهٔ پوش دست‌کم ۸ تلاش دارد (بی‌بودجه: {_weak_loop[:4]})",
      not _weak_loop)
check(f"هر عقب‌نشینیِ پوش jitter دارد — دو رانر هم‌گام تلاش نکنند "
      f"(بی‌jitter: {_no_jitter[:4]})", not _no_jitter)


# ── میزهای خاموش‌شده با دستور صریح حمید ───────────────────────────────
# خاموشی باید **چسبنده** باشد. یک ویرایشِ بی‌دقت که کرون را برگرداند،
# میزی را که سنجش ردش کرده دوباره وارد چرخه می‌کند و هیچ‌کس نمی‌فهمد.
# پس کرونِ برگشته = چرخهٔ سرخ، و دلیلِ خاموشی باید روی خودِ فایل بماند.
#   fname → (تاریخِ خاموشی، رشته‌ای که باید عددِ حکم را روی فایل ثابت کند)
OFF = {"shock-desk.yml": ("۲۴ اوت", "−۰.۰۳۱R")}
for fname, (when, why) in OFF.items():
    p = WF / fname
    check(f"{fname} هنوز وجود دارد (خاموش شد، حذف نشد)", p.exists())
    if not p.exists():
        continue
    txt = p.read_text(encoding="utf-8")
    body = yaml.safe_load(txt)
    trig = body.get(True) or body.get("on") or {}
    check(f"{fname} کرون ندارد — خاموشیِ {when} برنگشته",
          "schedule" not in trig)
    check(f"{fname} هنوز workflow_dispatch دارد (اجرای دستی ممکن بماند)",
          "workflow_dispatch" in trig)
    check(f"{fname} دلیلِ عددیِ خاموشی را روی خودش دارد",
          "خاموش شد" in txt and why in txt)

# ── میز ۱ دقیقه سیگنال تلگرام ندارد (دستور حمید، ۲۵ اوت) ────────────────
# «از ترید یک دقیقه نیازی به ارسال سیگنال نیست — فقط برای داشبورد است که
# مرتب پیپرمود کار کند و تجربه کسب کند.» تنها پیام مجاز میز ۱د، آلارمِ
# «تغییر حکم» (scalp_verdict --alert) است — سیگنال معامله هرگز.
_scalp_srcs = ""
for _n in ("scalp.py", "scalp1m.py", "scalp_verdict.py", "scalp_exec.py"):
    _p = ROOT / "claude-liam-signal" / "python" / "hamid" / _n
    if _p.exists():
        _scalp_srcs += _p.read_text(encoding="utf-8")
check("هیچ ماژول میز ۱د سیگنال تلگرام نمی‌فرستد (فقط پیپر + حکم)",
      "send_signals" not in _scalp_srcs
      and "from hamid import telegram" not in _scalp_srcs
      and "import telegram" not in _scalp_srcs)
_scalp_yml = (ROOT / ".github" / "workflows" / "scalp.yml").read_text(
    encoding="utf-8")
check("ورک‌فلوی اسکلپ تلگرام را فقط به ماشین حکم می‌دهد (آلارم تغییر حکم)",
      _scalp_yml.count("TELEGRAM_BOT_TOKEN:") == 1
      and "scalp_verdict --alert" in _scalp_yml)

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون سلامت ورک‌فلو گذشت ({len(files)} فایل)")
