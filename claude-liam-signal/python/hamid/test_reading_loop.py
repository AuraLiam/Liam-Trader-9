"""آزمون حلقهٔ مطالعهٔ ۳ساعته — چرخش عادلانه، ثبت append-only، بدون دستکاری مغز واقعی."""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from research import reading_loop as rl                       # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def run():
    tmp = Path(tempfile.mkdtemp())
    rl.ROOT = tmp
    rl.STATE = tmp / "brain" / "research" / "reading-state.json"
    rl.OUT = tmp / "signals" / "reading.json"
    reg = tmp / "config"
    reg.mkdir(parents=True)
    rl.REG = reg / "engine_learning_registry.yaml"
    rl.REG.write_text(json.dumps({"engines": [
        {"id": "E01", "name": "one", "books": ["A1", "A2"]},
        {"id": "E02", "name": "two", "books": ["B1"]},
    ]}))

    r1 = rl.run(1000)
    check("نوبت اول: E01 کتاب A1", r1["engine"] == "E01" and r1["book"] == "A1")
    r2 = rl.run(2000)
    check("چرخش: نوبت دوم E02", r2["engine"] == "E02" and r2["book"] == "B1")
    r3 = rl.run(3000)
    check("دور دوم E01 کتاب بعدی (A2)", r3["engine"] == "E01"
          and r3["book"] == "A2", str(r3))
    rows = [json.loads(x) for x in
            (tmp / "brain" / "research" / "E01" / "reading.jsonl")
            .read_text().splitlines()]
    check("ثبت append-only در reading.jsonl", len(rows) == 2
          and rows[0]["book"] == "A1" and rows[1]["book"] == "A2")
    out = json.loads(rl.OUT.read_text())
    check("توصیهٔ جاری برای پنل نوشته شد", out["book"] == "A2"
          and out["engine"] == "E01")

    print(f"\n✓ همهٔ {OK} آزمون حلقهٔ مطالعه گذشت")


if __name__ == "__main__":
    run()
