"""گرافیفایِ پنل — نقشهٔ دانشِ قطعیِ لیام تریدر ۹ (دستور حمید، ۲۹ سپتامبر).

حمید: «یه گرافیفای از پنل درست کن، نیاز نباشه توکن بسوزونی برای استفاده از
هر دستوری که میدم.» — یعنی هر پرسشِ «چه چیزی به چه چیزی وصل است؟» باید
بی مدل زبانی و بی گشتنِ پوشه جواب بگیرد (قانون ۱۷/۱۸: ابزار = انجام).

گراف از منبع حقیقت مشتق می‌شود، دست‌نویس نیست:
  · ورک‌فلوها (.github/workflows/*.yml) → کرون، ماژول‌هایی که اجرا می‌کنند،
    آزمون‌های دروازه، مسیرهایی که منتشر می‌کنند
  · قرارداد وضعیت (config/state_registry.json) → فایل → لایه/مالک/تولیدکننده/مصرف‌کننده
  · پنل (index.html) → کدام فایل‌های signals/ را می‌خواند و زیر کدام کارت
  · ایجنت‌ها (.claude/agents/*.md) → مهارت‌ها؛ مهارت‌ها → انجین (Exx)
  · ثبت انجین‌ها (config/engine_registry.yaml)
  · ماژول‌های پایتون (hamid/*.py) → وابستگیِ import درون‌پروژه + آزمونِ هم‌نام
  · قوانین (.claude/rules/*.md) → ماژول‌هایی که نام می‌برند

خروجی‌ها (همه در docs/graph/):
  graph.json   گره‌ها و یال‌ها (برای ابزار و برای صفحهٔ HTML)
  index.html   نمای تعاملی، بی‌وابستگیِ بیرونی (بدون CDN)، روشن/تاریک
  INDEX.md     فهرستِ فشردهٔ متنی: هر انجین/ورک‌فلو/فایل → همسایه‌هایش

پرسش بی‌توکن:
    python3 -m hamid.graphify --build              # ساخت هر سه خروجی
    python3 -m hamid.graphify --who signals/latest.json   # چه کسی می‌سازد/می‌خواند
    python3 -m hamid.graphify --who hamid/paper.py        # چه ورک‌فلو/آزمون/قانونی به آن وصل است
    python3 -m hamid.graphify --who E23                    # انجین: فایل‌ها، ماژول‌ها، ایجنت‌ها
    python3 -m hamid.graphify --selftest
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))
OUT_DIR = ROOT / "docs" / "graph"
WF_DIR = ROOT / ".github" / "workflows"

KINDS = {"engine": "انجین", "workflow": "ورک‌فلو", "module": "ماژول", "test": "آزمون",
         "state": "فایل وضعیت", "card": "کارت پنل", "agent": "ایجنت", "skill": "مهارت",
         "rule": "قانون"}
EDGES = {"runs": "اجرا می‌کند", "gates": "دروازه", "produces": "می‌سازد", "consumes": "می‌خواند",
         "owns": "مالک", "shows": "نمایش", "imports": "import", "tests": "آزمون", "has_skill": "مهارت",
         "for_engine": "برای انجین", "mentions": "نام می‌برد", "publishes": "منتشر می‌کند"}


class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: set[tuple] = set()

    def node(self, nid: str, kind: str, label: str | None = None, **attrs):
        n = self.nodes.setdefault(nid, {"id": nid, "kind": kind, "label": label or nid})
        n.update({k: v for k, v in attrs.items() if v not in (None, "", [])})
        return n

    def edge(self, a: str, rel: str, b: str):
        if a in self.nodes and b in self.nodes and a != b:
            self.edges.add((a, rel, b))


# ── استخراج ─────────────────────────────────────────────────────────────
_MOD_RE = re.compile(r"python3?\s+-m\s+(hamid\.[a-zA-Z0-9_]+|research\.[a-zA-Z0-9_]+)|python3?\s+(?:[\w./$\"{}-]*/)?([a-zA-Z0-9_]+\.py)")


def _workflows(g: Graph):
    import yaml
    for wf in sorted(WF_DIR.glob("*.yml")):
        t = wf.read_text(encoding="utf-8")
        try:
            doc = yaml.safe_load(t) or {}
        except yaml.YAMLError:
            doc = {}
        name = str(doc.get("name") or wf.stem)
        on = doc.get("on") or doc.get(True) or {}
        crons = []
        if isinstance(on, dict) and isinstance(on.get("schedule"), list):
            crons = [str(x.get("cron")) for x in on["schedule"] if isinstance(x, dict)]
        wid = f"wf:{wf.name}"
        g.node(wid, "workflow", name, file=f".github/workflows/{wf.name}", cron=crons,
               dispatch=bool(isinstance(on, dict) and "workflow_dispatch" in on))
        body = "\n".join(str(s.get("run") or "") for j in (doc.get("jobs") or {}).values()
                         if isinstance(j, dict) for s in (j.get("steps") or []) if isinstance(s, dict))
        for m in _MOD_RE.finditer(body):
            mod = m.group(1) or m.group(2)
            mid = _mod_id(mod)
            if mid:
                is_test = "test_" in mid or "--selftest" in body[m.end():m.end() + 14]
                g.node(mid, "test" if mid.split(":")[1].split(".")[-1].startswith("test_") else "module",
                       mid.split(":")[1])
                g.edge(wid, "gates" if is_test else "runs", mid)
        for m in re.finditer(r"publish\.sh\s+-m\s+\"[^\"]*\"\s+([^\n]+)", body):
            for p in m.group(1).replace("\\", " ").split():
                if p.startswith(("signals/", "brain/")):
                    g.node(f"path:{p}", "state", p)
                    g.edge(wid, "publishes", f"path:{p}")


def _mod_id(mod: str) -> str | None:
    mod = mod.strip()
    if mod.endswith(".py"):
        mod = mod[:-3]
        # فقط اسکریپت‌های ریشهٔ پوشهٔ پایتون (منبع حقیقت: وجودِ فایل، نه فهرست)
        return f"mod:{mod}" if (PY / f"{mod}.py").exists() else None
    return f"mod:{mod}"


def _registry(g: Graph):
    reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))
    for fname, r in (reg.get("files") or {}).items():
        sid = f"state:signals/{fname}"
        g.node(sid, "state", f"signals/{fname}", layer=r.get("layer"), kind_=r.get("kind"),
               cap=r.get("max_age_min"), critical=r.get("critical"))
        owner = r.get("owner")
        if owner:
            g.node(f"eng:{owner}", "engine", owner)
            g.edge(f"eng:{owner}", "owns", sid)
        prod = (r.get("producer") or "").split(" ")[0]
        if prod.endswith(".py"):
            mid = f"mod:{prod[:-3].replace('/', '.')}" if "/" in prod else _mod_id(prod)
            if mid:
                g.node(mid, "module", mid.split(":")[1])
                g.edge(mid, "produces", sid)
        for wf in re.findall(r"([a-z0-9-]+\.yml)", r.get("producer") or ""):
            if (WF_DIR / wf).exists():
                g.node(f"wf:{wf}", "workflow", wf)
                g.edge(f"wf:{wf}", "produces", sid)
        for c in re.split(r"[+,/ ]+", r.get("consumer") or ""):
            c = c.strip()
            if re.fullmatch(r"E\d\d", c):
                g.node(f"eng:{c}", "engine", c)
                g.edge(f"eng:{c}", "consumes", sid)
            elif c == "panel":
                g.node("card:پنل", "card", "پنل (کل)")
                g.edge("card:پنل", "consumes", sid)


def _panel(g: Graph):
    html = (ROOT / "index.html").read_text(encoding="utf-8", errors="ignore")
    heads = [(m.start(), re.sub(r"<[^>]+>|\$\{[^}]*\}", "", m.group(1)).strip())
             for m in re.finditer(r"<h[23][^>]*>(.*?)</h[23]>", html)]
    for m in re.finditer(r"signals/([a-z0-9_./-]+\.json)", html):
        f = "signals/" + m.group(1)
        sid = f"state:{f}"
        g.node(sid, "state", f)
        # نزدیک‌ترین عنوانِ پیش از این ارجاع = کارتِ میزبان (تقریب متنی، نه DOM)
        title = next((h for pos, h in reversed(heads) if pos < m.start() and h), None)
        cid = f"card:{title}" if title else "card:پنل"
        g.node(cid, "card", title or "پنل (کل)")
        g.edge(cid, "shows", sid)


def _agents(g: Graph):
    for f in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        t = f.read_text(encoding="utf-8")
        fm = t.split("---")[1] if t.startswith("---") else ""
        name = (re.search(r"^name:\s*(.+)$", fm, re.M) or [None, f.stem])[1].strip()
        aid = f"agent:{name}"
        g.node(aid, "agent", name, file=f".claude/agents/{f.name}")
        for s in re.findall(r"^\s*-\s*(liam-[a-z0-9-]+|signal-work|work-report)\s*$", fm, re.M):
            g.node(f"skill:{s}", "skill", s)
            g.edge(aid, "has_skill", f"skill:{s}")
            m = re.match(r"liam-(e\d\d)-", s)
            if m:
                g.node(f"eng:{m.group(1).upper()}", "engine", m.group(1).upper())
                g.edge(f"skill:{s}", "for_engine", f"eng:{m.group(1).upper()}")
        m = re.match(r"e(\d\d)-", f.stem)
        if m:
            g.node(f"eng:E{m.group(1)}", "engine", f"E{m.group(1)}")
            g.edge(aid, "for_engine", f"eng:E{m.group(1)}")


def _engines(g: Graph):
    import yaml
    d = yaml.safe_load((ROOT / "config" / "engine_registry.yaml").read_text(encoding="utf-8")) or {}
    eng = d.get("engines") or {}
    items = eng.items() if isinstance(eng, dict) else [(e.get("id"), e) for e in eng]
    for k, e in items:
        if isinstance(e, dict):
            g.node(f"eng:{k}", "engine", k, name=e.get("name") or e.get("title"))


def _modules(g: Graph):
    files = list((PY / "hamid").glob("*.py")) + [p for p in PY.glob("*.py")]
    known = {("hamid." + p.stem if p.parent.name == "hamid" else p.stem): p for p in files}
    for mod, p in known.items():
        mid = f"mod:{mod}"
        base = mod.split(".")[-1]
        kind = "test" if base.startswith("test_") else "module"
        g.node(mid, kind, mod, file=str(p.relative_to(ROOT)), lines=sum(1 for _ in p.open(encoding="utf-8", errors="ignore")))
        if kind == "test":
            tgt = "hamid." + base[5:]
            if tgt in known:
                g.edge(mid, "tests", f"mod:{tgt}")
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in re.finditer(r"^\s*(?:from\s+hamid\s+import\s+([\w, ]+)|from\s+(hamid\.\w+)\s+import|import\s+(hamid\.\w+)|from\s+(\w+)\s+import|import\s+(\w+)\s+as)", src, re.M):
            names = []
            if m.group(1):
                names = ["hamid." + x.strip().split(" as ")[0] for x in m.group(1).split(",")]
            else:
                names = [m.group(2) or m.group(3) or m.group(4) or m.group(5)]
            for n in names:
                if n in known and n != mod and kind != "test":
                    g.edge(mid, "imports", f"mod:{n}")


def _rules(g: Graph):
    for f in sorted((ROOT / ".claude" / "rules").glob("*.md")):
        rid = f"rule:{f.stem}"
        t = f.read_text(encoding="utf-8", errors="ignore")
        g.node(rid, "rule", f.stem, file=f".claude/rules/{f.name}")
        for m in set(re.findall(r"`?(hamid/[a-z0-9_]+)\.py`?", t)):
            mid = f"mod:{m.replace('/', '.')}"
            if mid in g.nodes:
                g.edge(rid, "mentions", mid)
        for m in set(re.findall(r"signals/([a-z0-9_.-]+\.json)", t)):
            sid = f"state:signals/{m}"
            if sid in g.nodes:
                g.edge(rid, "mentions", sid)


def build() -> Graph:
    g = Graph()
    _engines(g); _modules(g); _workflows(g); _registry(g); _panel(g); _agents(g); _rules(g)
    return g


# ── خروجی ───────────────────────────────────────────────────────────────
def neighbors(g: Graph, nid: str) -> dict[str, list]:
    out: dict[str, list] = defaultdict(list)
    for a, rel, b in g.edges:
        if a == nid:
            out[f"→ {EDGES.get(rel, rel)}"].append(b)
        elif b == nid:
            out[f"← {EDGES.get(rel, rel)}"].append(a)
    return {k: sorted(v) for k, v in sorted(out.items())}


def resolve(g: Graph, q: str) -> str | None:
    q = q.strip()
    if q in g.nodes:
        return q
    cands = [n for n in g.nodes if n.split(":", 1)[1] == q or n.endswith(":" + q)]
    if not cands:
        qq = q.replace("/", ".").removesuffix(".py")
        cands = [n for n in g.nodes if n.split(":", 1)[1] in (qq, "hamid." + qq, "signals/" + q)]
    if not cands:
        cands = [n for n in g.nodes if q.lower() in n.lower()]
    return sorted(cands, key=len)[0] if cands else None


def who(g: Graph, q: str) -> str:
    nid = resolve(g, q)
    if not nid:
        return f"گره‌ای برای «{q}» نیست"
    n = g.nodes[nid]
    L = [f"{KINDS.get(n['kind'], n['kind'])}: {n['label']}" + (f"  ({n.get('file')})" if n.get("file") else "")]
    for k in ("cron", "cap", "layer", "name"):
        if n.get(k):
            L.append(f"  {k}: {n[k]}")
    for rel, ids in neighbors(g, nid).items():
        L.append(f"  {rel}: " + "، ".join(g.nodes[i]["label"] for i in ids))
    return "\n".join(L)


def to_json(g: Graph) -> dict:
    return {"nodes": sorted(g.nodes.values(), key=lambda n: (n["kind"], n["id"])),
            "edges": [{"from": a, "rel": r, "to": b} for a, r, b in sorted(g.edges)],
            "kinds": KINDS, "rels": EDGES}


def to_index_md(g: Graph) -> str:
    L = ["# نقشهٔ دانش لیام تریدر ۹ — فهرست فشرده", "",
         "مشتق از منبع حقیقت با `python3 -m hamid.graphify --build`؛ پرسش بی‌توکن: "
         "`python3 -m hamid.graphify --who <چیز>`.", ""]
    counts = defaultdict(int)
    for n in g.nodes.values():
        counts[n["kind"]] += 1
    L.append("| نوع | شمار |\n|---|---|")
    L += [f"| {KINDS.get(k, k)} | {v} |" for k, v in sorted(counts.items())]
    L += ["", f"یال‌ها: {len(g.edges)}", ""]
    for kind, title in (("engine", "انجین‌ها"), ("workflow", "ورک‌فلوها"), ("state", "فایل‌های وضعیت"),
                        ("agent", "ایجنت‌ها"), ("card", "کارت‌های پنل")):
        L += [f"## {title}", ""]
        for n in sorted((x for x in g.nodes.values() if x["kind"] == kind), key=lambda x: x["id"]):
            nb = neighbors(g, n["id"])
            if not nb and kind != "engine":
                continue
            extra = f" · کرون `{' | '.join(n['cron'])}`" if n.get("cron") else ""
            extra += f" · سقف {n['cap']}د" if n.get("cap") else ""
            L.append(f"- **{n['label']}**{extra}")
            for rel, ids in nb.items():
                L.append(f"  - {rel}: " + "، ".join(g.nodes[i]["label"] for i in ids[:40])
                         + (f" … (+{len(ids) - 40})" if len(ids) > 40 else ""))
        L.append("")
    return "\n".join(L)


HTML = """<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>گراف لیام تریدر ۹</title>
<style>
:root{--bg:#f6f7f9;--fg:#111;--mut:#667;--card:#fff;--line:#c9ccd3}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1115;--fg:#e8e8ea;--mut:#9aa;--card:#171a21;--line:#333844}}
:root[data-theme=dark]{--bg:#0f1115;--fg:#e8e8ea;--mut:#9aa;--card:#171a21;--line:#333844}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,Tahoma,sans-serif}
header{padding:10px 16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;border-bottom:1px solid var(--line)}
input,select,button{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
#wrap{display:grid;grid-template-columns:1fr 340px;height:calc(100vh - 58px)}
@media(max-width:800px){#wrap{grid-template-columns:1fr}#side{max-height:40vh}}
canvas{width:100%;height:100%;display:block}
#side{overflow:auto;padding:12px 16px;border-inline-start:1px solid var(--line);background:var(--card)}
.k{display:inline-block;width:10px;height:10px;border-radius:50%;margin-inline-end:6px}
small{color:var(--mut)}
</style></head><body>
<header><strong>گراف لیام تریدر ۹</strong>
<input id="q" placeholder="جست‌وجو: latest.json · E23 · paper …" size="28">
<select id="kind"><option value="">همهٔ انواع</option></select>
<label><input type="checkbox" id="only" checked> فقط همسایه‌های انتخاب</label>
<small id="stat"></small></header>
<div id="wrap"><canvas id="c"></canvas><div id="side">روی گره کلیک کن یا جست‌وجو کن.</div></div>
<script>
const G=__GRAPH__;
const COL={engine:'#d97706',workflow:'#2563eb',module:'#059669',test:'#6b7280',state:'#7c3aed',card:'#db2777',agent:'#0891b2',skill:'#65a30d',rule:'#b91c1c'};
const byId={};G.nodes.forEach(n=>byId[n.id]=n);
const adj={};G.edges.forEach(e=>{(adj[e.from]=adj[e.from]||[]).push(e.to);(adj[e.to]=adj[e.to]||[]).push(e.from);});
const ks=document.getElementById('kind');Object.entries(G.kinds).forEach(([k,v])=>{const o=document.createElement('option');o.value=k;o.textContent=v;ks.appendChild(o)});
const cv=document.getElementById('c'),ctx=cv.getContext('2d');let W,H,sel=null,vis=[],pos={},drag=null,view={x:0,y:0,s:1};
function size(){W=cv.width=cv.clientWidth*devicePixelRatio;H=cv.height=cv.clientHeight*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0)}
addEventListener('resize',()=>{size();draw()});size();
function subset(){const q=document.getElementById('q').value.trim().toLowerCase(),k=ks.value,only=document.getElementById('only').checked;
 let ids;if(sel&&only){ids=new Set([sel,...(adj[sel]||[])]);(adj[sel]||[]).forEach(n=>(adj[n]||[]).slice(0,6).forEach(m=>ids.add(m)))}
 else ids=new Set(G.nodes.filter(n=>(!k||n.kind===k)&&(!q||n.id.toLowerCase().includes(q)||n.label.toLowerCase().includes(q))).map(n=>n.id));
 if(!sel&&!q&&!k){ids=new Set(G.nodes.filter(n=>['engine','workflow','card','agent'].includes(n.kind)).map(n=>n.id))}
 vis=[...ids].map(i=>byId[i]);layout();document.getElementById('stat').textContent=vis.length+' گره';}
function layout(){const n=vis.length,w=cv.clientWidth,h=cv.clientHeight;vis.forEach((v,i)=>{if(!pos[v.id]){const a=i/n*6.283;pos[v.id]={x:w/2+Math.cos(a)*Math.min(w,h)*.38,y:h/2+Math.sin(a)*Math.min(w,h)*.38,vx:0,vy:0}}});
 const set=new Set(vis.map(v=>v.id));for(let it=0;it<180;it++){vis.forEach(a=>{const p=pos[a.id];let fx=(w/2-p.x)*.002,fy=(h/2-p.y)*.002;vis.forEach(b=>{if(a===b)return;const q=pos[b.id],dx=p.x-q.x,dy=p.y-q.y,d2=dx*dx+dy*dy+1,f=900/d2;fx+=dx*f/Math.sqrt(d2);fy+=dy*f/Math.sqrt(d2)});(adj[a.id]||[]).forEach(o=>{if(!set.has(o))return;const q=pos[o],dx=q.x-p.x,dy=q.y-p.y,d=Math.sqrt(dx*dx+dy*dy)||1;fx+=dx/d*(d-90)*.02;fy+=dy/d*(d-90)*.02});p.vx=(p.vx+fx)*.6;p.vy=(p.vy+fy)*.6});vis.forEach(a=>{const p=pos[a.id];p.x+=p.vx;p.y+=p.vy})}}
function draw(){ctx.clearRect(0,0,cv.clientWidth,cv.clientHeight);ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.s,view.s);const set=new Set(vis.map(v=>v.id));
 ctx.strokeStyle=getComputedStyle(document.body).getPropertyValue('--line');ctx.lineWidth=1;G.edges.forEach(e=>{if(set.has(e.from)&&set.has(e.to)){const a=pos[e.from],b=pos[e.to];ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke()}});
 ctx.font='12px system-ui';vis.forEach(v=>{const p=pos[v.id];ctx.beginPath();ctx.arc(p.x,p.y,v.id===sel?9:6,0,6.283);ctx.fillStyle=COL[v.kind]||'#888';ctx.fill();if(vis.length<140||v.id===sel||(sel&&(adj[sel]||[]).includes(v.id))){ctx.fillStyle=getComputedStyle(document.body).getPropertyValue('--fg');ctx.fillText(v.label,p.x+9,p.y+4)}});ctx.restore()}
function hit(x,y){x=(x-view.x)/view.s;y=(y-view.y)/view.s;return vis.find(v=>{const p=pos[v.id];return (p.x-x)**2+(p.y-y)**2<121})}
cv.addEventListener('mousedown',e=>{const r=cv.getBoundingClientRect(),n=hit(e.clientX-r.left,e.clientY-r.top);drag={n,x:e.clientX,y:e.clientY,moved:false}});
cv.addEventListener('mousemove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;drag.moved=true;if(drag.n){pos[drag.n.id].x+=dx/view.s;pos[drag.n.id].y+=dy/view.s}else{view.x+=dx;view.y+=dy}draw()});
addEventListener('mouseup',e=>{if(drag&&!drag.moved&&drag.n){select(drag.n.id)}drag=null});
cv.addEventListener('wheel',e=>{e.preventDefault();const f=e.deltaY<0?1.1:.9;view.s*=f;draw()},{passive:false});
function select(id){sel=id;const n=byId[id];const rels={};G.edges.forEach(e=>{if(e.from===id)(rels['→ '+G.rels[e.rel]]=rels['→ '+G.rels[e.rel]]||[]).push(e.to);if(e.to===id)(rels['← '+G.rels[e.rel]]=rels['← '+G.rels[e.rel]]||[]).push(e.from)});
 let h='<h3 style="margin:.2em 0"><span class="k" style="background:'+COL[n.kind]+'"></span>'+n.label+'</h3><small>'+G.kinds[n.kind]+(n.file?' · '+n.file:'')+(n.cron?' · کرون '+n.cron.join(' | '):'')+(n.cap?' · سقف '+n.cap+'د':'')+'</small>';
 Object.entries(rels).forEach(([k,v])=>{h+='<p><b>'+k+'</b><br>'+v.sort().map(i=>'<a href="#" data-id="'+i+'">'+byId[i].label+'</a>').join('، ')+'</p>'});
 document.getElementById('side').innerHTML=h;document.querySelectorAll('#side a').forEach(a=>a.onclick=ev=>{ev.preventDefault();select(a.dataset.id)});subset();draw()}
['q','kind','only'].forEach(i=>document.getElementById(i).addEventListener('input',()=>{if(i==='q'||i==='kind')sel=null;subset();draw()}));
subset();draw();
</script></body></html>"""


def write_all(g: Graph) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    j = to_json(g)
    (OUT_DIR / "graph.json").write_text(json.dumps(j, ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT_DIR / "index.html").write_text(HTML.replace("__GRAPH__", json.dumps(j, ensure_ascii=False)), encoding="utf-8")
    (OUT_DIR / "INDEX.md").write_text(to_index_md(g), encoding="utf-8")
    return {"nodes": len(g.nodes), "edges": len(g.edges), "out": str(OUT_DIR.relative_to(ROOT))}


def selftest() -> int:
    g = build()
    ok = 0
    def chk(name, cond, extra=""):
        nonlocal ok
        print(("  ✓ " if cond else "  ✗ ") + name + (f"  — {extra}" if extra and not cond else ""))
        ok += 0 if cond else 1
    kinds = {n["kind"] for n in g.nodes.values()}
    chk("هر نُه نوع گره حاضر است", kinds >= set(KINDS), str(set(KINDS) - kinds))
    chk("۲۷ انجین", sum(1 for n in g.nodes.values() if n["kind"] == "engine") >= 27)
    py_wfs = [n["id"] for n in g.nodes.values() if n["kind"] == "workflow" and n.get("cron")
              and "python" in (WF_DIR / n["id"][3:]).read_text(encoding="utf-8")]
    missing = [w for w in py_wfs if not any(a == w for a, r, b in g.edges if r in ("runs", "gates"))]
    chk("هر ورک‌فلوی کرون‌دارِ پایتونی دست‌کم یک ماژول اجرا می‌کند", not missing, str(missing))
    chk("هر فایل قرارداد مالک دارد",
        all(any(b == n["id"] and r == "owns" for a, r, b in g.edges) for n in g.nodes.values()
            if n["kind"] == "state" and n.get("layer")))
    chk("پنل دست‌کم ۱۵ فایل signals می‌خواند",
        sum(1 for a, r, b in g.edges if r == "shows") >= 15)
    chk("هر ایجنت دست‌کم یک مهارت دارد",
        all(any(a == n["id"] and r == "has_skill" for a, r, b in g.edges) for n in g.nodes.values() if n["kind"] == "agent"))
    chk("پرسش «latest.json» تولیدکننده و کارت می‌دهد",
        "می‌سازد" in who(g, "latest.json") and "نمایش" in who(g, "latest.json"), who(g, "latest.json")[:200])
    chk("پرسش «E23» فایل‌هایش را می‌دهد", "مالک" in who(g, "E23"))
    chk("پرسش «hamid/paper.py» ورک‌فلو/آزمون می‌دهد", "آزمون" in who(g, "hamid/paper.py"))
    chk("گرهٔ ناموجود پیام روشن می‌دهد", "نیست" in who(g, "zzz-nope"))
    print(("✗ " if ok else "✓ ") + f"گرافیفای: {len(g.nodes)} گره · {len(g.edges)} یال")
    return 1 if ok else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--selftest" in a:
        sys.exit(selftest())
    g = build()
    if "--who" in a:
        print(who(g, a[a.index("--who") + 1]))
    else:
        print(json.dumps(write_all(g), ensure_ascii=False))
