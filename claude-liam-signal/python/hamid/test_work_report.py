"""پاسبان گزارش کار — همراه اجباری work_report.py. آفلاین.

خطر یک گزارشِ خودکار این است که **قانع‌کننده به‌نظر برسد**. پس بیشترِ
بررسی‌های این‌جا روی جلوگیری از همان‌اند: دفترِ آزمایشی نباید در سرخط
بیاید، تایم‌فریمِ کم‌نمونه نباید «بهترین» شود، پوششِ ناقص باید صریح چاپ
شود، و اثرِ تجربه بدون بازهٔ اطمینان نباید حکم بگیرد.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
from hamid import work_report as W                  # noqa: E402

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


NOW = 1_700_000_000_000
H = 3600_000


def row(r, stage="sig-ibs", tf="15m", outcome=None, closed=NOW - H,
        mfe=None, **kw):
    d = {"sym": "X", "R": r, "closed": closed, "tf": tf,
         "outcome": outcome or ("target" if r > 0 else "stop"),
         "why": {"stage": stage}}
    if mfe is not None:
        d["mfe_r"] = mfe
    d.update(kw)
    return d


def build(rows, **kw):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "closed.jsonl"
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
                     + "\n", encoding="utf-8")
        kw.setdefault("now_ms", NOW)
        kw.setdefault("since_ms", NOW - 24 * H)
        return W.build(path=str(p), **kw)


print("— دفترها قاطی نمی‌شوند:")
rep = build([row(1.0)] * 5 + [row(5.0, stage="vetoed")] * 50
            + [row(5.0, stage="inducement")] * 50)
check("سرخط فقط سیگنالِ ارسال‌شده است", rep["headline"]["n"] == 5,
      str(rep["headline"]["n"]))
check("دفتر وتوشده (ضدواقع) در «دفترهای عملکردی» شمرده نمی‌شود",
      rep["all_live_books"]["n"] == 5, str(rep["all_live_books"]["n"]))
stages = {b["stage"]: b for b in rep["per_book"]}
check("ولی حذف هم نمی‌شود — با برچسبِ غیرعملکردی می‌آید",
      stages["vetoed"]["n"] == 50 and stages["vetoed"]["is_performance"] is False)
check("دفتر آزمایشی ایندوسمنت هم همین‌طور",
      stages["inducement"]["is_performance"] is False)
check("اسکلپ و شوک عملکردی‌اند (فرضیهٔ آزمایشی نیستند)",
      build([row(1.0, stage="scalp"), row(-1.0, stage="shock")]
            )["all_live_books"]["n"] == 2)
check("دفتر ناشناخته پنهان نمی‌شود، زیر «سایر» می‌آید",
      any(b["stage"] == "zzz" for b in
          build([row(1.0, stage="zzz")] * 3)["per_book"]))

print("\n— تایم‌فریم: نمونهٔ کم حق «بهترین» بودن ندارد:")
rep = build([row(9.0, tf="1m")] * 3 + [row(0.2, tf="15m")] * 40)
check("تایم ۳نمونه‌ای با انتظار ۹R «بهترین» اعلام نمی‌شود",
      rep["timeframe"]["best"] == "15m", str(rep["timeframe"]["best"]))
check("ولی عددش چاپ می‌شود (پنهان نمی‌شود)",
      any(t["label"] == "1m" for t in rep["timeframe"]["rows"]))
check("وقتی هیچ تایمی نمونهٔ کافی ندارد، «بهترین» خالی می‌ماند",
      build([row(1.0, tf="1m")] * 3)["timeframe"]["best"] is None)

print("\n— پوششِ ناقص صریح گزارش می‌شود (عیبِ ۲۴ اوت):")
rep = build([row(1.0, tf=None)] * 8 + [row(1.0, tf="5m")] * 2)
check("پوشش درصدی حساب و چاپ می‌شود",
      rep["timeframe"]["coverage_pct"] == 20.0,
      str(rep["timeframe"]["coverage_pct"]))
check("ردیف‌های بی‌تایم زیر «نامشخص» می‌آیند، نه حذف",
      any(t["label"] == "نامشخص" and t["n"] == 8
          for t in rep["timeframe"]["rows"]))
# محافظِ اصلی: دفتر سیگنال باید tf بنویسد، وگرنه این پرسش برای همیشه کور است
paper_src = (PY / "hamid" / "paper.py").read_text(encoding="utf-8")
check("دفتر سیگنال (paper.open_from) تایم‌فریم را ثبت می‌کند",
      '"tf": s.get("tf")' in paper_src)

print("\n— استاپ و تارگت:")
rep = build([row(-1.0, outcome="stop", mfe=0.8) for _ in range(10)]
            + [row(2.0, outcome="target", mfe=2.1) for _ in range(5)])
st = rep["stops_targets"]
check("استاپ/تارگت/تریل جدا شمرده می‌شوند",
      (st["stop"], st["target"]) == (10, 5), str(st))
check("«در سود بود و استاپ خورد» شمرده می‌شود",
      st["in_profit_stopped"] == 10 and st["in_profit_stopped_pct"] == 100.0)
check("و وقتی زیاد شد، هشدارِ مشخص می‌دهد (نه سکوت)",
      any("تریل دیر مسلح" in h for h in st["hints"]), str(st["hints"]))
clean = build([row(-1.0, outcome="stop", mfe=-0.1) for _ in range(10)]
              )["stops_targets"]
check("استاپی که هرگز در سود نبوده، آن هشدار را نمی‌گیرد",
      clean["in_profit_stopped"] == 0
      and not any("تریل دیر" in h for h in clean["hints"]))

print("\n— پنجرهٔ زمانی واقعاً می‌بُرد:")
rep = build([row(1.0, closed=NOW - 2 * H), row(1.0, closed=NOW - 100 * H)])
check("ردیف بیرونِ پنجره شمرده نمی‌شود", rep["headline"]["n"] == 1)
check("پنجره روی خروجی نوشته می‌شود (قابل بازتولید)",
      rep["window"]["hours"] == 24.0 and "UTC" in rep["window"]["since"])
check("ردیف بی‌نمره (R=None) وارد آمار نمی‌شود",
      build([row(1.0), {"R": None, "closed": NOW - H,
                        "why": {"stage": "sig-ibs"}}])["headline"]["n"] == 1)
check("خط خرابِ دفتر گزارش را نمی‌کشد",
      build([row(1.0)])["headline"]["n"] == 1)

print("\n— مرزهای صادقانه روی خودِ خروجی:")
rep = build([row(1.0)] * 10)
check("مرز «پیپر سقف خوش‌بینانه است» روی گزارش هست",
      "خوش‌بینانه" in rep["boundary"])
check("و «هر ادعای اثر فقط با CI» هم", "CI" in rep["boundary"])
check("جایزهٔ انجین صریح می‌گوید علّی نیست",
      (not rep["rewards"].get("available"))
      or "علّی نیست" in rep["rewards"]["note"])
src = (PY / "hamid" / "work_report.py").read_text(encoding="utf-8")
check("اثر تجربه از ماژول خودش می‌آید، نه حسابِ دوبارهٔ این‌جا",
      "experience_effect" in src and "boot_diff" not in src)

print("\n— متن فارسیِ خلاصه:")
t = W.text(rep)
for want in ("گزارش کار", "سیگنالِ ارسال‌شده", "تایم‌فریم", "استاپ و تارگت"):
    check(f"خلاصه بخش «{want}» را دارد", want in t)
check("پنجرهٔ خالی هم متنِ سالم می‌دهد، نه خطا",
      "هیچ معامله‌ای" in W.text(build([])))

print("\n— ناشرِ ورک‌فلو هیچ خروجی‌ای را دور نمی‌ریزد (درس ۲ سپتامبر):")
# چه شد: گامِ «ثبت گزارش» بعد از reset فقط دو فایل را برمی‌گرداند
# (work-report، engine-focus). curriculum.json و trail-arms.json که
# گام‌های دیگرِ همین ورک‌فلو می‌نوشتند هر بار دور ریخته می‌شدند؛ سه
# اجرای سبزِ ۱ سپتامبر هیچ‌کدام را منتشر نکرد و گذرگاه وضعیت آن‌ها را ۳۱
# ساعت کهنه دید. این آزمون **خودِ اسکریپتِ گام** را از yml می‌خواند و در
# یک مخزن موقت با origin واقعی اجرا می‌کند — نه متنِ آن را می‌گردد.
import os                                            # noqa: E402
import shutil                                        # noqa: E402
import subprocess                                    # noqa: E402

import yaml                                          # noqa: E402

ROOT = PY.parents[1]
_wf = yaml.safe_load((ROOT / ".github/workflows/work-report.yml")
                     .read_text(encoding="utf-8"))
_steps = _wf["jobs"]["report"]["steps"]
_pub = next((s for s in _steps if "ثبت گزارش" in str(s.get("name"))), None)
check("گامِ ناشر پیدا شد", _pub is not None)


def _git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)


def _publish_scenario(script):
    """origin + کلون؛ چهار فایل signals/ عوض می‌شود، origin هم جلو می‌رود."""
    td = Path(tempfile.mkdtemp(prefix="wr-pub-"))
    origin = td / "origin.git"
    _git("init", "-q", "--bare", "-b", "main", str(origin), cwd=td)
    work = td / "work"
    _git("clone", "-q", str(origin), str(work), cwd=td)
    _git("config", "user.email", "t@t", cwd=work)
    _git("config", "user.name", "t", cwd=work)
    # گام ناشر حالا اسکریپت مشترک را صدا می‌زند؛ همان را داخل مخزن موقت
    # می‌گذاریم تا اسکریپتِ گام دقیقاً همان‌طور که روی رانر است اجرا شود.
    (work / "scripts").mkdir()
    for s in ("publish.sh", "resolve_brain_conflicts.py"):
        shutil.copy(ROOT / "scripts" / s, work / "scripts" / s)
    (work / "signals").mkdir()
    for f in ("work-report.json", "engine-focus.json", "curriculum.json",
              "trail-arms.json", "other.json"):
        (work / "signals" / f).write_text('{"v": 0}')
    _git("add", "-A", cwd=work)
    _git("commit", "-qm", "base", cwd=work)
    _git("push", "-q", "origin", "HEAD:main", cwd=work)
    # origin جلو می‌رود (اجرای دیگری فایل دیگری را عوض کرده)
    other = td / "other"
    _git("clone", "-q", str(origin), str(other), cwd=td)
    _git("config", "user.email", "o@o", cwd=other)
    _git("config", "user.name", "o", cwd=other)
    (other / "signals" / "other.json").write_text('{"v": 7}')
    _git("commit", "-qam", "elsewhere", cwd=other)
    _git("push", "-q", "origin", "HEAD:main", cwd=other)
    # همین اجرا: چهار فایل می‌نویسد (یکی تازه)
    for f in ("work-report.json", "engine-focus.json", "curriculum.json",
              "trail-arms.json"):
        (work / "signals" / f).write_text('{"v": 1}')
    (work / "signals" / "brand-new.json").write_text('{"v": 1}')
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    r = subprocess.run(["bash", "-e", "-c", script], cwd=work, env=env,
                       capture_output=True, text=True)
    got = {}
    for f in ("work-report.json", "engine-focus.json", "curriculum.json",
              "trail-arms.json", "brand-new.json", "other.json"):
        _git("fetch", "-q", "origin", "main", cwd=work)
        s = _git("show", f"origin/main:signals/{f}", cwd=work)
        got[f] = json.loads(s.stdout)["v"] if s.returncode == 0 else None
    shutil.rmtree(td, ignore_errors=True)
    return r, got


if _pub is not None:
    _r, _got = _publish_scenario(_pub["run"])
    check("اسکریپت ناشر بدون خطا تمام می‌شود", _r.returncode == 0,
          (_r.stdout + _r.stderr)[-400:])
    for f in ("work-report.json", "engine-focus.json", "curriculum.json",
              "trail-arms.json"):
        check(f"خروجیِ همین اجرا منتشر شد: {f}", _got.get(f) == 1,
              f"روی origin: {_got.get(f)!r}")
    check("فایلِ تازه‌ساخته هم منتشر شد (فهرستِ سفت‌نوشته نیست)",
          _got.get("brand-new.json") == 1, f"روی origin: {_got.get('brand-new.json')!r}")
    check("کارِ اجرای دیگر پاک نشد (origin که جلو رفته بود، ماند)",
          _got.get("other.json") == 7, f"روی origin: {_got.get('other.json')!r}")

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان گزارش کار: هر {OK} بررسی سبز")
