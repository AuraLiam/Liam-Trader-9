"""خوانندهٔ واحدِ ستاپ‌های منتشرشونده از signals/latest.json (۱ اکتبر).

درسِ همان روز: سه رانر (اتاق ساختار، میز ریسک، موتور ۱ دقیقه) هر کدام
`latest.json["symbols"]` را فهرست فرض کرده بودند — ولی آن کلید **شمار** است
(int)، و فهرست‌ها زیر `signals` / `alarms` / `watch` نشسته‌اند. آزمونِ
تزریقی سبز بود و روی رانر TypeError خورد. قاعده: شکلِ فایل را یک جا
بخوان، و آزمونش را روی **نمونهٔ هم‌شکلِ فایلِ واقعی** بزن، نه روی حدس.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LATEST = ROOT / "signals" / "latest.json"
LIST_KEYS = ("signals", "alarms", "watch")
RANK = {"SIGNAL": 0, "ARMED": 1, "PULLBACK_1": 2, "WATCH": 3}


def load(path=None) -> dict:
    try:
        d = json.loads((path or LATEST).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:                                 # noqa: BLE001
        return {}


def setups(stages=None, limit=None, doc=None, path=None) -> list[dict]:
    """ستاپ‌ها به ترتیب مرحله (SIGNAL جلوتر)، یکتا بر (نماد، جهت، تایم)."""
    d = doc if doc is not None else load(path)
    rows = []
    for k in LIST_KEYS:
        v = d.get(k)
        if isinstance(v, list):
            rows += [x for x in v if isinstance(x, dict) and x.get("sym")]
    rows.sort(key=lambda x: RANK.get(x.get("stage"), 9))
    seen, out = set(), []
    for x in rows:
        if stages and x.get("stage") not in stages:
            continue
        key = (x.get("sym"), x.get("dir"), x.get("tf"))
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
        if limit and len(out) >= limit:
            break
    return out


def symbols(stages=None, limit=None, doc=None, path=None) -> list[str]:
    seen, out = set(), []
    for x in setups(stages=stages, doc=doc, path=path):
        if x["sym"] not in seen:
            seen.add(x["sym"]); out.append(x["sym"])
        if limit and len(out) >= limit:
            break
    return out
