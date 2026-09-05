"""پاسبان چراغ و اثباتِ یادگیری (۴ سپتامبر) — آفلاین، بدون شبکه.

دستور حمید: «اطلاعات را به پایتون خودت که روی لپ‌تاپ پایش می‌کند انتقال
بده و زیر نظر داشته باش… و بررسی کنی بعد از اینکه نتیجه داد تغییری در
یادگیری‌اش ایجاد می‌شود یا نه.»

دو چیز این‌جا قفل می‌شود:
۱. چراغ هرگز سکرت بیرون نمی‌برد (قانون ۰۵) — با توکنِ ساختگی اثبات
   می‌شود، نه با اطمینان.
۲. «یادگیری» با همان چیزی سنجیده می‌شود که کد واقعاً می‌نویسد، نه با
   نامِ فیلدِ حدسی. (نسخهٔ اولِ سنجه دنبال فیلدهای ناموجود گشت و ۰٪ داد؛
   عددِ غلط بدتر از عددِ نداشته است.)
"""
import json
import os
import subprocess as _sp
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import beacon as B                        # noqa: E402
from hamid import learning_proof as L                # noqa: E402

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


# ── ۱. چراغ سکرت بیرون نمی‌برد ─────────────────────────────────────────
FAKE = "8123456789:AAF-fakeTokenForTestingOnly_x9Qz12345678"
dirty = {"TELEGRAM_BOT_TOKEN": FAKE, "chat_id": "123456",
         "note": f"سلام {FAKE} خداحافظ",
         "nested": [{"api_key": "abc"}, {"ok": "متن سالم"}],
         "secret_thing": "shhh", "R": -0.5}
clean = B._scrub(dirty)
blob = json.dumps(clean, ensure_ascii=False)
check("توکن در هیچ جای خروجی نمی‌ماند", FAKE not in blob, blob[:160])
check("کلیدِ توکن حذف می‌شود", clean["TELEGRAM_BOT_TOKEN"] == "‹حذف شد›")
check("شناسهٔ چت هم حذف می‌شود", clean["chat_id"] == "‹حذف شد›")
check("و توکنِ داخلِ متنِ آزاد هم پاک می‌شود", FAKE not in clean["note"])
check("کلیدِ تودرتو هم گرفته می‌شود", clean["nested"][0]["api_key"] == "‹حذف شد›")
check("ولی دادهٔ سالم دست‌نخورده می‌ماند",
      clean["nested"][1]["ok"] == "متن سالم" and clean["R"] == -0.5)

snap = B.build()
sblob = json.dumps(snap, ensure_ascii=False)
for word in ("TELEGRAM_BOT_TOKEN=", "AAF-", "AAH"):
    check(f"چراغِ واقعی «{word}» ندارد", word not in sblob)
check("چراغ خودش را چراغ معرفی می‌کند", snap["kind"] == "beacon")
check("و مرزش روی خروجی نوشته شده",
      "سکرتی" in snap["boundary"] and "دیر نمی‌کند" in snap["boundary"])
for k in ("service", "feed", "system_state", "learning", "recent_signals",
          "recent_results"):
    check(f"چراغ بخش «{k}» را دارد", k in snap)
check("سیگنال‌های اخیر سقف دارند (پیام غول‌پیکر نمی‌شود)",
      len(snap["recent_signals"]) <= B.RECENT_SIGNALS)
check("نتیجه‌های اخیر هم همین‌طور",
      len(snap["recent_results"]) <= B.RECENT_CLOSED)

src = (HERE / "beacon.py").read_text(encoding="utf-8")
check("چراغ روی شاخهٔ جدا می‌نویسد، نه main", 'BRANCH = "laptop-beacon"' in src)
check("و با worktree، تا درختِ کاریِ سرویس لمس نشود", "worktree" in src)
check("هیچ reset/pull در چراغ نیست",
      "reset --hard" not in src and '"pull"' not in src)
from hamid import liam9d as D                        # noqa: E402
keys = {j["key"] for j in D.JOBS}
check("چراغ در جدول کارِ سرویس هست", "beacon" in keys)
check("اثباتِ یادگیری هم در جدول هست", "learning_proof" in keys)
bi = [i for i, j in enumerate(D.JOBS) if j["key"] == "beacon"][0]
li = [i for i, j in enumerate(D.JOBS) if j["key"] == "learning_proof"][0]
check("اثبات قبل از چراغ اجرا می‌شود تا تازه‌ترین حکم برود", li < bi)

# ── ۲. اثباتِ یادگیری با دادهٔ ساختگیِ کنترل‌شده ────────────────────────
NOW = int(time.time() * 1000)
H = 3_600_000


def _mk(sym, d, r, hours_ago, outcome="target"):
    return {"sym": sym, "dir": d, "tf": "15m", "R": r,
            "R_net": None if r is None else r - 0.06,
            "outcome": outcome, "closed": NOW - int(hours_ago * H)}


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "learning").mkdir(parents=True)
    (root / "paper").mkdir(parents=True)
    saved = L.BRAIN
    try:
        L.BRAIN = root
        closed = [_mk("AAAUSDT", "LONG", 1.5, 2), _mk("BBBUSDT", "SHORT", -1.0, 3),
                  _mk("CCCUSDT", "LONG", 0.4, 100),          # بیرونِ پنجره
                  _mk("DDDUSDT", "LONG", None, 1, "expired")]  # معامله نبود
        # فقط اولی در دفتر تجربه هست
        (root / "learning" / "experiences.jsonl").write_text(
            L.exp_line(closed[0]) + "\n", encoding="utf-8")
        dg = L.digested(closed, NOW - L.WINDOW_H * H)
        check("معاملهٔ بیرونِ پنجره شمرده نمی‌شود",
              all(r["sym"] != "CCCUSDT" for r in dg), str([r["sym"] for r in dg]))
        check("سفارشِ منقضی معامله حساب نمی‌شود (مثل digest_closed)",
              all(r["sym"] != "DDDUSDT" for r in dg))
        check("معاملهٔ داخل دفتر تجربه «هضم‌شده» است",
              any(r["sym"] == "AAAUSDT" and r["digested"] for r in dg))
        check("و آنکه نیست، «هضم‌نشده»",
              any(r["sym"] == "BBBUSDT" and not r["digested"] for r in dg))

        fp = L.fingerprint()
        check("عکس‌فوری دفتر تجربه را می‌شمارد", fp["experiences"] == 1)
        check("بی‌مبنا، حرکت UNKNOWN است نه صفر",
              L.movement(fp, None)["status"] == "UNKNOWN")
        prev = dict(fp, closed=fp["closed"] - 5, experiences=0,
                    t=fp["t"] - 2 * H)
        check("معاملهٔ بسته + ردِ تازه = LEARNING",
              L.movement(fp, prev)["status"] == "LEARNING")
        stuck = dict(fp, closed=fp["closed"] - 5, t=fp["t"] - 2 * H)
        check("معاملهٔ بسته ولی بی‌ردِ تازه = STUCK",
              L.movement(fp, stuck)["status"] == "STUCK",
              L.movement(fp, stuck)["why"])
        idle = dict(fp, t=fp["t"] - 2 * H)
        check("بی‌معاملهٔ بسته = IDLE (نبودِ حرکت این‌جا عیب نیست)",
              L.movement(fp, idle)["status"] == "IDLE")
    finally:
        L.BRAIN = saved

# پلهٔ ۳ — مصرف
sent = [{"sym": "AAAUSDT", "dir": "LONG", "ts": NOW - 1 * H, "exp_used": True},
        {"sym": "BBBUSDT", "dir": "SHORT", "ts": NOW - 1 * H},
        {"sym": "ZZZUSDT", "dir": "LONG", "ts": NOW - 1 * H}]   # بی‌سابقه
closed2 = [_mk("AAAUSDT", "LONG", 1.0, 5), _mk("BBBUSDT", "SHORT", -1.0, 5)]
cs = L.consumed(sent, closed2, NOW - L.WINDOW_H * H)
check("فقط تصمیم‌هایی شمرده می‌شوند که سابقهٔ بسته دارند", len(cs) == 2,
      str([r["sym"] for r in cs]))
check("تصمیمِ با ردپای تجربه، «استفاده‌شده» است",
      any(r["sym"] == "AAAUSDT" and r["used"] for r in cs))
check("و بی‌ردپا، «استفاده‌نشده»",
      any(r["sym"] == "BBBUSDT" and not r["used"] for r in cs))

lsrc = (HERE / "learning_proof.py").read_text(encoding="utf-8")
check("اثبات فقط می‌خواند — چیزی جز تابلوی خودش نمی‌نویسد",
      lsrc.count("write_text") <= 2)
check("و مرزش صریح است: نرخ‌ها دروازه نیستند",
      "توصیفی‌اند" in lsrc and "قانون ۰۳" in lsrc)

# ── ۳. ادغامِ دفتر، تجربه‌ها را نکوبد (عیبِ ریشه‌ایِ ۵ سپتامبر) ─────────
#
# `merge_jsonl` روی «هویتِ معامله» اجتماع می‌گیرد — درست برای
# closed.jsonl، فاجعه برای experiences.jsonl. کلیدِ تجربه می‌شد
# (sym, None, None, None) و همهٔ تجربه‌های یک نماد به یک ردیف کوبیده
# می‌شد. اثر واقعی از تاریخچهٔ مخزن: ۲۵٬۱۵۱ → ۲۱٬۷۷۸ در یک کامیت.
import importlib.util as _ilu                        # noqa: E402

_spec = _ilu.spec_from_file_location(
    "rbc", HERE.parents[2] / "scripts" / "resolve_brain_conflicts.py")
_rbc = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_rbc)


def _exp(sym, d, r, outcome, stage):
    return {"sym": sym, "tf": "15m", "dir": d, "strategy": stage, "r": r,
            "outcome": outcome, "trend_4h": None, "fear": None,
            "funding": None, "stop_pct": None, "usdt_dom": None,
            "mode": None, "liq": None}


_rows = [_exp("BTCUSDT", "LONG", 1.5, "target", "scalp"),
         _exp("BTCUSDT", "SHORT", -1.0, "stop", "practice"),
         _exp("BTCUSDT", "LONG", 0.3, "trail", "first"),
         _exp("ETHUSDT", "LONG", 2.0, "target", "scalp")]
_keys = [_rbc.trade_key(r) for r in _rows]
check("ردیفِ تجربه هویتِ معامله ندارد (نه opened نه entry)",
      all(k[1] is None and k[2] is None for k in _keys), str(_keys[0]))
check("پس کلیدِ هویتی همه را به یک ردیف در هر نماد می‌کوبید",
      len({k for k in _keys}) == 2, str(set(_keys)))

# اثباتِ رفتاری: ادغامِ دو دفترِ تجربه نباید ردیف گم کند.
import tempfile as _tf                               # noqa: E402
with _tf.TemporaryDirectory() as _td:
    _a = Path(_td) / "a.jsonl"
    _b = Path(_td) / "b.jsonl"
    _o = Path(_td) / "o.jsonl"
    _a.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                             for r in _rows[:2]) + "\n", encoding="utf-8")
    _b.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                             for r in _rows) + "\n", encoding="utf-8")
    import subprocess as _sp
    _sp.run(["python3", str(HERE.parents[2] / "scripts" / "publish_merge.py"),
             "brain/learning/experiences.jsonl", str(_a), str(_b), str(_o)],
            capture_output=True, timeout=60)
    _n = len([l for l in _o.read_text(encoding="utf-8").splitlines() if l.strip()]) \
        if _o.exists() else 0
    check("ادغامِ دو دفترِ تجربه هر چهار ردیف را نگه می‌دارد (نه یکی در هر نماد)",
          _n == 4, f"{_n} ردیف")

_trade = {"sym": "BTCUSDT", "dir": "LONG", "opened": 1788559023959,
          "entry": 0.17282, "closed": 1788559900000, "R": 1.2,
          "why": {"stage": "scalp"}}
_tk = _rbc.trade_key(_trade)
check("ولی ردیفِ معاملهٔ واقعی هویت دارد (opened و entry) — محافظ ۲۴ اوت",
      _tk[1] is not None and _tk[2] is not None, str(_tk))

_src_rbc = (HERE.parents[2] / "scripts" / "resolve_brain_conflicts.py").read_text(
    encoding="utf-8")
check("شرطِ بازگشت به اجتماعِ متنی روی opened است، نه روی sym",
      "if k[1] is None:" in _src_rbc)
check("و شرطِ قدیمیِ معیوب دیگر نیست",
      "if k[1] is None and k[0] is None:" not in _src_rbc)
# ملاک با شمارشِ واقعیِ دو دفتر انتخاب شد، نه با سلیقه
check("و دلیلِ عددی‌اش ثبت است (۴۸٬۱۵۶ در برابر صفر)",
      "۴۸٬۱۵۶" in _src_rbc and "۲۱٬۷۷۸" in _src_rbc)
check("دلیلش با عددِ اندازه‌گیری‌شده ثبت شده",
      "۲۵٬۱۵۱" in _src_rbc and "۱.۴٪" in _src_rbc)

_lp = (HERE / "learning_proof.py").read_text(encoding="utf-8")
check("سنجهٔ یادگیری با خطِ دقیق تطبیق می‌دهد نه کلیدِ ضعیف",
      "def exp_line(" in _lp)
check("و ساختارش کپیِ دقیقِ digest_closed است",
      all(f'"{k}"' in _lp for k in ("strategy", "trend_4h", "usdt_dom", "liq")))

# ── ۴. آزمونِ ادغام نباید دفترِ تولید را بخورد ─────────────────────────
#
# ۵ سپتامبر، همین‌جا: آزمونِ بالا `publish_merge` را با مسیرِ واقعی صدا
# زد و `brain/learning/experiences.jsonl` را از ۲۱٬۷۷۸ خط به **۴ خط**
# رساند. از گیت برگشت و چیزی کامیت نشد، ولی فاصلهٔ «آزمون» تا «نابودیِ
# دفتر» یک خط بود. حالا در حالت شنی، فایلِ درخت دست‌نخورده برمی‌گردد.
_pm = (HERE.parents[2] / "scripts" / "publish_merge.py").read_text(encoding="utf-8")
check("ادغام‌گر حالت شنی را می‌شناسد",
      'LIAM9_SANDBOX' in _pm and "backup" in _pm)
check("و در آن حالت فایلِ درخت را برمی‌گرداند",
      "target.write_bytes(backup)" in _pm)
check("نتیجه قبل از بازگرداندن به out می‌رود (وگرنه out نسخهٔ اصلی می‌شود)",
      _pm.index("shutil.copy(target, out)") < _pm.index("target.write_bytes(backup)"))

with _tf.TemporaryDirectory() as _td2:
    _tiny = Path(_td2) / "tiny.jsonl"
    _out2 = Path(_td2) / "o.jsonl"
    _tiny.write_text(json.dumps(_rows[0], ensure_ascii=False) + "\n",
                     encoding="utf-8")
    _live = HERE.parents[2] / "brain" / "learning" / "experiences.jsonl"
    _before = _live.read_bytes() if _live.exists() else None
    _env = dict(os.environ, LIAM9_SANDBOX="1")
    _sp.run(["python3", str(HERE.parents[2] / "scripts" / "publish_merge.py"),
             "brain/learning/experiences.jsonl", str(_tiny), str(_tiny),
             str(_out2)], capture_output=True, timeout=60, env=_env)
    _after = _live.read_bytes() if _live.exists() else None
    check("دفتر تولید بعد از ادغامِ شنی بیت‌به‌بیت دست‌نخورده است",
          _before == _after,
          f"{len(_before or b'')} → {len(_after or b'')} بایت")
    check("ولی خروجیِ ادغام واقعاً ساخته می‌شود", _out2.exists())

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
