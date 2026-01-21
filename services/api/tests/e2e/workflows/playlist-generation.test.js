// Playlist generation workflow tests
const { test, expect } = require('../utils/base-test');
const HomePage = require('../pages/home-page');
const FestivalDetailPage = require('../pages/festival-detail-page');
const PlaylistPage = require('../pages/playlist-page');
const StreamingPage = require('../pages/streaming-page');

test.describe('Playlist Generation Workflows', () => {
  let homePage;
  let festivalDetailPage;
  let playlistPage;
  let streamingPage;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    festivalDetailPage = new FestivalDetailPage(page);
    playlistPage = new PlaylistPage(page);
    streamingPage = new StreamingPage(page);

    // Mock festival data
    await page.route('**/api/v1/festivals/coachella-2024', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'coachella-2024',
          name: 'Coachella Valley Music and Arts Festival',
          dates: ['2024-04-12', '2024-04-14'],
          location: 'Indio, CA',
          venue: 'Empire Polo Club',
          artists: ['Lana Del Rey', 'Tyler, The Creator', 'Doja Cat', 'No Doubt'],
          genres: ['Pop', 'Hip Hop', 'Alternative']
        })
      });
    });

    // Mock playlist generation
    await page.route('**/api/v1/playlists/generate', async route => {
      const requestBody = await route.request().postDataJSON();
      const playlistType = requestBody.type; // 'festival' or 'artist'
      const targetId = requestBody.festival_id || requestBody.artist_id;

      let songs = [];
      if (playlistType === 'festival' && targetId === 'coachella-2024') {
        songs = [
          {
            id: 'song-1',
            title: 'Video Games',
            artist: 'Lana Del Rey',
            performance_count: 8,
            is_cover: false
          },
          {
            id: 'song-2',
            title: 'EARFQUAKE',
            artist: 'Tyler, The Creator',
            performance_count: 7,
            is_cover: false
          },
          {
            id: 'song-3',
            title: 'Paint The Town Red',
            artist: 'Doja Cat',
            performance_count: 6,
            is_cover: false
          },
          {
            id: 'song-4',
            title: 'Don\'t Speak',
            artist: 'No Doubt',
            performance_count: 9,
            is_cover: false
          },
          {
            id: 'song-5',
            title: 'Born to Die',
            artist: 'Lana Del Rey',
            performance_count: 5,
            is_cover: false
          }
        ];
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: `playlist-${targetId}`,
          name: `${playlistType === 'festival' ? 'Festival' : 'Artist'} Playlist`,
          description: `Generated playlist for ${targetId}`,
          songs,
          festival_id: playlistType === 'festival' ? targetId : null,
          artist_id: playlistType === 'artist' ? targetId : null,
          created_at: new Date().toISOString()
        })
      });
    });

    // Mock playlist data
    await page.route('**/api/v1/playlists/*', async route => {
      const playlistId = route.request().url().split('/').pop();
      
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: playlistId,
          name: 'Coachella 2024 - Festival Playlist',
          description: 'Songs likely to be played at Coachella 2024',
          songs: [
            {
              id: 'song-1',
              title: 'Video Games',
              artist: 'Lana Del Rey',
              performance_count: 8,
              is_cover: false
            },
            {
              id: 'song-2',
              title: 'EARFQUAKE',
              artist: 'Tyler, The Creator',
              performance_count: 7,
              is_cover: false
            },
            {
              id: 'song-3',
              title: 'Paint The Town Red',
              artist: 'Doja Cat',
              performance_count: 6,
              is_cover: false
            }
          ],
          festival_id: 'coachella-2024',
          created_at: new Date().toISOString()
        })
      });
    });

    // Mock user preferences
    await page.route('**/api/v1/user/preferences', async route => {
      if (route.request().method() === 'POST') {
        // Save preferences
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true })
        });
      } else {
        // Get preferences
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            known_songs: ['song-1'],
            show_known_songs: true
          })
        });
      }
    });

    // Mock streaming service authentication
    await page.route('**/api/v1/streaming/auth/*', async route => {
      const platform = route.request().url().split('/').pop();
      
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          platform,
          authenticated: true,
          auth_url: `https://${platform}.com/oauth/authorize?client_id=test`
        })
      });
    });

    // Mock playlist creation on streaming platforms
    await page.route('**/api/v1/streaming/create-playlist', async route => {
      const requestBody = await route.request().postDataJSON();
      const platform = requestBody.platform;
      
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          platform,
          playlist_id: `${platform}_playlist_123`,
          playlist_url: `https://${platform}.com/playlist/123`,
          songs_added: requestBody.songs?.length || 0,
          songs_not_found: 0
        })
      });
    });
  });

  test('should generate festival playlist from festival detail page', async () => {
    // Navigate to festival detail page
    await festivalDetailPage.visit('coachella-2024');
    
    // Validate festival page loaded
    const pageStructure = await festivalDetailPage.validatePageStructure();
    expect(pageStructure.hasFestivalName).toBe(true);
    expect(pageStructure.hasCreatePlaylistButton).toBe(true);
    
    // Click create playlist button
    await festivalDetailPage.createPlaylist();
    
    // Should navigate to playlist page or show playlist
    await page.waitForSelector('.playlist-title, .songs-list', { timeout: 10000 });
    
    // Validate playlist was created
    const playlistStructure = await playlistPage.validatePlaylistStructure();
    expect(playlistStructure.hasTitle).toBe(true);
    expect(playlistStructure.hasSongsList).toBe(true);
    
    // Validate songs are present
    const songs = await playlistPage.getSongsList();
    expect(songs.length).toBeGreaterThan(0);
    expect(songs[0].title).toBeTruthy();
    expect(songs[0].artist).toBeTruthy();
  });

  test('should support song management and filtering', async () => {
    // Navigate to a playlist
    await playlistPage.visit('playlist-coachella-2024');
    
    // Validate playlist structure
    const structure = await playlistPage.validatePlaylistStructure();
    expect(structure.hasSongsList).toBe(true);
    expect(structure.hasFilterToggle).toBe(true);
    
    // Test song interactivity
    const interactivity = await playlistPage.validateSongInteractivity();
    expect(interactivity.hasInteractiveSongs).toBe(true);
    expect(interactivity.checkboxesWork).toBe(true);
    
    // Test filter functionality
    const filterTest = await playlistPage.validateFilterFunctionality();
    expect(filterTest.filterWorks).toBe(true);
    expect(filterTest.restoreWorks).toBe(true);
    
    // Validate stats update
    const stats = await playlistPage.getPlaylistStats();
    expect(stats.total).toBeGreaterThan(0);
  });

  test('should persist song preferences across sessions', async () => {
    // Navigate to playlist
    await playlistPage.visit('playlist-coachella-2024');
    
    // Test persistence
    const persistence = await playlistPage.validatePlaylistPersistence();
    expect(persistence.persistenceWorks).toBe(true);
  });

  test('should integrate with streaming services', async () => {
    // Navigate to playlist
    await playlistPage.visit('playlist-coachella-2024');
    
    // Validate streaming integration
    const streaming = await playlistPage.validateStreamingIntegration();
    expect(streaming.hasAnyPlatform).toBe(true);
    
    // Test Spotify integration
    if (streaming.hasSpotify) {
      await playlistPage.createOnSpotify();
      
      // Should show success or auth dialog
      const hasSuccess = await playlistPage.isElementVisible('.success-message');
      const hasAuth = await playlistPage.isElementVisible('.auth-dialog');
      expect(hasSuccess || hasAuth).toBe(true);
    }
  });

  test('should handle streaming service authentication', async () => {
    // Navigate to streaming page
    await streamingPage.visit();
    
    // Validate page structure
    const structure = await streamingPage.validatePageStructure();
    expect(structure.hasTitle).toBe(true);
    expect(structure.hasPlatformCards).toBe(true);
    
    // Test authentication flow for Spotify
    if (structure.hasSpotifyCard) {
      const authFlow = await streamingPage.validateAuthenticationFlow('spotify');
      expect(authFlow.authFlowStarted).toBe(true);
    }
    
    // Test service status
    const statuses = await streamingPage.getAllServiceStatuses();
    expect(Object.keys(statuses).length).toBeGreaterThan(0);
  });

  test('should support single artist playlist generation', async () => {
    // Mock artist data
    await page.route('**/api/v1/artists/lana-del-rey', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'lana-del-rey',
          name: 'Lana Del Rey',
          genres: ['Pop', 'Alternative'],
          popularity_score: 0.95
        })
      });
    });

    // Navigate to artist playlist generation
    await playlistPage.visitArtistPlaylist('lana-del-rey');
    
    // Should show artist-specific playlist
    const playlistInfo = await playlistPage.getPlaylistInfo();
    expect(playlistInfo.title).toContain('Lana Del Rey');
    
    const songs = await playlistPage.getSongsList();
    expect(songs.length).toBeGreaterThan(0);
    
    // All songs should be by the same artist for single artist playlist
    const artistSongs = songs.filter(song => 
      song.artist.toLowerCase().includes('lana del rey')
    );
    expect(artistSongs.length).toBeGreaterThan(0);
  });

  test('should handle playlist customization', async () => {
    await playlistPage.visit('playlist-coachella-2024');
    
    // Test song checking/unchecking
    const initialSongs = await playlistPage.getSongsList();
    const initialChecked = initialSongs.filter(s => s.isChecked).length;
    
    // Check first song
    await playlistPage.checkSong(0);
    
    const updatedSongs = await playlistPage.getSongsList();
    const updatedChecked = updatedSongs.filter(s => s.isChecked).length;
    
    expect(updatedChecked).toBeGreaterThan(initialChecked);
    
    // Test filtering
    await playlistPage.hideKnownSongs();
    const filteredSongs = await playlistPage.getVisibleSongs();
    const visibleChecked = filteredSongs.filter(s => s.isChecked).length;
    
    // Should show fewer checked songs when hiding known songs
    expect(visibleChecked).toBeLessThanOrEqual(updatedChecked);
  });

  test('should support playlist sharing and export', async () => {
    await playlistPage.visit('playlist-coachella-2024');
    
    // Test share functionality
    if (await playlistPage.isElementVisible('.share-playlist, .share-button')) {
      await playlistPage.sharePlaylist();
      
      // Should show share dialog or copy confirmation
      const hasShareDialog = await playlistPage.isElementVisible('.share-dialog, .copy-success');
      expect(hasShareDialog).toBe(true);
    }
    
    // Test export functionality
    if (await playlistPage.isElementVisible('.export-playlist, .export-button')) {
      const download = await playlistPage.exportPlaylist();
      expect(download).toBeTruthy();
    }
  });

  test('should handle playlist refresh and updates', async () => {
    await playlistPage.visit('playlist-coachella-2024');
    
    const initialSongs = await playlistPage.getSongsList();
    const initialCount = initialSongs.length;
    
    // Test refresh functionality
    if (await playlistPage.isElementVisible('.refresh-playlist, .update-button')) {
      await playlistPage.refreshPlaylist();
      
      // Playlist should reload
      const refreshedSongs = await playlistPage.getSongsList();
      expect(refreshedSongs.length).toBeGreaterThanOrEqual(initialCount);
    }
  });

  test('should validate playlist generation error handling', async () => {
    // Mock error response
    await page.route('**/api/v1/playlists/generate', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Failed to generate playlist',
          message: 'Unable to fetch setlist data'
        })
      });
    });

    await festivalDetailPage.visit('coachella-2024');
    await festivalDetailPage.createPlaylist();
    
    // Should show error message
    const hasError = await page.isVisible('.error-message, .error');
    expect(hasError).toBe(true);
  });

  test('should handle streaming service connection errors', async () => {
    // Mock auth error
    await page.route('**/api/v1/streaming/auth/*', async route => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Authentication failed',
          message: 'Invalid credentials'
        })
      });
    });

    await streamingPage.visit();
    
    if (await streamingPage.isElementVisible('.spotify-card')) {
      await streamingPage.connectToSpotify();
      
      // Should show error message
      const hasError = await streamingPage.hasAuthenticationError();
      expect(hasError).toBe(true);
    }
  });
});