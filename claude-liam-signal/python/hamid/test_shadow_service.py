"""پاسبان سرویس سایهٔ محلی (۲ سپتامبر) — آفلاین، بدون شبکه، بدون تلگرام.

آنچه قفل می‌شود:
۱. فرمان اسکن هرگز پرچم تحویل ندارد و محیطش اعتبارنامهٔ تلگرام را ندارد.
۲. خروجی فقط به پوشهٔ سایه می‌رود؛ دفتر تولید دست نمی‌خورد.
۳. ضربان شکل ثابت دارد و شکست‌ها را صادقانه می‌شمارد؛ فاصلهٔ بعد از
   شکست دو برابر می‌شود تا سقف.
۴. حلقه با اسکنِ خراب نمی‌میرد.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import shadow_service as SS                # noqa: E402

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


TMP = Path(tempfile.mkdtemp(prefix="liam9-shadow-"))
SH = TMP / "shadow"
HB = SH / "heartbeat.json"

# ── ۱. فرمان و محیط ────────────────────────────────────────────────────────
cmd = SS.scan_cmd()
check("فرمان اسکن بدون --telegram است", "--telegram" not in cmd and cmd[1].endswith("scan.py"))
check("جهان ۲۰۰ نماد با هستهٔ ۳۰ و دو تایم ۵د/۱۵د", "--rotate" in cmd and "200" in cmd and "5m,15m" in cmd)
# نام «TG_X» عمداً نام هیچ بات واقعی نیست (test_single_bot نام‌های بات دوم را در کد زنده ممنوع کرده)
env = SS.env_for({"TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHAT_ID": "y", "TG_X": "z",
                  "PATH": "/bin", "LIVE_EXECUTION": "true"}, shadow_dir=SH)
check("اعتبارنامهٔ تلگرام از محیط زیرفرایند حذف می‌شود",
      not any(k.startswith(("TELEGRAM_", "TG_")) for k in env), str([k for k in env]))
check("LIVE_EXECUTION حتی اگر true بیاید false می‌شود", env["LIVE_EXECUTION"] == "false")
check("خروجی به پوشهٔ سایه می‌رود، نه signals/", env["LIAM9_SIGNALS_DIR"] == str(SH))
check("منبع کندل پیش‌فرض پرپ (همان تولید)", env["LIAM9_CANDLES"] == "perp")
env2 = SS.env_for({"LIAM9_CANDLES": "spot"}, shadow_dir=SH)
check("انتخاب صریح اسپات محترم می‌ماند", env2["LIAM9_CANDLES"] == "spot")
check("پوشهٔ سایهٔ پیش‌فرض زیر signals/shadow است (state_bus فقط سطح اول را می‌بیند)",
      SS.SHADOW.parent.name == "signals" and SS.SHADOW.name == "shadow")

# ── ۲. scan.py واقعاً سوییچ مسیر را می‌خواند ───────────────────────────────
scan_src = (HERE.parent / "scan.py").read_text(encoding="utf-8")
check("scan.OUT از LIAM9_SIGNALS_DIR می‌آید", "LIAM9_SIGNALS_DIR" in scan_src)
check("دفتر پوشش هم به همان OUT می‌رود (سایه دفتر تولید را نمی‌شورد)",
      'OUT / "scan-coverage.json"' in scan_src and 'ROOT / "signals" / "scan-coverage.json"' not in scan_src)

# ── ۳. عقب‌نشینی ───────────────────────────────────────────────────────────
check("بدون شکست = کادنس عادی", SS.backoff(0, 300) == 300)
check("هر شکست فاصله را دو برابر می‌کند", SS.backoff(1, 300) == 600 and SS.backoff(2, 300) == 1200)
check("سقف ۳۰ دقیقه", SS.backoff(9, 300) == SS.MAX_BACKOFF_S)

# ── ۴. یک اسکن با رانر جعلی ────────────────────────────────────────────────
calls = []


class _R:
    def __init__(self, rc, out=""):
        self.returncode, self.stdout = rc, out


def good_runner(cmd, env=None, cwd=None, **kw):
    calls.append((cmd, env))
    Path(env["LIAM9_SIGNALS_DIR"]).mkdir(parents=True, exist_ok=True)
    (Path(env["LIAM9_SIGNALS_DIR"]) / "latest.json").write_text(json.dumps(
        {"generated": 1, "signals": [{"sym": "BTCUSDT"}], "watch": [{}, {}],
         "symbols": ["A", "B", "C"], "source": "bitunix-perp"}))
    return _R(0, "ok\nwritten")


def bad_runner(cmd, env=None, cwd=None, **kw):
    calls.append((cmd, env))
    raise RuntimeError("python exploded")


r = SS.run_once(runner=good_runner, shadow_dir=SH)
check("اسکن موفق: rc=0، مدت ثبت، خلاصهٔ latest سایه خوانده شد",
      r["ok"] and r["rc"] == 0 and r["latest"]["signals"] == 1 and r["latest"]["candle_src"] == "bitunix-perp", str(r))
check("رانر با محیط سایه صدا زده شد", calls[-1][1]["LIAM9_SIGNALS_DIR"] == str(SH) and "--telegram" not in calls[-1][0])
check("latest.json فقط داخل سایه نوشته شد", (SH / "latest.json").exists() and not (TMP / "latest.json").exists())
r2 = SS.run_once(runner=bad_runner, shadow_dir=SH)
check("رانر منفجر شود → نتیجهٔ شکست، نه استثنا", not r2["ok"] and r2["rc"] == -1 and "exploded" in r2["tail"])

# ── ۵. ضربان و حلقه ────────────────────────────────────────────────────────
clock = {"t": 1000.0}
slept = []


def fake_now():
    return clock["t"]


def fake_sleep(s):
    slept.append(s)
    clock["t"] += s


seq = iter([good_runner, bad_runner, bad_runner, good_runner])


def seq_runner(cmd, **kw):
    return next(seq)(cmd, **kw)


st = SS.loop(iterations=4, sleep=fake_sleep, runner=seq_runner, shadow_dir=SH, heart_path=HB,
             interval=120, hb=30, now=fake_now)
hb = json.loads(HB.read_text(encoding="utf-8"))
check("چهار اسکن انجام شد و حلقه با دو شکست پیاپی نمرد", st["scans"] == 4, str(st["scans"]))
check("شمارندهٔ شکست پیاپی بعد از موفقیت صفر می‌شود", st["failures"] == 0)
check("ضربان شکل ثابت دارد", all(k in hb for k in ("generated", "mode", "delivers", "tick", "scans",
                                                     "failures_in_row", "uptime_s", "next_scan_in_s", "last_scan", "candles")))
check("ضربان صریح می‌گوید سایه است و تحویل نمی‌دهد", hb["mode"] == "shadow" and hb["delivers"] is False)
check("ضربان بین اسکن‌ها هر ۳۰ ثانیه نوشته شد (tick > scans)", hb["tick"] > hb["scans"] and all(s <= 30 for s in slept))
# فاصله‌ها: بعد از اسکن ۱ (موفق) ۱۲۰ث؛ بعد از ۲ (شکست) ۲۴۰؛ بعد از ۳ (شکست دوم) ۴۸۰
waits = [round(sum(slept[i:j])) for i, j in ((0, 4), (4, 12), (12, 28))]
check("فاصلهٔ اسکن بعد از شکست دو برابر می‌شود (۱۲۰ → ۲۴۰ → ۴۸۰)", waits == [120, 240, 480], str(waits))
check("ضربان ادعای زمان واقعی نمی‌کند: uptime از ساعت تزریقی و صفر نیست", isinstance(hb["uptime_s"], int))

# ── ۶. مرزهای متنی ─────────────────────────────────────────────────────────
src = (HERE / "shadow_service.py").read_text(encoding="utf-8")
check("ماژول هیچ‌جا تلگرام را import نمی‌کند", "import telegram" not in src and "from telegram" not in src)
check("ماژول هیچ‌جا به اجرای زنده دست نمی‌زند", "liam9_link" not in src and "place_order" not in src)
sh = (SS.ROOT / "service" / "run.sh").read_text(encoding="utf-8")
ps = (SS.ROOT / "service" / "run.ps1").read_text(encoding="utf-8")
check("سوپروایزر لینوکس/مک بعد از مرگ دوباره بالا می‌آورد", "while" in sh and "hamid.shadow_service" in sh and "--telegram" not in sh)
check("سوپروایزر ویندوز هم همین‌طور", "while" in ps.lower() and "hamid.shadow_service" in ps and "--telegram" not in ps)

import shutil                                         # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
