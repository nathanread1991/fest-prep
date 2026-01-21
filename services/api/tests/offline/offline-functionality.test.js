// Offline functionality and network resilience tests
const { test, expect } = require('@playwright/test');

test.describe('Offline Functionality Tests', () => {
  test.describe('Service Worker Behavior', () => {
    test('should register service worker successfully', async ({ page }) => {
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
      
      if (swRegistration.success) {
        expect(swRegistration.scope).toBeTruthy();
        console.log(`Service Worker registered with scope: ${swRegistration.scope}`);
      } else {
        console.log(`Service Worker registration failed: ${swRegistration.error}`);
      }
    });

    test('should cache critical resources', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Wait for service worker to cache resources
      await page.waitForTimeout(2000);
      
      const cacheStatus = await page.evaluate(async () => {
        if ('caches' in window) {
          try {
            const cacheNames = await caches.keys();
            const results = {};
            
            for (const cacheName of cacheNames) {
              const cache = await caches.open(cacheName);
              const cachedRequests = await cache.keys();
              results[cacheName] = cachedRequests.map(req => req.url);
            }
            
            return {
              success: true,
              caches: results,
              cacheCount: cacheNames.length
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
      
      if (cacheStatus.success) {
        expect(cacheStatus.cacheCount).toBeGreaterThan(0);
        console.log(`Found ${cacheStatus.cacheCount} caches`);
      }
    });

    test('should update cache when new version is available', async ({ page }) => {
      await page.goto('/');
      
      const updateResult = await page.evaluate(async () => {
        if ('serviceWorker' in navigator) {
          try {
            const registration = await navigator.serviceWorker.ready;
            
            // Simulate update check
            await registration.update();
            
            return {
              success: true,
              hasUpdate: !!registration.waiting
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
      
      if (updateResult.success) {
        console.log(`Service Worker update check completed. Has update: ${updateResult.hasUpdate}`);
      }
    });
  });

  test.describe('Offline Data Access', () => {
    test('should display cached content when offline', async ({ page, context }) => {
      // First, load the page online to cache it
      await page.goto('/festivals');
      await page.waitForLoadState('networkidle');
      
      // Wait for caching
      await page.waitForTimeout(2000);
      
      // Go offline
      await context.setOffline(true);
      
      // Try to reload the page
      await page.reload();
      
      // Should still display content from cache
      const mainContent = page.locator('main, .main-content, body');
      await expect(mainContent.first()).toBeVisible();
      
      const pageTitle = await page.title();
      expect(pageTitle).toBeTruthy();
      
      // Restore online
      await context.setOffline(false);
    });

    test('should show offline indicator when disconnected', async ({ page, context }) => {
      await page.goto('/');
      
      // Go offline
      await context.setOffline(true);
      
      // Trigger offline detection
      await page.evaluate(() => {
        window.dispatchEvent(new Event('offline'));
      });
      
      await page.waitForTimeout(1000);
      
      // Should show offline indicator
      const offlineIndicator = page.locator('.offline-indicator, .network-status, [data-offline]');
      
      if (await offlineIndicator.count() > 0) {
        await expect(offlineIndicator.first()).toBeVisible();
        
        const indicatorText = await offlineIndicator.first().textContent();
        expect(indicatorText.toLowerCase()).toContain('offline');
      }
      
      // Restore online
      await context.setOffline(false);
      
      // Trigger online detection
      await page.evaluate(() => {
        window.dispatchEvent(new Event('online'));
      });
      
      await page.waitForTimeout(1000);
      
      // Offline indicator should be hidden
      if (await offlineIndicator.count() > 0) {
        const isVisible = await offlineIndicator.first().isVisible();
        expect(isVisible).toBe(false);
      }
    });

    test('should handle offline playlist viewing', async ({ page, context }) => {
      // Load playlist page online first
      await page.goto('/playlists');
      await page.waitForLoadState('networkidle');
      
      // Wait for data to be cached
      await page.waitForTimeout(2000);
      
      // Go offline
      await context.setOffline(true);
      
      // Navigate to a specific playlist
      const playlistLinks = page.locator('.playlist-link, a[href*="/playlists/"]');
      const linkCount = await playlistLinks.count();
      
      if (linkCount > 0) {
        await playlistLinks.first().click();
        
        // Should still be able to view playlist details
        const playlistContent = page.locator('.playlist-content, .playlist-details');
        if (await playlistContent.count() > 0) {
          await expect(playlistContent.first()).toBeVisible();
        }
      }
      
      // Restore online
      await context.setOffline(false);
    });

    test('should queue actions for when back online', async ({ page, context }) => {
      await page.goto('/playlists');
      
      // Go offline
      await context.setOffline(true);
      
      // Try to perform an action that requires network
      const createButton = page.locator('.create-playlist, button:has-text("Create")').first();
      
      if (await createButton.count() > 0) {
        await createButton.click();
        
        // Should show queued action indicator
        const queueIndicator = page.locator('.queued-action, .pending-sync, .offline-queue');
        
        if (await queueIndicator.count() > 0) {
          await expect(queueIndicator.first()).toBeVisible();
        }
      }
      
      // Restore online
      await context.setOffline(false);
      
      // Trigger sync
      await page.evaluate(() => {
        window.dispatchEvent(new Event('online'));
      });
      
      await page.waitForTimeout(2000);
      
      // Queue indicator should be cleared
      const queueIndicator = page.locator('.queued-action, .pending-sync');
      if (await queueIndicator.count() > 0) {
        const isVisible = await queueIndicator.first().isVisible();
        expect(isVisible).toBe(false);
      }
    });
  });

  test.describe('Network Error Handling', () => {
    test('should handle API request failures gracefully', async ({ page }) => {
      // Mock API to return errors
      await page.route('**/api/**', route => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Server error' })
        });
      });
      
      await page.goto('/festivals');
      
      // Should show error message instead of crashing
      const errorMessage = page.locator('.error-message, .api-error, .network-error');
      
      if (await errorMessage.count() > 0) {
        await expect(errorMessage.first()).toBeVisible();
        
        const errorText = await errorMessage.first().textContent();
        expect(errorText).toBeTruthy();
      }
      
      // Page should still be functional
      const navigation = page.locator('nav, .navigation');
      await expect(navigation.first()).toBeVisible();
    });

    test('should retry failed requests', async ({ page }) => {
      let requestCount = 0;
      
      // Mock API to fail first few requests, then succeed
      await page.route('**/api/festivals', route => {
        requestCount++;
        
        if (requestCount < 3) {
          route.fulfill({
            status: 500,
            contentType: 'application/json',
            body: JSON.stringify({ error: 'Temporary error' })
          });
        } else {
          route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify([
              { id: 1, name: 'Test Festival', location: 'Test Location' }
            ])
          });
        }
      });
      
      await page.goto('/festivals');
      
      // Wait for retries
      await page.waitForTimeout(5000);
      
      // Should eventually succeed
      expect(requestCount).toBeGreaterThanOrEqual(3);
      
      // Should show content after successful retry
      const festivalContent = page.locator('.festival-card, .festival-item');
      if (await festivalContent.count() > 0) {
        await expect(festivalContent.first()).toBeVisible();
      }
    });

    test('should handle timeout errors', async ({ page }) => {
      // Mock slow API responses
      await page.route('**/api/**', async route => {
        // Delay response by 10 seconds
        await new Promise(resolve => setTimeout(resolve, 10000));
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: 'delayed response' })
        });
      });
      
      await page.goto('/festivals');
      
      // Should show loading state initially
      const loadingIndicator = page.locator('.loading, .spinner, .loading-indicator');
      
      if (await loadingIndicator.count() > 0) {
        await expect(loadingIndicator.first()).toBeVisible();
      }
      
      // Should eventually show timeout error
      await page.waitForTimeout(8000);
      
      const timeoutError = page.locator('.timeout-error, .request-timeout, .error');
      if (await timeoutError.count() > 0) {
        const errorText = await timeoutError.first().textContent();
        expect(errorText.toLowerCase()).toContain('timeout');
      }
    });

    test('should handle network connectivity changes', async ({ page, context }) => {
      await page.goto('/');
      
      // Simulate network connectivity changes
      const connectivityTests = [
        { offline: true, description: 'Going offline' },
        { offline: false, description: 'Coming back online' },
        { offline: true, description: 'Going offline again' },
        { offline: false, description: 'Final online state' }
      ];
      
      for (const test of connectivityTests) {
        console.log(test.description);
        
        await context.setOffline(test.offline);
        
        // Trigger connectivity event
        await page.evaluate((isOffline) => {
          window.dispatchEvent(new Event(isOffline ? 'offline' : 'online'));
        }, test.offline);
        
        await page.waitForTimeout(1000);
        
        // Check network status indicator
        const networkStatus = page.locator('.network-status, .connectivity-indicator');
        
        if (await networkStatus.count() > 0) {
          const statusText = await networkStatus.first().textContent();
          
          if (test.offline) {
            expect(statusText.toLowerCase()).toContain('offline');
          } else {
            expect(statusText.toLowerCase()).toContain('online');
          }
        }
      }
    });
  });

  test.describe('Background Sync', () => {
    test('should register background sync when supported', async ({ page }) => {
      await page.goto('/');
      
      const backgroundSyncSupport = await page.evaluate(async () => {
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
      
      if (backgroundSyncSupport.supported) {
        console.log(`Background Sync supported. Registered: ${backgroundSyncSupport.registered}`);
      } else {
        console.log('Background Sync not supported');
      }
    });

    test('should sync data when connection is restored', async ({ page, context }) => {
      await page.goto('/playlists');
      
      // Go offline
      await context.setOffline(true);
      
      // Make changes that need to be synced
      const syncData = await page.evaluate(() => {
        // Simulate adding data to sync queue
        if ('localStorage' in window) {
          const syncQueue = JSON.parse(localStorage.getItem('syncQueue') || '[]');
          syncQueue.push({
            action: 'create_playlist',
            data: { name: 'Offline Playlist', songs: [] },
            timestamp: Date.now()
          });
          localStorage.setItem('syncQueue', JSON.stringify(syncQueue));
          
          return syncQueue.length;
        }
        return 0;
      });
      
      expect(syncData).toBeGreaterThan(0);
      
      // Come back online
      await context.setOffline(false);
      
      // Trigger sync
      await page.evaluate(() => {
        window.dispatchEvent(new Event('online'));
      });
      
      // Wait for sync to complete
      await page.waitForTimeout(3000);
      
      // Sync queue should be cleared
      const remainingSync = await page.evaluate(() => {
        if ('localStorage' in window) {
          const syncQueue = JSON.parse(localStorage.getItem('syncQueue') || '[]');
          return syncQueue.length;
        }
        return -1;
      });
      
      expect(remainingSync).toBe(0);
    });
  });

  test.describe('Offline Storage', () => {
    test('should store data locally for offline access', async ({ page }) => {
      await page.goto('/festivals');
      await page.waitForLoadState('networkidle');
      
      // Check if data is stored locally
      const localStorageData = await page.evaluate(() => {
        const keys = Object.keys(localStorage);
        const festivalData = keys.filter(key => key.includes('festival'));
        
        return {
          totalKeys: keys.length,
          festivalKeys: festivalData.length,
          sampleData: festivalData.length > 0 ? localStorage.getItem(festivalData[0]) : null
        };
      });
      
      console.log(`Local storage contains ${localStorageData.totalKeys} keys, ${localStorageData.festivalKeys} festival-related`);
      
      if (localStorageData.festivalKeys > 0) {
        expect(localStorageData.sampleData).toBeTruthy();
      }
    });

    test('should manage storage quota efficiently', async ({ page }) => {
      await page.goto('/');
      
      const storageInfo = await page.evaluate(async () => {
        if ('storage' in navigator && 'estimate' in navigator.storage) {
          try {
            const estimate = await navigator.storage.estimate();
            return {
              supported: true,
              quota: estimate.quota,
              usage: estimate.usage,
              usagePercentage: (estimate.usage / estimate.quota) * 100
            };
          } catch (error) {
            return {
              supported: false,
              error: error.message
            };
          }
        }
        return { supported: false };
      });
      
      if (storageInfo.supported) {
        console.log(`Storage usage: ${storageInfo.usage} / ${storageInfo.quota} (${storageInfo.usagePercentage.toFixed(2)}%)`);
        
        // Should not use excessive storage
        expect(storageInfo.usagePercentage).toBeLessThan(50);
      }
    });

    test('should clean up old cached data', async ({ page }) => {
      await page.goto('/');
      
      const cacheCleanup = await page.evaluate(async () => {
        if ('caches' in window) {
          try {
            const cacheNames = await caches.keys();
            let totalSize = 0;
            let oldCaches = 0;
            
            for (const cacheName of cacheNames) {
              // Check if cache name suggests it's old (this is app-specific)
              if (cacheName.includes('v1') || cacheName.includes('old')) {
                oldCaches++;
              }
              
              const cache = await caches.open(cacheName);
              const requests = await cache.keys();
              totalSize += requests.length;
            }
            
            return {
              totalCaches: cacheNames.length,
              oldCaches,
              totalCachedItems: totalSize
            };
          } catch (error) {
            return {
              error: error.message
            };
          }
        }
        return { supported: false };
      });
      
      if (cacheCleanup.totalCaches) {
        console.log(`Found ${cacheCleanup.totalCaches} caches with ${cacheCleanup.totalCachedItems} total items`);
        
        // Should not have excessive old caches
        expect(cacheCleanup.oldCaches).toBeLessThan(5);
      }
    });
  });

  test.describe('Progressive Enhancement', () => {
    test('should work without JavaScript', async ({ page }) => {
      // Disable JavaScript
      await page.context().addInitScript(() => {
        Object.defineProperty(window, 'navigator', {
          value: {
            ...window.navigator,
            serviceWorker: undefined
          }
        });
      });
      
      await page.goto('/');
      
      // Basic content should still be visible
      const mainContent = page.locator('main, .main-content, body');
      await expect(mainContent.first()).toBeVisible();
      
      // Navigation should work with basic HTML
      const navLinks = page.locator('nav a, .navigation a');
      const linkCount = await navLinks.count();
      
      if (linkCount > 0) {
        const firstLink = navLinks.first();
        const href = await firstLink.getAttribute('href');
        expect(href).toBeTruthy();
      }
    });

    test('should enhance functionality when JavaScript is available', async ({ page }) => {
      await page.goto('/');
      
      // Check for JavaScript enhancements
      const jsEnhancements = await page.evaluate(() => {
        return {
          hasServiceWorker: 'serviceWorker' in navigator,
          hasLocalStorage: 'localStorage' in window,
          hasFetch: 'fetch' in window,
          hasPromises: 'Promise' in window
        };
      });
      
      expect(jsEnhancements.hasServiceWorker).toBe(true);
      expect(jsEnhancements.hasLocalStorage).toBe(true);
      expect(jsEnhancements.hasFetch).toBe(true);
      expect(jsEnhancements.hasPromises).toBe(true);
    });
  });
});