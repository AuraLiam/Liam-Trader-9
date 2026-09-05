#!/usr/bin/env python3
"""چراغ دریایی — لپ‌تاپ وضعیتش را یک‌طرفه بیرون می‌فرستد تا من ببینمش.

دستور حمید (۴ سپتامبر): «می‌خوام به صورت لحظه‌ای اطلاعات را به پایتون
خودت که داره روی لپ‌تاپ پایش انجام می‌ده انتقال بدی و زیر نظر داشته
باشی که کارها را درست انجام بده.»

## مسئله

من در یک کانتینر ابری اجرا می‌شوم و لپ‌تاپ حمید جای دیگری است. هیچ راهِ
مستقیمی بینشان نیست. تنها زمینِ مشترک، همین مخزن است.

## چرا این، گیت را به مسیر سیگنال برنمی‌گرداند

سؤال درستی است، چون تازه گیت را از مسیر سیگنال بیرون کردیم. سه فرق:

۱. **شاخهٔ جدا (`laptop-beacon`)** — نه `main`. هیچ‌وقت با زنجیرهٔ
   سیگنال یا کارِ من روی `main` تلاقی نمی‌کند.
۲. **یک نویسنده** — فقط لپ‌تاپ روی این شاخه می‌نویسد. تصادم ساختاراً
   ممکن نیست، پس نه reset لازم است نه reapply نه merge.
۳. **بیرونِ مسیر تصمیم** — سیگنال منتظرش نمی‌ماند. اگر اینترنت نباشد یا
   push شکست بخورد، فقط من دیرتر می‌بینم؛ **هیچ سیگنالی دیر نمی‌رود.**

پس گیت این‌جا «راهِ خبررسانی» است، نه «راهِ کار کردن».

## چه چیزی می‌فرستد (و چه چیزی نمی‌فرستد)

می‌فرستد: حکمِ سرویس، سلامت ۱۳ منبع، سیگنال‌های اخیر با نتیجه‌شان،
اثباتِ سه‌پلهٔ یادگیری، حکم گذرگاه وضعیت، و آخرین خطاها.

**نمی‌فرستد**: توکن، هیچ کلیدی، هیچ مسیر شخصی. تابع `_scrub` هر چیزی
که بوی سکرت بدهد را قبل از نوشتن حذف می‌کند (قانون ۰۵) — و آزمونش با
یک توکن ساختگی اثبات می‌شود، نه با اطمینان.

    python3 -m hamid.beacon            # فقط بساز و چاپ کن
    python3 -m hamid.beacon --write    # + بنویس روی signals/beacon.json
    python3 -m hamid.beacon --push     # + بفرست روی شاخهٔ laptop-beacon
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

SIG = ROOT / "signals"
BRAIN = ROOT / "brain"
OUT = SIG / "beacon.json"
BRANCH = "laptop-beacon"
RECENT_SIGNALS = 25
RECENT_CLOSED = 25

SECRET_RE = re.compile(
    r"(\d{8,10}:[A-Za-z0-9_-]{30,})"                 # توکن بات تلگرام
    r"|([A-Za-z0-9_-]{32,})"                         # هر کلیدِ بلند
)
SECRET_KEYS = ("token", "secret", "key", "password", "chat_id", "apikey")


def _scrub(obj):
    """هر چیزی که بوی سکرت بدهد، قبل از بیرون‌رفتن حذف می‌شود."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(s in str(k).lower() for s in SECRET_KEYS):
                out[k] = "‹حذف شد›"
            else:
                out[k] = _scrub(v)
        return out
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    if isinstance(obj, str):
        return SECRET_RE.sub("‹حذف شد›", obj)
    return obj


def _load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def _rows(p, limit=None):
    p = Path(p)
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out[-limit:] if limit else out


def _age_min(snap):
    if not isinstance(snap, dict) or not snap.get("generated"):
        return None
    return round((time.time() * 1000 - snap["generated"]) / 60000, 1)


def build(now_ms=None):
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    svc = _load(SIG / "liam9d.json", {}) or {}
    feed = _load(SIG / "feed-health.json", {}) or {}
    state = _load(SIG / "system-state.json", {}) or {}
    proof = _load(SIG / "learning-proof.json", {}) or {}
    sent = _load(SIG / "telegram-log.json", []) or []
    if isinstance(sent, dict):
        sent = sent.get("rows") or sent.get("sent") or []
    closed = _rows(BRAIN / "paper" / "closed.jsonl", RECENT_CLOSED)

    # سیگنال‌های اخیر: فقط چیزی که برای پایش لازم است، نه کلِ ردیف
    sig_rows = []
    for s in (sent[-RECENT_SIGNALS:] if isinstance(sent, list) else []):
        if not isinstance(s, dict):
            continue
        sig_rows.append({k: s.get(k) for k in
                         ("sym", "dir", "tf", "strategy", "conf", "rr",
                          "ts", "t", "outcome", "phoenix_label", "candle_src")
                         if s.get(k) is not None})

    res = []
    for t in closed:
        res.append({k: t.get(k) for k in
                    ("sym", "dir", "tf", "outcome", "R", "R_net", "fee_r",
                     "held_h", "closed") if t.get(k) is not None})

    return _scrub({
        "generated": now, "engine": "E23", "panel": "لیام تریدر ۹",
        "kind": "beacon", "note": "گزارشِ یک‌طرفهٔ لپ‌تاپ — فقط برای پایش",
        "service": {"ticks": svc.get("ticks"), "tick_s": svc.get("tick_s"),
                    "ok": svc.get("ok"), "failed": svc.get("failed"),
                    "age_min": _age_min(svc),
                    "last_failures": svc.get("last_failures") or []},
        "feed": {"verdict": feed.get("verdict"), "why": feed.get("why"),
                 "alive": feed.get("alive"), "total": feed.get("total"),
                 "preferred_ok": feed.get("preferred_ok"),
                 "age_min": _age_min(feed),
                 "down": (feed.get("down") or [])[:6]},
        "system_state": {"verdict": state.get("verdict"),
                         "age_min": _age_min(state)},
        "learning": {k: proof.get(k) for k in
                     ("step1_digest", "step2_movement", "step3_consume",
                      "verdict", "fingerprint") if k in proof},
        "recent_signals": sig_rows,
        "recent_results": res,
        "boundary": "فقط می‌خواند و بیرون می‌فرستد. هیچ سکرتی در این فایل "
                    "نیست (_scrub). سیگنال منتظر این کانال نمی‌ماند — "
                    "شکستِ ارسال، سیگنال را دیر نمی‌کند.",
    })


def _git(*args, timeout=120):
    try:
        return subprocess.run(["git", *args], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=timeout)
    except Exception as e:                           # noqa: BLE001
        return subprocess.CompletedProcess(args, 1, "", f"{type(e).__name__}: {e}")


def push(snap, quiet=True):
    """روی شاخهٔ جدا می‌نشیند — با worktree، تا درختِ کاریِ سرویس
    اصلاً لمس نشود. اگر نشد، فقط برمی‌گردد؛ چیزی نمی‌شکند."""
    import tempfile
    payload = json.dumps(snap, ensure_ascii=False, indent=1) + "\n"
    with tempfile.TemporaryDirectory() as td:
        wt = Path(td) / "beacon"
        r = _git("fetch", "origin", BRANCH)
        base = f"origin/{BRANCH}" if r.returncode == 0 else None
        if base:
            r = _git("worktree", "add", "--detach", str(wt), base)
        else:                                        # اولین بار: شاخهٔ نو
            r = _git("worktree", "add", "--detach", str(wt), "HEAD")
        if r.returncode != 0:
            return False, (r.stderr or r.stdout).strip()[:200]
        try:
            (wt / "beacon.json").write_text(payload, encoding="utf-8")
            _git("-C", str(wt), "add", "beacon.json")
            _git("-C", str(wt), "-c", "user.name=liam9-laptop",
                 "-c", "user.email=noreply@anthropic.com",
                 "commit", "-q", "-m",
                 f"چراغ لپ‌تاپ {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
            p = _git("-C", str(wt), "push", "origin", f"HEAD:{BRANCH}")
            ok = p.returncode == 0
            return ok, ("" if ok else (p.stderr or p.stdout).strip()[:200])
        finally:
            _git("worktree", "remove", "--force", str(wt))


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    snap = build()
    if "--write" in argv or "--push" in argv:
        try:
            import brain
            blocked = brain.blocked(OUT)
        except Exception:                            # noqa: BLE001
            blocked = False
        if not blocked:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    if "--push" in argv:
        ok, why = push(snap)
        print(f"  چراغ {'رفت' if ok else 'نرفت'}"
              + (f" — {why}" if why else ""), flush=True)
    f, s = snap["feed"], snap["service"]
    print(f"\nچراغ لپ‌تاپ · سرویس {s.get('ok')}✓/{s.get('failed')}✗ "
          f"(تیک {s.get('ticks')}) · خوراک {f.get('verdict')} "
          f"{f.get('alive')}/{f.get('total')} · "
          f"وضعیت {snap['system_state'].get('verdict')}")
    print(f"  {len(snap['recent_signals'])} سیگنال اخیر · "
          f"{len(snap['recent_results'])} نتیجهٔ اخیر")
    lv = (snap.get("learning") or {}).get("verdict")
    if lv:
        print(f"  یادگیری: {lv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
