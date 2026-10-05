"""Print Telegram chat IDs that have messaged the bot.

Usage:
  TELEGRAM_BOT_TOKEN=... python src/telegram_setup.py

Send /start to the bot first. This script does not save or modify Telegram state.
"""
import os
import requests


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("ERROR: TELEGRAM_BOT_TOKEN belum diset.")
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    data = requests.get(url, timeout=30, params={"allowed_updates": '["message"]'}).json()
    if not data.get("ok"):
        raise SystemExit(f"Telegram error: {data}")
    seen = set()
    for update in data.get("result", []):
        msg = update.get("message", {})
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        if chat_id in seen:
            continue
        seen.add(chat_id)
        print(f"chat_id={chat_id} type={chat.get('type')} title={chat.get('title') or chat.get('first_name') or ''}")
    if not seen:
        print("Belum ada message dari user. Kirim /start ke bot lalu jalankan lagi.")


if __name__ == "__main__":
    main()
