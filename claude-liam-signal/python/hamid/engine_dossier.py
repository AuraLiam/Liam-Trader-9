"""پروندهٔ کامل هر انجین — آنچه حمید برای بررسیِ تک‌تکشان لازم دارد.

دستور حمید (۳۱ اوت): «قرار شد اطلاعات همهٔ انجین‌ها را بهم بدی که من
بررسی کنم همه را… کدام انجین چه‌جوری اطلاعاتش را پایش می‌کند و در اختیار
چه انجین‌هایی می‌گذارد؟»

`engine_map.py` ساختار را می‌داد (پایش، منبع، فایل). این فایل چیزی را
اضافه می‌کند که برای **بررسی‌کردن** لازم است و آن‌جا نبود:

| بخش | از کجا | چرا لازم است |
|---|---|---|
| گراف واقعی مصرف | grep نامِ فایل در سورس همهٔ ماژول‌ها | فیلد `consumer` قرارداد درشت است («پنل»، «موتور»)؛ این‌جا اسم خودِ انجین درمی‌آید |
| کادنس | کرون ورک‌فلوی تولیدکننده | «چه‌جوری پایش می‌کند» بدون هرچندوقت‌یک‌بار، جواب نیست |
| کد و محافظ | فایل‌های تولیدکننده + `test_*` مرتبط | انجین بی‌محافظ = ادعای بی‌پشتوانه (قانون ۱۷ اوت) |
| کارنامه | `rewards.json` · `agent-weights.json` · `engine-focus.json` | تنها چیزی که می‌گوید انجین **کار می‌کند** یا فقط **وجود دارد** |
| تحقیق و کتابخانه | `brain/research/Exx/findings.jsonl` · برنامهٔ درسی | قانون ۰۳: یادگیری باید ردپا داشته باشد |
| شکاف | محاسبه‌شده | بی‌ردپا / بی‌محافظ / بی‌کارنامه / بی‌تحقیق — صریح، نه پنهان |

## چرا مولد است، نه سند دستی

همان دلیل `engine_map`: سند دست‌نویس فردا دروغ می‌شود. این‌جا هر عدد از
خودِ ریپو خوانده می‌شود، پس با عوض‌شدن کد خودش عوض می‌شود.

## مرز صادقانه

«کارنامه» یعنی ردپای اندازه‌گیری‌شده، نه اثباتِ لبه. امتیاز جایزه
(`rewards`) انگیزشی/عیب‌یابانه است و **وتو و وزن ندارد** (دستور ۱۷ اوت).
هیچ عددی از این فایل دروازه‌ای را عوض نمی‌کند.

اجرا: `python3 -m hamid.engine_dossier [--json]`
"""
import collections
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parent.parent
REG = ROOT / "config" / "state_registry.json"
LIST = ROOT / "claude-liam-signal" / "ENGINE-LIST.json"
SIG = ROOT / "signals"
WF = ROOT / ".github" / "workflows"
AGENTS = ROOT / ".claude" / "agents"
SKILLS = ROOT / ".claude" / "skills"
RESEARCH = ROOT / "brain" / "research"

HOST_RE = re.compile(r"https?://([a-z0-9.\-]+)")
SKIP_HOST = ("github", "anthropic", "schema", "json-schema", "localhost")
CRON_RE = re.compile(r"cron:\s*['\"]([^'\"]+)['\"]")


def _read(p):
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:                                # noqa: BLE001
        return ""


def _resolve(mod):
    """مسیر واقعی یک تولیدکننده — نام ماژول می‌تواند نسبی به دو ریشه باشد."""
    for cand in (PY / mod, ROOT / mod):
        if cand.is_file():
            return cand
    return None


def _sources():
    """همهٔ فایل‌های پایتونِ غیرآزمونی — یک‌بار خوانده و کش می‌شوند."""
    out = {}
    for f in list(PY.glob("*.py")) + list((PY / "hamid").glob("*.py")):
        if f.name.startswith("test_"):
            continue
        rel = f"hamid/{f.name}" if f.parent.name == "hamid" else f.name
        out[rel] = _read(f)
    return out


def build(now_ms=None):
    now = now_ms or int(time.time() * 1000)
    reg = json.loads(_read(REG) or "{}")
    files = reg.get("files", reg)
    try:
        names = {e["id"]: e["name"] for e in json.loads(_read(LIST))}
    except Exception:                                # noqa: BLE001
        names = {}
    from hamid.engine_map import WATCHES

    src = _sources()
    # یک ماژول می‌تواند مالِ **چند** انجین باشد: `cycle.py` و `scan.py` هر
    # کدام برای چند انجین فایل می‌سازند. نسخهٔ اولِ همین نقشه `setdefault`
    # داشت، یعنی فقط اولین مالک را نگه می‌داشت — و گراف نامتقارن می‌شد:
    # E10 می‌گفت «از E17 تغذیه می‌شوم» ولی E17 نمی‌گفت «به E10 می‌دهم».
    # پاسبانِ تقارن همین را گرفت.
    mod2eng = collections.defaultdict(set)
    for fn, v in files.items():
        for m in re.split(r"[,\s]+", v.get("producer") or ""):
            if m and not m.startswith("external:") and v.get("owner"):
                mod2eng[m].add(v["owner"])

    # ── گراف مصرف: چه ماژولی نامِ این فایل را در سورسش دارد ──────────────
    # فقط تطبیقِ **عینِ نام فایل** داخل رشته. الگوی شل‌تر یال‌های جعلی
    # می‌سازد و نقشهٔ دروغ از نقشهٔ ناقص بدتر است.
    readers = collections.defaultdict(set)
    for rel, text in src.items():
        for fn in files:
            if re.search(r"[\"']" + re.escape(fn) + r"[\"']", text):
                readers[fn].add(rel)

    # ── کادنس: کرونِ ورک‌فلویی که این تولیدکننده را صدا می‌زند ───────────
    wf_cron, wf_calls = {}, collections.defaultdict(set)
    for w in sorted(WF.glob("*.yml")):
        t = _read(w)
        wf_cron[w.name] = CRON_RE.findall(t)
        for m in mod2eng:
            stem = Path(m).stem
            if re.search(r"\b" + re.escape(stem) + r"\b", t):
                wf_calls[m].add(w.name)

    # ── محافظ‌ها: آزمونی که نامِ ماژول را صدا می‌زند ─────────────────────
    guards = collections.defaultdict(set)
    for t in (PY / "hamid").glob("test_*.py"):
        text = _read(t)
        n_checks = text.count("check(")
        for m in mod2eng:
            stem = Path(m).stem
            if re.search(r"\b" + re.escape(stem) + r"\b", text):
                guards[m].add((f"hamid/{t.name}", n_checks))

    # ── کارنامه‌ها ──────────────────────────────────────────────────────
    rw = json.loads(_read(SIG / "rewards.json") or "{}")
    rewards = {r["engine"]: r for r in (rw.get("board") or [])}
    aw = json.loads(_read(SIG / "agent-weights.json") or "{}")
    rooms = collections.defaultdict(list)
    for key, v in (aw.get("rooms") or {}).items():
        if v.get("engine"):
            rooms[v["engine"]].append({"room": key, "label": v.get("label"),
                                       "rule": v.get("rule"),
                                       "n": ((v.get("by_context") or {})
                                             .get("all") or {}).get("n")})
    focus = json.loads(_read(SIG / "engine-focus.json") or "{}")
    # کارنامهٔ سنجیده (دستور ۳۱ اوت) — از خودِ ماژول، نه از فایلِ ممکن است
    # کهنه؛ پرونده و کارنامه باید همیشه یک چیز بگویند.
    try:
        from hamid.scorecard import build as _sc
        grades = {c["id"]: c for c in _sc(now)["cards"]}
    except Exception:                                # noqa: BLE001
        grades = {}

    by_owner = collections.defaultdict(list)
    for fn, v in files.items():
        by_owner[v.get("owner") or "?"].append((fn, v))

    engines = []
    for eid in sorted(set(list(by_owner) + list(WATCHES)) - {"?"}):
        rows = by_owner.get(eid, [])
        prods, hosts, layers, out_files, consumers = set(), set(), set(), [], set()
        code, cadence, tests = [], set(), set()
        for fn, v in rows:
            for m in re.split(r"[,\s]+", v.get("producer") or ""):
                if not m or m.startswith("external:"):
                    continue
                prods.add(m)
                p = _resolve(m)
                if p:
                    text = _read(p)
                    hosts |= {h for h in HOST_RE.findall(text)
                              if not any(s in h for s in SKIP_HOST)}
                    # کندل‌ها را کمتر ماژولی مستقیم صدا می‌زند؛ اکثراً از
                    # `sources.py` می‌گیرند. اگر این را نشمریم، انجینی که
                    # واقعاً از صرافی می‌خواند «بی‌منبع» چاپ می‌شود — یعنی
                    # نقشه دروغ می‌گوید. پس واسطه صریح علامت می‌خورد،
                    # نه اینکه میزبان‌های sources.py به پایش چسبانده شود.
                    if re.search(r"\bsources\.(klines|top_symbols|ticker)", text):
                        hosts.add("sources.py → صرافی‌ها (اسپات)")
                    if re.search(r"\bsources\.perp_klines", text):
                        hosts.add("sources.py → صرافی‌ها (پرپچوال)")
                    code.append({"file": m, "lines": text.count("\n") + 1})
                for w in wf_calls.get(m, ()):
                    for c in wf_cron.get(w) or ["(بدون کرون — دستی/وابسته)"]:
                        cadence.add(f"{w} · {c}")
                tests |= guards.get(m, set())
            if v.get("layer"):
                layers.add(v["layer"])
            # مصرف‌کنندهٔ واقعی: ماژولِ خواننده → انجینِ مالکش
            for rmod in readers.get(fn, ()):
                consumers |= {o for o in mod2eng.get(rmod, ()) if o != eid}
            f = SIG / fn
            age = None
            if f.exists():
                try:
                    g = json.loads(_read(f)).get("generated")
                    age = round((now - g) / 60000) if g else None
                except Exception:                    # noqa: BLE001
                    age = None
            cap = v.get("max_age_min")
            out_files.append({
                "file": fn, "kind": v.get("kind"), "max_age_min": cap,
                "age_min": age, "critical": bool(v.get("critical")),
                "stale": bool(cap and age is not None and age > cap),
                "readers": sorted(readers.get(fn, ())),
                "declared_consumer": v.get("consumer"),
            })

        # چه فایل‌هایی را **خودش** می‌خواند → از کدام انجین تغذیه می‌شود
        eats, upstream = set(), set()
        for m in prods:
            text = src.get(m, "")
            for fn, v in files.items():
                if v.get("owner") == eid:
                    continue
                if re.search(r"[\"']" + re.escape(fn) + r"[\"']", text):
                    eats.add(fn)
                    if v.get("owner"):
                        upstream.add(v["owner"])

        fnd = RESEARCH / eid / "findings.jsonl"
        n_find = len([x for x in _read(fnd).splitlines() if x.strip()])
        agent = next((f"agents/{p.name}" for p in AGENTS.glob("*.md")
                      if p.name.lower().startswith(eid.lower() + "-")), None)
        skl = sorted(f"skills/{p.name}" for p in SKILLS.glob("*")
                     if p.name.lower().startswith(f"liam-{eid.lower()}-"))
        rew = rewards.get(eid)
        engines.append({
            "id": eid, "name": names.get(eid, "—"),
            "watches": WATCHES.get(eid, "—"),
            "layers": sorted(layers),
            "agent": agent, "skills": skl,
            "code": sorted(code, key=lambda c: -c["lines"]),
            "cadence": sorted(cadence),
            "guards": sorted({t[0] for t in tests}),
            "guard_checks": sum(dict(tests).values()) if tests else 0,
            "sources_external": sorted(hosts),
            "eats_files": sorted(eats),
            "upstream": sorted(upstream),
            "downstream": sorted(consumers),
            "files": out_files,
            "rewards": rew,
            "grade": grades.get(eid),
            "rooms": rooms.get(eid, []),
            "focus": (focus.get("engines") or {}).get(eid),
            "research_findings": n_find,
            "traceless": not rows,
            "gaps": [g for g in (
                "بی‌ردپا (فایل وضعیت مستقل ندارد)" if not rows else None,
                "بی‌محافظ (آزمون اختصاصی ندارد)" if not tests and rows else None,
                # «بی‌کارنامه» حالا یعنی مترِ سنجیده ندارد — نه این‌که
                # امتیاز جایزه ندارد. جایزه فقط برای انجینِ روی-معامله
                # ساخته می‌شود و ۲۰ انجین ذاتاً از آن راه نمره نمی‌گیرند.
                "بی‌کارنامه (مترِ سنجیده ندارد)"
                if (grades.get(eid) or {}).get("verdict") == "NO_METRIC"
                or eid not in grades else None,
                "بی‌تحقیق (findings خالی)" if n_find == 0 else None,
                "فایل کهنه از سقف قرارداد"
                if any(f["stale"] for f in out_files) else None,
            ) if g],
        })
    return {"generated": now, "engines": engines,
            "n_files": len(files),
            "n_traceless": sum(1 for e in engines if e["traceless"])}


def main(argv=()):
    m = build()
    if "--json" in argv:
        print(json.dumps(m, ensure_ascii=False, indent=1))
        return 0
    print(f"### پروندهٔ انجین‌ها — {len(m['engines'])} انجین · "
          f"{m['n_files']} فایل وضعیت\n")
    for e in m["engines"]:
        print(f"{'⚪' if e['traceless'] else '🟢'} {e['id']} — {e['name']}"
              + (f"  [{'، '.join(e['layers'])}]" if e["layers"] else ""))
        print(f"    پایش: {e['watches']}")
        idn = [x for x in ([e["agent"]] + e["skills"]) if x]
        if idn:
            print(f"    ایجنت/مهارت: {'، '.join(idn)}")
        if e["cadence"]:
            print(f"    کادنس: {'، '.join(e['cadence'])}")
        print(f"    منبع بیرونی: {'، '.join(e['sources_external']) or '—'}")
        print(f"    تغذیه از: {'، '.join(e['upstream']) or '—'}"
              f"   →   می‌دهد به: {'، '.join(e['downstream']) or '—'}")
        if e["code"]:
            print("    کد: " + "، ".join(f"{c['file']} ({c['lines']} خط)"
                                         for c in e["code"][:4]))
        print(f"    محافظ: {len(e['guards'])} فایل / {e['guard_checks']} بررسی"
              f" · تحقیق: {e['research_findings']} یافته")
        if e["rewards"]:
            r = e["rewards"]
            print(f"    جایزه: {r['points']} امتیاز "
                  f"(تارگت {r['target']} · تریل {r['trail']} · استاپ {r['stop']})")
        for room in e["rooms"]:
            print(f"    اتاق «{room['label']}»: n={room['n']}")
        for f in e["files"]:
            age = f"{f['age_min']}د" if f["age_min"] is not None else "—"
            cap = f"/{f['max_age_min']}د" if f["max_age_min"] else ""
            print(f"      · {f['file']} ({f['kind']}) سن {age}{cap}"
                  + ("  ⚠️کهنه" if f["stale"] else "")
                  + ("  حیاتی" if f["critical"] else "")
                  + (f"  ← {len(f['readers'])} خواننده" if f["readers"] else ""))
        if e["gaps"]:
            print(f"    ⚠️ شکاف: {' · '.join(e['gaps'])}")
        print()
    print("### مرز صادقانه")
    print("  «کارنامه» یعنی ردپای اندازه‌گیری‌شده، نه اثباتِ لبه. امتیاز")
    print("  جایزه انگیزشی/عیب‌یابانه است و وتو و وزن ندارد (دستور ۱۷ اوت).")
    print("  هیچ عددی از این فایل دروازه‌ای را عوض نمی‌کند.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
