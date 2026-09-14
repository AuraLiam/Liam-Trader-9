"""صفِ بازبینی — «تولز اول، بعد ایجنت» (دستور حمید، ۱۴ سپتامبر).

حمید: «کارهایی که نیاز به reasoning ندارد را به شکل تولز آماده کن که انجام
بدهد و بعد ایجنت را وارد عمل کن که بررسی کند.»

این ماژول قطعی است و هیچ مدل زبانی ندارد (قانون ۰۶). از سطل‌های قانون ۱۷
(`signals/buckets.json`) و چند تابلوی دیگر می‌خواند و یک **صفِ کوتاه**
می‌سازد: کدام ایجنت، روی کدام تغییر، با کدام فایل‌ها باید فکر کند — و
کدام ایجنت‌ها امروز هیچ کاری ندارند. ایجنت اصلی (ارکستراتور) فقط ردیف‌های
`needs_reasoning=True` را به زیرایجنت می‌دهد؛ بقیه صدا زده نمی‌شوند.

سه دلیلِ «بازبینی لازم است»، به ترتیب اولویت:
  failed   منبعی جواب نداده — ایجنت داده‌ها باید علت را بگوید (E02/data-quality)
  stale    فایلی از سقف کهنگی گذشته — مالکش باید بگوید چرا (قانون ۱۳)
  changed  مهر/خلاصهٔ فایلی عوض شده — مالک و مصرف‌کننده‌ها بازخوانی می‌کنند

بعلاوه رویدادهای خاص که «تغییر» ساده نیستند:
  backtest_new   بک‌تست تازه نشسته (E18 + E22 بازبینی کنند)
  verdict_flip   حکم یک خانهٔ داور هندسه عوض شده (E18/E11/E16)
  killswitch     کیل‌سوییچ trip است (E16 — و حمید)

مرز: این صف **اهمیت** را قضاوت نمی‌کند و هیچ دروازه/امتیازی نمی‌سازد؛
فقط می‌گوید «چه چیزی عوض شده و چه کسی باید نگاهش کند». اهمیت همان جایی
است که ایجنت باید فکر کند — و فقط همان‌جا (قانون ۱۷ بند ۴).
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
SIGNALS = ROOT / "signals"
BUCKETS = SIGNALS / "buckets.json"
GEOMETRY = SIGNALS / "geometry-verdict.json"
KILLSWITCH = ROOT / "brain" / "killswitch.json"
OUT = SIGNALS / "review-queue.json"

# ایجنت‌های عملیاتی (زیرایجنت‌های .claude/agents) که ارکستراتور واقعاً
# صدا می‌زند — همان نگاشت dispatch.AGENT_ENGINES؛ این‌جا فقط ترتیب اولویت.
AGENT_ORDER = ["data-quality", "macro-dominance", "market-structure", "order-block",
               "liquidity", "lead-lag", "execution", "post-trade-learning", "research"]

# رویدادهای خاص → کدام انجین/ایجنت
EVENT_ROUTES = {
    "backtest_new": (["E18", "E22"], ["research"]),
    "verdict_flip": (["E18", "E11", "E16"], ["research"]),
    "killswitch": (["E16", "E23"], ["data-quality"]),
}

PRIORITY = {"failed": 0, "stale": 1, "changed": 2, "event": 1}


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return None


def _events(prev, geometry=None, killswitch=None):
    """رویدادهایی که «تغییرِ مهر» ساده نیستند و سطل‌ها نمی‌بینند."""
    ev = []
    g = geometry if geometry is not None else _load(GEOMETRY)
    prev_g = (prev or {}).get("_geometry") or {}
    g_sig = {}
    if g and g.get("status") == "OK":
        g_sig = {"generated": g.get("generated"),
                 "verdicts": {k: r.get("verdict") for k, r in (g.get("rows") or {}).items()}}
        if prev_g.get("generated") != g_sig["generated"]:
            ev.append({"kind": "backtest_new", "what": f"بک‌تست تازه: {g.get('backtest_at')}",
                       "read": ["signals/geometry-verdict.json"]})
        flips = [f"{k}: {prev_g.get('verdicts', {}).get(k)}→{v}"
                 for k, v in g_sig["verdicts"].items()
                 if prev_g.get("verdicts") and prev_g["verdicts"].get(k) not in (None, v)]
        if flips:
            ev.append({"kind": "verdict_flip", "what": "حکم عوض شد: " + "؛ ".join(flips[:6]),
                       "read": ["signals/geometry-verdict.json"]})
    ks = killswitch if killswitch is not None else _load(KILLSWITCH)
    if ks and ks.get("tripped"):
        ev.append({"kind": "killswitch", "what": f"کیل‌سوییچ فعال: {ks['tripped']}",
                   "read": ["brain/killswitch.json"]})
    return ev, g_sig


def build(buckets=None, prev=None, now_ms=None, geometry=None, killswitch=None):
    now = int(now_ms or time.time() * 1000)
    b = buckets if buckets is not None else (_load(BUCKETS) or {})
    engines = b.get("engines") or {}
    agents = b.get("agents") or {}
    events, g_sig = _events(prev, geometry, killswitch)

    rows = []
    # ۱) ایجنت‌های عملیاتی — از سطل‌های ادغام‌شدهٔ خودشان
    for name in AGENT_ORDER:
        a = agents.get(name) or {}
        reasons = []
        for eng in a.get("engines", []):
            e = engines.get(eng) or {}
            if e.get("failed"):
                reasons.append(("failed", eng, e["failed"]))
            if e.get("stale"):
                reasons.append(("stale", eng, e["stale"]))
        if a.get("changed"):
            reasons.append(("changed", None, a["changed"]))
        for ev in events:
            if name in EVENT_ROUTES.get(ev["kind"], ((), ()))[1]:
                reasons.append(("event", ev["kind"], [ev["what"]]))
        read = sorted(set(a.get("read_next", [])) |
                      {p for ev in events if name in EVENT_ROUTES.get(ev["kind"], ((), ()))[1]
                       for p in ev["read"]})
        rows.append({"agent": name, "engines": a.get("engines", []),
                     "needs_reasoning": bool(reasons),
                     "priority": min([PRIORITY[r[0]] for r in reasons], default=9),
                     "reasons": [{"kind": k, "engine": e, "items": v[:8]} for k, e, v in reasons],
                     "read_next": read[:12],
                     "digest": (a.get("digest") or "")[:400]})

    # ۲) انجین‌هایی که ایجنت عملیاتی ندارند ولی رویداد خاص دارند (E18/E22/E11/E16/E23)
    for ev in events:
        for eng in EVENT_ROUTES[ev["kind"]][0]:
            rows.append({"agent": eng, "engines": [eng], "needs_reasoning": True,
                         "priority": PRIORITY["event"],
                         "reasons": [{"kind": "event", "engine": ev["kind"], "items": [ev["what"]]}],
                         "read_next": ev["read"], "digest": ev["what"]})

    rows.sort(key=lambda r: (not r["needs_reasoning"], r["priority"], r["agent"]))
    todo = [r for r in rows if r["needs_reasoning"]]
    return {"generated": now, "buckets_at": b.get("generated"),
            "n_agents": len(rows), "n_todo": len(todo),
            "todo": [r["agent"] for r in todo],
            "idle": [r["agent"] for r in rows if not r["needs_reasoning"]],
            "events": events, "rows": rows,
            "how_to_use": ("ارکستراتور فقط ردیف‌های needs_reasoning را به زیرایجنت می‌دهد، "
                           "با read_next و reasons به‌عنوان ورودی؛ ایجنتِ idle صدا زده نمی‌شود "
                           "(قانون ۱۷/۱۸). ابزار = انجام؛ ایجنت = بررسی."),
            "boundary": ("این صف اهمیت را قضاوت نمی‌کند و هیچ دروازه/امتیازی نمی‌سازد؛ "
                         "فقط «چه عوض شد و چه کسی نگاه کند» (قانون ۰۵/۱۵)."),
            "_geometry": g_sig}


def render(q):
    L = [f"صف بازبینی: {q['n_todo']} از {q['n_agents']} ایجنت کار دارند · "
         f"{len(q['idle'])} بی‌کار (صدا زده نمی‌شوند)"]
    for ev in q["events"]:
        L.append(f"  ⚡ {ev['kind']}: {ev['what']}")
    for r in q["rows"]:
        if not r["needs_reasoning"]:
            continue
        why = "؛ ".join(f"{x['kind']}" + (f"[{x['engine']}]" if x["engine"] else "") +
                        ": " + "، ".join(map(str, x["items"][:4])) for x in r["reasons"])
        L.append(f"  → {r['agent']}: {why}")
        if r["read_next"]:
            L.append("      باز کن: " + ", ".join(r["read_next"][:6]))
    return "\n".join(L)


def write(doc):
    try:
        import brain
        if getattr(brain, "SANDBOX", False):
            print("review_queue: sandbox — ننوشت")
            return False
    except Exception:                                # noqa: BLE001
        pass
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
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

    from hamid import dispatch as DP
    check("ترتیب ایجنت‌ها دقیقاً همان نُه ایجنت دسته‌بند است",
          set(AGENT_ORDER) == set(DP.AGENT_ENGINES), str(set(AGENT_ORDER) ^ set(DP.AGENT_ENGINES)))

    # سطل ساختگی: یک ایجنت با شکست، یکی با تغییر، بقیه ساکت
    bk = {"generated": 1, "engines": {
        "E02": {"failed": ["fear_greed"], "stale": [], "changed": [], "read_next": []},
        "E03": {"failed": [], "stale": [], "changed": ["state:dominance.json"], "read_next": ["signals/dominance.json"]},
        "E07": {"failed": [], "stale": ["structure.json"], "changed": [], "read_next": ["signals/structure.json"]}},
        "agents": {n: {"engines": e, "read_next": [], "changed": [], "digest": ""}
                   for n, e in DP.AGENT_ENGINES.items()}}
    bk["agents"]["macro-dominance"]["changed"] = ["state:dominance.json"]
    bk["agents"]["macro-dominance"]["read_next"] = ["signals/dominance.json"]
    q = build(bk, prev={}, now_ms=2, geometry={"status": "NO_DATA"}, killswitch={})
    by = {r["agent"]: r for r in q["rows"]}
    check("ایجنت با تغییر کار دارد", by["macro-dominance"]["needs_reasoning"])
    check("و read_next‌اش همان فایل تغییرکرده است",
          by["macro-dominance"]["read_next"] == ["signals/dominance.json"])
    dq = by["data-quality"]
    check("شکستِ منبع به data-quality می‌رسد (E02 در سطلش)",
          dq["needs_reasoning"] and any(x["kind"] == "failed" for x in dq["reasons"]), str(dq))
    check("شکست اولویت ۰ دارد و اول صف است", q["rows"][0]["agent"] == "data-quality")
    ms = by["market-structure"]
    check("کهنگی به مالک می‌رسد (E07 → market-structure)",
          ms["needs_reasoning"] and any(x["kind"] == "stale" for x in ms["reasons"]))
    check("ایجنتِ بی‌تغییر بی‌کار است و در idle نشسته",
          "execution" in q["idle"] and not by["execution"]["needs_reasoning"])
    check("n_todo با ردیف‌ها می‌خواند", q["n_todo"] == sum(1 for r in q["rows"] if r["needs_reasoning"]))

    # رویدادِ بک‌تست تازه → E18/E22/research
    g1 = {"status": "OK", "generated": 100, "backtest_at": "t1",
          "rows": {"ibs|overall": {"verdict": "UNDECIDED"}}}
    q1 = build(bk, prev={}, now_ms=3, geometry=g1, killswitch={})
    check("بک‌تست تازه رویداد می‌سازد", any(e["kind"] == "backtest_new" for e in q1["events"]))
    check("و E18 و research به صف می‌آیند", {"E18", "E22", "research"} <= set(q1["todo"]))
    g2 = {"status": "OK", "generated": 200, "backtest_at": "t2",
          "rows": {"ibs|overall": {"verdict": "PROMOTE"}}}
    q2 = build(bk, prev=q1, now_ms=4, geometry=g2, killswitch={})
    check("تغییر حکم (UNDECIDED→PROMOTE) رویدادِ verdict_flip می‌سازد",
          any(e["kind"] == "verdict_flip" and "ibs|overall" in e["what"] for e in q2["events"]),
          str(q2["events"]))
    q3 = build(bk, prev=q2, now_ms=5, geometry=g2, killswitch={})
    check("همان بک‌تست دوباره رویداد نمی‌سازد (بی‌تغییر = بی‌ریزنینگ)",
          not any(e["kind"] in ("backtest_new", "verdict_flip") for e in q3["events"]))
    q4 = build(bk, prev=q2, now_ms=6, geometry=g2, killswitch={"tripped": "LOSS: −5.2R"})
    check("کیل‌سوییچِ فعال به صف E16 می‌آید", any(e["kind"] == "killswitch" for e in q4["events"])
          and "E16" in q4["todo"])
    check("سطلِ خالی → همه بی‌کار، صف خالی، بی‌خطا",
          build({}, prev={}, now_ms=7, geometry={}, killswitch={})["n_todo"] == 0)
    txt = render(q4)
    check("رندر متن فارسی با شمار کار/بی‌کار", "صف بازبینی" in txt and "بی‌کار" in txt)
    check("هیچ ردیفی دروازه/امتیاز نمی‌سازد (فقط کلیدهای مسیر)",
          all(set(r) == {"agent", "engines", "needs_reasoning", "priority", "reasons", "read_next", "digest"}
              for r in q4["rows"]))

    print(f"\n{'همهٔ' if not fail else ''} {ok} بررسیِ صف بازبینی گذشت" + (f" — {len(fail)} افتاد: {fail}" if fail else ""))
    return 0 if not fail else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    q = build(prev=_load(OUT))
    print(render(q))
    if a.write:
        write(q)
    return 0


if __name__ == "__main__":
    sys.exit(main())
