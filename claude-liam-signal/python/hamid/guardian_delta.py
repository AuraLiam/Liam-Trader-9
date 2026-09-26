#!/usr/bin/env python3
"""دلتای متخصص‌ها — رأی‌ها و دفتر پیپرِ هر مراقب، امروز در برابر دورهٔ قبل
(قانون ۱۸ بند ۵ — «باید تغییراتشون رو ببینم»).

هر مراقب دو ردپا دارد: رأی‌هایش (`brain/guardians/live-votes.jsonl`) و
معامله‌های کاغذی‌اش (`gd-<id>` در دفتر بسته). این ابزار برای پنجرهٔ
«اخیر» (پیش‌فرض ۲۴ ساعت) و پنجرهٔ «قبلی» (۲۴ ساعتِ پیش از آن) می‌شمارد:
نرخ امتناع، سهم تأیید/مخالف، میانگین رأی، n و میانگین R دفتر — و دلتا.
عددِ زیر کف نمونه (۲۰) گزارش نمی‌شود؛ «کم» می‌نویسد.

خروجی: `signals/guardian-delta.json` (ردیف قرارداد E00). فقط می‌خواند.

    python3 -m hamid.guardian_delta --write [--hours 24]
    python3 -m hamid.guardian_delta --selftest
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from hamid import ledger as _ledger                   # noqa: E402 - دفتر هفتگی‌پاره

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
VOTES = ROOT / "brain" / "guardians" / "live-votes.jsonl"
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OUT = ROOT / "signals" / "guardian-delta.json"
MIN_N = 20
GIDS = ("scorpio", "gemini", "taurus", "aries", "leo", "cancer",
        "pisces", "libra", "capricorn", "virgo", "sagittarius", "aquarius")


def _rows(p):
    if not _ledger.exists(p):
        return []
    out = []
    for ln in _ledger.text_lines(p):
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:                            # noqa: BLE001
            continue
    return out


def vote_stats(rows, gid):
    vals = [r.get("votes", {}).get(gid, "∅") for r in rows]
    n = len(vals)
    if n < MIN_N:
        return {"n": n, "low": True}
    ab = sum(1 for v in vals if v is None or v == "∅")
    nz = [v for v in vals if isinstance(v, (int, float))]
    return {"n": n, "abstain_pct": round(100 * ab / n, 1),
            "for_pct": round(100 * sum(1 for v in nz if v >= 0.15) / n, 1),
            "against_pct": round(100 * sum(1 for v in nz if v <= -0.15) / n, 1),
            "mean": round(statistics.fmean(nz), 3) if nz else None}


def desk_stats(rows, gid):
    rs = [r.get("R") for r in rows
          if str(r.get("stage_tag") or (r.get("why") or {}).get("stage") or "") == f"gd-{gid}"
          and isinstance(r.get("R"), (int, float))]
    n = len(rs)
    if n < MIN_N:
        return {"n": n, "low": True}
    return {"n": n, "win_pct": round(100 * sum(1 for x in rs if x > 0) / n, 1),
            "mean_r": round(statistics.fmean(rs), 3)}


def _delta(a, b, key):
    if a.get("low") or b.get("low") or a.get(key) is None or b.get(key) is None:
        return None
    return round(a[key] - b[key], 3)


def build(now_ms=None, hours=24, votes=None, closed=None):
    now = now_ms or time.time() * 1000
    w = hours * 3600 * 1000
    V = votes if votes is not None else _rows(VOTES)
    C = closed if closed is not None else _rows(CLOSED)
    v_now = [r for r in V if now - w <= r.get("at", 0) <= now]
    v_prev = [r for r in V if now - 2 * w <= r.get("at", 0) < now - w]
    c_now = [r for r in C if now - w <= (r.get("closed") or 0) <= now]
    c_prev = [r for r in C if now - 2 * w <= (r.get("closed") or 0) < now - w]
    out = {}
    for g in GIDS:
        vn, vp = vote_stats(v_now, g), vote_stats(v_prev, g)
        dn, dp = desk_stats(c_now, g), desk_stats(c_prev, g)
        out[g] = {"votes_now": vn, "votes_prev": vp, "desk_now": dn, "desk_prev": dp,
                  "delta": {"abstain_pct": _delta(vn, vp, "abstain_pct"),
                            "for_pct": _delta(vn, vp, "for_pct"),
                            "mean_vote": _delta(vn, vp, "mean"),
                            "desk_mean_r": _delta(dn, dp, "mean_r"),
                            "desk_n": (dn["n"] - dp["n"])}}
    active = [g for g in GIDS if not out[g]["desk_now"].get("low")]
    silent = [g for g in GIDS if out[g]["votes_now"].get("abstain_pct", 0) >= 90
              and not out[g]["votes_now"].get("low")]
    return {"generated": int(now), "window_h": hours, "guardians": out,
            "active_desks": active, "n_active_desks": len(active),
            "silent": silent,
            "boundary": (f"دلتا فقط با n≥{MIN_N} در هر دو پنجره؛ زیر آن «کم». دلتای یک روز "
                         "یادگیری را نه اثبات می‌کند نه رد (قانون ۰۳)")}


def render(d):
    L = [f"دلتای مراقبان — پنجرهٔ {d['window_h']}س · دفتر فعال: {d['n_active_desks']}/12 · ساکت: {d['silent'] or 'هیچ'}"]
    for g, r in d["guardians"].items():
        vn, dn, de = r["votes_now"], r["desk_now"], r["delta"]
        v = f"رأی n={vn['n']}" + ("" if vn.get("low") else f" ممتنع {vn['abstain_pct']}% تأیید {vn['for_pct']}%")
        k = f"دفتر n={dn['n']}" + ("" if dn.get("low") else f" برد {dn['win_pct']}% R̄ {dn['mean_r']:+.3f}")
        dl = " · ".join(f"Δ{k2}={v2:+}" for k2, v2 in de.items() if isinstance(v2, (int, float)) and k2 != "desk_n" and v2 != 0)
        L.append(f"  {g:<12} {v:<40} {k:<32} {dl}")
    return "\n".join(L)


def _selftest():
    ok, fail = 0, []

    def check(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1; print(f"  ✓ {name}")
        else:
            fail.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))

    now = 1_800_000_000_000
    H = 3600 * 1000
    def vote(at, **v):
        return {"at": at, "votes": {g: v.get(g, 0.0) for g in GIDS}}
    V = [vote(now - i * H // 2, gemini=None, leo=0.5, libra=-0.9) for i in range(40)] + \
        [vote(now - 24 * H - 1 - i * H // 2, gemini=None, leo=0.2, libra=-0.9) for i in range(40)]
    C = [{"closed": now - i * H // 2, "R": (1.0 if i % 2 else -0.5), "stage_tag": "gd-leo"} for i in range(30)] + \
        [{"closed": now - 24 * H - 1 - i * H // 2, "R": -0.2, "why": {"stage": "gd-leo"}} for i in range(30)] + \
        [{"closed": now - 3 * H, "R": 2.0, "stage_tag": "gd-virgo"}]
    d = build(now, 24, votes=V, closed=C)
    g = d["guardians"]
    check("جوزای همیشه‌ممتنع ۱۰۰٪ امتناع می‌گیرد و «ساکت» است", g["gemini"]["votes_now"]["abstain_pct"] == 100.0 and "gemini" in d["silent"])
    check("اسد: تأیید ۱۰۰٪ اکنون، و دلتای میانگین رأی +۰.۳", g["leo"]["votes_now"]["for_pct"] == 100.0 and g["leo"]["delta"]["mean_vote"] == 0.3)
    check("دفتر اسد از هر دو شکلِ مرحله خوانده می‌شود و دلتای R درست است",
          g["leo"]["desk_now"]["n"] == 30 and g["leo"]["desk_prev"]["n"] == 30 and g["leo"]["delta"]["desk_mean_r"] == round(0.25 + 0.2, 3))
    check("سنبله با n=۱ «کم» است و دلتا ندارد", g["virgo"]["desk_now"].get("low") and g["virgo"]["delta"]["desk_mean_r"] is None)
    check("میزانِ همیشه‌مخالف: مخالف ۱۰۰٪ و ساکت نیست", g["libra"]["votes_now"]["against_pct"] == 100.0 and "libra" not in d["silent"])
    check("شمار دفترهای فعال درست است", d["active_desks"] == ["leo"])
    check("رندر کار می‌کند", "دلتای مراقبان" in render(d))
    check("مرز n روی خروجی است", "n≥20" in d["boundary"])
    print(f"\nguardian_delta: {ok} بررسی سبز" + (f" · {len(fail)} قرمز: {fail}" if fail else ""))
    return 1 if fail else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    d = build(hours=a.hours)
    print(render(d))
    if a.write:
        try:
            import brain as _b
            if getattr(_b, "SANDBOX", False):
                return 0
        except Exception:                            # noqa: BLE001
            pass
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
