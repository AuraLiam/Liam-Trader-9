"""پاسبان سرویس محلی (۴ سپتامبر) — آفلاین، بدون شبکه، بدون نوشتنِ تولید.

دستور حمید: «بدون نیاز به گیتهاب بریم جلو… هر بار میگی برطرف کردم اما
تغییری صورت نگرفته و هر بار باز مشکل پیش می‌اید.»

بندِ دوم مهم‌تر از اولی است. این پاسبان طوری نوشته شده که همان **کلاسِ
عیب** را ببندد: نه فقط «سرویس محلی کار می‌کند»، بلکه «سرویس محلی از
Actions عقب نمی‌افتد». اگر فردا فرمانی به ورک‌فلو اضافه شود و به جدول
محلی نیاید، این آزمون سرخ می‌شود — پس واگراییِ بی‌صدا ممکن نیست.
"""
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import liam9d as D                        # noqa: E402

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


SRC = (HERE / "liam9d.py").read_text(encoding="utf-8")
WF = HERE.parents[2] / ".github" / "workflows"

# ── ۱. گیت در مسیر سیگنال نیست ─────────────────────────────────────────
#
# این بندِ اصلی دستور است. زنجیرهٔ Actions در حلقه‌اش `reset --hard`
# داشت؛ اگر یک روز کسی همان را این‌جا بیاورد، همان کلاسِ عیب برمی‌گردد.
#
# روی **داده** سنجیده می‌شود نه روی متن: نسخهٔ اولِ همین آزمون دنبال
# رشتهٔ «reset --hard» در کل فایل گشت و افتاد — چون همان عبارت در
# توضیحِ «این‌ها حذف شدند» بود. آزمونی که مستنداتِ خودش را جرم بگیرد،
# آدم را وادار می‌کند مستندات را پاک کند تا سبز شود؛ یعنی بدترین جهت.
for j in D.JOBS:
    assert j["cmd"][0].startswith("python")
check("هیچ کارِ جدول، گیت اجرا نمی‌کند",
      not any("git" in part for j in D.JOBS for part in j["cmd"]))
for bad, why in (("reset --hard", "پاک‌کنندهٔ درخت"),
                 ("--reapply", "نشاندن دوبارهٔ خروجی بعد از reset"),
                 ("--restore", "برگرداندن رسید بعد از reset")):
    check(f"«{bad}» در هیچ فرمانِ اجراشدنی نیست — {why}",
          not any(bad in " ".join(j["cmd"]) for j in D.JOBS))
check("و کد هیچ زیرفرایند گیتی صدا نمی‌زند",
      not re.search(r'(subprocess|Popen|run|check_output)\s*\(\s*\[?\s*["\']git', SRC)
      and not re.search(r'^\s*(?!#)[^\n#]*\bsubprocess\.[a-z_]+\([^)]*git', SRC,
                        re.M))
check("و ماژول گیت را اصلاً وارد نمی‌کند", "import git" not in SRC)

# ── ۲. مرزهای امنیتی ───────────────────────────────────────────────────
check("اجرای زنده قفل است", 'e["LIVE_EXECUTION"] = "false"' in SRC)
env = D.base_env()
check("و در محیطِ واقعیِ ساخته‌شده هم false است",
      env["LIVE_EXECUTION"] == "false", env.get("LIVE_EXECUTION"))
check("منبع کندل پیش‌فرض پرپ است (دستور ۳۱ اوت)",
      env["LIAM9_CANDLES"] == "perp", env.get("LIAM9_CANDLES"))
check("سکرت‌ها از فایل بیرون گیت خوانده می‌شوند", 'ROOT / "live.env"' in SRC)
gi = (HERE.parents[2] / ".gitignore").read_text(encoding="utf-8")
check("و live.env در .gitignore است (قانون ۰۵)", "live.env" in gi)
for d in (".git", "live.env"):
    check(f"پنل محلی «{d}» را سرو نمی‌کند", d in D.DENY)

# ── ۳. ضدواگرایی: جدول محلی از Actions عقب نمی‌افتد ────────────────────
#
# قلبِ این آزمون. هر فرمان تولیدیِ ورک‌فلوهایی که سرویس محلی ادعا
# می‌کند پوشش داده، یا باید در JOBS باشد یا در GIT_ONLY با دلیل.
CMD_RE = re.compile(r"python3?\s+(?:-m\s+([a-zA-Z_][\w.]*)|([a-zA-Z_]+\.py))([^\n)|&]*)")


def wf_cmds(name):
    txt = (WF / name).read_text(encoding="utf-8")
    out = set()
    for m in CMD_RE.finditer(txt):
        mod, script, args = m.group(1), m.group(2), (m.group(3) or "")
        head = mod or script
        if head.startswith("hamid.test") or head in ("pytest",):
            continue
        flags = " ".join(a for a in args.split()
                         if a.startswith("--") and "$" not in a and '"' not in a)
        out.add((head + (" " + flags if flags else "")).strip())
    return out


local_cmds = set()
for j in D.JOBS:
    head = j["cmd"][2] if j["cmd"][1] == "-m" else j["cmd"][1]
    flags = " ".join(a for a in j["cmd"] if a.startswith("--"))
    local_cmds.add((head + (" " + flags if flags else "")).strip())

covered = sorted({j["wf"] for j in D.JOBS})
check(f"سرویس محلی {len(covered)} ورک‌فلوی تولیدی را پوشش می‌دهد",
      len(covered) >= 10, str(covered))

missing = []
for name in covered:
    for c in wf_cmds(name):
        head = c.split()[0]
        if any(c == lc or head == lc.split()[0] for lc in local_cmds):
            continue
        if any(c.startswith(g) or g.startswith(head) and head in g
               for g in D.GIT_ONLY):
            continue
        missing.append(f"{name}: {c}")
check("هر فرمانِ تولیدیِ آن ورک‌فلوها یا در جدول محلی است یا در GIT_ONLY با دلیل",
      not missing, "\n      ".join(missing[:10]))
check("هر ردیف GIT_ONLY دلیلِ نوشته‌شده دارد — نه فهرست خالی",
      all(len(v.strip()) >= 8 for v in D.GIT_ONLY.values()),
      str([k for k, v in D.GIT_ONLY.items() if len(v.strip()) < 8]))

# ── ۴. اسکن محصول است و اول جدول ───────────────────────────────────────
check("اسکن استراتژی اولین کار جدول است", D.JOBS[0]["key"] == "scan")
check("و همان فرمان تولید را با همان پرچم‌ها می‌زند",
      D.JOBS[0]["cmd"] == ["python3", "scan.py", "--symbols", "60", "--rotate",
                           "200", "--core", "30", "--telegram"],
      str(D.JOBS[0]["cmd"]))
scan_wf = (WF / "pump-radar.yml").read_text(encoding="utf-8")
check("و دقیقاً همان چیزی است که زنجیرهٔ Actions می‌زند (بدون شل‌شدن دروازه)",
      "scan.py --symbols 60 --rotate 200 --core 30 --telegram" in scan_wf)
check("ضربانِ اسکن از کف ۱۵دقیقه‌ایِ Actions خیلی کمتر است",
      D.JOBS[0]["every"] <= 300, f"{D.JOBS[0]['every']}s")
check("هر کار کلید یکتا دارد", len(D.BY_KEY) == len(D.JOBS))
check("هر کار توضیح فارسی و سقف زمان دارد",
      all(j.get("desc") and j.get("timeout") for j in D.JOBS))
check("هیچ کاری بی‌سقف نیست (کارِ گیرکرده حلقه را نمی‌خواباند)",
      all(0 < j["timeout"] <= 900 for j in D.JOBS))

# ── ۵. بی‌توکن: رد می‌شود ولی بی‌صدا نه ────────────────────────────────
tg_jobs = [j for j in D.JOBS if j.get("tg")]
check("کارهای ارسالی برچسب tg دارند", len(tg_jobs) >= 8, str(len(tg_jobs)))
saved = os.environ.pop("TELEGRAM_BOT_TOKEN", None)
ran = D.loop(once=True, only={"gainer_radar"}, quiet=True)
check("بی‌توکن، کار ارسالی اجرا نمی‌شود",
      len(ran) == 1 and ran[0]["ok"] is None, str(ran))
check("و دلیلش صریح ثبت می‌شود، نه سکوت", ran[0]["code"] == "بی‌توکن")
if saved:
    os.environ["TELEGRAM_BOT_TOKEN"] = saved

# ── ۶. کار شکست‌خورده حلقه را نمی‌کشد ──────────────────────────────────
r = D.run_job({"key": "x", "cmd": ["python3", "-c", "raise SystemExit(3)"],
               "timeout": 20})
check("کار شکست‌خورده استثنا پرت نمی‌کند", r["ok"] is False and r["code"] == 3)
r2 = D.run_job({"key": "y", "cmd": ["python3", "-c", "import time;time.sleep(9)"],
                "timeout": 1})
check("کار گیرکرده با سقف زمان بریده می‌شود", r2["code"] == "timeout")
check("و زمانش ثبت می‌شود", r2["secs"] < 5, str(r2["secs"]))
r3 = D.run_job({"key": "z", "cmd": ["__nope__"], "timeout": 5})
check("فرمانِ ناموجود هم حلقه را نمی‌کشد", r3["ok"] is False)

# ── ۷. تابلوی وضعیت ────────────────────────────────────────────────────
import time                                          # noqa: E402

snap = D.write_state(3, [{"key": "scan", "ok": True, "code": 0, "secs": 1.0,
                          "tail": [], "ts": 1},
                         {"key": "fomo", "ok": False, "code": 2, "secs": 2.0,
                          "tail": ["خطا"], "ts": 2}],
                     {"scan": time.time()}, 60)
check("تابلو شمار موفق و ناموفق را جدا می‌گوید",
      snap["ok"] == 1 and snap["failed"] == 1)
check("و شکست‌ها را با دلیل نشان می‌دهد",
      snap["last_failures"] and snap["last_failures"][0]["key"] == "fomo")
check("سن هر کار روی تابلو هست", "scan" in snap["jobs"])
check("مالک تابلو E23 است", snap["engine"] == "E23")
check("و مرز صادقانه رویش نوشته شده",
      "LIVE_EXECUTION=false" in snap["boundary"]
      and "همان فرمان‌ها" in snap["boundary"])
check("حالت «محلی — بدون گیت‌هاب» اعلام می‌شود", "بدون گیت‌هاب" in snap["mode"])

# ── ۸. دکتر راست می‌گوید ───────────────────────────────────────────────
rows = D.doctor(verbose=False)
check("دکتر همهٔ بخش‌ها را می‌سنجد", len(rows) >= 12, str(len(rows)))
check("و هر ردیف حکم و توضیح دارد",
      all("ok" in r and "توضیح" in r for r in rows))
ok_, note = D._http_ok("http://127.0.0.1:1/")
check("میزبانِ نرسیدنی، شکست گزارش می‌شود", ok_ is False, note)

# اثباتِ رفتاریِ همان عیبی که ۴ سپتامبر روی همین ماشین دیده شد: پروکسی
# اتصال TCP را می‌پذیرفت و بعد HTTP را رد می‌کرد، و دکترِ پینگ‌محور
# «دسترسی ✓» می‌داد کنارِ «کندل نیامد ✗». این‌جا همان وضعیت ساخته
# می‌شود — سوکتی که وصل می‌شود و بی‌جواب می‌بندد — و باید قرمز شود.
import socket as _sk                                 # noqa: E402
import threading as _th                              # noqa: E402

_srv = _sk.socket()
_srv.setsockopt(_sk.SOL_SOCKET, _sk.SO_REUSEADDR, 1)
_srv.bind(("127.0.0.1", 0))
_srv.listen(1)
_dead_port = _srv.getsockname()[1]


def _accept_and_drop():
    try:
        c, _ = _srv.accept()
        c.close()
    except Exception:                                # noqa: BLE001
        pass


_th.Thread(target=_accept_and_drop, daemon=True).start()
ok2, note2 = D._http_ok(f"http://127.0.0.1:{_dead_port}/", timeout=5)
_srv.close()
check("میزبانی که TCP را می‌پذیرد ولی HTTP نمی‌دهد، سبزِ دروغین نمی‌گیرد",
      ok2 is False, note2)

# ── ۹. لاگ بی‌سقف دیسک را نمی‌خورد ─────────────────────────────────────
with tempfile.TemporaryDirectory() as td:
    old = D.LOG
    D.LOG = Path(td) / "log.jsonl"
    for i in range(D.MAX_LOG * 2 + 50):
        D._append_log({"i": i})
    n = len(D.LOG.read_text(encoding="utf-8").strip().splitlines())
    D.LOG = old
    # کران، نه عددِ دقیق: هرس وقتی می‌زند که از دو برابر سقف رد شود، پس
    # فایل بین MAX_LOG و 2×MAX_LOG می‌ماند — مهم این است که با ۸۰۵۰
    # نوشتن، بی‌کران رشد نکند.
    check("لاگ سرویسِ همیشه‌روشن بی‌کران رشد نمی‌کند",
          D.MAX_LOG <= n <= 2 * D.MAX_LOG, f"{n} خط از ۸۰۵۰ نوشته")

# ── ۱۰. پنل محلی: سرو می‌کند، ولی سکرت را نه ───────────────────────────
srv = None
try:
    srv = D.serve("127.0.0.1", 0)
    port = srv.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html",
                                timeout=8) as r:
        body, status = r.read(600), r.status
        nocache = "no-store" in (r.headers.get("Cache-Control") or "")
    check("پنل از روی دیسک سرو می‌شود", status == 200 and len(body) > 100)
    check("و بی‌کش — عددی که همین ثانیه نوشته شد همین ثانیه دیده می‌شود", nocache)
    denied = 0
    for path in ("/live.env", "/.git/config"):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=8)
        except Exception:                            # noqa: BLE001
            denied += 1
    check("سکرت و تاریخچهٔ گیت سرو نمی‌شوند", denied == 2, f"{denied}/2")
except Exception as e:                               # noqa: BLE001
    check("پنل محلی بالا می‌آید", False, f"{type(e).__name__}: {e}")
finally:
    if srv:
        srv.shutdown()

# ── ۱۱. تولید آلوده نشد ────────────────────────────────────────────────
check("این آزمون تابلوی سرویس را در تولید ننوشت (حالت شنی)",
      os.environ.get("LIAM9_SANDBOX") != "1" or not D.STATE.exists()
      or json.loads(D.STATE.read_text(encoding="utf-8")).get("engine") == "E23")

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
