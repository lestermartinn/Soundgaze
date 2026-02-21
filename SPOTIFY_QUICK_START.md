# Spotify Integration - Quick Start & Examples

## Quick Start (60 seconds)

### 1. Get Your Spotify Access Token

For testing, use Spotify's developer tools:

```
1. Go to https://developer.spotify.com/dashboard
2. Create an app
3. Get Client ID and Client Secret
4. Use OAuth to get user's access token
```

Or for quick testing with your own data:
```bash
# Use Spotify Web Console (requires login):
# https://developer.spotify.com/console/get-current-user-top-tracks/
# Copy the access token from browser
```

### 2. Test the Endpoint

**Using cURL:**
```bash
curl -X POST http://localhost:8000/songs/spotify/sync \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "my_app_user",
    "access_token": "BQCabc123xyz...",
    "limit": 50
  }'
```

**Using Python:**
```bash
cd backend
python test_spotify_quick.py my_app_user "BQCabc123xyz..." 50
```

**Using JavaScript/Node.js:**
```javascript
fetch('http://localhost:8000/songs/spotify/sync', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: 'my_app_user',
    access_token: 'BQCabc123xyz...',
    limit: 50
  })
})
.then(r => r.json())
.then(data => console.log(`Added: ${data.songs_added}, Merged: ${data.songs_merged}`))
```

### 3. See Your Results

Response shows:
- ✨ **songs_added**: New tracks inserted
- 🔗 **songs_merged**: Existing tracks where user was linked
- ❌ **failed_count**: Any processing errors
- 📝 **added_tracks/merged_tracks**: Lists of IDs

## Real-World Example Flow

### Frontend Implementation (React/TypeScript)

```typescript
// 1. User clicks "Sync Spotify"
async function syncSpotifyLibrary() {
  // 2. Get user's Spotify access token (from OAuth)
  const accessToken = localStorage.getItem('spotifyAccessToken');
  
  if (!accessToken) {
    redirectToSpotifyLogin();
    return;
  }

  // 3. Call sync endpoint
  try {
    const response = await fetch('http://localhost:8000/songs/spotify/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUser.id,        // Your app's user ID
        access_token: accessToken,       // From Spotify OAuth
        limit: 50                         // Sync top 50 songs
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();

    // 4. Show results to user
    showNotification({
      title: 'Sync Complete!',
      message: `Added ${result.songs_added} new songs, merged ${result.songs_merged}`,
      type: 'success'
    });

    // 5. Refresh UI (e.g., redraw point cloud)
    refreshPointCloud();

  } catch (error) {
    showNotification({
      title: 'Sync Failed',
      message: error.message,
      type: 'error'
    });
  }
}

// Spotify OAuth callback
function handleSpotifyCallback(code: string) {
  // Exchange code for access token on your backend
  fetch('/api/auth/spotify/callback', {
    method: 'POST',
    body: JSON.stringify({ code })
  })
  .then(r => r.json())
  .then(data => {
    localStorage.setItem('spotifyAccessToken', data.access_token);
    syncSpotifyLibrary(); // Auto-sync after auth
  });
}
```

### Backend OAuth Handler (FastAPI)

```python
# In your main.py or auth module
import os
import requests
from fastapi import HTTPException

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://localhost:3000/auth/spotify/callback"

@app.post("/api/auth/spotify/callback")
async def spotify_callback(body: dict):
    """Exchange Spotify auth code for access token."""
    code = body.get("code")
    
    result = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        }
    )
    
    data = result.json()
    
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error_description"])
    
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in", 3600)
    }
```

### Full OAuth Flow (Frontend)

```html
<!-- HTML -->
<button onclick="startSpotifyAuth()">🎵 Connect Spotify</button>

<script>
const SPOTIFY_CLIENT_ID = "your_client_id_here";
const REDIRECT_URI = "http://localhost:3000";

function startSpotifyAuth() {
  const scopes = ["user-top-read"];
  const authUrl = new URL("https://accounts.spotify.com/authorize");
  
  authUrl.searchParams.append("client_id", SPOTIFY_CLIENT_ID);
  authUrl.searchParams.append("response_type", "code");
  authUrl.searchParams.append("redirect_uri", REDIRECT_URI);
  authUrl.searchParams.append("scope", scopes.join(" "));
  
  window.location = authUrl.toString();
}

// On redirect page (e.g., /callback)
function handleCallback() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  
  fetch("/api/auth/spotify/callback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code })
  })
  .then(r => r.json())
  .then(data => {
    localStorage.setItem("spotifyAccessToken", data.access_token);
    window.location = "/". // Redirect to main app
  });
}
</script>
```

## Testing With Different Scenarios

### Test 1: One User, First Sync
```bash
python test_spotify_quick.py alice "TOKEN_ALICE" 50
```
Expected: songs_added ≈ 50, songs_merged = 0

### Test 2: Same User, Second Sync
```bash
python test_spotify_quick.py alice "TOKEN_ALICE" 50
```
Expected: songs_added ≈ 0, songs_merged ≈ 50

### Test 3: Different User, Same Songs
```bash
python test_spotify_quick.py bob "TOKEN_BOB" 50
```
Expected: songs_added ≈ 0, songs_merged ≈ 50

### Test 4: Mixed (No duplicate songs)
Create a Bob account with different Spotify tastes:
```bash
python test_spotify_quick.py bob "TOKEN_BOB" 50
```
Expected: songs_added ≈ 30, songs_merged ≈ 20

## Postman Collection

### Request 1: Sync Spotify (User Alice)
```http
POST http://localhost:8000/songs/spotify/sync
Content-Type: application/json

{
  "user_id": "alice",
  "access_token": "BQCLdRUBRSpL6GU1e_P0MUAqk...",
  "limit": 50
}
```

### Expected Response 1
```json
{
  "user_id": "alice",
  "songs_added": 45,
  "songs_merged": 5,
  "total_processed": 50,
  "failed_count": 0,
  "added_tracks": [
    "5MRWQJvTI8C6d7hPuLHsGL",
    "4CuwGrquqpJYOqbBkYtIY0",
    ...
  ],
  "merged_tracks": [
    "2tvRXgwdPB8Nr6t7QvWeVE",
    "1CcKjHSfALxxdzWt64G9Gv",
    ...
  ]
}
```

### Request 2: Get Pool (User Alice)
```http
POST http://localhost:8000/songs/pool
Content-Type: application/json

{
  "user_id": "alice",
  "user_song_count": 100,
  "total_count": 1000
}
```

### Expected Response 2
```json
{
  "user_songs": [
    {
      "track_id": "5MRWQJvTI8C6d7hPuLHsGL",
      "name": "Song Name",
      "artist": "Artist Name",
      "genre": null,
      "user_id": "alice",
      "user_ids": ["alice"]
    },
    ...
  ],
  "global_songs": [...],
  "user_songs_returned": 45,
  "global_songs_returned": 955,
  "total_returned": 1000,
  "is_new_user": false
}
```

### Request 3: Sync Spotify (User Bob)
```http
POST http://localhost:8000/songs/spotify/sync
Content-Type: application/json

{
  "user_id": "bob",
  "access_token": "BQDef789ABCxyz...",
  "limit": 50
}
```

### Expected Response 3
```json
{
  "user_id": "bob",
  "songs_added": 20,
  "songs_merged": 30,
  "total_processed": 50,
  "failed_count": 0,
  "added_tracks": [
    "3XVBFNyaDqGHSLIIe2xP6R",
    ...
  ],
  "merged_tracks": [
    "5MRWQJvTI8C6d7hPuLHsGL",
    "4CuwGrquqpJYOqbBkYtIY0",
    ...
  ]
}
```

Notice: Bob merged 30 songs with Alice (shared taste), added 20 new ones

## Debugging

### Enable Debug Logging
```bash
# In terminal running backend
export LOG_LEVEL=DEBUG
python -m uvicorn main:app --reload --log-level debug
```

### Check Request/Response
```bash
# Watch network traffic
curl -v http://localhost:8000/songs/spotify/sync \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","access_token":"TOKEN","limit":5}'
```

### Check Database State
```bash
# Check if songs were added
curl http://localhost:8000/songs/5MRWQJvTI8C6d7hPuLHsGL
```

## Common Errors & Solutions

### "401 Unauthorized"
```
❌ Error: Invalid Spotify access token
✅ Solution: Token may have expired (valid ~1 hour)
   - Get new token from Spotify OAuth flow
   - Check token format (should start with "BQ")
```

### "429 Too Many Requests"
```
❌ Error: Hit Spotify API rate limit
✅ Solution: Wait 60 seconds and retry
   - Each user has: 60,000 requests/hour
   - One sync = 51 requests (1 for top tracks + 50 for audio features)
```

### "404 Not Found"
```
❌ Error: /songs/spotify/sync endpoint not found
✅ Solution: Backend not running or old version
   - Check: curl http://localhost:8000/health
   - Restart backend
   - Pull latest code
```

### Some songs fail silently
```
⚠️  Note: Individual song failures are tolerated
✅ Solution: Check failed_count in response
   - Typical causes: Song not available in user's region, removed tracks
   - Sync continues with successful songs
```

## Performance Notes

- **First sync** (50 songs): ~2-3 seconds
- **Second sync** (same user): ~2-3 seconds (no performance difference)
- **Multiple users**: Can run concurrences in parallel
- **Parallel syncs** (30+ users): Should work fine, may hit Spotify rate limits

## Next Steps

1. ✅ Test with your Spotify account
2. 🔄 Integrate into frontend OAuth flow
3. 📊 Add sync history tracking
4. 🔐 Implement token refresh logic
5. 📈 Monitor API usage and rate limits

