"""پاسبان قفلِ ارسال (۱ اکتبر) — با HTTP ساختگی، بی‌شبکه.

۱. بی‌توکن → مجاز، با دلیل (قفل محلی غیرفعال).
۲. فایلِ ادعا نیست (۴۰۴) → ساخته می‌شود (PUT بی‌sha) → مجاز.
۳. ادعای تازه (< TTL) → رد با دلیل؛ ادعای کهنه → PUT با sha → مجاز.
۴. PUT با 409/422 (رانر دیگر همین لحظه برنده شد) → رد.
۵. خطای شبکه → مجاز (نرم) — سیگنال هرگز به‌خاطر قفل گم نمی‌شود.
۶. سیم‌کشی: قفل بعد از آخرین دروازه و پیش از چارت/ارسال در send_signals.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import send_lock as L                                # noqa: E402

OK, BAD = [], []


def check(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  — {extra}" if extra and not cond else ""))


NOW = 1_790_000_000_000
calls = []


def fake(script):
    """script: list of (status | HTTPError-code | Exception) per call, in order."""
    it = iter(script)

    def _api(url, tok, method="GET", data=None):
        calls.append((method, url.rsplit("/", 1)[-1], data))
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    return _api


def herr(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


def body(at, run="r1"):
    return {"sha": "abc", "content": base64.b64encode(json.dumps({"at": at, "run": run}).encode()).decode()}


_orig = L._api
for k in ("GITHUB_TOKEN", "GH_TOKEN", "LIAM9_SANDBOX", "LIAM9_NO_REMOTE_DEDUPE"):
    os.environ.pop(k, None)
os.environ["GITHUB_ACTIONS"] = "false"
ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
check("بیرون از رانر → مجاز، بی‌تماس (قفل فقط برای رانرهای هم‌زمان است)", ok and "رانر" in why and not calls, why)
os.environ["GITHUB_ACTIONS"] = "true"
ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW)
check("بی‌توکن → مجاز با دلیل", ok and "بی‌توکن" in why, why)
os.environ["LIAM9_SANDBOX"] = "1"
ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
check("حالت شنی → مجاز، بی‌تماس", ok and "شنی" in why and not calls, why)
os.environ.pop("LIAM9_SANDBOX", None)

try:
    L._api = fake([herr(404), (201, {})])
    ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
    check("ادعا نبود → ساخته شد → مجاز", ok and calls[-1][0] == "PUT" and "sha" not in calls[-1][2], why)
    check("مسیر فایل = brain/claims/<SYM>-<DIR>.json", calls[-1][1] == "XUSDT-LONG.json")

    L._api = fake([(200, body(NOW - 5 * 60000, "other"))])
    ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
    check("ادعای ۵ دقیقه پیش → رد (کس دیگری فرستاده)", not ok and "other" in why, why)

    L._api = fake([(200, body(NOW - 400 * 60000)), (200, {})])
    ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
    check("ادعای کهنه (۴۰۰د) → به‌روزرسانی با sha → مجاز", ok and calls[-1][2].get("sha") == "abc", why)

    L._api = fake([herr(404), herr(422)])
    ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
    check("رانر دیگر همین لحظه ساخت (422) → رد", not ok, why)

    L._api = fake([(200, body(NOW - 400 * 60000)), herr(409)])
    ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
    check("تعارض sha (409) → رد", not ok, why)

    L._api = fake([TimeoutError("net")])
    ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
    check("خطای شبکه → مجاز (نرم)", ok and "نرم" in why, why)

    L._api = fake([herr(404), herr(500)])
    ok, why = L.claim("XUSDT", "LONG", "5m", now_ms=NOW, tok="t")
    check("خطای ۵۰۰ در PUT → مجاز (نرم)", ok, why)
finally:
    L._api = _orig

src = (HERE.parent / "telegram.py").read_text(encoding="utf-8")
body_ = src[src.index("def send_signals"):]
i_lock = body_.index("_lock.claim(")
check("قفل بعد از هندسهٔ ×۲ (آخرین دروازه) و پیش از چارت/ارسال است",
      body_.index("apply_geo15(s)") < i_lock < body_.index("render_chart(s,"))
check("شکستِ قفل سیگنال را گم نمی‌کند (استثنا → ادامه)", "_ok, _why = True" in body_)
# ۱ اکتبر: دلیلِ قفل فقط در ردشدن چاپ می‌شد؛ «بی‌توکن → مجاز» بی‌صدا بود و
# ۴ ساعت کسی نفهمید قفل در دو حامل خاموش است. حالا هر ادعا یک خط دارد.
_seg = body_[i_lock:body_.index("render_chart(s,")]
check("دلیلِ قفل همیشه چاپ می‌شود، مجاز یا رد (قفلِ ساکت ممنوع)",
      "قفل ارسال" in _seg and _seg.index("قفل ارسال") < _seg.index("if not _ok"))
wf = HERE.parents[2] / ".github" / "workflows"
check("پاسبان در دروازهٔ هر دو زنجیره",
      all("hamid.test_send_lock" in (wf / f).read_text(encoding="utf-8") for f in ("hamid-cycle.yml", "pump-radar.yml")))

# ── کلاسِ عیب ۱ اکتبر: قفلی که اعتبارش به گامِ ارسال نرسیده ────────────────
#
# LDOUSDT ۱۳:۱۴:۴۳ (زنجیره، ادعا ثبت شد) و ۱۳:۱۶:۱۹ (اسکن زنده) — ۹۶ ثانیه؛
# AAVEUSDT ۱۴:۳۰:۵۲ و ۱۴:۳۱:۴۶ — ۵۴ ثانیه. گامِ «Scan and deliver» اسکن زنده و
# «Run the cycle» چرخه GITHUB_TOKEN را به env نمی‌دادند؛ قفل «بی‌توکن → مجاز»
# می‌گفت و هیچ‌کس نمی‌دید. آزمونِ قبلی فقط سیم‌کشیِ *کد* را می‌سنجید، نه
# ورک‌فلو را. خاصیت: **هر** گامی که فرستنده را صدا می‌زند، توکن دارد.
import yaml                                                      # noqa: E402

_SENDER = re.compile(r"scan\.py[^\n]*--telegram|hamid\.cycle\b")
_missing, _found = [], 0
for f in sorted(wf.glob("*.yml")):
    try:
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        continue
    wf_env = (doc.get("env") or {}) if isinstance(doc, dict) else {}
    for jname, job in ((doc.get("jobs") or {}) if isinstance(doc, dict) else {}).items():
        if not isinstance(job, dict):
            continue
        job_env = job.get("env") or {}
        for st in (job.get("steps") or []):
            if not isinstance(st, dict):
                continue
            run = "\n".join(l for l in (st.get("run") or "").splitlines()
                            if not l.strip().startswith("#"))
            if not _SENDER.search(run):
                continue
            _found += 1
            env = {**wf_env, **job_env, **(st.get("env") or {})}
            if "GITHUB_TOKEN" not in env and "GH_TOKEN" not in env:
                _missing.append(f"{f.name}: «{st.get('name')}»")
check(f"هر گامِ ارسال (scan --telegram / hamid.cycle) GITHUB_TOKEN دارد — {_found} گام، غایب: {_missing or 'هیچ'}",
      _found >= 3 and not _missing)

print()
if BAD:
    print(f"✗ {len(BAD)} بررسی افتاد: {BAD}")
    sys.exit(1)
print(f"پاسبان قفل ارسال: هر {len(OK)} بررسی سبز")
