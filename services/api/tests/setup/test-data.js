// Test data fixtures for UI tests

export const mockFestivals = [
  {
    id: 'coachella-2024',
    name: 'Coachella Valley Music and Arts Festival',
    dates: ['2024-04-12', '2024-04-14', '2024-04-19', '2024-04-21'],
    location: 'Indio, CA',
    venue: 'Empire Polo Club',
    artists: ['Lana Del Rey', 'Tyler, The Creator', 'Doja Cat', 'No Doubt', 'Ice Spice'],
    genres: ['Pop', 'Hip Hop', 'Alternative', 'Electronic'],
    ticket_url: 'https://coachella.com/tickets',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z'
  },
  {
    id: 'bonnaroo-2024',
    name: 'Bonnaroo Music & Arts Festival',
    dates: ['2024-06-13', '2024-06-16'],
    location: 'Manchester, TN',
    venue: 'Great Stage Park',
    artists: ['Post Malone', 'Pretty Lights', 'Red Hot Chili Peppers', 'Sturgill Simpson'],
    genres: ['Rock', 'Hip Hop', 'Electronic', 'Country'],
    ticket_url: 'https://bonnaroo.com/tickets',
    created_at: '2024-01-20T10:00:00Z',
    updated_at: '2024-01-20T10:00:00Z'
  }
];

export const mockArtists = [
  {
    id: 'lana-del-rey',
    name: 'Lana Del Rey',
    musicbrainz_id: 'b7539c32-53e7-4908-bda3-81449c367da6',
    genres: ['Pop', 'Alternative', 'Indie'],
    popularity_score: 0.95,
    created_at: '2024-01-15T10:00:00Z'
  },
  {
    id: 'tyler-the-creator',
    name: 'Tyler, The Creator',
    musicbrainz_id: 'f6beac20-5dfe-4d1f-ae02-0b0a740aafd6',
    genres: ['Hip Hop', 'Alternative Hip Hop'],
    popularity_score: 0.92,
    created_at: '2024-01-15T10:00:00Z'
  }
];

export const mockPlaylists = [
  {
    id: 'coachella-2024-playlist',
    name: 'Coachella 2024 - Festival Playlist',
    description: 'Songs likely to be played at Coachella 2024 based on recent setlists',
    songs: [
      {
        id: 'song-1',
        title: 'Video Games',
        artist: 'Lana Del Rey',
        original_artist: null,
        is_cover: false,
        normalized_title: 'video games',
        performance_count: 8
      },
      {
        id: 'song-2',
        title: 'EARFQUAKE',
        artist: 'Tyler, The Creator',
        original_artist: null,
        is_cover: false,
        normalized_title: 'earfquake',
        performance_count: 7
      }
    ],
    festival_id: 'coachella-2024',
    artist_id: null,
    user_id: 'test-user',
    platform: 'spotify',
    external_id: 'spotify:playlist:37i9dQZF1DX0XUsuxWHRQd',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z'
  }
];

export const mockUsers = [
  {
    id: 'test-user',
    email: 'test@example.com',
    preferences: {
      streaming_platform: 'spotify',
      notification_frequency: 'weekly',
      show_known_songs: false
    },
    connected_platforms: ['spotify'],
    known_songs: ['song-1'],
    festival_history: ['coachella-2024'],
    created_at: '2024-01-15T10:00:00Z'
  }
];

export const mockSetlists = [
  {
    id: 'setlist-1',
    artist_id: 'lana-del-rey',
    venue: 'Madison Square Garden',
    date: '2024-01-10T20:00:00Z',
    songs: ['Video Games', 'Born to Die', 'Summertime Sadness', 'West Coast'],
    tour_name: 'Did you know that there\'s a tunnel under Ocean Blvd Tour',
    festival_name: null,
    source: 'setlist.fm'
  }
];

// Mock API responses
export const mockApiResponses = {
  festivals: {
    success: {
      festivals: mockFestivals,
      total: mockFestivals.length,
      page: 1,
      per_page: 10
    },
    empty: {
      festivals: [],
      total: 0,
      page: 1,
      per_page: 10
    }
  },
  
  artists: {
    success: {
      artists: mockArtists,
      total: mockArtists.length,
      page: 1,
      per_page: 10
    }
  },
  
  playlists: {
    success: {
      playlists: mockPlaylists,
      total: mockPlaylists.length,
      page: 1,
      per_page: 10
    }
  }
};

// Helper functions for tests
export function createMockFetch(responses = {}) {
  return jest.fn((url) => {
    const response = responses[url] || { status: 404, json: () => Promise.resolve({}) };
    return Promise.resolve({
      ok: response.status < 400,
      status: response.status,
      json: () => Promise.resolve(response.json || response.data || {}),
      text: () => Promise.resolve(response.text || ''),
    });
  });
}

export function setupMockFetch(responses = {}) {
  global.fetch = createMockFetch(responses);
}

export function createMockElement(tagName = 'div', attributes = {}) {
  const element = document.createElement(tagName);
  Object.keys(attributes).forEach(key => {
    if (key === 'textContent') {
      element.textContent = attributes[key];
    } else {
      element.setAttribute(key, attributes[key]);
    }
  });
  return element;
}