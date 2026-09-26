#!/usr/bin/env python3
"""اسکن‌بردار — هر ۵ دقیقه همهٔ داده‌ای که ایجنت‌ها دنبالش می‌رفتند، یک‌جا
(دستور حمید، ۱۳ سپتامبر).

حمید: «یک سری کارها که نیاز به ریزنینگ نداره رو توی تولز پیاده کن که
اطلاعات رو هر ۵ دقیقه بیاره… همه داده‌هایی که ایجنت‌ها باید می‌رفتن
دنبالش رو تبدیل به تولز کن.»

═══════════════════════════════════════════════════════════════════════
  چه چیزی را جمع می‌کند و از کجا
═══════════════════════════════════════════════════════════════════════

دو خانوادهٔ آیتم، در یک صندوقِ ورودی (`signals/intake.json`):

۱. **وضعیتِ داخلی** — هر فایلِ `live` در `config/state_registry.json`.
   فهرست از خودِ قرارداد مشتق می‌شود، نه دست‌نویس (درس ۶ سپتامبر: سه
   حادثهٔ انتشار یک علت داشتند — فهرستی که آدم باید به‌خاطر بسپارد).
   برای هر فایل: سن، سقف، تازه/کهنه، و یک **خلاصهٔ کوچک** (چند فیلدِ
   سطح‌بالا)، نه محتوای کامل. ماژول تازه‌ای که ردیف قرارداد بگیرد،
   خودبه‌خود این‌جا هم دیده می‌شود.

۲. **خوراکِ بیرونی** — ترس‌وطمع، فاندینگ، تقویم، خبر، ترندِ کوین‌گکو،
   آنلاک — از همان `hamid/intel.py` که قبلاً هم بود. هر منبع سقفِ زمانی
   جدا دارد؛ منبعی که جواب نداد `ok:false` می‌گیرد با نامِ خطا. **هیچ
   عددی ساخته نمی‌شود** (قانون ۱).

═══════════════════════════════════════════════════════════════════════
  چرا این توکن کم می‌کند
═══════════════════════════════════════════════════════════════════════

قبلاً هر ایجنت/انجین در هر نوبت چند فایلِ چندصدخطی را باز می‌کرد تا
بفهمد «چه عوض شده». حالا یک ابزارِ قطعی همان را هر ۵ دقیقه می‌سازد و
`hamid/dispatch.py` برایش سطلِ کوچک می‌سازد. ایجنت سطل می‌خواند (چند
صد توکن)، و فقط اگر سطل گفت «تغییر کرده» یا «کهنه»، فایل خام را باز
می‌کند. ریزنینگ فقط جایی خرج می‌شود که چیزی عوض شده.

مرزها:
  · فقط می‌خواند و صندوقِ خودش را می‌نویسد (قانون ۰۵: یک نویسنده).
  · هیچ دروازه و امتیازی را عوض نمی‌کند؛ خوراکِ خبر/جمعیت طبق قانون ۱۵
    فقط دیدگاه است و همان‌طور برچسب می‌خورد.
  · کادنسِ ۵دقیقه‌ای روی Actions واقعاً ۵–۱۵ دقیقه است (دورِ زنجیره)؛
    ۵دقیقهٔ دقیق کارِ سرویس محلی liam9d است (قانون ۰۲). ادعای بیشتر
    نمی‌کنیم — مهرِ زمانِ هر آیتم روی خودش است.

    python3 -m hamid.intake --write
    python3 -m hamid.intake --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]

REGISTRY = ROOT / "config" / "state_registry.json"
SIGNALS = ROOT / "signals"
OUT = SIGNALS / "intake.json"

SOURCE_TIMEOUT_S = 20          # هر منبعِ بیرونی؛ کل اجرا زیر دو دقیقه می‌ماند
DIGEST_KEYS = 8                # چند فیلدِ سطح‌بالا از هر فایلِ وضعیت
DIGEST_STR = 90                # طولِ هر مقدارِ متنی در خلاصه

# خوراک‌های بیرونی: (شناسه، تابعِ intel، برش‌دهندهٔ خروجی به چیزی کوچک)
def _fg(d):      return {"value": d.get("value"), "label": d.get("label")}
def _fund(d):    return d[:10] if isinstance(d, list) else d
def _cal(d):     return d[:6] if isinstance(d, list) else d
def _news(d):    return [{"t": (x.get("title") or "")[:120], "s": x.get("source"),
                          "at": x.get("at") or x.get("ts")} for x in (d or [])][:20] \
                        if isinstance(d, list) else d
def _trend(d):   return d[:10] if isinstance(d, list) else d
def _unl(d):     return d[:8] if isinstance(d, list) else d

EXTERNAL = (
    ("fear_greed", "fear_greed", _fg),
    ("funding",    "funding",    _fund),
    ("calendar",   "calendar",   _cal),
    ("news",       "news",       _news),
    ("trending",   "trending",   _trend),
    ("unlocks",    "unlocks",    _unl),
)


def _registry():
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8")).get("files") or {}
    except Exception:                                # noqa: BLE001
        return {}


def _digest(doc):
    """چند فیلدِ سطح‌بالا — نه محتوای کامل. هدف: «چه هست/چه عوض شد»."""
    if isinstance(doc, list):
        return {"_list": len(doc)}
    if not isinstance(doc, dict):
        return {"_type": type(doc).__name__}
    out = {}
    for k in list(doc.keys())[:DIGEST_KEYS]:
        v = doc[k]
        if isinstance(v, (int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, str):
            out[k] = v[:DIGEST_STR]
        elif isinstance(v, list):
            out[k] = f"[{len(v)}]"
        elif isinstance(v, dict):
            out[k] = "{" + ",".join(list(v.keys())[:5]) + "}"
    return out


def _generated_ms(doc, path):
    g = doc.get("generated") if isinstance(doc, dict) else None
    if isinstance(g, (int, float)):
        return float(g)
    if isinstance(g, str):
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M UTC", "%Y-%m-%dT%H:%M:%S"):
            try:
                return time.mktime(time.strptime(g, fmt)) * 1000 - time.timezone * 1000
            except ValueError:
                continue
    try:
        return path.stat().st_mtime * 1000
    except OSError:
        return None


def collect_state(now_ms=None, registry=None):
    """یک آیتم برای هر فایلِ `live` قرارداد — سن در برابر سقفش + خلاصه."""
    now = now_ms or time.time() * 1000
    reg = registry if registry is not None else _registry()
    items = []
    for name, row in sorted(reg.items()):
        if (row or {}).get("kind") != "live":
            continue
        p = SIGNALS / name
        it = {"id": f"state:{name}", "family": "state", "source": name,
              "owner": row.get("owner"), "layer": row.get("layer"),
              "consumer": row.get("consumer"), "critical": bool(row.get("critical")),
              "optional": bool(row.get("optional")),
              "max_age_min": row.get("max_age_min")}
        if not p.exists():
            # اثبات محصول ۱۳ سپتامبر: دورِ اول روی رانر ۵ «شکست» داد که سه‌تایش
            # فایل‌های اختیاریِ سرویس محلی بودند (liam9d، beacon، feed-health)
            # و دوتایش خروجیِ خودِ همین دو ابزار که هنوز ساخته نشده بود.
            # غایبِ اختیاری شکست نیست — همان تفکیکی که state_bus می‌کند؛
            # وگرنه شمارِ «شکست» بی‌معنا می‌شود و بعدش نادیده گرفته می‌شود.
            it.update(ok=False, err="absent-optional" if it["optional"] else "missing")
            items.append(it)
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:                       # noqa: BLE001
            it.update(ok=False, err=f"unreadable:{type(e).__name__}")
            items.append(it)
            continue
        g = _generated_ms(doc, p)
        age = None if g is None else round((now - g) / 60000.0, 1)
        cap = row.get("max_age_min")
        it.update(ok=True, at=g, age_min=age,
                  fresh=(age is not None and (cap is None or age <= cap)),
                  digest=_digest(doc))
        items.append(it)
    return items


def collect_external(timeout_s=SOURCE_TIMEOUT_S, intel=None):
    """خوراک‌های بیرونی، هر کدام با سقفِ زمانِ خودش. شکست = ثبتِ شکست."""
    if intel is None:
        try:
            from hamid import intel as _i
            intel = _i
        except Exception as e:                       # noqa: BLE001
            return [{"id": f"ext:{sid}", "family": "external", "source": sid,
                     "ok": False, "err": f"intel unavailable:{type(e).__name__}"}
                    for sid, _, _ in EXTERNAL]
    now = time.time() * 1000
    items = []
    with ThreadPoolExecutor(max_workers=len(EXTERNAL)) as ex:
        futs = {sid: ex.submit(getattr(intel, fn)) for sid, fn, _ in EXTERNAL
                if hasattr(intel, fn)}
        for sid, fn, cut in EXTERNAL:
            it = {"id": f"ext:{sid}", "family": "external", "source": sid, "at": now}
            f = futs.get(sid)
            if f is None:
                it.update(ok=False, err="no fetcher")
            else:
                try:
                    pay = cut(f.result(timeout=timeout_s))
                    # منبعی که خودش «در دسترس نیست» می‌گوید، موفق نیست (قانون ۱) —
                    # ۲۶ سپتامبر: unlocks با status=UNAVAILABLE «ok:true» می‌گرفت.
                    bad = isinstance(pay, dict) and str(pay.get("status", "")).upper() in (
                        "UNAVAILABLE", "UNVERIFIED", "ERROR")
                    it.update(ok=not bad, payload=pay)
                    if bad:
                        it["err"] = f"payload:{pay.get('status')}"
                except FutTimeout:
                    it.update(ok=False, err=f"timeout>{timeout_s}s")
                except Exception as e:               # noqa: BLE001
                    # کدِ وضعیت HTTP هم ثبت می‌شود (۴۰۳/۴۲۹/۵۰۳ سه علتِ متفاوت‌اند)
                    it.update(ok=False, err=type(e).__name__ + (f":{e.code}" if hasattr(e, "code") else ""))
            items.append(it)
    return items


def build(now_ms=None, external=True, intel=None, registry=None,
          timeout_s=SOURCE_TIMEOUT_S):
    now = now_ms or time.time() * 1000
    state = collect_state(now, registry=registry)
    ext = collect_external(timeout_s=timeout_s, intel=intel) if external else []
    items = state + ext
    ok = sum(1 for i in items if i.get("ok"))
    absent_opt = sorted(i["source"] for i in items if i.get("err") == "absent-optional")
    failed = sorted(i["source"] for i in items
                    if not i.get("ok") and i.get("err") != "absent-optional")
    return {"generated": int(now),
            "n_items": len(items), "n_ok": ok, "n_failed": len(failed),
            "n_absent_optional": len(absent_opt),
            "n_state": len(state), "n_external": len(ext),
            "stale": sorted(i["source"] for i in state if i.get("ok") and not i.get("fresh")),
            "failed": failed, "absent_optional": absent_opt,
            "items": items,
            "boundary": ("صندوقِ ورودی فقط می‌گوید چه هست و چقدر تازه است؛ هیچ "
                         "حکم و امتیازی نمی‌سازد. خوراکِ خبر/جمعیت دیدگاه است "
                         "(قانون ۱۵). کادنس روی Actions ~۵–۱۵ دقیقه، محلی ۵.")}


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


def _selftest():
    import tempfile
    ok, fail = 0, []

    def check(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1
            print(f"  ✓ {name}")
        else:
            fail.append(name)
            print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))

    global SIGNALS
    old_sig = SIGNALS
    tmp = Path(tempfile.mkdtemp(prefix="intake-"))
    SIGNALS = tmp
    try:
        now = 1_800_000_000_000
        reg = {"a.json": {"kind": "live", "owner": "E03", "max_age_min": 10, "layer": "L2", "consumer": "lead"},
               "b.json": {"kind": "live", "owner": "E14", "max_age_min": 10, "layer": "L2"},
               "c.json": {"kind": "ledger", "owner": "E25"},
               "d.json": {"kind": "live", "owner": "E23", "max_age_min": 5}}
        (tmp / "a.json").write_text(json.dumps({"generated": now - 2 * 60000, "x": 1,
                                                "long": "س" * 500, "arr": [1, 2, 3]}))
        (tmp / "b.json").write_text(json.dumps({"generated": now - 40 * 60000}))
        (tmp / "d.json").write_text("{broken")
        st = collect_state(now, registry=reg)
        ids = {i["source"] for i in st}
        check("فقط فایل‌های live از قرارداد گرفته می‌شوند (ledger نه)",
              ids == {"a.json", "b.json", "d.json"}, str(ids))
        a = next(i for i in st if i["source"] == "a.json")
        b = next(i for i in st if i["source"] == "b.json")
        d = next(i for i in st if i["source"] == "d.json")
        check("تازه/کهنه از سن در برابر سقفِ همان ردیف", a["fresh"] and not b["fresh"])
        check("مالک روی آیتم می‌نشیند (برای دسته‌بند)", a["owner"] == "E03")
        check("خلاصه کوچک است، نه محتوای کامل",
              len(a["digest"]["long"]) <= DIGEST_STR and a["digest"]["arr"] == "[3]")
        check("فایلِ خراب «خراب» ثبت می‌شود، نه حدس", d["ok"] is False and "unreadable" in d["err"])
        check("فایلِ غایب «غایب» ثبت می‌شود",
              collect_state(now, registry={"zz.json": {"kind": "live"}})[0]["err"] == "missing")
        check("فایلِ غایبِ اختیاری «شکست» نیست — تفکیک همان state_bus",
              collect_state(now, registry={"zz.json": {"kind": "live", "optional": True}})[0]["err"] == "absent-optional")
        _d2 = build(now, external=False,
                    registry={"zz.json": {"kind": "live", "optional": True},
                              "qq.json": {"kind": "live"}})
        check("شمارِ شکست فقط غایبِ اجباری را می‌شمرد",
              _d2["n_failed"] == 1 and _d2["failed"] == ["qq.json"] and _d2["absent_optional"] == ["zz.json"],
              str((_d2["n_failed"], _d2["failed"], _d2["absent_optional"])))

        # خوراک بیرونی با intel جعلی — یکی موفق، یکی خطا، یکی کند
        class FakeIntel:
            def fear_greed(self): return {"value": 33, "label": "ترس", "extra": "x"}
            def funding(self): raise RuntimeError("boom")
            def calendar(self): time.sleep(3); return []
            def news(self): return [{"title": "t" * 300, "source": "s", "at": 1}]
            def trending(self): return list(range(30))
            def unlocks(self): return {"status": "UNAVAILABLE", "why": "HTTPError", "events": []}
        ext = collect_external(timeout_s=1, intel=FakeIntel())
        by = {i["source"]: i for i in ext}
        check("خوراکی که خودش UNAVAILABLE می‌گوید ok:false می‌گیرد",
              by["unlocks"]["ok"] is False and "UNAVAILABLE" in by["unlocks"].get("err", ""))
        check("منبعِ موفق payloadِ بریده می‌گیرد", by["fear_greed"]["ok"] and by["fear_greed"]["payload"] == {"value": 33, "label": "ترس"})
        check("منبعِ خطادار ok:false با نامِ خطا — نه عددِ ساختگی",
              by["funding"]["ok"] is False and by["funding"]["err"] == "RuntimeError")
        check("منبعِ کند timeout می‌گیرد و بقیه را نمی‌خواباند",
              by["calendar"]["ok"] is False and "timeout" in by["calendar"]["err"])
        check("خبر به ۲۰ تیتر و ۱۲۰ نویسه بریده می‌شود",
              len(by["news"]["payload"][0]["t"]) == 120)
        check("ترند به ۱۰ بریده می‌شود", len(by["trending"]["payload"]) == 10)
        check("همهٔ منابعِ اعلام‌شده حضور دارند حتی وقتی شکست خورده‌اند",
              set(by) == {s for s, _, _ in EXTERNAL})

        doc = build(now, external=True, intel=FakeIntel(), registry=reg, timeout_s=1)
        # چهار شکست: d.json خراب + funding خطا + calendar کند (سقف ۱ ثانیه)
        # + unlocks که خودش UNAVAILABLE گفت
        check("شمارِ شکست و کهنه روی سرِ صندوق است",
              doc["n_failed"] == 4 and doc["stale"] == ["b.json"]
              and {"funding", "calendar", "d.json", "unlocks"} <= set(doc["failed"]),
              str((doc["n_failed"], doc["stale"], doc["failed"])))
        check("مرزِ صادقانه روی خروجی است (قانون ۱۲)", "قانون ۱۵" in doc["boundary"])

        # حالت شنی: چیزی نوشته نمی‌شود
        import brain as _b
        old = getattr(_b, "SANDBOX", False)
        _b.SANDBOX = True
        try:
            check("در حالت شنی روی دیسکِ تولید نمی‌نویسد", write(doc) is False)
        finally:
            _b.SANDBOX = old
    finally:
        SIGNALS = old_sig
    print(f"\nintake: {ok} بررسی سبز" + (f" · {len(fail)} قرمز: {fail}" if fail else ""))
    return 1 if fail else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--no-external", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    t0 = time.time()
    doc = build(external=not a.no_external)
    print(f"intake: {doc['n_items']} آیتم ({doc['n_state']} وضعیت + {doc['n_external']} بیرونی) · "
          f"{doc['n_ok']} سالم · {doc['n_failed']} شکست · کهنه: {len(doc['stale'])} · "
          f"{time.time() - t0:.1f}s")
    if doc["failed"]:
        print("  شکست:", ", ".join(doc["failed"]))
    if a.write:
        write(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
