"""پاسبان توقفِ تحویل IBS روی ۵ دقیقه (دستور حمید، ۱ اکتبر) — خاصیت، نه شکل.

۱. جفت (ibs, 5m) در گلوگاه ارسال به تلگرام نمی‌رود؛ (smc, 5m) و (ibs, 15m) می‌روند.
۲. ستاپِ متوقف‌شده در دفترِ ضدواقع با مرحلهٔ `ibs5-muted` ثبت می‌شود
   (تا تصمیم با کندل واقعی سنجیده شود)، و آن مرحله «سیگنال ارسالی» شمرده نمی‌شود.
۳. سیم‌کشی: پاسبان در دروازهٔ هر دو زنجیره.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ["LIAM9_NO_REMOTE_DEDUPE"] = "1"
import telegram as TG                                           # noqa: E402
from hamid import paper as P                                    # noqa: E402

OK, BAD = [], []


def check(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  — {extra}" if extra and not cond else ""))


check("جفتِ متوقف فقط (ibs, 5m) است", TG.MUTED_PAIRS == {("ibs", "5m")})
check("مرحلهٔ ibs5-muted بیرون از کارنامهٔ سیگنال است", "ibs5-muted" in P._NOT_SIGNAL)

TMP = Path(tempfile.mkdtemp(prefix="ibs5-"))
TG.SENT, TG.SIDECAR, TG.TGLOG, TG.ARCHIVE_DIR = TMP / "sent.json", TMP / "side.json", TMP / "log.json", TMP / "arc"
TG.ARCHIVE_DIR.mkdir()
posts, opened = [], []
_o = (TG._post, TG.creds, P.open_from, TG._remote_log_rows)
TG._post = lambda token, method, data, files=None: posts.append((method, data)) or {"result": {"message_id": len(posts)}}
TG.creds = lambda: ("tok", "chat")
TG._remote_log_rows = lambda: []
P.open_from = lambda setups, ctx: opened.append((setups, ctx)) or len(setups)
# دروازه‌های شبکه‌ای (هم‌زمانی/روند/بازجویی) با نبودِ شبکه خودشان رد می‌کنند؛
# این آزمون فقط تا پیش از آن‌ها را می‌سنجد: ستاپِ متوقف‌شده باید *پیش* از
# دروازه‌های شبکه‌ای به دفتر ضدواقع برود، و ستاپ‌های دیگر به آن دروازه‌ها برسند.
sigs = [{"sym": "AUSDT", "tf": "5m", "dir": "LONG", "strategy": "ibs", "entry": 1.0, "sl": 0.9, "tp1": 1.3, "quality": 70},
        {"sym": "BUSDT", "tf": "5m", "dir": "LONG", "strategy": "smc", "entry": 1.0, "sl": 0.9, "tp1": 1.3, "quality": 70},
        {"sym": "CUSDT", "tf": "15m", "dir": "SHORT", "strategy": "ibs", "entry": 1.0, "sl": 1.1, "tp1": 0.7, "quality": 70}]
try:
    TG.send_signals([dict(s) for s in sigs], lambda s, p: None)
finally:
    TG._post, TG.creds, P.open_from, TG._remote_log_rows = _o
muted = [st for setups, ctx in opened for st in setups if st.get("stage_tag") == "ibs5-muted"]
check("ستاپ ibs/5m به دفتر ضدواقع رفت (مرحلهٔ ibs5-muted)", [m["symbol"] for m in muted] == ["AUSDT"], str(opened)[:300])
check("دلیلِ ثبت‌شده muted_ibs5 است", any(ctx.get("veto_why") == "muted_ibs5" for _, ctx in opened))
check("هیچ پیامی برای ستاپِ متوقف‌شده نرفت", not any("AUSDT" in json.dumps(d, ensure_ascii=False) for _, d in posts))
check("smc/5m و ibs/15m متوقف نشدند", not any(m["symbol"] in ("BUSDT", "CUSDT") for m in muted))

wf = HERE.parents[2] / ".github" / "workflows"
check("پاسبان در دروازهٔ هر دو زنجیره",
      all("hamid.test_ibs5_mute" in (wf / f).read_text(encoding="utf-8") for f in ("hamid-cycle.yml", "pump-radar.yml")))

print()
if BAD:
    print(f"✗ {len(BAD)} بررسی افتاد: {BAD}")
    sys.exit(1)
print(f"پاسبان توقفِ IBS ۵د: هر {len(OK)} بررسی سبز")
