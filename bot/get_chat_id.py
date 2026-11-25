"""Bot qo'shilgan guruh/kanallarning chat ID'sini ko'rsatadi.

Ishlatish: TELEGRAM_BOT_TOKEN muhit o'zgaruvchisi bilan ishga tushiring.
"""

import os
import sys

from coupang_bot import tg_call

UPDATE_KEYS = ("message", "channel_post", "my_chat_member", "chat_member", "edited_message")


def extract_chats(updates):
    chats = {}
    for upd in updates:
        for key in UPDATE_KEYS:
            chat = (upd.get(key) or {}).get("chat")
            if chat and chat.get("type") != "private":
                chats[chat["id"]] = (chat.get("type", "?"), chat.get("title", ""))
    return chats


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("XATO: TELEGRAM_BOT_TOKEN Secrets'da yo'q.")
        return 1
    try:
        updates = tg_call(token, "getUpdates", {"allowed_updates": list(UPDATE_KEYS)})["result"]
    except Exception as e:
        print(f"XATO: Telegram'dan javob olinmadi: {e}")
        return 1
    chats = extract_chats(updates)
    if not chats:
        print("Guruh topilmadi. Guruhga kirib  /start@BOT_NOMI  deb yozing va qayta ishga tushiring.")
        return 1
    print("Topilgan guruh/kanallar (ID'ni TELEGRAM_CHAT_ID ga qo'ying):")
    for cid, (ctype, title) in chats.items():
        print(f"  {cid}   ({ctype})   {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
