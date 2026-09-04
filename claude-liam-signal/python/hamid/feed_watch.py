#!/usr/bin/env python3
"""پاسبان خوراک زنده — «اصلاً قطع نشود» را می‌سنجد، نه امیدوار می‌ماند.

دستور حمید (۴ سپتامبر): «داده‌های زنده از تمامی منابع معتبر به ایجنت‌ها را
بررسی کنی که درست کار کند و اصلاً قطع نشود.»

## عیبی که این فایل می‌بندد

زنجیرهٔ جایگزینی از قبل خوب بود: بیت‌یونیکس پرپ → بایننس پرپ → MEXC پرپ →
ده صرافی اسپات. ولی **هیچ‌کس نمی‌دانست چند تا از این‌ها همین الان زنده‌اند.**
تا وقتی یکی جواب می‌داد سامانه کار می‌کرد و هیچ‌جا نوشته نمی‌شد که سیزده
منبع به یکی رسیده. یعنی از «همه‌چیز خوب» به «همه‌چیز خاموش» بدون هیچ
هشدارِ میانی — و آن لحظه دیر است.

قاعده: چیزی که شمرده نشود، مدیریت نمی‌شود. این پاسبان همهٔ منابع را
دوره‌ای می‌زند و حکم می‌دهد:

| حکم | یعنی | کار |
|---|---|---|
| `HEALTHY` | ≥۳ منبع زنده و منبعِ ترجیحی جواب می‌دهد | هیچ |
| `THIN` | ۱ یا ۲ منبع مانده | آلارم — هنوز کار می‌کند ولی حاشیهٔ امن رفته |
| `DEGRADED` | منبعِ ترجیحی (پرپ بیت‌یونیکس) افتاده ولی بقیه هستند | آلارم یک‌باره |
| `DARK` | هیچ منبعی جواب نمی‌دهد | آلارم فوری — سامانه کور است |

`THIN` مهم‌ترینِ این چهارتاست و دقیقاً همان چیزی است که تا امروز نبود:
هشدارِ **قبل از** خاموشی، نه بعدش.

## مرز

این پاسبان فقط می‌خواند و حکم می‌دهد (قانون ۰۵ — یک نویسنده برای هر
دامنه). هیچ منبعی را روشن/خاموش نمی‌کند؛ انتخابِ منبع کارِ
`sources.klines` است و دست‌نخورده ماند. آلارمش از `alert_gate` رد
می‌شود، پس تکرار نمی‌شود (قانون ۰۷).
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]

OUT = ROOT / "signals" / "feed-health.json"
HIST = ROOT / "brain" / "feed" / "health.jsonl"      # append-only

PROBE_SYM = "BTCUSDT"
PROBE_TF = "5m"
PROBE_BARS = 60
PREFERRED = "bitunix-perp"                           # دستور ۳۱ اوت
THIN_AT = 3                                          # کمتر از این = حاشیه رفته
STALE_MAX_S = 900                                    # کندلِ کهنه‌تر = مرده


def _probe_one(v, kind):
    """یک منبع را با کندلِ واقعی می‌زند — نه پینگ، نه شمارش خطا."""
    import sources
    t0 = time.time()
    try:
        rows = (v["fetch"](PROBE_SYM, PROBE_TF, PROBE_BARS) if v.get("fetch")
                else v["parse"](sources._json(v["url"](PROBE_SYM, PROBE_TF,
                                                       PROBE_BARS))))
        rows = rows[-PROBE_BARS:]
    except Exception as e:                           # noqa: BLE001
        return {"id": v["id"], "kind": kind, "alive": False,
                "why": f"{type(e).__name__}: {str(e)[:70]}",
                "ms": int((time.time() - t0) * 1000)}
    ms = int((time.time() - t0) * 1000)
    if not sources.sane(rows, PROBE_BARS):
        return {"id": v["id"], "kind": kind, "alive": False, "ms": ms,
                "why": f"سری ناسالم: {sources.sane_why(rows, PROBE_BARS)}"}
    # تازگی: منبعی که جواب می‌دهد ولی کندلش مالِ دیروز است، زنده نیست.
    last_ms = rows[-1][0] if isinstance(rows[-1], (list, tuple)) else rows[-1].get("t")
    age = (time.time() * 1000 - float(last_ms)) / 1000.0
    if age > STALE_MAX_S:
        return {"id": v["id"], "kind": kind, "alive": False, "ms": ms,
                "why": f"کندل {int(age / 60)} دقیقه کهنه است"}
    return {"id": v["id"], "kind": kind, "alive": True, "ms": ms,
            "bars": len(rows), "age_s": int(age)}


def probe(quiet=True):
    import sources
    rows = []
    for v in sources.PERP_VENUES:
        rows.append(_probe_one(v, "perp"))
    for v in sources.VENUES:
        rows.append(_probe_one(v, "spot"))
    if not quiet:
        for r in rows:
            mark = "✓" if r["alive"] else "✗"
            print(f"  {mark} {r['id']:<16} {r['kind']:<5} {r['ms']:>5}ms "
                  f"{r.get('why', '')}", flush=True)
    return rows


def verdict(rows):
    alive = [r for r in rows if r["alive"]]
    pref = next((r for r in rows if r["id"] == PREFERRED), None)
    pref_ok = bool(pref and pref["alive"])
    if not alive:
        v, why = "DARK", "هیچ منبعی جواب نمی‌دهد — سامانه کور است"
    elif len(alive) < THIN_AT:
        v, why = "THIN", (f"فقط {len(alive)} منبع زنده مانده (کف {THIN_AT}) — "
                          "هنوز کار می‌کند ولی حاشیهٔ امن رفته")
    elif not pref_ok:
        v, why = "DEGRADED", (f"منبعِ ترجیحی ({PREFERRED}) نمی‌دهد؛ "
                              f"{len(alive)} منبع دیگر جواب می‌دهند — "
                              "تحلیل روی بازارِ دیگری می‌نشیند")
    else:
        v, why = "HEALTHY", f"{len(alive)} منبع زنده، منبعِ ترجیحی سرِ کار"
    return v, why, alive, pref_ok


def snapshot(rows, now_ms=None):
    v, why, alive, pref_ok = verdict(rows)
    fast = sorted([r for r in alive], key=lambda r: r["ms"])[:3]
    return {
        "generated": int(now_ms if now_ms is not None else time.time() * 1000),
        "engine": "E02", "panel": "لیام تریدر ۹",
        "verdict": v, "why": why,
        "alive": len(alive), "total": len(rows),
        "preferred": PREFERRED, "preferred_ok": pref_ok,
        "perp_alive": len([r for r in alive if r["kind"] == "perp"]),
        "spot_alive": len([r for r in alive if r["kind"] == "spot"]),
        "fastest": [{"id": r["id"], "ms": r["ms"]} for r in fast],
        "sources": rows,
        "down": [{"id": r["id"], "why": r.get("why")} for r in rows
                 if not r["alive"]],
        "thresholds": {"thin_below": THIN_AT, "stale_max_s": STALE_MAX_S,
                       "probe": f"{PROBE_SYM} {PROBE_TF} × {PROBE_BARS}"},
        "boundary": "این پاسبان فقط می‌سنجد و حکم می‌دهد؛ انتخاب منبع کارِ "
                    "sources.klines است و دست‌نخورده ماند (قانون ۰۵).",
    }


def alarm_text(snap):
    """پیام فقط برای چیزی که حمید باید بداند — نه گزارشِ سلامتیِ روزمره."""
    if snap["verdict"] == "HEALTHY":
        return None
    lines = [f"📡 خوراک داده — {snap['verdict']}", snap["why"], ""]
    lines.append(f"زنده: {snap['alive']} از {snap['total']} "
                 f"(پرپ {snap['perp_alive']} · اسپات {snap['spot_alive']})")
    for d in snap["down"][:6]:
        lines.append(f"  ✗ {d['id']}: {d['why']}")
    if snap["verdict"] == "DARK":
        lines.append("\nتا وصل‌شدن، هیچ سیگنالی صادر نمی‌شود (قانون ۱: "
                     "دادهٔ ناموجود = NO_SIGNAL) — این درست‌ترین رفتار است.")
    return "\n".join(lines)


def run(write=False, alert=False, quiet=True):
    rows = probe(quiet=quiet)
    snap = snapshot(rows)
    if write:
        try:
            import brain
            if brain.blocked(OUT):                   # حالت شنی — قانون ۰۵
                write = False
        except Exception:                            # noqa: BLE001
            pass
    if write:
        try:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
            HIST.parent.mkdir(parents=True, exist_ok=True)
            with HIST.open("a", encoding="utf-8") as f:
                f.write(json.dumps({k: snap[k] for k in
                                    ("generated", "verdict", "alive", "total",
                                     "preferred_ok")}, ensure_ascii=False) + "\n")
        except Exception as e:                       # noqa: BLE001
            print(f"نوشتن نشد: {e}", flush=True)
    if alert:
        txt = alarm_text(snap)
        if txt:
            try:
                from hamid import alert_gate
                # کلیدِ درشت (قانون ۰۷): فقط حکم، نه فهرست منابع — وگرنه
                # هر بار که یک صرافی می‌آید و می‌رود، «کلید تازه» می‌شود
                # و همان اسپمی که ۲۳ اوت بسته شد برمی‌گردد.
                alert_gate.send(f"feed:{snap['verdict']}", txt)
            except Exception as e:                   # noqa: BLE001
                print(f"آلارم نرفت: {e}", flush=True)
    return snap


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    snap = run(write="--write" in argv, alert="--alert" in argv,
               quiet="--quiet" in argv)
    print(f"\nخوراک داده: {snap['verdict']} — {snap['why']}")
    print(f"  زنده {snap['alive']}/{snap['total']} · پرپ {snap['perp_alive']} · "
          f"اسپات {snap['spot_alive']} · ترجیحی "
          f"{'✓' if snap['preferred_ok'] else '✗'}")
    if snap["fastest"]:
        print("  سریع‌ترین: " + "، ".join(f"{f['id']} {f['ms']}ms"
                                          for f in snap["fastest"]))
    for d in snap["down"][:8]:
        print(f"  ✗ {d['id']}: {d['why']}")
    return 0 if snap["verdict"] != "DARK" else 1


if __name__ == "__main__":
    sys.exit(main())
