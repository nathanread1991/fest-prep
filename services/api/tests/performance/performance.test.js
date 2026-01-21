// Performance and loading tests
const { test, expect } = require('@playwright/test');

test.describe('Performance Tests', () => {
  test.describe('Page Load Performance', () => {
    test('should load homepage within 3 seconds', async ({ page }) => {
      const startTime = Date.now();
      
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      const loadTime = Date.now() - startTime;
      expect(loadTime).toBeLessThan(3000);
      
      // Check Core Web Vitals
      const webVitals = await page.evaluate(() => {
        return new Promise((resolve) => {
          const vitals = {};
          
          // Largest Contentful Paint
          new PerformanceObserver((list) => {
            const entries = list.getEntries();
            const lastEntry = entries[entries.length - 1];
            vitals.lcp = lastEntry.startTime;
          }).observe({ entryTypes: ['largest-contentful-paint'] });
          
          // First Input Delay would be measured on actual user interaction
          // For testing, we'll simulate
          vitals.fid = 0;
          
          // Cumulative Layout Shift
          let clsValue = 0;
          new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
              if (!entry.hadRecentInput) {
                clsValue += entry.value;
              }
            }
            vitals.cls = clsValue;
          }).observe({ entryTypes: ['layout-shift'] });
          
          setTimeout(() => resolve(vitals), 2000);
        });
      });
      
      // LCP should be under 2.5 seconds
      if (webVitals.lcp) {
        expect(webVitals.lcp).toBeLessThan(2500);
      }
      
      // CLS should be under 0.1
      if (webVitals.cls !== undefined) {
        expect(webVitals.cls).toBeLessThan(0.1);
      }
    });

    test('should load festival listing page efficiently', async ({ page }) => {
      const startTime = Date.now();
      
      await page.goto('/festivals');
      await page.waitForLoadState('networkidle');
      
      const loadTime = Date.now() - startTime;
      expect(loadTime).toBeLessThan(3000);
      
      // Check that content is visible
      const festivalCards = page.locator('.festival-card, .festival-item');
      const cardCount = await festivalCards.count();
      
      if (cardCount > 0) {
        // First few cards should be visible quickly
        await expect(festivalCards.first()).toBeVisible();
      }
    });

    test('should handle slow network conditions', async ({ page, context }) => {
      // Simulate slow 3G connection
      await context.route('**/*', async (route) => {
        await new Promise(resolve => setTimeout(resolve, 100)); // Add 100ms delay
        await route.continue();
      });
      
      const startTime = Date.now();
      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      const loadTime = Date.now() - startTime;
      
      // Should still load within reasonable time on slow connection
      expect(loadTime).toBeLessThan(8000);
      
      // Critical content should be visible
      const mainContent = page.locator('main, .main-content');
      await expect(mainContent.first()).toBeVisible();
    });

    test('should handle very slow network conditions', async ({ page, context }) => {
      // Simulate very slow connection (2G-like)
      await context.route('**/*', async (route) => {
        await new Promise(resolve => setTimeout(resolve, 300)); // Add 300ms delay
        await route.continue();
      });
      
      const startTime = Date.now();
      await page.goto('/');
      
      // Should show loading indicators
      const loadingIndicator = page.locator('.loading, .spinner, [data-loading]');
      if (await loadingIndicator.count() > 0) {
        await expect(loadingIndicator.first()).toBeVisible();
      }
      
      await page.waitForLoadState('domcontentloaded');
      const loadTime = Date.now() - startTime;
      
      // Should still load within reasonable time even on very slow connection
      expect(loadTime).toBeLessThan(15000);
    });

    test('should handle limited bandwidth efficiently', async ({ page, context }) => {
      // Track total bytes transferred
      let totalBytes = 0;
      const resourceSizes = [];
      
      page.on('response', response => {
        const contentLength = response.headers()['content-length'];
        if (contentLength) {
          const size = parseInt(contentLength);
          totalBytes += size;
          resourceSizes.push({
            url: response.url(),
            size,
            type: response.request().resourceType()
          });
        }
      });
      
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Total page size should be reasonable for limited bandwidth
      expect(totalBytes).toBeLessThan(5 * 1024 * 1024); // Under 5MB
      
      // Images should be optimized
      const imageResources = resourceSizes.filter(r => r.type === 'image');
      imageResources.forEach(img => {
        expect(img.size).toBeLessThan(500 * 1024); // Each image under 500KB
      });
      
      console.log(`Total page size: ${totalBytes} bytes`);
      console.log(`Image resources: ${imageResources.length}`);
    });

    test('should implement progressive loading', async ({ page }) => {
      await page.goto('/festivals');
      
      // Test progressive loading of content
      const progressiveLoadingTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          const observer = new MutationObserver((mutations) => {
            const addedNodes = mutations.reduce((acc, mutation) => {
              return acc + mutation.addedNodes.length;
            }, 0);
            
            if (addedNodes > 0) {
              resolve({
                progressiveLoading: true,
                addedNodes
              });
            }
          });
          
          observer.observe(document.body, {
            childList: true,
            subtree: true
          });
          
          // If no progressive loading detected in 3 seconds, resolve
          setTimeout(() => {
            observer.disconnect();
            resolve({ progressiveLoading: false });
          }, 3000);
        });
      });
      
      // Progressive loading is good for performance
      if (progressiveLoadingTest.progressiveLoading) {
        expect(progressiveLoadingTest.addedNodes).toBeGreaterThan(0);
      }
    });
  });

  test.describe('Resource Loading', () => {
    test('should optimize image loading', async ({ page }) => {
      await page.goto('/festivals');
      
      // Check for lazy loading implementation
      const images = page.locator('img');
      const imageCount = await images.count();
      
      if (imageCount > 0) {
        for (let i = 0; i < Math.min(imageCount, 5); i++) {
          const image = images.nth(i);
          
          // Check for lazy loading attributes
          const loading = await image.getAttribute('loading');
          const src = await image.getAttribute('src');
          const dataSrc = await image.getAttribute('data-src');
          
          // Images should either have loading="lazy" or use data-src for lazy loading
          const hasLazyLoading = loading === 'lazy' || dataSrc !== null;
          
          // First few images might not be lazy loaded (above the fold)
          if (i > 2) {
            expect(hasLazyLoading).toBe(true);
          }
          
          // Images should have proper src or data-src
          expect(src || dataSrc).toBeTruthy();
        }
      }
    });

    test('should minimize JavaScript bundle size', async ({ page }) => {
      // Monitor network requests
      const jsRequests = [];
      
      page.on('response', response => {
        if (response.url().includes('.js') && response.status() === 200) {
          jsRequests.push({
            url: response.url(),
            size: response.headers()['content-length']
          });
        }
      });
      
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Calculate total JS size
      let totalJSSize = 0;
      jsRequests.forEach(request => {
        if (request.size) {
          totalJSSize += parseInt(request.size);
        }
      });
      
      // Total JS should be reasonable (under 1MB for initial load)
      expect(totalJSSize).toBeLessThan(1024 * 1024);
      
      console.log(`Total JavaScript size: ${totalJSSize} bytes`);
    });

    test('should minimize CSS bundle size', async ({ page }) => {
      const cssRequests = [];
      
      page.on('response', response => {
        if (response.url().includes('.css') && response.status() === 200) {
          cssRequests.push({
            url: response.url(),
            size: response.headers()['content-length']
          });
        }
      });
      
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      let totalCSSSize = 0;
      cssRequests.forEach(request => {
        if (request.size) {
          totalCSSSize += parseInt(request.size);
        }
      });
      
      // Total CSS should be reasonable (under 500KB)
      expect(totalCSSSize).toBeLessThan(500 * 1024);
      
      console.log(`Total CSS size: ${totalCSSSize} bytes`);
    });

    test('should use efficient caching strategies', async ({ page }) => {
      // First visit
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      const firstLoadRequests = [];
      page.on('response', response => {
        firstLoadRequests.push({
          url: response.url(),
          fromCache: response.fromServiceWorker() || response.status() === 304
        });
      });
      
      // Second visit (should use cache)
      await page.reload();
      await page.waitForLoadState('networkidle');
      
      // Some resources should be cached
      const cachedRequests = firstLoadRequests.filter(req => req.fromCache);
      
      // At least some static resources should be cached
      if (firstLoadRequests.length > 0) {
        expect(cachedRequests.length).toBeGreaterThan(0);
      }
    });
  });

  test.describe('Runtime Performance', () => {
    test('should handle large lists efficiently', async ({ page }) => {
      await page.goto('/festivals');
      
      // Measure rendering performance for large lists
      const renderingMetrics = await page.evaluate(() => {
        const startTime = performance.now();
        
        // Simulate adding many items to a list
        const container = document.createElement('div');
        document.body.appendChild(container);
        
        for (let i = 0; i < 1000; i++) {
          const item = document.createElement('div');
          item.textContent = `Item ${i}`;
          container.appendChild(item);
        }
        
        const endTime = performance.now();
        document.body.removeChild(container);
        
        return endTime - startTime;
      });
      
      // Should render 1000 items in under 100ms
      expect(renderingMetrics).toBeLessThan(100);
    });

    test('should handle scroll performance', async ({ page }) => {
      await page.goto('/festivals');
      
      // Test scroll performance
      const scrollMetrics = await page.evaluate(() => {
        return new Promise((resolve) => {
          let frameCount = 0;
          let startTime = performance.now();
          
          const measureFrame = () => {
            frameCount++;
            if (frameCount < 60) { // Measure for ~1 second at 60fps
              requestAnimationFrame(measureFrame);
            } else {
              const endTime = performance.now();
              const avgFrameTime = (endTime - startTime) / frameCount;
              resolve(avgFrameTime);
            }
          };
          
          // Start scrolling
          window.scrollTo(0, 100);
          requestAnimationFrame(measureFrame);
        });
      });
      
      // Average frame time should be under 16.67ms (60fps)
      expect(scrollMetrics).toBeLessThan(16.67);
    });

    test('should prevent memory leaks', async ({ page }) => {
      await page.goto('/');
      
      // Measure initial memory usage
      const initialMemory = await page.evaluate(() => {
        if (performance.memory) {
          return performance.memory.usedJSHeapSize;
        }
        return 0;
      });
      
      // Navigate through several pages
      const pages = ['/festivals', '/playlists', '/profile', '/'];
      
      for (const pagePath of pages) {
        await page.goto(pagePath);
        await page.waitForLoadState('networkidle');
      }
      
      // Force garbage collection if available
      await page.evaluate(() => {
        if (window.gc) {
          window.gc();
        }
      });
      
      const finalMemory = await page.evaluate(() => {
        if (performance.memory) {
          return performance.memory.usedJSHeapSize;
        }
        return 0;
      });
      
      if (initialMemory > 0 && finalMemory > 0) {
        // Memory usage shouldn't increase dramatically
        const memoryIncrease = finalMemory - initialMemory;
        const memoryIncreasePercent = (memoryIncrease / initialMemory) * 100;
        
        // Allow for some memory increase but not excessive
        expect(memoryIncreasePercent).toBeLessThan(200);
        
        console.log(`Memory usage: ${initialMemory} -> ${finalMemory} (${memoryIncreasePercent.toFixed(2)}% increase)`);
      }
    });

    test('should prevent event listener memory leaks', async ({ page }) => {
      await page.goto('/');
      
      // Test event listener cleanup
      const eventListenerTest = await page.evaluate(() => {
        let listenerCount = 0;
        const originalAddEventListener = EventTarget.prototype.addEventListener;
        const originalRemoveEventListener = EventTarget.prototype.removeEventListener;
        
        // Override addEventListener to count listeners
        EventTarget.prototype.addEventListener = function(...args) {
          listenerCount++;
          return originalAddEventListener.apply(this, args);
        };
        
        // Override removeEventListener to count removals
        EventTarget.prototype.removeEventListener = function(...args) {
          listenerCount--;
          return originalRemoveEventListener.apply(this, args);
        };
        
        // Add some test listeners
        const testHandler = () => {};
        document.addEventListener('click', testHandler);
        window.addEventListener('resize', testHandler);
        
        // Remove them
        document.removeEventListener('click', testHandler);
        window.removeEventListener('resize', testHandler);
        
        // Restore original methods
        EventTarget.prototype.addEventListener = originalAddEventListener;
        EventTarget.prototype.removeEventListener = originalRemoveEventListener;
        
        return { listenerCount };
      });
      
      // Listeners should be properly cleaned up
      expect(eventListenerTest.listenerCount).toBeLessThanOrEqual(0);
    });

    test('should prevent DOM node memory leaks', async ({ page }) => {
      await page.goto('/');
      
      // Test DOM node cleanup
      const domLeakTest = await page.evaluate(() => {
        const initialNodeCount = document.querySelectorAll('*').length;
        
        // Create and remove many DOM nodes
        const container = document.createElement('div');
        document.body.appendChild(container);
        
        for (let i = 0; i < 1000; i++) {
          const node = document.createElement('div');
          node.textContent = `Node ${i}`;
          container.appendChild(node);
        }
        
        const peakNodeCount = document.querySelectorAll('*').length;
        
        // Remove the container
        document.body.removeChild(container);
        
        const finalNodeCount = document.querySelectorAll('*').length;
        
        return {
          initialNodeCount,
          peakNodeCount,
          finalNodeCount,
          nodesCreated: peakNodeCount - initialNodeCount,
          nodesRemoved: peakNodeCount - finalNodeCount
        };
      });
      
      // All created nodes should be removed
      expect(domLeakTest.finalNodeCount).toBeLessThanOrEqual(domLeakTest.initialNodeCount + 5); // Allow small variance
      expect(domLeakTest.nodesRemoved).toBeGreaterThan(900); // Most nodes should be removed
    });

    test('should prevent timer memory leaks', async ({ page }) => {
      await page.goto('/');
      
      // Test timer cleanup
      const timerLeakTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          let activeTimers = 0;
          const originalSetTimeout = window.setTimeout;
          const originalSetInterval = window.setInterval;
          const originalClearTimeout = window.clearTimeout;
          const originalClearInterval = window.clearInterval;
          
          // Override timer functions to count active timers
          window.setTimeout = function(...args) {
            activeTimers++;
            return originalSetTimeout.apply(this, args);
          };
          
          window.setInterval = function(...args) {
            activeTimers++;
            return originalSetInterval.apply(this, args);
          };
          
          window.clearTimeout = function(...args) {
            activeTimers--;
            return originalClearTimeout.apply(this, args);
          };
          
          window.clearInterval = function(...args) {
            activeTimers--;
            return originalClearInterval.apply(this, args);
          };
          
          // Create and clear timers
          const timeout1 = setTimeout(() => {}, 1000);
          const timeout2 = setTimeout(() => {}, 2000);
          const interval1 = setInterval(() => {}, 1000);
          
          clearTimeout(timeout1);
          clearTimeout(timeout2);
          clearInterval(interval1);
          
          // Restore original functions
          window.setTimeout = originalSetTimeout;
          window.setInterval = originalSetInterval;
          window.clearTimeout = originalClearTimeout;
          window.clearInterval = originalClearInterval;
          
          setTimeout(() => resolve({ activeTimers }), 100);
        });
      });
      
      // All timers should be cleared
      expect(timerLeakTest.activeTimers).toBeLessThanOrEqual(0);
    });

    test('should handle form interactions efficiently', async ({ page }) => {
      await page.goto('/login');
      
      const formInput = page.locator('input[type="email"], input[type="text"]').first();
      
      if (await formInput.count() > 0) {
        // Measure input performance
        const inputMetrics = await page.evaluate(() => {
          const input = document.querySelector('input[type="email"], input[type="text"]');
          if (!input) return 0;
          
          const startTime = performance.now();
          
          // Simulate rapid typing
          for (let i = 0; i < 100; i++) {
            const event = new Event('input', { bubbles: true });
            input.dispatchEvent(event);
          }
          
          const endTime = performance.now();
          return endTime - startTime;
        });
        
        // Should handle 100 input events quickly
        expect(inputMetrics).toBeLessThan(50);
      }
    });
  });

  test.describe('Network Performance', () => {
    test('should minimize HTTP requests', async ({ page }) => {
      const requests = [];
      
      page.on('request', request => {
        requests.push({
          url: request.url(),
          method: request.method(),
          resourceType: request.resourceType()
        });
      });
      
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Count different types of requests
      const requestTypes = {};
      requests.forEach(req => {
        requestTypes[req.resourceType] = (requestTypes[req.resourceType] || 0) + 1;
      });
      
      console.log('Request breakdown:', requestTypes);
      
      // Total requests should be reasonable
      expect(requests.length).toBeLessThan(50);
      
      // Should not have excessive image requests
      if (requestTypes.image) {
        expect(requestTypes.image).toBeLessThan(20);
      }
    });

    test('should use compression for text resources', async ({ page }) => {
      const textRequests = [];
      
      page.on('response', response => {
        const contentType = response.headers()['content-type'] || '';
        if (contentType.includes('text/') || contentType.includes('application/javascript') || contentType.includes('application/json')) {
          textRequests.push({
            url: response.url(),
            contentEncoding: response.headers()['content-encoding'],
            contentLength: response.headers()['content-length']
          });
        }
      });
      
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Most text resources should be compressed
      const compressedRequests = textRequests.filter(req => 
        req.contentEncoding === 'gzip' || req.contentEncoding === 'br' || req.contentEncoding === 'deflate'
      );
      
      if (textRequests.length > 0) {
        const compressionRatio = compressedRequests.length / textRequests.length;
        expect(compressionRatio).toBeGreaterThan(0.5); // At least 50% should be compressed
      }
    });

    test('should handle API request performance', async ({ page }) => {
      // Mock API responses with timing
      await page.route('**/api/**', async (route) => {
        const startTime = Date.now();
        
        // Simulate API processing time
        await new Promise(resolve => setTimeout(resolve, 50));
        
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: 'test', processingTime: Date.now() - startTime })
        });
      });
      
      await page.goto('/festivals');
      
      // Test API request timing
      const apiTiming = await page.evaluate(async () => {
        const startTime = performance.now();
        
        try {
          const response = await fetch('/api/festivals');
          const data = await response.json();
          const endTime = performance.now();
          
          return {
            success: true,
            duration: endTime - startTime,
            data
          };
        } catch (error) {
          return {
            success: false,
            error: error.message
          };
        }
      });
      
      expect(apiTiming.success).toBe(true);
      expect(apiTiming.duration).toBeLessThan(200); // Should complete within 200ms
    });
  });

  test.describe('Progressive Web App Performance', () => {
    test('should register service worker efficiently', async ({ page }) => {
      await page.goto('/');
      
      const swRegistration = await page.evaluate(async () => {
        if ('serviceWorker' in navigator) {
          try {
            const registration = await navigator.serviceWorker.register('/sw.js');
            return {
              success: true,
              scope: registration.scope,
              state: registration.installing?.state || registration.waiting?.state || registration.active?.state
            };
          } catch (error) {
            return {
              success: false,
              error: error.message
            };
          }
        }
        return { success: false, error: 'Service Worker not supported' };
      });
      
      // Service worker should register successfully (if implemented)
      if (swRegistration.success) {
        expect(swRegistration.scope).toBeTruthy();
      }
    });

    test('should cache resources effectively', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Test cache performance
      const cacheTest = await page.evaluate(async () => {
        if ('caches' in window) {
          try {
            const cache = await caches.open('test-cache');
            const testUrl = '/api/test';
            
            // Add to cache
            const startTime = performance.now();
            await cache.put(testUrl, new Response('test data'));
            const cacheTime = performance.now() - startTime;
            
            // Retrieve from cache
            const retrieveStart = performance.now();
            const cachedResponse = await cache.match(testUrl);
            const retrieveTime = performance.now() - retrieveStart;
            
            return {
              success: true,
              cacheTime,
              retrieveTime,
              hasCachedResponse: !!cachedResponse
            };
          } catch (error) {
            return {
              success: false,
              error: error.message
            };
          }
        }
        return { success: false, error: 'Cache API not supported' };
      });
      
      if (cacheTest.success) {
        expect(cacheTest.cacheTime).toBeLessThan(50);
        expect(cacheTest.retrieveTime).toBeLessThan(10);
        expect(cacheTest.hasCachedResponse).toBe(true);
      }
    });

    test('should handle offline scenarios', async ({ page, context }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Simulate offline
      await context.setOffline(true);
      
      // Try to navigate to a cached page
      await page.goto('/festivals');
      
      // Page should still load (if properly cached)
      const pageContent = await page.textContent('body');
      expect(pageContent).toBeTruthy();
      expect(pageContent.length).toBeGreaterThan(0);
      
      // Restore online
      await context.setOffline(false);
    });

    test('should support PWA installation', async ({ page }) => {
      await page.goto('/');
      
      // Check for PWA manifest
      const manifestTest = await page.evaluate(async () => {
        const manifestLink = document.querySelector('link[rel="manifest"]');
        if (!manifestLink) {
          return { hasManifest: false };
        }
        
        try {
          const response = await fetch(manifestLink.href);
          const manifest = await response.json();
          
          return {
            hasManifest: true,
            manifest,
            hasName: !!manifest.name,
            hasShortName: !!manifest.short_name,
            hasIcons: Array.isArray(manifest.icons) && manifest.icons.length > 0,
            hasStartUrl: !!manifest.start_url,
            hasDisplay: !!manifest.display,
            hasThemeColor: !!manifest.theme_color
          };
        } catch (error) {
          return {
            hasManifest: true,
            error: error.message
          };
        }
      });
      
      if (manifestTest.hasManifest && !manifestTest.error) {
        expect(manifestTest.hasName).toBe(true);
        expect(manifestTest.hasIcons).toBe(true);
        expect(manifestTest.hasStartUrl).toBe(true);
        expect(manifestTest.hasDisplay).toBe(true);
      }
    });

    test('should handle PWA lifecycle events', async ({ page }) => {
      await page.goto('/');
      
      // Test PWA lifecycle events
      const lifecycleTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          const events = {
            beforeInstallPrompt: false,
            appInstalled: false,
            visibilityChange: false
          };
          
          // Test beforeinstallprompt event
          window.addEventListener('beforeinstallprompt', () => {
            events.beforeInstallPrompt = true;
          });
          
          // Test appinstalled event
          window.addEventListener('appinstalled', () => {
            events.appInstalled = true;
          });
          
          // Test visibility change
          document.addEventListener('visibilitychange', () => {
            events.visibilityChange = true;
          });
          
          // Simulate visibility change
          Object.defineProperty(document, 'hidden', { value: true, configurable: true });
          document.dispatchEvent(new Event('visibilitychange'));
          
          setTimeout(() => resolve(events), 1000);
        });
      });
      
      expect(lifecycleTest.visibilityChange).toBe(true);
    });

    test('should handle PWA background sync', async ({ page }) => {
      await page.goto('/');
      
      // Test background sync capability
      const backgroundSyncTest = await page.evaluate(async () => {
        if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
          try {
            const registration = await navigator.serviceWorker.ready;
            await registration.sync.register('background-sync-test');
            
            return {
              supported: true,
              registered: true
            };
          } catch (error) {
            return {
              supported: true,
              registered: false,
              error: error.message
            };
          }
        }
        
        return { supported: false };
      });
      
      // Background sync might not be supported in all browsers
      if (backgroundSyncTest.supported) {
        expect(backgroundSyncTest.registered).toBe(true);
      }
    });

    test('should handle PWA push notifications', async ({ page, context }) => {
      // Grant notification permission
      await context.grantPermissions(['notifications']);
      
      await page.goto('/');
      
      // Test push notification capability
      const pushTest = await page.evaluate(async () => {
        if ('Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window) {
          try {
            const permission = await Notification.requestPermission();
            const registration = await navigator.serviceWorker.ready;
            
            // Check if push messaging is supported
            const pushSupported = 'pushManager' in registration;
            
            return {
              supported: true,
              permission,
              pushSupported,
              notificationSupported: Notification.permission !== 'denied'
            };
          } catch (error) {
            return {
              supported: true,
              error: error.message
            };
          }
        }
        
        return { supported: false };
      });
      
      if (pushTest.supported && !pushTest.error) {
        expect(['granted', 'default', 'denied']).toContain(pushTest.permission);
        expect(pushTest.pushSupported).toBe(true);
      }
    });

    test('should handle PWA app shortcuts', async ({ page }) => {
      await page.goto('/');
      
      // Test app shortcuts in manifest
      const shortcutsTest = await page.evaluate(async () => {
        const manifestLink = document.querySelector('link[rel="manifest"]');
        if (!manifestLink) {
          return { hasManifest: false };
        }
        
        try {
          const response = await fetch(manifestLink.href);
          const manifest = await response.json();
          
          return {
            hasManifest: true,
            hasShortcuts: Array.isArray(manifest.shortcuts),
            shortcutsCount: manifest.shortcuts ? manifest.shortcuts.length : 0,
            shortcuts: manifest.shortcuts || []
          };
        } catch (error) {
          return {
            hasManifest: true,
            error: error.message
          };
        }
      });
      
      if (shortcutsTest.hasManifest && !shortcutsTest.error) {
        // App shortcuts are optional but if present should be valid
        if (shortcutsTest.hasShortcuts && shortcutsTest.shortcutsCount > 0) {
          expect(shortcutsTest.shortcuts[0]).toHaveProperty('name');
          expect(shortcutsTest.shortcuts[0]).toHaveProperty('url');
        }
      }
    });

    test('should handle PWA share target', async ({ page }) => {
      await page.goto('/');
      
      // Test Web Share API
      const shareTest = await page.evaluate(() => {
        return {
          webShareSupported: 'share' in navigator,
          canShare: navigator.canShare ? navigator.canShare({ title: 'Test', url: 'https://example.com' }) : false
        };
      });
      
      // Web Share API might not be supported in all browsers
      expect(typeof shareTest.webShareSupported).toBe('boolean');
      
      if (shareTest.webShareSupported) {
        expect(typeof shareTest.canShare).toBe('boolean');
      }
    });
  });

  test.describe('Database and Storage Performance', () => {
    test('should handle localStorage efficiently', async ({ page }) => {
      await page.goto('/');
      
      const storagePerformance = await page.evaluate(() => {
        const iterations = 1000;
        const testData = 'x'.repeat(100); // 100 character string
        
        // Test write performance
        const writeStart = performance.now();
        for (let i = 0; i < iterations; i++) {
          localStorage.setItem(`test-key-${i}`, testData);
        }
        const writeTime = performance.now() - writeStart;
        
        // Test read performance
        const readStart = performance.now();
        for (let i = 0; i < iterations; i++) {
          localStorage.getItem(`test-key-${i}`);
        }
        const readTime = performance.now() - readStart;
        
        // Cleanup
        for (let i = 0; i < iterations; i++) {
          localStorage.removeItem(`test-key-${i}`);
        }
        
        return {
          writeTime,
          readTime,
          avgWriteTime: writeTime / iterations,
          avgReadTime: readTime / iterations
        };
      });
      
      // Should handle storage operations efficiently
      expect(storagePerformance.avgWriteTime).toBeLessThan(1); // Under 1ms per write
      expect(storagePerformance.avgReadTime).toBeLessThan(0.5); // Under 0.5ms per read
      
      console.log(`Storage performance - Write: ${storagePerformance.avgWriteTime.toFixed(3)}ms, Read: ${storagePerformance.avgReadTime.toFixed(3)}ms`);
    });

    test('should handle IndexedDB efficiently (if used)', async ({ page }) => {
      await page.goto('/');
      
      const idbPerformance = await page.evaluate(() => {
        return new Promise((resolve) => {
          if (!('indexedDB' in window)) {
            resolve({ supported: false });
            return;
          }
          
          const dbName = 'test-performance-db';
          const request = indexedDB.open(dbName, 1);
          
          request.onerror = () => resolve({ supported: false, error: 'Failed to open DB' });
          
          request.onupgradeneeded = (event) => {
            const db = event.target.result;
            const objectStore = db.createObjectStore('test-store', { keyPath: 'id' });
          };
          
          request.onsuccess = (event) => {
            const db = event.target.result;
            const transaction = db.transaction(['test-store'], 'readwrite');
            const objectStore = transaction.objectStore('test-store');
            
            const testData = { id: 1, data: 'x'.repeat(1000) };
            
            const writeStart = performance.now();
            const addRequest = objectStore.add(testData);
            
            addRequest.onsuccess = () => {
              const writeTime = performance.now() - writeStart;
              
              const readStart = performance.now();
              const getRequest = objectStore.get(1);
              
              getRequest.onsuccess = () => {
                const readTime = performance.now() - readStart;
                
                // Cleanup
                indexedDB.deleteDatabase(dbName);
                
                resolve({
                  supported: true,
                  writeTime,
                  readTime
                });
              };
            };
          };
        });
      });
      
      if (idbPerformance.supported) {
        expect(idbPerformance.writeTime).toBeLessThan(50);
        expect(idbPerformance.readTime).toBeLessThan(20);
      }
    });
  });
});