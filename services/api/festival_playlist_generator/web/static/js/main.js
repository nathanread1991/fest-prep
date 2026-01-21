// Main JavaScript file for Festival Playlist Generator

// Global variables
let isOnline = navigator.onLine;
let serviceWorkerRegistration = null;
let lastSectionRefresh = {};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// Initialize the application
function initializeApp() {
    // Register service worker for offline support
    if ('serviceWorker' in navigator) {
        registerServiceWorker();
    }
    
    // Set up online/offline event listeners
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    // Set up global form handling
    setupGlobalFormHandling();
    
    // Set up search functionality
    setupSearchFunctionality();
    
    // Initialize offline indicator
    updateOfflineIndicator();
    
    // Set up data refresh mechanisms
    setupDataRefreshMechanisms();
}

// Set up data refresh mechanisms
function setupDataRefreshMechanisms() {
    // Clear cache on page load if coming from different section
    const currentSection = getCurrentSection();
    const lastSection = sessionStorage.getItem('lastSection');
    
    if (lastSection && lastSection !== currentSection) {
        clearSectionSpecificCache(lastSection);
    }
    
    sessionStorage.setItem('lastSection', currentSection);
    
    // Set up periodic refresh for active sections
    setInterval(() => {
        if (!document.hidden) {
            refreshCurrentSectionIfStale();
        }
    }, 30000); // Check every 30 seconds
}

// Get current section from URL
function getCurrentSection() {
    const path = window.location.pathname;
    if (path === '/') return 'home';
    if (path.startsWith('/festivals')) return 'festivals';
    if (path.startsWith('/artists')) return 'artists';
    if (path.startsWith('/playlists')) return 'playlists';
    if (path.startsWith('/streaming')) return 'streaming';
    if (path.startsWith('/admin')) return 'admin';
    return 'unknown';
}

// Clear section-specific cache
function clearSectionSpecificCache(section) {
    const cacheKeys = [
        `${section}_data`,
        `${section}_last_update`,
        `cache_${section}`,
        `section_${section}_cache`
    ];
    
    cacheKeys.forEach(key => {
        localStorage.removeItem(key);
        sessionStorage.removeItem(key);
    });
}

// Refresh current section if data is stale
function refreshCurrentSectionIfStale() {
    const section = getCurrentSection();
    
    // Never auto-refresh the festivals page - it has its own dynamic loading
    if (section === 'festivals') {
        return;
    }
    
    const lastRefresh = lastSectionRefresh[section];
    const now = Date.now();
    
    // Refresh if no recent refresh or if data is older than 2 minutes
    if (!lastRefresh || (now - lastRefresh) > 120000) {
        refreshCurrentSectionData();
        lastSectionRefresh[section] = now;
    }
}

// Refresh current section data
function refreshCurrentSectionData() {
    const section = getCurrentSection();
    
    switch (section) {
        case 'admin':
            if (typeof refreshAdminStats === 'function') {
                refreshAdminStats();
            }
            break;
        case 'artists':
            refreshArtistsData();
            break;
        case 'festivals':
            // Skip auto-refresh for festivals - it has its own dynamic loading
            console.log('Skipping auto-refresh for festivals page');
            break;
        case 'playlists':
            refreshPlaylistsData();
            break;
    }
}

// Refresh artists data
function refreshArtistsData() {
    const artistsList = document.querySelector('.artists-list, .artist-grid, #artists-container');
    if (artistsList) {
        // Add loading indicator
        showDataRefreshIndicator('Refreshing artists data...');
        
        // Force reload artists data with cache-busting
        const url = new URL(window.location.href);
        url.searchParams.set('_refresh', Date.now());
        
        fetch(url.toString(), {
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        })
        .then(response => response.text())
        .then(html => {
            // Parse the response and update the artists section
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newArtistsList = doc.querySelector('.artists-list, .artist-grid, #artists-container');
            
            if (newArtistsList) {
                artistsList.innerHTML = newArtistsList.innerHTML;
            }
            
            hideDataRefreshIndicator();
        })
        .catch(error => {
            console.error('Error refreshing artists data:', error);
            hideDataRefreshIndicator();
        });
    }
}

// Refresh festivals data
function refreshFestivalsData() {
    // Skip auto-refresh for festivals page - it has its own dynamic loading
    // The festivals page uses client-side pagination and filtering
    // Auto-refreshing would clear dynamically loaded content
    console.log('Skipping auto-refresh for festivals page (uses dynamic loading)');
    return;
    
    const festivalsList = document.querySelector('.festivals-list, .festival-grid, #festivals-container');
    if (festivalsList) {
        showDataRefreshIndicator('Refreshing festivals data...');
        
        const url = new URL(window.location.href);
        url.searchParams.set('_refresh', Date.now());
        
        fetch(url.toString(), {
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        })
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newFestivalsList = doc.querySelector('.festivals-list, .festival-grid, #festivals-container');
            
            if (newFestivalsList) {
                festivalsList.innerHTML = newFestivalsList.innerHTML;
            }
            
            hideDataRefreshIndicator();
        })
        .catch(error => {
            console.error('Error refreshing festivals data:', error);
            hideDataRefreshIndicator();
        });
    }
}

// Refresh playlists data
function refreshPlaylistsData() {
    const playlistsList = document.querySelector('.playlists-list, .playlist-grid, #playlists-container');
    if (playlistsList) {
        showDataRefreshIndicator('Refreshing playlists data...');
        
        const url = new URL(window.location.href);
        url.searchParams.set('_refresh', Date.now());
        
        fetch(url.toString(), {
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        })
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newPlaylistsList = doc.querySelector('.playlists-list, .playlist-grid, #playlists-container');
            
            if (newPlaylistsList) {
                playlistsList.innerHTML = newPlaylistsList.innerHTML;
            }
            
            hideDataRefreshIndicator();
        })
        .catch(error => {
            console.error('Error refreshing playlists data:', error);
            hideDataRefreshIndicator();
        });
    }
}

// Show data refresh indicator
function showDataRefreshIndicator(message = 'Refreshing data...') {
    let indicator = document.getElementById('data-refresh-indicator');
    
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'data-refresh-indicator';
        indicator.style.cssText = `
            position: fixed;
            top: 70px;
            right: 20px;
            background: #6366f1;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            z-index: 1000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transform: translateX(100%);
            transition: transform 0.3s ease;
        `;
        document.body.appendChild(indicator);
    }
    
    indicator.textContent = message;
    
    // Animate in
    setTimeout(() => {
        indicator.style.transform = 'translateX(0)';
    }, 100);
}

// Hide data refresh indicator
function hideDataRefreshIndicator() {
    const indicator = document.getElementById('data-refresh-indicator');
    if (indicator) {
        indicator.style.transform = 'translateX(100%)';
        setTimeout(() => {
            indicator.remove();
        }, 300);
    }
}

// Register service worker
async function registerServiceWorker() {
    try {
        serviceWorkerRegistration = await navigator.serviceWorker.register('/static/js/sw.js');
        console.log('Service Worker registered successfully');
    } catch (error) {
        console.error('Service Worker registration failed:', error);
    }
}

// Handle online event
function handleOnline() {
    isOnline = true;
    updateOfflineIndicator();
    syncOfflineData();
}

// Handle offline event
function handleOffline() {
    isOnline = false;
    updateOfflineIndicator();
}

// Update offline indicator
function updateOfflineIndicator() {
    let indicator = document.getElementById('offline-indicator');
    
    if (!isOnline) {
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'offline-indicator';
            indicator.className = 'offline-indicator';
            indicator.innerHTML = '📡 You are offline. Some features may be limited.';
            document.body.appendChild(indicator);
        }
    } else {
        if (indicator) {
            indicator.remove();
        }
    }
}

// Sync offline data when back online
async function syncOfflineData() {
    const offlineData = getOfflineData();
    
    if (offlineData.length > 0) {
        console.log('Syncing offline data...');
        
        for (const data of offlineData) {
            try {
                await fetch(data.url, {
                    method: data.method,
                    headers: data.headers,
                    body: data.body
                });
                
                // Remove from offline storage after successful sync
                removeOfflineData(data.id);
            } catch (error) {
                console.error('Failed to sync offline data:', error);
            }
        }
    }
}

// Get offline data from localStorage
function getOfflineData() {
    const data = localStorage.getItem('offlineData');
    return data ? JSON.parse(data) : [];
}

// Store data for offline sync
function storeOfflineData(id, url, method, headers, body) {
    const offlineData = getOfflineData();
    offlineData.push({ id, url, method, headers, body, timestamp: Date.now() });
    localStorage.setItem('offlineData', JSON.stringify(offlineData));
}

// Remove offline data after sync
function removeOfflineData(id) {
    const offlineData = getOfflineData();
    const filtered = offlineData.filter(item => item.id !== id);
    localStorage.setItem('offlineData', JSON.stringify(filtered));
}

// Setup global form handling
function setupGlobalFormHandling() {
    // Handle all forms with data-ajax attribute
    document.addEventListener('submit', function(e) {
        const form = e.target;
        if (form.hasAttribute('data-ajax')) {
            e.preventDefault();
            handleAjaxForm(form);
        }
    });
}

// Handle AJAX form submissions
async function handleAjaxForm(form) {
    const formData = new FormData(form);
    const url = form.action || window.location.href;
    const method = form.method || 'POST';
    
    try {
        const response = await fetch(url, {
            method: method,
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            handleFormSuccess(form, data);
        } else {
            throw new Error('Form submission failed');
        }
    } catch (error) {
        handleFormError(form, error);
    }
}

// Handle successful form submission
function handleFormSuccess(form, data) {
    // Show success message
    showNotification('Success!', 'success');
    
    // Reset form if specified
    if (form.hasAttribute('data-reset')) {
        form.reset();
    }
    
    // Redirect if specified
    if (data.redirect) {
        window.location.href = data.redirect;
    }
}

// Handle form submission error
function handleFormError(form, error) {
    console.error('Form error:', error);
    showNotification('Something went wrong. Please try again.', 'error');
}

// Setup search functionality
function setupSearchFunctionality() {
    const searchForm = document.getElementById('festival-search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', handleSearch);
    }
    
    // Setup search input with debounced suggestions
    const searchInput = document.getElementById('festival-search');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                showSearchSuggestions(this.value);
            }, 300);
        });
    }
}

// Handle search form submission
async function handleSearch(e) {
    e.preventDefault();
    
    const searchInput = document.getElementById('festival-search');
    const query = searchInput.value.trim();
    
    if (!query) return;
    
    // Determine search type based on placeholder or context
    const searchType = searchInput.placeholder.includes('artist') ? 'artists' : 'festivals';
    
    // Redirect to search results
    window.location.href = `/search?q=${encodeURIComponent(query)}&type=${searchType}`;
}

// Show search suggestions
async function showSearchSuggestions(query) {
    if (!query || query.length < 2) {
        hideSearchSuggestions();
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/search/suggestions?q=${encodeURIComponent(query)}`);
        if (response.ok) {
            const data = await response.json();
            displaySearchSuggestions(data.suggestions);
        }
    } catch (error) {
        console.error('Error fetching search suggestions:', error);
    }
}

// Display search suggestions
function displaySearchSuggestions(suggestions) {
    let suggestionsContainer = document.getElementById('search-suggestions');
    
    if (!suggestionsContainer) {
        suggestionsContainer = document.createElement('div');
        suggestionsContainer.id = 'search-suggestions';
        suggestionsContainer.className = 'search-suggestions';
        
        const searchInput = document.getElementById('festival-search');
        searchInput.parentNode.appendChild(suggestionsContainer);
    }
    
    if (suggestions.length === 0) {
        hideSearchSuggestions();
        return;
    }
    
    suggestionsContainer.innerHTML = suggestions.map(suggestion => `
        <div class="suggestion-item" onclick="selectSuggestion('${suggestion.text}', '${suggestion.type}')">
            <span class="suggestion-icon">${suggestion.type === 'festival' ? '🎪' : '🎤'}</span>
            <span class="suggestion-text">${suggestion.text}</span>
            <span class="suggestion-type">${suggestion.type}</span>
        </div>
    `).join('');
    
    suggestionsContainer.style.display = 'block';
}

// Hide search suggestions
function hideSearchSuggestions() {
    const suggestionsContainer = document.getElementById('search-suggestions');
    if (suggestionsContainer) {
        suggestionsContainer.style.display = 'none';
    }
}

// Select a search suggestion
function selectSuggestion(text, type) {
    const searchInput = document.getElementById('festival-search');
    searchInput.value = text;
    hideSearchSuggestions();
    
    // Trigger search
    const searchForm = document.getElementById('festival-search-form');
    if (searchForm) {
        searchForm.dispatchEvent(new Event('submit'));
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Utility function to format dates
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Utility function to format date ranges
function formatDateRange(dates) {
    if (!dates || dates.length === 0) return 'Dates TBA';
    
    if (dates.length === 1) {
        return formatDate(dates[0]);
    }
    
    const startDate = new Date(dates[0]);
    const endDate = new Date(dates[dates.length - 1]);
    
    if (startDate.getFullYear() === endDate.getFullYear() && 
        startDate.getMonth() === endDate.getMonth()) {
        return `${startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${endDate.toLocaleDateString('en-US', { day: 'numeric', year: 'numeric' })}`;
    } else {
        return `${formatDate(dates[0])} - ${formatDate(dates[dates.length - 1])}`;
    }
}

// Utility function to truncate text
function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// Export functions for use in other scripts
window.FestivalPlaylistApp = {
    showNotification,
    formatDate,
    formatDateRange,
    truncateText,
    isOnline: () => isOnline,
    refreshCurrentSectionData,
    clearSectionSpecificCache,
    getCurrentSection,
    showDataRefreshIndicator,
    hideDataRefreshIndicator
};