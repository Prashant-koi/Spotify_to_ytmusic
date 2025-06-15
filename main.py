import spotipy
from spotipy.oauth2 import SpotifyOAuth
import argparse
import os
from dotenv import load_dotenv
from ytmusicapi import YTMusic, OAuthCredentials 
import json

def load_credentials():
    """Loads Spotify API credentials from environment variables."""
    load_dotenv() # Load variables from .env file
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")

    if not all([client_id, client_secret, redirect_uri]):
        print("Error: SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, or SPOTIPY_REDIRECT_URI not found.")
        print("Please set them in a .env file or as environment variables.")
        print("Ensure you have created a .env file in the same directory as main.py with your credentials.")
        exit(1)
    return client_id, client_secret, redirect_uri

def get_spotify_client(client_id, client_secret, redirect_uri):
    """Initializes and returns a Spotipy client with user authorization."""
    # Scope needed to read user's private and collaborative playlists
    scope = "playlist-read-private playlist-read-collaborative"
    
    # Spotipy will look for credentials in environment variables by default if not passed directly
    # It will also create a .spotifycache file to store the access token
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        cache_path=".spotifycache" # Ensures the cache file is in the project root
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)
    return sp

def get_playlist_tracks(sp, playlist_id_input):
    """
    Fetches all tracks from a given Spotify playlist ID, URL, or URI.
    Returns a list of dictionaries, each with 'title' and 'artist'.
    """
    playlist_id = None
    if "open.spotify.com/playlist/" in playlist_id_input:
        playlist_id = playlist_id_input.split("/")[-1].split("?")[0]
    elif "spotify:playlist:" in playlist_id_input:
        playlist_id = playlist_id_input.split(":")[-1]
    else:
        playlist_id = playlist_id_input

    if not playlist_id:
        print(f"Invalid playlist input: {playlist_id_input}")
        return []

    print(f"Fetching Spotify tracks for playlist ID: {playlist_id}...")
    
    spotify_tracks_details = []
    try:
        results = sp.playlist_items(playlist_id)
        if not results:
            print(f"Could not retrieve playlist items for playlist ID: {playlist_id}")
            return []

        current_tracks = results['items']
        while results['next']:
            results = sp.next(results)
            current_tracks.extend(results['items'])
        
        for item in current_tracks:
            if not item or not item.get('track'):
                continue
            track = item['track']
            if track and track.get('name') and track.get('artists'):
                track_name = track['name']
                artists = ", ".join([artist['name'] for artist in track['artists']])
                spotify_tracks_details.append({'title': track_name, 'artist': artists})
    except spotipy.SpotifyException as e:
        print(f"Error fetching Spotify playlist tracks: {e}")
        if "Invalid playlist Id" in str(e) or "Not found." in str(e):
             print(f"Please ensure the playlist ID '{playlist_id}' is correct and you have access to it.")
        return []
    
    return spotify_tracks_details



def initialize_ytmusic():
    """Initializes and returns a YTMusic client using OAuth."""
    oauth_file = "oauth.json"
    
    # Load YTM credentials from .env
    load_dotenv() # Ensure .env is loaded
    ytm_client_id = os.getenv("YTM_CLIENT_ID")
    ytm_client_secret = os.getenv("YTM_CLIENT_SECRET")

    if not all([ytm_client_id, ytm_client_secret]):
        print("\nError: YTM_CLIENT_ID or YTM_CLIENT_SECRET not found in your .env file.")
        print("Please obtain these from the Google Cloud Console (YouTube Data API v3, OAuth for 'TVs and Limited Input devices')")
        print("and add them to your .env file.")
        return None

    if not os.path.exists(oauth_file):
        print(f"\n'{oauth_file}' not found.")
        print("To use YouTube Music features, you need to authenticate via OAuth.")
        print("1. Ensure you have YTM_CLIENT_ID and YTM_CLIENT_SECRET in your .env file.")
        print("2. Run 'ytmusicapi oauth' in your terminal and follow the instructions.")
        print(f"   This will create the '{oauth_file}' file for you.")
        print("\nAfter creating 'oauth.json', re-run the script.")
        return None

    try:
        credentials = OAuthCredentials(client_id=ytm_client_id, client_secret=ytm_client_secret)
        ytmusic = YTMusic(oauth_file, oauth_credentials=credentials)
        
        ytmusic.get_library_playlists(limit=1) 
        print("Successfully authenticated with YouTube Music using OAuth.")
        return ytmusic
    except Exception as e:
        print(f"Error during YTMusic OAuth initialization: {e}")
        print(f"Please ensure '{oauth_file}' is present (run 'ytmusicapi oauth'),")
        print("and YTM_CLIENT_ID/YTM_CLIENT_SECRET in your .env file are correct and correspond to an")
        print("OAuth client for 'TVs and Limited Input devices' with the YouTube Data API v3 enabled.")
        return None

def search_song_on_ytmusic(ytmusic, title, artist):
    """Searches for a song on YouTube Music and returns its videoId."""
    query = f"{title} {artist}"
    print(f"Searching YouTube Music for: {query}")
    try:
        search_results = ytmusic.search(query, filter="songs")
        if search_results and len(search_results) > 0:
            # Prioritize songs
            best_match = None
            for result in search_results:
                if result['resultType'] == 'song':
                    best_match = result
                    break
            if not best_match and search_results[0]['resultType'] == 'video': # Fallback to first video if no song
                 best_match = search_results[0]


            if best_match:
                print(f"Found: {best_match['title']} by {', '.join([a['name'] for a in best_match.get('artists', [])]) if best_match.get('artists') else 'Unknown Artist'} (ID: {best_match['videoId']})")
                return best_match['videoId']
            else:
                # If still no best_match, try searching for videos explicitly if songs didn't yield good results
                search_results_videos = ytmusic.search(query, filter="videos")
                if search_results_videos and len(search_results_videos) > 0:
                    best_match_video = search_results_videos[0]
                    print(f"Found video: {best_match_video['title']} (ID: {best_match_video['videoId']})")
                    return best_match_video['videoId']

        print(f"Could not find a suitable match for '{query}' on YouTube Music.")
        return None
    except Exception as e:
        print(f"Error searching on YouTube Music for '{query}': {e}")
        return None

def create_ytmusic_playlist(ytmusic, playlist_name, video_ids, description=""):
    """Creates a new playlist on YouTube Music and adds songs to it."""
    if not video_ids:
        print("No video IDs to add to the playlist.")
        return None
    try:
        print(f"\nCreating YouTube Music playlist: '{playlist_name}'...")
        playlist_id = ytmusic.create_playlist(
            title=playlist_name,
            description=description,
            privacy_status="PRIVATE" # Or "PUBLIC" or "UNLISTED"
        )
        print(f"Playlist '{playlist_name}' created with ID: {playlist_id}")
        
        print(f"Adding {len(video_ids)} songs to the playlist...")
        status = ytmusic.add_playlist_items(playlist_id, video_ids, duplicates=True) # duplicates=True to add even if already there
        
        if status and isinstance(status, dict) and status.get('status') == 'SUCCEEDED':
             print("Successfully added all songs to the playlist.")
        elif status and isinstance(status, list): 
            print("Songs added to playlist (individual status not fully parsed).")
        else:
            print(f"Could not add all songs or status unknown. Response: {status}")
        return playlist_id
    except Exception as e:
        print(f"Error creating or adding songs to YouTube Music playlist: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Fetch songs from a Spotify playlist and create a YouTube Music playlist.")
    parser.add_argument("playlist_identifier", help="The ID, URL, or URI of the Spotify playlist.")
    parser.add_argument("-n", "--name", help="Name for the new YouTube Music playlist (defaults to Spotify playlist name if possible, or prompts).")
    parser.add_argument("-d", "--description", default="Created from Spotify playlist.", help="Description for the new YouTube Music playlist.")
    args = parser.parse_args()

    # --- Spotify Part ---
    client_id, client_secret, redirect_uri = load_credentials()
    sp = get_spotify_client(client_id, client_secret, redirect_uri)

    try:
        current_user = sp.current_user()
        print(f"Successfully authenticated with Spotify as {current_user['display_name'] if current_user else 'user'}.")
    except Exception as e:
        print(f"Spotify authentication failed: {e}")
        return

    spotify_playlist_name = "My Spotify Playlist" # Default
    try:
        # Attempt to get Spotify playlist name
        playlist_id_for_name = args.playlist_identifier
        if "open.spotify.com/playlist/" in playlist_id_for_name:
            playlist_id_for_name = playlist_id_for_name.split("/")[-1].split("?")[0]
        elif "spotify:playlist:" in playlist_id_for_name:
            playlist_id_for_name = playlist_id_for_name.split(":")[-1]
        
        spotify_playlist_data = sp.playlist(playlist_id_for_name, fields="name")
        if spotify_playlist_data and spotify_playlist_data.get('name'):
            spotify_playlist_name = spotify_playlist_data['name']
            print(f"Spotify playlist name: '{spotify_playlist_name}'")
    except Exception as e:
        print(f"Could not fetch Spotify playlist name, using default. Error: {e}")


    spotify_songs = get_playlist_tracks(sp, args.playlist_identifier)

    if not spotify_songs:
        print("No songs found from Spotify playlist or unable to fetch tracks.")
        return
    
    print(f"\n--- Found {len(spotify_songs)} songs in the Spotify playlist ---")
    for i, song in enumerate(spotify_songs, 1):
        print(f"{i}. {song['title']} by {song['artist']}")
    
    # --- YouTube Music Part ---
    ytmusic = initialize_ytmusic()
    if not ytmusic:
        print("Exiting due to YouTube Music authentication setup needed.")
        return

    yt_playlist_name = args.name
    if not yt_playlist_name:
        yt_playlist_name_prompt = input(f"\nEnter a name for the new YouTube Music playlist (default: '{spotify_playlist_name} on YTMusic'): ")
        yt_playlist_name = yt_playlist_name_prompt if yt_playlist_name_prompt else f"{spotify_playlist_name} on YTMusic"

    yt_video_ids = []
    print("\n--- Searching for songs on YouTube Music ---")
    for song in spotify_songs:
        video_id = search_song_on_ytmusic(ytmusic, song['title'], song['artist'])
        if video_id:
            yt_video_ids.append(video_id)
        else:
            print(f"Skipping '{song['title']} by {song['artist']}' as it was not found on YouTube Music.")
    
    if not yt_video_ids:
        print("\nNo songs were successfully found on YouTube Music. Cannot create playlist.")
        return

    create_ytmusic_playlist(ytmusic, yt_playlist_name, yt_video_ids, args.description)
    print("\nProcess finished.")


if __name__ == "__main__":
    main()

