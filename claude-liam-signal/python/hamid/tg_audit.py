"""ممیزی هفتگی تلگرام — «پیام‌های یک هفتهٔ اخیر را بررسی کن» (دستور حمید، ۱۴ سپتامبر).

بی‌LLM (قانون ۰۶). از دفترهای append-only خودِ ارسال می‌خواند (هر چیزی که
@LiamTrader9_Bot فرستاده در `signals/archive/telegram-feed-*.jsonl` و
`telegram-sent-*.jsonl` ثبت است) و جواب سه سؤال را با عدد می‌دهد:

  ۱. سرشماری: هر روز چند پیام از هر نوع؟ کدام نوع‌ها در فهرست مجازِ قانون ۱۱
     (سیگنال، نتیجه، ۵ گزارش پامپ، گزارش کار، دامیننس ساعتی) نیستند؟
     → «بی‌مخاطب» = پیامی که حمید کاری با آن نمی‌تواند بکند.
  ۲. سیگنال: چند تا در روز، کِی سقفِ ۲۴ پر می‌شود، چه ترکیبی (استراتژی/تایم/جهت)؟
  ۳. نتیجهٔ سیگنال‌های ارسالی با **تطبیق دقیق** به دفتر بستهٔ پیپر (نماد+تایم+
     جهت+ورود، بازشدن در ±۳۰د از ارسال): توزیع نتیجه، R خالص، برد؛ ردیفِ
     بی‌تطبیق شمرده می‌شود، حدس زده نمی‌شود (قانون عددِ درست).

خروجی: signals/tg-audit.json (ردیف قرارداد، E25) + متن. هیچ چیزی را عوض نمی‌کند.
"""
import argparse
import collections
import glob
import json
import statistics
import sys
import time
from pathlib import Path
from hamid import ledger as _ledger                   # noqa: E402 - دفتر هفتگی‌پاره

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
ARCHIVE = ROOT / "signals" / "archive"
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OUT = ROOT / "signals" / "tg-audit.json"

DAY_MS = 86_400_000
# فهرست مجاز قانون ۱۱ بند ۳ + سقف روزانهٔ هر کدام (از کادنس مصوب)
ALLOWED = {"signal": 24, "outcome": None, "pump_report": 5, "work_report": 3, "dom_report": 24, "trade_mgmt": None}
MATCH_WINDOW_MS = 30 * 60_000


def _rows(pattern, since_ms):
    out = []
    for f in sorted(glob.glob(str(ARCHIVE / pattern))):
        for line in open(f, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:                        # noqa: BLE001
                continue
            if (r.get("at") or 0) >= since_ms:
                out.append(r)
    return out


def _day(ms):
    return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))


def _alert_class(title):
    t = title or ""
    if "شکاک" in t:
        return "skeptic"
    if "ارجاع خودکار" in t:
        return "escalation"
    if "مسیر" in t or "TP1" in t or "سیو سود" in t:
        return "trail_rung"
    return "other_alert"


def census(feed):
    by_day = collections.defaultdict(collections.Counter)
    for r in feed:
        by_day[_day(r["at"])][r.get("kind") or "?"] += 1
    alerts = collections.Counter(_alert_class(r.get("title")) for r in feed if r.get("kind") == "alert")
    total = collections.Counter(r.get("kind") or "?" for r in feed)
    n_days = max(1, len(by_day))
    useless = {k: v for k, v in total.items() if k not in ALLOWED}
    over_cap = {}
    for d, c in by_day.items():
        for k, cap in ALLOWED.items():
            if cap and c.get(k, 0) > cap:
                over_cap.setdefault(k, []).append(f"{d}:{c[k]}")
    return {"days": n_days, "per_day": {d: dict(c) for d, c in sorted(by_day.items())},
            "total": dict(total), "alert_classes": dict(alerts),
            "useless_kinds": useless, "useless_share_pct": round(100 * sum(useless.values()) / max(1, sum(total.values())), 1),
            "over_cap": over_cap}


def signal_stats(feed):
    sg = [r for r in feed if r.get("kind") == "signal"]
    per_day = collections.defaultdict(list)
    for r in sg:
        per_day[_day(r["at"])].append(r["at"])
    cap_hour = {}
    for d, ts in per_day.items():
        ts.sort()
        cap_hour[d] = {"n": len(ts), "first": time.strftime("%H:%M", time.gmtime(ts[0] / 1000)),
                       "last": time.strftime("%H:%M", time.gmtime(ts[-1] / 1000))}
    ex = [r.get("extra") or {} for r in sg]
    return {"n": len(sg), "per_day": cap_hour,
            "strategy": dict(collections.Counter(e.get("strategy") for e in ex)),
            "tf": dict(collections.Counter(e.get("tf") for e in ex)),
            "dir": dict(collections.Counter(e.get("dir") for e in ex)),
            "hour_utc": dict(sorted(collections.Counter(time.gmtime(r["at"] / 1000).tm_hour for r in sg).items()))}


def _closed(since_ms):
    out = []
    if not _ledger.exists(CLOSED):
        return out
    for line in _ledger.text_lines(CLOSED):
        try:
            r = json.loads(line)
        except Exception:                            # noqa: BLE001
            continue
        if (r.get("opened") or 0) >= since_ms - DAY_MS and not r.get("stage_tag"):
            out.append(r)
    return out


def _net(r):
    if r.get("R_net") is not None:
        return r["R_net"]
    return (r.get("R") or 0) - (r.get("fee_r") or 0)


def match_outcomes(sent, closed):
    """تطبیق دقیق: نماد+تایم+جهت+ورود (نسبی ۱e-6) و opened در ±۳۰د از ارسال."""
    idx = collections.defaultdict(list)
    for r in closed:
        idx[(r.get("sym"), r.get("tf"), r.get("dir"))].append(r)
    matched, unmatched, used = [], 0, set()
    for s in sent:
        cands = idx.get((s.get("sym"), s.get("tf"), s.get("dir"))) or []
        best = None
        for r in cands:
            if id(r) in used:
                continue
            e1, e2 = s.get("entry"), r.get("entry")
            if not e1 or not e2 or abs(e1 - e2) / abs(e1) > 1e-6:
                continue
            if abs((r.get("opened") or 0) - s["at"]) > MATCH_WINDOW_MS:
                continue
            best = r
            break
        if best is None:
            unmatched += 1
            continue
        used.add(id(best))
        matched.append({"sym": s.get("sym"), "tf": s.get("tf"), "dir": s.get("dir"), "strategy": s.get("strategy"),
                        "outcome": best.get("outcome"), "net": _net(best), "R": best.get("R"), "fee_r": best.get("fee_r"),
                        "mfe_r": best.get("mfe_r"), "held_h": best.get("held_h"), "at": s["at"]})
    return matched, unmatched


def _stats(rows):
    if not rows:
        return {"n": 0}
    xs = [r["net"] for r in rows if r.get("net") is not None]
    return {"n": len(rows), "mean_net": round(statistics.mean(xs), 3) if xs else None,
            "sum_net": round(sum(xs), 1) if xs else None,
            "win_pct": round(100 * sum(1 for x in xs if x > 0) / len(xs), 1) if xs else None,
            "outcomes": dict(collections.Counter(r.get("outcome") for r in rows))}


def outcome_stats(matched, unmatched, n_sent):
    by = {}
    for grp, key in (("strategy", lambda r: r.get("strategy")), ("tf", lambda r: r.get("tf")), ("dir", lambda r: r.get("dir"))):
        d = collections.defaultdict(list)
        for r in matched:
            d[key(r)].append(r)
        by[grp] = {k: _stats(v) for k, v in d.items()}
    trail = [r["net"] for r in matched if r.get("outcome") == "trail" and r.get("net") is not None]
    return {"sent": n_sent, "matched": len(matched), "unmatched": unmatched,
            "match_pct": round(100 * len(matched) / max(1, n_sent), 1),
            "overall": _stats(matched), "by": by,
            "trail_zero_share_pct": round(100 * sum(1 for x in trail if abs(x) < 0.02) / len(trail), 1) if trail else None,
            "open_or_unfound": unmatched,
            "method": "تطبیق دقیق نماد+تایم+جهت+ورود، opened در ±۳۰د از ارسال؛ ردیف بدون stage_tag؛ R خالص از R_net"}


def build(days=7, now_ms=None):
    now = int(now_ms or time.time() * 1000)
    since = now - days * DAY_MS
    feed = _rows("telegram-feed-*.jsonl", since)
    sent = _rows("telegram-sent-*.jsonl", since)
    closed = _closed(since)
    matched, unmatched = match_outcomes(sent, closed)
    return {"generated": now, "window_days": days, "since": since,
            "census": census(feed), "signals": signal_stats(feed),
            "outcomes": outcome_stats(matched, unmatched, len(sent)),
            "boundary": ("فقط پیام‌های خودِ بات از دفتر ارسال؛ پیام‌های حمید به بات جدا (brain/fomo). "
                         "نتیجه‌ها روی دفتر پیپر (فیل کامل، بی‌لغزش) — سقف خوش‌بینانهٔ اجرای دستی."),
            "rule": "قانون ۱۱ بند ۳: تلگرام فقط سیگنال، نتیجه، ۵ گزارش پامپ، گزارش کار، دامیننس ساعتی"}


def render(a):
    c, s, o = a["census"], a["signals"], a["outcomes"]
    L = [f"ممیزی تلگرام {a['window_days']} روز — {sum(c['total'].values())} پیام · "
         f"بی‌مخاطب {c['useless_share_pct']}٪ {c['useless_kinds']} · کلاس آلارم {c['alert_classes']}"]
    for d, cnt in c["per_day"].items():
        L.append(f"  {d}: " + " · ".join(f"{k}={v}" for k, v in sorted(cnt.items())))
    if c["over_cap"]:
        L.append(f"  بالاتر از سقف: {c['over_cap']}")
    L.append(f"سیگنال: {s['n']} · استراتژی {s['strategy']} · تایم {s['tf']} · جهت {s['dir']}")
    L.append(f"نتیجه: {o['matched']}/{o['sent']} تطبیق ({o['match_pct']}٪) · {o['overall']}")
    for g, d in o["by"].items():
        L.append(f"  به تفکیک {g}: " + " | ".join(f"{k}: n={v['n']} R̄={v.get('mean_net')} برد={v.get('win_pct')}٪" for k, v in d.items()))
    L.append(f"  تریل در ≈صفر: {o['trail_zero_share_pct']}٪")
    return "\n".join(L)


def write(a):
    try:
        import brain
        if getattr(brain, "SANDBOX", False):
            return False
    except Exception:                                # noqa: BLE001
        pass
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def _selftest():
    ok, fail = 0, []

    def check(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1
            print(f"  ✓ {name}")
        else:
            fail.append(name)
            print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))

    t0 = 1_789_000_000_000
    feed = [{"at": t0, "kind": "signal", "title": "AUSDT 5m LONG", "extra": {"strategy": "ibs", "tf": "5m", "dir": "LONG"}},
            {"at": t0 + 1, "kind": "alert", "title": "🚨 ارجاع خودکار (E2): x"},
            {"at": t0 + 2, "kind": "alert", "title": "🕵️ شکاک — 1 مورد"},
            {"at": t0 + 3, "kind": "alert", "title": "⅓ مسیر تارگت رد شد"},
            {"at": t0 + 4, "kind": "dom_report", "title": "x"}]
    c = census(feed)
    check("پیام‌های خارج از فهرست قانون ۱۱ «بی‌مخاطب» شمرده می‌شوند", c["useless_kinds"] == {"alert": 3} and c["useless_share_pct"] == 60.0, str(c))
    check("کلاس آلارم‌ها جدا شمرده می‌شود", c["alert_classes"] == {"escalation": 1, "skeptic": 1, "trail_rung": 1}, str(c["alert_classes"]))
    feed25 = [{"at": t0 + i * 60000, "kind": "dom_report", "title": "x"} for i in range(25)]
    check("بالاتر از سقف روزانه ثبت می‌شود", "dom_report" in census(feed25)["over_cap"])
    sent = [{"at": t0, "sym": "AUSDT", "tf": "5m", "dir": "LONG", "entry": 1.0, "strategy": "ibs"},
            {"at": t0, "sym": "BUSDT", "tf": "5m", "dir": "LONG", "entry": 2.0, "strategy": "smc"}]
    closed = [{"sym": "AUSDT", "tf": "5m", "dir": "LONG", "entry": 1.0, "opened": t0 + 5 * 60000, "outcome": "target", "R": 2.0, "fee_r": 0.3, "R_net": 1.7},
              {"sym": "AUSDT", "tf": "5m", "dir": "LONG", "entry": 1.0, "opened": t0 + 5 * 3600_000, "outcome": "stop", "R": -1, "fee_r": 0.3},
              {"sym": "BUSDT", "tf": "5m", "dir": "LONG", "entry": 2.0001, "opened": t0, "outcome": "stop", "R": -1}]
    m, u = match_outcomes(sent, closed)
    check("تطبیق دقیق: همان ورود و پنجرهٔ ±۳۰د؛ ردیف ۵ساعت بعد و ورودِ متفاوت تطبیق نمی‌خورد",
          len(m) == 1 and u == 1 and m[0]["outcome"] == "target" and m[0]["net"] == 1.7, str((m, u)))
    o = outcome_stats(m, u, 2)
    check("آمار نتیجه با n و روش", o["matched"] == 1 and o["match_pct"] == 50.0 and "روش" not in o["method"][:0] and o["method"])
    check("بی‌ارسال → آمار خالی، بی‌خطا", outcome_stats([], 0, 0)["overall"]["n"] == 0)
    print(f"\ntg_audit: {ok} بررسی سبز" + (f" — {len(fail)} افتاد: {fail}" if fail else ""))
    return 0 if not fail else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    doc = build(days=a.days)
    print(render(doc))
    if a.write:
        write(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
