from django.shortcuts import redirect, render
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseServerError
from django.urls import reverse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic, OAuthCredentials
import json
import base64
import os
import time
from datetime import datetime

# For Google OAuth Web Flow
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials as GoogleCredentials
from google.auth.transport.requests import Request as GoogleAuthRequest


# --- Spotify Authentication ---
SPOTIFY_SCOPE = "playlist-read-private playlist-read-collaborative"

def get_spotify_oauth(request):
    # Construct the redirect_uri dynamically using Django's reverse
    
    redirect_uri = request.build_absolute_uri(reverse('spotify_callback'))
    print(f"DEBUG: Spotify OAuth redirect_uri being used: {redirect_uri}") # <<< ADD THIS LINE
    
    return SpotifyOAuth(
        client_id=settings.SPOTIPY_CLIENT_ID,
        client_secret=settings.SPOTIPY_CLIENT_SECRET,
        redirect_uri=redirect_uri,
        scope=SPOTIFY_SCOPE,
    )

@require_http_methods(["GET"])
def spotify_authorize(request):
    sp_oauth = get_spotify_oauth(request)
    auth_url = sp_oauth.get_authorize_url()
    # Instead of redirecting directly, we can send the URL to the frontend
    # so it can perform the redirect. This is often better for SPA UX.
    # Or, for simplicity now, we can redirect from the backend.
    return redirect(auth_url)
    # return JsonResponse({'authorization_url': auth_url})


@require_http_methods(["GET"])
def spotify_callback(request):
    print("DEBUG: spotify_callback view hit")
    sp_oauth = get_spotify_oauth(request)
    code = request.GET.get('code')
    error = request.GET.get('error')
    print(f"DEBUG: Spotify callback code: {code[:50] if code else None}..., error: {error}")

    if error:
        print(f"ERROR from Spotify redirect: {error}")
        return redirect(f'http://localhost:3000/?error=spotify_auth_failed&message={error}')

    if not code:
        print("ERROR: No code received in Spotify callback.")
        return redirect('http://localhost:3000/?error=spotify_auth_failed&message=No code received')

    try:
        print("DEBUG: Attempting to get Spotify access token...")
        token_info = sp_oauth.get_access_token(code, check_cache=False)
        
        if token_info:
            print("DEBUG: Spotify token_info obtained successfully.")
            # Instead of storing in session, encode token and redirect with it
            # Base64 encode the token info to pass it in URL (for simplicity)
            token_json = json.dumps(token_info)
            token_encoded = base64.urlsafe_b64encode(token_json.encode()).decode()
            print("DEBUG: Redirecting to frontend with encoded token")
            return redirect(f'http://localhost:3000/?spotify_auth=success&token={token_encoded}')
        else:
            print("ERROR: sp_oauth.get_access_token returned None or empty.")
            return redirect('http://localhost:3000/?error=spotify_auth_failed&message=Token exchange failed')

    except Exception as e:
        print(f"EXCEPTION during Spotify token exchange: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(f'http://localhost:3000/?error=spotify_auth_failed&message={str(e)}')

# --- YouTube Music Authentication ---

@require_http_methods(["GET"])
def ytmusic_authorize(request):
    """Initiate YouTube Music OAuth flow."""
    print("DEBUG: ytmusic_authorize view hit")
    
    # Create Google OAuth flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.YTM_CLIENT_ID,
                "client_secret": settings.YTM_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=["https://www.googleapis.com/auth/youtube"]
    )
    
    # Set the redirect URI to our callback
    flow.redirect_uri = request.build_absolute_uri(reverse('ytmusic_callback'))
    print(f"DEBUG: YouTube Music OAuth redirect_uri: {flow.redirect_uri}")
    
    # Get the authorization URL
    authorization_url, state = flow.authorization_url(
        access_type='offline',  # Request offline access for refresh tokens
        include_granted_scopes='true'
    )
    
    # Store state in session for security (optional but recommended)
    request.session['ytmusic_oauth_state'] = state
    
    print(f"DEBUG: Redirecting to Google OAuth: {authorization_url}")
    return redirect(authorization_url)

@require_http_methods(["GET"])
def ytmusic_callback(request):
    print("DEBUG: ytmusic_callback view hit")
    
    # Get authorization code from query parameters
    code = request.GET.get('code')
    error = request.GET.get('error')
    
    if error:
        print(f"ERROR from Google redirect: {error}")
        return redirect(f'http://localhost:3000/?error=ytmusic_auth_failed&message={error}')
        
    if not code:
        print("ERROR: No authorization code received.")
        return redirect('http://localhost:3000/?error=ytmusic_auth_failed&message=No code received')

    try:
        print("DEBUG: Attempting to get YouTube Music access token...")
        
        # Create flow instance (same as in ytmusic_authorize)
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.YTM_CLIENT_ID,
                    "client_secret": settings.YTM_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=["https://www.googleapis.com/auth/youtube"]
        )
        flow.redirect_uri = request.build_absolute_uri(reverse('ytmusic_callback'))
        
        # Exchange code for token
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Create token info similar to Spotify format
        token_info = {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': list(credentials.scopes) if credentials.scopes else [],
            'expires_at': int(credentials.expiry.timestamp()) if credentials.expiry else None,
        }
        
        print("DEBUG: YouTube Music token_info obtained successfully.")
        
        # Base64 encode the token info to pass it in URL
        token_json = json.dumps(token_info)
        token_encoded = base64.urlsafe_b64encode(token_json.encode()).decode()
        print("DEBUG: Redirecting to frontend with encoded YTMusic token")
        return redirect(f'http://localhost:3000/?ytmusic_auth=success&token={token_encoded}')
        
    except Exception as e:
        print(f"EXCEPTION during YouTube Music token exchange: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(f'http://localhost:3000/?error=ytmusic_auth_failed&message={str(e)}')


# --- Transfer Logic ---
@csrf_exempt
@require_http_methods(["POST"])
def transfer_playlist(request):
    print(f"DEBUG: /transfer/ view hit")
    
    # Get tokens from request body instead of session
    try:
        body = json.loads(request.body)
        spotify_token_info = body.get('spotify_token')
        ytmusic_token_info = body.get('ytmusic_token')
        playlist_identifier = body.get('playlist_identifier')
        yt_playlist_name = body.get('yt_playlist_name')
        
        print(f"DEBUG: Received tokens - Spotify: {spotify_token_info is not None}, YTMusic: {ytmusic_token_info is not None}")
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)

    if not spotify_token_info:
        print("DEBUG: /transfer/ - Spotify token not provided!")
        return JsonResponse({'error': 'Spotify not authenticated. Please authorize Spotify first.'}, status=401)
    if not ytmusic_token_info:
        print("DEBUG: /transfer/ - YouTube Music token not provided!")
        return JsonResponse({'error': 'YouTube Music not authenticated. Please authorize YouTube Music first.'}, status=401)

    if not playlist_identifier:
        return JsonResponse({'error': 'Playlist identifier is required.'}, status=400)

    # Initialize Spotify client with provided token
    try:
        sp = spotipy.Spotify(auth=spotify_token_info['access_token'])
        # Test the token
        sp.current_user()
        print("DEBUG: Spotify token validated successfully")
    except Exception as e:
        print(f"ERROR: Invalid Spotify token: {e}")
        return JsonResponse({'error': 'Invalid Spotify token. Please re-authenticate.'}, status=401)

    # Initialize YouTube Music client with provided token
    try:
        print("DEBUG: Creating YouTube Music client...")
        
        # Create OAuth credentials for YTMusic using the client credentials from settings
        oauth_credentials = OAuthCredentials(
            client_id=settings.YTM_CLIENT_ID,
            client_secret=settings.YTM_CLIENT_SECRET
        )
        
        print("DEBUG: OAuth credentials created")
        
        # Create a temporary token file with the user's token info
        import tempfile
        import os
        
        # Create a temporary file to store the token
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            # Write the token info in the format expected by YTMusic
            token_data = {
                "access_token": ytmusic_token_info['access_token'],
                "refresh_token": ytmusic_token_info.get('refresh_token'),
                "scope": ytmusic_token_info.get('scopes', ['https://www.googleapis.com/auth/youtube']),
                "token_type": "Bearer",
                "expires_at": ytmusic_token_info.get('expires_at')
            }
            json.dump(token_data, temp_file)
            temp_token_file = temp_file.name
        
        print(f"DEBUG: Created temporary token file: {temp_token_file}")
        
        # Initialize YTMusic with the token file and OAuth credentials
        ytmusic = YTMusic(auth=temp_token_file, oauth_credentials=oauth_credentials)
        
        print("DEBUG: YTMusic client initialized")
        
        # Test the YouTube Music connection
        try:
            # Try to get library playlists to validate the token
            test_playlists = ytmusic.get_library_playlists(limit=1)
            print("DEBUG: YouTube Music token validated successfully")
        except Exception as e:
            print(f"ERROR: YouTube Music token validation failed: {e}")
            # Clean up the temporary file
            try:
                os.unlink(temp_token_file)
            except:
                pass
            return JsonResponse({'error': 'Invalid YouTube Music token. Please re-authenticate.'}, status=401)
            
    except Exception as e:
        print(f"ERROR: Invalid YouTube Music token setup: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Invalid YouTube Music token setup: {str(e)}'}, status=401)

    # Now implement the actual transfer logic
    try:
        print("DEBUG: Starting playlist transfer logic...")
        
        # Extract playlist ID from various Spotify URL formats
        playlist_id = playlist_identifier
        if "open.spotify.com/playlist/" in playlist_identifier:
            playlist_id = playlist_identifier.split("/")[-1].split("?")[0]
        elif "spotify:playlist:" in playlist_identifier:
            playlist_id = playlist_identifier.split(":")[-1]
        
        print(f"DEBUG: Extracted playlist ID: {playlist_id}")
        
        # Get Spotify playlist info
        try:
            spotify_playlist = sp.playlist(playlist_id, fields="name,description,tracks.items(track(name,artists(name),external_urls))")
            spotify_playlist_name = spotify_playlist.get('name', 'Unknown Playlist')
            print(f"DEBUG: Spotify playlist name: {spotify_playlist_name}")
            
            # Use provided name or default to Spotify playlist name
            yt_playlist_name = yt_playlist_name or f"{spotify_playlist_name} (from Spotify)"
            
        except Exception as e:
            print(f"ERROR: Failed to fetch Spotify playlist: {e}")
            # Clean up the temporary file
            try:
                os.unlink(temp_token_file)
            except:
                pass
            return JsonResponse({'error': f'Failed to fetch Spotify playlist: {str(e)}'}, status=400)
        
        # Get playlist tracks
        tracks = spotify_playlist['tracks']['items']
        spotify_songs = []
        
        for item in tracks:
            track = item.get('track')
            if track and track.get('name'):
                song_info = {
                    'title': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track.get('artists', [])]),
                    'spotify_url': track.get('external_urls', {}).get('spotify', '')
                }
                spotify_songs.append(song_info)
        
        print(f"DEBUG: Found {len(spotify_songs)} tracks in Spotify playlist")
        
        if not spotify_songs:
            # Clean up the temporary file
            try:
                os.unlink(temp_token_file)
            except:
                pass
            return JsonResponse({'error': 'No tracks found in the Spotify playlist'}, status=400)
        
        # Search for songs on YouTube Music and collect video IDs
        found_video_ids = []
        not_found_songs = []
        
        for i, song in enumerate(spotify_songs):
            print(f"DEBUG: Searching for song {i+1}/{len(spotify_songs)}: {song['title']} by {song['artist']}")
            
            try:
                # Search for the song on YouTube Music
                query = f"{song['title']} {song['artist']}"
                search_results = ytmusic.search(query, filter="songs", limit=5)
                
                video_id = None
                if search_results:
                    # Try to find the best match
                    for result in search_results:
                        if result.get('resultType') == 'song':
                            video_id = result.get('videoId')
                            print(f"DEBUG: Found match: {result.get('title')} - {video_id}")
                            break
                    
                    # Fallback to first result if no song type found
                    if not video_id and search_results[0].get('videoId'):
                        video_id = search_results[0]['videoId']
                        print(f"DEBUG: Using fallback match: {search_results[0].get('title')} - {video_id}")
                
                if video_id:
                    found_video_ids.append(video_id)
                else:
                    not_found_songs.append(song)
                    print(f"DEBUG: No match found for: {song['title']} by {song['artist']}")
                    
            except Exception as e:
                print(f"ERROR: Failed to search for song {song['title']}: {e}")
                not_found_songs.append(song)
        
        print(f"DEBUG: Found {len(found_video_ids)} songs on YouTube Music, {len(not_found_songs)} not found")
        
        if not found_video_ids:
            # Clean up the temporary file
            try:
                os.unlink(temp_token_file)
            except:
                pass
            return JsonResponse({'error': 'No songs could be found on YouTube Music'}, status=400)
        
        # Create YouTube Music playlist
        try:
            print(f"DEBUG: Creating YouTube Music playlist: {yt_playlist_name}")
            playlist_id = ytmusic.create_playlist(
                title=yt_playlist_name,
                description=f"Transferred from Spotify playlist '{spotify_playlist_name}'",
                privacy_status="PRIVATE"
            )
            print(f"DEBUG: Created playlist with ID: {playlist_id}")
            
            # Add songs to the playlist
            if found_video_ids:
                print(f"DEBUG: Adding {len(found_video_ids)} songs to playlist")
                add_result = ytmusic.add_playlist_items(playlist_id, found_video_ids)
                print(f"DEBUG: Add result: {add_result}")
            
            # Clean up the temporary file
            try:
                os.unlink(temp_token_file)
            except:
                pass
            
            # Prepare response
            response_data = {
                'message': f'Successfully transferred playlist to YouTube Music',
                'playlist_id': playlist_id,
                'spotify_track_count': len(spotify_songs),
                'songs_found_count': len(found_video_ids),
                'songs_not_found_count': len(not_found_songs),
                'yt_playlist_name': yt_playlist_name
            }
            
            if not_found_songs:
                response_data['not_found_songs'] = not_found_songs[:10]  # Limit to first 10 for response size
                response_data['warning'] = f'{len(not_found_songs)} songs could not be found on YouTube Music'
            
            return JsonResponse(response_data)
            
        except Exception as e:
            print(f"ERROR: Failed to create YouTube Music playlist: {e}")
            import traceback
            traceback.print_exc()
            # Clean up the temporary file
            try:
                os.unlink(temp_token_file)
            except:
                pass
            return JsonResponse({'error': f'Failed to create YouTube Music playlist: {str(e)}'}, status=500)
            
    except Exception as e:
        print(f"ERROR: Transfer logic failed: {e}")
        import traceback
        traceback.print_exc()
        # Clean up the temporary file if it exists
        try:
            if 'temp_token_file' in locals():
                os.unlink(temp_token_file)
        except:
            pass
        return JsonResponse({'error': f'Transfer failed: {str(e)}'}, status=500)
