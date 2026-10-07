"""Posting satu item 'approved' berikutnya dari antrean ke Threads."""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from textfmt import reflow, strict_rules
from common import (
    approval_settings,
    load_config,
    load_posts,
    now_iso,
    request_with_retry,
    require_env,
    save_posts,
)

GRAPH = "https://graph.threads.net/v1.0"
MAX_ATTEMPTS = 3


def api_error(resp):
    try:
        err = resp.json().get("error", {})
        return f"HTTP {resp.status_code}: {err.get('message', resp.text[:200])}"
    except ValueError:
        return f"HTTP {resp.status_code}: {resp.text[:200]}"


def publish(text, user_id, token, delay):
    create = request_with_retry(
        "POST",
        f"{GRAPH}/{user_id}/threads",
        data={"media_type": "TEXT", "text": text, "access_token": token},
    )
    if not create.ok:
        raise RuntimeError(f"Gagal membuat container: {api_error(create)}")
    creation_id = create.json()["id"]

    time.sleep(delay)

    pub = request_with_retry(
        "POST",
        f"{GRAPH}/{user_id}/threads_publish",
        data={"creation_id": creation_id, "access_token": token},
    )
    if not pub.ok:
        raise RuntimeError(f"Gagal publish: {api_error(pub)}")
    return pub.json()["id"]


def parse_iso(value):
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_eligible(item, now, mode, window_minutes):
    """Draft boleh diposting jika:
    - status 'approved' (kamu menekan Approve), atau
    - mode veto: status 'pending', SUDAH terkirim ke Telegram, dan jendela veto sudah lewat.
    Draft yang belum pernah terkirim ke Telegram tidak pernah auto-post (fail-safe)."""
    status = item.get("status")
    if status == "approved":
        return True
    if status == "pending" and mode == "veto":
        if item.get("needs_review"):
            return False  # verifikasi fakta otomatis gagal: wajib Approve manual
        notified = parse_iso(item.get("telegram_notified_at"))
        if notified is None:
            return False
        return now - notified >= timedelta(minutes=window_minutes)
    return False


def main():
    dry_run = "--dry-run" in sys.argv or os.environ.get("DRY_RUN") == "1"
    cfg = load_config()
    posts = load_posts()

    today = now_iso()[:10]
    posted_today = sum(
        1 for p in posts if p["status"] == "posted" and p.get("posted_at", "").startswith(today)
    )
    if posted_today >= cfg["max_posts_per_day"]:
        print(f"Batas harian tercapai ({posted_today}/{cfg['max_posts_per_day']}). Lewati.")
        return

    mode, window = approval_settings(cfg)
    now = datetime.now(timezone.utc)
    queue = sorted((p for p in posts if is_eligible(p, now, mode, window)), key=lambda p: p["id"])
    if not queue:
        waiting = sum(1 for p in posts if p["status"] == "pending" and p.get("telegram_notified_at"))
        unsent = sum(1 for p in posts if p["status"] == "pending" and not p.get("telegram_notified_at"))
        print(f"Tidak ada draft yang siap diposting (mode={mode}, jendela veto={window} menit).")
        print(f"Pending menunggu jendela veto: {waiting}; pending belum terkirim ke Telegram: {unsent}.")
        return

    item = queue[0]
    # Pengaman terakhir: draft lama yang berupa satu paragraf panjang dirapikan menjadi blok pendek.
    formatted = reflow(item["text"], strict_rules(cfg))
    if formatted != item["text"]:
        print("Teks dirapikan menjadi blok pendek sebelum diposting.")
        item["text"] = formatted
    text = item["text"]
    auto = item["status"] == "pending"
    print(f"Postingan #{item['id']} ({item.get('pillar')}/{item.get('format')}/{item.get('style')})"
          + (" [auto-approve: tidak ada veto]" if auto else " [approved manual]") + ":")
    print(text)

    if len(text) > 500:
        item["status"] = "failed"
        item["last_error"] = "Teks melebihi 500 karakter"
        save_posts(posts)
        sys.exit("ERROR: teks melebihi batas 500 karakter Threads.")

    if dry_run:
        print("\n[DRY RUN] Tidak benar-benar diposting.")
        return

    user_id = require_env("THREADS_USER_ID")
    token = require_env("THREADS_ACCESS_TOKEN")

    try:
        post_id = publish(text, user_id, token, cfg["publish_delay_seconds"])
    except (RuntimeError, KeyError) as exc:
        item["attempts"] = item.get("attempts", 0) + 1
        item["last_error"] = str(exc)
        if item["attempts"] >= MAX_ATTEMPTS:
            item["status"] = "failed"
        save_posts(posts)
        sys.exit(f"ERROR: {exc} (percobaan {item['attempts']}/{MAX_ATTEMPTS})")

    if auto:
        item["auto_approved_at"] = now_iso()
    item["status"] = "posted"
    item["posted_at"] = now_iso()
    item["threads_post_id"] = post_id
    item.pop("last_error", None)
    save_posts(posts)
    print(f"Berhasil diposting. Threads post id: {post_id}")


if __name__ == "__main__":
    main()
