"""ساختِ نسخهٔ **تک‌فایلِ** موتور شورت برای جعبهٔ استراتژی داشبورد.

دستور حمید (۷ سپتامبر): «تحویل داشبورد بده که بدون خطا» — و ۸ سپتامبر:
«سریع بهش کد پایتون استراتژی شورت رو بده».

## مسئله‌ای که این ساز حل می‌کند

`liam9_short_strategy.py` از نسخهٔ ۲.۰ تعریف‌ها را از ماژول‌های ریپو
**قرض می‌گیرد** (`hamid.structure` · `hamid.orderblocks` · `hamid.fees`)
— که همان رفعِ ریشه‌ایِ واگراییِ اندازه‌گیری و اجرا بود. ولی همان انتخاب،
فایل را برای جعبهٔ داشبورد **غیرقابل‌استفاده** می‌کرد: داشبورد ریپو ندارد،
پس `from hamid.structure import channel` روی اولین فراخوانی می‌ترکد.

دو راهِ غلط که انتخاب **نشد**:
  · بازنویسیِ تعریف‌ها داخل فایل تک — همان اشتباهِ نسخهٔ ۱.۰ که پنج تعریفِ
    واگرا ساخت و بک‌تست را بی‌معنا کرد.
  · کپیِ دستیِ ماژول‌ها — همان چیز، فقط با تأخیر: اولین تغییرِ
    `structure.py` دو نسخه را از هم جدا می‌کند.

راهِ درست: **تولید**، نه نوشتن. این ساز همان سورسِ واقعی را برمی‌دارد،
کامنت/داک‌استرینگ را می‌کند (همان `build_dashboard.strip`)، و داخل یک
فایل به‌عنوان ماژولِ واقعی نصبش می‌کند (`sys.modules`). پس کدِ اجراشده
در داشبورد **همان بایت‌های** کدِ اندازه‌گیری است، و هر تغییر در ریپو با
اجرای دوبارهٔ همین ساز به داشبورد می‌رسد.

    python3 -m hamid.build_short_dashboard            # ساخت + راستی‌آزمایی
    python3 -m hamid.build_short_dashboard --check    # فقط: تازه هست؟

خروجی: `claude-liam-signal/python/liam9_short_dash.py`
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid.build_dashboard import strip                # noqa: E402

# ترتیب **وابستگی** است، نه سلیقه: orderblocks از structure می‌خواند.
DEPS = ("hamid.structure", "hamid.orderblocks", "hamid.microstructure",
        "hamid.stairs", "hamid.fees")
ENGINE = "liam9_short_strategy"
OUT = PY / "liam9_short_dash.py"
MARK = "'''"                     # جداکنندهٔ رشته — نبودش در سورس اثبات می‌شود


def _path(mod):
    return PY / (mod.replace(".", "/") + ".py")


def _clean(mod):
    """سورسِ کم‌حجم‌شده، با اثباتِ اینکه داخل رشتهٔ بلند جا می‌شود."""
    src = strip(_path(mod).read_text(encoding="utf-8"))
    if MARK in src or src.rstrip().endswith("\\"):
        raise SystemExit(f"سورسِ {mod} داخل رشتهٔ بلند جا نمی‌شود — ساز متوقف شد")
    return src


def build(out_path=None):
    out = Path(out_path) if out_path else OUT
    parts = [
        "#!/usr/bin/env python3",
        '"""لیام تریدر ۹ — موتور شورت، نسخهٔ تک‌فایلِ داشبورد.',
        "",
        "**این فایل تولید می‌شود؛ دستی ویرایشش نکن.**",
        "    python3 -m hamid.build_short_dashboard",
        "",
        "کلِ فایل را در جعبهٔ «استراتژی» داشبورد بگذار. فقط کتابخانهٔ",
        "استاندارد پایتون لازم دارد.",
        "",
        "ماژول‌های زیر عیناً از ریپو آمده‌اند و این‌جا به‌عنوان ماژولِ واقعی",
        "نصب می‌شوند — پس تعریفِ ساختار/اردر بلاک/کارمزد **دقیقاً** همان",
        "چیزی است که بک‌تست با آن سنجیده شده:",
        "    " + " · ".join(DEPS),
        "",
        "مرز: این موتور هنوز مجوز تولید ندارد (PRODUCTION_APPROVED=False).",
        "خروجی‌اش پیشنهادِ سنجش‌پذیر است، نه سیگنالِ تأییدشده.",
        '"""',
        "import sys as _sys, types as _types",
        "",
        "_BUNDLED = {}",
    ]
    for mod in DEPS:
        parts += [f"_BUNDLED[{mod!r}] = r{MARK}", _clean(mod), MARK, ""]
    parts += [
        "",
        "def _install_bundled():",
        "    pkgs = {}",
        "    for _name in list(_BUNDLED) :",
        "        _top = _name.split('.')[0]",
        "        if _top not in _sys.modules:",
        "            _p = _types.ModuleType(_top)",
        "            _p.__path__ = []",
        "            _sys.modules[_top] = _p",
        "        pkgs[_top] = _sys.modules[_top]",
        "    for _name, _src in _BUNDLED.items():",
        "        if _name in _sys.modules:",
        "            continue",
        "        _m = _types.ModuleType(_name)",
        "        _m.__file__ = '<bundled:' + _name + '>'",
        "        _sys.modules[_name] = _m",
        "        exec(compile(_src, _m.__file__, 'exec'), _m.__dict__)",
        "        _top, _, _leaf = _name.rpartition('.')",
        "        if _top:",
        "            setattr(pkgs[_top], _leaf, _m)",
        "",
        "",
        "_install_bundled()",
        "",
        "",
    ]
    parts.append(_clean(ENGINE))
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return out


def verify(path):
    """اثباتِ **محصول**، نه اثباتِ ساز (درس ۶ سپتامبر).

    ۱) خودآزمایی خودِ فایل روی یک پوشهٔ موقت — یعنی بی‌ریپو هم کار کند.
    ۲) برابریِ تصمیم با موتورِ اصلی روی سناریوی مرجع.
    """
    path = Path(path)
    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / path.name
        copy.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        r = subprocess.run([sys.executable, str(copy), "--selftest"],
                           capture_output=True, text=True, timeout=300, cwd=td)
        if r.returncode != 0:
            return False, (r.stdout + r.stderr)[-800:]

        probe = Path(td) / "_parity.py"
        probe.write_text(
            "import json, sys\n"
            f"sys.path.insert(0, {str(td)!r})\n"
            f"sys.path.insert(0, {str(PY)!r})\n"
            f"import {path.stem} as B\n"
            "import liam9_short_strategy as S\n"
            "now = 1788800000000\n"
            "cd = S._zig(end=now, **S.REF)\n"
            "cd4 = S._zig(legs=6, down=10, up=5, end=now, tf_ms=14_400_000)\n"
            "kw = dict(cd_4h=cd4, btc_4h='down', btc_1h='down', equity=1000,\n"
            "          now_ms=now, alt_stance='SHORT_ALT')\n"
            "a = S.decide('AAAUSDT', cd, **kw)\n"
            "b = B.decide('AAAUSDT', cd, **kw)\n"
            "keys = ('action','entry','sl','tp1','tp2','leverage','stop_pct',\n"
            "        'rr_net','chan_pos','alt_stance','stair')\n"
            "out = {k: [a.get(k), b.get(k)] for k in keys}\n"
            # رادارِ ریزش هم باید در بسته همان جواب را بدهد — وگرنه
            # «شناسایی ریزش» در داشبورد چیزِ دیگری از اندازه‌گیری است.
            # سریِ مرجعِ `_zig` عمداً پله‌ای نیست (سقف‌های برابر می‌سازد و
            # فرکتالِ سختِ `microstructure` روی آن پیوت نمی‌دهد). برای
            # سنجشِ رادارِ ریزش یک **نردبانِ واقعی** لازم است، وگرنه
            # «نامعلوم» هر دو طرف را یکسان و بی‌معنا سبز می‌کند.
            "from hamid import stairs as ST\n"
            "lad = [[c['t'],c['o'],c['h'],c['l'],c['c'],c['v']]\n"
            "       for c in ST._ladder(steps=18, start=200.0, leg=6.0,\n"
            "                           back=2.2, bars=7)]\n"
            "out['drop_radar'] = [S.drop_radar('AAAUSDT', lad),\n"
            "                     B.drop_radar('AAAUSDT', lad)]\n"
            "print(json.dumps(out))\n",
            encoding="utf-8")
        r2 = subprocess.run([sys.executable, str(probe)], capture_output=True,
                            text=True, timeout=300, cwd=td)
        if r2.returncode != 0:
            return False, (r2.stdout + r2.stderr)[-800:]
        import json as _j
        pairs = _j.loads(r2.stdout.strip().splitlines()[-1])
        bad = {k: v for k, v in pairs.items() if v[0] != v[1]}
        if bad:
            return False, f"تصمیمِ بسته با موتور اصلی یکی نیست: {bad}"
        # برابری کافی نیست — **هر دو طرف می‌توانند یکسان خراب باشند**.
        # همین یک بار افتاد: `_stair` کندلِ خام را به ماژولِ دیکشنری‌خواه
        # می‌داد، هر دو طرف None برگرداندند و پروب سبز ماند. پس حضورِ
        # شاهد هم شرط است، نه فقط یکسان بودنش.
        if pairs.get("stair", [None])[0] is None:
            return False, "شاهدِ نردبان روی خروجی نیست (هر دو طرف None)"
        if (pairs.get("drop_radar") or [{}])[0].get("state") in (None, "UNKNOWN"):
            return False, "رادارِ ریزش روی سریِ مرجع «نامعلوم» داد"
    return True, "خودآزمایی سبز + تصمیم با موتور اصلی یکی است"


def main(argv):
    if "--check" in argv:
        if not OUT.exists():
            print("✗ فایل داشبورد ساخته نشده")
            return 1
        cur = OUT.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            fresh = build(Path(td) / OUT.name).read_text(encoding="utf-8")
        if cur != fresh:
            print("✗ فایل داشبورد از سورس عقب افتاده — دوباره بساز")
            return 1
        print("✓ فایل داشبورد با سورس هم‌گام است")
        return 0
    p = build()
    ok, why = verify(p)
    size_kb = p.stat().st_size / 1024
    print(f"{'✓' if ok else '✗'} {p.name} — {size_kb:.0f}KB · {why}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
