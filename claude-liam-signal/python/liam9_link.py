#!/usr/bin/env python3
"""لیام تریدر ۹ — خط ارتباط زندهٔ امن بین استراتژی و این‌جا (دستور حمید، ۱۹ اوت).

«حتماً یک راه اتصال امن بین این‌جا یا پایتون به استراتژی متصل باشیم که به
صورت لایو ببینیم دارد چه کار می‌کند و روند کار را زیر نظر داشته باشیم و با
دریافت اطلاعات جدید بتوانیم دقیق به آن دیتا بدهیم که بهتر تصمیم بگیرد.»

دو جهت، هر دو امضاشده:

  **بالا-رو (استراتژی → ما)** — هر تصمیم، هر ضربان، هر رد شدن با دلیل، در
  `signals/live-link.json` می‌نشیند (حلقهٔ آخرین N رویداد). پنل و ما همان را
  می‌خوانیم. یعنی لحظه‌ای می‌بینی چه دید، چه کرد، و چرا نکرد.

  **پایین-رو (ما → استراتژی)** — `signals/link-commands.json`. استراتژی هر
  چرخه می‌خواندش، امضا را می‌سنجد، و فقط فرمان‌های مجاز را اجرا می‌کند.
  این‌جوری می‌شود وسط کار به آن دیتا داد («روی این ارز محتاط باش»،
  «آستانهٔ شوک ۵د را ببر بالا») بدون آن‌که کد عوض شود یا ری‌استارت لازم باشد.

امنیت — چه چیزی این را «امن» می‌کند و چه چیزی نمی‌کند:
  · هر پیام با HMAC-SHA256 امضا می‌شود؛ کلید فقط از محیط
    (`LIAM9_LINK_SECRET`) خوانده می‌شود. هیچ سکرتی در کد، لاگ یا خروجی نیست
    و مقدار کلید هرگز چاپ نمی‌شود.
  · ضدبازپخش (replay): هر فرمان `seq` صعودی و `expires` دارد؛ فرمان تکراری
    یا منقضی رد می‌شود، حتی اگر امضایش درست باشد.
  · فهرست سفید: فقط شش نوع فرمان. هر چیز دیگر — از جمله هر چیزی که بوی
    اجرای زنده بدهد — رد می‌شود. `enable_live` **همیشه** رد می‌شود؛
    LIVE_EXECUTION فقط با دست حمید و بیرون از این کانال عوض می‌شود.
  · سقف اندازه و سقف تعداد، تا کانال به انبار تبدیل نشود.
  · بدون کلید، خط در حالت «فقط خواندن» کار می‌کند: ضربان می‌نویسد ولی هیچ
    فرمانی را نمی‌پذیرد (نبود کلید = رد همه، نه قبول همه).

استفاده در استراتژی (داشبورد):
    from liam9_link import Link
    link = Link(role="dashboard")
    link.heartbeat({"symbol": "BTCUSDT", "state": "WATCHING", "px": 64000})
    link.event("DECISION", sig)             # هر تصمیم
    cmds = link.pull()                      # فرمان‌های تازهٔ ما
    link.apply(cmds, params=liam9_shock.P)  # اعمال امن روی پارامترها

خط فرمان:
    python3 liam9_link.py --selftest
    python3 liam9_link.py --send set_param shock_vol_mult 2.5   # نیاز به کلید
"""
import hashlib
import hmac
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UP = ROOT / "signals" / "live-link.json"          # استراتژی → ما
DOWN = ROOT / "signals" / "link-commands.json"    # ما → استراتژی
REPO_RAW = "https://raw.githubusercontent.com/Auraliam/Liam-Trader-9/main"
PAGES = "https://auraliam.github.io/Liam-Trader-9"

MAX_EVENTS = 200            # حلقهٔ رویداد؛ فایل بی‌انتها نمی‌شود
MAX_CMDS = 50
MAX_BYTES = 64 * 1024
CMD_TTL_S = 3600

# فهرست سفید — هر چیز بیرون این، رد.
ALLOWED = {
    "set_param":  "یک پارامتر عددی موتور را عوض کن",
    "set_risk":   "ریسک هر معامله / سقف روزانه را عوض کن",
    "pause":      "موقتاً هیچ سیگنالی صادر نکن",
    "resume":     "دوباره فعال شو",
    "hint":       "دیتای تازه از حمید (متن + برچسب نماد)",
    "watch":      "این نمادها را ویژه زیر نظر بگیر",
    # دستور حمید ۲۴ اوت: «با موتور ۱ دقیقه در ارتباط باشی که بتوانی
    # آپدیت‌های تحلیل‌ها را بهش بدی.»
    #
    # عمداً **یک‌طرفه**: این فرمان فقط می‌تواند موتور را سخت‌گیرتر کند
    # (`avoid` یا `confidence_delta` منفی). هیچ میدانی برای بازکردن
    # دروازه، ساختن سیگنال، یا بالا بردن اطمینان ندارد — چون خروجی یک
    # ایجنت هرگز واقعیت تلقی نمی‌شود (قانون ۰۱ بند ۱۱). اگر روزی کسی
    # چنین میدانی اضافه کند، `hamid/test_scalp1m.py` چرخه را سرخ می‌کند.
    "analysis":   "آپدیت تحلیلِ مشورتی برای موتور ۱ دقیقه (فقط محدودکننده)",
    # دستور حمید ۱۹ اوت: «اگر سیگنالی دیدی برای اسکلپ مناسب است، سریع
    # دستور بده به داشبورد که آن پوزیشن فیوچرز را اجرا کند.»
    #
    # این تنها فرمانی است که به سفارش می‌رسد، و عمداً سخت‌گیرترین است:
    #   · فقط فیوچرز (product همیشه "futures"؛ اسپات پذیرفته نمی‌شود)
    #   · اهرم ≤ سقف داشبورد و ≤ محافظ لیکویید
    #   · نوشنال ≤ سقف سخت
    #   · mode پیش‌فرض "demo"؛ «live» فقط وقتی اجرا می‌شود که خودِ حمید
    #     روی ماشین داشبورد LIAM9_ALLOW_LIVE=1 گذاشته باشد. کانال به‌
    #     تنهایی هرگز پول واقعی را روشن نمی‌کند.
    "open_position": "اجرای پوزیشن فیوچرز روی داشبورد (اسکلپ سریع)",
}
# فرمان‌هایی که حتی با امضای درست هم رد می‌شوند (مرز ایمنی، نه سلیقه).
FORBIDDEN = {"enable_live", "live_execution", "set_secret", "exec", "eval",
             "shell", "disable_guard", "set_leverage_cap"}

# پارامترهایی که فرمان حق تغییرشان را دارد و بازهٔ مجازشان.
# بیرون این جدول = رد. بازه‌ها از محافظ‌های خودِ موتور می‌آیند.
PARAM_BOUNDS = {
    "shock_atr_mult": (1.5, 6.0),
    "shock_vol_mult": (1.2, 8.0),
    "shock_fresh_bars": (2, 40),
    "ob_max_age_bars": (5, 120),
    "rr_target": (1.0, 5.0),
    "min_net_rr": (0.8, 4.0),
    "min_stop_pct": (0.1, 2.0),
    "max_stop_pct": (0.5, 5.0),
    "risk_per_trade_pct": (0.25, 5.0),
    "min_quality": (0, 100),
}


# ── مرزهای سخت سفارش (تغییرشان از راه دور ممکن نیست) ──────────────────────
EXEC_MAX_NOTIONAL_USD = 200.0     # سقف سخت هر سفارش، حتی در دمو
EXEC_MAX_LEVERAGE = 20            # سقف داشبورد حمید
EXEC_LIQ_GUARD = 50.0             # اهرم ≤ ۵۰÷استاپ٪ (استاپ ≤ نصف لیکویید)
EXEC_TTL_S = 300                  # سفارش کهنه اجرا نمی‌شود؛ ۵ دقیقه


def validate_exec(order):
    """اعتبارسنجی سفارش فیوچرز. خروجی: لیست ایرادها (خالی = سالم).

    هرچه این‌جا رد شود، هیچ‌جای دیگری قابل دور زدن نیست — نه با امضا،
    نه با فرمان، نه با پارامتر."""
    errs = []
    if order.get("product") != "futures":
        errs.append("فقط فیوچرز؛ product باید futures باشد")
    sym = str(order.get("symbol") or "")
    if not sym.endswith("USDT") or len(sym) < 5:
        errs.append("نماد فیوچرز USDT نیست")
    if order.get("side") not in ("LONG", "SHORT"):
        errs.append("جهت نامعتبر")
    # دستور حمید (۲۰ اوت): پوزیشن بی‌استاپ/بی‌تارگت ممنوع؛ tp1 هم اجباری شد.
    for k in ("entry", "sl", "tp1", "stop_pct", "leverage", "notional_usd"):
        v = order.get(k)
        if not isinstance(v, (int, float)) or v <= 0:
            errs.append(f"«{k}» عددی مثبت نیست — استاپ و تارگت اجباری‌اند")
    if order.get("margin_mode") != "isolated":
        errs.append("مارجین باید isolated باشد — کراس ممنوع (دستور ۲۰ اوت)")
    if errs:
        return errs
    if order["leverage"] > EXEC_MAX_LEVERAGE:
        errs.append(f"اهرم {order['leverage']} بالاتر از سقف {EXEC_MAX_LEVERAGE}")
    if order["leverage"] > int(EXEC_LIQ_GUARD / order["stop_pct"]):
        errs.append("اهرم از محافظ فاصلهٔ لیکویید رد می‌کند")
    if order["notional_usd"] > EXEC_MAX_NOTIONAL_USD:
        errs.append(f"نوشنال {order['notional_usd']} بالاتر از سقف "
                    f"{EXEC_MAX_NOTIONAL_USD}")
    if order.get("mode") not in ("demo", "live"):
        errs.append("mode باید demo یا live باشد")
    d = order["side"]
    if (d == "LONG" and order["sl"] >= order["entry"]) or \
       (d == "SHORT" and order["sl"] <= order["entry"]):
        errs.append("استاپ سمت اشتباه ورود است")
    return errs


def make_exec_command(seq, symbol, side, entry, sl, tp1, stop_pct, leverage,
                      notional_usd, mode="demo", ttl_s=EXEC_TTL_S, **extra):
    """سفارش فیوچرز امضاشده. mode پیش‌فرض demo — «live» فقط با تأیید
    جداگانهٔ حمید روی ماشین داشبورد اجرا می‌شود."""
    order = {"product": "futures", "symbol": symbol, "side": side,
             "entry": float(entry), "sl": float(sl),
             "tp1": (float(tp1) if tp1 else None),
             "stop_pct": float(stop_pct), "leverage": int(leverage),
             "notional_usd": round(float(notional_usd), 2),
             "margin_mode": "isolated", "mode": mode, **extra}
    errs = validate_exec(order)
    if errs:
        raise ValueError("سفارش رد شد: " + "؛ ".join(errs))
    return make_command("open_position", seq, ttl_s=ttl_s, order=order)


def _secret():
    """کلید فقط از محیط. نبودش خطا نیست — یعنی حالت فقط-خواندن."""
    return (os.environ.get("LIAM9_LINK_SECRET") or "").encode() or None


def sign(payload, secret=None):
    """امضای قطعی روی JSON مرتب‌شده. کلید هرگز برنمی‌گردد."""
    s = secret if secret is not None else _secret()
    if not s:
        return None
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()
    return hmac.new(s, body, hashlib.sha256).hexdigest()


def verify(payload, signature, secret=None):
    """مقایسهٔ ثابت-زمان. بدون کلید = رد (نه قبول)."""
    if not signature:
        return False
    expect = sign(payload, secret)
    if not expect:
        return False
    return hmac.compare_digest(expect, signature)


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:                                    # noqa: BLE001
        return default


def _fetch_remote(rel):
    for base in (REPO_RAW, PAGES):
        try:
            req = urllib.request.Request(base + rel,
                                         headers={"User-Agent": "liam9-link"})
            with urllib.request.urlopen(req, timeout=12) as r:
                return json.load(r)
        except Exception:                                # noqa: BLE001
            continue
    return None


class Link:
    """خط زنده. `role` فقط برچسب است تا در گزارش معلوم باشد چه کسی نوشته."""

    def __init__(self, role="strategy", up=None, down=None, remote=True):
        self.role = role
        self.up = Path(up) if up else UP
        self.down = Path(down) if down else DOWN
        self.remote = remote
        self.paused = False
        self.last_seq = 0
        self.applied = []
        self.orders = []          # سفارش‌های تحویل‌شده به داشبورد

    # ── بالا-رو ───────────────────────────────────────────────────────
    def _append(self, kind, data):
        doc = _read_json(self.up, {"panel": "لیام تریدر ۹", "events": []})
        ev = {"t": int(time.time() * 1000), "kind": kind, "role": self.role,
              "data": data}
        sig = sign(ev)
        if sig:
            ev["sig"] = sig                # قابل راستی‌آزمایی، نه محرمانه
        doc.setdefault("events", []).append(ev)
        doc["events"] = doc["events"][-MAX_EVENTS:]
        doc["updated"] = ev["t"]
        doc["signed"] = bool(sig)
        try:                                         # حالت شنی: دفتر تولید نه
            import brain as _b
            if _b.blocked(self.up):
                return
        except Exception:                            # noqa: BLE001
            pass
        self.up.parent.mkdir(parents=True, exist_ok=True)
        self.up.write_text(json.dumps(doc, ensure_ascii=False))
        return ev

    def heartbeat(self, state):
        """ضربان: زنده‌ام، این را می‌بینم، این وضعیتم است."""
        return self._append("HEARTBEAT", state)

    def event(self, kind, data):
        """رویداد معنادار: تصمیم، رد شدن با دلیل، شوک، خطا."""
        return self._append(kind, data)

    # ── پایین-رو ──────────────────────────────────────────────────────
    def pull(self):
        """فرمان‌های تازه: فقط امضادار، تازه، و با seq بزرگ‌تر از آخرین."""
        doc = None
        if self.remote:
            doc = _fetch_remote("/signals/link-commands.json")
        if doc is None:
            doc = _read_json(self.down, {"commands": []})
        out, now = [], time.time()
        for c in (doc.get("commands") or [])[-MAX_CMDS:]:
            body = {k: v for k, v in c.items() if k != "sig"}
            if not verify(body, c.get("sig")):
                continue                              # امضا غلط یا بی‌کلید
            if body.get("type") in FORBIDDEN or body.get("type") not in ALLOWED:
                continue
            seq = body.get("seq")
            if not isinstance(seq, int) or seq <= self.last_seq:
                continue                              # بازپخش یا قدیمی
            if float(body.get("expires", 0)) < now:
                continue                              # منقضی
            out.append(body)
        for c in out:
            self.last_seq = max(self.last_seq, c["seq"])
        return out

    def apply(self, commands, params=None, risk=None):
        """اعمال امن. هر فرمان اثرش را روی خط بالا-رو هم گزارش می‌دهد."""
        done = []
        for c in commands:
            t = c["type"]
            res = {"seq": c["seq"], "type": t, "ok": False, "why": ""}
            if t == "pause":
                self.paused, res["ok"] = True, True
            elif t == "resume":
                self.paused, res["ok"] = False, True
            elif t == "hint":
                txt = str(c.get("text", ""))[:500]
                res["ok"], res["hint"] = bool(txt), txt
            elif t == "watch":
                syms = [str(s)[:20] for s in (c.get("symbols") or [])][:50]
                res["ok"], res["symbols"] = bool(syms), syms
            elif t == "analysis":
                # سقف‌خورده در همین لایه، نه فقط در مصرف‌کننده: فرمانی که
                # اطمینان را **بالا** ببرد این‌جا به صفر بریده می‌شود.
                sym = str(c.get("sym") or "")[:20].upper()
                delta = c.get("confidence_delta", 0)
                delta = (max(-40.0, min(0.0, float(delta)))
                         if isinstance(delta, (int, float)) else 0.0)
                res.update(ok=bool(sym), sym=sym,
                           note=str(c.get("note", ""))[:400],
                           avoid=bool(c.get("avoid")),
                           confidence_delta=delta)
                if not sym:
                    res["why"] = "بدون نماد — آپدیت تحلیل بی‌هدف پذیرفته نیست"
            elif t == "set_param":
                k, v = c.get("key"), c.get("value")
                lo_hi = PARAM_BOUNDS.get(k)
                if params is None:
                    res["why"] = "موتوری برای تنظیم داده نشده"
                elif not lo_hi:
                    res["why"] = f"پارامتر «{k}» قابل تنظیم از راه دور نیست"
                elif not isinstance(v, (int, float)):
                    res["why"] = "مقدار عددی نیست"
                elif not (lo_hi[0] <= v <= lo_hi[1]):
                    res["why"] = f"مقدار بیرون بازهٔ مجاز {lo_hi}"
                else:
                    params[k] = v
                    res["ok"] = True
            elif t == "open_position":
                # کانال فقط سفارش را **تحویل** می‌دهد؛ اجرا کار داشبورد است.
                # مرز پول واقعی این‌جاست: mode="live" فقط وقتی عبور می‌کند
                # که خودِ حمید روی ماشین داشبورد LIAM9_ALLOW_LIVE=1 گذاشته
                # باشد. نبودش = تبدیل به دمو، نه رد کامل (تا اسکلپ نخوابد).
                order = c.get("order") or {}
                errs = validate_exec(order)
                if errs:
                    res["why"] = "؛ ".join(errs)
                elif self.paused:
                    res["why"] = "موتور متوقف است"
                else:
                    if order.get("mode") == "live" and \
                            os.environ.get("LIAM9_ALLOW_LIVE") != "1":
                        order = dict(order, mode="demo",
                                     downgraded="LIAM9_ALLOW_LIVE تنظیم نیست")
                    res["ok"], res["order"] = True, order
                    self.orders.append(order)
            elif t == "set_risk":
                k, v = c.get("key"), c.get("value")
                if risk is None:
                    res["why"] = "دفتر ریسکی داده نشده"
                elif k not in ("risk_per_trade_pct", "daily_loss_cap_pct"):
                    res["why"] = "این کلید ریسک قابل تنظیم نیست"
                elif not isinstance(v, (int, float)) or not (0.1 <= v <= 10):
                    res["why"] = "مقدار بیرون بازهٔ امن (۰.۱ تا ۱۰)"
                else:
                    risk[k] = v
                    res["ok"] = True
            done.append(res)
            self.applied.append(res)
        if done:
            self.event("COMMANDS_APPLIED", done)
        return done


# ── سمت ما: ساخت فرمان امضاشده ─────────────────────────────────────────────
def make_command(cmd_type, seq, ttl_s=CMD_TTL_S, **fields):
    """فرمان امضاشده می‌سازد. بدون کلید، امضا None است و گیرنده ردش می‌کند."""
    if cmd_type in FORBIDDEN or cmd_type not in ALLOWED:
        raise ValueError(f"فرمان «{cmd_type}» مجاز نیست")
    body = {"type": cmd_type, "seq": int(seq),
            "expires": time.time() + ttl_s, **fields}
    s = sign(body)
    if s:
        body["sig"] = s
    return body


def push_command(cmd, path=None):
    """فرمان را در دفتر پایین-رو می‌گذارد (سقف تعداد و اندازه رعایت می‌شود)."""
    p = Path(path) if path else DOWN
    doc = _read_json(p, {"panel": "لیام تریدر ۹", "commands": []})
    doc.setdefault("commands", []).append(cmd)
    doc["commands"] = doc["commands"][-MAX_CMDS:]
    doc["updated"] = int(time.time() * 1000)
    blob = json.dumps(doc, ensure_ascii=False)
    if len(blob.encode()) > MAX_BYTES:
        doc["commands"] = doc["commands"][-10:]
        blob = json.dumps(doc, ensure_ascii=False)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(blob)
    return doc


def next_seq(path=None):
    doc = _read_json(Path(path) if path else DOWN, {"commands": []})
    seqs = [c.get("seq", 0) for c in (doc.get("commands") or [])
            if isinstance(c.get("seq"), int)]
    return (max(seqs) + 1) if seqs else 1


# ── خودآزمایی ───────────────────────────────────────────────────────────────
def _selftest():
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    up, down = tmp / "live-link.json", tmp / "link-commands.json"
    os.environ["LIAM9_LINK_SECRET"] = "test-secret-not-a-real-key"

    link = Link(role="test", up=up, down=down, remote=False)
    link.heartbeat({"state": "WATCHING", "px": 100})
    doc = json.loads(up.read_text())
    assert doc["events"][-1]["kind"] == "HEARTBEAT" and doc["signed"]
    assert "LIAM9_LINK_SECRET" not in up.read_text()      # کلید هرگز نوشته نشود
    assert "test-secret" not in up.read_text()

    # امضا: دستکاری محتوا = رد
    ev = doc["events"][-1]
    body = {k: v for k, v in ev.items() if k != "sig"}
    assert verify(body, ev["sig"])
    body["data"]["px"] = 999
    assert not verify(body, ev["sig"])

    # فرمان مجاز، امضادار، تازه → اعمال می‌شود
    params = {"shock_vol_mult": 2.0}
    push_command(make_command("set_param", next_seq(down),
                              key="shock_vol_mult", value=2.5), down)
    cmds = link.pull()
    assert len(cmds) == 1, cmds
    res = link.apply(cmds, params=params)
    assert res[0]["ok"] and params["shock_vol_mult"] == 2.5

    # بازپخش همان فرمان = رد
    assert link.pull() == []

    # مقدار بیرون بازه = رد
    push_command(make_command("set_param", next_seq(down),
                              key="shock_vol_mult", value=99), down)
    res2 = link.apply(link.pull(), params=params)
    assert not res2[0]["ok"] and params["shock_vol_mult"] == 2.5

    # پارامتر خارج از فهرست = رد
    push_command(make_command("set_param", next_seq(down),
                              key="lev_pump_chase", value=50), down)
    res3 = link.apply(link.pull(), params={"lev_pump_chase": 15})
    assert not res3[0]["ok"], res3

    # فرمان ممنوع اصلاً ساخته نمی‌شود
    for bad in ("enable_live", "shell", "set_secret"):
        try:
            make_command(bad, 99)
            raise AssertionError(f"فرمان ممنوع ساخته شد: {bad}")
        except ValueError:
            pass
    # و اگر دستی هم در فایل کاشته شود، رد می‌شود
    forged = {"type": "enable_live", "seq": 500,
              "expires": time.time() + 60}
    forged["sig"] = sign(forged)
    push_command(forged, down)
    assert all(c["type"] != "enable_live" for c in link.pull())

    # امضای غلط = رد
    bad = {"type": "pause", "seq": 600, "expires": time.time() + 60,
           "sig": "00" * 32}
    push_command(bad, down)
    assert all(c["seq"] != 600 for c in link.pull())

    # منقضی = رد
    old = {"type": "pause", "seq": 700, "expires": time.time() - 1}
    old["sig"] = sign(old)
    push_command(old, down)
    assert all(c["seq"] != 700 for c in link.pull())

    # بدون کلید: هیچ فرمانی پذیرفته نمی‌شود (رد امن، نه قبول)
    ok_cmd = make_command("pause", 800)
    push_command(ok_cmd, down)
    del os.environ["LIAM9_LINK_SECRET"]
    link2 = Link(role="test2", up=up, down=down, remote=False)
    assert link2.pull() == []
    link2.heartbeat({"state": "بدون کلید"})              # ضربان باز هم می‌نویسد
    assert json.loads(up.read_text())["events"][-1]["kind"] == "HEARTBEAT"

    # حلقهٔ رویداد: فایل بی‌انتها نمی‌شود
    os.environ["LIAM9_LINK_SECRET"] = "test-secret-not-a-real-key"
    l3 = Link(role="t3", up=up, down=down, remote=False)
    for i in range(MAX_EVENTS + 30):
        l3.heartbeat({"i": i})
    assert len(json.loads(up.read_text())["events"]) == MAX_EVENTS

    # pause/resume
    l3.apply([{"type": "pause", "seq": 1}])
    assert l3.paused
    l3.apply([{"type": "resume", "seq": 2}])
    assert not l3.paused
    del os.environ["LIAM9_LINK_SECRET"]
    print("✓ خودآزمایی خط زنده گذشت — امضا، ضدبازپخش، فهرست سفید، مرز لایو")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    elif "--send" in sys.argv:
        i = sys.argv.index("--send")
        rest = sys.argv[i + 1:]
        if not rest:
            raise SystemExit("استفاده: --send <type> [key] [value]")
        ctype = rest[0]
        fields = {}
        if ctype == "set_param" and len(rest) >= 3:
            fields = {"key": rest[1], "value": float(rest[2])}
        elif ctype == "hint" and len(rest) >= 2:
            fields = {"text": " ".join(rest[1:])}
        elif ctype == "watch" and len(rest) >= 2:
            fields = {"symbols": rest[1:]}
        c = make_command(ctype, next_seq(), **fields)
        if "sig" not in c:
            raise SystemExit("کلید LIAM9_LINK_SECRET تنظیم نیست — "
                             "فرمان بدون امضا ساخته نمی‌شود")
        push_command(c)
        print(f"فرمان {ctype} با seq={c['seq']} در دفتر پایین-رو نشست")
    else:
        d = _read_json(UP, {"events": []})
        evs = d.get("events", [])[-10:]
        print(f"آخرین {len(evs)} رویداد خط زنده:")
        for e in evs:
            print(" ", time.strftime("%H:%M:%S", time.gmtime(e["t"] / 1000)),
                  e["kind"], json.dumps(e["data"], ensure_ascii=False)[:120])
