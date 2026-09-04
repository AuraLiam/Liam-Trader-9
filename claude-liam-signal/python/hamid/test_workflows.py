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
PY = Path(__file__).resolve().parents[1]

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


# ── ضدتکثیر ناشر (دستور حمید، ۲ سپتامبر: «برای همیشه») ──────────────────
#
# اندازه‌گیریِ همان روز: ۴۶ ورک‌فلو، ۴۱ push، ۳۶ حلقهٔ انتشارِ دست‌نویس،
# ۹ reset سخت، فقط ۱۸ با حل‌کنندهٔ معنادار، و ۱۱ خطِ pip پراکنده. سه
# قطعیِ یک روز هر سه از همین تکثیر آمدند. ناشر یگانه `scripts/publish.sh`
# است (آزمون رفتاری: hamid/test_publish.py) و محیط یگانه
# `requirements-ci.txt`.
#
# این پاسبان **ratchet** است: شمارِ ورک‌فلوهای دست‌نویس فقط حق دارد پایین
# برود. مهاجرت تدریجی است (هر ورک‌فلو با اثباتِ اجرای سبز)، ولی ورک‌فلوی
# تازه‌ای که ناشرِ خودش را بیاورد یا pip پراکنده بنویسد، همین‌جا سرخ
# می‌شود. با هر مهاجرت، دو عددِ زیر پایین آورده می‌شود.
import os as _os                                       # noqa: E402
INLINE_PUSHERS_MAX = 31      # ۲ سپتامبر: hamid-cycle، work-report، scout،
                             # history-ingest، strategy-volume، dominance-report،
                             # pump-review مهاجرت کردند
NO_SHARED_DEPS_MAX = 28
_inline, _nodeps, _both = [], [], []
for f in files:
    try:
        doc = yaml.safe_load(f.read_text())
    except yaml.YAMLError:
        continue
    runs, uses = [], []
    for job in (doc.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for st in (job.get("steps") or []):
            if isinstance(st, dict):
                runs.append(st.get("run") or "")
                uses.append(st.get("uses") or "")
    body = "\n".join(runs)
    shared = "scripts/publish.sh" in body
    # «HEAD:main» تحت‌اللفظی کافی نبود: live-scan و backtest و mine با
    # «HEAD:$BRANCH» می‌نوشتند و از شمارش می‌افتادند (۲ سپتامبر). حلقهٔ
    # ناشر با هر نامی که main را هدف بگیرد شمرده می‌شود.
    inline = bool(re.search(r"git push\b", body)) and \
        bool(re.search(r'HEAD:(main|"?\$\{?BRANCH\}?)', body))
    if inline:
        _inline.append(f.name)
    if shared and inline:
        _both.append(f.name)
    if any("setup-python" in u for u in uses) and "hamid." in body \
            and "requirements-ci.txt" not in body:
        _nodeps.append(f.name)
check(f"ناشرِ دست‌نویس تکثیر نشد ({len(_inline)} ≤ {INLINE_PUSHERS_MAX})",
      len(_inline) <= INLINE_PUSHERS_MAX)
if len(_inline) > INLINE_PUSHERS_MAX:
    print(f"      ↳ {_inline}")
elif len(_inline) < INLINE_PUSHERS_MAX:
    print(f"      ↳ ratchet را پایین بیاور: INLINE_PUSHERS_MAX = {len(_inline)}")
check("هیچ ورک‌فلویی هم ناشر مشترک دارد هم حلقهٔ خودش", not _both)
if _both:
    print(f"      ↳ {_both}")
check(f"محیط pip پراکنده تکثیر نشد ({len(_nodeps)} ≤ {NO_SHARED_DEPS_MAX})",
      len(_nodeps) <= NO_SHARED_DEPS_MAX)
if len(_nodeps) > NO_SHARED_DEPS_MAX:
    print(f"      ↳ {_nodeps}")
elif len(_nodeps) < NO_SHARED_DEPS_MAX:
    print(f"      ↳ ratchet را پایین بیاور: NO_SHARED_DEPS_MAX = {len(_nodeps)}")
_pub = WF.parent.parent / "scripts" / "publish.sh"
check("ناشر مشترک وجود دارد و اجرایی است",
      _pub.exists() and _os.access(_pub, _os.X_OK))
check("محیط مشترک وجود دارد و pyyaml را دارد",
      (WF.parent.parent / "requirements-ci.txt").exists()
      and "pyyaml" in (WF.parent.parent / "requirements-ci.txt").read_text())

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

# ── درس ۲۶ اوت عصر: انتشار gh-pages هرگز با rebase نمی‌جنگد ────────────
# پنل حمید ۴۹ دقیقه عقب ماند چون انتشارِ چرخه سرِ تعارض rebase با
# نوشته‌های هم‌زمانِ زنجیره «تسلیم» می‌شد (سه ورک‌فلو با exit 1، بقیه با
# break بی‌صدا). قاعدهٔ کلاس: روی gh-pages فقط merge -X ours — نتیجه‌اش
# همان rebaseِ موفق است ولی روی تعارض نمی‌میرد و حلقهٔ تلاش ادامه دارد.
_bad_rebase = [f.name for f in files
               if "git rebase origin/gh-pages" in f.read_text(encoding="utf-8")]
check(f"هیچ ورک‌فلویی روی gh-pages با rebase نمی‌جنگد {_bad_rebase or ''}",
      not _bad_rebase)
_no_merge = []
for f in files:
    t = f.read_text(encoding="utf-8")
    if "git fetch origin gh-pages" in t and "HEAD:gh-pages" in t \
            and "-X ours" not in t:
        _no_merge.append(f.name)
check(f"هر حلقهٔ پوش gh-pages ادغام ضدتعارض -X ours دارد {_no_merge or ''}",
      not _no_merge)

# ── چسبندگیِ رفعِ «چرخه بیدار شود» (۲۸ اوت) ─────────────────────────────
# گیت‌هاب رویدادهای schedule را در ریپوی پرمصرف می‌اندازد و هیچ خطایی هم
# ثبت نمی‌کند — همهٔ اجراها «موفق» می‌مانند، فقط کمترند. اندازه‌گیری آن
# شب: فاصلهٔ اجراهای hamid-cycle ۹ تا ۱۲ ساعت شد و لایهٔ یادگیری ۷.۵ ساعت
# کهنه ماند. رفع، بیدارکردنِ چرخه از داخل زنجیره است؛ اگر کسی این گام را
# بردارد، همان خرابیِ بی‌صدا برمی‌گردد. پس برداشتنش چرخه را سرخ می‌کند.
_chain = (WF / "pump-radar.yml").read_text(encoding="utf-8")
check("زنجیره چرخه را در کهنگی بیدار می‌کند (رفع اُفتادنِ کرون)",
      "hamid-cycle.yml/dispatches" in _chain
      and "hamid-latest.json" in _chain)
check("بیدارکردن مشروط به کهنگی است، نه هر دور (ضد‌اسپمِ اجرا)",
      'AGE" -gt' in _chain or "AGE\" -gt" in _chain)

# ── کلاسِ عیب: «کهنه بودن» با mtime سنجیده نمی‌شود (۳۰ اوت) ─────────────
# هر اجرای Actions چک‌اوتِ تازه است، پس mtime هر فایل «همین الان» است و
# شرطی مثل `find signals/x.json -mmin +1200` هرگز درست نمی‌شود. عیبِ
# اندازه‌گیری‌شده: btc-sensitivity.json ۲۴۸۵ دقیقه کهنه ماند و گذرگاه
# وضعیت DEGRADED می‌داد، در حالی که ورک‌فلو فکر می‌کرد تازه است. سنِ
# فایلِ وضعیت فقط از مهرِ خودش (`generated`) خوانده می‌شود.
_mtime_gates = []
for f in files:
    for line in f.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        if "-mmin" in s and ("signals/" in s or "brain/" in s):
            _mtime_gates.append(f"{f.name}: {s[:70]}")
check(f"هیچ دروازهٔ تازگی روی mtime دیسک نمی‌نشیند {_mtime_gates or ''}",
      not _mtime_gates)
check("سنِ btc-sensitivity از مهرِ خودِ فایل خوانده می‌شود",
      "btc-sensitivity.json'))['generated']" in _chain)

# ── کلاسِ عیبِ ۱ سپتامبر: محافظِ بمب‌ساعتی ─────────────────────────────
#
# `test_strategy_priority` شرط گذاشته بود سررسیدِ ترجیح **در آینده** باشد
# و ترجیح **فعال** باشد. ترجیح دقیقاً طبق طراحی ساعت ۲۰:۲۹ UTC سررسید شد
# → محافظ قرمز → دروازهٔ سختِ زنجیره → حلقهٔ ۵دقیقه‌ای skip → latest،
# funnel، system-state و loop-audit کهنه ماندند. یک محافظ، تولید را
# خواباند، بی‌آنکه هیچ کدی خراب شده باشد.
#
# قاعده: هر محافظی که روی وضعیتِ **منقضی‌شونده** حکم می‌دهد باید شاخهٔ
# «سررسیده» را هم سالم بداند. تشخیصش عینی است: فایلی که هم `until` دارد
# هم با `now` مقایسه می‌کند، باید کلمهٔ `expired` را هم داشته باشد —
# یعنی هر دو شاخه را پوشانده باشد.
_gate_dir = Path(__file__).resolve().parent
_bombs = []
for _t in sorted(_gate_dir.glob("test_*.py")):
    _txt = _t.read_text(encoding="utf-8", errors="ignore")
    if '"until"' in _txt and "now" in _txt and "expired" not in _txt:
        _bombs.append(_t.name)
check(f"هیچ محافظی وضعیتِ منقضی‌شونده را «باید فعال باشد» فرض نمی‌کند "
      f"{_bombs or ''}", not _bombs)

# و خودِ فایلِ ترجیح باید سررسید داشته باشد — ترجیحِ ابدی همان چیزی است
# که این محافظ‌ها اصلاً برایش گذاشته شدند.
import json as _json
_pref_p = _gate_dir.parent.parent.parent / "config" / "strategy_priority.json"
try:
    _pref = _json.loads(_pref_p.read_text(encoding="utf-8"))
    check("ترجیح استراتژی سررسید عددی دارد (ابدی نیست)",
          isinstance(_pref.get("until"), (int, float)))
except FileNotFoundError:
    check("ترجیح استراتژی سررسید عددی دارد (ابدی نیست)", True,
          "فایل ترجیح وجود ندارد — یعنی ترجیحی هم نیست")

# ── کلاسِ عیبِ ۱ سپتامبر (دوم): حلقهٔ پوشِ خودکش ───────────────────────
#
# چرخهٔ حمید ۲۶ گام را سبز تمام می‌کرد و بعد گامِ «Publish to main» در
# ۳ ثانیه با exit 128 می‌مرد. لاگ اجرای ۳۲۰:
#     ! [rejected] HEAD -> main (non-fast-forward)
#     fatal: refusing to merge unrelated histories
#     fatal: There is no merge to abort (MERGE_HEAD missing)
# یعنی: پوش رد شد (عادی) → merge با «تاریخچهٔ نامرتبط» نخورد (این ریپو
# واقعاً دو ریشه دارد) → پس هیچ merge ای در جریان نبود → `git merge
# --abort` خطای کشنده داد → و زیر `bash -e` کلِ گام مرد. حلقهٔ ۸تایی
# **هرگز دور دوم را ندید**. نتیجه: چرخه کار می‌کرد ولی هرگز منتشر
# نمی‌شد، و همهٔ فایل‌هایش ساعت‌ها کهنه می‌ماندند.
#
# دو ناوردا که این را ناممکن می‌کنند:
_loop_bad_abort, _loop_no_allow = [], []
for _w in sorted(WF.glob("*.yml")):
    _t = _w.read_text(encoding="utf-8")
    if "resolve_brain_conflicts" not in _t:
        continue
    if "git merge --abort; exit 1" in _t or "git merge --abort;exit 1" in _t:
        _loop_bad_abort.append(_w.name)
    if re.search(r'git merge --no-edit (?!--allow)["\']?origin', _t):
        _loop_no_allow.append(_w.name)

check(f"هیچ حلقهٔ پوشی با پاک‌سازیِ کشنده نمی‌میرد {_loop_bad_abort or ''}",
      not _loop_bad_abort)
check(f"هر merge با origin تاریخچهٔ نامرتبط را می‌پذیرد (ریپو دو ریشه دارد) "
      f"{_loop_no_allow or ''}", not _loop_no_allow)

# ── حالت شنی: هیچ گامِ آزمونی حق نوشتن روی دفترِ تولید ندارد (۴ سپتامبر)
#
# ریشه: اجرای کاملِ دروازه چهار فایلِ runtime را عوض کرد — `test_loop_audit`
# مسیرهای paper.OPEN/CLOSED را به پوشهٔ موقت می‌برد، ولی `_append_gatelog`
# و `brain.room_log` مسیرِ ثابتِ خودشان را داشتند و از آن تغییرِ مسیر در
# می‌رفتند؛ بعد ناشرِ زنجیره همان آلودگی را روی main می‌نشاند. درمانش
# سوییچ مرکزی `LIAM9_SANDBOX` است، و این بررسی نگه‌داشتنش را اجباری
# می‌کند: گامِ آزمونیِ تازه‌ای که آن را نگذارد، چرخه را سرخ می‌کند.
_GATE_NAMES = ("آزمون آفلاین", "خودآزمایی", "Method self-check")
_no_sandbox = []
for _w in sorted(WF.glob("*.yml")):
    _lines = _w.read_text(encoding="utf-8").splitlines()
    for _i, _ln in enumerate(_lines):
        _m = re.match(r"^(\s*)- name: (.*)$", _ln)
        if not (_m and any(n in _m.group(2) for n in _GATE_NAMES)):
            continue
        _ind = _m.group(1)
        _body = []
        _j = _i + 1
        while _j < len(_lines) and (not _lines[_j].strip()
                                    or _lines[_j].startswith(_ind + "  ")):
            _body.append(_lines[_j]); _j += 1
        if "LIAM9_SANDBOX" not in "\n".join(_body):
            _no_sandbox.append(f"{_w.name}:{_m.group(2).strip()}")

check(f"هر گام آزمون با LIAM9_SANDBOX=1 می‌دود — پاسبان دفترِ تولید را "
      f"نمی‌نویسد {_no_sandbox or ''}", not _no_sandbox)

_brain = (PY / "brain.py").read_text(encoding="utf-8") if (PY / "brain.py").exists() else ""
check("حالت شنی در brain.py تعریف شده", 'SANDBOX = os.environ.get("LIAM9_SANDBOX")' in _brain)
check("و نویسنده‌های brain در حالت شنی ساکت‌اند",
      _brain.count("if SANDBOX:") >= 4)
_paper = (PY / "hamid" / "paper.py").read_text(encoding="utf-8")
check("دفترِ دروازهٔ دوام هم حالت شنی را رعایت می‌کند",
      'getattr(_b, "SANDBOX", False)' in _paper)

print()
if fail:
    print(f"✗ {len(fail)} آزمون شکست: {fail}")
    raise SystemExit(1)
print(f"✓ همهٔ {ok} آزمون سلامت ورک‌فلو گذشت ({len(files)} فایل)")
