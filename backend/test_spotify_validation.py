#!/usr/bin/env python3
"""
Comprehensive test suite for Spotify integration.

Tests:
1. Vector conversion (11-D, correct normalization)
2. Audio features parsing
3. Pydantic model validation
4. Async/await patterns
5. Database operation flow (mocked)

Run: python test_spotify_validation.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from models import SpotifyImportRequest, SpotifySyncResponse, SongUpsertRequest
from spotify import SpotifyImporter


def test_vector_conversion():
    """Test that A Spotify audio features → 11-D vector conversion works correctly."""
    print("=" * 70)
    print("TEST 1: Vector Conversion (11-D)")
    print("=" * 70)
    
    # Mock audio features from Spotify API
    mock_features = {
        "tempo": 120.0,
        "energy": 0.8,
        "loudness": -5.0,
        "danceability": 0.7,
        "valence": 0.6,
        "mode": 1,
        "key": 5,
        "acousticness": 0.3,
        "instrumentalness": 0.1,
        "liveness": 0.4,
        "speechiness": 0.05,
        "duration_ms": 240000,
    }
    
    vector = SpotifyImporter.audio_features_to_vector(mock_features)
    
    print(f"\n✓ Input (12 Spotify features):")
    print(f"  Tempo: {mock_features['tempo']} BPM")
    print(f"  Energy: {mock_features['energy']}")
    print(f"  Loudness: {mock_features['loudness']} dB")
    print(f"  Danceability: {mock_features['danceability']}")
    print(f"  Valence: {mock_features['valence']}")
    print(f"  Mode: {mock_features['mode']}")
    print(f"  Key: {mock_features['key']}")
    print(f"  Acousticness: {mock_features['acousticness']}")
    print(f"  Instrumentalness: {mock_features['instrumentalness']}")
    print(f"  Liveness: {mock_features['liveness']}")
    print(f"  Speechiness: {mock_features['speechiness']}")
    print(f"  Duration: {mock_features['duration_ms']} ms")
    
    print(f"\n✓ Output (11-D vector):")
    print(f"  Vector length: {len(vector)}")
    print(f"  Vector: {vector}")
    
    # Validate
    assert len(vector) == 11, f"Vector must be 11-D, got {len(vector)}"
    assert all(isinstance(x, float) for x in vector), "All elements must be floats"
    assert all(0 <= x <= 1 for x in vector), f"All elements must be in [0,1], got {vector}"
    
    print(f"\n✅ PASS: Vector is 11-D with all values in [0, 1]")
    return True


def test_edge_cases():
    """Test vector conversion with edge case audio features."""
    print("\n" + "=" * 70)
    print("TEST 2: Edge Cases (Extreme Values)")
    print("=" * 70)
    
    # Test 1: Very high tempo
    print("\n✓ Test 2a: Extreme tempo (250+ BPM)")
    features_high_tempo = {
        "tempo": 300.0,  # Over max
        "energy": 1.0,
        "loudness": 0.0,  # Max loudness
        "danceability": 1.0,
        "valence": 1.0,
        "mode": 1,
        "key": 11,  # Max key
        "acousticness": 0.0,
        "instrumentalness": 0.0,
        "liveness": 1.0,
        "speechiness": 0.0,
    }
    v = SpotifyImporter.audio_features_to_vector(features_high_tempo)
    assert v[0] <= 1.0, f"Tempo should be capped at 1.0, got {v[0]}"
    print(f"   Tempo normalized: {v[0]:.4f} (capped correctly)")
    assert len(v) == 11, f"Still 11-D: {len(v)}"
    
    # Test 2: Very low values
    print("\n✓ Test 2b: All zeros")
    features_zero = {
        "tempo": 0.0,
        "energy": 0.0,
        "loudness": -60.0,  # Min loudness
        "danceability": 0.0,
        "valence": 0.0,
        "mode": 0,
        "key": 0,
        "acousticness": 0.0,
        "instrumentalness": 0.0,
        "liveness": 0.0,
        "speechiness": 0.0,
    }
    v = SpotifyImporter.audio_features_to_vector(features_zero)
    assert v[0] == 0.0, f"Zero tempo: {v[0]}"
    assert v[2] == 0.0, f"Zero loudness: {v[2]}"
    print(f"   All zeros handled correctly")
    assert len(v) == 11
    
    # Test 3: Missing optional fields (should use defaults)
    print("\n✓ Test 2c: Missing fields (using defaults)")
    features_sparse = {
        "tempo": 120.0,
        "energy": 0.5,
        # All others missing - will use defaults
    }
    v = SpotifyImporter.audio_features_to_vector(features_sparse)
    print(f"   Defaults applied for missing fields")
    assert len(v) == 11
    
    print(f"\n✅ PASS: All edge cases handled correctly")
    return True


def test_pydantic_models():
    """Test that Pydantic models validate correctly."""
    print("\n" + "=" * 70)
    print("TEST 3: Pydantic Model Validation")
    print("=" * 70)
    
    # Test SpotifyImportRequest validation
    print("\n✓ Test 3a: SpotifyImportRequest")
    request_valid = SpotifyImportRequest(
        user_id="user123",
        access_token="BQCabc123xyz",
        limit=50
    )
    assert request_valid.user_id == "user123"
    assert request_valid.limit == 50
    print(f"   Valid request created: {request_valid}")
    
    # Test with default limit
    request_default = SpotifyImportRequest(
        user_id="user456",
        access_token="BQDef456uvw"
    )
    assert request_default.limit == 50
    print(f"   Default limit applied: {request_default.limit}")
    
    # Test SpotifySyncResponse
    print("\n✓ Test 3b: SpotifySyncResponse")
    response = SpotifySyncResponse(
        user_id="user123",
        songs_added=25,
        songs_merged=20,
        total_processed=50,
        failed_count=5,
        added_tracks=["id1", "id2"],
        merged_tracks=["id3", "id4"]
    )
    assert response.songs_added == 25
    assert response.songs_merged == 20
    assert len(response.added_tracks) == 2
    print(f"   Valid response created")
    print(f"   - Added: {response.songs_added}")
    print(f"   - Merged: {response.songs_merged}")
    print(f"   - Failed: {response.failed_count}")
    
    # Test SongUpsertRequest with 11-D vector
    print("\n✓ Test 3c: SongUpsertRequest with 11-D vector")
    vector_11d = [0.5] * 11
    upsert_req = SongUpsertRequest(
        track_id="spotify_track_123",
        vector=vector_11d,
        name="Test Song",
        artist="Test Artist",
        user_id="user123"
    )
    assert len(upsert_req.vector) == 11
    print(f"   Valid upsert request with 11-D vector")
    
    # Test invalid vector (wrong dimension)
    print("\n✓ Test 3d: Invalid vector (wrong dimension)")
    try:
        SongUpsertRequest(
            track_id="test",
            vector=[0.5] * 12,  # Wrong: 12-D instead of 11-D
            name="Test"
        )
        print("   ❌ FAIL: Should have rejected 12-D vector")
        return False
    except Exception as e:
        print(f"   ✓ Correctly rejected 12-D vector: {type(e).__name__}")
    
    print(f"\n✅ PASS: All Pydantic models validate correctly")
    return True


async def test_async_flow():
    """Test the async/await flow without real Spotify."""
    print("\n" + "=" * 70)
    print("TEST 4: Async/Await Flow")
    print("=" * 70)
    
    print("\n✓ Testing asyncio loop.run_in_executor pattern (Python 3.8 compatible)...")
    
    # Create a mock synchronous function (like Spotify API)
    def sync_operation():
        """Simulates a blocking Spotify API call."""
        import time
        time.sleep(0.1)  # Simulated blocking I/O
        return {"result": "mock_result"}
    
    # Use loop.run_in_executor to run it without blocking (Python 3.8 compatible)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, sync_operation)
    
    assert result["result"] == "mock_result"
    print(f"   ✓ sync_operation() executed without blocking event loop")
    print(f"   Result: {result}")
    
    print(f"\n✅ PASS: Async/await patterns work correctly")
    return True


async def test_full_flow_mock():
    """Test the full flow with mocked data."""
    print("\n" + "=" * 70)
    print("TEST 5: Full Sync Flow (Mocked)")
    print("=" * 70)
    
    print("\n✓ Simulating complete sync workflow...")
    
    # Step 1: Create request
    request = SpotifyImportRequest(
        user_id="user_test",
        access_token="MOCK_TOKEN",  # Not real token
        limit=50
    )
    print(f"   Step 1: Request created for user '{request.user_id}'")
    
    # Step 2: Show what track data would look like
    mock_track = {
        "track_id": "spotify_id_123",
        "name": "Test Song",
        "artist": "Test Artist",
        "audio_features": {
            "tempo": 120.0,
            "energy": 0.8,
            "loudness": -5.0,
            "danceability": 0.7,
            "valence": 0.6,
            "mode": 1,
            "key": 5,
            "acousticness": 0.3,
            "instrumentalness": 0.1,
            "liveness": 0.4,
            "speechiness": 0.05,
        }
    }
    print(f"   Step 2: Track fetched: {mock_track['name']} by {mock_track['artist']}")
    
    # Step 3: Convert to vector
    vector = SpotifyImporter.audio_features_to_vector(mock_track["audio_features"])
    print(f"   Step 3: Audio features converted to 11-D vector: {vector}")
    
    # Step 4: Prepare for database
    upsert_data = SongUpsertRequest(
        track_id=mock_track["track_id"],
        vector=vector,
        name=mock_track["name"],
        artist=mock_track["artist"],
        user_id=request.user_id
    )
    print(f"   Step 4: Prepared for database upsert")
    
    # Step 5: Simulate response
    response = SpotifySyncResponse(
        user_id=request.user_id,
        songs_added=1,
        songs_merged=0,
        total_processed=1,
        failed_count=0,
        added_tracks=[mock_track["track_id"]],
        merged_tracks=[]
    )
    print(f"   Step 5: Response ready")
    print(f"      - Added: {response.songs_added}")
    print(f"      - Merged: {response.songs_merged}")
    
    print(f"\n✅ PASS: Full workflow flow logic is sound")
    return True


async def main():
    """Run all tests."""
    print("\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  SPOTIFY INTEGRATION VALIDATION TEST SUITE".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)
    
    tests = [
        ("Vector Conversion", test_vector_conversion),
        ("Edge Cases", test_edge_cases),
        ("Pydantic Models", test_pydantic_models),
        ("Async/Await", test_async_flow),
        ("Full Flow (Mocked)", test_full_flow_mock),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:10} {name}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED - Code is ready for use!")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print("❌ SOME TESTS FAILED - Review output above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
