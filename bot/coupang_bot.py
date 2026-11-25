"""Coupang Goldbox chegirmalarini Telegram guruhiga tashlaydigan bot.

Faqat Python standart kutubxonasi ishlatiladi.
Muhit o'zgaruvchilari: APIFY_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

POST_COUNT = 20
FETCH_COUNT = 40
PAUSE_SECONDS = 4
APIFY_URL = (
    "https://api.apify.com/v2/acts/lentic_clockss~coupang-scraper/"
    "run-sync-get-dataset-items"
)
TITLE_MAX = 300
IMAGE_KEYS = ("image", "imageUrl", "imageURL", "thumbnail", "productImage")
PRICE_KEYS = ("price", "salePrice", "finalPrice")


def to_number(v):
    """45, "45%", "21,900원" -> raqam; bo'sh yoki noto'g'ri qiymat -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    # faqat birinchi raqamni olamiz: "21,900원 (10g당 1,234원)" -> 21900
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(v))
    if not m:
        return None
    n = float(m.group().replace(",", ""))
    return int(n) if n.is_integer() else n


def _price(item):
    for key in PRICE_KEYS:
        p = to_number(item.get(key))
        if p:
            return p
    return None


def _discount(item):
    d = to_number(item.get("discountPercentage"))
    if d:
        return d
    # chegirma foizi berilmagan bo'lsa — narxlardan hisoblaymiz
    price, old = _price(item), to_number(item.get("listPrice"))
    if price and old and old > price:
        return round(100 * (1 - price / old))
    return 0


def pick_top(items, n):
    """Chegirma foizi bo'yicha kamayish tartibida, takrorsiz, eng yaxshi n ta."""
    seen = set()
    unique = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not item.get("title") and not item.get("url"):
            continue
        key = item.get("productId") or item.get("url") or item.get("title")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    unique.sort(key=_discount, reverse=True)
    return unique[:n]


def find_image(item):
    for key in IMAGE_KEYS:
        v = item.get(key)
        if isinstance(v, str):
            if v.startswith("//"):
                v = "https:" + v
            if v.startswith(("http://", "https://")):
                return v
    return None


def _won(n):
    return f"{int(round(n)):,}₩"


def format_caption(item):
    raw_title = str(item.get("title") or "Mahsulot")
    if len(raw_title) > TITLE_MAX:
        raw_title = raw_title[: TITLE_MAX - 1] + "…"
    title = html.escape(raw_title)
    url = html.escape(str(item.get("url") or ""), quote=True)
    discount = _discount(item)

    price = _price(item)
    old = to_number(item.get("listPrice"))

    head = f"🔥 <b>-{int(round(discount))}%</b>  {title}" if discount > 0 else f"🔥 {title}"
    lines = [head]
    if price:
        if old and old > price:
            lines.append(f"<s>{_won(old)}</s>  →  <b>{_won(price)}</b>")
        else:
            lines.append(f"<b>{_won(price)}</b>")
    if url:
        lines.append(f'🛒 <a href="{url}">Coupang\'da ko\'rish</a>')
    return "\n".join(lines)


class HttpError(RuntimeError):
    def __init__(self, code, body):
        super().__init__(f"HTTP {code}: {body[:300]}")
        self.code = code
        self.body = body

    def params(self):
        try:
            return json.loads(self.body).get("parameters") or {}
        except (ValueError, AttributeError):
            return {}


def _post_json(url, payload, headers=None, timeout=60):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, e.read().decode("utf-8", "replace")[:500]) from None


def fetch_goldbox(token, max_results=FETCH_COUNT):
    """Apify orqali Coupang Goldbox ro'yxatini oladi (token sarlavhada, URL'da emas)."""
    for attempt in (1, 2):
        try:
            data = _post_json(
                APIFY_URL,
                {"mode": "goldbox", "maxResults": max_results},
                headers={"Authorization": f"Bearer {token}"},
                timeout=330,  # Apify o'zi 300 s da 408 qaytaradi
            )
            break
        except (HttpError, TimeoutError) as e:
            slow = isinstance(e, TimeoutError) or e.code == 408
            if not slow or attempt == 2:
                if slow:
                    raise RuntimeError("Apify juda sekin ishladi, keyinroq qayta urinib ko'ring") from None
                raise
            print("Apify sekin javob berdi, yana bir marta urinilmoqda...")
    if not isinstance(data, list):
        raise RuntimeError(f"Apify kutilmagan javob qaytardi: {str(data)[:200]}")
    return data


def tg_call(bot_token, method, payload):
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    for attempt in (1, 2):
        try:
            data = _post_json(url, payload, timeout=30)
            break
        except HttpError as e:
            params = e.params()
            if e.code == 429 and attempt == 1:
                time.sleep(int(params.get("retry_after", 5)) + 1)
                continue
            if params.get("migrate_to_chat_id"):
                raise RuntimeError(
                    "Guruh superguruhga aylangan. Yangi ID: "
                    f"{params['migrate_to_chat_id']} — uni TELEGRAM_CHAT_ID ga qo'ying"
                ) from None
            raise
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram xatosi"))
    return data


def send_item(bot_token, chat_id, item):
    caption = format_caption(item)
    image = find_image(item)
    if image:
        try:
            tg_call(bot_token, "sendPhoto",
                    {"chat_id": chat_id, "photo": image, "caption": caption, "parse_mode": "HTML"})
            return True
        except Exception as e:  # rasm yaroqsiz bo'lsa — matn bilan yuboramiz
            print(f"  rasm yuborilmadi ({e}), matn bilan yuborilmoqda")
    try:
        tg_call(bot_token, "sendMessage",
                {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"})
        return True
    except Exception as e:
        print(f"  xabar yuborilmadi: {e}")
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Coupang Goldbox → Telegram")
    parser.add_argument("--dry-run", action="store_true", help="faqat ko'rsatadi, yubormaydi")
    parser.add_argument("--count", type=int, default=POST_COUNT)
    args = parser.parse_args(argv)

    apify = os.environ.get("APIFY_TOKEN", "").strip()
    bot = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    missing = [n for n, v in (("APIFY_TOKEN", apify), ("TELEGRAM_BOT_TOKEN", bot),
                              ("TELEGRAM_CHAT_ID", chat)) if not v]
    if args.dry_run:
        missing = [m for m in missing if m == "APIFY_TOKEN"]
    if missing:
        print("XATO: GitHub Secrets'da yo'q: " + ", ".join(missing))
        return 1

    try:
        items = fetch_goldbox(apify)
    except Exception as e:
        print(f"XATO: Apify'dan ma'lumot olinmadi: {e}")
        return 1

    top = pick_top(items, args.count)
    print(f"Apify'dan {len(items)} ta mahsulot keldi, {len(top)} tasi tanlandi.")
    if not top:
        print("XATO: bugun chegirmali mahsulot topilmadi, hech narsa yuborilmadi.")
        return 1

    sent = 0
    for i, item in enumerate(top, 1):
        if args.dry_run:
            print(f"--- {i} ---\n{format_caption(item)}\nrasm: {find_image(item)}")
            continue
        print(f"{i}/{len(top)} yuborilmoqda...")
        if send_item(bot, chat, item):
            sent += 1
        if i < len(top):
            time.sleep(PAUSE_SECONDS)

    if args.dry_run:
        return 0
    print(f"Tayyor: {sent}/{len(top)} ta post yuborildi.")
    return 0 if sent else 1


if __name__ == "__main__":
    sys.exit(main())
