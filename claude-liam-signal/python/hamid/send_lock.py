"""قفلِ ارسال — یک نویسنده برای هر سیگنال، بین رانرهای هم‌زمان (دستور حمید، ۱ اکتبر).

ریشهٔ اندازه‌گیری‌شده (۲۹ سپتامبر): SPCXBUSDT ۵د لانگ دو بار در ۵۰ ثانیه
(۱۳:۰۰:۲۲ و ۱۳:۰۱:۱۲) — دو رانر (اسکن زنده و زنجیره) هم‌زمان رسیده بودند.
چهار منبعِ ضدتکرار (دیسک، /tmp، لاگ، ریموت) همه **بعد از push** دیده
می‌شوند؛ push زنجیره تا پایانِ دور (تا ۳ دقیقه) می‌افتد، پس فاصلهٔ زیر یک
دقیقه را هیچ‌کدام نمی‌بینند. ۱ از ۱۷۹ سیگنال ۸ روز (۰.۶٪).

درمانِ کلاس (قانون ۰۵: یک نویسنده برای تلگرام): پیش از هر ارسال، یک
«ادعا» با API محتوای گیت‌هاب نوشته می‌شود — `brain/claims/<SYM>-<DIR>.json`.
ساخت/به‌روزرسانیِ آن اتمیک است (PUT با sha؛ sha کهنه = 409/422)، پس دو رانر
نمی‌توانند هر دو برنده شوند. ادعای تازه‌تر از TTL = «کسی فرستاده» → این
رانر نمی‌فرستد.

مرزها (صادقانه):
  · شکستِ شبکه/API = **نرم**: ارسال متوقف نمی‌شود (سیگنال محصول است)؛
    فقط لاگ. قفل، لایهٔ پنجم است نه تنها لایه.
  · بی GITHUB_TOKEN (آزمون محلی) = بی‌قفل، با دلیل.
  · فایل‌های claims دادهٔ runtime‌اند؛ محتوایشان را resolver مثل عکس‌فوری
    می‌بیند (نسخهٔ ما) — بعد از لحظهٔ ارسال دیگر اهمیتی ندارد.
  · شمار فایل‌ها بسته است: یکی برای هر (نماد، جهت)؛ پاک‌سازی لازم نیست.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request

REPO = "AuraLiam/Liam-Trader-9"
DIR = "brain/claims"
TTL_MIN = 180                       # همان پنجرهٔ ضدتکرارِ جفتِ (نماد، جهت)
TIMEOUT_S = 12


def _tok():
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _api(url, tok, method="GET", data=None):
    req = urllib.request.Request(
        url, method=method, data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "liam9-send-lock/1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        body = r.read()
        return r.status, (json.loads(body) if body else {})


def _path(sym, direction):
    return f"{DIR}/{str(sym).upper()}-{str(direction).upper()}.json"


def claim(sym, direction, tf=None, ttl_min=TTL_MIN, now_ms=None, run=None, tok=None):
    """→ (ok, why). ok=True یعنی این رانر مجاز است بفرستد."""
    tok = tok or _tok()
    now = now_ms or int(time.time() * 1000)
    if os.environ.get("LIAM9_SANDBOX") or os.environ.get("LIAM9_NO_REMOTE_DEDUPE"):
        # آزمون‌ها/حالت شنی: هیچ ادعایی روی ریپوی واقعی نوشته نمی‌شود
        return True, "حالت شنی — قفل غیرفعال"
    if os.environ.get("GITHUB_ACTIONS") != "true":
        # قفل برای رانرهای هم‌زمانِ Actions است؛ بیرون از رانر (محلی/سرویس
        # تک‌نویسنده) معنایی ندارد و نباید روی ریپوی واقعی بنویسد
        return True, "بیرون از رانر — قفل غیرفعال"
    if not tok:
        # روی رانر بی‌توکن یعنی گامِ ورک‌فلو GITHUB_TOKEN را به env نداده —
        # عیبِ سیم‌کشی است، نه حالتِ عادی (۱ اکتبر: اسکن زنده و چرخه همین
        # بودند و قفل بی‌صدا هیچ‌کاره شد). محافظ: test_send_lock روی هر گامِ
        # ارسال. این‌جا نرم می‌ماند تا سیگنال گم نشود، ولی بلند می‌گوید.
        return True, "بی‌توکن — قفل غیرفعال؛ GITHUB_TOKEN به env این گام نرسیده (عیب سیم‌کشی)"
    url = f"https://api.github.com/repos/{REPO}/contents/{_path(sym, direction)}"
    body = {"at": now, "sym": sym, "dir": direction, "tf": tf,
            "run": run or os.environ.get("GITHUB_RUN_ID") or "local"}
    content = base64.b64encode(json.dumps(body, ensure_ascii=False).encode()).decode()
    sha = None
    try:
        st, cur = _api(url, tok)
        if st == 200 and isinstance(cur, dict):
            sha = cur.get("sha")
            try:
                prev = json.loads(base64.b64decode((cur.get("content") or "").encode()).decode() or "{}")
            except Exception:                         # noqa: BLE001
                prev = {}
            age = (now - float(prev.get("at") or 0)) / 60000.0
            if age < ttl_min:
                return False, f"ادعای تازه ({age:.1f}د پیش، رانر {prev.get('run')}) — کس دیگری فرستاده"
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return True, f"قفل نرم‌شکست (GET HTTP {e.code}) — ارسال ادامه دارد"
    except Exception as e:                            # noqa: BLE001
        return True, f"قفل نرم‌شکست ({type(e).__name__}) — ارسال ادامه دارد"
    put = {"message": f"ادعای ارسال {sym} {direction} {tf or ''}".strip(),
           "content": content, "branch": "main"}
    if sha:
        put["sha"] = sha
    try:
        st, _ = _api(url, tok, "PUT", put)
        return (st in (200, 201)), f"ادعا ثبت شد (HTTP {st})"
    except urllib.error.HTTPError as e:
        if e.code in (409, 422):
            return False, f"رانر دیگری همین لحظه ادعا کرد (HTTP {e.code})"
        return True, f"قفل نرم‌شکست (PUT HTTP {e.code}) — ارسال ادامه دارد"
    except Exception as e:                            # noqa: BLE001
        return True, f"قفل نرم‌شکست ({type(e).__name__}) — ارسال ادامه دارد"
