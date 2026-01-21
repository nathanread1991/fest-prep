// Playlist-specific JavaScript functionality
// Handles interactive checklist, filtering, and real-time updates

class PlaylistManager {
    constructor() {
        this.knownSongs = new Set();
        this.currentFilter = 'all';
        this.hideKnownSongs = false;
        this.searchTerm = '';
        this.selectedArtist = '';
        this.isOffline = !navigator.onLine;
        
        this.init();
    }
    
    init() {
        this.loadUserPreferences();
        this.setupEventListeners();
        this.populateArtistFilter();
        this.setupOfflineHandling();
    }
    
    // Load user preferences from API or localStorage
    async loadUserPreferences() {
        try {
            // Try to load from API first
            const response = await fetch('/api/v1/user/preferences');
            if (response.ok) {
                const data = await response.json();
                this.knownSongs = new Set(data.known_songs || []);
            } else {
                // Fallback to localStorage for offline
                this.loadPreferencesFromStorage();
            }
        } catch (error) {
            console.log('Loading preferences from localStorage (offline)');
            this.loadPreferencesFromStorage();
        }
        
        this.updateSongCheckboxes();
    }
    
    // Load preferences from localStorage
    loadPreferencesFromStorage() {
        const stored = localStorage.getItem('knownSongs');
        if (stored) {
            this.knownSongs = new Set(JSON.parse(stored));
        }
    }
    
    // Save preferences to localStorage
    savePreferencesToStorage() {
        localStorage.setItem('knownSongs', JSON.stringify([...this.knownSongs]));
    }
    
    // Update song checkboxes based on known songs
    updateSongCheckboxes() {
        this.knownSongs.forEach(songId => {
            const checkbox = document.getElementById(`song-${songId}`);
            if (checkbox) {
                checkbox.checked = true;
                checkbox.closest('.song-item').dataset.known = 'true';
                checkbox.closest('.song-item').classList.add('known-song');
            }
        });
    }
    
    // Setup event listeners
    setupEventListeners() {
        // Filter tabs
        document.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.handleFilterTab(e));
        });
        
        // Search input with debouncing
        const searchInput = document.getElementById('song-search');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.searchTerm = e.target.value.toLowerCase();
                    this.filterSongs();
                }, 300);
            });
        }
        
        // Artist filter
        const artistFilter = document.getElementById('artist-filter');
        if (artistFilter) {
            artistFilter.addEventListener('change', (e) => {
                this.selectedArtist = e.target.value;
                this.filterSongs();
            });
        }
        
        // Toggle known songs button
        const toggleBtn = document.getElementById('toggle-known-btn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggleKnownSongs());
        }
        
        // Song checkboxes (using event delegation)
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('song-known-checkbox')) {
                const songId = e.target.id.replace('song-', '');
                this.toggleSongKnown(songId, e.target.checked);
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
        
        // Online/offline events
        window.addEventListener('online', () => this.handleOnline());
        window.addEventListener('offline', () => this.handleOffline());
    }
    
    // Handle filter tab clicks
    handleFilterTab(e) {
        document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        this.currentFilter = e.target.dataset.filter;
        this.filterSongs();
    }
    
    // Toggle known songs visibility
    toggleKnownSongs() {
        this.hideKnownSongs = !this.hideKnownSongs;
        const toggleBtn = document.getElementById('toggle-known-btn');
        toggleBtn.textContent = this.hideKnownSongs ? '👁️ Show Known Songs' : '👁️ Hide Known Songs';
        toggleBtn.classList.toggle('active', this.hideKnownSongs);
        this.filterSongs();
    }
    
    // Toggle song known status
    async toggleSongKnown(songId, isKnown) {
        const songItem = document.querySelector(`[data-song-id="${songId}"]`);
        
        // Update local state immediately for responsive UI
        if (isKnown) {
            this.knownSongs.add(songId);
            songItem.classList.add('known-song');
        } else {
            this.knownSongs.delete(songId);
            songItem.classList.remove('known-song');
        }
        
        songItem.dataset.known = isKnown.toString();
        
        // Save to localStorage immediately
        this.savePreferencesToStorage();
        
        // Try to sync with server
        try {
            const response = await fetch('/api/v1/user/preferences/song', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    song_id: songId,
                    is_known: isKnown
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to sync preference');
            }
            
            // Add visual feedback for successful sync
            this.showSyncStatus(songItem, 'synced');
            
        } catch (error) {
            console.log('Preference saved offline, will sync when online');
            
            // Store for offline sync
            this.storeOfflinePreference(songId, isKnown);
            
            // Add visual feedback for offline storage
            this.showSyncStatus(songItem, 'offline');
        }
        
        // Update filters
        this.filterSongs();
    }
    
    // Store preference for offline sync
    storeOfflinePreference(songId, isKnown) {
        const offlinePrefs = JSON.parse(localStorage.getItem('offlinePreferences') || '[]');
        
        // Remove any existing preference for this song
        const filtered = offlinePrefs.filter(pref => pref.song_id !== songId);
        
        // Add new preference
        filtered.push({
            song_id: songId,
            is_known: isKnown,
            timestamp: Date.now()
        });
        
        localStorage.setItem('offlinePreferences', JSON.stringify(filtered));
    }
    
    // Show sync status visual feedback
    showSyncStatus(songItem, status) {
        const existingIndicator = songItem.querySelector('.sync-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }
        
        const indicator = document.createElement('span');
        indicator.className = `sync-indicator sync-${status}`;
        indicator.textContent = status === 'synced' ? '✓' : '📱';
        indicator.title = status === 'synced' ? 'Synced' : 'Saved offline';
        
        songItem.querySelector('.song-meta').appendChild(indicator);
        
        // Remove indicator after 2 seconds
        setTimeout(() => {
            indicator.remove();
        }, 2000);
    }
    
    // Filter songs based on current criteria
    filterSongs() {
        const songItems = document.querySelectorAll('.song-item');
        let visibleCount = 0;
        
        songItems.forEach(item => {
            const songTitle = item.querySelector('.song-title').textContent.toLowerCase();
            const songArtist = item.querySelector('.song-artist').textContent;
            const isKnown = item.dataset.known === 'true';
            
            let shouldShow = true;
            
            // Apply search filter
            if (this.searchTerm && 
                !songTitle.includes(this.searchTerm) && 
                !songArtist.toLowerCase().includes(this.searchTerm)) {
                shouldShow = false;
            }
            
            // Apply artist filter
            if (this.selectedArtist && songArtist !== this.selectedArtist) {
                shouldShow = false;
            }
            
            // Apply known/unknown filter
            if (this.currentFilter === 'known' && !isKnown) {
                shouldShow = false;
            } else if (this.currentFilter === 'unknown' && isKnown) {
                shouldShow = false;
            }
            
            // Apply hide known songs toggle
            if (this.hideKnownSongs && isKnown) {
                shouldShow = false;
            }
            
            // Show/hide item with animation
            if (shouldShow) {
                item.style.display = 'flex';
                item.classList.add('visible');
                visibleCount++;
            } else {
                item.style.display = 'none';
                item.classList.remove('visible');
            }
        });
        
        // Update empty state
        this.updateEmptyState(visibleCount);
        
        // Update filter counts
        this.updateFilterCounts();
    }
    
    // Update empty state visibility
    updateEmptyState(visibleCount) {
        const emptyState = document.getElementById('empty-state');
        if (emptyState) {
            emptyState.style.display = visibleCount === 0 ? 'block' : 'none';
        }
    }
    
    // Update filter tab counts
    updateFilterCounts() {
        const allCount = document.querySelectorAll('.song-item').length;
        const knownCount = document.querySelectorAll('.song-item[data-known="true"]').length;
        const unknownCount = allCount - knownCount;
        
        // Update tab text with counts
        const allTab = document.querySelector('[data-filter="all"]');
        const knownTab = document.querySelector('[data-filter="known"]');
        const unknownTab = document.querySelector('[data-filter="unknown"]');
        
        if (allTab) allTab.textContent = `All Songs (${allCount})`;
        if (knownTab) knownTab.textContent = `Known (${knownCount})`;
        if (unknownTab) unknownTab.textContent = `Unknown (${unknownCount})`;
    }
    
    // Populate artist filter dropdown
    populateArtistFilter() {
        const artists = new Set();
        document.querySelectorAll('.song-artist').forEach(element => {
            artists.add(element.textContent);
        });
        
        const artistFilter = document.getElementById('artist-filter');
        if (artistFilter) {
            Array.from(artists).sort().forEach(artist => {
                const option = document.createElement('option');
                option.value = artist;
                option.textContent = artist;
                artistFilter.appendChild(option);
            });
        }
    }
    
    // Handle keyboard shortcuts
    handleKeyboardShortcuts(e) {
        // Ctrl/Cmd + F: Focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.getElementById('song-search');
            if (searchInput) {
                searchInput.focus();
            }
        }
        
        // H: Toggle hide known songs
        if (e.key === 'h' && !e.ctrlKey && !e.metaKey && !e.altKey) {
            const activeElement = document.activeElement;
            if (activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA') {
                this.toggleKnownSongs();
            }
        }
        
        // 1, 2, 3: Switch filter tabs
        if (['1', '2', '3'].includes(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) {
            const activeElement = document.activeElement;
            if (activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA') {
                const tabs = document.querySelectorAll('.filter-tab');
                const index = parseInt(e.key) - 1;
                if (tabs[index]) {
                    tabs[index].click();
                }
            }
        }
    }
    
    // Setup offline handling
    setupOfflineHandling() {
        this.updateOfflineIndicator();
    }
    
    // Handle coming back online
    async handleOnline() {
        this.isOffline = false;
        this.updateOfflineIndicator();
        
        // Sync offline preferences
        await this.syncOfflinePreferences();
        
        // Show notification
        if (window.FestivalPlaylistApp) {
            window.FestivalPlaylistApp.showNotification('Back online! Syncing your preferences...', 'success');
        }
    }
    
    // Handle going offline
    handleOffline() {
        this.isOffline = true;
        this.updateOfflineIndicator();
        
        if (window.FestivalPlaylistApp) {
            window.FestivalPlaylistApp.showNotification('You are offline. Changes will be saved locally.', 'info');
        }
    }
    
    // Update offline indicator
    updateOfflineIndicator() {
        const playlistHeader = document.querySelector('.playlist-header');
        if (!playlistHeader) return;
        
        let indicator = document.getElementById('offline-indicator');
        
        if (this.isOffline) {
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.id = 'offline-indicator';
                indicator.className = 'offline-indicator';
                indicator.innerHTML = '📱 Offline mode - changes saved locally';
                playlistHeader.appendChild(indicator);
            }
        } else {
            if (indicator) {
                indicator.remove();
            }
        }
    }
    
    // Sync offline preferences when back online
    async syncOfflinePreferences() {
        const offlinePrefs = JSON.parse(localStorage.getItem('offlinePreferences') || '[]');
        
        if (offlinePrefs.length === 0) return;
        
        console.log('Syncing offline preferences...');
        
        for (const pref of offlinePrefs) {
            try {
                const response = await fetch('/api/v1/user/preferences/song', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        song_id: pref.song_id,
                        is_known: pref.is_known
                    })
                });
                
                if (response.ok) {
                    console.log('Synced preference for song:', pref.song_id);
                }
            } catch (error) {
                console.error('Failed to sync preference:', error);
                return; // Stop syncing if there's an error
            }
        }
        
        // Clear offline preferences after successful sync
        localStorage.removeItem('offlinePreferences');
        console.log('All offline preferences synced successfully');
    }
    
    // Bulk operations
    markAllAsKnown() {
        const songItems = document.querySelectorAll('.song-item:not([data-known="true"])');
        songItems.forEach(item => {
            const songId = item.dataset.songId;
            const checkbox = item.querySelector('.song-known-checkbox');
            if (checkbox) {
                checkbox.checked = true;
                this.toggleSongKnown(songId, true);
            }
        });
    }
    
    markAllAsUnknown() {
        const songItems = document.querySelectorAll('.song-item[data-known="true"]');
        songItems.forEach(item => {
            const songId = item.dataset.songId;
            const checkbox = item.querySelector('.song-known-checkbox');
            if (checkbox) {
                checkbox.checked = false;
                this.toggleSongKnown(songId, false);
            }
        });
    }
    
    // Export current playlist state
    exportPlaylistState() {
        const playlistData = {
            knownSongs: [...this.knownSongs],
            filters: {
                currentFilter: this.currentFilter,
                hideKnownSongs: this.hideKnownSongs,
                searchTerm: this.searchTerm,
                selectedArtist: this.selectedArtist
            },
            timestamp: Date.now()
        };
        
        const blob = new Blob([JSON.stringify(playlistData, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'playlist-preferences.json';
        a.click();
        
        URL.revokeObjectURL(url);
    }
}

// Initialize playlist manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.playlist-header')) {
        window.playlistManager = new PlaylistManager();
    }
});

// Export for use in other scripts
window.PlaylistManager = PlaylistManager;