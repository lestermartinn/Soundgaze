#!/usr/bin/env python3
"""Critical endpoint test for user-song ownership + pool behavior.

Validates:
1) Insert a new song for user A
2) Re-upload same song for user B (must merge ownership, not overwrite)
3) Fetch song and assert both user IDs are present
4) Query pool for each user and verify a user song + random/global song are returned
5) Verify new user fallback still returns random songs

Usage:
  python backend/scripts/critical_endpoint_test.py
  python backend/scripts/critical_endpoint_test.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import random
import string
import urllib.error
import urllib.request


def _request_json(method: str, url: str, body: dict | None = None, timeout: int = 20) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, json.loads(payload)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {method} {url}: {payload}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error for {method} {url}: {exc}") from exc


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _rand_suffix(n: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def main() -> int:
    parser = argparse.ArgumentParser(description="Critical endpoint test for Hacklytics backend")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")

    print("[1/8] health check")
    status, health = _request_json("GET", f"{base}/health")
    _assert(status == 200 and health.get("status") == "ok", f"/health failed: {status}, {health}")

    track_id = f"critical_track_{_rand_suffix()}"
    user_a = f"user_a_{_rand_suffix(6)}"
    user_b = f"user_b_{_rand_suffix(6)}"
    vector = [0.11, 0.22, 0.33, 0.44, 0.55, 0.66, 0.77, 0.88, 0.99, 0.12, 0.23]

    print("[2/8] insert new song for user A")
    status, created = _request_json(
        "POST",
        f"{base}/songs",
        body={
            "track_id": track_id,
            "vector": vector,
            "name": "Critical Test Song",
            "artist": "Copilot",
            "genre": "test",
            "user_id": user_a,
        },
    )
    _assert(status == 200, f"POST /songs failed: {status}")
    _assert(created.get("track_id") == track_id, f"Unexpected track on create: {created}")
    _assert(user_a in (created.get("user_ids") or []), f"user A missing after create: {created}")

    print("[3/8] upload same song for user B (must merge user ownership)")
    status, updated = _request_json(
        "POST",
        f"{base}/songs",
        body={
            "track_id": track_id,
            "vector": vector,
            "name": "Critical Test Song",
            "artist": "Copilot",
            "genre": "test",
            "user_id": user_b,
        },
    )
    _assert(status == 200, f"POST /songs (merge) failed: {status}")
    user_ids_after_update = set(updated.get("user_ids") or [])
    _assert(user_a in user_ids_after_update and user_b in user_ids_after_update, f"Ownership not merged correctly: {updated}")

    print("[4/8] fetch song and verify merged user IDs")
    status, fetched = _request_json("GET", f"{base}/songs/{track_id}")
    _assert(status == 200, f"GET /songs/{{id}} failed: {status}")
    fetched_user_ids = set(fetched.get("user_ids") or [])
    _assert(user_a in fetched_user_ids and user_b in fetched_user_ids, f"Merged user IDs missing in fetch: {fetched}")
    _assert(len(fetched.get("vector") or []) == 11, f"Vector length mismatch: {fetched}")

    print("[5/8] pool for user A: expect >=1 user song and >=1 global/random song")
    status, pool_a = _request_json(
        "POST",
        f"{base}/songs/pool",
        body={"user_id": user_a, "user_song_count": 1, "total_count": 2},
        timeout=45,
    )
    _assert(status == 200, f"POST /songs/pool user A failed: {status}")
    _assert(pool_a.get("user_songs_returned", 0) >= 1, f"Expected user songs for A: {pool_a}")
    _assert(pool_a.get("global_songs_returned", 0) >= 1, f"Expected global/random songs for A: {pool_a}")

    print("[6/8] pool for user B: expect >=1 user song and >=1 global/random song")
    status, pool_b = _request_json(
        "POST",
        f"{base}/songs/pool",
        body={"user_id": user_b, "user_song_count": 1, "total_count": 2},
        timeout=45,
    )
    _assert(status == 200, f"POST /songs/pool user B failed: {status}")
    _assert(pool_b.get("user_songs_returned", 0) >= 1, f"Expected user songs for B: {pool_b}")
    _assert(pool_b.get("global_songs_returned", 0) >= 1, f"Expected global/random songs for B: {pool_b}")

    print("[7/8] pool for unseen user: expect new-user fallback")
    status, pool_new = _request_json(
        "POST",
        f"{base}/songs/pool",
        body={"user_id": f"unseen_{_rand_suffix(6)}", "user_song_count": 1, "total_count": 2},
        timeout=45,
    )
    _assert(status == 200, f"POST /songs/pool unseen user failed: {status}")
    _assert(pool_new.get("is_new_user") is True, f"Expected is_new_user=True: {pool_new}")
    _assert(pool_new.get("global_songs_returned", 0) >= 1, f"Expected fallback random songs: {pool_new}")

    print("[8/8] recommend endpoint on uploaded track")
    status, rec = _request_json("POST", f"{base}/songs/recommend", body={"song_id": track_id, "top_k": 3})
    _assert(status == 200, f"POST /songs/recommend failed: {status}")
    _assert(len(rec.get("recommendations") or []) >= 1, f"Expected recommendations: {rec}")

    print("\nPASS: critical endpoint test passed.")
    print(f"Track tested: {track_id}")
    print(f"Merged users: {user_a}, {user_b}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nFAIL: {exc}")
        raise SystemExit(1)
