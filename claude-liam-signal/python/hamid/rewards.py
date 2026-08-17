"""دفتر جایزهٔ انجین‌ها — دستور حمید، ۱۷ اوت.

«هر انجینی که بتواند از تجربه در سیگنال‌های قبل TP بزند جایزه بگیرد تا
بداند این قضیه خیلی مهم است.» جایزه از روی ردپای واقعی هر انجین روی
معاملهٔ بسته حساب می‌شود (بند CLAUDE.md: انجین بی‌ردپا ناقص است):

  امتیازها: TARGET = +۳ · TRAIL = +۱ · STOP = −۱ برای هر انجینی که روی
  همان معامله ردپای تأیید داشت. اگر ردپای «تجربه» (exp_used — حافظهٔ
  E21) روی معامله باشد، جایزهٔ همان معامله ۲× می‌شود — TP از تجربه
  باارزش‌ترین اتفاق مجموعه است.

نگاشت ردپا → انجین (auditable؛ ردپای خام هم ذخیره می‌شود):
  ob_align/ob_hunts→E08 · pattern_align→E13 · liq→E10 · pm_pro→E17 ·
  trend_4h هم‌جهت→E07 · exp_used→E21 (و ضریب ۲×)

خروجی: brain/rewards.json (دفتر تجمیعی + دنبالهٔ آخرین جایزه‌ها) و
signals/rewards.json (عکس‌فوری پنل). این دفتر فقط انگیزشی/عیب‌یابانه
است — هیچ وتو یا وزنی در تصمیم ندارد تا وقتی CI چیزی را ثابت کند
(قانون ۰۳).
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
LEDGER = ROOT / "brain" / "rewards.json"
OUT = ROOT / "signals" / "rewards.json"
KEEP_HISTORY = 300

POINTS = {"target": 3, "trail": 1, "stop": -1}


def _fingerprints(t):
    """ردپاهای انجین روی یک معاملهٔ بسته → [(engine, ردپا)]."""
    w = t.get("why") or t.get("ctx") or {}
    fp = []
    if w.get("ob_align"):
        fp.append(("E08", "ob_align"))
    if w.get("pattern_align"):
        fp.append(("E13", "pattern_align"))
    if w.get("liq"):
        fp.append(("E10", "liq"))
    if w.get("pm_pro"):
        fp.append(("E17", "pm_pro"))
    t4, d = w.get("trend_4h"), (t.get("dir") or w.get("dir") or "").upper()
    if (t4 == "up" and d == "LONG") or (t4 == "down" and d == "SHORT"):
        fp.append(("E07", "trend_4h_align"))
    if w.get("exp_used"):
        fp.append(("E21", "exp_used"))
    return fp


def _load():
    try:
        d = json.loads(LEDGER.read_text())
        return {"engines": d.get("engines") or {}, "history": d.get("history") or []}
    except Exception:                                # noqa: BLE001
        return {"engines": {}, "history": []}


def award(closed_trades, now_ms=None):
    """جایزهٔ معامله‌های تازه‌بسته را ثبت می‌کند؛ خروجی: چند جایزه داده شد."""
    now = now_ms or int(time.time() * 1000)
    st = _load()
    given = 0
    for t in closed_trades or []:
        outcome = t.get("outcome")
        if outcome not in POINTS:
            continue
        fps = _fingerprints(t)
        if not fps:
            continue
        exp_bonus = 2 if any(e == "E21" for e, _ in fps) else 1
        for eng, fp in fps:
            pts = POINTS[outcome] * exp_bonus
            row = st["engines"].setdefault(
                eng, {"points": 0, "target": 0, "trail": 0, "stop": 0})
            row["points"] += pts
            row[outcome] += 1
            row["last"] = now
            st["history"].append({
                "t": now, "engine": eng, "fingerprint": fp,
                "sym": t.get("sym"), "outcome": outcome, "points": pts,
                "from_experience": exp_bonus == 2})
            given += 1
    if not given:
        return 0
    st["history"] = st["history"][-KEEP_HISTORY:]
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(st, ensure_ascii=False))
    board = sorted(st["engines"].items(), key=lambda kv: -kv[1]["points"])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": now,
        "note": "جایزهٔ انجین‌ها — TP از تجربه ۲× (دستور حمید ۱۷ اوت)",
        "board": [{"engine": e, **v} for e, v in board],
        "recent": st["history"][-20:],
    }, ensure_ascii=False, indent=1))
    return given
