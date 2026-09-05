"""پاسبان ناشر مشترک — scripts/publish.sh (درس ۲ سپتامبر).

حمید: «به وجود اومدن مشکلات و رفع کردنشون شده کار هر روزت. قرار نیست این
مشکل برای همیشه برطرف بشه؟» — سه قطعیِ یک روز، هر سه از تکثیرِ ناشرِ
دست‌نویس در ۳۶ ورک‌فلو. این آزمون **رفتار** ناشرِ یگانه را در مخزن‌های
موقتِ واقعی می‌سنجد (نه متنش را)، دقیقاً روی سناریوهایی که خرابی‌ها از
آن‌ها آمدند:

  · فایلِ بی‌handler در تعارض → job نمی‌میرد (قطعی ۸ساعتهٔ چرخه)
  · خروجیِ همین اجرا هرگز دور ریخته نمی‌شود (عیب work-report)
  · دفتر append-only از هر دو طرف اجتماع می‌شود (درس ۱۵ اوت، ۳۹۰ ردیف)
  · چک‌اوتِ کم‌عمق هم کار می‌کند و کدِ upstream را نمی‌کوبد
  · هیچ مارکر تعارضی منتشر نمی‌شود

اجرا: `python3 -m hamid.test_publish`
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PUBLISH = REPO / "scripts" / "publish.sh"
RESOLVER = REPO / "scripts" / "resolve_brain_conflicts.py"

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


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)


def _seed(work):
    (work / "scripts").mkdir(exist_ok=True)
    shutil.copy(PUBLISH, work / "scripts" / "publish.sh")
    shutil.copy(RESOLVER, work / "scripts" / "resolve_brain_conflicts.py")
    shutil.copy(REPO / "scripts" / "publish_merge.py", work / "scripts" / "publish_merge.py")
    for d in ("signals", "brain/paper", "brain/memory", "code"):
        (work / d).mkdir(parents=True, exist_ok=True)
    (work / "signals/latest.json").write_text('{"generated": 1}')
    (work / "brain/paper/closed.jsonl").write_text(
        json.dumps({"sym": "BASE", "closed": 100, "R": 0.1}) + "\n")
    (work / "brain/memory/.revalidated").write_text("2026-09-01\n")
    (work / "code/engine.py").write_text("VERSION = 1\n")


class World:
    """origin + دو کلون: «ما» (رانر) و «دیگری» (اجرای هم‌زمان)."""

    def __init__(self, shallow=False):
        self.td = Path(tempfile.mkdtemp(prefix="publish-"))
        self.origin = self.td / "origin.git"
        git("init", "-q", "--bare", "-b", "main", str(self.origin), cwd=self.td)
        seed = self.td / "seed"
        git("clone", "-q", str(self.origin), str(seed), cwd=self.td)
        self._ident(seed)
        _seed(seed)
        git("add", "-A", cwd=seed)
        git("commit", "-qm", "base", cwd=seed)
        git("commit", "-q", "--allow-empty", "-m", "base2", cwd=seed)
        git("push", "-q", "origin", "HEAD:main", cwd=seed)
        self.other = self.td / "other"
        git("clone", "-q", str(self.origin), str(self.other), cwd=self.td)
        self._ident(self.other)
        self.work = self.td / "work"
        args = ["clone", "-q"] + (["--depth", "1"] if shallow else []) + \
               [f"file://{self.origin}", str(self.work)]
        git(*args, cwd=self.td)
        self._ident(self.work)

    @staticmethod
    def _ident(p):
        git("config", "user.email", "t@t", cwd=p)
        git("config", "user.name", "t", cwd=p)

    def other_push(self, writes):
        for rel, content in writes.items():
            p = self.other / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                p.write_text(p.read_text() + "")
            else:
                p.write_text(content)
        git("add", "-A", cwd=self.other)
        git("commit", "-qm", "elsewhere", cwd=self.other)
        r = git("push", "-q", "origin", "HEAD:main", cwd=self.other)
        assert r.returncode == 0, r.stderr

    def publish(self, *paths, msg="run", env=None):
        e = dict(os.environ, GIT_TERMINAL_PROMPT="0", PUBLISH_ATTEMPTS="4")
        e.update(env or {})
        return subprocess.run(["bash", "scripts/publish.sh", "-m", msg, *paths],
                              cwd=self.work, env=e, capture_output=True, text=True)

    def on_origin(self, rel):
        git("fetch", "-q", "origin", "main", cwd=self.other)
        r = git("show", f"origin/main:{rel}", cwd=self.other)
        return r.stdout if r.returncode == 0 else None

    def markers_on_origin(self):
        git("fetch", "-q", "origin", "main", cwd=self.other)
        r = git("grep", "-lE", "^(<<<<<<< |>>>>>>> )", "origin/main", "--",
                "signals", "brain", cwd=self.other)
        return r.stdout.strip()

    def close(self):
        shutil.rmtree(self.td, ignore_errors=True)


print("── ناشر مشترک: scripts/publish.sh ──")
check("اسکریپت وجود دارد و اجرایی است",
      PUBLISH.exists() and os.access(PUBLISH, os.X_OK))
# ۲ سپتامبر: تاریخچهٔ مخزن ۴.۴ گیگابایت است. `--unshallow` (اجرای ۲۰) و
# حتی `--deepen` (اجرای ۲۲) گام انتشار را تا سقف ۱۵ دقیقهٔ job خواباندند.
# ناشر حق ندارد تاریخچه بکشد یا merge کند: فقط نوکِ کم‌عمق + بازسازیِ
# محتوایی.
_src = PUBLISH.read_text(encoding="utf-8")
_code = "\n".join(l for l in _src.splitlines() if not l.lstrip().startswith("#"))
check("ناشر هرگز تاریخچه نمی‌کشد و merge نمی‌کند (فقط نوکِ کم‌عمق + بازسازی محتوایی)",
      "--unshallow" not in _code and "--deepen" not in _code
      and "git merge " not in _code and "--depth=1" in _code)

# ── ۱) بدون تغییر → خروج ۰ و هیچ کامیتی ─────────────────────────────────
w = World()
r = w.publish("signals", "brain")
check("بدون تغییر: خروج ۰", r.returncode == 0, r.stdout + r.stderr)
check("بدون تغییر: کامیتی ساخته نشد",
      git("rev-parse", "HEAD", cwd=w.work).stdout ==
      git("rev-parse", "origin/main", cwd=w.work).stdout)
w.close()

# ── ۲) انتشار ساده ───────────────────────────────────────────────────────
w = World()
(w.work / "signals/latest.json").write_text('{"generated": 2}')
(w.work / "signals/new-file.json").write_text('{"v": 1}')
r = w.publish("signals", "brain")
check("انتشار ساده: خروج ۰", r.returncode == 0, r.stdout + r.stderr)
check("عکس‌فوری روی origin است", w.on_origin("signals/latest.json") == '{"generated": 2}')
check("فایلِ تازه هم روی origin است (فهرست سفت‌نوشته نیست)",
      w.on_origin("signals/new-file.json") == '{"v": 1}')
check("فقط مسیرهای داده‌شده منتشر می‌شوند",
      "code/engine.py" not in git("show", "--stat", "--format=", "HEAD", cwd=w.work).stdout)
w.close()

# ── ۲ب) مسیرِ ناموجود در فهرست، تغییرِ واقعی را نمی‌کشد (اجرای ۱ فومو) ──
# `git add -A -- a b` وقتی b وجود ندارد با خطا هیچ‌چیز stage نمی‌کند؛ ناشر
# «بدون تغییر» می‌گفت در حالی که a عوض شده بود.
w = World()
(w.work / "signals/latest.json").write_text('{"generated": 3}')
r = w.publish("signals/latest.json", "brain/not-yet-there")
check("مسیر ناموجود: خروج ۰ و اعلام در لاگ", r.returncode == 0 and "ناموجود" in r.stdout, r.stdout + r.stderr)
check("مسیر ناموجود: فایلِ واقعاً عوض‌شده منتشر شد",
      w.on_origin("signals/latest.json") == '{"generated": 3}')
r = w.publish("brain/also-missing")
check("همهٔ مسیرها ناموجود: «بدون تغییر»، خروج ۰", r.returncode == 0 and "بدون تغییر" in r.stdout, r.stdout + r.stderr)
w.close()

# ── ۳) origin جلو رفته (فایل دیگر) → ادغام، هر دو می‌مانند ──────────────
w = World()
w.other_push({"signals/other.json": '{"o": 7}'})
(w.work / "signals/latest.json").write_text('{"generated": 3}')
r = w.publish("signals", "brain")
check("origin جلوتر: خروج ۰", r.returncode == 0, r.stdout + r.stderr)
check("خروجیِ ما رسید", w.on_origin("signals/latest.json") == '{"generated": 3}')
check("کارِ اجرای دیگر پاک نشد (نه reset، نه --ours کور)",
      w.on_origin("signals/other.json") == '{"o": 7}')
w.close()

# ── ۴) دفتر append-only از هر دو طرف → اجتماع (درس ۱۵ اوت) ──────────────
w = World()
base = (w.work / "brain/paper/closed.jsonl").read_text()
w.other_push({"brain/paper/closed.jsonl":
              base + json.dumps({"sym": "THEIRS", "closed": 200, "R": 0.5}) + "\n"})
(w.work / "brain/paper/closed.jsonl").write_text(
    base + json.dumps({"sym": "OURS", "closed": 300, "R": -1.0}) + "\n")
r = w.publish("signals", "brain")
check("تعارض دفتر: خروج ۰", r.returncode == 0, r.stdout + r.stderr)
led = w.on_origin("brain/paper/closed.jsonl") or ""
syms = [json.loads(l)["sym"] for l in led.splitlines() if l.strip()]
check("هیچ ردیفی از هیچ طرف گم نشد", set(syms) == {"BASE", "THEIRS", "OURS"}, str(syms))
check("مارکر تعارض منتشر نشد", not w.markers_on_origin())
w.close()

# ── ۵) نشانگر بی‌پسوند (قطعی ۸ساعتهٔ ۲ سپتامبر) ─────────────────────────
w = World()
w.other_push({"brain/memory/.revalidated": "2026-09-01\n",
              "signals/other.json": '{"o": 1}'})
(w.work / "brain/memory/.revalidated").write_text("2026-09-02\n")
r = w.publish("signals", "brain")
check("نشانگر بازسنجی در تعارض: job نمی‌میرد", r.returncode == 0, r.stdout + r.stderr)
check("تاریخ تازه‌تر منتشر شد",
      (w.on_origin("brain/memory/.revalidated") or "").strip() == "2026-09-02")
w.close()

# ── ۶) فایلی که هیچ handlerی ندارد (بیرون brain/) → باز هم نمی‌میرد ───────
w = World()
(w.other / "notes").mkdir(exist_ok=True)
w.other_push({"notes/run.txt": "theirs\n"})
(w.work / "notes").mkdir(exist_ok=True)
(w.work / "notes/run.txt").write_text("ours\n")
r = w.publish("signals", "brain", "notes")
check("مسیرِ بی‌handler در تعارض: خروج ۰ (قانون: هیچ تعارضی job را نمی‌کشد)",
      r.returncode == 0, r.stdout + r.stderr)
check("فایلی که همین اجرا نوشته، نسخهٔ ما را می‌گیرد",
      w.on_origin("notes/run.txt") == "ours\n")
check("بدون مارکر", not w.markers_on_origin())
w.close()

# ── ۷) چک‌اوت کم‌عمق (fetch-depth: 1) + کدِ upstream عوض شده ─────────────
w = World(shallow=True)
w.other_push({"code/engine.py": "VERSION = 2\n", "signals/other.json": '{"o": 2}'})
(w.work / "signals/latest.json").write_text('{"generated": 9}')
r = w.publish("signals", "brain")
check("کلون کم‌عمق: خروج ۰", r.returncode == 0, r.stdout + r.stderr)
check("کلون کم‌عمق: خروجی ما رسید", w.on_origin("signals/latest.json") == '{"generated": 9}')
check("کدِ upstream که ما دست نزده‌ایم، دست‌نخورده ماند (نه چک‌اوتِ کهنهٔ رانر)",
      w.on_origin("code/engine.py") == "VERSION = 2\n")
w.close()

# ── ۸) تاریخچهٔ بی‌ربط (ریشهٔ دوم) — هر فایلِ متفاوت add/add می‌شود ────────
#
# این مخزن دو ریشه دارد و merge با --allow-unrelated-histories گاهی
# همهٔ فایل‌های متفاوت را تعارض می‌کند. خطر: فایلی که همین اجرا ننوشته
# (چک‌اوتِ کهنهٔ رانر) با قاعدهٔ «عکس‌فوری → مال ما» روی خروجیِ تازهٔ
# اجرای دیگر بنشیند. قاعده: فایلِ نانوشته = نسخهٔ origin، همیشه.
w = World()
w.other_push({"signals/other.json": '{"o": 99}', "code/engine.py": "VERSION = 3\n"})
alien = w.td / "alien"
alien.mkdir()
git("init", "-q", "-b", "main", cwd=alien)
World._ident(alien)
_seed(alien)
(alien / "signals/other.json").write_text('{"o": 0}')      # کهنه، دست‌نخورده
git("add", "-A", cwd=alien)
git("commit", "-qm", "second root", cwd=alien)
git("remote", "add", "origin", f"file://{w.origin}", cwd=alien)
(alien / "signals/latest.json").write_text('{"generated": 77}')
r = subprocess.run(["bash", "scripts/publish.sh", "-m", "alien", "signals", "brain"],
                   cwd=alien, env=dict(os.environ, PUBLISH_ATTEMPTS="4"),
                   capture_output=True, text=True)
check("ریشهٔ بی‌ربط: خروج ۰", r.returncode == 0, (r.stdout + r.stderr)[-500:])
check("ریشهٔ بی‌ربط: خروجیِ ما رسید", w.on_origin("signals/latest.json") == '{"generated": 77}')
check("فایلی که ما ننوشتیم، نسخهٔ تازهٔ origin ماند (نه چک‌اوتِ کهنهٔ رانر)",
      w.on_origin("signals/other.json") == '{"o": 99}', str(w.on_origin("signals/other.json")))
check("کدِ upstream هم دست‌نخورده", w.on_origin("code/engine.py") == "VERSION = 3\n")
check("بدون مارکر", not w.markers_on_origin())
w.close()

# ── ۸ب) همان چیزی که اجرای ۳۶۳ چرخه را کشت (۱۰:۳۷، ۸ تلاش، هیچ انتشاری) ──
#
# دو عیب هم‌زمان: (۱) حل‌کننده برای brain/*.jsonِ ناشناخته هشدار روی
# stdout چاپ می‌کند و ناشر همان را به‌جای sha گرفت؛ (۲) brain/events یک
# ردیفِ رشته‌ای خام داشت و اجتماعِ دفتر با AttributeError افتاد. هر دو
# باید در یک انتشارِ «origin جلوتر» زنده بمانند.
w = World()
w.other_push({"brain/events/2026-09-02.jsonl": '"a"\n{"t": 1}\n"b"\n',
              "brain/room-snapshot.json": '{"o": 1}',
              "brain/alert-state.json": '{"o": 1}',
              "signals/other.json": '{"o": 5}'})
(w.work / "brain/events").mkdir(parents=True, exist_ok=True)
(w.work / "brain/events/2026-09-02.jsonl").write_text('"a"\n{"t": 1}\n{"t": 2}\n')
(w.work / "brain/room-snapshot.json").write_text('{"m": 1}')     # ناشناخته → هشدار stdout
(w.work / "brain/alert-state.json").write_text('{"m": 1}')       # مرز پیشروی → اجتماع کلیدها
r = w.publish("signals", "brain")
check("هشدارِ stdout حل‌کننده sha را خراب نمی‌کند: خروج ۰", r.returncode == 0,
      (r.stdout + r.stderr)[-600:])
check("دفترِ با ردیفِ رشته‌ای: هیچ ردیفی از هیچ طرف گم نشد",
      sorted((w.on_origin("brain/events/2026-09-02.jsonl") or "").split())
      == sorted(['"a"', '{"t":', '1}', '"b"', '{"t":', '2}']),
      repr(w.on_origin("brain/events/2026-09-02.jsonl")))
check("عکس‌فوریِ ناشناختهٔ brain → مال ما", w.on_origin("brain/room-snapshot.json") == '{"m": 1}')
_st = json.loads(w.on_origin("brain/alert-state.json") or "{}")
check("مرز پیشروی (-state.json) → اجتماع کلیدهای هر دو طرف", _st == {"m": 1, "o": 1}, str(_st))
check("فایلِ نانوشته → نسخهٔ origin", w.on_origin("signals/other.json") == '{"o": 5}')
w.close()

# ── ۸ب) آرشیو شماره‌دارِ signals/archive → دفتر است، نه عکس‌فوری ──────────
#
# عیبِ ۵ سپتامبر: `signals/` یک‌جا take_ours می‌گرفت، پس وقتی دو اجرا در
# یک روز روی `telegram-sent-<روز>.jsonl` می‌نوشتند نسخهٔ کامل یکی روی
# دیگری می‌نشست و ردیف‌های اضافیِ آن یکی گم می‌شدند. اندازه‌گیری: دفتر
# ارسال ۲۴ ردیف در ۲۴ ساعت داشت و آرشیو ۲۳ (DOGEUSDT گم شده بود) —
# و همین آرشیو منبعِ شمارندهٔ سقف روزانه است.
w = World()
_row = lambda n, at, sym, mid: json.dumps(          # noqa: E731
    {"n": n, "at": at, "sym": sym, "tf": "5m", "dir": "LONG",
     "entry": 1.0, "sl": 0.9, "tp1": 1.2, "strategy": "ibs",
     "tg_msg_id": mid}, ensure_ascii=False)
w.other_push({"signals/archive/telegram-sent-20260904.jsonl":
              _row(1, 1000, "AAAUSDT", 11) + "\n" + _row(2, 3000, "CCCUSDT", 13) + "\n"})
(w.work / "signals/archive").mkdir(parents=True, exist_ok=True)
(w.work / "signals/archive/telegram-sent-20260904.jsonl").write_text(
    _row(1, 1000, "AAAUSDT", 11) + "\n" + _row(2, 2000, "BBBUSDT", 12) + "\n")
r = w.publish("signals")
_arc = [json.loads(x) for x in (w.on_origin(
    "signals/archive/telegram-sent-20260904.jsonl") or "").splitlines() if x.strip()]
check("انتشار آرشیو: خروج ۰", r.returncode == 0, (r.stdout + r.stderr)[-500:])
check("آرشیو ارسال: هیچ ردیفی از هیچ طرف گم نشد (اجتماع، نه take_ours)",
      [a["sym"] for a in _arc] == ["AAAUSDT", "BBBUSDT", "CCCUSDT"], str(_arc))
check("آرشیو ارسال: ردیف مشترک دوبار نمی‌شود",
      sum(1 for a in _arc if a["tg_msg_id"] == 11) == 1, str(_arc))
check("آرشیو ارسال: شماره‌گذاری بعد از اجتماع پیاپی و بی‌تکرار",
      [a["n"] for a in _arc] == [1, 2, 3], str([a["n"] for a in _arc]))
w.close()

# کلاسِ عیب: هیچ دفتر jsonl زیر signals/ نباید عکس‌فوری فرض شود.
sys.path.insert(0, str(REPO / "scripts"))
import importlib.util as _ilu                                   # noqa: E402
_spec = _ilu.spec_from_file_location("rbc_guard", RESOLVER)
_rbc = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_rbc)
check("کلاس: هر jsonl زیر signals/archive → اجتماع، نه take_ours",
      all(_rbc.handler_for(p) is _rbc.merge_archive_jsonl for p in (
          "signals/archive/telegram-sent-20260904.jsonl",
          "signals/archive/telegram-feed-20260904.jsonl",
          "signals/archive/delivery-failures-20260904.jsonl")),
      str([_rbc.handler_for("signals/archive/telegram-feed-20260904.jsonl")]))
check("مرز: عکس‌فوریِ signals همچنان take_ours می‌ماند",
      _rbc.handler_for("signals/latest.json") is _rbc.take_ours)

# ── ۹) ریموتِ مرده → خروج ۱ بعد از تلاش‌ها، نه سکوت ───────────────────────
w = World()
(w.work / "signals/latest.json").write_text('{"generated": 4}')
r = w.publish("signals", env={"PUBLISH_REMOTE": "nowhere", "PUBLISH_ATTEMPTS": "2"})
check("ریموتِ ناموجود: خروج غیرصفر (خرابیِ واقعی پنهان نمی‌شود)", r.returncode != 0)
w.close()

print()
if FAIL:
    print(f"✗ {len(FAIL)} بررسی افتاد: {FAIL}")
    sys.exit(1)
print(f"✓ همهٔ {OK} بررسی ناشر مشترک گذشت")
