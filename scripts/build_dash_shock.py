#!/usr/bin/env python3
"""ساخت فایل تک‌پارچهٔ داشبورد از منبع تست‌شده — نه کپی دستی.

داشبورد حمید یک فایل می‌خواهد که خودش کلاس `BaseStrategy` با `meta` داشته
باشد و به هیچ ماژول کناری وابسته نباشد. از طرف دیگر، منطق شوک و خط زنده
باید یک منبع حقیقت داشته باشند وگرنه نسخهٔ داشبورد از نسخهٔ تست‌شده جدا
می‌افتد و کسی خبردار نمی‌شود.

پس فایل داشبورد **تولید** می‌شود، نه نوشته: این اسکریپت `liam9_shock.py` و
`liam9_link.py` را (بدون بلاک اجرای مستقیمشان) با پوستهٔ کلاسی یکی می‌کند.
هر تغییری در منبع، با یک بار اجرای این اسکریپت به داشبورد می‌رسد؛ آزمون
`hamid/test_dash_shock.py` هم می‌سنجد که خروجی از منبع عقب نمانده باشد.

    python3 scripts/build_dash_shock.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "claude-liam-signal" / "python"
OUT = SRC / "liam9_shock_strategy.py"

HEADER = '''#!/usr/bin/env python3
"""لیام تریدر ۹ — موتور شوک + خط زندهٔ امن، آمادهٔ داشبورد (دستور حمید، ۱۹ اوت).

⚠️ این فایل **تولیدشده** است: `python3 scripts/build_dash_shock.py`
   منبع حقیقت `liam9_shock.py` و `liam9_link.py` است. دستی ویرایشش نکن.

همین فایل را کامل در اسلات «استراتژی» داشبورد بگذار. تک است (فقط
کتابخانهٔ استاندارد پایتون) و دو کلاس با `meta` دارد:

    Liam9ShockStrategy   — موتور شوک بیت‌کوین
    (کلاس اصلی؛ داشبورد همین را پیدا و بارگذاری می‌کند)

قانون کدشده:
  · شوک روی هر تایم (۱د/۵د/۱۵د/۱س/۴س) = بدنه ≥۲.۵×ATR + کف مطلق آن تایم
    + حجم ≥۲× میانه.
  · ورود روی **بازگشت به اردر بلاک ایمپالس** با اهرم ۵–۶ — نه وسط حرکت.
  · شکار پامپ با اهرم ۱۵ **فقط** با هر شش تأیید حجمی. یکی غایب = ممنوع.
  · اهرم ≤ min(خواسته، ۵۰÷استاپ٪، سقف داشبورد ۲۰). سایز از ریسک ۲٪
    می‌آید نه از اهرم.
  · خط زندهٔ امن: هر تصمیم و هر ردشدن با دلیل گزارش می‌شود؛ فرمان‌های
    امضاشده (HMAC) با seq و انقضا پذیرفته می‌شوند. بدون کلید = رد همه.

راه‌اندازی در داشبورد:
    ۱. فایل را در اسلات استراتژی بگذار.
    ۲. (اختیاری ولی توصیه‌شده) متغیر محیطی `LIAM9_LINK_SECRET` را همان
       چیزی بگذار که در گیت‌هاب گذاشتی، تا فرمان‌های زنده هم کار کنند.
    ۳. تمام. داشبورد کلاس را می‌سازد و `generate_signal(symbol)` صدا می‌زند.

خط فرمان (برای تست بیرون داشبورد):
    python3 liam9_shock_strategy.py BTCUSDT
    python3 liam9_shock_strategy.py --selftest
"""
'''

WRAPPER = '''

# ══════════════════════════════════════════════════════════════════════════
#  پوستهٔ کلاسی برای داشبورد
# ══════════════════════════════════════════════════════════════════════════
try:
    from strategy_base import BaseStrategy            # قالب رایج داشبوردها
except Exception:                                     # noqa: BLE001
    try:
        from base_strategy import BaseStrategy
    except Exception:                                 # noqa: BLE001
        class BaseStrategy:                           # پایهٔ خنثی
            pass


class RiskBook:
    """قوانین ریسک داشبورد حمید، کد شده — قبل از هر ورود جواب می‌دهد
    «چقدر، یا اصلاً نه»: ریسک ۲٪ · سقف روزانه ۵٪ · ۵ پوزیشن · اهرم ۲۰."""

    def __init__(self, equity=None, cfg=None):
        self.equity = float(equity) if equity else None
        self.cfg = {"risk_per_trade_pct": P["risk_per_trade_pct"],
                    "daily_loss_cap_pct": 5.0, "max_open_positions": 5,
                    "max_leverage": P["max_leverage_cap"]}
        self.cfg.update(cfg or {})
        self.day_loss_pct, self.open_positions = 0.0, 0

    def approve(self, stop_pct, lev):
        c = self.cfg
        if self.open_positions >= c["max_open_positions"]:
            return False, {"reason": f"سقف {c['max_open_positions']} پوزیشن پر است"}
        if self.day_loss_pct >= c["daily_loss_cap_pct"]:
            return False, {"reason": f"سقف ضرر روزانه {c['daily_loss_cap_pct']}٪ "
                                     "خورده — توقف خودکار"}
        lev = min(lev or 0, c["max_leverage"])
        if lev < 2:
            return False, {"reason": "اهرم مجاز کمتر از حداقل عملی"}
        info = {"leverage": lev}
        if self.equity:
            s = size_for(self.equity, stop_pct, lev)
            if s:
                info.update(s)
        left = c["daily_loss_cap_pct"] - self.day_loss_pct
        if left < c["risk_per_trade_pct"] * 2:
            info["warn"] = (f"فقط {left:.1f}٪ تا سقف روزانه مانده — جا برای "
                            f"{left / c['risk_per_trade_pct']:.1f} باخت کامل")
        return True, info

    def on_open(self):
        self.open_positions += 1

    def on_close(self, r_multiple):
        self.open_positions = max(0, self.open_positions - 1)
        if r_multiple < 0:
            self.day_loss_pct += abs(r_multiple) * self.cfg["risk_per_trade_pct"]

    def new_day(self):
        self.day_loss_pct = 0.0


class Liam9ShockStrategy(BaseStrategy):
    """شوک بیت‌کوین → اردر بلاک (اهرم ۵–۶) یا شکار پامپ (اهرم ۱۵ با تأیید ۱۰۰٪).

    هر فراخوانی: فرمان‌های امضاشده را می‌گیرد، تصمیم می‌سازد، و تصمیم یا
    دلیل ردش را روی خط زنده گزارش می‌دهد — پس حمید لحظه‌ای می‌بیند موتور
    چه دید و چرا نرفت."""

    meta = {
        "name": "لیام تریدر ۹ — شوک بیت‌کوین",
        "id": "liam9-shock",
        "version": P["version"],
        "author": "لیام تریدر ۹",
        "timeframes": TFS,
        "market": "crypto-futures",
        "risk_profile": {"risk_per_trade_pct": P["risk_per_trade_pct"],
                         "leverage_follow": [P["lev_follow_base"],
                                             P["lev_follow_max"]],
                         "leverage_pump_chase": P["lev_pump_chase"],
                         "max_leverage": P["max_leverage_cap"],
                         "stop_pct_range": [P["min_stop_pct"],
                                            P["max_stop_pct"]]},
        "description": ("شوک روی هر تایم (بدنه ≥۲.۵×ATR + کف تایم + حجم "
                        "≥۲× میانه) → ورود روی بازگشت به اردر بلاک ایمپالس "
                        "با اهرم ۵–۶؛ شکار پامپ با اهرم ۱۵ فقط با هر شش "
                        "تأیید حجمی. NO_SIGNAL تصمیم معتبر است."),
    }

    def __init__(self, *a, **kw):
        try:
            super().__init__(*a, **kw)
        except Exception:                             # noqa: BLE001
            pass
        self.equity = kw.get("equity")
        self.book = RiskBook(self.equity)
        self.link = Link(role="dashboard-shock", remote=True)
        self.tf = kw.get("timeframe") or "5m"
        self.btc_shocks = {}

    # ── ورودی‌های رایج داشبورد ───────────────────────────────────────
    def generate_signal(self, symbol, candles=None, timeframe=None, **kw):
        tf = timeframe or self.tf
        cmds = self.link.pull()
        if cmds:
            self.link.apply(cmds, params=P, risk=self.book.cfg)
        if self.link.paused:
            return {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf,
                    "why": "با فرمان امضاشده متوقف شده", "panel": "لیام تریدر ۹"}
        cd = candles if candles and len(candles) >= 60 else \\
            fetch_klines(symbol, tf, 200)
        if not cd:
            return {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf,
                    "why": "کندل نرسید — قانون ۱: حدس ممنوع"}
        sig = decide(symbol, cd, tf, equity=kw.get("equity") or self.equity,
                     btc_shock=self.btc_shocks.get(tf))
        if sig["action"] != "NO_SIGNAL":
            ok, info = self.book.approve(sig["stop_pct"], sig["leverage"])
            sig["risk"] = info
            if not ok:
                sig = {"action": "NO_SIGNAL", "symbol": symbol, "tf": tf,
                       "why": "ریسک اجازه نداد: " + info["reason"],
                       "panel": "لیام تریدر ۹"}
            else:
                sig["leverage"] = info["leverage"]
                if info.get("notional_usd"):
                    sig["size_usd"] = info["notional_usd"]
                    sig["margin_usd"] = info["margin_usd"]
                if info.get("warn"):
                    sig.setdefault("why", []).append("⚠️ " + info["warn"])
        self.link.event("SIGNAL" if sig["action"] != "NO_SIGNAL" else "SKIP",
                        {k: sig.get(k) for k in
                         ("symbol", "tf", "action", "mode", "entry", "sl",
                          "tp1", "leverage", "stop_pct", "volume_score", "why")})
        return sig

    def on_bar(self, symbol, candles=None, **kw):
        return self.generate_signal(symbol, candles=candles, **kw)

    def run(self, symbol, **kw):
        return self.generate_signal(symbol, **kw)

    # ── بستر: شوک خود بیت‌کوین، برای همهٔ نمادها ─────────────────────
    def refresh_btc(self):
        """یک بار در هر چرخه صدا بزن؛ بعدش همهٔ نمادها بسترشان را دارند."""
        self.btc_shocks = scan_btc()
        self.link.heartbeat({"btc_shocks": {tf: {"dir": s["dir"],
                                                 "pct": s["move_pct"],
                                                 "vol": s["vol_mult"]}
                                            for tf, s in self.btc_shocks.items()}})
        return self.btc_shocks

    # ── مدیریت معامله: نردبان تریل حمید ──────────────────────────────
    def manage_position(self, position, candle):
        long = position["action"] == "LONG"
        sl = position.get("sl_current", position["sl"])
        hi, lo = candle["h"], candle["l"]
        if (long and lo <= sl) or (not long and hi >= sl):
            return {"event": "STOP", "price": sl}
        if (long and hi >= position["tp1"]) or (not long and lo <= position["tp1"]):
            return {"event": "TARGET", "price": position["tp1"]}
        t1 = position["trail"]["step1_at"]
        if (long and hi >= t1) or (not long and lo <= t1):
            be = position["entry"] * (1.0015 if long else 0.9985)
            if (long and sl < be) or (not long and sl > be):
                return {"event": "TRAIL", "sl": be}
        return {"event": "HOLD"}

    # ── ممیزی: موتور ریسک داشبورد با این استراتژی تداخل دارد؟ ────────
    def audit(self, risk=None):
        out = {"contract": self.meta["risk_profile"], "conflicts": [],
               "notes": []}
        if risk is None:
            out["notes"].append("آبجکت ریسک داده نشد — بررسی دستی لازم است")
            return out
        def dig(*names):
            for n in names:
                if isinstance(risk, dict) and n in risk:
                    return risk[n]
                if hasattr(risk, n):
                    return getattr(risk, n)
            return None
        lev = dig("leverage_cap", "max_leverage", "maxLeverage")
        if lev is not None and lev < P["lev_pump_chase"]:
            out["notes"].append(
                f"سقف اهرم داشبورد {lev}× زیر ۱۵× است — شکار پامپ با همان "
                "سقف اجرا می‌شود (سایز کوچک‌تر، لبه دست‌نخورده)")
        ms = dig("min_stop_pct", "min_stop_distance_pct")
        if ms is not None and ms > P["max_stop_pct"]:
            out["conflicts"].append(
                f"کف استاپ داشبورد {ms}٪ بالاتر از سقف {P['max_stop_pct']}٪ "
                "این موتور — همهٔ ستاپ‌ها در سکوت رد می‌شوند")
        fee = dig("fee_pct", "taker_fee", "commission")
        if fee is not None and float(fee) < P["fee_round_trip_pct"] / 3:
            out["conflicts"].append(
                f"کارمزد داشبورد {fee}٪ خیلی پایین‌تر از واقعیت "
                f"({P['fee_round_trip_pct']}٪) — RR خوش‌بین می‌شود")
        return out


def _dash_selftest():
    _selftest()                                        # موتور شوک
    _link_selftest()                                   # خط زنده
    s = Liam9ShockStrategy(equity=1000)
    assert isinstance(s.meta, dict) and s.meta.get("id") == "liam9-shock"
    for ep in ("generate_signal", "on_bar", "run", "manage_position", "audit"):
        assert callable(getattr(s, ep)), ep
    # تصمیم روی کندل تزریقی، بدون شبکه
    base = [100.0 + (i % 3) * 0.02 for i in range(80)]
    cd = [{"t": i * 300000, "o": p, "h": p * 1.002, "l": p * 0.998, "c": p,
           "v": 100.0} for i, p in enumerate(base)]
    cd.append({"t": 80 * 300000, "o": 100.05, "h": 100.08, "l": 99.90,
               "c": 99.92, "v": 90})
    cd.append({"t": 81 * 300000, "o": 99.92, "h": 101.60, "l": 99.90,
               "c": 101.50, "v": 700})
    r = s.generate_signal("BTCUSDT", candles=cd, timeframe="5m")
    assert r["action"] == "LONG" and r["mode"] == "PUMP_CHASE", r
    assert r["leverage"] <= P["max_leverage_cap"] and r.get("size_usd"), r
    # سقف پوزیشن داشبورد واقعاً جلو می‌گیرد
    for _ in range(5):
        s.book.on_open()
    r2 = s.generate_signal("BTCUSDT", candles=cd, timeframe="5m")
    assert r2["action"] == "NO_SIGNAL" and "پوزیشن" in r2["why"], r2
    # ممیزی تداخل
    a = s.audit({"min_stop_pct": 5.0, "max_leverage": 20})
    assert a["conflicts"], a
    print("✓ خودآزمایی فایل داشبورد گذشت — کلاس، meta، ریسک، خط زنده")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _dash_selftest()
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        sym = args[0] if args else "BTCUSDT"
        st = Liam9ShockStrategy(equity=1000)
        print("شوک بیت‌کوین:", json.dumps(st.refresh_btc(), ensure_ascii=False)[:400])
        for tf in TFS:
            out = st.generate_signal(sym, timeframe=tf)
            print(tf, json.dumps(out, ensure_ascii=False)[:220])
'''


def strip(src_text, drop_docstring=True):
    """بدنهٔ ماژول بدون شبنگ، بدون داک‌استرینگ، بدون بلاک اجرای مستقیم."""
    t = src_text
    t = re.sub(r"^#![^\n]*\n", "", t)
    if drop_docstring:
        t = re.sub(r'^"""(?:.|\n)*?"""\n', "", t, count=1)
    t = re.split(r'\nif __name__ == "__main__":', t)[0]
    return t.rstrip() + "\n"


def build():
    shock = strip((SRC / "liam9_shock.py").read_text())
    link = strip((SRC / "liam9_link.py").read_text())
    # نام خودآزمایی‌ها با هم برخورد می‌کنند؛ خط زنده تغییر نام می‌دهد.
    link = link.replace("def _selftest(", "def _link_selftest(")
    # مسیر فایل‌های خط زنده در داشبورد ممکن است وجود نداشته باشد؛
    # ریشهٔ محلی جایگزین امن است (بدون هیچ فرض دربارهٔ ساختار پوشه).
    link = link.replace(
        'ROOT = Path(__file__).resolve().parents[2]',
        'ROOT = Path(__file__).resolve().parent\n'
        'if not (ROOT / "signals").exists():\n'
        '    ROOT = Path(".").resolve()')
    body = HEADER + "\n" + shock + "\n\n" + link + WRAPPER
    OUT.write_text(body)
    print(f"ساخته شد: {OUT.relative_to(ROOT)} ({len(body.splitlines())} خط)")
    return OUT


if __name__ == "__main__":
    build()
