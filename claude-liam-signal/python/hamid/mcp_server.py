"""سرور MCP لیام تریدر ۹ — ابزارها به‌جای خواندن فایل (دستور حمید، ۱۴ سپتامبر: «ام‌سی‌پی رو هم انجام بده»).

هر ایجنت/کلاینتی که MCP بلد است (Claude Code، داشبورد، سرویس محلی) به‌جای
باز کردن فایل‌های `signals/` و حدس‌زدن شکلشان، همین ابزارها را صدا می‌زند.
ابزارها همان ماژول‌های قطعیِ قانون ۱۷/۱۸ را می‌پیچند؛ هیچ منطق تازه‌ای
این‌جا نیست و هیچ مدل زبانی صدا زده نمی‌شود (قانون ۰۶).

بی‌وابستگی: MCP روی stdio فقط JSON-RPC 2.0 است، هر پیام یک خط. این فایل
همان را با کتابخانهٔ استاندارد پیاده می‌کند تا روی رانر Actions، لپ‌تاپ
حمید و این‌جا با یک `python3` خالی بالا بیاید — «محیط یگانه» (قانون ۱۴).
اگر روزی بستهٔ رسمی `mcp` لازم شد، جدول TOOLS همین‌جا مصرف‌شدنی است.

مرزها (قانون ۰۵/۱۸):
  • ابزارهای بی‌پیشوند فقط می‌خوانند. هیچ ابزاری چیزی را در signals/brain
    بازنویسی نمی‌کند جز سه ابزار `run_*` که همان تولیدکنندهٔ رسمیِ فایلِ
    خودشان را صدا می‌زنند (یک نویسنده برای هر دامنه).
  • کیل‌سوییچ فقط «وضعیت» دارد؛ trip/reset از این‌جا ممکن نیست — ریست
    فقط با تأیید حمید (استثنای دائمی قانون ۱۸ بند ۳).
  • هیچ ابزاری دروازه/امتیاز/اهرم را عوض نمی‌کند و LIVE_EXECUTION را
    نمی‌بیند.
  • خروجی هر ابزار سقفِ متن دارد (MAX_TEXT) — «هیچ‌وقت توکن کم نیاوریم».

اجرای دستی بدون کلاینت MCP:
  python3 -m hamid.mcp_server --list
  python3 -m hamid.mcp_server --call bucket '{"key": "E03"}'
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
SIGNALS = ROOT / "signals"
REGISTRY = ROOT / "config" / "state_registry.json"

PROTOCOL = "2025-06-18"
SERVER = {"name": "liam9", "version": "1.0.0"}
MAX_TEXT = 12000            # سقف متنِ هر پاسخ — بودجهٔ توکن محدودیتِ سختِ طراحی است (قانون ۱۸)
INSTRUCTIONS = ("ابزارهای لیام تریدر ۹. اول review_queue یا bucket را بزن؛ فایل خام "
                "فقط از read_next (signal_file). هیچ ابزاری دروازه یا عددی را عوض نمی‌کند.")


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return None


def _registry_names():
    r = _load(REGISTRY) or {}
    return set((r.get("files") or {}).keys())


# ── ابزارها ────────────────────────────────────────────────────────────
def t_bucket(key: str):
    from hamid import dispatch as DP
    doc = _load(DP.OUT) or {}
    b = (doc.get("engines") or {}).get(key) or (doc.get("agents") or {}).get(key)
    return {"text": DP.render_bucket(doc, key), "bucket": b,
            "buckets_at": doc.get("generated"), "found": bool(b)}


def t_review_queue():
    from hamid import review_queue as RQ
    q = RQ.build(prev=_load(RQ.OUT))
    return {"text": RQ.render(q), "todo": q["todo"], "idle": q["idle"],
            "events": q["events"],
            "rows": [r for r in q["rows"] if r["needs_reasoning"]]}


def t_state_packet():
    from hamid import state_bus as SB, evidence_packet as EP
    st = SB.scan()
    pk = SB.packet(st)
    return {"text": EP.render(pk), "verdict": st["verdict"], "n_files": st["n_files"],
            "n_faults": st["n_faults"], "faults": st["faults"][:20], "packet": pk}


def t_geometry_verdict():
    from hamid import geometry_verdict as GV
    v = _load(SIGNALS / "geometry-verdict.json")
    if not v:
        return {"text": "داور هندسه: فایلی نیست", "status": "NO_DATA"}
    rows = {k: {kk: r.get(kk) for kk in ("n", "strict", "ci", "verdict", "why")}
            for k, r in (v.get("rows") or {}).items()}
    return {"text": GV.render(v), "status": v.get("status"), "backtest_at": v.get("backtest_at"),
            "bars": v.get("bars"), "n_cells": v.get("n_cells"),
            "alpha_per_test": v.get("alpha_per_test"), "rows": rows,
            "rule": v.get("rule"), "boundary": v.get("boundary")}


def t_guardian_delta(hours: int = 24):
    from hamid import guardian_delta as GD
    d = GD.build(hours=int(hours))
    return {"text": GD.render(d), "delta": {k: d[k] for k in d if not k.startswith("_")}}


def t_live_results():
    d = _load(SIGNALS / "live-results.json")
    if not d:
        return {"text": "نتایج لایو: فایلی نیست — فایل صادرشدهٔ بیت‌یونیکس در brain/holding/inbox/ بگذار", "found": False}
    return {"text": d.get("summary") or d.get("text") or json.dumps({k: d[k] for k in d if k != "rows"}, ensure_ascii=False)[:2000],
            "found": True, "doc": d}


def t_holding_status():
    d = _load(SIGNALS / "holding.json")
    if not d:
        return {"text": "صندوق هولدینگ: فایلی نیست", "found": False}
    return {"text": d.get("summary") or json.dumps({k: d[k] for k in d if k not in ("items", "rows")}, ensure_ascii=False)[:2000],
            "found": True, "doc": d}


def t_handoff():
    from hamid import handoff as H
    p = H.OUT
    txt = p.read_text(encoding="utf-8") if p.exists() else H.build()
    return {"text": txt, "path": str(p.relative_to(ROOT)), "from_file": p.exists()}


def t_killswitch_status():
    from hamid import killswitch as KS
    s = KS._load()
    return {"text": ("🛑 کیل‌سوییچ فعال: " + str(s["tripped"])) if s.get("tripped")
            else "کیل‌سوییچ آرام (tripped=None) — ریست/فعال‌سازی از این ابزار ممکن نیست",
            "state": s, "config": KS._cfg(),
            "boundary": "trip/reset از MCP ممکن نیست؛ ریست فقط دستی با تأیید حمید"}


def t_signal_file(name: str):
    """خواندنِ یک فایل وضعیت — فقط نام‌های ثبت‌شده در قرارداد (قانون ۱۳)، نه هر مسیری."""
    name = str(name).strip()
    if name.startswith("signals/"):
        name = name[len("signals/"):]
    if "/" in name or ".." in name or not name.endswith(".json"):
        return {"text": f"نام نامعتبر: {name!r} — فقط <name>.json داخل signals/", "ok": False}
    if name not in _registry_names():
        return {"text": f"«{name}» در قرارداد وضعیت ثبت نیست — فایلِ بی‌مالک خوانده نمی‌شود (قانون ۱۳)", "ok": False}
    p = SIGNALS / name
    if not p.exists():
        return {"text": f"{name}: روی این چک‌اوت نیست", "ok": False, "absent": True}
    d = _load(p)
    # سن از مهرِ خودِ داده (`generated`)، نه mtime چک‌اوت — چک‌اوت می‌تواند
    # ساعت‌ها عقب یا تازه‌کلون باشد (درس ۱۴ سپتامبر: scalp.json با mtime
    # ۱۴ دقیقه، ولی generated ۷۸۸ دقیقه).
    gen = (d or {}).get("generated") if isinstance(d, dict) else None
    if isinstance(gen, (int, float)) and gen > 1e11:
        age, src = (time.time() * 1000 - gen) / 60000, "generated"
    else:
        age, src = (time.time() - p.stat().st_mtime) / 60, "mtime"
    return {"text": f"{name} — سن {age:.0f}د ({src})", "ok": True, "age_min": round(age, 1),
            "age_source": src, "doc": d}


def t_tg_audit(days: int = 7):
    from hamid import tg_audit as TA
    a = TA.build(days=int(days))
    return {"text": TA.render(a), "census": a["census"], "signals": a["signals"], "outcomes": a["outcomes"]}


def t_run_intake(external: bool = True):
    from hamid import intake as IN
    doc = IN.build(external=bool(external))
    wrote = IN.write(doc)
    return {"text": f"اسکن‌بردار: {doc.get('n_items')} آیتم · {doc.get('n_failed', '?')} شکست · نوشته‌شد={wrote}",
            "n_items": doc.get("n_items"), "wrote": wrote}


def t_run_dispatch():
    from hamid import dispatch as DP
    intake = _load(DP.INTAKE)
    if not intake:
        return {"text": "صندوقِ ورودی نیست — اول run_intake", "wrote": False}
    doc = DP.build(intake, prev=_load(DP.OUT))
    wrote = DP.write(doc)
    return {"text": f"دسته‌بند: {doc['n_items']} آیتم → {len(doc['engines'])} سطل · {doc['n_changed']} تغییر · نوشته‌شد={wrote}",
            "n_changed": doc["n_changed"], "wrote": wrote}


def t_run_review_queue():
    from hamid import review_queue as RQ
    q = RQ.build(prev=_load(RQ.OUT))
    wrote = RQ.write(q)
    return {"text": RQ.render(q) + f"\nنوشته‌شد={wrote}", "todo": q["todo"], "wrote": wrote}


def _schema(props=None, required=None):
    return {"type": "object", "properties": props or {}, "required": required or [],
            "additionalProperties": False}


TOOLS = {
    "review_queue": dict(fn=t_review_queue, schema=_schema(), readonly=True,
                         desc="صف بازبینی «تولز اول، بعد ایجنت»: کدام ایجنت روی کدام تغییر/کهنگی/شکست باید فکر کند؛ بقیه بی‌کارند و صدا زده نمی‌شوند. اول این را بزن."),
    "bucket": dict(fn=t_bucket, schema=_schema({"key": {"type": "string", "description": "کد انجین (E03) یا نام ایجنت (macro-dominance)"}}, ["key"]), readonly=True,
                   desc="سطل یک انجین/ایجنت (قانون ۱۷): خلاصه + read_next. اگر read_next خالی بود چیزی عوض نشده — فایلی باز نکن."),
    "signal_file": dict(fn=t_signal_file, schema=_schema({"name": {"type": "string", "description": "نام فایل داخل signals/ (مثل dominance.json) — فقط نام‌های ثبت‌شده در قرارداد"}}, ["name"]), readonly=True,
                        desc="خواندن یک فایل وضعیتِ ثبت‌شده در قرارداد، با سنش. فقط برای فایل‌هایی که در read_next آمده‌اند."),
    "state_packet": dict(fn=t_state_packet, schema=_schema(), readonly=True,
                         desc="گذرگاه وضعیت (قانون ۱۳): حکم HEALTHY/DEGRADED/SICK + بستهٔ شواهد. قبل از هر ادعای وضعیت سامانه."),
    "geometry_verdict": dict(fn=t_geometry_verdict, schema=_schema(), readonly=True,
                             desc="آخرین حکم داور بک‌تست (سنجهٔ سختگیرانه، بوت‌استرپ خوشه‌ای، شیداک) برای هر بازو × جهت. ترفیع = پیشنهاد، نه اجرا."),
    "guardian_delta": dict(fn=t_guardian_delta, schema=_schema({"hours": {"type": "integer", "minimum": 1, "maximum": 720, "default": 24}}), readonly=True,
                           desc="دلتای ۱۲ مراقب ققنوس: رأی‌ها و دفتر پیپرِ هر مراقب در پنجرهٔ اخیر در برابر دورهٔ قبل، با n."),
    "live_results": dict(fn=t_live_results, schema=_schema(), readonly=True,
                         desc="نتایج معاملات لایو بیت‌یونیکس (از فایل صادرشده در brain/holding/inbox) با تطبیق دقیق به سیگنال ارسالی."),
    "holding_status": dict(fn=t_holding_status, schema=_schema(), readonly=True,
                           desc="وضعیت صندوق هولدینگ: نشست‌ها/داده‌های واردشده، دسته‌بندی‌شده بی‌ریزنینگ (قانون ۱۸ بند ۱)."),
    "handoff": dict(fn=t_handoff, schema=_schema(), readonly=True,
                    desc="نسخهٔ انتقال به چت تازه (HANDOFF.md): وضعیت زنده + حکم‌ها + رشته‌های باز."),
    "killswitch_status": dict(fn=t_killswitch_status, schema=_schema(), readonly=True,
                              desc="وضعیت کیل‌سوییچ چندماشه (فقط خواندن؛ trip/reset از این‌جا ممکن نیست)."),
    "tg_audit": dict(fn=t_tg_audit, schema=_schema({"days": {"type": "integer", "minimum": 1, "maximum": 60, "default": 7}}), readonly=True,
                     desc="ممیزی پیام‌های تلگرام در N روز: سرشماری هر نوع، پیام‌های بی‌مخاطب (قانون ۱۱)، و نتیجهٔ سیگنال‌های ارسالی با تطبیق دقیق به دفتر پیپر."),
    "run_intake": dict(fn=t_run_intake, schema=_schema({"external": {"type": "boolean", "default": True, "description": "خوراک‌های بیرونی هم گرفته شود؟"}}), readonly=False,
                       desc="اجرای دستی اسکن‌بردار (همان تولیدکنندهٔ رسمی signals/intake.json). روی زنجیره/سرویس محلی خودش هر ۵ دقیقه می‌چرخد."),
    "run_dispatch": dict(fn=t_run_dispatch, schema=_schema(), readonly=False,
                         desc="اجرای دستی دسته‌بند (signals/buckets.json) روی آخرین صندوق ورودی."),
    "run_review_queue": dict(fn=t_run_review_queue, schema=_schema(), readonly=False,
                             desc="ساخت و نوشتن صف بازبینی (signals/review-queue.json) از سطل‌های فعلی."),
}


def tool_list():
    return [{"name": n, "description": t["desc"], "inputSchema": t["schema"],
             "annotations": {"readOnlyHint": t["readonly"], "destructiveHint": False,
                             "idempotentHint": True, "openWorldHint": False}}
            for n, t in TOOLS.items()]


def _validate(schema, args):
    props = schema.get("properties") or {}
    for r in schema.get("required") or []:
        if r not in args:
            return f"آرگومان اجباری «{r}» نیست"
    for k, v in args.items():
        if k not in props:
            return f"آرگومان ناشناخته «{k}»"
        want = props[k].get("type")
        okt = {"string": str, "integer": int, "boolean": bool, "number": (int, float)}.get(want)
        if okt and (not isinstance(v, okt) or (want == "integer" and isinstance(v, bool))):
            return f"«{k}» باید {want} باشد"
    return None


def call_tool(name, args=None):
    """اجرای یک ابزار؛ خروجی همیشه {content, structuredContent, isError}."""
    args = dict(args or {})
    t = TOOLS.get(name)
    if not t:
        return {"content": [{"type": "text", "text": f"ابزار ناشناخته: {name}"}], "isError": True}
    err = _validate(t["schema"], args)
    if err:
        return {"content": [{"type": "text", "text": err}], "isError": True}
    try:
        out = t["fn"](**args)
    except Exception as e:                           # noqa: BLE001
        return {"content": [{"type": "text", "text": f"{name}: خطا — {type(e).__name__}: {e}"}], "isError": True}
    text = str(out.pop("text", "") or "")
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + f"\n…[بریده شد: {len(text)} نویسه؛ سقف {MAX_TEXT} — بودجهٔ توکن]"
    return {"content": [{"type": "text", "text": text}], "structuredContent": out, "isError": False}


# ── JSON-RPC ───────────────────────────────────────────────────────────
def _ok(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_, code, msg):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}


def handle(msg):
    """یک پیام JSON-RPC → پاسخ (یا None برای notification)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _err(None, -32600, "درخواست نامعتبر")
    method, id_, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if method is None:
        return _err(id_, -32600, "method نیست")
    if method.startswith("notifications/"):
        return None
    if method == "initialize":
        return _ok(id_, {"protocolVersion": PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                         "serverInfo": SERVER, "instructions": INSTRUCTIONS})
    if method == "ping":
        return _ok(id_, {})
    if method == "tools/list":
        return _ok(id_, {"tools": tool_list()})
    if method == "tools/call":
        name = params.get("name")
        if not name:
            return _err(id_, -32602, "name نیست")
        return _ok(id_, call_tool(name, params.get("arguments") or {}))
    return _err(id_, -32601, f"متد ناشناخته: {method}")


def serve(stdin=None, stdout=None):
    """حلقهٔ stdio: هر خط یک پیام. خطای پارس، پاسخِ -32700 می‌گیرد و حلقه نمی‌میرد."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:                            # noqa: BLE001
            resp = _err(None, -32700, "JSON خراب")
        else:
            resp = handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            stdout.flush()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="فهرست ابزارها")
    ap.add_argument("--call", nargs="+", metavar=("NAME", "JSON"), help="اجرای مستقیم یک ابزار")
    ap.add_argument("--serve", action="store_true", help="حلقهٔ MCP روی stdio (پیش‌فرض)")
    a = ap.parse_args(argv)
    if a.list:
        for t in tool_list():
            print(f"{t['name']:<18} {'[خواندنی]' if t['annotations']['readOnlyHint'] else '[نویسنده]'} {t['description']}")
        return 0
    if a.call:
        args = json.loads(a.call[1]) if len(a.call) > 1 else {}
        r = call_tool(a.call[0], args)
        try:
            print(r["content"][0]["text"])
            if r.get("structuredContent"):
                print(json.dumps(r["structuredContent"], ensure_ascii=False, indent=1)[:MAX_TEXT])
        except BrokenPipeError:                      # `| head` — خروجی بریده شد، خطا نیست
            pass
        return 1 if r["isError"] else 0
    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
