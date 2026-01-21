// Push Notifications Manager for Festival Playlist Generator

// Wrap in IIFE to prevent redeclaration errors
(function() {
    // Check if already initialized
    if (window.NotificationManager) {
        return;
    }

    class NotificationManager {
        constructor() {
            this.isSupported = 'serviceWorker' in navigator && 'PushManager' in window;
            this.registration = null;
            this.subscription = null;
            this.vapidPublicKey = null;
            this.userId = 'anonymous'; // In real app, get from auth
            
            this.init();
        }
        
        async init() {
            if (!this.isSupported) {
                console.log('Push notifications not supported');
                return;
            }
            
            try {
            // Get service worker registration
            this.registration = await navigator.serviceWorker.ready;
            
            // Get VAPID public key
            await this.getVapidPublicKey();
            
            // Check current subscription status
            await this.checkSubscriptionStatus();
            
            // Set up UI
            this.setupUI();
            
        } catch (error) {
            console.error('Failed to initialize notifications:', error);
        }
    }
    
    async getVapidPublicKey() {
        try {
            const response = await fetch('/api/v1/notifications/vapid-public-key');
            if (response.ok) {
                const data = await response.json();
                this.vapidPublicKey = data.public_key;
            }
        } catch (error) {
            console.error('Failed to get VAPID public key:', error);
        }
    }
    
    async checkSubscriptionStatus() {
        try {
            // Check browser subscription
            this.subscription = await this.registration.pushManager.getSubscription();
            
            // Check server subscription status
            const response = await fetch(`/api/v1/notifications/subscription-status?user_id=${this.userId}`);
            if (response.ok) {
                const data = await response.json();
                this.serverSubscribed = data.subscribed;
            }
            
        } catch (error) {
            console.error('Failed to check subscription status:', error);
        }
    }
    
    async requestPermission() {
        if (!this.isSupported) {
            throw new Error('Push notifications not supported');
        }
        
        const permission = await Notification.requestPermission();
        
        if (permission === 'granted') {
            console.log('Notification permission granted');
            return true;
        } else if (permission === 'denied') {
            console.log('Notification permission denied');
            throw new Error('Notification permission denied');
        } else {
            console.log('Notification permission dismissed');
            throw new Error('Notification permission dismissed');
        }
    }
    
    async subscribe() {
        try {
            // Request permission first
            await this.requestPermission();
            
            if (!this.vapidPublicKey) {
                throw new Error('VAPID public key not available');
            }
            
            // Convert VAPID key to Uint8Array
            const applicationServerKey = this.urlBase64ToUint8Array(this.vapidPublicKey);
            
            // Subscribe to push notifications
            this.subscription = await this.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });
            
            // Send subscription to server
            const response = await fetch('/api/v1/notifications/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    endpoint: this.subscription.endpoint,
                    keys: {
                        p256dh: this.arrayBufferToBase64(this.subscription.getKey('p256dh')),
                        auth: this.arrayBufferToBase64(this.subscription.getKey('auth'))
                    }
                })
            });
            
            if (response.ok) {
                console.log('Successfully subscribed to push notifications');
                this.serverSubscribed = true;
                this.updateUI();
                return true;
            } else {
                throw new Error('Failed to register subscription on server');
            }
            
        } catch (error) {
            console.error('Failed to subscribe to push notifications:', error);
            throw error;
        }
    }
    
    async unsubscribe() {
        try {
            if (this.subscription) {
                await this.subscription.unsubscribe();
                this.subscription = null;
            }
            
            // Notify server
            const response = await fetch('/api/v1/notifications/unsubscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_id: this.userId })
            });
            
            if (response.ok) {
                console.log('Successfully unsubscribed from push notifications');
                this.serverSubscribed = false;
                this.updateUI();
                return true;
            } else {
                throw new Error('Failed to unsubscribe on server');
            }
            
        } catch (error) {
            console.error('Failed to unsubscribe from push notifications:', error);
            throw error;
        }
    }
    
    async sendTestNotification() {
        try {
            const response = await fetch('/api/v1/notifications/send-test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: '🎵 Test Notification',
                    body: 'This is a test notification from Festival Playlist Generator!',
                    data: {
                        type: 'test',
                        url: '/'
                    },
                    actions: [
                        {
                            action: 'view',
                            title: 'View App',
                            icon: '/static/images/action-view.png'
                        }
                    ]
                })
            });
            
            if (response.ok) {
                console.log('Test notification sent');
                return true;
            } else {
                throw new Error('Failed to send test notification');
            }
            
        } catch (error) {
            console.error('Failed to send test notification:', error);
            throw error;
        }
    }
    
    setupUI() {
        // Create notification controls if they don't exist
        let notificationControls = document.getElementById('notification-controls');
        
        if (!notificationControls && this.isSupported) {
            notificationControls = document.createElement('div');
            notificationControls.id = 'notification-controls';
            notificationControls.className = 'notification-controls';
            
            // Add to page (you might want to customize where this appears)
            const container = document.querySelector('.container') || document.body;
            container.appendChild(notificationControls);
        }
        
        this.updateUI();
    }
    
    updateUI() {
        const controls = document.getElementById('notification-controls');
        if (!controls) return;
        
        const isSubscribed = this.subscription && this.serverSubscribed;
        
        controls.innerHTML = `
            <div class="notification-status">
                <h3>🔔 Push Notifications</h3>
                <p class="status ${isSubscribed ? 'subscribed' : 'unsubscribed'}">
                    ${isSubscribed ? '✅ Subscribed' : '❌ Not subscribed'}
                </p>
                
                ${!this.isSupported ? `
                    <p class="error">Push notifications are not supported in this browser.</p>
                ` : `
                    <div class="notification-actions">
                        ${!isSubscribed ? `
                            <button id="subscribe-btn" class="btn btn-primary">
                                Enable Notifications
                            </button>
                        ` : `
                            <button id="unsubscribe-btn" class="btn btn-secondary">
                                Disable Notifications
                            </button>
                            <button id="test-notification-btn" class="btn btn-outline">
                                Send Test
                            </button>
                        `}
                    </div>
                `}
                
                <div class="notification-info">
                    <p><small>Get notified about new festivals, playlist updates, and more!</small></p>
                </div>
            </div>
        `;
        
        // Add event listeners
        const subscribeBtn = document.getElementById('subscribe-btn');
        const unsubscribeBtn = document.getElementById('unsubscribe-btn');
        const testBtn = document.getElementById('test-notification-btn');
        
        if (subscribeBtn) {
            subscribeBtn.addEventListener('click', async () => {
                try {
                    subscribeBtn.disabled = true;
                    subscribeBtn.textContent = 'Subscribing...';
                    await this.subscribe();
                } catch (error) {
                    alert('Failed to enable notifications: ' + error.message);
                } finally {
                    subscribeBtn.disabled = false;
                    subscribeBtn.textContent = 'Enable Notifications';
                }
            });
        }
        
        if (unsubscribeBtn) {
            unsubscribeBtn.addEventListener('click', async () => {
                try {
                    unsubscribeBtn.disabled = true;
                    unsubscribeBtn.textContent = 'Unsubscribing...';
                    await this.unsubscribe();
                } catch (error) {
                    alert('Failed to disable notifications: ' + error.message);
                } finally {
                    unsubscribeBtn.disabled = false;
                    unsubscribeBtn.textContent = 'Disable Notifications';
                }
            });
        }
        
        if (testBtn) {
            testBtn.addEventListener('click', async () => {
                try {
                    testBtn.disabled = true;
                    testBtn.textContent = 'Sending...';
                    await this.sendTestNotification();
                    alert('Test notification sent! Check your notifications.');
                } catch (error) {
                    alert('Failed to send test notification: ' + error.message);
                } finally {
                    testBtn.disabled = false;
                    testBtn.textContent = 'Send Test';
                }
            });
        }
    }
    
    // Utility functions
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
    
    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }
}

    // Add CSS styles (inside IIFE to avoid global scope pollution)
    const notificationStyle = document.createElement('style');
    notificationStyle.textContent = `
.notification-controls {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.5rem;
    margin: 2rem 0;
    max-width: 500px;
}

.notification-controls h3 {
    margin: 0 0 1rem 0;
    color: #374151;
}

.notification-status .status {
    font-weight: 600;
    margin: 0.5rem 0;
}

.notification-status .status.subscribed {
    color: #059669;
}

.notification-status .status.unsubscribed {
    color: #dc2626;
}

.notification-status .error {
    color: #dc2626;
    font-style: italic;
}

.notification-actions {
    margin: 1rem 0;
}

.notification-actions .btn {
    margin-right: 0.5rem;
    margin-bottom: 0.5rem;
}

.notification-info {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #e5e7eb;
}

.notification-info small {
    color: #6b7280;
}
`;
    document.head.appendChild(notificationStyle);

    // Expose NotificationManager globally
    window.NotificationManager = NotificationManager;

    // Initialize notification manager when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.notificationManager = new NotificationManager();
        });
    } else {
        window.notificationManager = new NotificationManager();
    }
})();
