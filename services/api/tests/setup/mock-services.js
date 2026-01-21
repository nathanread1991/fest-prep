// Mock services for testing

class MockStreamingService {
  constructor(platform = 'spotify') {
    this.platform = platform;
    this.isAuthenticated = false;
    this.playlists = [];
  }

  async authenticate(credentials) {
    if (credentials && credentials.access_token) {
      this.isAuthenticated = true;
      return { success: true, token: credentials.access_token };
    }
    throw new Error('Authentication failed');
  }

  async createPlaylist(name, description, songs) {
    if (!this.isAuthenticated) {
      throw new Error('Not authenticated');
    }
    
    const playlist = {
      id: `mock-playlist-${Date.now()}`,
      name,
      description,
      songs: songs || [],
      platform: this.platform,
      created_at: new Date().toISOString()
    };
    
    this.playlists.push(playlist);
    return playlist;
  }

  async searchSong(title, artist) {
    // Mock search results
    return [
      {
        id: `mock-track-${title.replace(/\s+/g, '-').toLowerCase()}`,
        title,
        artist,
        album: 'Mock Album',
        duration: 180000,
        preview_url: 'https://example.com/preview.mp3',
        external_url: `https://${this.platform}.com/track/mock`
      }
    ];
  }

  async getUserPlaylists() {
    if (!this.isAuthenticated) {
      throw new Error('Not authenticated');
    }
    return this.playlists;
  }
}

class MockNotificationService {
  constructor() {
    this.notifications = [];
    this.subscribers = [];
  }

  async subscribe(userId, preferences) {
    this.subscribers.push({ userId, preferences });
    return { success: true };
  }

  async sendNotification(userId, notification) {
    this.notifications.push({
      userId,
      ...notification,
      sent_at: new Date().toISOString()
    });
    return { success: true };
  }

  getNotifications(userId) {
    return this.notifications.filter(n => n.userId === userId);
  }
}

class MockGeolocationService {
  constructor() {
    this.currentPosition = {
      coords: {
        latitude: 37.7749,
        longitude: -122.4194,
        accuracy: 10
      }
    };
  }

  getCurrentPosition() {
    return Promise.resolve(this.currentPosition);
  }

  setPosition(lat, lng, accuracy = 10) {
    this.currentPosition = {
      coords: {
        latitude: lat,
        longitude: lng,
        accuracy
      }
    };
  }
}

// Mock browser APIs
function mockBrowserAPIs() {
  // Mock Geolocation API
  global.navigator.geolocation = {
    getCurrentPosition: jest.fn((success) => {
      success({
        coords: {
          latitude: 37.7749,
          longitude: -122.4194,
          accuracy: 10
        }
      });
    }),
    watchPosition: jest.fn(),
    clearWatch: jest.fn()
  };

  // Mock Notification API
  global.Notification = {
    permission: 'granted',
    requestPermission: jest.fn(() => Promise.resolve('granted'))
  };

  // Mock Service Worker
  global.navigator.serviceWorker = {
    register: jest.fn(() => Promise.resolve({
      installing: null,
      waiting: null,
      active: {
        postMessage: jest.fn()
      }
    })),
    ready: Promise.resolve({
      showNotification: jest.fn()
    })
  };

  // Mock Web Share API
  global.navigator.share = jest.fn(() => Promise.resolve());

  // Mock Clipboard API
  global.navigator.clipboard = {
    writeText: jest.fn(() => Promise.resolve()),
    readText: jest.fn(() => Promise.resolve(''))
  };
}

// Mock intersection observer for lazy loading tests
function mockIntersectionObserver() {
  global.IntersectionObserver = jest.fn().mockImplementation((callback) => ({
    observe: jest.fn(),
    unobserve: jest.fn(),
    disconnect: jest.fn(),
    trigger: (entries) => callback(entries)
  }));
}

// Mock resize observer for responsive tests
function mockResizeObserver() {
  global.ResizeObserver = jest.fn().mockImplementation((callback) => ({
    observe: jest.fn(),
    unobserve: jest.fn(),
    disconnect: jest.fn(),
    trigger: (entries) => callback(entries)
  }));
}

// Mock fetch setup
function setupMockFetch() {
  const mockFetch = jest.fn();
  global.fetch = mockFetch;
  return mockFetch;
}

module.exports = {
  MockStreamingService,
  MockNotificationService,
  MockGeolocationService,
  mockBrowserAPIs,
  mockIntersectionObserver,
  mockResizeObserver,
  setupMockFetch
};