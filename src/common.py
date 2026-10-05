"""Fungsi bersama: load/save config & antrean, HTTP dengan retry."""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
POSTS_PATH = ROOT / "data" / "posts.json"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_posts():
    if not POSTS_PATH.exists():
        return []
    return json.loads(POSTS_PATH.read_text(encoding="utf-8"))


def save_posts(posts):
    POSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    POSTS_PATH.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"ERROR: environment variable {name} belum diset.")
    return value


def request_with_retry(method, url, *, retries=3, backoff=5, **kwargs):
    """HTTP request dengan retry untuk 429/5xx/network error.

    Pesan error sengaja tidak menyertakan URL agar token tidak bocor ke log.
    """
    import requests

    last = "unknown"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.request(method, url, timeout=60, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                last = f"HTTP {resp.status_code}"
            else:
                return resp
        except requests.RequestException as exc:
            last = type(exc).__name__
        if attempt < retries:
            time.sleep(backoff * attempt)
    raise RuntimeError(f"Request gagal setelah {retries} percobaan ({last}).")
