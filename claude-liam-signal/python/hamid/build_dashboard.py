#!/usr/bin/env python3
"""سازندهٔ نسخهٔ فشردهٔ داشبورد (دستور حمید، ۲۹ اوت — «داشبورد نشون نمیده»).

مشکل: `liam9_strategy.py` با هر نسخه بزرگ‌تر شده — ۸۶KB در v2.8 که کار
می‌کرد، ۹۲KB در v2.9، و ۹۵KB در v3.0 که حمید گفت داشبورد نشانش نمی‌دهد.
جعبهٔ «استراتژی» داشبورد سقف دارد و فایل از آن رد شده است.

چرا فایل بزرگ است: ~۴۰٪ حجمش کامنت و داک‌استرینگ فارسی است — یعنی همان
چیزی که ما را از تکرارِ اشتباه‌های گذشته نگه می‌دارد. پس **پاکشان
نمی‌کنیم**؛ دو خروجی از یک منبع می‌سازیم:

  · `liam9_strategy.py` — نسخهٔ خوانا و مستند، مرجعِ ریپو و بازبینی.
  · `liam9_strategy_dash.py` — همان کد، بدون کامنت و داک‌استرینگ، برای
    جعبهٔ داشبورد.

قیدِ ایمنی که این ابزار را از «یک اسکریپت کوچک‌کننده» جدا می‌کند: خروجی
تا **خودآزمایی خودِ استراتژی را پاس نکند** نوشته نمی‌شود. یعنی فشرده‌سازی
هرگز بی‌صدا رفتار را عوض نمی‌کند؛ اگر عوض کند، ساخت شکست می‌خورد.

    python3 -m hamid.build_dashboard          # ساخت + اثبات
    python3 -m hamid.build_dashboard --out /tmp/x.py
"""
import io
import re
import subprocess
import sys
import tempfile
import time
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]

SRC = PY / "liam9_strategy.py"
OUT = PY / "liam9_strategy_dash.py"


def _version(src):
    m = re.search(r"نسخهٔ داشبورد ([\d.]+)", src)
    return m.group(1) if m else "?"


def _docstring_spans(src):
    """جای دقیقِ داک‌استرینگ‌ها از AST — نه حدسِ نشانه‌ای.

    نسخهٔ اولِ همین تابع با هیوریستیک «رشته‌ای که اول دستور است» کار
    می‌کرد و **کلیدِ دیکشنری را داک‌استرینگ گرفت**: `"version": …` شد
    `"": …` و کل فایل با KeyError افتاد. محافظِ ساخت (خودآزمایی روی
    خروجی) همان‌جا جلویش را گرفت — و درس ماند: جای داک‌استرینگ را باید
    از درختِ نحو پرسید، نه از ترتیب نشانه‌ها."""
    import ast
    spans = set()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            spans.add((first.value.lineno, first.value.col_offset))
    return spans


def strip(src):
    """کامنت و داک‌استرینگ را برمی‌دارد؛ به هیچ دستوری دست نمی‌زند."""
    docs = _docstring_spans(src)
    keep = []
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type == tokenize.COMMENT:
            continue
        if t.type == tokenize.STRING and t.start in docs:
            keep.append((tokenize.STRING, '""'))     # جای‌گزینِ کوتاه، نه حذف
            continue
        keep.append((t.type, t.string))
    out = tokenize.untokenize(keep)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def banner(src, body):
    v = _version(src)
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(ROOT), capture_output=True,
                             text=True, timeout=20).stdout.strip() or "?"
    except Exception:                                # noqa: BLE001
        sha = "?"
    head = (
        "#!/usr/bin/env python3\n"
        f'"""لیام تریدر ۹ — استراتژی داشبورد {v} (نسخهٔ فشرده)\n\n'
        "این فایل برای جعبهٔ «استراتژی» داشبورد ساخته شده: همان کدِ کامل،\n"
        "بدون کامنت و داک‌استرینگ، تا از سقف اندازهٔ جعبه رد نشود.\n"
        "نسخهٔ خوانا و مستند در ریپو است — این‌جا فقط اجرا.\n\n"
        f"ساخت: {stamp} · کامیت {sha}\n"
        "منبع: claude-liam-signal/python/liam9_strategy.py\n"
        "ساخته‌شده با: python3 -m hamid.build_dashboard\n\n"
        "هر تغییرِ تحلیلی در ریپو انجام می‌شود و این فایل دوباره ساخته\n"
        "می‌شود؛ دست‌کاری مستقیمِ این نسخه در دور بعدِ ساخت پاک می‌شود.\n"
        '"""\n')
    return head + body


def verify(path):
    """خودآزمایی خودِ استراتژی روی خروجی — بدون این، ساخت پذیرفته نیست."""
    r = subprocess.run([sys.executable, str(path), "--selftest"],
                       cwd=str(PY), capture_output=True, text=True, timeout=600)
    return r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]


def build(out_path=None):
    src = SRC.read_text(encoding="utf-8")
    body = strip(src)
    text = banner(src, body)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     dir=str(PY), encoding="utf-8") as f:
        f.write(text)
        tmp = Path(f.name)
    try:
        ok, tail = verify(tmp)
        if not ok:
            raise SystemExit(f"ساخت رد شد — خروجی فشرده خودآزمایی را پاس نکرد:\n{tail[0]}")
        dest = Path(out_path) if out_path else OUT
        dest.write_text(text, encoding="utf-8")
    finally:
        tmp.unlink(missing_ok=True)
    a, b = len(src.encode()), len(text.encode())
    return {"src_bytes": a, "out_bytes": b,
            "saved_pct": round(100 * (a - b) / a), "path": str(dest),
            "selftest": tail[0]}


def main(argv):
    out = None
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    r = build(out)
    print(f"منبع  : {r['src_bytes']:,} بایت")
    print(f"فشرده : {r['out_bytes']:,} بایت  ({r['saved_pct']}٪ کوچک‌تر)")
    print(f"خروجی : {r['path']}")
    print(f"اثبات : {r['selftest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
