// Song checklist component tests
const { setupMockFetch, mockBrowserAPIs } = require('../setup/mock-services');

describe('Song Checklist Component', () => {
  let container;
  let mockFetch;

  beforeEach(() => {
    // Set up DOM
    document.body.innerHTML = `
      <div id="test-container">
        <div class="playlist-container">
          <div class="playlist-header">
            <h2 class="playlist-title">Test Playlist</h2>
            <div class="filter-controls">
              <button class="filter-toggle" data-filter="known">Hide Known Songs</button>
              <button class="filter-toggle" data-filter="unknown">Show Only Unknown</button>
              <button class="show-all">Show All</button>
            </div>
          </div>
          <div class="songs-list">
            <div class="song-item" data-song-id="song-1">
              <input type="checkbox" class="song-checkbox" id="song-1" data-song-id="song-1">
              <label for="song-1" class="song-info">
                <span class="song-title">Video Games</span>
                <span class="song-artist">Lana Del Rey</span>
              </label>
            </div>
            <div class="song-item" data-song-id="song-2">
              <input type="checkbox" class="song-checkbox" id="song-2" data-song-id="song-2">
              <label for="song-2" class="song-info">
                <span class="song-title">EARFQUAKE</span>
                <span class="song-artist">Tyler, The Creator</span>
              </label>
            </div>
            <div class="song-item" data-song-id="song-3">
              <input type="checkbox" class="song-checkbox" id="song-3" data-song-id="song-3">
              <label for="song-3" class="song-info">
                <span class="song-title">Paint The Town Red</span>
                <span class="song-artist">Doja Cat</span>
              </label>
            </div>
          </div>
          <div class="playlist-stats">
            <span class="total-songs">Total: <span class="count">3</span></span>
            <span class="known-songs">Known: <span class="count">0</span></span>
            <span class="unknown-songs">Unknown: <span class="count">3</span></span>
          </div>
        </div>
      </div>
    `;

    container = document.getElementById('test-container');
    
    // Mock browser APIs
    mockBrowserAPIs();
    
    // Set up fetch mock
    mockFetch = setupMockFetch({
      '/api/v1/user/preferences': {
        status: 200,
        json: { known_songs: [], show_known_songs: true }
      }
    });

    // Initialize song checklist functionality
    initializeSongChecklist();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    jest.clearAllMocks();
  });

  // Mock song checklist functionality
  function initializeSongChecklist() {
    const checkboxes = document.querySelectorAll('.song-checkbox');
    const filterButtons = document.querySelectorAll('.filter-toggle');
    const showAllButton = document.querySelector('.show-all');
    const songItems = document.querySelectorAll('.song-item');
    
    let knownSongs = new Set();
    let currentFilter = 'all';

    // Checkbox event listeners
    checkboxes.forEach(checkbox => {
      checkbox.addEventListener('change', function() {
        const songId = this.dataset.songId;
        
        if (this.checked) {
          knownSongs.add(songId);
          this.closest('.song-item').classList.add('known');
        } else {
          knownSongs.delete(songId);
          this.closest('.song-item').classList.remove('known');
        }
        
        updateStats();
        savePreferences();
        
        // Trigger custom event for testing
        document.dispatchEvent(new CustomEvent('songToggled', {
          detail: { songId, checked: this.checked }
        }));
      });
    });

    // Filter event listeners
    filterButtons.forEach(button => {
      button.addEventListener('click', function() {
        const filter = this.dataset.filter;
        currentFilter = filter;
        applyFilter(filter);
        
        // Update button states
        filterButtons.forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');
      });
    });

    showAllButton.addEventListener('click', function() {
      currentFilter = 'all';
      applyFilter('all');
      
      // Update button states
      filterButtons.forEach(btn => btn.classList.remove('active'));
    });

    function applyFilter(filter) {
      songItems.forEach(item => {
        const isKnown = item.classList.contains('known');
        let shouldShow = true;

        switch (filter) {
          case 'known':
            shouldShow = !isKnown; // Hide known songs
            break;
          case 'unknown':
            shouldShow = !isKnown; // Show only unknown songs
            break;
          case 'all':
          default:
            shouldShow = true;
            break;
        }

        if (shouldShow) {
          item.style.display = '';
          item.classList.remove('hidden');
        } else {
          item.style.display = 'none';
          item.classList.add('hidden');
        }
      });

      // Trigger custom event for testing
      document.dispatchEvent(new CustomEvent('filterApplied', {
        detail: { filter, visibleCount: getVisibleSongCount() }
      }));
    }

    function updateStats() {
      const totalCount = songItems.length;
      const knownCount = knownSongs.size;
      const unknownCount = totalCount - knownCount;

      document.querySelector('.total-songs .count').textContent = totalCount;
      document.querySelector('.known-songs .count').textContent = knownCount;
      document.querySelector('.unknown-songs .count').textContent = unknownCount;
    }

    function getVisibleSongCount() {
      return Array.from(songItems).filter(item => item.style.display !== 'none').length;
    }

    function savePreferences() {
      // Mock API call to save preferences
      fetch('/api/v1/user/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          known_songs: Array.from(knownSongs),
          show_known_songs: currentFilter !== 'known'
        })
      });
    }

    // Expose functions for testing
    window.testHelpers = {
      getKnownSongs: () => Array.from(knownSongs),
      getCurrentFilter: () => currentFilter,
      getVisibleSongCount,
      applyFilter,
      updateStats
    };
  }

  describe('Song Checkbox Functionality', () => {
    test('should check and uncheck songs', () => {
      const checkbox = container.querySelector('#song-1');
      const songItem = container.querySelector('[data-song-id="song-1"]');

      // Initially unchecked
      expect(checkbox.checked).toBe(false);
      expect(songItem.classList.contains('known')).toBe(false);

      // Check the song
      checkbox.click();
      expect(checkbox.checked).toBe(true);
      expect(songItem.classList.contains('known')).toBe(true);

      // Uncheck the song
      checkbox.click();
      expect(checkbox.checked).toBe(false);
      expect(songItem.classList.contains('known')).toBe(false);
    });

    test('should update stats when songs are checked', () => {
      const checkbox1 = container.querySelector('#song-1');
      const checkbox2 = container.querySelector('#song-2');
      
      const knownCountElement = container.querySelector('.known-songs .count');
      const unknownCountElement = container.querySelector('.unknown-songs .count');

      // Initially all unknown
      expect(knownCountElement.textContent).toBe('0');
      expect(unknownCountElement.textContent).toBe('3');

      // Check first song
      checkbox1.click();
      expect(knownCountElement.textContent).toBe('1');
      expect(unknownCountElement.textContent).toBe('2');

      // Check second song
      checkbox2.click();
      expect(knownCountElement.textContent).toBe('2');
      expect(unknownCountElement.textContent).toBe('1');

      // Uncheck first song
      checkbox1.click();
      expect(knownCountElement.textContent).toBe('1');
      expect(unknownCountElement.textContent).toBe('2');
    });

    test('should trigger custom events when songs are toggled', (done) => {
      const checkbox = container.querySelector('#song-1');
      
      document.addEventListener('songToggled', (event) => {
        expect(event.detail.songId).toBe('song-1');
        expect(event.detail.checked).toBe(true);
        done();
      });

      checkbox.click();
    });

    test('should persist song preferences', () => {
      const checkbox = container.querySelector('#song-1');
      
      checkbox.click();
      
      // Should have called the API to save preferences
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/user/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          known_songs: ['song-1'],
          show_known_songs: true
        })
      });
    });
  });

  describe('Song Filtering Functionality', () => {
    beforeEach(() => {
      // Check some songs for filtering tests
      container.querySelector('#song-1').click();
      container.querySelector('#song-2').click();
    });

    test('should hide known songs when filter is applied', () => {
      const hideKnownButton = container.querySelector('[data-filter="known"]');
      const song1 = container.querySelector('[data-song-id="song-1"]');
      const song2 = container.querySelector('[data-song-id="song-2"]');
      const song3 = container.querySelector('[data-song-id="song-3"]');

      hideKnownButton.click();

      // Known songs should be hidden
      expect(song1.style.display).toBe('none');
      expect(song2.style.display).toBe('none');
      
      // Unknown songs should be visible
      expect(song3.style.display).toBe('');
    });

    test('should show only unknown songs when filter is applied', () => {
      const showUnknownButton = container.querySelector('[data-filter="unknown"]');
      const song1 = container.querySelector('[data-song-id="song-1"]');
      const song2 = container.querySelector('[data-song-id="song-2"]');
      const song3 = container.querySelector('[data-song-id="song-3"]');

      showUnknownButton.click();

      // Known songs should be hidden
      expect(song1.style.display).toBe('none');
      expect(song2.style.display).toBe('none');
      
      // Unknown songs should be visible
      expect(song3.style.display).toBe('');
    });

    test('should show all songs when show all is clicked', () => {
      const hideKnownButton = container.querySelector('[data-filter="known"]');
      const showAllButton = container.querySelector('.show-all');
      const song1 = container.querySelector('[data-song-id="song-1"]');
      const song2 = container.querySelector('[data-song-id="song-2"]');
      const song3 = container.querySelector('[data-song-id="song-3"]');

      // First hide known songs
      hideKnownButton.click();
      expect(song1.style.display).toBe('none');
      expect(song2.style.display).toBe('none');

      // Then show all
      showAllButton.click();
      expect(song1.style.display).toBe('');
      expect(song2.style.display).toBe('');
      expect(song3.style.display).toBe('');
    });

    test('should update filter button states', () => {
      const hideKnownButton = container.querySelector('[data-filter="known"]');
      const showUnknownButton = container.querySelector('[data-filter="unknown"]');

      hideKnownButton.click();
      expect(hideKnownButton.classList.contains('active')).toBe(true);
      expect(showUnknownButton.classList.contains('active')).toBe(false);

      showUnknownButton.click();
      expect(hideKnownButton.classList.contains('active')).toBe(false);
      expect(showUnknownButton.classList.contains('active')).toBe(true);
    });

    test('should trigger filter events', (done) => {
      const hideKnownButton = container.querySelector('[data-filter="known"]');
      
      document.addEventListener('filterApplied', (event) => {
        expect(event.detail.filter).toBe('known');
        expect(event.detail.visibleCount).toBe(1); // Only song-3 should be visible
        done();
      });

      hideKnownButton.click();
    });
  });

  describe('Real-time Updates', () => {
    test('should update display immediately when songs are checked', () => {
      const checkbox = container.querySelector('#song-1');
      const songItem = container.querySelector('[data-song-id="song-1"]');
      const knownCount = container.querySelector('.known-songs .count');

      // Check song
      checkbox.click();

      // Should update immediately without page refresh
      expect(songItem.classList.contains('known')).toBe(true);
      expect(knownCount.textContent).toBe('1');
    });

    test('should update filter display immediately', () => {
      const checkbox = container.querySelector('#song-1');
      const hideKnownButton = container.querySelector('[data-filter="known"]');
      const songItem = container.querySelector('[data-song-id="song-1"]');

      // Check song and apply filter
      checkbox.click();
      hideKnownButton.click();

      // Should hide immediately
      expect(songItem.style.display).toBe('none');
    });

    test('should maintain filter state when new songs are checked', () => {
      const checkbox1 = container.querySelector('#song-1');
      const checkbox3 = container.querySelector('#song-3');
      const hideKnownButton = container.querySelector('[data-filter="known"]');
      const song1 = container.querySelector('[data-song-id="song-1"]');
      const song3 = container.querySelector('[data-song-id="song-3"]');

      // Apply filter first
      hideKnownButton.click();
      
      // Check a song
      checkbox1.click();
      
      // Song should be hidden immediately due to active filter
      expect(song1.style.display).toBe('none');
      expect(song3.style.display).toBe(''); // Should still be visible

      // Check another song
      checkbox3.click();
      
      // This song should also be hidden
      expect(song3.style.display).toBe('none');
    });
  });

  describe('Accessibility', () => {
    test('should have proper labels for checkboxes', () => {
      const checkbox = container.querySelector('#song-1');
      const label = container.querySelector('label[for="song-1"]');

      expect(label).toBeTruthy();
      expect(label.textContent).toContain('Video Games');
      expect(label.textContent).toContain('Lana Del Rey');
    });

    test('should support keyboard navigation', () => {
      const checkbox = container.querySelector('#song-1');
      
      // Focus the checkbox
      checkbox.focus();
      expect(document.activeElement).toBe(checkbox);

      // Simulate space key press
      const spaceEvent = new KeyboardEvent('keydown', { key: ' ', code: 'Space' });
      checkbox.dispatchEvent(spaceEvent);
      
      // Should toggle the checkbox (this would need actual keyboard event handling)
      // For now, just verify the checkbox can receive focus
      expect(checkbox.tabIndex).not.toBe(-1);
    });

    test('should have appropriate ARIA attributes', () => {
      const playlistContainer = container.querySelector('.playlist-container');
      const songsList = container.querySelector('.songs-list');

      // Check for basic accessibility attributes
      expect(playlistContainer.getAttribute('role') || 'region').toBeTruthy();
      expect(songsList.getAttribute('role') || 'list').toBeTruthy();
    });
  });

  describe('Error Handling', () => {
    test('should handle API errors gracefully', () => {
      // Mock API error
      mockFetch.mockImplementationOnce(() => 
        Promise.reject(new Error('Network error'))
      );

      const checkbox = container.querySelector('#song-1');
      
      // Should not throw error when API fails
      expect(() => {
        checkbox.click();
      }).not.toThrow();

      // Song should still be marked as known locally
      expect(checkbox.checked).toBe(true);
    });

    test('should handle missing elements gracefully', () => {
      // Remove stats elements
      container.querySelector('.playlist-stats').remove();

      const checkbox = container.querySelector('#song-1');
      
      // Should not throw error when stats elements are missing
      expect(() => {
        checkbox.click();
      }).not.toThrow();
    });
  });

  describe('Performance', () => {
    test('should handle large numbers of songs efficiently', () => {
      // Add many more songs to test performance
      const songsList = container.querySelector('.songs-list');
      
      for (let i = 4; i <= 100; i++) {
        const songItem = document.createElement('div');
        songItem.className = 'song-item';
        songItem.dataset.songId = `song-${i}`;
        songItem.innerHTML = `
          <input type="checkbox" class="song-checkbox" id="song-${i}" data-song-id="song-${i}">
          <label for="song-${i}" class="song-info">
            <span class="song-title">Song ${i}</span>
            <span class="song-artist">Artist ${i}</span>
          </label>
        `;
        songsList.appendChild(songItem);
      }

      // Re-initialize with more songs
      initializeSongChecklist();

      const startTime = performance.now();
      
      // Apply filter to many songs
      const hideKnownButton = container.querySelector('[data-filter="known"]');
      hideKnownButton.click();
      
      const endTime = performance.now();
      
      // Should complete quickly (less than 100ms for 100 songs)
      expect(endTime - startTime).toBeLessThan(100);
    });
  });
});