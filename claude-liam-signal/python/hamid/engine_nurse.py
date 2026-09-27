#!/usr/bin/env python3
"""پرستار انجین‌ها — درمانِ همیشگیِ قطعِ اتصالِ انجین به پنل (دستور حمید، ۲۵ سپتامبر).

حمید: «اول برای برطرف کردنش راه حل همیشگی پیدا کن، و برطرفش کن و باید به
کل مجموعه متصل باشه» + «من برای دونه به دونه انجین‌ها وظایف تعریف کردم و
قابلیت کسب تجربه و مهارت هم داشته باشند.»

## عیبی که این ماژول با آن متولد شد — پنج قطعیِ مستندِ گذشته

هر پنج تای پرتکرار (مدیک ۹۳د، اسکلپ ۱۳ ساعت، live-scan خفه‌شده،
dominance قحطی‌زده، btc-sensitivity خاموش) یک الگوی مشترک داشتند:
  گذرگاه وضعیت (قانون ۱۳) عیب را **می‌دید** ولی درمانش **دستی** بود —
  و دستِ آدم همیشه سرِ جایش نیست. مدیک فقط دو خط زنده را می‌پاید
  (hamid-latest، latest)؛ بقیهٔ ۱۰۰+ فایل قراردادِ حالتی از درمان
  نداشتند. پرستار همان قاعدهٔ مدیک را برای **همهٔ مالک‌ها** تعمیم می‌دهد:
  معاینه از گذرگاه وضعیت، تشخیصِ مالکِ کهنه، و بیدارکردنِ خطِ تولیدِ همان
  مالک با dispatch ورک‌فلوی خودش.

## سازوکار — چهار دروازه، تا پرستار خودش عیب نسازد

۱. **سن از مهرِ فایل** (`state_bus._age_min`): همان منطق قانون ۱۳، نه
   mtime (درس ۲۵ اوت: mtime روی رانر پس از checkout همیشه «همین الان» است
   و حکمِ دروغ می‌سازد).
۲. **فقط خطِ دارای بیدارسازی** — فایلی که تولیدکننده‌اش زنجیرهٔ مشترک
   یا کادنسِ سنگین است (اسکن ۲۰۰تایی، بک‌تست شبانه، تمرین) فقط
   **گزارش** می‌شود؛ درمانِ مستقیمِ آن‌ها همان کلاسی است که در ۲۳ اوت
   ۵۵۰ اجرای قرمز و پنلِ خوابیده ساخت (کرش‌لوپ).
۳. **پادزهر ردگیری، دو لایه**: حافظهٔ درون-فرایندی (چون زنجیره در هر دور
   `git reset --hard origin/main` می‌کند و فایلِ مهرِ این job را می‌بَرد)
   + فایلِ `signals/nurse.json` (بین jobها). هر ورک‌فلو در پنجرهٔ خودش
   حداکثر یک بار بیدار می‌شود.
۴. **چکِ خواب‌بودنِ خط** پیش از dispatch — مثل مدیک: dispatch روی خطِ
   در حال اجرا «cancelled» قرمز در اینباکس حمید می‌کاشت (۴ تا در ۷۵ دقیقه).

## تجربه (دستور حمید) — هر انجین، با تکرار، قوی‌تر

· هر درمان موفق با `skill_ledger.learn` ثبت می‌شود: واحد «E23-پرستار»،
  مهارت «بیدارسازیِ <workflow> برای <owner>». تکرارِ همان درمان ضریبِ
  همان مهارت را بالا می‌برد (بازده نزولیِ خودِ دفتر) — انجینی که مدام
  به درمان نیاز دارد در `signals/skills.json` خودش را لو می‌دهد و
  عیبِ ساختاری‌اش (کادنس، نویسندهٔ گم‌شده) قابل درست‌کردن می‌شود.
· **تولیدِ تازهٔ هر انجین** هم یک تجربهٔ مثبت با واحدِ خودِ انجین
  می‌گیرد (E03، E08…) — دفتر مهارت سلامتِ معمول را هم ثبت کند، نه فقط
  مریضی را. وزنِ تجربهٔ هر انجین با ردیف «تولیدِ تازه» همان انجین
  انباشته می‌شود و کارنامه‌اش در پنل دیده می‌شود.
· پرستار فقط تشخیص می‌دهد و ثبت؛ **هیچ دروازه‌ای را عوض نمی‌کند** —
  ورودِ تجربه به تصمیم فقط از مسیر قانون ۰۳.

## مرزها (قانون ۰۵/۱۲)

· فقط فایلِ وضعیتِ خودش (`signals/nurse.json`) را می‌نویسد.
· هیچ فایل سیگنالی را بازنویسی نمی‌کند؛ هیچ پیام تلگرامی نمی‌فرستد —
  گزارشش پنل (کارت System Health) و گذرگاه وضعیت است (قانون ۱۱ بند ۳).
· درمان = dispatch ورک‌فلوی موجود، نه اجرای مستقیم تولیدکننده — اجرای
  مستقیم روی چک‌اوتِ محلی همان «حکمِ دروغ» درسِ ۲۹ اوت است.
· بدون GITHUB_TOKEN/REVIVE فقط گزارش می‌دهد و اثر را صادقانه
  `treatment_disabled` می‌نویسد — مدعی درمان نمی‌شود.

اجرا:
    python3 -m hamid.engine_nurse --write        # معاینه + درمان (زنجیره/چرخه)
    python3 -m hamid.engine_nurse --force --write  # نوشتن محلی برای بازرسی
    python3 -m hamid.engine_nurse --selftest     # آزمون آفلاین
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

OUT = ROOT / "signals" / "nurse.json"
REPO = "AuraLiam/Liam-Trader-9"
ENGINE = "E23"                    # ناظر و SRE — مالک این دامنهٔ وضعیت
UNIT = "E23-پرستار"               # واحدِ تجربهٔ درمان در دفتر مهارت

# ── خط بیدارسازی هر مالکِ کهنه ────────────────────────────────────────────
# مأموریتِ هر انجین در رجیستری ثبت است (config/engine_registry.yaml)؛
# این‌جا فقط پاسخِ «کهنه شد، چه خطی او را تازه می‌کند» تعریف می‌شود.
WAKE = {
    "E03": "dominance.yml",        # dominance.json / dominance-desk / report
    "E04": "dominance.yml",
    "E05": "news-hunt.yml",        # macro-guard / market-stance
    "E06": "hamid-cycle.yml",      # btc-patterns سوار چرخه
    "E08": "ob-lab.yml",           # ob-radar
    "E10": "hamid-cycle.yml",      # top-liquidity (publish در چرخه)
    "E11": "scalp.yml",            # scalp / scalp-exec
    "E12": "pump-review.yml",      # پامپ ۵ نوبت روزانه (قانون ۰۷)
    "E13": "hamid-cycle.yml",      # history-room
    "E14": "news-hunt.yml",        # news / news-poll / newsboard
    "E15": "hamid-cycle.yml",      # fomo
    "E16": "hamid-cycle.yml",      # viability-gate
    "E17": "hamid-cycle.yml",      # hamid-latest (چرخهٔ کامل)
    "E18": None,                   # بک‌تست شبانه — کادنسِ خودش را دارد
    "E19": "hamid-cycle.yml",      # position-watch / trail-alert
    "E20": "hamid-cycle.yml",      # loss-analysis / direction-lessons
    "E21": "hamid-cycle.yml",      # حافظه/مهارت/اثبات یادگیری
    "E22": "hamid-cycle.yml",      # کارنامه‌ها / edge / bandit
    "E23": "medic.yml",            # خودِ پاسبان سلامت
    "E25": "hamid-cycle.yml",      # تحویل و دفترهای تلگرام
    "E26": "hamid-cycle.yml",      # overseer
    "E27": "hamid-cycle.yml",      # router
    "E00": None,                   # ارکستراتور — خروجی‌هایش همه زنجیره‌سوارند
}

# مالک‌های بدون فایل زندهٔ مستقل (خروجی‌شان داخل فایل دیگر می‌نشیند) —
# قرارداد تازگی جداگانه‌ای ندارند؛ گزارشِ گذرگاه برایشان کافی است.
NO_LIVE_FILES = {"E01", "E02", "E07", "E09", "E24"}

# پادزهرِ بیدارسازی (دقیقه) — از سقف کهنگیِ فایل‌های همان خط مشتق است
WAKE_COOLDOWN_MIN = {
    "default": 60,
    "medic.yml": 20,               # سقفِ فایل‌های E23 پایین است (۱۵–۴۵د)
    "dominance.yml": 45,           # سقف dominance.json = ۴۵د
    "hamid-cycle.yml": 30,         # چرخه هر ~۳۰د خودش می‌آید
    "scalp.yml": 90,
    "news-hunt.yml": 90,
    "pump-review.yml": 120,        # ۵ نوبت روزانه = هر ~۵ ساعت
    "ob-lab.yml": 90,
}

# حافظهٔ درون-فرایندی — زنجیره هر دور reset می‌کند؛ مهرِ این job این‌جا می‌ماند
_PROC_WAKES: dict[str, dict] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _load(path: Path, default):
    try:
        j = json.loads(path.read_text(encoding="utf-8"))
        return j if isinstance(j, dict) else default
    except Exception:                                 # noqa: BLE001
        return default


def _state() -> dict:
    """خروجی گذرگاه وضعیت؛ اگر هنوز منتشر نشده بود، همین‌جا سنجیده می‌شود."""
    from hamid import state_bus as SB
    j = _load(ROOT / "signals" / "system-state.json", None)
    if j and j.get("rows"):
        return j
    try:
        return SB.scan()
    except Exception:                                 # noqa: BLE001
        return {"rows": [], "faults": []}


# ── درمان: dispatch با همان محافظِ مدیک ───────────────────────────────────
def _runs(workflow: str, tok: str, status: str) -> int:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}"
        f"/runs?status={status}&per_page=5",
        headers={"Authorization": f"Bearer {tok}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "engine-nurse/1"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return len(json.load(r).get("workflow_runs") or [])


def _dispatch(workflow: str, tok: str) -> tuple[bool, str]:
    """dispatch فقط وقتی خط واقعاً خواب است. بازگشت: (اجرا شد؟، پیام)."""
    try:
        if _runs(workflow, tok, "in_progress") > 0:
            return False, "همین حالا در حال اجراست — دست نمی‌زنم"
        if _runs(workflow, tok, "queued") > 0:
            return False, "در صف است — dispatch لازم نیست"
    except Exception as e:                            # noqa: BLE001 - چک ناموفق مانع درمان نمی‌شود
        return False, f"چکِ وضعیت اجرا ناموفق: {type(e).__name__}"
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/dispatches",
        data=json.dumps({"ref": "main"}).encode(),
        headers={"Authorization": f"Bearer {tok}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "engine-nurse/1"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status in (200, 204), f"dispatch شد (HTTP {r.status})"
    except Exception as e:                            # noqa: BLE001 - متن خطا خودش گزارش است
        return False, f"dispatch شکست خورد: {type(e).__name__}"


# ── تجربه: ثبت در دفتر مهارت، با احترام به محافظ شنی ──────────────────────
def _ledger_paths() -> tuple[Path, Path]:
    """در حالت شنی دفترِ آزمایشی — برندهٔ هرگز واقعی نمی‌نویسد (محافظ brain)."""
    from hamid import skill_ledger as SL
    import brain as _b
    if _b.blocked(SL.LEDGER):
        return SL.BRAIN / "ledger.sandbox.json", SL.BRAIN / "events.sandbox.jsonl"
    return SL.LEDGER, SL.EVENTS


def _learn(unit: str, skill: str, evidence: str) -> None:
    """یک تجربه در دفتر مهارت. تکرارِ همان (واحد، مهارت) ضریبش را بالا می‌برد.

    تجربه هیچ‌وقت درمان را نمی‌کشد — شکستش فقط گزارش می‌شود (قانون ۱۲)."""
    try:
        from hamid import skill_ledger as SL
        ledger, events = _ledger_paths()
        SL.learn(unit, skill, scope="engine-nurse", evidence=evidence,
                 path=ledger, events=events)
    except Exception as e:                            # noqa: BLE001
        print(f"تجربه: {type(e).__name__}: {e}")


def _learn_production(fresh_rows: list) -> int:
    """تجربهٔ سلامتِ معمول: تولیدِ تازهٔ هر انجین به نام خودش ثبت می‌شود."""
    by_owner: dict[str, list] = {}
    for r in fresh_rows:
        if r.get("owner"):
            by_owner.setdefault(r["owner"], []).append(r["file"])
    n = 0
    for owner in sorted(by_owner):
        files = ", ".join(sorted(by_owner[owner])[:3])
        _learn(owner, "تولیدِ تازه",
               f"{files} داخل قرارداد کهنگی‌شان — مأموریتِ ثبت‌شده انجام شد")
        n += 1
    return n


def _structural_repeats() -> list:
    """مالک‌هایی که تجربهٔ «بیدارسازیِ» ثبت‌شده‌شان بالا رفته = عیبِ کادنس."""
    try:
        from hamid import skill_ledger as SL
        ledger, _ = _ledger_paths()
        out = []
        for row in (SL._load(ledger).get("skills") or {}).values():
            if row.get("unit") == UNIT and str(row.get("skill", "")).startswith("بیدارسازی"):
                if row.get("times", 0) >= 3:
                    out.append({"skill": row["skill"], "times": row["times"],
                                "weight": row.get("weight")})
        out.sort(key=lambda r: -r["times"])
        return out[:6]
    except Exception:                                 # noqa: BLE001
        return []


# ── معاینه + درمان ────────────────────────────────────────────────────────
def examine(write: bool = False) -> dict:
    from hamid import state_bus as SB
    st = _state()
    rows = st.get("rows") or []
    stale: dict[str, list] = {}
    for r in rows:
        if r.get("status") in ("stale", "missing") and r.get("owner"):
            stale.setdefault(r["owner"], []).append(r)

    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    can_treat = bool(tok) and os.environ.get("REVIVE") == "1"

    actions, wakes = [], {}
    for owner in sorted(stale):
        bad = stale[owner]
        oldest = max(bad, key=lambda r: r.get("age_min") or 0)
        names = ", ".join(r["file"] for r in bad[:4])
        wf = WAKE.get(owner)
        if owner in NO_LIVE_FILES:
            continue
        if wf is None:
            actions.append({
                "owner": owner, "files": names,
                "age_min": oldest.get("age_min"), "cap": oldest.get("max_age_min"),
                "verdict": "monitor_only",
                "note": ("کادنسِ خودش را دارد (بک‌تست شبانه/ارکستراتور) — "
                         "درمانِ dispatch بی‌حساب، کلاسِ کرش‌لوپِ ۲۳ اوت است")})
            continue
        # پادزهر، لایهٔ ۱: این فرایند (درونِ یک job که reset می‌کند)
        prev = _PROC_WAKES.get(wf)
        src = "memory"
        if prev is None:
            # پادزهر، لایهٔ ۲: مهرِ job قبلی از nurse.json
            last = (_load(OUT, {}) or {}).get("wakes", {}).get(wf) or {}
            if last.get("t"):
                prev, src = last, "file"
        cd = WAKE_COOLDOWN_MIN.get(wf, WAKE_COOLDOWN_MIN["default"])
        since = None
        if prev and prev.get("t"):
            since = round((time.time() * 1000 - prev["t"]) / 60000, 1)
        if since is not None and since < cd:
            actions.append({
                "owner": owner, "files": names, "workflow": wf,
                "verdict": "cooldown",
                "note": f"بیدارسازی قبلی {since:.0f}د پیش ({src}) — "
                        f"پادزهر {cd}د؛ اجرای تازهٔ خط در راه است"})
            continue
        if not can_treat:
            actions.append({
                "owner": owner, "files": names, "workflow": wf,
                "verdict": "treatment_disabled",
                "note": "پرستار توان بیدارسازی ندارد (REVIVE=1 + GITHUB_TOKEN)"})
            continue
        ok, msg = _dispatch(wf, tok)
        if ok:
            _PROC_WAKES[wf] = {"t": _now_ms(), "for_owner": owner,
                               "for_files": names, "age_min": oldest.get("age_min")}
            wakes[wf] = _PROC_WAKES[wf]
            _learn(UNIT, f"بیدارسازیِ {wf} برای {owner}",
                   f"{names} کهنه ({oldest.get('age_min'):.0f}د > "
                   f"{oldest.get('max_age_min')}د سقف) — {msg}")
        actions.append({
            "owner": owner, "files": names, "workflow": wf,
            "verdict": "woken" if ok else "wake_failed",
            "note": msg})

    # تجربهٔ سلامتِ معمول — فقط وقتی نتیجه منتشر می‌شود، نه هر معاینهٔ محلی
    n_prod = 0
    if write:
        fresh = [r for r in rows if r.get("status") in ("ok", "absent_ok")]
        n_prod = _learn_production(fresh)

    doc = {
        "generated": _now_ms(),
        "owner": ENGINE,
        "producer": "hamid/engine_nurse.py",
        "verdict": ("TREATED" if any(a["verdict"] == "woken" for a in actions)
                    else "MONITORED" if actions else "HEALTHY"),
        "n_stale_owners": len(stale),
        "n_actions": len(actions),
        "n_woken": sum(1 for a in actions if a["verdict"] == "woken"),
        "n_experiences": n_prod,
        "treatment_enabled": can_treat,
        "actions": actions,
        "wakes": wakes,
        "structural": _structural_repeats(),
        "packet": SB.packet(st) if rows else None,
        "policy": ("چهار دروازه: سن از مهرِ فایل · فقط خطِ دارای بیدارسازی · "
                   "پادزهر دو لایه (حافظه + مهر فایل) · چکِ خواب‌بودن پیش از dispatch. "
                   "فایل‌های زنجیره‌سوار فقط گزارش می‌شوند؛ درمانِ مستقیمشان "
                   "کلاسِ کرش‌لوپ ۲۳ اوت (۵۵۰ اجرای قرمز) است."),
    }
    if write and (os.environ.get("GITHUB_ACTIONS") == "true" or "--force" in sys.argv):
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


def main(argv):
    if "--selftest" in argv:
        return selftest()
    doc = examine(write="--write" in argv)
    print(f"پرستار: {doc['verdict']} — {doc['n_stale_owners']} مالکِ کهنه، "
          f"{doc['n_woken']} بیدار شد، تجربهٔ سلامت: {doc['n_experiences']}، "
          f"درمان {'فعال' if doc['treatment_enabled'] else 'غیرفعال'}")
    for a in doc["actions"][:14]:
        print(f"  · {a['owner']} {(a['files'] or '')[:60]} → {a['verdict']} ({a['note'][:70]})")
    return 0


def selftest():
    OK = 0
    FAIL = []

    def check(name, cond, extra=""):
        nonlocal OK
        if cond:
            OK += 1
            print(f"  ✓ {name}")
        else:
            FAIL.append(name)
            print(f"  ✗ {name}")
            if extra:
                print(f"      ↳ {extra}")

    print("پرستار انجین‌ها — آزمون آفلاین")
    # ۱. هر ورک‌فلوی خط بیدارسازی واقعاً در ریپو هست — dispatchِ خطِ ناموجود
    #    یعنی درمانی که هرگز نمی‌رسد (همان کلاسِ «مدعی درمان»).
    for owner, wf in sorted(WAKE.items()):
        if wf:
            check(f"خطِ {owner} → {wf} وجود دارد",
                  (ROOT / ".github" / "workflows" / wf).exists())
    # ۲. هر مالکِ رجیستری پوشش دارد: خطِ درمان، یا ردِ مستند
    from hamid import state_bus as SB
    owners = {s["owner"] for s in SB.registry()["files"].values() if s.get("owner")}
    uncovered = {o for o in owners if o not in WAKE and o not in NO_LIVE_FILES}
    check("همهٔ مالک‌ها پوشیده‌اند", not uncovered, f"بی‌پوشش: {sorted(uncovered)}")
    # ۳. پادزهرها در محدودهٔ سالم — نه صفر (اسپم dispatch) نه ساعت‌ها (درمانِ دیر)
    for wf, cd in WAKE_COOLDOWN_MIN.items():
        check(f"پادزهرِ {wf} = {cd}د سالم", 10 <= cd <= 240)
    # ۴. پرستار خودش بیرون از قانون ۱۳ نماند — فایلش در قرارداد ثبت است
    check("nurse.json در قرارداد وضعیت ثبت است",
          "nurse.json" in SB.registry()["files"])
    # ۵. شنی: دفترِ واقعی بسته می‌شود و تجربه به دفتر آزمایشی می‌رود
    import brain as _b
    from hamid import skill_ledger as SL
    if _SANDBOX:
        check("محافظ شنی دفتر واقعی را می‌بندد", _b.blocked(SL.LEDGER))
        _learn("__آزمون__", "آزمونِ شنی", "رد شدن از مسیر آزمایشی")
        check("دفتر واقعی در شنی دست‌نخورده ماند", not SL.LEDGER.exists()
              or "__آزمون__" not in SL.LEDGER.read_text(encoding="utf-8"))
    else:
        check("محافظ شنی در حالت عادی بی‌اثر است", not _b.blocked(SL.LEDGER))
    print(f"\n{OK} بررسی درست، {len(FAIL)} غلط")
    return 1 if FAIL else 0


_SANDBOX = os.environ.get("LIAM9_SANDBOX") == "1"

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
