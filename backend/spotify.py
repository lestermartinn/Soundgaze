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

try:
    import spotipy
    from spotipy import SpotifyClientCredentials
except ImportError:
    raise ImportError(
        "Missing 'spotipy' package. Install via: pip install spotipy>=2.23.0"
    )

logger = logging.getLogger(__name__)


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
        """
        Fetch user's top 50 tracks from Spotify.
        
        NOTE: This is synchronous (spotipy doesn't support async).
        Call via asyncio.to_thread() in async context.

        Args:
            limit: Number of tracks to fetch (max 50 per request)

        Returns:
            List of track dictionaries containing: track_id, name, artist, audio features
        """
        try:
            # Fetch top tracks (short_term = last 4 weeks, medium_term = 6 months, all_time = all_time)
            results = self.sp.current_user_top_tracks(limit=limit, time_range="medium_term")
            
            tracks = []
            for item in results.get("items", []):
                track_id = item["id"]
                name = item["name"]
                artists = ", ".join([a["name"] for a in item.get("artists", [])])
                
                # Fetch audio features for this track
                audio_features = self.sp.audio_features(track_id)[0]
                if audio_features is None:
                    self.logger.warning(f"Skipped {track_id} (no audio features)")
                    continue
                
                tracks.append({
                    "track_id": track_id,
                    "name": name,
                    "artist": artists,
                    "audio_features": audio_features,
                })
            
            self.logger.info(f"Fetched {len(tracks)} top tracks from Spotify")
            return tracks
            
        except spotipy.exceptions.SpotifyException as e:
            self.logger.error(f"Spotify API error: {e}")
            raise RuntimeError(f"Failed to fetch Spotify top tracks: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error fetching Spotify tracks: {e}")
            raise RuntimeError(f"Unexpected error: {e}")

    @staticmethod
    def audio_features_to_vector(audio_features: dict) -> List[float]:
        """
        Convert Spotify audio features to our 11-D vector format.

        Matches the normalization in models.AudioFeatures.to_vector()

        Args:
            audio_features: Dict from Spotify audio features endpoint

        Returns:
            11-element normalized float vector
        """
        tempo = float(audio_features.get("tempo", 120))
        energy = float(audio_features.get("energy", 0.5))
        loudness = float(audio_features.get("loudness", -5))
        danceability = float(audio_features.get("danceability", 0.5))
        valence = float(audio_features.get("valence", 0.5))
        mode = int(audio_features.get("mode", 1))
        key = int(audio_features.get("key", 0))
        acousticness = float(audio_features.get("acousticness", 0.5))
        instrumentalness = float(audio_features.get("instrumentalness", 0.0))
        liveness = float(audio_features.get("liveness", 0.5))
        speechiness = float(audio_features.get("speechiness", 0.0))

        # Normalize to [0, 1] range (must match models.AudioFeatures.to_vector() exactly)
        # NOTE: Returns exactly 11 dimensions (matches DB schema)
        vector = [
            min(tempo / 250.0, 1.0),                    # normalize BPM to [0, 1]
            energy,                                      # already [0, 1]
            min((loudness + 60) / 60.0, 1.0),           # shift dB to [0, 1]
            danceability,                                # already [0, 1]
            valence,                                     # already [0, 1]
            float(mode),                                 # 0 or 1
            min(key / 11.0, 1.0),                        # normalize key to [0, 1]
            acousticness,                                # already [0, 1]
            instrumentalness,                            # already [0, 1]
            liveness,                                    # already [0, 1]
            speechiness,                                 # already [0, 1]
        ]

        if len(vector) != 11:
            raise ValueError(f"Vector has {len(vector)} dimensions, expected 11")

        return vector

    async def get_tracks_with_vectors(self, limit: int = 50) -> List[Dict]:
        """
        Fetch user's top tracks and convert to database-ready format.
        
        Runs the synchronous Spotify API calls in a thread pool to avoid blocking.
        
        Note: Uses loop.run_in_executor() for Python 3.8 compatibility
              (asyncio.to_thread added in Python 3.9)

        Returns:
            List of dicts with: track_id, name, artist, vector (11-D)
        """
        # Run the synchronous Spotify API call in a thread pool
        # Using run_in_executor for Python 3.8 compatibility
        loop = asyncio.get_event_loop()
        tracks = await loop.run_in_executor(None, self.fetch_user_top_tracks, limit)
        
        for track in tracks:
            audio_features = track.pop("audio_features")
            vector = self.audio_features_to_vector(audio_features)
            track["vector"] = vector
        
        return tracks
