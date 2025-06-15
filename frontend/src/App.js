import React, { useState, useEffect } from 'react';
import './App.css';
import logo from './logo.svg';

// Define the base URL for your Django backend API
const API_BASE_URL = 'https://3858-209-6-206-102.ngrok-free.app/api/v1'; // Adjust if your Django server runs elsewhere

function App() {
  const [spotifyPlaylistUrl, setSpotifyPlaylistUrl] = useState('');
  const [ytPlaylistName, setYtPlaylistName] = useState(''); // Optional: for custom YT playlist name
  const [message, setMessage] = useState('');
  const [spotifyAuthStatus, setSpotifyAuthStatus] = useState('Not Authenticated');
  const [ytMusicAuthStatus, setYtMusicAuthStatus] = useState('Not Authenticated');

  // Simple function to check auth status (can be expanded)
  // This is a placeholder; real auth status check would involve backend calls
  // or checking for specific cookies/session info if frontend could access it (not typical for httpOnly session cookies)
  useEffect(() => {
    // For this basic example, we don't have a direct way to check session status from frontend
    // without making an API call. We'll rely on user actions and backend responses.
    // A more advanced app might have an endpoint like /api/v1/auth/status
    setMessage('Welcome! Please authenticate with Spotify and YouTube Music.');
  }, []);


  const handleSpotifyAuth = () => {
    setMessage('Redirecting to Spotify for authentication...');
    // The backend will handle the redirect to Spotify's authorization page
    window.location.href = `${API_BASE_URL}/spotify/authorize/`;
  };

  const handleYouTubeMusicAuth = () => {
    setMessage('Redirecting to Google for YouTube Music authentication...');
    // The backend will handle the redirect to Google's authorization page
    window.location.href = `${API_BASE_URL}/ytmusic/authorize/`;
  };

  const handleTransfer = async () => {
    if (!spotifyPlaylistUrl) {
      setMessage('Please enter a Spotify Playlist URL or ID.');
      return;
    }
    setMessage('Starting playlist transfer...');

    try {
      const response = await fetch(`${API_BASE_URL}/transfer/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // If you implement CSRF protection on Django for POST, you'd need to include the CSRF token here.
          // For session-based auth, Django usually handles this if requests are from the same domain
          // or if you configure CSRF trusted origins. For API calls from a different port (like React dev server),
          // you might need to ensure CSRF is handled (e.g., by getting a token first).
          // For simplicity now, we assume session auth handles it or CSRF is not strictly enforced on this API endpoint yet.
        },
        body: JSON.stringify({
          playlist_identifier: spotifyPlaylistUrl,
          yt_playlist_name: ytPlaylistName || undefined, // Send if user provided a name
        }),
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
            // Optionally display these to the user
        }
      } else {
        setMessage(`Error: ${data.error || data.detail || 'Unknown error during transfer.'} (Status: ${response.status})`);
      }
    } catch (error) {
      console.error('Transfer request failed:', error);
      setMessage(`Transfer request failed: ${error.message}. Check console for details.`);
    }
  };

  // This is a simple way to update status after redirecting back from OAuth
  // In a real app, you'd have proper routing and state management.
  useEffect(() => {
    const queryParams = new URLSearchParams(window.location.search);
    if (queryParams.get('spotify_auth') === 'success') {
      setSpotifyAuthStatus('Authenticated (Assumed after redirect)');
      setMessage('Spotify authentication likely successful! You can now try YouTube Music auth or transfer.');
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    if (queryParams.get('ytmusic_auth') === 'success') {
      setYtMusicAuthStatus('Authenticated (Assumed after redirect)');
      setMessage('YouTube Music authentication likely successful! You can now proceed to transfer.');
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);


  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        <h1>Spotify to YouTube Music Playlist Transfer</h1>
      </header>
      <main>
        <section className="auth-section">
          <div>
            <button onClick={handleSpotifyAuth}>1. Authenticate with Spotify</button>
            {/* Basic status display, not dynamically updated from backend session in this simple version */}
            {/* <span>Status: {spotifyAuthStatus}</span> */}
          </div>
          <div>
            <button onClick={handleYouTubeMusicAuth}>2. Authenticate with YouTube Music</button>
            {/* <span>Status: {ytMusicAuthStatus}</span> */}
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
          <button onClick={handleTransfer} disabled={!spotifyPlaylistUrl}>
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
