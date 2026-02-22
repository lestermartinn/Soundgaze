"""
Pydantic models for Spotify audio features and API request/response shapes.

Spotify's audio analysis API returns these 12 numeric features per track.
Reference: https://developer.spotify.com/documentation/web-api/reference/get-audio-features
"""

from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core audio feature vector (12-dimensional)
# ---------------------------------------------------------------------------

class AudioFeatures(BaseModel):
    """Raw Spotify audio features for a single track."""

    track_id: str = Field(..., description="Spotify track URI or ID")

    # Rhythm / energy
    tempo: float = Field(..., ge=0, description="BPM (0–250)")
    energy: float = Field(..., ge=0, le=1, description="Perceptual intensity (0–1)")
    loudness: float = Field(..., description="Overall loudness in dB (typically -60–0)")
    danceability: float = Field(..., ge=0, le=1, description="Rhythmic regularity (0–1)")

    # Mood / tonality
    valence: float = Field(..., ge=0, le=1, description="Musical positivity (0–1)")
    mode: int = Field(..., ge=0, le=1, description="0 = minor, 1 = major")
    key: int = Field(..., ge=0, le=11, description="Pitch class (0=C, 1=C#, …, 11=B)")

    # Structure / texture
    acousticness: float = Field(..., ge=0, le=1)
    instrumentalness: float = Field(..., ge=0, le=1)
    liveness: float = Field(..., ge=0, le=1, description="Audience presence probability")
    speechiness: float = Field(..., ge=0, le=1, description="Spoken-word proportion")

    # Duration
    duration_ms: int = Field(..., ge=0, description="Track length in milliseconds")

    def to_vector(self) -> List[float]:
        """Return features as an ordered float list for ML pipelines."""
        return [
            self.tempo / 250.0,          # normalize BPM to [0, 1]
            self.energy,
            (self.loudness + 60) / 60.0, # shift dB to [0, 1]
            self.danceability,
            self.valence,
            float(self.mode),
            self.key / 11.0,             # normalize key to [0, 1]
            self.acousticness,
            self.instrumentalness,
            self.liveness,
            self.speechiness,
            min(self.duration_ms / 600_000.0, 1.0),  # cap at 10 min
        ]


# ---------------------------------------------------------------------------
# UMAP embedding result
# ---------------------------------------------------------------------------

class EmbeddedPoint(BaseModel):
    """A single song mapped to 3-D space by UMAP."""

    track_id: str
    x: float
    y: float
    z: float
    # Optional metadata to surface in the frontend tooltip
    title: Optional[str] = None
    artist: Optional[str] = None
    country: Optional[str] = None


# ---------------------------------------------------------------------------
# Request / response shapes for recommendation endpoint
# ---------------------------------------------------------------------------

class RecommendRequest(BaseModel):
    song_id: str = Field(..., description="ID of the query song")
    top_k: int = Field(5, ge=1, le=50, description="Number of twins to return")


class RecommendResponse(BaseModel):
    query_id: str
    recommendations: List[str] = Field(
        ..., description="Ordered list of similar song IDs (nearest first)"
    )
    scores: List[float] = Field(
        ..., description="Cosine similarity scores (1 = identical, 0 = orthogonal)"
    )


class SongSampleItem(BaseModel):
    track_id: str
    name: Optional[str] = None
    artist: Optional[str] = None
    genre: Optional[str] = None
    user_id: Optional[str] = None
    user_ids: List[str] = Field(default_factory=list)


class SongPoolRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="Optional app user id to fetch personal songs")
    user_song_count: int = Field(100, ge=0, le=1000, description="Target personal songs when user_id is provided")
    total_count: int = Field(1000, ge=1, le=5000, description="Total points to return for visualization")


class SongPoolResponse(BaseModel):
    user_songs: List[SongSampleItem]
    global_songs: List[SongSampleItem]
    user_songs_returned: int
    global_songs_returned: int
    total_returned: int
    is_new_user: bool


class SongUpsertRequest(BaseModel):
    track_id: str = Field(..., description="Unique song ID")
    vector: List[float] = Field(..., min_length=11, max_length=11, description="11-D embedding vector")
    name: Optional[str] = None
    artist: Optional[str] = None
    genre: Optional[str] = None
    user_id: Optional[str] = None


class SongGetResponse(BaseModel):
    track_id: str
    vector: List[float]
    name: Optional[str] = None
    artist: Optional[str] = None
    genre: Optional[str] = None
    user_id: Optional[str] = None
    user_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Bulk embed request
# ---------------------------------------------------------------------------

class EmbedRequest(BaseModel):
    tracks: List[AudioFeatures]


class EmbedResponse(BaseModel):
    points: List[EmbeddedPoint]

# ---------------------------------------------------------------------------
# Spotify import endpoint
# ---------------------------------------------------------------------------

class SpotifyImportRequest(BaseModel):
    user_id: str = Field(..., description="App user ID to associate with synced songs")
    access_token: str = Field(..., description="Spotify OAuth access token from user's session")
    limit: int = Field(50, ge=1, le=50, description="Number of top songs to fetch (max 50)")


class SpotifySyncResponse(BaseModel):
    user_id: str
    songs_added: int = Field(..., description="Number of new songs added to database")
    songs_merged: int = Field(..., description="Number of existing songs where user was added")
    total_processed: int = Field(..., description="Total songs processed from Spotify")
    failed_count: int = Field(..., description="Number of songs that failed to process")
    added_tracks: List[str] = Field(default_factory=list, description="Track IDs of newly added songs")
    merged_tracks: List[str] = Field(default_factory=list, description="Track IDs where user was merged")


# -------------------------------------------------
# Similarity
# -------------------------------------------------
class SimilarSong(BaseModel):
    track_id: str
    score: float

class SimilarRequest(BaseModel):
    vector: list[float]
    k: int = 5  # default to 5 results

class SimilarResponse(BaseModel):
    results: list[SimilarSong]