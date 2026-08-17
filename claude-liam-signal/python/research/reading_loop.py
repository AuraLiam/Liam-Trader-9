"""حلقهٔ مطالعه — هر ۳ ساعت یک کتاب برای یک انجین (دستور حمید، ۱۷ اوت).

چرخشی و قطعی (بدون LLM — قانون ۰۶): هر اجرا انجین بعدی را برمی‌دارد،
کتاب بعدیِ برنامهٔ درسی همان انجین را توصیه می‌کند و توصیه را ثبت
می‌کند:

  brain/research/<Exx>/reading.jsonl  ← ردیف append-only (تکلیف مطالعه)
  signals/reading.json                ← توصیهٔ جاری برای پنل

منبع کتاب‌ها: config/engine_learning_registry.yaml (۳ کتاب رسمی هر
انجین). خواندن واقعی و ثبت درس، کار ایجنت همان انجین در نشست است
(قانون ۰۳: ادعا فقط با منبع و شواهد وارد قفسه می‌شود)؛ پاسبان C4
انجینی را که قفسه دارد و findings خالی است، رسوا می‌کند.

    python3 -m research.reading_loop
"""
import json
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent.parent
REG = ROOT / "config" / "engine_learning_registry.yaml"
STATE = ROOT / "brain" / "research" / "reading-state.json"
OUT = ROOT / "signals" / "reading.json"


def _engines():
    reg = yaml.safe_load(REG.read_text())
    return [(e["id"], e.get("name") or e["id"], e.get("books") or [])
            for e in reg["engines"] if e.get("books")]


def _state():
    try:
        return json.loads(STATE.read_text())
    except Exception:                                # noqa: BLE001
        return {"cursor": 0, "rounds": {}}


def run(now_ms=None):
    now = now_ms or int(time.time() * 1000)
    engines = _engines()
    if not engines:
        print("رجیستری خالی است — توصیه‌ای نیست")
        return None
    st = _state()
    eid, name, books = engines[st.get("cursor", 0) % len(engines)]
    round_i = st.setdefault("rounds", {}).get(eid, 0)
    book = books[round_i % len(books)]
    row = {"t": now, "engine": eid, "book": book,
           "round": round_i + 1, "status": "TO_READ",
           "note": "حلقهٔ ۳ساعتهٔ مطالعه — خواندن و ثبت درس با ایجنت همان انجین"}
    d = ROOT / "brain" / "research" / eid
    d.mkdir(parents=True, exist_ok=True)
    with (d / "reading.jsonl").open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    st["rounds"][eid] = round_i + 1
    st["cursor"] = (st.get("cursor", 0) + 1) % len(engines)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": now, "engine": eid, "engine_name": name, "book": book,
        "note": "توصیهٔ مطالعهٔ این نوبت — قانون ۰۳: درسِ خوانده با منبع ثبت می‌شود",
    }, ensure_ascii=False, indent=1))
    print(f"📚 توصیهٔ این نوبت → {eid}: {book}")
    return row


if __name__ == "__main__":
    run()
