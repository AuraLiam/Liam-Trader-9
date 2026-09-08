#!/usr/bin/env python3
"""پاسبان درسِ جهتِ مخالف (۷ سپتامبر) — آفلاین، بدون شبکه.

قفل می‌کند: تفکیکِ سه نوعِ شکست · اینکه استاپِ نویزی «درسِ جهتی» علامت
نخورد · یکتاسازی پیش از CI · فرضیه‌بودن (نه قاعده) با باطل‌کننده ·
نمره‌دادنِ جدا به هر کلاس با کف نمونه · فقط-خواندن (قانون ۰۵).
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import direction_lessons as DL              # noqa: E402

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


def row(sym="AAA", d="LONG", R=-1.0, mfe=0.0, mae=1.6, entry=100.0,
        sl=98.0, opened=1, closed=2, stage="sig-ibs", stop_pct=None):
    w = {"stage": stage, "mfe": mfe, "mae": -abs(mae)}
    if stop_pct is not None:
        w["stop_pct"] = stop_pct
    return {"sym": sym, "dir": d, "entry": entry, "sl": sl, "R": R,
            "mfe_r": mfe, "mae_r": mae, "outcome": "stop", "tf": "15m",
            "opened": opened, "filled": opened, "closed": closed, "why": w}


# ── ۱. سه نوعِ شکست از هم جدا می‌شوند ────────────────────────────────────
#
# قاطی‌کردنشان همان اشتباهی است که سنجهٔ ۶ سپتامبر را رد کرد: استاپِ نویزی
# دربارهٔ جهت حرفی نمی‌زند و اگر با بقیه جمع شود سیگنالِ واقعی را رقیق
# می‌کند.
c, _, dirn = DL.classify(row(mfe=0.02, mae=1.6, stop_pct=2.0))
check("هرگز-در-سود-نرفت → WRONG_SIDE و شاهدِ جهتی است",
      c == "WRONG_SIDE" and dirn, f"{c}/{dirn}")
c, _, dirn = DL.classify(row(mfe=1.2, mae=1.1, stop_pct=2.0))
check("رفت-در-سود-برگشت → FAILED_CONT و شاهدِ جهتی است",
      c == "FAILED_CONT" and dirn, f"{c}/{dirn}")
c, why, dirn = DL.classify(row(mfe=0.05, mae=1.05, stop_pct=0.3))
check("استاپِ تنگِ نویزی → NOISE_STOP",
      c == "NOISE_STOP", f"{c} · {why}")
check("و صریح «بدون درسِ جهتی» علامت می‌خورد", not dirn)
c, _, dirn = DL.classify(row(mfe=0.3, mae=1.2, stop_pct=2.0))
check("حرکتِ کم‌عمق شاهدِ جهتی حساب نمی‌شود",
      c == "SHALLOW" and not dirn, f"{c}/{dirn}")

# نویز **قبل** از WRONG_SIDE سنجیده می‌شود، وگرنه همان ردیف‌ها به‌غلط
# شاهدِ جهتی می‌شوند — همان رقیق‌شدنی که این ماژول برای رفعش ساخته شد.
c, _, dirn = DL.classify(row(mfe=0.01, mae=1.1, stop_pct=0.2))
check("کلاس: استاپِ تنگ بر «هرگز در سود نرفت» مقدم است",
      c == "NOISE_STOP" and not dirn, f"{c}/{dirn}")

# ── ۲. درس فقط از بازنده، و جهتش قرینه است ──────────────────────────────
les = DL.lesson_from(row(d="LONG"))
check("از لانگِ بازنده، درسِ SHORT می‌سازد",
      les and les["opposite"] == "SHORT" and les["lost_dir"] == "LONG")
les_s = DL.lesson_from(row(d="SHORT", entry=100.0, sl=102.0))
check("و از شورتِ بازنده، درسِ LONG (قرینه)",
      les_s and les_s["opposite"] == "LONG")
check("سطحِ درس، قیمتِ استاپ است", les["level"] == 98.0, str(les["level"]))
check("از معاملهٔ برنده درس ساخته نمی‌شود",
      DL.lesson_from(row(R=1.5)) is None)
check("از منقضی هم نه",
      DL.lesson_from({**row(), "outcome": "expired"}) is None)

# ── ۳. فرضیه است، نه قاعده (قانون ۰۳/۱۲) ────────────────────────────────
check("هر درس باطل‌کنندهٔ خودش را دارد",
      "falsifier" in les and "CI" in les["falsifier"])
check("و صریح «فرضیه» است نه حکم", "hypothesis" in les)
check("درسِ بی‌جهت، فرضیهٔ جهتی نمی‌سازد",
      DL.lesson_from(row(mfe=0.05, mae=1.05, stop_pct=0.3))["hypothesis"]
      == "این شکست درسِ جهتی ندارد")

# ── ۴. یکتاسازی پیش از هر CI (تصحیح ۲۴ اوت) ─────────────────────────────
p = Path(tempfile.mkdtemp(prefix="liam9-dl-")) / "closed.jsonl"
dup = [row(sym="D", opened=5), row(sym="D", opened=5), row(sym="E", opened=6)]
p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in dup) + "\n",
             encoding="utf-8")
check("ردیف تکراری یک بار شمرده می‌شود", len(DL.rows(p)) == 2,
      str(len(DL.rows(p))))

# ── ۵. هر کلاس جدا نمره می‌گیرد، با کف نمونه ────────────────────────────
check("کف نمونه از پیش ثبت شده",
      isinstance(DL.MIN_N, int) and DL.MIN_N >= 30, str(DL.MIN_N))
small = [row(sym=f"S{i}", opened=i, closed=i + 1) for i in range(5)]
p2 = Path(tempfile.mkdtemp(prefix="liam9-dl2-")) / "closed.jsonl"
p2.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in small)
              + "\n", encoding="utf-8")
v = DL.build(path=p2)
check("زیر کف نمونه، کلاس «enough» نمی‌گیرد",
      all(not s.get("enough") for s in v["scores"].values()), str(v["scores"]))
check("خروجی کلاس‌ها را جدا نگه می‌دارد (پول نمی‌کند)",
      isinstance(v["scores"], dict))
check("و مرز صادقانه روی خروجی هست",
      "قانون ۰۳" in v["note"] and "NOISE_STOP" in v["boundary"])

# ── ۶. فقط می‌خواند؛ دفترش append-only است (قانون ۰۵) ───────────────────
_src = (HERE / "direction_lessons.py").read_text(encoding="utf-8")
check("دفتر فقط append می‌شود، بازنویسی نه",
      '.open("a"' in _src and "BOOK.write_text" not in _src)
check("جز خروجی خودش فایلی نمی‌نویسد",
      _src.count("write_text") == 1 and "OUT.write_text" in _src)

# ── ۷. یکتا بر هویتِ معامله — هضمِ دوباره درسِ دوباره نمی‌سازد (۸ سپتامبر)
_bk = Path(tempfile.mkdtemp(prefix="liam9-dl3-")) / "direction.jsonl"
_lost = row(sym="DUPUSDT", opened=10, closed=11)
_lost["R"], _lost["outcome"] = -1.0, "stop"
_n1 = DL.append_lessons([_lost], now_ms=1, path=_bk)
_n2 = DL.append_lessons([_lost, dict(_lost)], now_ms=2, path=_bk)
check("باختِ اول درس می‌سازد", _n1 == 1, str(_n1))
check("همان باخت دوباره (دو رانر / هضم دوباره) درس نمی‌سازد", _n2 == 0, str(_n2))
_other = dict(_lost, closed=99)
check("ولی باختِ دیگرِ همان نماد درس خودش را می‌گیرد",
      DL.append_lessons([_other], now_ms=3, path=_bk) == 1)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
