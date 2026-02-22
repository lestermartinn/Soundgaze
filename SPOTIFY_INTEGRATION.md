# Spotify Integration Guide

## Overview

The backend now includes a `/songs/spotify/sync` endpoint that allows users to sync their top 50 Spotify tracks to the local database with proper user ownership tracking.

## Architecture

### Components

1. **spotify.py** - Spotify API client handling
   - `SpotifyImporter` class: Manages Spotify API calls
   - `fetch_user_top_tracks()`: Gets user's top 50 tracks
   - `audio_features_to_vector()`: Converts Spotify features to 11-D vectors

2. **models.py** - Request/Response schemas
   - `SpotifyImportRequest`: Request body (user_id, access_token, limit)
   - `SpotifySyncResponse`: Response with import summary

3. **main.py** - Endpoint
   - `POST /songs/spotify/sync`: Main sync endpoint

### How It Works

```
User Login (Spotify OAuth)
        ↓
Frontend gets access_token from Spotify
        ↓
Frontend POST /songs/spotify/sync with (user_id, access_token)
        ↓
Backend fetches user's top 50 songs via Spotify API
        ↓
For each song:
  - Get audio features from Spotify
  - Convert to 11-D vector (normalized)
  - Check if song exists in DB
  - If new: INSERT with user_id
  - If exists: MERGE user_id into user_ids array
        ↓
Return summary (added, merged, failed counts)
```

## API Reference

### POST /songs/spotify/sync

**Request Body:**
```json
{
  "user_id": "user123",
  "access_token": "BQCabc123xyz...",
  "limit": 50
}
```

**Parameters:**
- `user_id` (string, required): Your app's user ID
- `access_token` (string, required): Spotify OAuth token from user's session
- `limit` (int, optional): Number of top songs to fetch (1-50, default 50)

**Response:**
```json
{
  "user_id": "user123",
  "songs_added": 25,
  "songs_merged": 20,
  "total_processed": 50,
  "failed_count": 5,
  "added_tracks": ["id1", "id2", "id3", ...],
  "merged_tracks": ["id4", "id5", "id6", ...]
}
```

**Fields:**
- `songs_added`: Number of new songs inserted into database
- `songs_merged`: Number of existing songs where this user was added
- `total_processed`: Total songs fetched from Spotify
- `failed_count`: Songs that failed to process
- `added_tracks`: List of track IDs that were newly added
- `merged_tracks`: List of track IDs where user was merged

## User Ownership Model

When syncing Spotify tracks:

1. **First Upload (New Song):**
   - `user_id` = requesting user (primary owner)
   - `user_ids` = [requesting user]

2. **Duplicate Upload (Same Song, Different User):**
   - `user_id` = original uploader (unchanged)
   - `user_ids` = [original uploader, new user, ...]

3. **Same User Re-sync:**
   - Song ownership unchanged
   - Counted as "merged" even though user already in list

## Example Usage

### cURL
```bash
curl -X POST http://localhost:8000/songs/spotify/sync \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "my_app_user_123",
    "access_token": "BQCabc123xyz...",
    "limit": 50
  }'
```

### Python
```python
import json
import urllib.request

body = {
    "user_id": "my_app_user_123",
    "access_token": "BQCabc123xyz...",
    "limit": 50
}

req = urllib.request.Request(
    "http://localhost:8000/songs/spotify/sync",
    data=json.dumps(body).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

with urllib.request.urlopen(req) as response:
    result = json.loads(response.read())
    print(f"Added: {result['songs_added']}, Merged: {result['songs_merged']}")
```

### JavaScript/TypeScript
```typescript
async function syncSpotifyLibrary(userId: string, accessToken: string) {
  const response = await fetch('http://localhost:8000/songs/spotify/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      access_token: accessToken,
      limit: 50
    })
  });
  
  const result = await response.json();
  console.log(`Added: ${result.songs_added}, Merged: ${result.songs_merged}`);
  return result;
}
```

## Getting a Spotify Access Token

### Option 1: OAuth Flow (Recommended)

Your frontend should implement Spotify's OAuth 2.0 authorization code flow:

1. Redirect user to: https://accounts.spotify.com/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=YOUR_REDIRECT_URI&scope=user-top-read,user-read-playback-state
2. User authorizes your app
3. Spotify redirects back with a `code`
4. Backend exchanges `code` for `access_token` and `refresh_token`
5. Send `access_token` to `/songs/spotify/sync`

### Option 2: Client Credentials (Development Only)

For testing without a full OAuth flow:
```bash
# 1. Get client credentials from https://developer.spotify.com
# 2. Base64 encode: client_id:client_secret
# 3. Get access token:
curl -X POST https://accounts.spotify.com/api/token \
  -H "Authorization: Basic YOUR_BASE64_CREDENTIALS" \
  -d "grant_type=client_credentials"
```

**Note:** Client credentials tokens don't have access to user-specific data like "top tracks". Use OAuth for real users.

## Vector Conversion

Spotify audio features are converted to an 11-dimensional vector:

1. **tempo** → normalized BPM (0-250 → 0-1)
2. **energy** → perceptual intensity (0-1)
3. **loudness** → dB (-60 to 0 → 0-1)
4. **danceability** → rhythmic regularity (0-1)
5. **valence** → musical positivity (0-1)
6. **mode** → minor/major (0 or 1)
7. **key** → pitch class 0-11 → 0-1
8. **acousticness** → acoustic vs electronic (0-1)
9. **instrumentalness** → lack of vocals (0-1)
10. **liveness** → audience presence (0-1)
11. **speechiness** → spoken word ratio (0-1)
12. **duration** → track length (capped at 10 min)

(Note: The final vector actually has 11 dimensions - one dimension was dropped to match the database schema)

## Error Handling

### Token Expired
```json
{
  "detail": "Failed to sync Spotify library: Invalid access token"
}
```
→ User needs to re-authenticate with Spotify

### Rate Limited
```json
{
  "detail": "Failed to sync Spotify library: Rate limit exceeded"
}
```
→ Wait a minute and retry

### Song Processing Failed
Individual song failures are logged but don't stop the sync:
- Failed count shows how many songs couldn't be processed
- Successfully processed songs are still added to the database

## Testing

### Test Script
```bash
python backend/test_spotify_sync.py "user123" "BQCabc123xyz..."
```

### Automated Tests
See `backend/scripts/` for integration tests that verify:
- Song ownership merging
- Vector creation accuracy
- Database consistency

## Current Limitations

1. Fetches top tracks from "medium_term" (last 6 months)
   - Can be changed to "short_term" (4 weeks) or "long_term" (all time)
2. Limited to 50 songs per sync (Spotify API constraint)
   - Could paginate for more songs
3. Genre not provided by Spotify track API
   - Would need additional artist genre lookup
4. No conflict resolution if same song uploaded with different vectors
   - Later uploads overwrite earlier vectors

## Future Enhancements

- [ ] Support paginated sync (>50 songs)
- [ ] Add user-configurable time range (short/medium/long term)
- [ ] Track sync history and detect duplicates
- [ ] Refresh tokens for long-lived sessions
- [ ] Batch sync multiple users
- [ ] Webhook support for real-time sync on playback

