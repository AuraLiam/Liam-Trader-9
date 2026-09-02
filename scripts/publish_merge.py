#!/usr/bin/env python3
"""ادغامِ تک‌فایل با معنای خودش — بازوی پایتونیِ scripts/publish.sh.

    publish_merge.py <path> <ours_file|-> <theirs_file|-> <out_file>

همان handlerهای resolve_brain_conflicts.py را روی دو نسخهٔ یک فایل اجرا
می‌کند (دفتر → اجتماع، عکس‌فوری → مال ما، نشانگر → تاریخ جلوتر، سند →
origin) بدون این‌که merge واقعیِ گیت لازم باشد. چرا: مخزن ۴.۴ گیگابایت
تاریخچه دارد؛ هر merge روی چک‌اوتِ کم‌عمق یا باید تاریخچه بکشد (دقیقه‌ها،
دو بار job را تا سقف ۱۵ دقیقه خواباند) یا تاریخچه را بی‌ربط می‌بیند و
هزاران تعارض ساختگی می‌سازد. ناشر حالا اصلاً merge نمی‌کند: نوکِ origin
را می‌گیرد و فقط فایل‌هایی را که همین اجرا نوشته، با همین معنا رویش
می‌نشاند.

«-» یعنی آن طرف فایل را ندارد.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _load_resolver():
    spec = importlib.util.spec_from_file_location(
        "rbc", HERE / "resolve_brain_conflicts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv):
    path, ours_f, theirs_f, out_f = argv[1:5]
    ours = None if ours_f == "-" else Path(ours_f)
    theirs = None if theirs_f == "-" else Path(theirs_f)
    out = Path(out_f)

    if ours is None:                       # ما حذف کرده‌ایم → حذف
        if out.exists():
            out.unlink()
        return 0
    if theirs is None:                     # origin ندارد → مال ما
        shutil.copy(ours, out)
        return 0

    R = _load_resolver()

    def _stage(stage, p):
        f = ours if stage == 2 else theirs
        try:
            return f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None

    def _stage_bytes(stage, p):
        f = ours if stage == 2 else theirs
        return f.read_bytes()

    R._stage = _stage
    R._stage_bytes = _stage_bytes
    fn = R.handler_for(path) or R.take_ours
    if fn is R.take_ours:
        shutil.copy(ours, out)
        return 0
    if fn is R.take_theirs:
        shutil.copy(theirs, out)
        return 0
    # handlerهای معنادار روی ROOT/path می‌نویسند؛ همان را به out می‌بریم.
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fn(path)
    except Exception as e:                 # noqa: BLE001 — هرگز job را نکش
        print(f"publish_merge: {path}: {type(e).__name__}: {e} → مال ما",
              file=sys.stderr)
        shutil.copy(ours, out)
        return 0
    if target.resolve() != out.resolve():
        shutil.copy(target, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
