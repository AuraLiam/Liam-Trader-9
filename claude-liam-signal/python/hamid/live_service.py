"""حلقهٔ زندهٔ محلی — ضربان ۳۰ ثانیه، طبق قانون ۰۲ (معماری v2.1).

GitHub Actions حلقهٔ بازار نیست؛ کفِ آن ~۳ دقیقه است. این سرویس روی ماشین
خود حمید می‌نشیند و مسیرهای حساس-به-ثانیه را هر ۳۰ ثانیه می‌زند:

  هر ۳۰ ثانیه  — شعله‌گیری ۱۵د (early_movers) + پایش دفتر انتظار پامپ؛
                 شلیک = سیگنال فوری تلگرام با علامت 🧠 و دلیل تاریخی.
  هر ۲ دقیقه   — همگام‌سازی گیت: pull نوشته‌های Actions؛ push دفترها تا
                 فرستندهٔ Actions همان سیگنال را دوباره نفرستد.
  هر ۳۰ دقیقه  — چرخهٔ کامل روش حمید (hamid.cycle) در پردازهٔ جدا، تا کل
                 خط تولید بدون ابر هم بچرخد؛ اگر گزارش تازهٔ Actions از
                 همگام‌سازی رسیده باشد، اجرای محلی تکراری انجام نمی‌شود.
                 بعد از هر چرخهٔ موفق، رادار اردر بلاک (hamid.ob_intel).
                 (چرخهٔ استراتژی است، نه پامپ — کادنس پامپ طبق قانون ۰۷
                 همان ۵ نوبت pump-review.yml می‌ماند.)

  رادار کامل پامپ این‌جا نیست (قانون ۰۷، ۲۰ اوت): ۵ نوبت در روز در
  pump-review.yml — پیوسته‌گردی پامپ با دفتر n=۳۰۹۶ و −۰.۱۸۰R نسخ شد.

Actions خاموش نمی‌شود (قانون: هیچ‌چیزِ کارکرده قبل از جایگزین اثبات‌شده
خاموش نمی‌شود) — پشتیبان می‌ماند: اگر این سرویس بمیرد، کف ۳ دقیقه‌ای
برمی‌گردد ولی سیستم زنده است. ضدتکرارِ دفترهای brain/ دوفرستادن را می‌گیرد.

آلارم (قانون حمید): تیکِ کندتر از SLA یا شکست پیاپی منبع داده → گزارش
فوری، حداکثر یک بار در ساعت برای هر عارضه.

اجرا:  python3 -m hamid.live_service          (از پوشهٔ python)
توقف:  Ctrl+C
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent

TICK_S = 30                 # ضربان — قانون ۰۲
SYNC_EVERY_S = 120          # گیت pull/push
UNI_EVERY_S = 600           # تازه‌سازی لیست ۳۰ ارز پرحجم
SLA_TICK_S = 60             # تیک بیش از این = آلارم
ALARM_COOLDOWN_S = 3600     # هر عارضه حداکثر یک آلارم در ساعت
CYCLE_EVERY_S = int(os.getenv("LIVE_CYCLE_EVERY_S", "1800"))   # چرخهٔ کامل
CYCLE_FRESH_S = 600         # گزارش تازه‌تر از این از Actions = اجرای محلی لازم نیست
CYCLE_SYMBOLS = os.getenv("LIVE_CYCLE_SYMBOLS", "200")
HB = ROOT / "signals" / "live-heartbeat.json"
LATEST = ROOT / "signals" / "hamid-latest.json"


def _env_file():
    """live.env در ریشهٔ ریپو — KEY=VALUE ساده؛ توکن تلگرام بدون ترمینال.
    (قانون ۰۵: سکرت در گیت نه — فایل در .gitignore است.)"""
    f = ROOT / "live.env"
    if not f.exists():
        return
    for ln in f.read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _git(*args, timeout=60):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=timeout)


class Alarm:
    def __init__(self):
        self.last = {}

    def fire(self, kind, msg):
        now = time.time()
        if now - self.last.get(kind, 0) < ALARM_COOLDOWN_S:
            return
        self.last[kind] = now
        text = f"🚨 حلقهٔ زنده — {kind}: {msg}"
        print(text, flush=True)
        try:
            import telegram as tg
            token, chat = tg.creds()
            if token:
                tg._post(token, "sendMessage",
                         {"chat_id": chat, "text": text})
        except Exception:                            # noqa: BLE001
            pass


class CycleRunner:
    """چرخهٔ کامل روش حمید، محلی و غیرمسدودکننده.

    چرخه در پردازهٔ جدا اجرا می‌شود تا ضربان ۳۰ ثانیه‌ای هیچ‌وقت پشت تحلیل
    سنگین نایستد (قانون ۰۲: هیچ سد سراسری‌ای روی مسیر لحظه‌ای). Actions
    خاموش نمی‌شود — اگر گزارش تازه‌اش از همگام‌سازی گیت رسیده باشد، اجرای
    محلی همان پنجره را تکرار نمی‌کند؛ ضدتکرارِ ارسال هم سر جایش است، پس
    بدترین حالتِ هم‌پوشانی فقط محاسبهٔ اضافه است، نه سیگنال دوباره.
    این چرخهٔ استراتژی است؛ کادنس پامپ (قانون ۰۷) از این‌جا عوض نمی‌شود.
    """

    def __init__(self):
        self.proc = None            # پردازهٔ چرخهٔ در حال اجرا
        self.ob = None              # رادار اردر بلاک بعد از چرخهٔ موفق
        self.last = 0.0             # شروع آخرین چرخهٔ محلی

    def _fresh_elsewhere(self, now):
        try:
            gen = json.loads(LATEST.read_text()).get("generated", 0) / 1000.0
            return 0 < now - gen < CYCLE_FRESH_S
        except Exception:                            # noqa: BLE001
            return False

    def _spawn(self, *mod_args):
        return subprocess.Popen([sys.executable, "-m", *mod_args],
                                cwd=HERE.parent)

    def poll(self, now):
        """یک قدم؛ اگر چیزی گفتنی بود، متن لاگ برمی‌گرداند وگرنه None."""
        if self.ob is not None and self.ob.poll() is not None:
            self.ob = None                           # درو، تا زامبی نماند
        if self.proc is not None:
            rc = self.proc.poll()
            if rc is None:
                return None                          # هنوز مشغول است
            self.proc = None
            if rc == 0:
                if self.ob is None:                  # مثل ورک‌فلو: بعد از چرخه
                    self.ob = self._spawn("hamid.ob_intel", "--symbols", "40")
                return "🔄 چرخهٔ محلی تمام شد + رادار اردر بلاک"
            return f"🔄 چرخهٔ محلی با کد {rc} برگشت — Actions پشتیبان است"
        if now - self.last < CYCLE_EVERY_S:
            return None
        self.last = now
        if self._fresh_elsewhere(now):
            return "🔄 گزارش تازه از Actions رسیده — چرخهٔ محلی لازم نشد"
        self.proc = self._spawn("hamid.cycle", "--mode", "auto",
                                "--symbols", str(CYCLE_SYMBOLS))
        return "🔄 چرخهٔ کامل روش حمید روی همین ماشین شروع شد"


def run():
    _env_file()
    from hamid.pump_radar import Kcache, early_movers
    from hamid import pump_watchlist
    import sources

    alarm = Alarm()
    cycles = CycleRunner()
    last_sync = last_uni = 0.0
    uni = []
    fails = 0
    n_tick = 0
    print(f"حلقهٔ زندهٔ محلی روشن شد — ضربان {TICK_S}س · "
          f"رادار پامپ فقط ۵ نوبت روزانه در Actions (قانون ۰۷) · "
          f"ریشه: {ROOT}", flush=True)

    while True:
        t0 = time.time()
        n_tick += 1
        try:
            if t0 - last_uni > UNI_EVERY_S or not uni:
                uni = [s["symbol"] for s in
                       sorted(sources.tickers(),
                              key=lambda x: -float(x["quoteVolume"] or 0))
                       if s["symbol"].endswith("USDT")][:30]
                last_uni = t0

            kc = Kcache()

            # ۱) دفتر انتظار — لحظهٔ حجم خوردن، نه ۳ دقیقه بعد
            ignited, notes = pump_watchlist.sweep(kc)
            if ignited:
                n = pump_watchlist.send_ignitions(ignited, kc)
                print(f"⚡ شلیک دفتر انتظار: "
                      + "، ".join(x['symbol'] for x in ignited)
                      + (f" ({n} تلگرام)" if n else " (بدون توکن — فقط پنل)"),
                      flush=True)
            for wn in notes:
                print(f"  دفتر انتظار: {wn}", flush=True)

            # ۲) شعله‌گیری — خبرِ زودتر از جدول گینرها
            ign = early_movers(kc, uni)
            if ign:
                print("  شعله‌ور: " + ", ".join(
                    f"{x['symbol']} {x['change_pct']:+}%" for x in ign[:5]),
                    flush=True)

            # ۳) رادار کامل این‌جا اجرا نمی‌شود — قانون ۰۷ (۲۰ اوت):
            # مرور پامپ دقیقاً ۵ نوبت در روز در pump-review.yml است؛ دفتر
            # آلارمِ پیوسته n=۳۰۹۶ با میانگین −۰.۱۸۰R (CI زیر صفر) این
            # کادنس را نسخ کرد. سهم حلقهٔ محلی فقط شلیکِ دفتر انتظار است
            # (سیستم جایگزینی که حمید ۱۷ اوت خواست) + شعله‌گیری برای لاگ.

            # ۴) چرخهٔ کامل محلی — کل خط تولید بدون ابر (پردازهٔ جدا)
            note = cycles.poll(t0)
            if note:
                print(note, flush=True)

            # ۵) همگام‌سازی گیت — دفترها مشترک‌اند با Actions
            if t0 - last_sync > SYNC_EVERY_S:
                _git("fetch", "origin", "main")
                _git("stash", "--include-untracked")
                _git("rebase", "origin/main")
                _git("stash", "pop")
                st = _git("status", "--porcelain",
                          "brain/", "signals/").stdout.strip()
                if st:
                    _git("add", "brain/", "signals/")
                    _git("commit", "-m", "حلقهٔ زنده — دفترها و سیگنال‌ها")
                    p = _git("push", "origin", "HEAD:main")
                    if p.returncode != 0:
                        _git("fetch", "origin", "main")
                        _git("rebase", "origin/main")
                        _git("push", "origin", "HEAD:main")
                last_sync = time.time()

            fails = 0
        except KeyboardInterrupt:
            raise
        except Exception as e:                       # noqa: BLE001
            fails += 1
            print(f"تیک {n_tick}: {type(e).__name__}: {e}", flush=True)
            if fails >= 3:
                alarm.fire("منبع داده",
                           f"{fails} تیک پیاپی شکست — {type(e).__name__}. "
                           "منابع جایگزین sources.py در حال چرخش‌اند؛ اگر "
                           "ادامه یافت اینترنت/فیلترینگ ماشین را چک کن.")

        dt = time.time() - t0
        try:
            HB.parent.mkdir(exist_ok=True)
            HB.write_text(json.dumps(
                {"ts": int(time.time() * 1000), "tick": n_tick,
                 "tick_s": round(dt, 1), "watch": len(pump_watchlist._load()),
                 "cycle_running": cycles.proc is not None,
                 "fails": fails}, ensure_ascii=False))
        except Exception:                            # noqa: BLE001
            pass
        if dt > SLA_TICK_S:
            alarm.fire("SLA", f"تیک {dt:.0f} ثانیه طول کشید (سقف {SLA_TICK_S}س)")
        time.sleep(max(1.0, TICK_S - dt))


def main():
    try:
        run()
    except KeyboardInterrupt:
        print("\nحلقهٔ زنده خاموش شد — Actions به‌عنوان پشتیبان فعال است.")


if __name__ == "__main__":
    main()
