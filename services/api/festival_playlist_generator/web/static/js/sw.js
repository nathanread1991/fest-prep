// Service Worker for Festival Playlist Generator
// Provides offline support and advanced caching strategies

const CACHE_NAME = 'festival-playlists-v2';
const STATIC_CACHE_URLS = [
    '/',
    '/static/css/main.css',
    '/static/js/main.js',
    '/static/manifest.json',
    '/festivals',
    '/playlists',
    '/offline'
];

const API_CACHE_URLS = [
    '/api/v1/festivals',
    '/api/v1/playlists',
    '/api/v1/user/preferences'
];

// Cache strategies
const CACHE_STRATEGIES = {
    'static': 'cache-first',
    'api': 'network-first',
    'images': 'cache-first',
    'pages': 'network-first'
};

// Cache TTL (Time To Live) in milliseconds
const CACHE_TTL = {
    'static': 24 * 60 * 60 * 1000,    // 24 hours
    'api': 30 * 60 * 1000,            // 30 minutes
    'images': 7 * 24 * 60 * 60 * 1000, // 7 days
    'pages': 5 * 60 * 1000             // 5 minutes
};

// Install event - cache static resources
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Caching static resources');
                return cache.addAll(STATIC_CACHE_URLS);
            })
            .then(() => {
                console.log('Service worker installed');
                return self.skipWaiting();
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== CACHE_NAME) {
                            console.log('Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('Service worker activated');
                return self.clients.claim();
            })
    );
});

// Fetch event - advanced caching strategies
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Handle API requests
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }
    
    // Handle static resources
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(handleStaticRequest(request));
        return;
    }
    
    // Handle page requests
    event.respondWith(handlePageRequest(request));
});

// Handle API requests with network-first strategy
async function handleApiRequest(request) {
    const url = new URL(request.url);
    
    try {
        // Try network first for API requests
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            // Cache successful GET requests with TTL
            if (request.method === 'GET') {
                const responseClone = networkResponse.clone();
                await cacheWithTTL(request, responseClone, 'api');
            }
            
            // Handle POST requests for offline sync
            if (request.method === 'POST' && url.pathname.includes('/preferences')) {
                const requestClone = request.clone();
                const body = await requestClone.text();
                
                await storeOfflineAction({
                    url: request.url,
                    method: request.method,
                    headers: Object.fromEntries(request.headers.entries()),
                    body: body,
                    timestamp: Date.now()
                });
            }
        }
        
        return networkResponse;
    } catch (error) {
        console.log('Network request failed, trying cache:', request.url);
        
        // For GET requests, try to serve from cache
        if (request.method === 'GET') {
            const cachedResponse = await getCachedResponse(request);
            if (cachedResponse && !isExpired(cachedResponse, 'api')) {
                return cachedResponse;
            }
        }
        
        // For POST requests, store for later sync
        if (request.method === 'POST') {
            const requestClone = request.clone();
            const body = await requestClone.text();
            
            await storeOfflineAction({
                id: generateId(),
                url: request.url,
                method: request.method,
                headers: Object.fromEntries(request.headers.entries()),
                body: body,
                timestamp: Date.now()
            });
            
            return new Response(JSON.stringify({ success: true, offline: true }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }
        
        throw error;
    }
}

// Handle static resources with cache-first strategy
async function handleStaticRequest(request) {
    const cachedResponse = await getCachedResponse(request);
    
    // Return cached version if available and not expired
    if (cachedResponse && !isExpired(cachedResponse, 'static')) {
        return cachedResponse;
    }
    
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            await cacheWithTTL(request, networkResponse.clone(), 'static');
        }
        
        return networkResponse;
    } catch (error) {
        // Return cached version even if expired
        if (cachedResponse) {
            return cachedResponse;
        }
        
        throw error;
    }
}

// Handle page requests with network-first strategy
async function handlePageRequest(request) {
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            await cacheWithTTL(request, networkResponse.clone(), 'pages');
        }
        
        return networkResponse;
    } catch (error) {
        // Try cache for navigation requests
        if (request.mode === 'navigate') {
            const cachedResponse = await getCachedResponse(request);
            if (cachedResponse) {
                return cachedResponse;
            }
            
            // Return offline page as last resort
            return caches.match('/offline');
        }
        
        throw error;
    }
}

// Cache response with TTL metadata
async function cacheWithTTL(request, response, type) {
    const cache = await caches.open(CACHE_NAME);
    
    // Add TTL metadata to response headers
    const responseWithTTL = new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: {
            ...Object.fromEntries(response.headers.entries()),
            'sw-cached-at': Date.now().toString(),
            'sw-cache-type': type
        }
    });
    
    await cache.put(request, responseWithTTL);
}

// Get cached response
async function getCachedResponse(request) {
    const cache = await caches.open(CACHE_NAME);
    return await cache.match(request);
}

// Check if cached response is expired
function isExpired(response, type) {
    const cachedAt = response.headers.get('sw-cached-at');
    
    if (!cachedAt) {
        return true; // No timestamp, consider expired
    }
    
    const cacheTime = parseInt(cachedAt);
    const ttl = CACHE_TTL[type] || CACHE_TTL.pages;
    
    return (Date.now() - cacheTime) > ttl;
}

// Store offline actions in IndexedDB
async function storeOfflineAction(action) {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('OfflineActions', 1);
        
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            const db = request.result;
            const transaction = db.transaction(['actions'], 'readwrite');
            const store = transaction.objectStore('actions');
            
            store.add(action);
            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error);
        };
        
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains('actions')) {
                const store = db.createObjectStore('actions', { keyPath: 'id', autoIncrement: true });
                store.createIndex('timestamp', 'timestamp');
            }
        };
    });
}

// Generate unique ID for offline actions
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Handle background sync
self.addEventListener('sync', event => {
    if (event.tag === 'sync-offline-actions') {
        event.waitUntil(syncOfflineActions());
    }
});

// Sync offline actions when back online
async function syncOfflineActions() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('OfflineActions', 1);
        
        request.onsuccess = () => {
            const db = request.result;
            const transaction = db.transaction(['actions'], 'readonly');
            const store = transaction.objectStore('actions');
            const getAllRequest = store.getAll();
            
            getAllRequest.onsuccess = async () => {
                const actions = getAllRequest.result;
                
                for (const action of actions) {
                    try {
                        await fetch(action.url, {
                            method: action.method,
                            headers: action.headers,
                            body: action.body
                        });
                        
                        // Remove synced action
                        const deleteTransaction = db.transaction(['actions'], 'readwrite');
                        const deleteStore = deleteTransaction.objectStore('actions');
                        deleteStore.delete(action.id);
                    } catch (error) {
                        console.error('Failed to sync action:', error);
                    }
                }
                
                resolve();
            };
        };
        
        request.onerror = () => reject(request.error);
    });
}

// Handle push notifications (for future enhancement)
self.addEventListener('push', event => {
    if (event.data) {
        const data = event.data.json();
        
        const options = {
            body: data.body,
            icon: '/static/images/icon-192.png',
            badge: '/static/images/badge.png',
            data: data.data,
            actions: [
                {
                    action: 'view',
                    title: 'View',
                    icon: '/static/images/view-icon.png'
                },
                {
                    action: 'dismiss',
                    title: 'Dismiss',
                    icon: '/static/images/dismiss-icon.png'
                }
            ]
        };
        
        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    if (event.action === 'view') {
        const url = event.notification.data?.url || '/';
        event.waitUntil(
            clients.openWindow(url)
        );
    }
});