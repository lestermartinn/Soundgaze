#!/usr/bin/env python3
"""Minimal backend smoke test for Hacklytics API.

Checks:
1) GET /health
2) POST /songs/pool
3) POST /songs/recommend using a sampled track_id

Usage:
  python backend/scripts/smoke_test_backend.py
  python backend/scripts/smoke_test_backend.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Hacklytics backend")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")

    print("[1/3] Checking /health ...")
    status, health = _request_json("GET", f"{base}/health")
    if status != 200 or health.get("status") != "ok":
        raise RuntimeError(f"/health failed: status={status}, body={health}")
    print(f"  OK -> {health}")

    print("[2/3] Checking /songs/pool ...")
    status, pool = _request_json(
        "POST",
        f"{base}/songs/pool",
        body={"user_song_count": 5, "total_count": 25},
        timeout=45,
    )
    if status != 200:
        raise RuntimeError(f"/songs/pool failed: status={status}")

    global_songs = pool.get("global_songs", [])
    user_songs = pool.get("user_songs", [])
    if not isinstance(global_songs, list) or not isinstance(user_songs, list):
        raise RuntimeError(f"/songs/pool malformed response: {pool}")
    if not global_songs:
        raise RuntimeError("/songs/pool returned no global songs; cannot continue smoke test")

    sample_song_id = global_songs[0].get("track_id")
    if not sample_song_id:
        raise RuntimeError(f"/songs/pool returned song without track_id: {global_songs[0]}")

    print(
        "  OK -> "
        f"user_songs_returned={pool.get('user_songs_returned')}, "
        f"global_songs_returned={pool.get('global_songs_returned')}, "
        f"sample_track_id={sample_song_id}"
    )

    print("[3/3] Checking /songs/recommend ...")
    status, rec = _request_json(
        "POST",
        f"{base}/songs/recommend",
        body={"song_id": sample_song_id, "top_k": 5},
    )
    if status != 200:
        raise RuntimeError(f"/songs/recommend failed: status={status}")

    recommendations = rec.get("recommendations", [])
    scores = rec.get("scores", [])
    if not recommendations or not scores:
        raise RuntimeError(f"/songs/recommend returned empty lists: {rec}")

    print(
        "  OK -> "
        f"query_id={rec.get('query_id')}, "
        f"n_recommendations={len(recommendations)}, "
        f"top_score={scores[0]}"
    )

    print("\nPASS: backend smoke test completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nFAIL: {exc}")
        raise SystemExit(1)
