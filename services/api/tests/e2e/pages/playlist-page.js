// Playlist page object model
const BasePage = require('./base-page');

class PlaylistPage extends BasePage {
  constructor(page) {
    super(page);
  }

  // Selectors
  get playlistTitle() { return this.page.locator('.playlist-title, h1'); }
  get playlistDescription() { return this.page.locator('.playlist-description, .description'); }
  get songsList() { return this.page.locator('.songs-list, .playlist-songs'); }
  get songItems() { return this.page.locator('.song-item, .song-card'); }
  get songCheckboxes() { return this.page.locator('.song-checkbox, input[type="checkbox"]'); }
  get filterToggle() { return this.page.locator('.filter-toggle, .show-hide-toggle'); }
  get showKnownButton() { return this.page.locator('.show-known, .show-all'); }
  get hideKnownButton() { return this.page.locator('.hide-known, .hide-checked'); }
  get streamingButtons() { return this.page.locator('.streaming-button, .create-on-platform'); }
  get spotifyButton() { return this.page.locator('.spotify-button, [data-platform="spotify"]'); }
  get youtubeButton() { return this.page.locator('.youtube-button, [data-platform="youtube"]'); }
  get appleMusicButton() { return this.page.locator('.apple-music-button, [data-platform="apple_music"]'); }
  get shareButton() { return this.page.locator('.share-playlist, .share-button'); }
  get exportButton() { return this.page.locator('.export-playlist, .export-button'); }
  get refreshButton() { return this.page.locator('.refresh-playlist, .update-button'); }
  get playlistStats() { return this.page.locator('.playlist-stats, .stats-section'); }
  get totalSongs() { return this.page.locator('.total-songs, .song-count'); }
  get knownSongs() { return this.page.locator('.known-songs, .checked-count'); }
  get unknownSongs() { return this.page.locator('.unknown-songs, .unchecked-count'); }

  // Actions
  async visit(playlistId) {
    await this.goto(`/playlists/${playlistId}`);
  }

  async visitFestivalPlaylist(festivalId) {
    await this.goto(`/festivals/${festivalId}/playlist`);
  }

  async visitArtistPlaylist(artistId) {
    await this.goto(`/artists/${artistId}/playlist`);
  }

  async checkSong(songIndex) {
    const checkboxes = await this.songCheckboxes.all();
    if (checkboxes[songIndex]) {
      await checkboxes[songIndex].check();
      // Wait for UI update
      await this.page.waitForTimeout(500);
    }
  }

  async uncheckSong(songIndex) {
    const checkboxes = await this.songCheckboxes.all();
    if (checkboxes[songIndex]) {
      await checkboxes[songIndex].uncheck();
      // Wait for UI update
      await this.page.waitForTimeout(500);
    }
  }

  async toggleSong(songIndex) {
    const checkboxes = await this.songCheckboxes.all();
    if (checkboxes[songIndex]) {
      await checkboxes[songIndex].click();
      // Wait for UI update
      await this.page.waitForTimeout(500);
    }
  }

  async toggleKnownSongsVisibility() {
    await this.filterToggle.click();
    // Wait for filter animation
    await this.page.waitForTimeout(500);
  }

  async showAllSongs() {
    if (await this.isElementVisible('.show-known, .show-all')) {
      await this.showKnownButton.click();
      await this.page.waitForTimeout(500);
    }
  }

  async hideKnownSongs() {
    if (await this.isElementVisible('.hide-known, .hide-checked')) {
      await this.hideKnownButton.click();
      await this.page.waitForTimeout(500);
    }
  }

  async createOnSpotify() {
    await this.spotifyButton.click();
    // Wait for authentication or creation process
    await this.page.waitForSelector('.success-message, .auth-dialog, .error-message', { timeout: 10000 });
  }

  async createOnYouTube() {
    await this.youtubeButton.click();
    await this.page.waitForSelector('.success-message, .auth-dialog, .error-message', { timeout: 10000 });
  }

  async createOnAppleMusic() {
    await this.appleMusicButton.click();
    await this.page.waitForSelector('.success-message, .auth-dialog, .error-message', { timeout: 10000 });
  }

  async sharePlaylist() {
    await this.shareButton.click();
    await this.page.waitForSelector('.share-dialog, .copy-success', { timeout: 5000 });
  }

  async exportPlaylist() {
    const [download] = await Promise.all([
      this.page.waitForEvent('download'),
      this.exportButton.click()
    ]);
    return download;
  }

  async refreshPlaylist() {
    await this.refreshButton.click();
    await this.waitForPageLoad();
  }

  // Validation methods
  async getPlaylistInfo() {
    const title = await this.playlistTitle.textContent();
    let description = '';
    if (await this.isElementVisible('.playlist-description, .description')) {
      description = await this.playlistDescription.textContent();
    }
    return { title, description };
  }

  async getSongsList() {
    const songElements = await this.songItems.all();
    const songs = [];

    for (const element of songElements) {
      const title = await element.locator('.song-title, .title').textContent();
      const artist = await element.locator('.song-artist, .artist').textContent();
      const isChecked = await element.locator('.song-checkbox, input[type="checkbox"]').isChecked();
      const isVisible = await element.isVisible();
      
      songs.push({ title, artist, isChecked, isVisible });
    }

    return songs;
  }

  async getVisibleSongs() {
    const allSongs = await this.getSongsList();
    return allSongs.filter(song => song.isVisible);
  }

  async getCheckedSongs() {
    const allSongs = await this.getSongsList();
    return allSongs.filter(song => song.isChecked);
  }

  async getUncheckedSongs() {
    const allSongs = await this.getSongsList();
    return allSongs.filter(song => !song.isChecked);
  }

  async getPlaylistStats() {
    const stats = {};
    
    if (await this.isElementVisible('.total-songs, .song-count')) {
      const totalText = await this.totalSongs.textContent();
      stats.total = parseInt(totalText.match(/\d+/)?.[0] || '0');
    }
    
    if (await this.isElementVisible('.known-songs, .checked-count')) {
      const knownText = await this.knownSongs.textContent();
      stats.known = parseInt(knownText.match(/\d+/)?.[0] || '0');
    }
    
    if (await this.isElementVisible('.unknown-songs, .unchecked-count')) {
      const unknownText = await this.unknownSongs.textContent();
      stats.unknown = parseInt(unknownText.match(/\d+/)?.[0] || '0');
    }

    return stats;
  }

  async validatePlaylistStructure() {
    return {
      hasTitle: await this.isElementVisible('.playlist-title, h1'),
      hasSongsList: await this.isElementVisible('.songs-list, .playlist-songs'),
      hasFilterToggle: await this.isElementVisible('.filter-toggle, .show-hide-toggle'),
      hasStreamingButtons: await this.isElementVisible('.streaming-button, .create-on-platform'),
      hasShareButton: await this.isElementVisible('.share-playlist, .share-button'),
      hasStats: await this.isElementVisible('.playlist-stats, .stats-section')
    };
  }

  async validateSongInteractivity() {
    const songs = await this.getSongsList();
    if (songs.length === 0) return { hasInteractiveSongs: false };

    // Test first song checkbox
    const initialState = songs[0].isChecked;
    await this.toggleSong(0);
    
    // Wait and check if state changed
    await this.page.waitForTimeout(1000);
    const updatedSongs = await this.getSongsList();
    const newState = updatedSongs[0].isChecked;

    return {
      hasInteractiveSongs: true,
      checkboxesWork: initialState !== newState,
      songsCount: songs.length
    };
  }

  async validateFilterFunctionality() {
    const initialSongs = await this.getVisibleSongs();
    const initialCount = initialSongs.length;

    // Check some songs first
    await this.checkSong(0);
    if (initialCount > 1) {
      await this.checkSong(1);
    }

    // Toggle filter to hide known songs
    await this.hideKnownSongs();
    
    const filteredSongs = await this.getVisibleSongs();
    const filteredCount = filteredSongs.length;

    // Show all songs again
    await this.showAllSongs();
    
    const restoredSongs = await this.getVisibleSongs();
    const restoredCount = restoredSongs.length;

    return {
      initialCount,
      filteredCount,
      restoredCount,
      filterWorks: filteredCount < initialCount,
      restoreWorks: restoredCount === initialCount
    };
  }

  async validateStreamingIntegration() {
    const hasSpotify = await this.isElementVisible('.spotify-button, [data-platform="spotify"]');
    const hasYouTube = await this.isElementVisible('.youtube-button, [data-platform="youtube"]');
    const hasAppleMusic = await this.isElementVisible('.apple-music-button, [data-platform="apple_music"]');

    return {
      hasSpotify,
      hasYouTube,
      hasAppleMusic,
      hasAnyPlatform: hasSpotify || hasYouTube || hasAppleMusic
    };
  }

  async validatePlaylistPersistence() {
    // Check some songs
    await this.checkSong(0);
    await this.checkSong(1);
    
    const checkedBefore = await this.getCheckedSongs();
    
    // Refresh page
    await this.page.reload();
    await this.waitForPageLoad();
    
    const checkedAfter = await this.getCheckedSongs();
    
    return {
      persistenceWorks: checkedBefore.length === checkedAfter.length,
      checkedBefore: checkedBefore.length,
      checkedAfter: checkedAfter.length
    };
  }
}

module.exports = PlaylistPage;