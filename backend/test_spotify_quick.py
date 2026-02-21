#!/usr/bin/env python3
"""
Quick test of the /songs/spotify/sync endpoint.

This demonstrates the full workflow with mock data, useful for testing
the endpoint without a real Spotify account.

Requirements:
  - Backend running on http://localhost:8000
  - For real testing: A valid Spotify OAuth access token
"""

import json
import urllib.request
import urllib.error
import sys


def test_sync_endpoint(user_id: str, access_token: str, limit: int = 50):
    """
    Test the Spotify sync endpoint.
    
    Args:
        user_id: Application user ID
        access_token: Spotify OAuth access token
        limit: Number of songs to fetch (1-50)
    """
    
    print("=" * 70)
    print("SPOTIFY SYNC ENDPOINT TEST")
    print("=" * 70)
    print()
    
    # Prepare request
    endpoint = "http://localhost:8000/songs/spotify/sync"
    body = {
        "user_id": user_id,
        "access_token": access_token,
        "limit": limit
    }
    
    print(f"📤 Sending request to {endpoint}")
    print()
    print("Request body:")
    print(f"  user_id: {user_id}")
    print(f"  access_token: {access_token[:20]}..." if len(access_token) > 20 else f"  access_token: {access_token}")
    print(f"  limit: {limit}")
    print()
    
    try:
        # Make request
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            print("=" * 70)
            print("✅ SUCCESS!")
            print("=" * 70)
            print()
            print("Response:")
            print(json.dumps(result, indent=2))
            print()
            print("Summary:")
            print(f"  📊 Total Processed: {result['total_processed']}")
            print(f"  ✨ New Songs Added: {result['songs_added']}")
            print(f"  🔗 Songs Merged: {result['songs_merged']}")
            print(f"  ❌ Failed: {result['failed_count']}")
            print()
            
            if result['added_tracks']:
                print(f"Added tracks ({len(result['added_tracks'])} total):")
                for track_id in result['added_tracks'][:5]:
                    print(f"  • {track_id}")
                if len(result['added_tracks']) > 5:
                    print(f"  ... and {len(result['added_tracks']) - 5} more")
                print()
            
            if result['merged_tracks']:
                print(f"Merged tracks ({len(result['merged_tracks'])} total):")
                for track_id in result['merged_tracks'][:5]:
                    print(f"  • {track_id}")
                if len(result['merged_tracks']) > 5:
                    print(f"  ... and {len(result['merged_tracks']) - 5} more")
                print()
            
            return True
    
    except urllib.error.HTTPError as e:
        print("=" * 70)
        print(f"❌ ERROR {e.code}")
        print("=" * 70)
        print()
        
        try:
            error_body = json.loads(e.read().decode('utf-8'))
            print(f"Detail: {error_body.get('detail', 'No details provided')}")
        except:
            print(f"Response: {e.read().decode('utf-8')}")
        
        return False
    
    except Exception as e:
        print("=" * 70)
        print("❌ UNEXPECTED ERROR")
        print("=" * 70)
        print()
        print(f"Error: {type(e).__name__}: {e}")
        return False


def main():
    """Main entry point."""
    
    print()
    print("🎵 Hacklytics Spotify Sync Demo")
    print()
    
    # Get inputs
    if len(sys.argv) < 3:
        print("Usage: python test_spotify_quick.py <user_id> <access_token> [limit]")
        print()
        print("Examples:")
        print("  python test_spotify_quick.py alice BQCabc...xyz 50")
        print("  python test_spotify_quick.py bob BQDef...uvw 25")
        print()
        print("To get an access token:")
        print("  1. Go to https://spotify.com/login")
        print("  2. Authorize the Hacklytics app")
        print("  3. Copy the access token from your browser/app")
        print()
        sys.exit(1)
    
    user_id = sys.argv[1]
    access_token = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    
    # Validate inputs
    if not user_id or not access_token:
        print("❌ Error: user_id and access_token are required")
        sys.exit(1)
    
    if limit < 1 or limit > 50:
        print("⚠️  Warning: limit must be 1-50, using 50")
        limit = 50
    
    # Run test
    success = test_sync_endpoint(user_id, access_token, limit)
    
    # Exit with status
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
