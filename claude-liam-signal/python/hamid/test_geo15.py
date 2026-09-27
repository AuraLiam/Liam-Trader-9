"""پاسبان اجرای هندسهٔ ×۲ روی سیگنال ۱۵ دقیقه (تأیید صریح حمید، ۲۷ سپتامبر).

خاصیت‌ها، نه شکل:
  ۱. فقط ۱۵د؛ ۵د دست نمی‌خورد.
  ۲. استاپ و تارگت دو برابرِ فاصله، RR ثابت، سایز نصف.
  ۳. دوباره‌زدن بی‌اثر است (هرگز ×۴ نمی‌شود).
  ۴. بعد از آخرین دروازه اجرا می‌شود — هیچ دروازه‌ای با استاپِ پهن‌تر داوری نمی‌کند.
  ۵. کپشن به حمید می‌گوید سایز را نصف کند؛ دفتر پیپر ردپای geo_mult دارد.
  ۶. بازوی کنترلِ exp-tf15 زنده می‌ماند.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import telegram as T                                            # noqa: E402
from hamid import paper as P                                    # noqa: E402

OK, BAD = [], []


def check(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  — {extra}" if extra and not cond else ""))


def sig(tf="15m", d="LONG"):
    if d == "LONG":
        return {"sym": "XUSDT", "tf": tf, "dir": d, "entry": 100.0, "sl": 99.0,
                "tp1": 102.0, "tp2": 104.0, "rr": 2.0, "stop_pct": 1.0}
    return {"sym": "XUSDT", "tf": tf, "dir": d, "entry": 100.0, "sl": 101.0,
            "tp1": 98.0, "tp2": 96.0, "rr": 2.0, "stop_pct": 1.0}


s = T.apply_geo15(sig())
check("۱۵د لانگ: استاپ و تارگت دو برابرِ فاصله",
      s["sl"] == 98.0 and s["tp1"] == 104.0 and s["tp2"] == 108.0, str(s))
check("RR ثابت می‌ماند", abs((s["tp1"] - s["entry"]) / (s["entry"] - s["sl"]) - 2.0) < 1e-9)
check("سایز نصف روی سیگنال ثبت است", s["geo"]["size_mult"] == 0.5 and s["geo"]["mult"] == 2.0)
check("هندسهٔ پایه برای ردپا نگه داشته می‌شود", s["geo"]["base"]["sl"] == 99.0)
sh = T.apply_geo15(sig(d="SHORT"))
check("۱۵د شورت: قرینه درست است", sh["sl"] == 102.0 and sh["tp1"] == 96.0, str(sh))
f5 = T.apply_geo15(sig(tf="5m"))
check("۵د دست نمی‌خورد", f5["sl"] == 99.0 and "geo" not in f5)
T.apply_geo15(s)
check("دوباره‌زدن بی‌اثر است (هرگز ×۴ نمی‌شود)", s["sl"] == 98.0 and s["tp1"] == 104.0)

src = (HERE.parent / "telegram.py").read_text(encoding="utf-8")
body = src[src.index("def send_signals"):]
i_geo = body.index("apply_geo15(s)")
gates = {"هم‌زمانی": "_signed > 0.025", "روند": "_tg_gate.assess(",
         "بازجویی": "_pm.review(s, _c15)"}
late = [k for k, g in gates.items() if body.index(g) > i_geo]
check("بعد از همهٔ دروازه‌ها اجرا می‌شود (هیچ دروازه‌ای با استاپ پهن داوری نمی‌کند)",
      not late, str(late))
check("قبل از چارت و کپشن و دفتر پیپر",
      i_geo < body.index("render_chart(s,") < body.index("caption(s)")
      and i_geo < body.index('"geo_mult"'))
cap = T.caption({**s, "strategy": "ibs"}) if hasattr(T, "caption") else ""
check("کپشن صریح می‌گوید سایز را نصف کن", "سایز را نصف کن" in cap)
check("بازوی کنترل exp-tf15 سرِ جایش است",
      "exp-tf15" in P.EXPERIMENT_STAGES and P.GEO_ARMS.get("exp-tf15-x2", (None,))[0] == "exp-tf15")

wf = HERE.parents[2] / ".github" / "workflows"
check("پاسبان در دروازهٔ هر دو زنجیره",
      all("hamid.test_geo15" in (wf / f).read_text() for f in ("hamid-cycle.yml", "pump-radar.yml")))

print()
if BAD:
    print(f"✗ {len(BAD)} بررسی افتاد: {BAD}")
    sys.exit(1)
print(f"پاسبان هندسهٔ ×۲ روی ۱۵د: هر {len(OK)} بررسی سبز")
