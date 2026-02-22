"""
Spotify API integration module.

Handles OAuth token authentication and fetches user's top tracks with audio features
from the Spotify Web API. Converts Spotify audio features into the 11-D vector format
used by our vector database.

Requires a valid Spotify access token (from OAuth flow).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, List, Dict
import httpx

try:
    import spotipy
    from spotipy import SpotifyClientCredentials
except ImportError:
    raise ImportError(
        "Missing 'spotipy' package. Install via: pip install spotipy>=2.23.0"
    )

logger = logging.getLogger(__name__)


async def fetch_reccobeats_audio_features(track_ids: list[str]) -> list[dict | None]:
    """Fetch audio features from ReccoBeats in small batches of 5."""
    results = []
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(0, len(track_ids), 5):
            chunk = track_ids[i:i + 5]
            ids_param = ",".join(chunk)
            url = f"https://api.reccobeats.com/v1/audio-features?ids={ids_param}"
            
            try:
                r = await client.get(url)
                print(f"ReccoBeats status: {r.status_code}, response: {r.text[:200]}")
                r.raise_for_status()
                data = r.json()
                chunk_results = data.get("content", [None] * len(chunk))
                results.extend(chunk_results)
            except Exception as e:
                logger.warning(f"ReccoBeats chunk failed: {e}")
                results.extend([None] * len(chunk))
    
    return results


class SpotifyImporter:
    """Handles Spotify API calls with user's access token."""

    def __init__(self, access_token: str):
        """
        Initialize with user's access token from Spotify OAuth.

        Args:
            access_token: User's Spotify OAuth access token (not client credentials)
        """
        self.access_token = access_token
        self.sp = spotipy.Spotify(auth=access_token)
        self.logger = logger

    def fetch_user_top_tracks(self, limit: int = 50) -> List[Dict]:
        """Fetch user's recently played tracks from Spotify."""
        results = self.sp.current_user_recently_played(limit=limit)
        items = results.get("items", [])

        # recently_played returns items with a nested "track" object
        tracks = []
        seen_ids = set()
        for item in items:
            track = item.get("track", {})
            track_id = track.get("id")
            if not track_id or track_id in seen_ids:
                continue
            seen_ids.add(track_id)
            tracks.append({
                "track_id": track_id,
                "name": track.get("name"),
                "artist": ", ".join([a["name"] for a in track.get("artists", [])]),
            })

        return tracks

    @staticmethod
    def audio_features_to_vector(audio_features: dict) -> List[float]:
        """
        Convert Spotify audio features to our 8-D vector format.

        Matches the normalization in ingest.py _FEATURE_COLS order:
        [danceability, energy, loudness, speechiness, instrumentalness, liveness, valence, tempo]

        Args:
            audio_features: Dict from Spotify/ReccoBeats audio features endpoint

        Returns:
            8-element normalized float vector
        """
        danceability     = float(audio_features.get("danceability", 0.5))
        energy           = float(audio_features.get("energy", 0.5))
        loudness         = float(audio_features.get("loudness", -5))
        speechiness      = float(audio_features.get("speechiness", 0.0))
        instrumentalness = float(audio_features.get("instrumentalness", 0.0))
        liveness         = float(audio_features.get("liveness", 0.5))
        valence          = float(audio_features.get("valence", 0.5))
        tempo            = float(audio_features.get("tempo", 120))

        # Normalize to [0, 1] range (must match ingest.py _scale_features() exactly)
        # NOTE: Returns exactly 8 dimensions (matches DB schema)
        vector = [
            danceability,                        # already [0, 1]
            energy,                              # already [0, 1]
            min((loudness + 60) / 60.0, 1.0),   # shift dB to [0, 1]
            speechiness,                         # already [0, 1]
            instrumentalness,                    # already [0, 1]
            liveness,                            # already [0, 1]
            valence,                             # already [0, 1]
            min(tempo / 250.0, 1.0),             # normalize BPM to [0, 1]
        ]

        if len(vector) != 8:
            raise ValueError(f"Vector has {len(vector)} dimensions, expected 8")

        return vector

    async def get_tracks_with_vectors(self, limit: int = 50) -> List[Dict]:
        """
        Fetch user's top tracks and convert to database-ready format.

        1. Fetches top tracks from Spotify (name, artist, track_id)
        2. Fetches audio features from ReccoBeats using Spotify track IDs
        3. Converts audio features to 11-D vectors

        Returns:
            List of dicts with: track_id, name, artist, vector (11-D)
        """
        # Run the synchronous Spotify API call in a thread pool
        loop = asyncio.get_event_loop()
        tracks = await loop.run_in_executor(None, self.fetch_user_top_tracks, limit)

        if not tracks:
            return []

        # Fetch audio features from ReccoBeats for all tracks at once
        track_ids = [t["track_id"] for t in tracks]
        audio_features_list = await fetch_reccobeats_audio_features(track_ids)

        result = []
        for track, audio_features in zip(tracks, audio_features_list):
            if audio_features is None:
                self.logger.warning(f"Skipped {track['track_id']} (no audio features from ReccoBeats)")
                continue
            try:
                vector = self.audio_features_to_vector(audio_features)
                result.append({
                    "track_id": track["track_id"],
                    "name": track["name"],
                    "artist": track["artist"],
                    "vector": vector,
                })
            except Exception as e:
                self.logger.warning(f"Failed to build vector for {track['track_id']}: {e}")
                continue

        return result
    
    def fetch_user_top_tracks_by_popularity(self, limit: int = 50, time_range: str = "medium_term") -> List[Dict]:
        results = self.sp.current_user_top_tracks(limit=limit, time_range=time_range)
        items = results.get("items", [])

        tracks = []
        for i, track in enumerate(items):
            track_id = track.get("id")
            if not track_id:
                continue
            tracks.append({
                "track_id": track_id,
                "name":     track.get("name"),
                "artist":   ", ".join([a["name"] for a in track.get("artists", [])]),
                "rank":     i + 1,
            })

        return tracks

    async def get_top_tracks_with_vectors(self, limit: int = 50, time_range: str = "medium_term") -> List[Dict]:
        loop = asyncio.get_event_loop()
        tracks = await loop.run_in_executor(None, self.fetch_user_top_tracks_by_popularity, limit, time_range)

        if not tracks:
            return []

        track_ids = [t["track_id"] for t in tracks]
        audio_features_list = await fetch_reccobeats_audio_features(track_ids)

        result = []
        for track, audio_features in zip(tracks, audio_features_list):
            if audio_features is None:
                self.logger.warning(f"Skipped {track['track_id']} (no audio features from ReccoBeats)")
                continue
            try:
                vector = self.audio_features_to_vector(audio_features)
                result.append({
                    "track_id": track["track_id"],
                    "name":     track["name"],
                    "artist":   track["artist"],
                    "rank":     track["rank"],
                    "vector":   vector,
                })
            except Exception as e:
                self.logger.warning(f"Failed to build vector for {track['track_id']}: {e}")
                continue

        return result
    
    