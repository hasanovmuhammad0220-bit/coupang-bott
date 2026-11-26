"""Coupang chegirmalarini (avto moy, avto qismlar, brend kiyim, oyoq kiyim)
Telegram guruhiga kuniga 3 marta tashlaydigan bot.

Faqat Python standart kutubxonasi ishlatiladi.
Muhit o'zgaruvchilari: APIFY_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# ===== SOZLAMALAR (shu yerni o'zgartirsangiz bo'ladi) =====
# (postdagi nomi, Coupang'da qidiriladigan so'z — koreyscha)
KEYWORDS = [
    ("🛢 Avto moy", "엔진오일"),
    ("🔧 Avto ehtiyot qismlar", "자동차 부품"),
    ("👕 Brend kiyim", "나이키 의류"),
    ("👟 Oyoq kiyim", "운동화"),
]
PER_KEYWORD = 11          # har bir so'zdan nechta mahsulot olinadi (bepul $5 limit uchun)
SLOTS = {"morning": 5, "noon": 10, "evening": 5}   # 08:00, 12:00, 18:00
POOL_PATH = "data/pool.json"
# ===========================================================
TOTAL = sum(SLOTS.values())
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
    if item.get("_category"):
        lines.insert(0, f"<i>{html.escape(str(item['_category']))}</i>")
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


def fetch_keyword(token, keyword, max_results=PER_KEYWORD):
    """Apify orqali Coupang'da kalit so'z bo'yicha qidiradi (token sarlavhada, URL'da emas)."""
    for attempt in (1, 2):
        try:
            data = _post_json(
                APIFY_URL,
                {"mode": "keywordSearch", "keyword": keyword, "maxResults": max_results},
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


def collect(token):
    """Har bir kalit so'z bo'yicha qidiradi; {nomi: [mahsulotlar]} qaytaradi."""
    by_cat, errors = {}, []
    for label, keyword in KEYWORDS:
        try:
            items = fetch_keyword(token, keyword)
        except Exception as e:
            print(f"  '{keyword}' qidirilmadi: {e}")
            errors.append(keyword)
            continue
        for item in items:
            if isinstance(item, dict):
                item["_category"] = label
        by_cat[label] = items
        print(f"  {label}: {len(items)} ta mahsulot")
    if not by_cat:
        raise RuntimeError("hech bir kalit so'z bo'yicha ma'lumot olinmadi")
    return by_cat


def _key(item):
    return item.get("productId") or item.get("url") or item.get("title")


def build_queue(by_cat, total=TOTAL):
    """Har bo'limdan navbatma-navbat eng katta chegirmani oladi (aralash), takrorsiz."""
    lists = [[i for i in pick_top(items, len(items)) if _discount(i) > 0]
             for items in by_cat.values()]
    queue, seen = [], set()
    while len(queue) < total and any(lists):
        for lst in lists:
            while lst:
                item = lst.pop(0)
                if _key(item) not in seen:
                    seen.add(_key(item))
                    queue.append(item)
                    break
            if len(queue) >= total:
                break
    return queue


def today_kst():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()


def load_pool(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("queue"), list):
            return data
    except (OSError, ValueError):
        pass
    return None


def save_pool(path, date, queue):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": date, "queue": queue}, f, ensure_ascii=False, indent=1)


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
    parser = argparse.ArgumentParser(description="Coupang chegirmalar → Telegram")
    parser.add_argument("--slot", choices=list(SLOTS), required=True,
                        help="morning=08:00, noon=12:00, evening=18:00")
    parser.add_argument("--dry-run", action="store_true", help="faqat ko'rsatadi, yubormaydi")
    parser.add_argument("--pool", default=POOL_PATH)
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

    today = today_kst()
    pool = load_pool(args.pool)
    if args.slot == "morning" or not pool or pool.get("date") != today:
        print("Coupang'dan bugungi chegirmalar qidirilmoqda...")
        try:
            queue = build_queue(collect(apify))
        except Exception as e:
            print(f"XATO: Apify'dan ma'lumot olinmadi: {e}")
            return 1
        print(f"Bugun uchun {len(queue)} ta chegirmali mahsulot tanlandi.")
        if not queue:
            print("XATO: bugun chegirmali mahsulot topilmadi, hech narsa yuborilmadi.")
            return 1
    else:
        queue = pool["queue"]

    take, rest = queue[: SLOTS[args.slot]], queue[SLOTS[args.slot]:]
    if not take:
        print("Bugungi chegirmalar tugadi, bu safar yuboriladigan narsa yo'q.")
        return 0

    if args.dry_run:
        for i, item in enumerate(take, 1):
            print(f"--- {i} ---\n{format_caption(item)}\nrasm: {find_image(item)}")
        return 0

    sent = 0
    for i, item in enumerate(take, 1):
        print(f"{i}/{len(take)} yuborilmoqda...")
        if send_item(bot, chat, item):
            sent += 1
        if i < len(take):
            time.sleep(PAUSE_SECONDS)
    save_pool(args.pool, today, rest)
    print(f"Tayyor: {sent}/{len(take)} ta post yuborildi. Keyingi vaqtlar uchun {len(rest)} ta qoldi.")
    return 0 if sent else 1


if __name__ == "__main__":
    sys.exit(main())
