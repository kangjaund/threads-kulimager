"""Telegram approval queue for pending Threads drafts.

- Sends pending drafts to a private Telegram chat with Approve/Reject buttons.
- Polls callback queries and /approve <id> /reject <id> commands.
- Only the configured TELEGRAM_CHAT_ID can approve/reject.
"""
import html
import json
import os
import sys
import time
from pathlib import Path

import requests

from common import load_posts, now_iso, require_env, save_posts

ROOT = Path(__file__).resolve().parent.parent
OFFSET_PATH = ROOT / "data" / "telegram_offset.json"
MAX_TEXT = 3900


def tg_call(token, method, **kwargs):
    url = f"https://api.telegram.org/bot{token}/{method}"
    resp = requests.post(url, timeout=30, **kwargs)
    if not resp.ok:
        raise RuntimeError(f"Telegram {method} error {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} error: {str(data)[:300]}")
    return data["result"]


def safe_answer(token, callback_id, text=None):
    """Konfirmasi tombol ke Telegram. Hanya efek visual di HP, jadi kegagalan diabaikan.

    Telegram menolak konfirmasi jika tombol sudah terlalu lama ditekan (error 400
    'query is too old'), dan itu normal karena approval diproses secara terjadwal.
    """
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    try:
        tg_call(token, "answerCallbackQuery", json=payload)
    except RuntimeError as exc:
        print(f"Info: konfirmasi tombol dilewati ({str(exc)[:120]})")


def chat_id_matches(value, configured):
    return str(value) == str(configured)


def score_post(post):
    """A transparent heuristic score for the approval UI; not an LLM judgment."""
    text = post["text"].strip()
    first = text.split("\n", 1)[0].strip()
    hook = 5
    low = text.lower()
    if len(first) <= 90:
        hook += 1
    if any(x in first for x in ("?", ":", "—", "–")):
        hook += 1
    if any(x in first.lower() for x in ("nggak", "cuma", "justru", "masalahnya", "ternyata", "bukan ")):
        hook += 1
    if first.endswith(".") and len(first) > 70:
        hook -= 1

    specificity = 5
    if any(c.isdigit() for c in text):
        specificity += 1
    if any(x in low for x in ("contoh", "client", "klien", "cv", "portfolio", "portofolio", "harga", "scope", "deadline", "royalti", "keyword")):
        specificity += 1
    if len(text) >= 180:
        specificity += 1

    boldness = 5
    if any(x in low for x in ("bukan", "justru", "masalahnya", "salah kaprah", "nggak", "cuma")):
        boldness += 2
    if "?" in text:
        boldness += 1

    aiish = 5
    generic = (
        "banyak orang", "di era digital", "yang perlu kamu pahami", "pada akhirnya",
        "semoga bermanfaat", "berikut beberapa", "kunci sukses"
    )
    if any(x in low for x in generic):
        aiish += 3
    if low.count("padahal") >= 2 or low.count("realita") >= 2:
        aiish += 1
    if text.count("\n") >= 2:
        aiish -= 1

    hook = max(1, min(10, hook))
    specificity = max(1, min(10, specificity))
    boldness = max(1, min(10, boldness))
    aiish = max(1, min(10, aiish))
    overall = round((hook * 0.35 + specificity * 0.30 + boldness * 0.25 + (11 - aiish) * 0.10) * 10)
    return overall, hook, specificity, boldness, aiish


def format_draft(post):
    overall, hook, specificity, boldness, aiish = score_post(post)
    text = post["text"]
    body = (
        f"🤖 <b>Draft Threads #{post['id']}</b>\n\n"
        f"{html.escape(text)}\n\n"
        f"────────────\n"
        f"Score: <b>{overall}/100</b>\n"
        f"Hook: {hook}/10  ·  Specificity: {specificity}/10\n"
        f"Boldness: {boldness}/10  ·  AI-ish: {aiish}/10\n\n"
        f"Pillar: {post.get('pillar', '-')}\n"
        f"Format: {post.get('format', '-')}"
    )
    if len(body) > MAX_TEXT:
        body = body[: MAX_TEXT - 30] + "\n\n[truncated]"
    return body


def send_draft(token, chat_id, post):
    result = tg_call(
        token,
        "sendMessage",
        json={
            "chat_id": chat_id,
            "text": format_draft(post),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "✅ Approve", "callback_data": f"approve:{post['id']}"},
                    {"text": "❌ Reject", "callback_data": f"reject:{post['id']}"},
                ]]
            },
            "disable_web_page_preview": True,
        },
    )
    return result["message_id"]


def get_offset():
    if not OFFSET_PATH.exists():
        return 0
    try:
        return int(json.loads(OFFSET_PATH.read_text(encoding="utf-8")).get("offset", 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return 0


def save_offset(offset):
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(json.dumps({"offset": offset}, indent=2) + "\n", encoding="utf-8")


def update_message(token, chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        tg_call(token, "editMessageText", json=payload)
    except RuntimeError as exc:
        print(f"Peringatan edit Telegram: {exc}")


def process_action(token, configured_chat_id, posts, action, post_id, message=None):
    try:
        post_id = int(post_id)
    except ValueError:
        return False
    item = next((p for p in posts if p.get("id") == post_id), None)
    if not item:
        return False

    if item.get("status") not in ("pending", "approved", "rejected", "posted"):
        return False

    status = item.get("status")
    if status == "posted":
        result_text = f"ℹ️ <b>Draft #{post_id} sudah diposting.</b>"
    elif action == "approve":
        if status == "approved":
            result_text = f"✅ <b>Draft #{post_id} sudah approved.</b>"
        elif status == "rejected":
            result_text = f"ℹ️ <b>Draft #{post_id} sudah rejected.</b>"
        else:
            item["status"] = "approved"
            item["approved_at"] = now_iso()
            item.pop("rejected_at", None)
            item.pop("rejection_reason", None)
            result_text = f"✅ <b>Draft #{post_id} approved.</b>\n\nPost akan masuk antrean Threads."
    elif action == "reject":
        if status == "rejected":
            result_text = f"❌ <b>Draft #{post_id} sudah rejected.</b>"
        elif status == "approved":
            result_text = f"ℹ️ <b>Draft #{post_id} sudah approved.</b>"
        else:
            item["status"] = "rejected"
            item["rejected_at"] = now_iso()
            result_text = f"❌ <b>Draft #{post_id} rejected.</b>"
    else:
        return False

    if message:
        update_message(token, configured_chat_id, message["message_id"], result_text)
    return True


def process_updates(token, chat_id, posts):
    offset = get_offset()
    updates = tg_call(
        token,
        "getUpdates",
        json={
            "offset": offset,
            "timeout": 5,
            "allowed_updates": ["callback_query", "message"],
        },
    )
    changed = False
    highest = offset

    for update in updates:
        highest = max(highest, update["update_id"] + 1)
        callback = update.get("callback_query")
        if callback:
            sender_chat = callback.get("message", {}).get("chat", {}).get("id")
            if not chat_id_matches(sender_chat, chat_id):
                safe_answer(token, callback["id"], "Unauthorized chat.")
                continue
            data = callback.get("data", "")
            if ":" in data:
                action, post_id = data.split(":", 1)
                if process_action(token, chat_id, posts, action, post_id, callback.get("message")):
                    changed = True
            safe_answer(token, callback["id"])
            continue

        message = update.get("message")
        if not message:
            continue
        sender_chat = message.get("chat", {}).get("id")
        if not chat_id_matches(sender_chat, chat_id):
            continue
        text = (message.get("text") or "").strip()
        parts = text.split()
        if len(parts) == 2 and parts[0].lower() in ("/approve", "/reject"):
            action = parts[0].lstrip("/").lower()
            if process_action(token, chat_id, posts, action, parts[1], message):
                changed = True

    # Offset TIDAK disimpan di sini. main() menyimpannya setelah posts.json aman,
    # supaya approval yang sudah diproses tidak hilang jika langkah berikutnya gagal.
    return changed, highest


def notify_pending(token, chat_id, posts):
    changed = False
    for post in posts:
        if post.get("status") != "pending" or post.get("telegram_message_id"):
            continue
        message_id = send_draft(token, chat_id, post)
        post["telegram_message_id"] = message_id
        post["telegram_notified_at"] = now_iso()
        save_posts(posts)  # simpan per draft agar tidak terkirim ganda jika run berikutnya gagal
        changed = True
        print(f"Telegram: mengirim draft #{post['id']} (message {message_id}).")
        time.sleep(1.2)  # batas Telegram: ~1 pesan/detik ke chat yang sama
    return changed


def main():
    token = require_env("TELEGRAM_BOT_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")
    posts = load_posts()

    offset_before = get_offset()
    changed, highest = process_updates(token, chat_id, posts)
    if changed:
        save_posts(posts)  # 1) simpan approval/reject dulu
    if highest != offset_before:
        save_offset(highest)  # 2) offset maju hanya setelah state tersimpan

    notify_pending(token, chat_id, posts)  # 3) kirim draft baru (menyimpan per draft)

    pending = sum(1 for p in posts if p.get("status") == "pending")
    approved = sum(1 for p in posts if p.get("status") == "approved")
    rejected = sum(1 for p in posts if p.get("status") == "rejected")
    print(f"Approval queue: pending={pending}, approved={approved}, rejected={rejected}")


if __name__ == "__main__":
    main()
