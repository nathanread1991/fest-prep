/**
 * Login Prompt Component
 * Shows a modal prompting users to sign in when accessing protected features
 */

class LoginPrompt {
    constructor() {
        this.modal = null;
        this.overlay = null;
        this.closeButton = null;
        this.messageElement = null;
        this.isOpen = false;
        
        this.init();
    }
    
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupPrompt());
        } else {
            this.setupPrompt();
        }
    }
    
    setupPrompt() {
        // Get modal elements
        this.modal = document.getElementById('login-prompt-modal');
        this.overlay = document.getElementById('login-prompt-overlay');
        this.closeButton = document.getElementById('login-prompt-close');
        this.messageElement = document.getElementById('login-prompt-message');
        
        if (!this.modal) {
            console.warn('Login prompt modal not found in DOM');
            return;
        }
        
        this.bindEvents();
    }
    
    bindEvents() {
        // Close modal events
        if (this.closeButton) {
            this.closeButton.addEventListener('click', () => this.close());
        }
        
        if (this.overlay) {
            this.overlay.addEventListener('click', () => this.close());
        }
        
        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }
    
    open(message = null, feature = null) {
        if (!this.modal) return;
        
        // Set custom message if provided
        if (message && this.messageElement) {
            this.messageElement.textContent = message;
        }
        
        this.modal.style.display = 'flex';
        this.isOpen = true;
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        // Focus management for accessibility
        this.closeButton?.focus();
        
        // Track login prompt event
        this.trackEvent('login_prompt_shown', { feature });
    }
    
    close() {
        if (!this.modal) return;
        
        this.modal.style.display = 'none';
        this.isOpen = false;
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        // Reset message to default
        if (this.messageElement) {
            this.messageElement.textContent = 'You need to sign in to access this feature.';
        }
        
        // Track login prompt close event
        this.trackEvent('login_prompt_closed');
    }
    
    trackEvent(eventName, properties = {}) {
        // Track login prompt events for analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', eventName, properties);
        }
        
        // Also log to console in development
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.log('Login Prompt Event:', eventName, properties);
        }
    }
    
    // Public API methods
    static getInstance() {
        if (!window.loginPromptInstance) {
            window.loginPromptInstance = new LoginPrompt();
        }
        return window.loginPromptInstance;
    }
    
    static show(message = null, feature = null) {
        const instance = LoginPrompt.getInstance();
        instance.open(message, feature);
    }
    
    static hide() {
        const instance = LoginPrompt.getInstance();
        instance.close();
    }
}

// Initialize login prompt when script loads
document.addEventListener('DOMContentLoaded', () => {
    // Don't initialize login prompt on admin pages (they use HTTP Basic Auth)
    if (window.location.pathname.startsWith('/admin')) {
        console.log('Skipping login prompt initialization on admin page');
        return;
    }
    LoginPrompt.getInstance();
});

// Global functions for easy access
window.showLoginPrompt = (message, feature) => LoginPrompt.show(message, feature);
window.closeLoginPrompt = () => LoginPrompt.hide();

// Protected feature access handler
window.requireAuth = function(callback, feature = null, message = null) {
    // Check if user is authenticated
    fetch('/api/auth/me', { credentials: 'include' })
        .then(response => {
            if (response.ok) {
                // User is authenticated, execute callback
                if (typeof callback === 'function') {
                    callback();
                } else if (typeof callback === 'string') {
                    // Treat as URL to navigate to
                    window.location.href = callback;
                }
            } else {
                // User is not authenticated, show login prompt
                const defaultMessage = message || `You need to sign in to ${feature || 'access this feature'}.`;
                LoginPrompt.show(defaultMessage, feature);
            }
        })
        .catch(error => {
            console.error('Error checking authentication:', error);
            // Show login prompt on error
            LoginPrompt.show(message || 'Please sign in to continue.', feature);
        });
};

// Intercept clicks on protected links
document.addEventListener('DOMContentLoaded', function() {
    // Don't intercept clicks on admin pages (they use HTTP Basic Auth)
    if (window.location.pathname.startsWith('/admin')) {
        console.log('Skipping protected link interception on admin page');
        return;
    }
    
    // Add click handlers to elements with data-require-auth attribute
    document.addEventListener('click', function(e) {
        const element = e.target.closest('[data-require-auth]');
        if (element) {
            e.preventDefault();
            
            const feature = element.getAttribute('data-feature') || 'access this feature';
            const message = element.getAttribute('data-auth-message') || null;
            const href = element.getAttribute('href') || element.getAttribute('data-href');
            
            requireAuth(href, feature, message);
        }
    });
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LoginPrompt;
}