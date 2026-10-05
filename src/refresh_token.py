"""Refresh long-lived token Threads, lalu simpan ke GitHub Secret THREADS_ACCESS_TOKEN."""
import os
import subprocess
import sys

from common import request_with_retry, require_env

REFRESH_URL = "https://graph.threads.net/refresh_access_token"


def main():
    token = require_env("THREADS_ACCESS_TOKEN")
    repo = require_env("GITHUB_REPOSITORY")
    require_env("GH_TOKEN")  # PAT yang boleh menulis secret (dari secrets.GH_PAT)

    resp = request_with_retry(
        "GET",
        REFRESH_URL,
        params={"grant_type": "th_refresh_token", "access_token": token},
    )
    if not resp.ok:
        try:
            msg = resp.json().get("error", {}).get("message", resp.text[:200])
        except ValueError:
            msg = resp.text[:200]
        sys.exit(f"ERROR: refresh gagal (HTTP {resp.status_code}): {msg}")

    data = resp.json()
    new_token = data["access_token"]
    days = int(data.get("expires_in", 0)) // 86400

    # Token dikirim lewat stdin supaya tidak muncul di argumen/log.
    subprocess.run(
        ["gh", "secret", "set", "THREADS_ACCESS_TOKEN", "--repo", repo],
        input=new_token,
        text=True,
        check=True,
        env=os.environ.copy(),
    )
    print(f"Token berhasil di-refresh dan disimpan. Masa berlaku baru: ~{days} hari.")


if __name__ == "__main__":
    main()
