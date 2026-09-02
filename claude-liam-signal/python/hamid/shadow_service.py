"""سرویس سایهٔ محلی — حلقهٔ همیشه‌روشن روی لپ‌تاپ حمید (قانون ۰۲، ۲ سپتامبر).

حمید: «فضایی می‌خوام که هیچ تأخیری در کارها به وجود نیاره» و «بعد از این
کار از لپ‌تاپ من به‌عنوان سرور استفاده کن (استارلینک)». کف واقعی
GitHub Actions ~۱۵ دقیقه است و هیچ تنظیمی آن را ثانیه‌ای نمی‌کند؛ راهش
همان است که قانون ۰۲ می‌گوید: یک فرایند پایتونِ همیشه‌روشن.

## مرزها (تغییرناپذیر بی‌دستور صریح حمید)

۱. **سایه، نه تولید.** خروجی فقط در `signals/shadow/` می‌نشیند
   (`LIAM9_SIGNALS_DIR`)؛ `signals/latest.json` و دفترهای تولید دست
   نمی‌خورند. زنجیرهٔ Actions همچنان مرجع عملیاتی است — «هیچ‌چیزِ کارکرده
   قبل از جایگزینِ اثبات‌شده خاموش نمی‌شود».
۲. **هیچ ارسالی.** فرمان اسکن هرگز `--telegram` ندارد و متغیرهای
   `TELEGRAM_*` از محیط زیرفرایند حذف می‌شوند — یک ناشر برای تلگرام
   (قانون ۰۵)، و آن ناشر این نیست.
۳. **LIVE_EXECUTION=false** در محیط زیرفرایند قفل است.
۴. **همان کد، همان دروازه‌ها.** این فایل هیچ تحلیلی نمی‌کند؛ فقط
   `scan.py` را (با همان `LIAM9_CANDLES=perp` و همان جهانِ ۲۰۰ نماد)
   با کادنس خودش می‌راند و ضربان می‌نویسد. عددِ تازه‌ای این‌جا ساخته
   نمی‌شود.
۵. **ضربان صادقانه.** `heartbeat.json` هر ۳۰ ثانیه: چند اسکن، آخرین اسکن
   چند ثانیه طول کشید، چه منبع کندلی، چند شکستِ پیاپی. پنل سن این فایل
   را نشان می‌دهد، نه ادعای «لحظه‌ای».

## مسیر ارتقا (فقط از راه قانون ۰۳)

دورهٔ سایه کنار Actions → مقایسهٔ سیگنال‌های سایه با تولید (همان
دروازه‌ها، کادنس تندتر: چند سیگنال زودتر دیده شد؟) → CI → تأیید حمید →
آن‌وقت تحویل تلگرام به این فرایند می‌رود و Actions به CI/بک‌فیل برمی‌گردد.
"""
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parent.parent
SHADOW = ROOT / "signals" / "shadow"
HEART = SHADOW / "heartbeat.json"

SCAN_INTERVAL_S = 300      # کادنس اسکن کامل (۲۰۰ نماد ~۳–۵ دقیقه)
HEARTBEAT_S = 30           # ضربان (قانون ۰۲: ۳۰ ثانیه)
MAX_BACKOFF_S = 1800
SYMBOLS, ROTATE, CORE, TFS = 200, 200, 30, "5m,15m"
FORBIDDEN_FLAGS = ("--telegram",)
STRIP_ENV_PREFIXES = ("TELEGRAM_", "TG_")


def scan_cmd(symbols=SYMBOLS, rotate=ROTATE, core=CORE, tf=TFS):
    """فرمان اسکن — عمداً بدون هیچ پرچم تحویل."""
    cmd = [sys.executable, str(PY / "scan.py"), "--symbols", str(symbols),
           "--rotate", str(rotate), "--core", str(core), "--tf", tf]
    assert not any(f in cmd for f in FORBIDDEN_FLAGS)
    return cmd


def env_for(base=None, shadow_dir=None):
    """محیط زیرفرایند: خروجی به سایه، پرپ اول، بدون اعتبارنامهٔ تلگرام، بدون لایو."""
    env = {k: v for k, v in dict(base if base is not None else os.environ).items()
           if not k.startswith(STRIP_ENV_PREFIXES)}
    env["LIAM9_SIGNALS_DIR"] = str(shadow_dir or SHADOW)
    env.setdefault("LIAM9_CANDLES", "perp")
    env["LIVE_EXECUTION"] = "false"
    env["LIAM9_SHADOW"] = "1"
    return env


def backoff(failures, base=SCAN_INTERVAL_S):
    """بعد از شکست‌های پیاپی فاصله دو برابر می‌شود تا سقف؛ صفر شکست = کادنس عادی."""
    return min(base * (2 ** max(0, int(failures))), MAX_BACKOFF_S)


def read_latest(shadow_dir=None):
    p = Path(shadow_dir or SHADOW) / "latest.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001 - هنوز اسکنی نشده
        return None
    return {"generated": d.get("generated"),
            "signals": len(d.get("signals") or []),
            "watch": len(d.get("watch") or []),
            "symbols": len(d.get("symbols") or []),
            "candle_src": d.get("source") or d.get("candle_src")}


def run_once(runner=None, shadow_dir=None, timeout=900, **kw):
    """یک اسکن سایه؛ نتیجه با کد خروج و مدت — هرگز استثنا به بیرون نمی‌دهد."""
    runner = runner or subprocess.run
    Path(shadow_dir or SHADOW).mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        r = runner(scan_cmd(**kw), env=env_for(shadow_dir=shadow_dir), cwd=str(PY),
                   capture_output=True, text=True, timeout=timeout)
        rc, tail = int(r.returncode), (r.stdout or "")[-600:]
    except Exception as e:                           # noqa: BLE001 - شکست ثبت می‌شود
        rc, tail = -1, f"{type(e).__name__}: {e}"
    return {"started": int(t0 * 1000), "duration_s": round(time.time() - t0, 1),
            "rc": rc, "ok": rc == 0, "tail": tail, "latest": read_latest(shadow_dir)}


def heartbeat(state, path=None):
    """ضربان روی دیسک — عکسِ صادقانهٔ وضعیت فرایند."""
    p = Path(path or HEART)
    p.parent.mkdir(parents=True, exist_ok=True)
    d = {"generated": int(time.time() * 1000), "mode": "shadow", "delivers": False,
         "host": platform.node(), "python": platform.python_version(),
         "tick": state.get("tick", 0), "scans": state.get("scans", 0),
         "failures_in_row": state.get("failures", 0),
         "uptime_s": round(time.time() - state.get("t0", time.time())),
         "scan_interval_s": state.get("interval", SCAN_INTERVAL_S),
         "next_scan_in_s": max(0, round(state.get("next_at", 0) - time.time())),
         "last_scan": state.get("last"),
         "candles": os.environ.get("LIAM9_CANDLES", "perp")}
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return d


def loop(iterations=None, sleep=time.sleep, runner=None, shadow_dir=None,
         heart_path=None, interval=SCAN_INTERVAL_S, hb=HEARTBEAT_S, now=time.time, **kw):
    """حلقهٔ اصلی: اسکن → ضربان هر ۳۰ث تا نوبت بعد → اسکن …

    `iterations` فقط برای آزمون (تعداد اسکن)؛ در تولید بی‌پایان است و
    سوپروایزر بیرونی (run.sh / run.ps1) بعد از هر مرگ دوباره بالا می‌آورد."""
    state = {"t0": now(), "tick": 0, "scans": 0, "failures": 0, "interval": interval,
             "next_at": now(), "last": None}
    done = 0
    while iterations is None or done < iterations:
        res = run_once(runner=runner, shadow_dir=shadow_dir, **kw)
        state["scans"] += 1
        state["failures"] = 0 if res["ok"] else state["failures"] + 1
        state["last"] = {k: v for k, v in res.items() if k != "tail"}
        wait = backoff(state["failures"], interval)
        state["next_at"] = now() + wait
        state["tick"] += 1
        heartbeat(state, heart_path)
        done += 1
        if iterations is not None and done >= iterations:
            break
        while now() < state["next_at"]:
            sleep(min(hb, max(0.0, state["next_at"] - now())))
            state["tick"] += 1
            heartbeat(state, heart_path)
    return state


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="سرویس سایهٔ محلی — بدون ارسال، بدون لایو")
    ap.add_argument("--interval", type=int, default=SCAN_INTERVAL_S)
    ap.add_argument("--symbols", type=int, default=SYMBOLS)
    ap.add_argument("--once", action="store_true", help="یک اسکن و خروج (آزمایش نصب)")
    a = ap.parse_args(argv)
    print(f"سرویس سایه · اسکن هر {a.interval}s · {a.symbols} نماد · خروجی {SHADOW} · بدون تلگرام", flush=True)
    if a.once:
        r = run_once(symbols=a.symbols, rotate=max(a.symbols, ROTATE))
        heartbeat({"t0": time.time(), "tick": 1, "scans": 1, "failures": 0 if r["ok"] else 1,
                   "interval": a.interval, "next_at": 0, "last": {k: v for k, v in r.items() if k != "tail"}})
        print(r["tail"])
        return 0 if r["ok"] else 1
    loop(interval=a.interval, symbols=a.symbols, rotate=max(a.symbols, ROTATE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
