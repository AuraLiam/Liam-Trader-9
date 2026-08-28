#!/usr/bin/env python3
"""ممیزِ حلقهٔ بسته — هیچ سیگنالی بیرون از جعبه نمی‌ماند (دستور حمید، ۲۸ اوت).

حمید: «پنل یک جعبهٔ زیباست؛ وقتی درش را برمی‌داری باید یک سامانهٔ یکپارچه
ببینی که هیچ فعالیتی خارج از قوانین جعبه انجام نمی‌دهد. سیگنالی که از
تلگرام می‌رود باید هم در تست‌های یادگیری باشد، هم در سیگنال نهایی پنل،
و هم نتیجه‌اش در یادگیری و علت‌یابی.»

پس هر سیگنالِ ارسالی باید **چهار رد** بگذارد و این ماژول هر چهار را
می‌شمرد. چیزی که شمرده نشود، ادعاست:

| رد | کجا | یعنی |
|---|---|---|
| ۱ تحویل | `signals/telegram-log.json` | واقعاً برای حمید رفت |
| ۲ پنل | `signals/telegram-feed.json` | پنل همان را نشان می‌دهد |
| ۳ یادگیری | `brain/paper/{open,closed}.jsonl` با `tg_msg_id` | تحت پیگیری است |
| ۴ علت‌یابی | `brain/cases/` یا `outcome` روی ردیف بسته | نتیجه هضم شد |

سیگنالی که رد ۳ ندارد، «تجربه» نمی‌سازد. سیگنالی که رد ۴ ندارد، درس
نمی‌شود. هر دو، نشتیِ حلقه‌اند — و این ماژول با اسم و زمان نشان‌شان
می‌دهد، نه با جملهٔ کلی.

مرز (قانون ۰۵): فقط می‌خواند. خروجی‌اش `signals/loop-audit.json` است.

    python3 -m hamid.loop_audit            # گزارش
    python3 -m hamid.loop_audit --write    # + نوشتن خروجی
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

SIG = ROOT / "signals"
BRAIN = ROOT / "brain"
OUT = SIG / "loop-audit.json"
WINDOW_H = 72          # پنجرهٔ ممیزی: ۳ روز


def _rows(p):
    try:
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    except Exception:                                # noqa: BLE001
        return []


def _load(p, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def audit(window_h=WINDOW_H):
    now = time.time() * 1000
    lo = now - window_h * 3600 * 1000

    sent = [s for s in ((_load(SIG / "telegram-log.json", {}) or {}).get("sent") or [])
            if (s.get("at") or 0) >= lo]
    feed = [r for r in ((_load(SIG / "telegram-feed.json", {}) or {}).get("rows") or [])
            if r.get("kind") == "signal" and (r.get("at") or 0) >= lo]
    ledger = _rows(BRAIN / "paper" / "open.jsonl") + _rows(BRAIN / "paper" / "closed.jsonl")
    cases = {p.stem for p in (BRAIN / "cases").glob("*.json")} if (BRAIN / "cases").exists() else set()

    # ردیف دفتر با کلیدِ (نماد، دقیقهٔ باز شدن) و همچنین با tg_msg_id
    by_sym = {}
    mids = set()
    for r in ledger:
        why = r.get("why") or {}
        if why.get("tg_msg_id"):
            mids.add(why["tg_msg_id"])
        by_sym.setdefault(r.get("sym"), []).append(r)

    feed_keys = {(r.get("extra") or {}).get("sym") for r in feed}
    # مرزِ صادقانه، اجراشده نه فقط اعلام‌شده: دفتر پنل (telegram-feed) از
    # ۲۸ اوت ساخته شد. ارسال‌های قبل از اولین ردیفش نمی‌توانند در آن باشند،
    # پس «نشتیِ پنل» شمردنشان نشتیِ ساختگی است. مبنا = زمان اولین ردیف
    # دفتر؛ اگر دفتر هنوز خالی است، رد پنل اصلاً سنجیده نمی‌شود.
    all_feed = ((_load(SIG / "telegram-feed.json", {}) or {}).get("rows") or [])
    feed_since = min((r.get("at") or 0) for r in all_feed) if all_feed else None

    leaks = []
    ok = 0
    for s in sent:
        sym, at = s.get("sym"), s.get("at") or 0
        row = None
        for r in by_sym.get(sym, []):
            if abs((r.get("opened") or 0) - at) < 90 * 60000:      # ±۹۰ دقیقه
                row = r
                break
        miss = []
        if feed_since is not None and at >= feed_since and sym not in feed_keys:
            miss.append("panel")            # رد ۲: پنل
        if row is None:
            miss.append("learning")         # رد ۳: یادگیری
        elif row.get("closed") and not (row.get("outcome") or
                                        any(sym in c for c in cases)):
            miss.append("rootcause")        # رد ۴: علت‌یابی
        if miss:
            leaks.append({"sym": sym, "tf": s.get("tf"), "dir": s.get("dir"),
                          "at": at, "missing": miss})
        else:
            ok += 1

    closed_sig = [r for r in ledger
                  if (r.get("why") or {}).get("tg_msg_id") and r.get("closed")]
    digested = [r for r in closed_sig if r.get("outcome")]
    return {"generated": int(now), "window_h": window_h,
            "n_sent": len(sent), "n_feed": len(feed),
            "n_ledger_with_msgid": len(mids),
            "n_closed_sig": len(closed_sig), "n_digested": len(digested),
            "closed_loop": ok, "leaks": leaks[:40], "n_leaks": len(leaks)}


def packet(a):
    from hamid import evidence_packet as EP
    total = a["n_sent"] or 1
    pct = round(100 * a["closed_loop"] / total)
    return EP.build(
        claim=(f"{a['closed_loop']} از {a['n_sent']} سیگنالِ {a['window_h']} ساعت "
               f"اخیر هر چهار رد را دارند ({pct}٪)"),
        numbers={"ارسال": a["n_sent"], "روی پنل": a["n_feed"],
                 "در دفتر": a["n_ledger_with_msgid"],
                 "بسته": a["n_closed_sig"], "هضم‌شده": a["n_digested"],
                 "نشتی": a["n_leaks"]},
        track_record=(f"{a['n_digested']} از {a['n_closed_sig']} سیگنالِ بسته "
                      f"نتیجه‌شان ثبت شده"),
        scenario_up="نشتی صفر شود → هر سیگنال تجربه می‌سازد و وزن اتاق‌ها از دادهٔ کامل می‌آید",
        scenario_down=("نشتی بماند → کارنامه از نمونهٔ ناقص ساخته می‌شود و "
                       "CI روی دادهٔ سوگیرانه محاسبه می‌شود (همان خطای دفتر باددار ۲۴ اوت)"),
        invalidator="ثبت پس‌گذشتهٔ همان ردیف در دفتر، نشتی را باطل می‌کند",
        sources=["signals/telegram-log.json", "signals/telegram-feed.json",
                 "brain/paper/*.jsonl", "brain/cases/"],
        limit=("پنجرهٔ ۷۲ ساعت است و رد «پنل» فقط از دفتر تازهٔ telegram-feed "
               "خوانده می‌شود؛ ارسال‌های قبل از ساخت آن دفتر عمداً شمرده "
               "نمی‌شوند تا نشتیِ ساختگی گزارش نشود"))


def main(argv):
    a = audit()
    from hamid import evidence_packet as EP
    print(EP.render(packet(a)))
    if a["leaks"]:
        print("\nنشتی‌ها:")
        for l in a["leaks"][:12]:
            t = time.strftime("%m-%d %H:%M", time.gmtime(l["at"] / 1000))
            print(f"  {t} {l['sym']} {l['tf']} {l['dir']} — بدون: {'، '.join(l['missing'])}")
    if "--write" in argv:
        OUT.write_text(json.dumps({**a, "packet": packet(a)}, ensure_ascii=False),
                       encoding="utf-8")
        print(f"\nنوشته شد: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
