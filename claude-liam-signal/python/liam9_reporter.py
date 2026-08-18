#!/usr/bin/env python3
"""گزارشگر داشبورد → لیام تریدر ۹ (کانال برگشتی؛ دستور حمید، ۱۸ اوت).

این فایل را کنار استراتژی در داشبورد بگذار. هر معامله/رویدادی که داشبورد
انجام داد را به ریپو می‌فرستد تا من (کلود) و ماشین‌های شبانه ببینندش،
با دفتر پیپر مقایسه شود و عیب‌یابی روی دادهٔ واقعی داشبورد انجام شود.

راه‌اندازی (یک بار):
  ۱. گیت‌هاب → Settings → Developer settings → Fine-grained tokens →
     توکن جدید فقط برای مخزن Auraliam/Liam-Trader-9 با مجوز
     «Contents: Read and write» — هیچ مجوز دیگری نده.
  ۲. توکن را در محیط داشبورد بگذار:  LIAM9_REPORT_TOKEN=github_pat_...
     (فقط env — نه کد، نه چت. قانون ۰۵.)

استفاده در داشبورد:
    import liam9_reporter as rep
    rep.report({"event": "order_filled", "symbol": "BTCUSDT",
                "dir": "LONG", "entry": 61234.5, "qty": 0.001,
                "mode": "demo"})

هر ردیف به brain/shadow/dash-<سال-ماه>.jsonl ریپو append می‌شود
(append-only؛ نویسندهٔ این فایل فقط داشبورد است — ایمنی تک‌نویسنده).
شکست شبکه چیزی را نمی‌خواباند: ردیف در صف محلی می‌ماند و دفعهٔ بعد می‌رود.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

OWNER_REPO = "Auraliam/Liam-Trader-9"
API = f"https://api.github.com/repos/{OWNER_REPO}/contents"
QUEUE = Path.home() / ".liam9-report-queue.jsonl"


def _token():
    return os.environ.get("LIAM9_REPORT_TOKEN", "").strip()


def _req(url, method="GET", data=None):
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"Bearer {_token()}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "liam9-reporter"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _path_now():
    return f"brain/shadow/dash-{time.strftime('%Y-%m')}.jsonl"


def _push_lines(lines):
    """append چند ردیف به فایل ماهِ جاری در ریپو (GET sha → PUT)."""
    path = _path_now()
    url = f"{API}/{path}"
    sha, current = None, ""
    try:
        d = _req(url)
        sha = d.get("sha")
        current = base64.b64decode(d.get("content") or "").decode()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    body = current + "".join(json.dumps(x, ensure_ascii=False) + "\n"
                             for x in lines)
    payload = {"message": f"گزارش داشبورد ({len(lines)} ردیف)",
               "content": base64.b64encode(body.encode()).decode()}
    if sha:
        payload["sha"] = sha
    _req(url, "PUT", payload)


def report(event):
    """یک رویداد بفرست؛ خطا = صف محلی، دفعهٔ بعد همراه می‌رود."""
    if not isinstance(event, dict):
        return False
    event = {"t": int(time.time() * 1000), "src": "dashboard", **event}
    pending = []
    if QUEUE.exists():
        pending = [json.loads(l) for l in QUEUE.read_text().splitlines() if l]
    pending.append(event)
    if not _token():
        QUEUE.write_text("\n".join(json.dumps(x, ensure_ascii=False)
                                   for x in pending) + "\n")
        print("liam9_reporter: LIAM9_REPORT_TOKEN تنظیم نیست — در صف محلی ماند")
        return False
    try:
        _push_lines(pending)
        QUEUE.unlink(missing_ok=True)
        return True
    except Exception as e:                           # noqa: BLE001
        QUEUE.write_text("\n".join(json.dumps(x, ensure_ascii=False)
                                   for x in pending) + "\n")
        print(f"liam9_reporter: نرفت ({type(e).__name__}) — در صف ماند")
        return False


if __name__ == "__main__":
    ok = report({"event": "hello", "note": "تست کانال برگشتی داشبورد"})
    print("ارسال:", "✅" if ok else "در صف")
