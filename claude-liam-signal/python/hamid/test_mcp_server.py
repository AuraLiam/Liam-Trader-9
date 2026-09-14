"""محافظ سرور MCP (دستور حمید ۱۴ سپتامبر) — خاصیت، نه شکل.

چه چیزی را قفل می‌کند:
  ۱. پروتکل: initialize/tools/list/tools/call/ping درست جواب می‌دهند؛ JSON
     خراب حلقه را نمی‌کشد؛ notification پاسخ ندارد.
  ۲. مرز نوشتن: ابزارهای خواندنی هیچ فایلی را در signals/ و brain/ لمس
     نمی‌کنند (مهرِ زمان قبل/بعد)، و در sandbox حتی run_* هم نمی‌نویسند.
  ۳. مرز قدرت: هیچ ابزاری trip/reset کیل‌سوییچ، LIVE_EXECUTION، اهرم یا
     دروازه را نمی‌بیند (قانون ۱۸ بند ۳).
  ۴. signal_file فقط نام‌های ثبت‌شدهٔ قرارداد را می‌خواند؛ مسیرِ بیرون‌رو رد
     می‌شود (قانون ۱۳).
  ۵. سقف متن: پاسخ بلند بریده می‌شود (بودجهٔ توکن).
  ۶. اتصال: .mcp.json ریشه به اسکریپتِ اجرایی اشاره می‌کند و آن اسکریپت
     همین ماژول را بالا می‌آورد؛ صف بازبینی ردیف قرارداد و کار سرویس محلی
     و مرحلهٔ زنجیره دارد.
"""
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ["LIAM9_SANDBOX"] = "1"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import mcp_server as M, review_queue as RQ   # noqa: E402

ROOT = M.ROOT
ok, fail = 0, []


def check(name, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail.append(name)
        print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


def _mtimes():
    out = {}
    for d in (ROOT / "signals", ROOT / "brain"):
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file():
                    try:
                        out[str(p)] = p.stat().st_mtime_ns
                    except OSError:
                        pass
    return out


print("── ۱. پروتکل ─────────────────────────────")
r = M.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}})
check("initialize: نسخهٔ پروتکل + قابلیت tools + serverInfo",
      r["result"]["protocolVersion"] == M.PROTOCOL and "tools" in r["result"]["capabilities"]
      and r["result"]["serverInfo"]["name"] == "liam9", str(r)[:200])
check("notification پاسخ ندارد", M.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None)
check("ping خالی برمی‌گردد", M.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {})
tl = M.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]["tools"]
names = {t["name"] for t in tl}
check("tools/list دقیقاً همان جدول TOOLS است", names == set(M.TOOLS), str(names ^ set(M.TOOLS)))
check("هر ابزار اسکیمای بستهٔ ورودی + توضیح فارسی + annotations دارد",
      all(t["inputSchema"].get("additionalProperties") is False and len(t["description"]) > 20
          and "readOnlyHint" in t["annotations"] for t in tl))
check("متد ناشناخته → -32601", M.handle({"jsonrpc": "2.0", "id": 4, "method": "x/y"})["error"]["code"] == -32601)
check("پیام غیر JSON-RPC → -32600", M.handle({"id": 5})["error"]["code"] == -32600)
bad = M.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "nope"}})["result"]
check("ابزار ناشناخته isError=True (نه استثنا)", bad["isError"])
bad2 = M.call_tool("bucket", {})
check("آرگومان اجباریِ غایب رد می‌شود", bad2["isError"] and "key" in bad2["content"][0]["text"])
bad3 = M.call_tool("guardian_delta", {"hours": "24"})
check("نوعِ غلط رد می‌شود (hours رشته)", bad3["isError"])
bad4 = M.call_tool("bucket", {"key": "E03", "extra": 1})
check("آرگومان ناشناخته رد می‌شود", bad4["isError"])

print("── ۲. مرز نوشتن ───────────────────────────")
before = _mtimes()
results = {}
for n, t in M.TOOLS.items():
    args = {"key": "E03"} if n == "bucket" else {"name": "dominance.json"} if n == "signal_file" else {}
    results[n] = M.call_tool(n, args)
after = _mtimes()
touched = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
check("همهٔ ابزارها بی‌استثنا اجرا شدند (isError=False)",
      all(not r["isError"] for r in results.values()),
      str({n: r["content"][0]["text"][:80] for n, r in results.items() if r["isError"]}))
check("هیچ فایلی در signals/ و brain/ لمس نشد — حتی run_* در sandbox", not touched, str(touched[:5]))
check("run_* در sandbox صریح wrote=False می‌گویند",
      all(results[n]["structuredContent"].get("wrote") is False for n in ("run_intake", "run_dispatch", "run_review_queue")),
      str({n: results[n]["structuredContent"] for n in ("run_intake", "run_dispatch", "run_review_queue")}))
check("ابزار خواندنی/نویسنده در annotations با جدول می‌خواند",
      all(next(t for t in tl if t["name"] == n)["annotations"]["readOnlyHint"] == (not n.startswith("run_")) for n in M.TOOLS))

print("── ۳. مرز قدرت ────────────────────────────")
srcs = {n: inspect.getsource(t["fn"]) for n, t in M.TOOLS.items()}
import re as _re
forbidden = (r"\btrip\(", r"\breset\(", r"LIVE_EXECUTION", r"leverage", r"send_signals", r"sendMessage", r"subprocess")
hits = [(n, f) for n, s in srcs.items() for f in forbidden if _re.search(f, s)]
check("هیچ ابزاری trip/reset/LIVE_EXECUTION/اهرم/ارسال/زیرپردازه ندارد", not hits, str(hits))
ks = results["killswitch_status"]["structuredContent"]
check("کیل‌سوییچ فقط وضعیت + مرزِ صریح برمی‌گرداند", "state" in ks and "ریست" in ks["boundary"])

print("── ۴. signal_file فقط قرارداد ─────────────")
check("مسیر بیرون‌رو رد", M.call_tool("signal_file", {"name": "../config/risk.json"})["structuredContent"]["ok"] is False)
check("زیرمسیر رد", M.call_tool("signal_file", {"name": "archive/x.json"})["structuredContent"]["ok"] is False)
check("نام ثبت‌نشده رد با ارجاع به قانون ۱۳",
      "قانون ۱۳" in M.call_tool("signal_file", {"name": "definitely-not-registered.json"})["content"][0]["text"])
sf = M.call_tool("signal_file", {"name": "signals/dominance.json"})["structuredContent"]
check("پیشوند signals/ پذیرفته و سن گزارش می‌شود", sf.get("ok") is True and "age_min" in sf, str(sf)[:120])

print("── ۵. سقف متن ─────────────────────────────")
M.TOOLS["_long"] = dict(fn=lambda: {"text": "x" * (M.MAX_TEXT * 3)}, schema=M._schema(), readonly=True, desc="t")
lr = M.call_tool("_long")
del M.TOOLS["_long"]
check("پاسخ بلند بریده می‌شود و می‌گوید چقدر بود",
      len(lr["content"][0]["text"]) < M.MAX_TEXT + 200 and "بریده" in lr["content"][0]["text"])
check("سقف متن زیر ~۴k توکن است (۱۲k نویسه)", M.MAX_TEXT <= 12000)

print("── ۶. اتصال ───────────────────────────────")
cfg = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
srv = cfg["mcpServers"]["liam9"]
script = ROOT / srv["args"][-1] if srv["command"] in ("bash", "sh") else None
check(".mcp.json ریشه سرور liam9 را با اسکریپت bash ثبت کرده", script is not None and script.exists(), str(srv))
check("اسکریپت اجرایی است و همین ماژول را با python3 بالا می‌آورد",
      script and os.access(script, os.X_OK) and "hamid.mcp_server" in script.read_text(encoding="utf-8"))
# stdio واقعی: initialize → tools/list → ping
env = dict(os.environ, LIAM9_SANDBOX="1")
msgs = "\n".join(json.dumps(m) for m in [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    "not json",
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "bucket", "arguments": {"key": "E00"}}},
    {"jsonrpc": "2.0", "id": 4, "method": "ping"}]).replace('"not json"', "not json") + "\n"
t0 = time.time()
p = subprocess.run(["bash", str(script)], input=msgs, capture_output=True, text=True, timeout=120, env=env, cwd=str(ROOT))
lines = [json.loads(x) for x in p.stdout.splitlines() if x.strip()]
ids = [x.get("id") for x in lines]
check("stdio: چهار پاسخ برای چهار درخواست + یک خطای پارس، notification بی‌پاسخ",
      sorted(i for i in ids if i is not None) == [1, 2, 3, 4] and any(x.get("error", {}).get("code") == -32700 for x in lines),
      f"stdout={p.stdout[:300]!r} stderr={p.stderr[-300:]!r}")
check("stdio: JSON خراب حلقه را نکشت (ping بعدش جواب گرفت)", 4 in ids)
check("stdio: فهرست ابزارها از راه واقعی همان جدول است",
      any(x.get("id") == 2 and {t["name"] for t in x["result"]["tools"]} == set(M.TOOLS) for x in lines))
check("stdio: کل رفت‌وبرگشت زیر ۶۰ ثانیه", time.time() - t0 < 60, f"{time.time()-t0:.1f}s")

reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("review-queue.json ردیف قرارداد دارد (قانون ۱۳)", "review-queue.json" in reg and reg["review-queue.json"].get("owner"))
from hamid import liam9d as D
check("سرویس محلی review_queue را می‌چرخاند", any(j["key"] == "review_queue" for j in D.JOBS))
wf = (ROOT / ".github" / "workflows" / "pump-radar.yml").read_text(encoding="utf-8")
check("زنجیره بعد از dispatch صف بازبینی را می‌نویسد",
      "hamid.review_queue --write" in wf and wf.index("hamid.dispatch --write") < wf.index("hamid.review_queue --write"))
check("و همین محافظ در دروازهٔ زنجیره است", "hamid.test_mcp_server" in wf)
q = RQ.build(prev=M._load(RQ.OUT))   # همان prev که ابزار می‌بیند
check("صف بازبینی و ابزار review_queue یک جواب می‌دهند",
      set(results["review_queue"]["structuredContent"]["todo"]) == set(q["todo"]))

print(f"\n{ok} بررسیِ سرور MCP گذشت" + (f" — {len(fail)} افتاد: {fail}" if fail else " — همه سبز"))
sys.exit(1 if fail else 0)
