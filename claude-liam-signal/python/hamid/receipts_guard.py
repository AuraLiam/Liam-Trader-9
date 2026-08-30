"""بقای رسیدهای ارسال از reset زنجیره — رفع ریشه‌ای «رسید گم‌شدهٔ یونی».

## عیبی که این ماژول می‌بندد (اندازه‌گیری ۳۰ اوت)

سیگنال `smc|UNIUSDT|5m|LONG` در ۳۰ اوت ۱۲:۰۸:۵۰ UTC به تلگرام رفت — حمید
دیدش و رویش معامله کرد. ولی در ریپو **هیچ رسیدی از آن نماند**: نه ردیف
آرشیو شماره‌دار، نه ردیف `telegram-log`، نه ردیف فید پنل، نه پروندهٔ
پیپر. فقط سه کلید ضدتکرار ماند.

مکانیزم، خط به خط:

```
BK=/tmp/pump-radar-backup
cp signals/telegram-log.json  "$BK/"     ← عکس‌فوری، **قبل** از اسکن
cp signals/sent.json          "$BK/"
cp brain/paper/*.jsonl        "$BK/"
for i in 1..8; do
    git reset --hard origin/main         ← هرچه اسکن نوشته پاک می‌شود
    pump_radar --reapply "$BK"           ← فقط فهرست بالا برمی‌گردد
    scan.py --telegram                   ← اسکن و ارسال (فقط تلاش اول)
    git push … || retry
done
```

عکس‌فوریِ `$BK` **قبل از حلقه** گرفته می‌شود، یعنی قبل از این‌که اسکن
چیزی بفرستد. پس اگر پوشِ تلاش اول شکست بخورد و حلقه دور دوم بزند:

| فایل | سرنوشت |
|---|---|
| `sent.json` | ✅ زنده — `merge_sent` نسخهٔ پس‌ازاسکن را اجتماع می‌کند |
| `latest.json` | ✅ زنده — از `/tmp/scan-latest.json` برمی‌گردد |
| `telegram-log.json` | ❌ به نسخهٔ **پیش‌ازاسکن** برمی‌گردد (۴۰ ردیف، همان ۴۰ ردیف) |
| `archive/telegram-sent-*.jsonl` | ❌ اصلاً در فهرست نیست — پاک |
| `telegram-feed.json` | ❌ اصلاً در فهرست نیست — پاک |
| `brain/paper/*.jsonl` | ❌ به نسخهٔ **پیش‌ازاسکن** برمی‌گردد |

و این دقیقاً همان چیزی است که در دادهٔ ۳۰ اوت دیده شد. رفعِ PAXG (۲۶ اوت)
`sent.json` و دفترهای پیپر را به فهرست اضافه کرد — ولی عکس‌فوری را
**جای درستش** نبرد: بکاپی که قبل از تولید گرفته شود، تولیدِ خودش را
هرگز در بر ندارد.

## رفع

دو نیم‌کار که با هم کامل می‌شوند:

۱. **عکس‌فوری بعد از تولید** (`snapshot`) — بلافاصله پس از اسکن، رسیدها
   در `$BK/receipts/` می‌نشینند. زیرپوشهٔ جدا تا با انتظارهای `reapply`
   درگیر نشود.
۲. **بازگردانی با اجتماعِ هویت** (`restore`) — در هر دور حلقه، ردیف‌ها
   روی درختِ تازه **اجتماع** می‌شوند، نه بازنویسی. قانون ضد-merge:
   هیچ دفتری با نسخهٔ دیگر «یکی» نمی‌شود؛ فقط ردیفِ گم‌شده برمی‌گردد.

هویت هر ردیف:

- آرشیو `telegram-sent-*.jsonl` → `(at, sym, tf, dir)`
- آرشیو `telegram-feed-*.jsonl` → `(at, kind, title)`
- `telegram-feed.json` → همان، روی `rows`
- `telegram-log.json` → `(at, sym)` روی `sent`

شمارهٔ `n` در آرشیوها بعد از اجتماع **بازشماری** می‌شود تا پیاپی بماند
(دستور شماره‌گذاری، ۲۶ اوت شب).

## مرز

این ماژول فقط رسیدها را نگه می‌دارد. هیچ تصمیمی نمی‌گیرد، هیچ سیگنالی
نمی‌سازد و هیچ دروازه‌ای را دست نمی‌زند.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
SIG = ROOT / "signals"
ARCHIVE = SIG / "archive"

# فایل‌های تک — (مسیر نسبت به ریشه، کلید آرایه، فیلدهای هویت)
SINGLES = (
    ("signals/telegram-feed.json", "rows", ("at", "kind", "title")),
    ("signals/telegram-log.json", "sent", ("at", "sym")),
)
# آرشیوهای jsonl — (پیشوند نام، فیلدهای هویت)
ARCHIVES = (
    ("telegram-sent-", ("at", "sym", "tf", "dir")),
    ("telegram-feed-", ("at", "kind", "title")),
    ("delivery-failures-", ("at", "sym", "why")),
)


def _ident(row, fields):
    return tuple(row.get(f) for f in fields)


def _read_jsonl(p):
    out = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("{"):
                out.append(json.loads(line))
    except Exception:                                # noqa: BLE001
        pass
    return out


def snapshot(bk_dir):
    """رسیدهای **الان** را کنار می‌گذارد — بعد از اسکن، نه قبلش."""
    dst = Path(bk_dir) / "receipts"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for rel, _key, _ids in SINGLES:
        src = ROOT / rel
        if src.exists():
            shutil.copy(src, dst / Path(rel).name)
            n += 1
    if ARCHIVE.exists():
        adst = dst / "archive"
        adst.mkdir(exist_ok=True)
        for f in ARCHIVE.glob("*.jsonl"):
            if any(f.name.startswith(pfx) for pfx, _ in ARCHIVES):
                shutil.copy(f, adst / f.name)
                n += 1
    return n


def restore(bk_dir):
    """ردیف‌های گم‌شده را روی درختِ تازه برمی‌گرداند — اجتماع، نه بازنویسی."""
    src = Path(bk_dir) / "receipts"
    if not src.exists():
        return {"restored": 0, "why": "عکس‌فوری رسید وجود ندارد"}
    added = 0

    for rel, key, ids in SINGLES:
        b = src / Path(rel).name
        if not b.exists():
            continue
        try:
            ours = json.loads(b.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            continue
        tgt = ROOT / rel
        try:
            theirs = json.loads(tgt.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            theirs = {}
        rows = list(theirs.get(key) or [])
        seen = {_ident(r, ids) for r in rows if isinstance(r, dict)}
        for r in (ours.get(key) or []):
            if isinstance(r, dict) and _ident(r, ids) not in seen:
                rows.append(r)
                seen.add(_ident(r, ids))
                added += 1
        rows.sort(key=lambda r: r.get("at") or 0, reverse=True)
        merged = dict(theirs)
        merged[key] = rows
        # `generated` تازه‌ترین برنده است — عددِ عقب‌رفته، پاسبان کهنگی را
        # به دروغ می‌اندازد (درس ۲۵ اوت روی pump-radar)
        for stamp in ("generated", "at"):
            if stamp in ours or stamp in theirs:
                merged[stamp] = max(ours.get(stamp) or 0, theirs.get(stamp) or 0)
        tgt.parent.mkdir(parents=True, exist_ok=True)
        tgt.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")

    adir = src / "archive"
    if adir.exists():
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        for b in sorted(adir.glob("*.jsonl")):
            ids = next((i for pfx, i in ARCHIVES if b.name.startswith(pfx)), None)
            if ids is None:
                continue
            tgt = ARCHIVE / b.name
            rows = _read_jsonl(tgt)
            seen = {_ident(r, ids) for r in rows}
            for r in _read_jsonl(b):
                if _ident(r, ids) not in seen:
                    rows.append(r)
                    seen.add(_ident(r, ids))
                    added += 1
            rows.sort(key=lambda r: r.get("at") or 0)
            for i, r in enumerate(rows, 1):
                r["n"] = i                           # شماره‌گذاری پیاپی می‌ماند
            tgt.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                   for r in rows), encoding="utf-8")
    return {"restored": added}


def main(argv):
    if not argv or argv[0] not in ("--snapshot", "--restore"):
        print("usage: python3 -m hamid.receipts_guard --snapshot|--restore <dir>")
        return 2
    d = argv[1] if len(argv) > 1 else "/tmp/pump-radar-backup"
    if argv[0] == "--snapshot":
        print(f"رسیدها کنار گذاشته شد: {snapshot(d)} فایل")
    else:
        r = restore(d)
        print(f"رسیدهای بازگردانده‌شده: {r.get('restored')} ردیف"
              + (f" — {r['why']}" if r.get("why") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
