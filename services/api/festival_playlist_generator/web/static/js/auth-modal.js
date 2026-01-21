/**
 * Authentication Modal Component
 * Handles OAuth provider selection and authentication flow initiation
 */

class AuthModal {
    constructor() {
        this.modal = null;
        this.overlay = null;
        this.closeButton = null;
        this.providerButtons = null;
        this.errorContainer = null;
        this.isOpen = false;
        
        this.init();
    }
    
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupModal());
        } else {
            this.setupModal();
        }
    }
    
    setupModal() {
        // Get modal elements
        this.modal = document.getElementById('auth-modal');
        this.overlay = document.getElementById('auth-modal-overlay');
        this.closeButton = document.getElementById('auth-modal-close');
        this.errorContainer = document.getElementById('auth-modal-error');
        this.providerButtons = document.querySelectorAll('.oauth-button-modal[data-provider]');
        
        if (!this.modal) {
            console.warn('Auth modal not found in DOM');
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
        
        // Provider button events
        this.providerButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const provider = e.currentTarget.getAttribute('data-provider');
                this.initiateOAuth(provider, e.currentTarget);
            });
        });
        
        // Handle authentication errors from URL parameters
        this.handleAuthErrors();
    }
    
    open() {
        if (!this.modal) return;
        
        this.modal.style.display = 'flex';
        this.isOpen = true;
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        // Focus management for accessibility
        this.closeButton?.focus();
        
        // Clear any previous errors
        this.clearError();
        
        // Track modal open event
        this.trackEvent('auth_modal_opened');
    }
    
    close() {
        if (!this.modal) return;
        
        this.modal.style.display = 'none';
        this.isOpen = false;
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        // Clear any loading states
        this.clearLoadingStates();
        
        // Track modal close event
        this.trackEvent('auth_modal_closed');
    }
    
    showError(message) {
        if (!this.errorContainer) return;
        
        this.errorContainer.textContent = message;
        this.errorContainer.style.display = 'block';
        
        // Auto-hide error after 5 seconds
        setTimeout(() => this.clearError(), 5000);
    }
    
    clearError() {
        if (!this.errorContainer) return;
        
        this.errorContainer.style.display = 'none';
        this.errorContainer.textContent = '';
    }
    
    async initiateOAuth(provider, buttonElement) {
        if (!provider) return;
        
        try {
            // Set loading state
            this.setButtonLoading(buttonElement, true);
            this.clearError();
            
            // Track provider selection
            this.trackEvent('oauth_provider_selected', { provider });
            
            // Create form and submit to initiate OAuth flow
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/auth/login/${provider}`;
            form.style.display = 'none';
            
            // Add CSRF token if available
            const csrfToken = this.getCSRFToken();
            if (csrfToken) {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = csrfToken;
                form.appendChild(csrfInput);
            }
            
            document.body.appendChild(form);
            form.submit();
            
        } catch (error) {
            console.error('OAuth initiation error:', error);
            this.showError('Failed to initiate sign-in. Please try again.');
            this.setButtonLoading(buttonElement, false);
            this.trackEvent('oauth_initiation_error', { provider, error: error.message });
        }
    }
    
    setButtonLoading(button, loading) {
        if (!button) return;
        
        if (loading) {
            button.classList.add('loading');
            button.disabled = true;
            
            // Change text to show loading
            const textSpan = button.querySelector('span:last-child');
            if (textSpan) {
                textSpan.setAttribute('data-original-text', textSpan.textContent);
                textSpan.textContent = 'Connecting...';
            }
        } else {
            button.classList.remove('loading');
            button.disabled = false;
            
            // Restore original text
            const textSpan = button.querySelector('span:last-child');
            if (textSpan && textSpan.hasAttribute('data-original-text')) {
                textSpan.textContent = textSpan.getAttribute('data-original-text');
                textSpan.removeAttribute('data-original-text');
            }
        }
    }
    
    clearLoadingStates() {
        this.providerButtons.forEach(button => {
            this.setButtonLoading(button, false);
        });
    }
    
    handleAuthErrors() {
        const urlParams = new URLSearchParams(window.location.search);
        const error = urlParams.get('error');
        
        if (error) {
            let errorMessage = 'An error occurred during sign-in. Please try again.';
            
            switch (error) {
                case 'oauth_denied':
                    errorMessage = 'Authentication was cancelled. Please try again.';
                    break;
                case 'invalid_callback':
                    errorMessage = 'Invalid authentication response. Please try again.';
                    break;
                case 'auth_failed':
                    errorMessage = 'Authentication failed. Please check your credentials and try again.';
                    break;
                case 'server_error':
                    errorMessage = 'Server error occurred. Please try again later.';
                    break;
            }
            
            // Show error and open modal
            setTimeout(() => {
                this.open();
                this.showError(errorMessage);
            }, 100);
            
            // Clean up URL
            const cleanUrl = window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
        }
    }
    
    getCSRFToken() {
        // Try to get CSRF token from meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        
        // Try to get from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') {
                return decodeURIComponent(value);
            }
        }
        
        return null;
    }
    
    trackEvent(eventName, properties = {}) {
        // Track authentication events for analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', eventName, properties);
        }
        
        // Also log to console in development
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.log('Auth Event:', eventName, properties);
        }
    }
    
    // Public API methods
    static getInstance() {
        if (!window.authModalInstance) {
            window.authModalInstance = new AuthModal();
        }
        return window.authModalInstance;
    }
    
    static open() {
        const instance = AuthModal.getInstance();
        instance.open();
    }
    
    static close() {
        const instance = AuthModal.getInstance();
        instance.close();
    }
    
    static showError(message) {
        const instance = AuthModal.getInstance();
        instance.showError(message);
    }
}

// Initialize auth modal when script loads
document.addEventListener('DOMContentLoaded', () => {
    // Don't initialize auth modal on admin pages (they use HTTP Basic Auth)
    if (window.location.pathname.startsWith('/admin')) {
        console.log('Skipping auth modal initialization on admin page');
        return;
    }
    AuthModal.getInstance();
});

// Global functions for easy access
window.openAuthModal = () => AuthModal.open();
window.closeAuthModal = () => AuthModal.close();
window.showAuthError = (message) => AuthModal.showError(message);

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuthModal;
}