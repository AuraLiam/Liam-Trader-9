#!/usr/bin/env python3
"""دسته‌بند — صندوقِ ورودیِ اسکن‌بردار را به سطلِ هر انجین/ایجنت می‌ریزد
(دستور حمید، ۱۳ سپتامبر).

حمید: «یک تولز دیگه ایجاد کن که داده‌هایی که اومده رو دسته‌بندی کنه و
بعد ایجنت بر اساس نوع فعالیتش میره داده‌های مورد نظرشو آپدیت می‌کنه.»

═══════════════════════════════════════════════════════════════════════
  قاعدهٔ مسیریابی — از قرارداد، نه از حدس
═══════════════════════════════════════════════════════════════════════

هر آیتمِ **وضعیت** به سطلِ مالکش می‌رود (`owner` در قرارداد) و به هر
مصرف‌کننده‌ای که ردیفِ قرارداد نام برده. هر آیتمِ **بیرونی** طبق
جدولِ ثابتِ `EXTERNAL_ROUTES` می‌رود — جدولی که خودش آزمون دارد تا هیچ
منبعی بی‌سطل نماند و هیچ سطلی روی خبر/جمعیت وزنِ تصمیم نگیرد (قانون
۱۵: این‌ها فقط دیدگاه‌اند و روی سطل برچسبِ «viewpoint» می‌خورند).

نُه ایجنتِ عملیاتیِ `.claude/agents/` هم هر کدام روی یک یا چند انجین
نگاشت شده‌اند (`AGENT_ENGINES`) تا ایجنت با نامِ خودش سطلش را پیدا کند.

═══════════════════════════════════════════════════════════════════════
  چه چیزی در هر سطل هست — و چرا کوچک است
═══════════════════════════════════════════════════════════════════════

  digest      یک پاراگرافِ فارسیِ قطعی: چند تازه، چند کهنه، چه چیزی از
              دورِ قبل عوض شده، کدام منبع شکست خورده. سقفِ طول دارد.
  changed     شناسهٔ آیتم‌هایی که از دورِ قبل عوض شده‌اند (مهرِ زمانِ
              تولید یا خلاصه فرق کرده).
  read_next   فقط همان فایل‌های خامی که **ارزشِ بازکردن** دارند — یعنی
              تغییرکرده یا کهنه. این همان جایی است که توکن ذخیره
              می‌شود: ایجنت سطل را می‌خواند (چند صد توکن) و اگر
              `read_next` خالی بود، هیچ فایلی باز نمی‌کند.
  items       آیتم‌های سطل، فقط با خلاصه — نه محتوای کامل.

مرزها: فقط می‌خواند و `signals/buckets.json` خودش را می‌نویسد (قانون
۰۵). هیچ دروازه/امتیازی نمی‌سازد. «تغییر» یعنی مهر یا خلاصه فرق کرده،
نه قضاوت دربارهٔ اهمیت — قضاوت کارِ ایجنت است، همان‌جا که ریزنینگ
معنا دارد.

    python3 -m hamid.dispatch --write
    python3 -m hamid.dispatch --bucket E03        # سطل یک انجین را چاپ کن
    python3 -m hamid.dispatch --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]

SIGNALS = ROOT / "signals"
INTAKE = SIGNALS / "intake.json"
OUT = SIGNALS / "buckets.json"
DIGEST_MAX = 700               # نویسه — سقفِ خلاصهٔ هر سطل

# خوراکِ بیرونی → انجین‌ها. خبر/جمعیت/تقویم «دیدگاه»‌اند (قانون ۱۵).
EXTERNAL_ROUTES = {
    "fear_greed": (("E15", "E05"), "viewpoint"),
    "funding":    (("E10", "E16"), "evidence"),
    "calendar":   (("E05", "E14", "E03"), "viewpoint"),
    "news":       (("E14",), "viewpoint"),
    "trending":   (("E12", "E15"), "viewpoint"),
    "unlocks":    (("E14",), "viewpoint"),
}

# نُه ایجنتِ عملیاتی → انجین‌هایی که سطلشان را می‌خوانند
AGENT_ENGINES = {
    # ۲۶ سپتامبر: E04/E07/E09 فایلِ خودشان را ندارند، پس market-structure
    # همیشه سطلِ خالی می‌گرفت و قاعدهٔ «read_next خالی = چیزی نخوان» عملاً
    # کورش می‌کرد. ورودیِ واقعیِ کارش اضافه شد: ستاپ‌ها (E17)، اردر بلاک
    # (E08)، بستر BTC (E06). execution هم ستاپ و دامیننس را ندید.
    "macro-dominance":     ("E03", "E04", "E05", "E06"),
    "market-structure":    ("E07", "E17", "E08", "E06"),
    "order-block":         ("E08", "E10"),
    "liquidity":           ("E10",),
    "lead-lag":            ("E12", "E06"),
    "execution":           ("E09", "E11", "E19", "E17", "E03"),
    "post-trade-learning": ("E20", "E21"),
    "research":            ("E22", "E13"),
    "data-quality":        ("E02", "E23"),
}

# مصرف‌کننده‌های نمادین در قرارداد → انجین
CONSUMER_ALIAS = {"lead": "E00", "panel": "E24", "telegram": "E25", "all": None}


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return None


def _engines_for(item):
    """آیتم → مجموعهٔ انجین‌هایی که باید ببینندش."""
    out = set()
    if item.get("family") == "state":
        if item.get("owner"):
            out.add(item["owner"])
        cons = item.get("consumer")
        # مصرف‌کننده در قرارداد متنِ آزاد است («panel+telegram»، «E18/E22/E11 + MCP»)؛
        # تا ۲۶ سپتامبر فقط رشتهٔ دقیق خوانده می‌شد و ستونِ مصرف‌کننده هیچ‌چیز را مسیر نمی‌داد.
        for c in (cons if isinstance(cons, list) else [cons] if cons else []):
            for tok in re.split(r"[+·/,\s]+", str(c)):
                tok = tok.strip()
                if re.fullmatch(r"E\d\d", tok):
                    out.add(tok)
                elif tok in CONSUMER_ALIAS and CONSUMER_ALIAS[tok]:
                    out.add(CONSUMER_ALIAS[tok])
        out.add("E00")                               # ارکستراتور همه را می‌بیند
    else:
        eng, _ = EXTERNAL_ROUTES.get(item.get("source"), ((), "viewpoint"))
        out.update(eng)
        out.add("E00")
    return out


def _sig(item):
    """امضای «تغییر»: مهرِ تولید + خلاصه/بار. برابر = عوض نشده."""
    if item.get("family") == "state":
        return json.dumps([item.get("at"), item.get("digest")], sort_keys=True, ensure_ascii=False)
    return json.dumps([item.get("ok"), item.get("payload"), item.get("err")],
                      sort_keys=True, ensure_ascii=False)


def build(intake, prev=None, now_ms=None):
    now = now_ms or time.time() * 1000
    prev_sigs = (prev or {}).get("_sigs") or {}
    items = (intake or {}).get("items") or []
    sigs = {i["id"]: _sig(i) for i in items}
    changed_ids = {k for k, v in sigs.items() if prev_sigs.get(k) != v}

    buckets = {}
    for it in items:
        for eng in _engines_for(it):
            b = buckets.setdefault(eng, {"items": [], "changed": [], "stale": [],
                                         "failed": [], "read_next": [], "viewpoint": []})
            slim = {k: it.get(k) for k in ("id", "family", "source", "owner", "ok",
                                           "age_min", "max_age_min", "fresh", "err")
                    if it.get(k) is not None}
            if it.get("family") == "external":
                slim["payload"] = it.get("payload")
                if EXTERNAL_ROUTES.get(it.get("source"), ((), "viewpoint"))[1] == "viewpoint":
                    b["viewpoint"].append(it["id"])
            else:
                slim["digest"] = it.get("digest")
            b["items"].append(slim)
            if it["id"] in changed_ids:
                b["changed"].append(it["id"])
            if it.get("ok") and it.get("family") == "state" and not it.get("fresh"):
                b["stale"].append(it["source"])
            # غایبِ اختیاری (فایل‌های سرویس محلی روی رانر) شکست نیست —
            # همان تفکیکِ intake/state_bus؛ وگرنه شمارِ شکست بی‌معنا می‌شود.
            if not it.get("ok") and it.get("err") != "absent-optional":
                b["failed"].append(it["source"])
            if it.get("family") == "state" and (it["id"] in changed_ids or
                                                (it.get("ok") and not it.get("fresh"))):
                b["read_next"].append(f"signals/{it['source']}")

    for eng, b in buckets.items():
        n = len(b["items"])
        fresh = sum(1 for i in b["items"] if i.get("fresh"))
        parts = [f"{n} آیتم · {fresh} تازه · {len(b['stale'])} کهنه · "
                 f"{len(b['failed'])} شکست · {len(b['changed'])} تغییر از دورِ قبل."]
        if b["changed"]:
            parts.append("تغییر: " + "، ".join(b["changed"][:8]))
        if b["stale"]:
            parts.append("کهنه: " + "، ".join(b["stale"][:6]))
        if b["failed"]:
            parts.append("شکست: " + "، ".join(b["failed"][:6]))
        if b["viewpoint"]:
            parts.append("دیدگاه (نه دروازه — قانون ۱۵): " + "، ".join(b["viewpoint"]))
        parts.append("باز کن: " + ("، ".join(b["read_next"][:8]) if b["read_next"]
                                    else "هیچ — چیزی عوض نشده"))
        b["digest"] = " ".join(parts)[:DIGEST_MAX]
        b["n"] = n
        b["read_next"] = b["read_next"][:12]

    agents = {a: {"engines": list(e),
                  "read_next": sorted({p for x in e for p in buckets.get(x, {}).get("read_next", [])})[:12],
                  "changed": sorted({c for x in e for c in buckets.get(x, {}).get("changed", [])}),
                  "digest": " | ".join(f"{x}: {buckets[x]['digest'][:160]}" for x in e if x in buckets)[:DIGEST_MAX]}
              for a, e in AGENT_ENGINES.items()}

    return {"generated": int(now), "intake_at": (intake or {}).get("generated"),
            "n_items": len(items), "n_changed": len(changed_ids),
            "engines": buckets, "agents": agents,
            "how_to_use": ("ایجنت اول سطل خودش را می‌خواند (engines[Exx] یا agents[نام]). "
                           "فقط اگر read_next خالی نبود، همان فایل‌ها را باز می‌کند. "
                           "ریزنینگ فقط روی «تغییر»، نه روی بازخوانیِ همه‌چیز."),
            "boundary": ("دسته‌بند فقط مسیر می‌دهد و «تغییر» را می‌شمارد؛ اهمیت را "
                         "قضاوت نمی‌کند و هیچ دروازه/امتیازی نمی‌سازد (قانون ۰۵/۱۵)."),
            "_sigs": sigs}


def write(doc):
    try:
        import brain as _b
        if getattr(_b, "SANDBOX", False):
            return False
    except Exception:                                # noqa: BLE001
        pass
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return True


def render_bucket(doc, key):
    b = (doc.get("engines") or {}).get(key) or (doc.get("agents") or {}).get(key)
    if not b:
        return f"سطلِ «{key}» وجود ندارد"
    L = [f"سطل {key}: {b['digest']}"]
    if b.get("read_next"):
        L.append("  باز کن: " + ", ".join(b["read_next"]))
    return "\n".join(L)


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

    # ۱) هر خوراکِ بیرونیِ اعلام‌شده در اسکن‌بردار مسیر دارد — هیچ منبعِ بی‌سطل
    from hamid import intake as IN
    srcs = {s for s, _, _ in IN.EXTERNAL}
    check("هر منبعِ بیرونیِ اسکن‌بردار در جدولِ مسیر هست", srcs <= set(EXTERNAL_ROUTES), str(srcs - set(EXTERNAL_ROUTES)))
    check("خبر/تقویم/جمعیت/ترند/آنلاک «دیدگاه» برچسب خورده‌اند (قانون ۱۵)",
          all(EXTERNAL_ROUTES[s][1] == "viewpoint" for s in ("news", "calendar", "fear_greed", "trending", "unlocks")))
    check("هر نُه ایجنت عملیاتی نگاشت دارند",
          set(AGENT_ENGINES) == {"macro-dominance", "market-structure", "order-block", "liquidity",
                                 "lead-lag", "execution", "post-trade-learning", "research", "data-quality"})

    # ۲) مسیریابی روی صندوقِ ساختگی
    now = 1_800_000_000_000
    intake = {"generated": now, "items": [
        {"id": "state:dominance.json", "family": "state", "source": "dominance.json", "owner": "E03",
         "consumer": "lead", "ok": True, "at": now - 60000, "age_min": 1, "max_age_min": 45, "fresh": True, "digest": {"v": 1}},
        {"id": "state:latest.json", "family": "state", "source": "latest.json", "owner": "E17",
         "consumer": ["E25", "panel"], "ok": True, "at": now - 90 * 60000, "age_min": 90, "max_age_min": 45, "fresh": False, "digest": {"v": 2}},
        {"id": "state:gone.json", "family": "state", "source": "gone.json", "owner": "E02", "ok": False, "err": "missing"},
        {"id": "ext:news", "family": "external", "source": "news", "ok": True, "payload": [{"t": "x"}]},
        {"id": "ext:funding", "family": "external", "source": "funding", "ok": False, "err": "timeout>20s"},
    ]}
    doc = build(intake, prev=None, now_ms=now)
    E = doc["engines"]
    check("آیتم وضعیت به مالکش می‌رود", "state:dominance.json" in [i["id"] for i in E["E03"]["items"]])
    check("و به مصرف‌کننده‌های نام‌برده (E25، پنل=E24)",
          "state:latest.json" in [i["id"] for i in E["E25"]["items"]] and
          "state:latest.json" in [i["id"] for i in E["E24"]["items"]])
    check("ارکستراتور همه را می‌بیند", E["E00"]["n"] == 5)
    check("خبر به E14 می‌رود و «دیدگاه» است", "ext:news" in E["E14"]["viewpoint"])
    check("فاندینگِ شکست‌خورده در failed سطلِ E10 است", "funding" in E["E10"]["failed"])
    check("فایلِ کهنه در read_next مالکش است (ارزشِ بازکردن دارد)",
          "signals/latest.json" in E["E17"]["read_next"])
    check("همه در دورِ اول «تغییر» شمرده می‌شوند (دورِ قبلی نیست)", doc["n_changed"] == 5)
    check("خلاصهٔ هر سطل زیر سقف است", all(len(b["digest"]) <= DIGEST_MAX for b in E.values()))
    check("سطل ایجنت macro-dominance از E03 پر می‌شود",
          "state:dominance.json" in doc["agents"]["macro-dominance"]["changed"])

    # ۳) دورِ دوم بی‌تغییر → read_next فقط کهنه‌ها، changed خالی
    doc2 = build(intake, prev=doc, now_ms=now + 1)
    check("دورِ دوم با همان داده: هیچ «تغییری» نیست", doc2["n_changed"] == 0)
    check("و read_next سطلِ تازه خالی است — ایجنت هیچ فایلی باز نمی‌کند",
          doc2["engines"]["E03"]["read_next"] == [] and "هیچ" in doc2["engines"]["E03"]["digest"])
    check("ولی فایلِ کهنه هنوز read_next است", "signals/latest.json" in doc2["engines"]["E17"]["read_next"])
    # ۴) تغییرِ واقعی دیده می‌شود
    intake2 = json.loads(json.dumps(intake))
    intake2["items"][0]["digest"] = {"v": 9}
    doc3 = build(intake2, prev=doc2, now_ms=now + 2)
    check("تغییرِ خلاصهٔ یک فایل، فقط همان را «تغییر» می‌کند",
          doc3["engines"]["E03"]["changed"] == ["state:dominance.json"] and doc3["n_changed"] == 1)
    # ۵) مرزها
    check("راهنمای مصرف و مرزِ صادقانه روی خروجی است", "read_next" in doc["how_to_use"] and "قانون" in doc["boundary"])
    check("رندرِ سطلِ ناموجود خطا نمی‌دهد", "وجود ندارد" in render_bucket(doc, "E99"))
    import brain as _b
    old = getattr(_b, "SANDBOX", False)
    _b.SANDBOX = True
    try:
        check("در حالت شنی نمی‌نویسد", write(doc) is False)
    finally:
        _b.SANDBOX = old

    print(f"\ndispatch: {ok} بررسی سبز" + (f" · {len(fail)} قرمز: {fail}" if fail else ""))
    return 1 if fail else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--bucket", help="چاپ سطل یک انجین (E03) یا ایجنت (macro-dominance)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if a.bucket:
        print(render_bucket(_load(OUT) or {}, a.bucket))
        return 0
    intake = _load(INTAKE)
    if not intake:
        print("dispatch: صندوقِ ورودی نیست — اول hamid.intake --write")
        return 0
    doc = build(intake, prev=_load(OUT))
    print(f"dispatch: {doc['n_items']} آیتم → {len(doc['engines'])} سطل انجین · "
          f"{doc['n_changed']} تغییر از دورِ قبل")
    if a.write:
        write(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
