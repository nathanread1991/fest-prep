// Streaming service integration JavaScript
// Handles authentication flows and playlist creation for various streaming platforms

class StreamingIntegration {
    constructor() {
        this.connectedServices = new Set();
        this.authTokens = {};
        this.supportedPlatforms = ['spotify', 'youtube_music', 'apple_music', 'youtube'];
        
        this.init();
    }
    
    init() {
        this.loadConnectedServices();
        this.setupEventListeners();
        this.checkAuthStatus();
    }
    
    // Load connected services from localStorage
    loadConnectedServices() {
        const stored = localStorage.getItem('connectedServices');
        if (stored) {
            this.connectedServices = new Set(JSON.parse(stored));
        }
        
        const tokens = localStorage.getItem('authTokens');
        if (tokens) {
            this.authTokens = JSON.parse(tokens);
        }
    }
    
    // Save connected services to localStorage
    saveConnectedServices() {
        localStorage.setItem('connectedServices', JSON.stringify([...this.connectedServices]));
        localStorage.setItem('authTokens', JSON.stringify(this.authTokens));
    }
    
    // Setup event listeners
    setupEventListeners() {
        // Export playlist buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-streaming-platform]')) {
                const platform = e.target.dataset.streamingPlatform;
                this.handleExportClick(platform, e.target);
            }
        });
        
        // Connect service buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-connect-service]')) {
                const platform = e.target.dataset.connectService;
                this.connectService(platform);
            }
        });
        
        // Disconnect service buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-disconnect-service]')) {
                const platform = e.target.dataset.disconnectService;
                this.disconnectService(platform);
            }
        });
        
        // Handle OAuth callbacks
        this.handleOAuthCallback();
    }
    
    // Check authentication status for all platforms
    async checkAuthStatus() {
        for (const platform of this.supportedPlatforms) {
            try {
                const response = await fetch(`/api/v1/streaming/${platform}/auth/status`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.authenticated) {
                        this.connectedServices.add(platform);
                        this.authTokens[platform] = data.token;
                    }
                }
            } catch (error) {
                console.log(`Could not check auth status for ${platform}:`, error);
            }
        }
        
        this.saveConnectedServices();
        this.updateUI();
    }
    
    // Handle export button clicks
    async handleExportClick(platform, button) {
        if (!this.connectedServices.has(platform)) {
            // Need to authenticate first
            const shouldConnect = confirm(`You need to connect your ${this.getPlatformName(platform)} account first. Connect now?`);
            if (shouldConnect) {
                await this.connectService(platform);
                return;
            }
        }
        
        // Get playlist ID from the page
        const playlistId = this.getPlaylistIdFromPage();
        if (!playlistId) {
            this.showError('Could not determine playlist to export');
            return;
        }
        
        await this.exportPlaylist(platform, playlistId, button);
    }
    
    // Connect to a streaming service
    async connectService(platform) {
        try {
            this.showLoading(`Connecting to ${this.getPlatformName(platform)}...`);
            
            // Get authorization URL
            const response = await fetch(`/api/v1/streaming/${platform}/auth/url`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error('Failed to get authorization URL');
            }
            
            const data = await response.json();
            
            // Store the platform we're connecting to
            sessionStorage.setItem('connectingPlatform', platform);
            
            // Open OAuth popup or redirect
            if (this.isMobile()) {
                // On mobile, redirect to auth URL
                window.location.href = data.auth_url;
            } else {
                // On desktop, open popup
                this.openAuthPopup(data.auth_url, platform);
            }
            
        } catch (error) {
            console.error('Error connecting service:', error);
            this.showError(`Failed to connect to ${this.getPlatformName(platform)}`);
        } finally {
            this.hideLoading();
        }
    }
    
    // Disconnect from a streaming service
    async disconnectService(platform) {
        const shouldDisconnect = confirm(`Disconnect from ${this.getPlatformName(platform)}?`);
        if (!shouldDisconnect) return;
        
        try {
            const response = await fetch(`/api/v1/streaming/${platform}/auth/disconnect`, {
                method: 'POST'
            });
            
            if (response.ok) {
                this.connectedServices.delete(platform);
                delete this.authTokens[platform];
                this.saveConnectedServices();
                this.updateUI();
                this.showSuccess(`Disconnected from ${this.getPlatformName(platform)}`);
            } else {
                throw new Error('Failed to disconnect');
            }
            
        } catch (error) {
            console.error('Error disconnecting service:', error);
            this.showError(`Failed to disconnect from ${this.getPlatformName(platform)}`);
        }
    }
    
    // Open OAuth popup window
    openAuthPopup(authUrl, platform) {
        const popup = window.open(
            authUrl,
            `${platform}_auth`,
            'width=600,height=700,scrollbars=yes,resizable=yes'
        );
        
        // Poll for popup closure
        const pollTimer = setInterval(() => {
            if (popup.closed) {
                clearInterval(pollTimer);
                // Check if authentication was successful
                setTimeout(() => {
                    this.checkAuthStatus();
                }, 1000);
            }
        }, 1000);
    }
    
    // Handle OAuth callback (for mobile redirects)
    handleOAuthCallback() {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        const platform = sessionStorage.getItem('connectingPlatform');
        
        if (code && platform) {
            this.completeOAuthFlow(platform, code, state);
            
            // Clean up URL
            const cleanUrl = window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
            
            // Clean up session storage
            sessionStorage.removeItem('connectingPlatform');
        }
    }
    
    // Complete OAuth flow
    async completeOAuthFlow(platform, code, state) {
        try {
            this.showLoading(`Completing ${this.getPlatformName(platform)} connection...`);
            
            const response = await fetch(`/api/v1/streaming/${platform}/auth/callback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code, state })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.connectedServices.add(platform);
                this.authTokens[platform] = data.token;
                this.saveConnectedServices();
                this.updateUI();
                this.showSuccess(`Successfully connected to ${this.getPlatformName(platform)}!`);
            } else {
                throw new Error('Failed to complete authentication');
            }
            
        } catch (error) {
            console.error('Error completing OAuth flow:', error);
            this.showError(`Failed to connect to ${this.getPlatformName(platform)}`);
        } finally {
            this.hideLoading();
        }
    }
    
    // Export playlist to streaming platform
    async exportPlaylist(platform, playlistId, button) {
        const originalText = button.textContent;
        
        try {
            button.textContent = '🔄 Exporting...';
            button.disabled = true;
            
            const response = await fetch(`/api/v1/streaming/${platform}/create-playlist`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    playlist_id: playlistId
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showSuccess(`Playlist exported to ${this.getPlatformName(platform)}!`);
                
                // Show link to created playlist if available
                if (data.external_url) {
                    this.showPlaylistLink(data.external_url, platform);
                }
                
                // Update button to show success
                button.textContent = '✅ Exported';
                setTimeout(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                }, 3000);
                
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Export failed');
            }
            
        } catch (error) {
            console.error('Error exporting playlist:', error);
            this.showError(`Failed to export to ${this.getPlatformName(platform)}: ${error.message}`);
            
            // Reset button
            button.textContent = originalText;
            button.disabled = false;
        }
    }
    
    // Show link to created playlist
    showPlaylistLink(url, platform) {
        const notification = document.createElement('div');
        notification.className = 'playlist-link-notification';
        notification.innerHTML = `
            <p>Playlist created on ${this.getPlatformName(platform)}!</p>
            <a href="${url}" target="_blank" class="btn btn-primary btn-small">
                Open in ${this.getPlatformName(platform)}
            </a>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            notification.remove();
        }, 10000);
    }
    
    // Update UI based on connection status
    updateUI() {
        // Update streaming service buttons
        this.supportedPlatforms.forEach(platform => {
            const buttons = document.querySelectorAll(`[data-streaming-platform="${platform}"]`);
            const connectButtons = document.querySelectorAll(`[data-connect-service="${platform}"]`);
            const disconnectButtons = document.querySelectorAll(`[data-disconnect-service="${platform}"]`);
            
            const isConnected = this.connectedServices.has(platform);
            
            buttons.forEach(button => {
                if (isConnected) {
                    button.classList.remove('btn-secondary');
                    button.classList.add('btn-primary');
                    button.disabled = false;
                } else {
                    button.classList.remove('btn-primary');
                    button.classList.add('btn-secondary');
                    button.title = `Connect your ${this.getPlatformName(platform)} account first`;
                }
            });
            
            connectButtons.forEach(button => {
                button.style.display = isConnected ? 'none' : 'inline-flex';
            });
            
            disconnectButtons.forEach(button => {
                button.style.display = isConnected ? 'inline-flex' : 'none';
            });
        });
        
        // Update connection status indicators
        this.updateConnectionIndicators();
    }
    
    // Update connection status indicators
    updateConnectionIndicators() {
        const indicators = document.querySelectorAll('.connection-status');
        indicators.forEach(indicator => {
            const platform = indicator.dataset.platform;
            const isConnected = this.connectedServices.has(platform);
            
            indicator.className = `connection-status ${isConnected ? 'connected' : 'disconnected'}`;
            indicator.textContent = isConnected ? '✅ Connected' : '❌ Not connected';
        });
    }
    
    // Get playlist ID from current page
    getPlaylistIdFromPage() {
        // Try to get from URL path
        const pathMatch = window.location.pathname.match(/\/playlists\/([^\/]+)/);
        if (pathMatch) {
            return pathMatch[1];
        }
        
        // Try to get from data attribute
        const playlistElement = document.querySelector('[data-playlist-id]');
        if (playlistElement) {
            return playlistElement.dataset.playlistId;
        }
        
        return null;
    }
    
    // Get human-readable platform name
    getPlatformName(platform) {
        const names = {
            'spotify': 'Spotify',
            'youtube_music': 'YouTube Music',
            'apple_music': 'Apple Music',
            'youtube': 'YouTube'
        };
        return names[platform] || platform;
    }
    
    // Check if running on mobile device
    isMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }
    
    // Show loading message
    showLoading(message) {
        this.hideLoading(); // Remove any existing loading
        
        const loading = document.createElement('div');
        loading.id = 'streaming-loading';
        loading.className = 'streaming-loading';
        loading.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <p>${message}</p>
            </div>
        `;
        
        document.body.appendChild(loading);
    }
    
    // Hide loading message
    hideLoading() {
        const loading = document.getElementById('streaming-loading');
        if (loading) {
            loading.remove();
        }
    }
    
    // Show success message
    showSuccess(message) {
        if (window.FestivalPlaylistApp) {
            window.FestivalPlaylistApp.showNotification(message, 'success');
        } else {
            alert(message);
        }
    }
    
    // Show error message
    showError(message) {
        if (window.FestivalPlaylistApp) {
            window.FestivalPlaylistApp.showNotification(message, 'error');
        } else {
            alert(message);
        }
    }
    
    // Get connection summary for user
    getConnectionSummary() {
        const connected = [...this.connectedServices];
        const total = this.supportedPlatforms.length;
        
        return {
            connected: connected.length,
            total: total,
            platforms: connected.map(p => this.getPlatformName(p))
        };
    }
    
    // Bulk connect to multiple services
    async connectMultipleServices(platforms) {
        for (const platform of platforms) {
            if (!this.connectedServices.has(platform)) {
                await this.connectService(platform);
                // Add delay between connections to avoid rate limiting
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }
    }
    
    // Export to multiple platforms
    async exportToMultiplePlatforms(platforms, playlistId) {
        const results = {};
        
        for (const platform of platforms) {
            if (this.connectedServices.has(platform)) {
                try {
                    const response = await fetch(`/api/v1/streaming/${platform}/create-playlist`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            playlist_id: playlistId
                        })
                    });
                    
                    results[platform] = {
                        success: response.ok,
                        data: response.ok ? await response.json() : null,
                        error: response.ok ? null : await response.text()
                    };
                    
                } catch (error) {
                    results[platform] = {
                        success: false,
                        error: error.message
                    };
                }
                
                // Add delay between exports
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
        
        return results;
    }
}

// Initialize streaming integration when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.streamingIntegration = new StreamingIntegration();
});

// Export for use in other scripts
window.StreamingIntegration = StreamingIntegration;