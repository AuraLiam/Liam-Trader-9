"""آزمون دفتر جایزهٔ انجین‌ها — TP از تجربه ۲×، استاپ منفی، بی‌ردپا هیچ."""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import rewards as rw                               # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def trade(outcome="target", **why):
    return {"sym": "XUSDT", "dir": "LONG", "outcome": outcome,
            "why": {"dir": "LONG", **why}}


def run():
    tmp = Path(tempfile.mkdtemp())
    rw.LEDGER, rw.OUT = tmp / "rewards.json", tmp / "rewards-panel.json"

    # ۱) TP با ردپای OB و روند → دو جایزهٔ +۳
    n = rw.award([trade(ob_align=True, trend_4h="up")])
    check("دو انجین جایزه گرفتند", n == 2)
    st = json.loads(rw.LEDGER.read_text())
    check("E08 و E07 هر کدام +۳", st["engines"]["E08"]["points"] == 3
          and st["engines"]["E07"]["points"] == 3, str(st["engines"]))

    # ۲) TP «از تجربه» → ضریب ۲× برای همهٔ ردپاهای همان معامله
    rw.award([trade(exp_used=True, ob_align=True)])
    st = json.loads(rw.LEDGER.read_text())
    check("TP از تجربه دو برابر است (E21=+۶، E08=۳+۶=۹)",
          st["engines"]["E21"]["points"] == 6
          and st["engines"]["E08"]["points"] == 9, str(st["engines"]))

    # ۳) استاپ با ردپای تأیید = −۱ (پاسخ‌گویی، نه فقط جایزه)
    rw.award([trade(outcome="stop", liq="زیر سطح")])
    st = json.loads(rw.LEDGER.read_text())
    check("E10 روی استاپ −۱ گرفت", st["engines"]["E10"]["points"] == -1)

    # ۴) معاملهٔ بی‌ردپا یا expired هیچ جایزه‌ای نمی‌سازد
    check("بی‌ردپا/expired = هیچ", rw.award([trade(), {"outcome": "expired"}]) == 0)

    # ۵) عکس‌فوری پنل نوشته شد و مرتب است
    out = json.loads(rw.OUT.read_text())
    check("تابلوی پنل مرتب بر اساس امتیاز", out["board"][0]["engine"] == "E08"
          and out["recent"], str(out["board"][:2]))

    print(f"\n✓ همهٔ {OK} آزمون دفتر جایزه گذشت")


if __name__ == "__main__":
    run()
