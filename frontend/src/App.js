import React, { useState, useEffect } from 'react';
import './App.css';
import logo from './logo.svg';

// Define the base URL for Django backend API
const API_BASE_URL = 'https://3858-209-6-206-102.ngrok-free.app/api/v1';

function App() {
  const [spotifyPlaylistUrl, setSpotifyPlaylistUrl] = useState('');
  const [ytPlaylistName, setYtPlaylistName] = useState('');
  const [message, setMessage] = useState('');
  const [spotifyAuthStatus, setSpotifyAuthStatus] = useState('Not Authenticated');
  const [ytMusicAuthStatus, setYtMusicAuthStatus] = useState('Not Authenticated');

  // Check for stored tokens on component mount
  useEffect(() => {
    const spotifyToken = localStorage.getItem('spotify_token');
    const ytMusicToken = localStorage.getItem('ytmusic_token');
    
    if (spotifyToken) {
      setSpotifyAuthStatus('Authenticated');
    }
    if (ytMusicToken) {
      setYtMusicAuthStatus('Authenticated');
    }
    
    if (spotifyToken && ytMusicToken) {
      setMessage('Both services authenticated! You can now transfer playlists.');
    } else if (spotifyToken || ytMusicToken) {
      setMessage('Partial authentication complete. Please authenticate with both services.');
    } else {
      setMessage('Welcome! Please authenticate with Spotify and YouTube Music.');
    }
  }, []);

  // Handle OAuth redirects with tokens
  useEffect(() => {
    const queryParams = new URLSearchParams(window.location.search);
    
    // Handle Spotify auth success
    if (queryParams.get('spotify_auth') === 'success') {
      const encodedToken = queryParams.get('token');
      if (encodedToken) {
        try {
          const tokenJson = atob(encodedToken); // Base64 decode
          const tokenInfo = JSON.parse(tokenJson);
          localStorage.setItem('spotify_token', JSON.stringify(tokenInfo));
          setSpotifyAuthStatus('Authenticated');
          setMessage('Spotify authentication successful! Now authenticate with YouTube Music.');
          console.log('Spotify token stored successfully');
        } catch (error) {
          console.error('Error parsing Spotify token:', error);
          setMessage('Error processing Spotify authentication. Please try again.');
        }
      }
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // Handle YouTube Music auth success
    if (queryParams.get('ytmusic_auth') === 'success') {
      const encodedToken = queryParams.get('token');
      if (encodedToken) {
        try {
          const tokenJson = atob(encodedToken); // Base64 decode
          const tokenInfo = JSON.parse(tokenJson);
          localStorage.setItem('ytmusic_token', JSON.stringify(tokenInfo));
          setYtMusicAuthStatus('Authenticated');
          setMessage('YouTube Music authentication successful! You can now transfer playlists.');
          console.log('YouTube Music token stored successfully');
        } catch (error) {
          console.error('Error parsing YouTube Music token:', error);
          setMessage('Error processing YouTube Music authentication. Please try again.');
        }
      }
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // Handle authentication errors
    const error = queryParams.get('error');
    if (error) {
      const errorMessage = queryParams.get('message') || 'Authentication failed';
      setMessage(`Authentication Error: ${errorMessage}`);
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const handleSpotifyAuth = () => {
    setMessage('Redirecting to Spotify for authentication...');
    window.location.href = `${API_BASE_URL}/spotify/authorize/`;
  };

  const handleYouTubeMusicAuth = () => {
    setMessage('Redirecting to Google for YouTube Music authentication...');
    window.location.href = `${API_BASE_URL}/ytmusic/authorize/`;
  };

  const handleTransfer = async () => {
    if (!spotifyPlaylistUrl) {
      setMessage('Please enter a Spotify Playlist URL or ID.');
      return;
    }
    
    // Get tokens from localStorage
    const spotifyTokenStr = localStorage.getItem('spotify_token');
    const ytMusicTokenStr = localStorage.getItem('ytmusic_token');
    
    if (!spotifyTokenStr) {
      setMessage('Spotify not authenticated. Please authenticate with Spotify first.');
      return;
    }
    
    if (!ytMusicTokenStr) {
      setMessage('YouTube Music not authenticated. Please authenticate with YouTube Music first.');
      return;
    }
    
    let spotifyToken, ytMusicToken;
    try {
      spotifyToken = JSON.parse(spotifyTokenStr);
      ytMusicToken = JSON.parse(ytMusicTokenStr);
    } catch (error) {
      setMessage('Error parsing stored tokens. Please re-authenticate.');
      localStorage.removeItem('spotify_token');
      localStorage.removeItem('ytmusic_token');
      setSpotifyAuthStatus('Not Authenticated');
      setYtMusicAuthStatus('Not Authenticated');
      return;
    }
    
    setMessage('Starting playlist transfer...');

    try {
      const response = await fetch(`${API_BASE_URL}/transfer/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          playlist_identifier: spotifyPlaylistUrl,
          yt_playlist_name: ytPlaylistName || undefined,
          spotify_token: spotifyToken,
          ytmusic_token: ytMusicToken,
        }),
        credentials: 'include',
      });

      const data = await response.json();

      if (response.ok) {
        let successMsg = data.message || 'Playlist transfer process completed.';
        if (data.playlist_id) {
          successMsg += ` YouTube Music Playlist ID: ${data.playlist_id}.`;
        }
        if (data.songs_added_count !== undefined) {
          successMsg += ` Songs processed/added: ${data.songs_added_count}/${data.spotify_track_count}.`;
        }
        if (data.warning) {
          successMsg = `${data.warning} (Details: ${JSON.stringify(data.status_from_ytmusicapi)})`;
        }
        setMessage(successMsg);
        if (data.not_found_log && data.not_found_log.length > 0) {
          console.warn("Songs not found:", data.not_found_log);
        }
      } else {
        setMessage(`Error: ${data.error || data.detail || 'Unknown error during transfer.'} (Status: ${response.status})`);
        
        // If authentication error, clear tokens
        if (response.status === 401) {
          localStorage.removeItem('spotify_token');
          localStorage.removeItem('ytmusic_token');
          setSpotifyAuthStatus('Not Authenticated');
          setYtMusicAuthStatus('Not Authenticated');
        }
      }
    } catch (error) {
      console.error('Transfer request failed:', error);
      setMessage(`Transfer request failed: ${error.message}. Check console for details.`);
    }
  };

  const handleClearAuth = () => {
    localStorage.removeItem('spotify_token');
    localStorage.removeItem('ytmusic_token');
    setSpotifyAuthStatus('Not Authenticated');
    setYtMusicAuthStatus('Not Authenticated');
    setMessage('Authentication cleared. Please re-authenticate with both services.');
  };

  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        <h1>Spotify to YouTube Music Playlist Transfer</h1>
      </header>
      <main>
        <section className="auth-section">
          <div>
            <button onClick={handleSpotifyAuth}>
              1. Authenticate with Spotify
            </button>
            <span>Status: {spotifyAuthStatus}</span>
          </div>
          <div>
            <button onClick={handleYouTubeMusicAuth}>
              2. Authenticate with YouTube Music
            </button>
            <span>Status: {ytMusicAuthStatus}</span>
          </div>
          <div>
            <button onClick={handleClearAuth}>
              Clear Authentication
            </button>
          </div>
        </section>

        <section className="transfer-section">
          <div>
            <label htmlFor="spotify-url">Spotify Playlist URL or ID:</label>
            <input
              type="text"
              id="spotify-url"
              value={spotifyPlaylistUrl}
              onChange={(e) => setSpotifyPlaylistUrl(e.target.value)}
              placeholder="Enter Spotify Playlist URL or ID"
            />
          </div>
          <div>
            <label htmlFor="yt-playlist-name">Optional: YouTube Music Playlist Name:</label>
            <input
              type="text"
              id="yt-playlist-name"
              value={ytPlaylistName}
              onChange={(e) => setYtPlaylistName(e.target.value)}
              placeholder="Defaults to Spotify playlist name"
            />
          </div>
          <button 
            onClick={handleTransfer} 
            disabled={!spotifyPlaylistUrl || spotifyAuthStatus === 'Not Authenticated' || ytMusicAuthStatus === 'Not Authenticated'}
          >
            3. Transfer Playlist
          </button>
        </section>

        {message && (
          <section className="message-section">
            <p>{message}</p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
