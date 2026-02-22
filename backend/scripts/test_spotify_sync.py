#!/usr/bin/env python3
"""
Test script for Spotify sync endpoint.

Usage:
  python test_spotify_sync.py <user_id> <access_token>

Requirements:
  - Backend running on http://localhost:8000
  - Valid Spotify OAuth access token from user's session
"""

import json
import sys
import urllib.request
import urllib.error


def test_spotify_sync(user_id: str, access_token: str, limit: int = 50):
    """Test the /songs/spotify/sync endpoint."""
    
    endpoint = "http://localhost:8000/songs/spotify/sync"
    
    request_body = {
        "user_id": user_id,
        "access_token": access_token,
        "limit": limit,
    }
    
    request_data = json.dumps(request_body).encode('utf-8')
    
    print(f"[*] Testing Spotify sync endpoint...")
    print(f"    URL: {endpoint}")
    print(f"    User: {user_id}")
    print(f"    Limit: {limit}")
    print()
    
    try:
        req = urllib.request.Request(
            endpoint,
            data=request_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            print("[✓] Success!")
            print()
            print(f"    User ID: {result.get('user_id')}")
            print(f"    Total processed: {result.get('total_processed')}")
            print(f"    Songs added: {result.get('songs_added')}")
            print(f"    Songs merged: {result.get('songs_merged')}")
            print(f"    Failed: {result.get('failed_count')}")
            print()
            
            if result.get('added_tracks'):
                print(f"[+] Added {len(result['added_tracks'])} new tracks:")
                for tid in result['added_tracks'][:10]:
                    print(f"      - {tid}")
                if len(result['added_tracks']) > 10:
                    print(f"      ... and {len(result['added_tracks']) - 10} more")
            
            if result.get('merged_tracks'):
                print(f"[+] Merged {len(result['merged_tracks'])} existing tracks:")
                for tid in result['merged_tracks'][:10]:
                    print(f"      - {tid}")
                if len(result['merged_tracks']) > 10:
                    print(f"      ... and {len(result['merged_tracks']) - 10} more")
            
            return result
    
    except urllib.error.HTTPError as e:
        error_detail = e.read().decode('utf-8')
        print(f"[!] HTTP {e.code} Error:")
        try:
            error_json = json.loads(error_detail)
            print(f"    {error_json.get('detail', 'No details provided')}")
        except:
            print(f"    {error_detail}")
        return None
    except Exception as e:
        print(f"[!] Error: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_spotify_sync.py <user_id> <access_token> [limit]")
        print()
        print("Example:")
        print("  python test_spotify_sync.py user123 BQCabc123xyz... 50")
        sys.exit(1)
    
    user_id = sys.argv[1]
    access_token = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    
    test_spotify_sync(user_id, access_token, limit)
