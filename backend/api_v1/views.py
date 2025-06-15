from django.shortcuts import redirect, render
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseServerError
from django.urls import reverse
from django.conf import settings
from django.views.decorators.http import require_http_methods
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic, OAuthCredentials
import json
import os
import time # For calculating token expiry

# For Google OAuth Web Flow
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials as GoogleCredentials # Alias to avoid conflict
from google.auth.transport.requests import Request as GoogleAuthRequest


# --- Spotify Authentication ---
SPOTIFY_SCOPE = "playlist-read-private playlist-read-collaborative"

def get_spotify_oauth(request):
    # Construct the redirect_uri dynamically using Django's reverse
    # Ensure this matches exactly what's in your Spotify Developer Dashboard
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
    sp_oauth = get_spotify_oauth(request)
    code = request.GET.get('code')
    error = request.GET.get('error')

    if error:
        # TODO: Redirect to a frontend error page
        return HttpResponseBadRequest(f"Spotify authorization failed: {error}")

    if not code:
        # TODO: Redirect to a frontend error page
        return HttpResponseBadRequest("Spotify authorization failed: No code received.")

    try:
        token_info = sp_oauth.get_access_token(code, check_cache=False)
        request.session['spotify_token_info'] = token_info
        # Redirect to frontend, indicating success
        return redirect('http://localhost:3000/?spotify_auth=success') # Adjust port if your React app runs elsewhere
    except Exception as e:
        # TODO: Redirect to a frontend error page
        return HttpResponseServerError(f"Error getting Spotify token: {str(e)}")

# --- YouTube Music Authentication (Web Server Flow) ---

YTM_SCOPES = ['https://www.googleapis.com/auth/youtube'] # Standard YouTube scope

def get_google_oauth_flow(request):
    # Note: For web server flow, your Google Cloud OAuth client should be "Web application" type.
    # The client ID/secret for "TVs and Limited Input devices" might not work correctly for this flow.
    # You might need to create a new OAuth Client ID of type "Web application" in Google Cloud Console
    # and update YTM_CLIENT_ID and YTM_CLIENT_SECRET in your .env accordingly.
    # Ensure the redirect URI for this web client is also registered in Google Cloud Console.
    
    redirect_uri = request.build_absolute_uri(reverse('ytmusic_callback'))
    
    # client_secrets.json structure or direct parameters
    # We'll use direct parameters from settings
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.YTM_CLIENT_ID,
                "client_secret": settings.YTM_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                # "redirect_uris" list is usually part of client_secrets.json, but flow needs one for this instance
            }
        },
        scopes=YTM_SCOPES,
        redirect_uri=redirect_uri
    )
    return flow

@require_http_methods(["GET"])
def ytmusic_authorize(request):
    if request.session.get('ytmusic_token_info'):
        # TODO: Redirect to frontend indicating already authorized
        return JsonResponse({'message': 'YouTube Music already authorized.'})

    flow = get_google_oauth_flow(request)
    authorization_url, state = flow.authorization_url(
        access_type='offline', # Request a refresh token
        prompt='consent'       # Ensure user sees consent screen even if previously authorized
    )
    request.session['ytmusic_oauth_state'] = state # Store state to prevent CSRF
    return redirect(authorization_url)

@require_http_methods(["GET"])
def ytmusic_callback(request):
    state = request.session.pop('ytmusic_oauth_state', None)
    if not state or state != request.GET.get('state'):
        # TODO: Redirect to a frontend error page (CSRF attempt)
        return HttpResponseBadRequest('Invalid OAuth state.')

    if 'error' in request.GET:
        # TODO: Redirect to a frontend error page
        return HttpResponseBadRequest(f"YouTube Music authorization error: {request.GET.get('error')}")

    flow = get_google_oauth_flow(request)
    try:
        # Use the full URL for fetching the token
        flow.fetch_token(authorization_response=request.build_absolute_uri())
    except Exception as e: # Catch specific exceptions like MismatchingStateError if possible
        # TODO: Redirect to a frontend error page
        return HttpResponseServerError(f"Failed to fetch YouTube Music token: {str(e)}")

    credentials = flow.credentials # google.oauth2.credentials.Credentials object

    # Prepare token_info in a structure similar to Spotify's and ytmusicapi's oauth.json
    # This is what we'll store in the session and use to initialize YTMusic
    token_info = {
        'token': credentials.token, # Access token
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        # For compatibility with ytmusicapi, let's mimic oauth.json structure more closely
        # The `auth` parameter of YTMusic might expect a dict like the content of oauth.json
        'access_token': credentials.token,
        # 'expires_at' is needed by ytmusicapi if it checks expiry.
        # credentials.expiry is datetime, convert to timestamp
        'expires_at': int(credentials.expiry.timestamp()) if credentials.expiry else None,
        'expires_in': (int(credentials.expiry.timestamp()) - int(time.time())) if credentials.expiry else None,
        'token_type': 'Bearer', # Typically Bearer for Google OAuth
        'scope': " ".join(credentials.scopes) # Space-separated string
    }
    
    request.session['ytmusic_token_info'] = token_info
    # Redirect to frontend, indicating success
    return redirect('http://localhost:3000/?ytmusic_auth=success') # Adjust port if your React app runs elsewhere


# --- Transfer Logic ---
@require_http_methods(["POST"])
def transfer_playlist(request):
    spotify_token_info = request.session.get('spotify_token_info')
    ytmusic_token_info = request.session.get('ytmusic_token_info') # This will be our new structure

    if not spotify_token_info:
        return JsonResponse({'error': 'Spotify not authenticated. Please authorize Spotify first.'}, status=401)
    if not ytmusic_token_info:
        return JsonResponse({'error': 'YouTube Music not authenticated. Please authorize YouTube Music first.'}, status=401)

    try:
        data = json.loads(request.body)
        spotify_playlist_id_input = data.get('playlist_identifier')
        yt_playlist_name_input = data.get('yt_playlist_name', 'Spotify Transfer')
        yt_playlist_description = data.get('yt_playlist_description', 'Transferred from Spotify')
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON data in request.")
    except AttributeError: 
        return HttpResponseBadRequest("Malformed request.")

    if not spotify_playlist_id_input:
        return HttpResponseBadRequest("Missing 'playlist_identifier' in request.")

    # Initialize Spotify client
    try:
        sp_oauth_for_refresh = get_spotify_oauth(request)
        if sp_oauth_for_refresh.is_token_expired(spotify_token_info):
            new_token_info = sp_oauth_for_refresh.refresh_access_token(spotify_token_info['refresh_token'])
            request.session['spotify_token_info'] = new_token_info
            spotify_token_info = new_token_info
        sp = spotipy.Spotify(auth=spotify_token_info['access_token'])
    except Exception as e:
        return HttpResponseServerError(f"Failed to initialize Spotify client: {str(e)}")

    # Initialize YouTube Music client
    try:
        # The app's own credentials for ytmusicapi's OAuthCredentials object
        app_ytm_credentials = OAuthCredentials(client_id=settings.YTM_CLIENT_ID, client_secret=settings.YTM_CLIENT_SECRET)
        
        # Now, ytmusic_token_info is the dictionary we constructed, similar to oauth.json content
        # YTMusic(auth=...) expects this kind of dictionary.
        yt = YTMusic(auth=ytmusic_token_info, oauth_credentials=app_ytm_credentials)
        yt.get_library_playlists(limit=1) # Test call
    except Exception as e:
        if 'ytmusic_token_info' in request.session:
            del request.session['ytmusic_token_info'] # Clear potentially bad token
        return HttpResponseServerError(f"Failed to initialize YouTube Music client: {str(e)}. Please re-authorize YouTube Music.")

    # --- Refactored logic from temp/main.py (Spotify track fetching) ---
    spotify_playlist_name_default = "My Spotify Playlist on YTMusic"
    try:
        playlist_id_for_name = spotify_playlist_id_input
        if "open.spotify.com/playlist/" in playlist_id_for_name:
            playlist_id_for_name = playlist_id_for_name.split("/")[-1].split("?")[0]
        elif "spotify:playlist:" in playlist_id_for_name:
            playlist_id_for_name = playlist_id_for_name.split(":")[-1]
        spotify_playlist_data = sp.playlist(playlist_id_for_name, fields="name")
        if spotify_playlist_data and spotify_playlist_data.get('name'):
            spotify_playlist_name_default = f"{spotify_playlist_data['name']} on YTMusic"
    except Exception:
        pass # Use default name if fetching fails

    yt_playlist_name = yt_playlist_name_input if yt_playlist_name_input else spotify_playlist_name_default

    try:
        playlist_id = None
        if "open.spotify.com/playlist/" in spotify_playlist_id_input:
            playlist_id = spotify_playlist_id_input.split("/")[-1].split("?")[0]
        elif "spotify:playlist:" in spotify_playlist_id_input:
            playlist_id = spotify_playlist_id_input.split(":")[-1]
        else:
            playlist_id = spotify_playlist_id_input

        spotify_tracks_details = []
        results = sp.playlist_items(playlist_id)
        if not results:
            return JsonResponse({'error': f"Could not retrieve items for Spotify playlist ID: {playlist_id}"}, status=404)

        current_tracks_spotify = results['items']
        while results['next']:
            results = sp.next(results)
            current_tracks_spotify.extend(results['items'])
        
        for item in current_tracks_spotify:
            if not item or not item.get('track'): continue
            track = item['track']
            if track and track.get('name') and track.get('artists'):
                track_name = track['name']
                artists = ", ".join([artist['name'] for artist in track['artists']])
                spotify_tracks_details.append({'title': track_name, 'artist': artists, 'query': f"{track_name} {artists}"})
        
        if not spotify_tracks_details:
            return JsonResponse({'message': 'No tracks found in the Spotify playlist.'}, status=200)
    except Exception as e:
        return HttpResponseServerError(f"Error fetching Spotify tracks: {str(e)}")

    # --- Refactored logic (YouTube Music search and playlist creation) ---
    yt_video_ids = []
    found_songs_log = []
    not_found_songs_log = []
    for song_detail in spotify_tracks_details:
        try:
            query = song_detail['query']
            search_results = yt.search(query, filter="songs") 
            video_id_found = None
            if search_results:
                for result in search_results: 
                    if result.get('resultType') == 'song' and result.get('videoId'):
                        video_id_found = result['videoId']
                        found_songs_log.append(f"Found '{result['title']}' for '{query}'")
                        break
                if not video_id_found and search_results[0].get('videoId'): 
                    video_id_found = search_results[0]['videoId']
                    found_songs_log.append(f"Found (fallback) '{search_results[0]['title']}' for '{query}'")

            if video_id_found:
                yt_video_ids.append(video_id_found)
            else: 
                search_results_videos = yt.search(query, filter="videos")
                if search_results_videos and search_results_videos[0].get('videoId'):
                    video_id_found = search_results_videos[0]['videoId']
                    yt_video_ids.append(video_id_found)
                    found_songs_log.append(f"Found (video) '{search_results_videos[0]['title']}' for '{query}'")
                else:
                    not_found_songs_log.append(f"Could not find '{query}' on YouTube Music.")
        except Exception as e:
            not_found_songs_log.append(f"Error searching for '{song_detail['query']}' on YouTube Music: {str(e)}")
            continue 

    if not yt_video_ids:
        return JsonResponse({
            'message': 'No songs could be found on YouTube Music to add to a playlist.',
            'found_count': 0, 'spotify_track_count': len(spotify_tracks_details),
            'not_found_log': not_found_songs_log
        }, status=200)

    try:
        created_playlist_id = yt.create_playlist(
            title=yt_playlist_name, description=yt_playlist_description, privacy_status="PRIVATE"
        )
        if not created_playlist_id:
            return HttpResponseServerError("Failed to create YouTube Music playlist.")

        status = yt.add_playlist_items(created_playlist_id, yt_video_ids, duplicates=True)
        
        success_add = False
        if isinstance(status, dict) and status.get('status') == 'SUCCEEDED': success_add = True
        elif isinstance(status, list) and all(item.get('status') == 'SUCCESS' for item in status if isinstance(item, dict)): success_add = True
        
        if success_add or (isinstance(status, list) and len(status) > 0):
             return JsonResponse({
                'message': f"Successfully created YouTube Music playlist '{yt_playlist_name}' (ID: {created_playlist_id}) and attempted to add {len(yt_video_ids)} songs.",
                'playlist_id': created_playlist_id, 'songs_added_count': len(yt_video_ids),
                'spotify_track_count': len(spotify_tracks_details),
                'found_songs_log': found_songs_log, 'not_found_songs_log': not_found_songs_log
            })
        else:
            return JsonResponse({
                'warning': f"YouTube Music playlist '{yt_playlist_name}' created (ID: {created_playlist_id}), but adding songs might have failed or status is unclear.",
                'playlist_id': created_playlist_id, 'status_from_ytmusicapi': status,
                'songs_for_yt_count': len(yt_video_ids), 'spotify_track_count': len(spotify_tracks_details),
                'found_songs_log': found_songs_log, 'not_found_songs_log': not_found_songs_log
            }, status=207) 
    except Exception as e:
        return HttpResponseServerError(f"Error during YouTube Music playlist creation or adding songs: {str(e)}")

    return JsonResponse({'message': 'Transfer process should have returned earlier.'}) # Should not be reached
