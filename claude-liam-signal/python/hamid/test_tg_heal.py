"""آزمون خوددرمانی chat_id تلگرام — Secret غلط، کشف چت واقعی، ارسال موفق."""
import io
import json
import sys
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import telegram as tg                                          # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


class FakeNet:
    """شبیه‌ساز API تلگرام: ارسال به شناسهٔ ربات رد می‌شود، چت واقعی موجود است."""

    def __init__(self):
        self.sent = []          # (chat_id, تکه‌ای از متن)

    def urlopen(self, req, timeout=0):
        url = req.get_full_url()
        body = (req.data or b"").decode("utf-8", "ignore")
        if url.endswith("/getUpdates"):
            return io.BytesIO(json.dumps({"ok": True, "result": [
                {"message": {"chat": {"id": 777001, "type": "private",
                                      "first_name": "حمید"}}}]}).encode())
        # chat_id از بدنهٔ multipart در می‌آید
        chat = ""
        for part in body.split("Content-Disposition"):
            if 'name="chat_id"' in part:
                chat = part.split("\r\n\r\n")[1].split("\r\n")[0]
        if chat == "999BOT":
            err = json.dumps({"ok": False, "error_code": 403,
                              "description": "Forbidden: the bot can't send messages to the bot"})
            raise urllib.error.HTTPError(url, 403, "Forbidden", None,
                                         io.BytesIO(err.encode()))
        self.sent.append((chat, "پیام"))
        return io.BytesIO(json.dumps(
            {"ok": True, "result": {"message_id": 42}}).encode())


def run():
    net = FakeNet()
    old = tg.urllib.request.urlopen
    tg.urllib.request.urlopen = net.urlopen
    tg._HEALED_CHAT, tg._HEAL_NOTICED = None, False
    try:
        # ۱) ارسال با Secret غلط (شناسهٔ ربات) → خوددرمانی → ارسال به چت واقعی
        r = tg._post_once("tok", "sendMessage",
                          {"chat_id": "999BOT", "text": "سیگنال"})
        check("ارسال با chat_id غلط، خوددرمان و موفق شد",
              r.get("ok") and r["result"]["message_id"] == 42)
        check("مقصد واقعی همان چت کشف‌شده است",
              any(c == "777001" for c, _ in net.sent), str(net.sent))
        check("پیام یک‌بارمصرف «Secret را اصلاح کن» هم رفت",
              len(net.sent) == 2 and tg._HEAL_NOTICED)

        # ۲) ارسال دوم در همان اجرا: بدون getUpdates اضافه، بدون نوتیس تکراری
        n_before = len(net.sent)
        r2 = tg._post_once("tok", "sendMessage",
                           {"chat_id": "999BOT", "text": "سیگنال ۲"})
        check("ارسال دوم هم موفق و نوتیس تکرار نشد",
              r2.get("ok") and len(net.sent) == n_before + 1)

        # ۳) خطای غیرِ chat (مثلاً ۴۰۱ توکن) دست‌نخورده بالا می‌آید
        def bad(req, timeout=0):
            err = json.dumps({"ok": False, "description": "Unauthorized"})
            raise urllib.error.HTTPError("u", 401, "Unauthorized", None,
                                         io.BytesIO(err.encode()))
        tg.urllib.request.urlopen = bad
        try:
            tg._post_once("tok", "sendMessage", {"chat_id": "1", "text": "x"})
            check("خطای توکن باید بالا بیاید", False)
        except urllib.error.HTTPError:
            check("خطای غیرقابل‌درمان همان رفتار قبلی را دارد", True)
    finally:
        tg.urllib.request.urlopen = old
        tg._HEALED_CHAT, tg._HEAL_NOTICED = None, False

    print(f"\n✓ همهٔ {OK} آزمون خوددرمانی تلگرام گذشت")


if __name__ == "__main__":
    run()
