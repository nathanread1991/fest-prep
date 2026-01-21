// Performance optimization utilities for Festival Playlist Generator

class PerformanceOptimizer {
    constructor() {
        this.lazyImages = [];
        this.intersectionObserver = null;
        this.loadingIndicators = new Map();
        
        this.init();
    }
    
    init() {
        // Initialize lazy loading
        this.initLazyLoading();
        
        // Initialize progressive loading indicators
        this.initProgressiveLoading();
        
        // Optimize scroll performance
        this.optimizeScrollPerformance();
        
        // Bundle splitting and loading optimization
        this.optimizeBundleLoading();
        
        // Monitor performance
        this.monitorPerformance();
    }
    
    initLazyLoading() {
        // Set up Intersection Observer for lazy loading
        if ('IntersectionObserver' in window) {
            this.intersectionObserver = new IntersectionObserver(
                this.handleIntersection.bind(this),
                {
                    rootMargin: '50px 0px',
                    threshold: 0.01
                }
            );
            
            // Find all lazy-loadable elements
            this.setupLazyElements();
        } else {
            // Fallback for browsers without Intersection Observer
            this.loadAllImages();
        }
    }
    
    setupLazyElements() {
        // Images with data-src attribute
        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(img => {
            this.lazyImages.push(img);
            this.intersectionObserver.observe(img);
        });
        
        // Lazy-loaded content sections
        const lazyContent = document.querySelectorAll('[data-lazy-content]');
        lazyContent.forEach(element => {
            this.intersectionObserver.observe(element);
        });
        
        // Background images
        const lazyBackgrounds = document.querySelectorAll('[data-bg-src]');
        lazyBackgrounds.forEach(element => {
            this.intersectionObserver.observe(element);
        });
    }
    
    handleIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const element = entry.target;
                
                if (element.tagName === 'IMG' && element.dataset.src) {
                    this.loadImage(element);
                } else if (element.dataset.lazyContent) {
                    this.loadContent(element);
                } else if (element.dataset.bgSrc) {
                    this.loadBackgroundImage(element);
                }
                
                this.intersectionObserver.unobserve(element);
            }
        });
    }
    
    loadImage(img) {
        // Create a new image to preload
        const imageLoader = new Image();
        
        imageLoader.onload = () => {
            img.src = img.dataset.src;
            img.classList.add('loaded');
            img.removeAttribute('data-src');
        };
        
        imageLoader.onerror = () => {
            img.classList.add('error');
            // Set a placeholder or error image
            img.src = '/static/images/placeholder.png';
        };
        
        imageLoader.src = img.dataset.src;
    }
    
    loadBackgroundImage(element) {
        const imageLoader = new Image();
        
        imageLoader.onload = () => {
            element.style.backgroundImage = `url(${element.dataset.bgSrc})`;
            element.classList.add('bg-loaded');
            element.removeAttribute('data-bg-src');
        };
        
        imageLoader.src = element.dataset.bgSrc;
    }
    
    loadContent(element) {
        const contentUrl = element.dataset.lazyContent;
        
        if (contentUrl) {
            this.showLoadingIndicator(element);
            
            fetch(contentUrl)
                .then(response => response.text())
                .then(html => {
                    element.innerHTML = html;
                    element.classList.add('content-loaded');
                    element.removeAttribute('data-lazy-content');
                })
                .catch(error => {
                    console.error('Failed to load lazy content:', error);
                    element.innerHTML = '<p>Failed to load content</p>';
                })
                .finally(() => {
                    this.hideLoadingIndicator(element);
                });
        }
    }
    
    loadAllImages() {
        // Fallback for browsers without Intersection Observer
        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(img => {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
        });
    }
    
    initProgressiveLoading() {
        // Set up progressive loading for slow connections
        this.connectionSpeed = this.getConnectionSpeed();
        
        if (this.connectionSpeed === 'slow') {
            this.enableProgressiveMode();
        }
        
        // Listen for network changes
        if ('connection' in navigator) {
            navigator.connection.addEventListener('change', () => {
                this.connectionSpeed = this.getConnectionSpeed();
                this.adjustForConnection();
            });
        }
    }
    
    getConnectionSpeed() {
        if ('connection' in navigator) {
            const connection = navigator.connection;
            
            if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
                return 'slow';
            } else if (connection.effectiveType === '3g') {
                return 'medium';
            } else {
                return 'fast';
            }
        }
        
        return 'unknown';
    }
    
    enableProgressiveMode() {
        document.body.classList.add('progressive-mode');
        
        // Reduce image quality for slow connections
        const images = document.querySelectorAll('img[data-src]');
        images.forEach(img => {
            if (img.dataset.srcLow) {
                img.dataset.src = img.dataset.srcLow;
            }
        });
        
        // Defer non-critical resources
        this.deferNonCriticalResources();
    }
    
    adjustForConnection() {
        if (this.connectionSpeed === 'slow') {
            this.enableProgressiveMode();
        } else {
            document.body.classList.remove('progressive-mode');
        }
    }
    
    deferNonCriticalResources() {
        // Defer loading of non-critical CSS
        const nonCriticalCSS = document.querySelectorAll('link[data-defer]');
        nonCriticalCSS.forEach(link => {
            setTimeout(() => {
                link.rel = 'stylesheet';
            }, 1000);
        });
        
        // Defer loading of non-critical JavaScript
        const nonCriticalJS = document.querySelectorAll('script[data-defer]');
        nonCriticalJS.forEach(script => {
            setTimeout(() => {
                const newScript = document.createElement('script');
                newScript.src = script.dataset.src;
                newScript.async = true;
                document.head.appendChild(newScript);
            }, 2000);
        });
    }
    
    optimizeScrollPerformance() {
        let ticking = false;
        
        const optimizedScrollHandler = () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    this.handleScroll();
                    ticking = false;
                });
                ticking = true;
            }
        };
        
        // Use passive event listeners for better performance
        window.addEventListener('scroll', optimizedScrollHandler, { passive: true });
        
        // Debounce resize events
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
            }, 250);
        }, { passive: true });
    }
    
    handleScroll() {
        // Implement scroll-based optimizations
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        // Show/hide elements based on scroll position
        this.updateScrollBasedElements(scrollTop);
        
        // Lazy load more content if needed
        this.checkForMoreContent(scrollTop);
    }
    
    updateScrollBasedElements(scrollTop) {
        // Example: Hide header when scrolling down, show when scrolling up
        const header = document.querySelector('.header');
        if (header) {
            if (scrollTop > this.lastScrollTop && scrollTop > 100) {
                header.classList.add('header-hidden');
            } else {
                header.classList.remove('header-hidden');
            }
            this.lastScrollTop = scrollTop;
        }
    }
    
    checkForMoreContent(scrollTop) {
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;
        
        // Load more content when near bottom
        if (scrollTop + windowHeight > documentHeight - 1000) {
            this.loadMoreContent();
        }
    }
    
    loadMoreContent() {
        // Implement infinite scroll or pagination
        const loadMoreButton = document.querySelector('[data-load-more]');
        if (loadMoreButton && !loadMoreButton.disabled) {
            loadMoreButton.click();
        }
    }
    
    handleResize() {
        // Recalculate lazy loading thresholds
        this.setupLazyElements();
        
        // Update responsive images
        this.updateResponsiveImages();
    }
    
    updateResponsiveImages() {
        const responsiveImages = document.querySelectorAll('img[data-sizes]');
        responsiveImages.forEach(img => {
            const sizes = JSON.parse(img.dataset.sizes);
            const windowWidth = window.innerWidth;
            
            let bestSize = sizes[0];
            for (const size of sizes) {
                if (windowWidth >= size.minWidth) {
                    bestSize = size;
                }
            }
            
            if (img.src !== bestSize.src) {
                img.src = bestSize.src;
            }
        });
    }
    
    optimizeBundleLoading() {
        // Preload critical resources
        this.preloadCriticalResources();
        
        // Load non-critical bundles asynchronously
        this.loadNonCriticalBundles();
        
        // Implement module loading based on user interaction
        this.setupModuleLoading();
    }
    
    preloadCriticalResources() {
        const criticalResources = [
            '/static/css/main.css',
            '/static/js/main.js'
        ];
        
        criticalResources.forEach(resource => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = resource.endsWith('.css') ? 'style' : 'script';
            link.href = resource;
            document.head.appendChild(link);
        });
    }
    
    loadNonCriticalBundles() {
        // Load non-critical JavaScript modules after page load
        window.addEventListener('load', () => {
            setTimeout(() => {
                this.loadModule('notifications');
                this.loadModule('analytics');
            }, 1000);
        });
    }
    
    loadModule(moduleName) {
        if (!window.loadedModules) {
            window.loadedModules = new Set();
        }
        
        if (window.loadedModules.has(moduleName)) {
            return Promise.resolve();
        }
        
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = `/static/js/${moduleName}.js`;
            script.async = true;
            
            script.onload = () => {
                window.loadedModules.add(moduleName);
                resolve();
            };
            
            script.onerror = reject;
            
            document.head.appendChild(script);
        });
    }
    
    setupModuleLoading() {
        // Load modules based on user interaction
        document.addEventListener('click', (e) => {
            const target = e.target.closest('[data-module]');
            if (target) {
                const moduleName = target.dataset.module;
                this.loadModule(moduleName);
            }
        });
    }
    
    showLoadingIndicator(element) {
        const indicator = document.createElement('div');
        indicator.className = 'loading-indicator';
        indicator.innerHTML = `
            <div class="loading-spinner"></div>
            <p>Loading...</p>
        `;
        
        element.appendChild(indicator);
        this.loadingIndicators.set(element, indicator);
    }
    
    hideLoadingIndicator(element) {
        const indicator = this.loadingIndicators.get(element);
        if (indicator) {
            indicator.remove();
            this.loadingIndicators.delete(element);
        }
    }
    
    monitorPerformance() {
        // Monitor Core Web Vitals
        if ('PerformanceObserver' in window) {
            this.monitorLCP();
            this.monitorFID();
            this.monitorCLS();
        }
        
        // Monitor custom metrics
        this.monitorCustomMetrics();
    }
    
    monitorLCP() {
        // Largest Contentful Paint
        const observer = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            const lastEntry = entries[entries.length - 1];
            
            console.log('LCP:', lastEntry.startTime);
            
            // Send to analytics if needed
            this.reportMetric('lcp', lastEntry.startTime);
        });
        
        observer.observe({ entryTypes: ['largest-contentful-paint'] });
    }
    
    monitorFID() {
        // First Input Delay
        const observer = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            entries.forEach(entry => {
                console.log('FID:', entry.processingStart - entry.startTime);
                this.reportMetric('fid', entry.processingStart - entry.startTime);
            });
        });
        
        observer.observe({ entryTypes: ['first-input'] });
    }
    
    monitorCLS() {
        // Cumulative Layout Shift
        let clsValue = 0;
        
        const observer = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            entries.forEach(entry => {
                if (!entry.hadRecentInput) {
                    clsValue += entry.value;
                }
            });
            
            console.log('CLS:', clsValue);
            this.reportMetric('cls', clsValue);
        });
        
        observer.observe({ entryTypes: ['layout-shift'] });
    }
    
    monitorCustomMetrics() {
        // Time to Interactive
        window.addEventListener('load', () => {
            setTimeout(() => {
                const tti = performance.now();
                console.log('TTI:', tti);
                this.reportMetric('tti', tti);
            }, 0);
        });
        
        // Resource loading times
        window.addEventListener('load', () => {
            const resources = performance.getEntriesByType('resource');
            resources.forEach(resource => {
                if (resource.duration > 1000) {
                    console.log('Slow resource:', resource.name, resource.duration);
                }
            });
        });
    }
    
    reportMetric(name, value) {
        // Send metrics to analytics service
        if (window.gtag) {
            window.gtag('event', 'web_vitals', {
                event_category: 'Performance',
                event_label: name,
                value: Math.round(value)
            });
        }
        
        // Or send to custom analytics endpoint
        // fetch('/api/v1/analytics/performance', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify({ metric: name, value: value })
        // });
    }
}

// Initialize performance optimizer
document.addEventListener('DOMContentLoaded', () => {
    window.performanceOptimizer = new PerformanceOptimizer();
});

// Add CSS for performance optimizations
const performanceStyle = document.createElement('style');
performanceStyle.textContent = `
/* Lazy loading styles */
img[data-src] {
    opacity: 0;
    transition: opacity 0.3s;
}

img.loaded {
    opacity: 1;
}

img.error {
    opacity: 0.5;
    filter: grayscale(100%);
}

/* Loading indicators */
.loading-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    color: #6b7280;
}

.loading-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #e5e7eb;
    border-top: 3px solid #6366f1;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Progressive mode optimizations */
.progressive-mode img {
    image-rendering: auto;
    image-rendering: crisp-edges;
    image-rendering: pixelated;
}

.progressive-mode .non-critical {
    display: none;
}

/* Scroll performance optimizations */
.header {
    transition: transform 0.3s ease;
}

.header-hidden {
    transform: translateY(-100%);
}

/* Reduce motion for users who prefer it */
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* High contrast mode support */
@media (prefers-contrast: high) {
    .loading-spinner {
        border-color: currentColor;
        border-top-color: transparent;
    }
}
`;
document.head.appendChild(performanceStyle);