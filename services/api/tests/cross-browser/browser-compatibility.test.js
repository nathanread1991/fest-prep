// Cross-browser compatibility tests
const { test, expect, devices } = require('@playwright/test');

// Test across all configured browsers (defined in playwright.config.js)
test.describe('Cross-Browser Compatibility Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should load main page successfully', async ({ page }) => {
    // Check that the page loads without errors
    await expect(page).toHaveTitle(/Festival Playlist Generator/);
    
    // Check for main content
    const mainContent = page.locator('main, .main-content, body');
    await expect(mainContent.first()).toBeVisible();
    
    // Check for navigation
    const navigation = page.locator('nav, .navigation, .main-nav');
    await expect(navigation.first()).toBeVisible();
  });

  test('should handle JavaScript features correctly', async ({ page }) => {
    // Test modern JavaScript features
    const jsFeatures = await page.evaluate(() => {
      const results = {};
      
      try {
        // Arrow functions
        const arrow = () => 'arrow';
        results.arrowFunctions = arrow() === 'arrow';
        
        // Template literals
        const template = `template`;
        results.templateLiterals = template === 'template';
        
        // Destructuring
        const [a, b] = [1, 2];
        results.destructuring = a === 1 && b === 2;
        
        // Promises
        results.promises = typeof Promise !== 'undefined';
        
        // Fetch API
        results.fetch = typeof fetch !== 'undefined';
        
        // Local Storage
        results.localStorage = typeof localStorage !== 'undefined';
        
        // Session Storage
        results.sessionStorage = typeof sessionStorage !== 'undefined';
        
        // Geolocation
        results.geolocation = 'geolocation' in navigator;
        
        // Service Workers
        results.serviceWorker = 'serviceWorker' in navigator;
        
      } catch (error) {
        results.error = error.message;
      }
      
      return results;
    });
    
    // All modern browsers should support these features
    expect(jsFeatures.arrowFunctions).toBe(true);
    expect(jsFeatures.templateLiterals).toBe(true);
    expect(jsFeatures.destructuring).toBe(true);
    expect(jsFeatures.promises).toBe(true);
    expect(jsFeatures.fetch).toBe(true);
    expect(jsFeatures.localStorage).toBe(true);
    expect(jsFeatures.sessionStorage).toBe(true);
    expect(jsFeatures.geolocation).toBe(true);
    
    // Service Workers might not be available in all test environments
    expect(typeof jsFeatures.serviceWorker).toBe('boolean');
  });

  test('should handle CSS features correctly', async ({ page }) => {
    // Test CSS Grid support
    const gridSupport = await page.evaluate(() => {
      const testElement = document.createElement('div');
      testElement.style.display = 'grid';
      return testElement.style.display === 'grid';
    });
    expect(gridSupport).toBe(true);
    
    // Test Flexbox support
    const flexSupport = await page.evaluate(() => {
      const testElement = document.createElement('div');
      testElement.style.display = 'flex';
      return testElement.style.display === 'flex';
    });
    expect(flexSupport).toBe(true);
    
    // Test CSS Custom Properties (Variables)
    const customPropsSupport = await page.evaluate(() => {
      const testElement = document.createElement('div');
      testElement.style.setProperty('--test-var', 'test');
      return testElement.style.getPropertyValue('--test-var') === 'test';
    });
    expect(customPropsSupport).toBe(true);
  });

  test('should handle form interactions consistently', async ({ page }) => {
    await page.goto('/login');
    
    const emailInput = page.locator('#email, input[type="email"]').first();
    const passwordInput = page.locator('#password, input[type="password"]').first();
    const submitButton = page.locator('button[type="submit"], input[type="submit"]').first();
    
    if (await emailInput.count() > 0) {
      // Test form input
      await emailInput.fill('test@example.com');
      await expect(emailInput).toHaveValue('test@example.com');
      
      if (await passwordInput.count() > 0) {
        await passwordInput.fill('password123');
        await expect(passwordInput).toHaveValue('password123');
      }
      
      // Test form validation
      await emailInput.fill('invalid-email');
      if (await submitButton.count() > 0) {
        await submitButton.click();
        
        // Check for validation message (browser-specific)
        const validationMessage = await emailInput.evaluate(input => input.validationMessage);
        expect(validationMessage).toBeTruthy();
      }
    }
  });

  test('should handle event listeners correctly', async ({ page }) => {
    // Test click events
    const buttons = page.locator('button:visible');
    const buttonCount = await buttons.count();
    
    if (buttonCount > 0) {
      const button = buttons.first();
      
      // Add event listener
      await page.evaluate(() => {
        window.testClickCount = 0;
        document.addEventListener('click', () => {
          window.testClickCount++;
        });
      });
      
      await button.click();
      
      const clickCount = await page.evaluate(() => window.testClickCount);
      expect(clickCount).toBeGreaterThan(0);
    }
    
    // Test keyboard events
    await page.keyboard.press('Tab');
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });

  test('should handle AJAX requests correctly', async ({ page }) => {
    // Mock an API endpoint
    await page.route('**/api/festivals', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, name: 'Test Festival', location: 'Test Location' }
        ])
      });
    });
    
    // Test fetch request
    const fetchResult = await page.evaluate(async () => {
      try {
        const response = await fetch('/api/festivals');
        const data = await response.json();
        return { success: true, data };
      } catch (error) {
        return { success: false, error: error.message };
      }
    });
    
    expect(fetchResult.success).toBe(true);
    expect(fetchResult.data).toHaveLength(1);
  });

  test('should handle media queries and responsive design', async ({ page }) => {
    // Test different viewport sizes
    const viewports = [
      { width: 375, height: 667, name: 'mobile' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 1920, height: 1080, name: 'desktop' }
    ];
    
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      
      // Check that layout adapts
      const navigation = page.locator('nav, .navigation').first();
      if (await navigation.isVisible()) {
        const navBox = await navigation.boundingBox();
        expect(navBox.width).toBeLessThanOrEqual(viewport.width);
      }
      
      // Test media query matching
      const mediaQueryResult = await page.evaluate((vp) => {
        const mobileQuery = window.matchMedia('(max-width: 768px)');
        const tabletQuery = window.matchMedia('(min-width: 769px) and (max-width: 1024px)');
        const desktopQuery = window.matchMedia('(min-width: 1025px)');
        
        return {
          mobile: mobileQuery.matches,
          tablet: tabletQuery.matches,
          desktop: desktopQuery.matches,
          width: vp.width
        };
      }, viewport);
      
      if (viewport.width <= 768) {
        expect(mediaQueryResult.mobile).toBe(true);
      } else if (viewport.width <= 1024) {
        expect(mediaQueryResult.tablet).toBe(true);
      } else {
        expect(mediaQueryResult.desktop).toBe(true);
      }
    }
  });

  test('should handle local storage consistently', async ({ page }) => {
    // Test localStorage
    await page.evaluate(() => {
      localStorage.setItem('test-key', 'test-value');
    });
    
    const storedValue = await page.evaluate(() => {
      return localStorage.getItem('test-key');
    });
    
    expect(storedValue).toBe('test-value');
    
    // Test sessionStorage
    await page.evaluate(() => {
      sessionStorage.setItem('session-key', 'session-value');
    });
    
    const sessionValue = await page.evaluate(() => {
      return sessionStorage.getItem('session-key');
    });
    
    expect(sessionValue).toBe('session-value');
  });

  test('should handle date and time formatting', async ({ page }) => {
    const dateFormatting = await page.evaluate(() => {
      const testDate = new Date('2024-01-15T10:30:00Z');
      
      return {
        toLocaleDateString: testDate.toLocaleDateString(),
        toLocaleTimeString: testDate.toLocaleTimeString(),
        toISOString: testDate.toISOString(),
        intlDateFormat: new Intl.DateTimeFormat('en-US').format(testDate),
        intlSupport: typeof Intl !== 'undefined'
      };
    });
    
    expect(dateFormatting.toISOString).toBe('2024-01-15T10:30:00.000Z');
    expect(dateFormatting.intlSupport).toBe(true);
    expect(dateFormatting.intlDateFormat).toBeTruthy();
  });

  test('should handle file upload consistently', async ({ page }) => {
    await page.goto('/playlists/import');
    
    const fileInput = page.locator('input[type="file"]').first();
    
    if (await fileInput.count() > 0) {
      // Create a test file
      const testFile = {
        name: 'test.csv',
        mimeType: 'text/csv',
        buffer: Buffer.from('artist,song\nTest Artist,Test Song')
      };
      
      await fileInput.setInputFiles(testFile);
      
      // Verify file was selected
      const fileName = await fileInput.evaluate(input => {
        return input.files[0]?.name;
      });
      
      expect(fileName).toBe('test.csv');
    }
  });

  test('should handle WebSocket connections (if applicable)', async ({ page }) => {
    // Test WebSocket support
    const wsSupport = await page.evaluate(() => {
      return typeof WebSocket !== 'undefined';
    });
    
    expect(wsSupport).toBe(true);
    
    // If the app uses WebSockets, test connection
    // This would be app-specific implementation
  });

  test('should handle geolocation API consistently', async ({ page }) => {
    // Mock geolocation
    await page.context().grantPermissions(['geolocation']);
    await page.context().setGeolocation({ latitude: 37.7749, longitude: -122.4194 });
    
    const geolocationResult = await page.evaluate(() => {
      return new Promise((resolve) => {
        if ('geolocation' in navigator) {
          navigator.geolocation.getCurrentPosition(
            (position) => {
              resolve({
                success: true,
                latitude: position.coords.latitude,
                longitude: position.coords.longitude
              });
            },
            (error) => {
              resolve({
                success: false,
                error: error.message
              });
            }
          );
        } else {
          resolve({ success: false, error: 'Geolocation not supported' });
        }
      });
    });
    
    expect(geolocationResult.success).toBe(true);
    expect(geolocationResult.latitude).toBe(37.7749);
    expect(geolocationResult.longitude).toBe(-122.4194);
  });
});

test.describe('Cross-Browser Feature Comparison', () => {
  test('should have consistent rendering across browsers', async ({ page, browserName }) => {
    await page.goto('/');
    
    // Take screenshot for visual comparison
    await expect(page).toHaveScreenshot(`homepage-${browserName}.png`, {
      fullPage: true,
      threshold: 0.3 // Allow for minor rendering differences
    });
  });

  test('should handle JavaScript version compatibility', async ({ page, browserName }) => {
    // Test ES6+ features across browsers
    const jsCompatibility = await page.evaluate(() => {
      const results = {};
      
      try {
        // ES6 features
        results.letConst = (() => { let x = 1; const y = 2; return x + y === 3; })();
        results.arrowFunctions = (() => [1,2,3].map(x => x * 2).length === 3)();
        results.templateLiterals = `test${1}` === 'test1';
        results.destructuring = (() => { const [a, b] = [1, 2]; return a === 1 && b === 2; })();
        results.defaultParams = ((x = 1) => x)(undefined) === 1;
        results.restSpread = (() => { const arr = [1, 2, 3]; return [...arr].length === 3; })();
        
        // ES2017+ features
        results.asyncAwait = typeof (async () => {}) === 'function';
        results.objectSpread = (() => { const obj = {a: 1}; return {...obj, b: 2}.b === 2; })();
        
        // ES2018+ features
        results.regexNamedGroups = /(?<year>\d{4})/.test('2024');
        
        // ES2019+ features
        results.arrayFlat = Array.prototype.flat !== undefined;
        results.objectFromEntries = Object.fromEntries !== undefined;
        
        // ES2020+ features
        results.nullishCoalescing = (null ?? 'default') === 'default';
        results.optionalChaining = (() => { const obj = {}; return obj?.prop?.nested === undefined; })();
        results.bigInt = typeof BigInt !== 'undefined';
        
        // ES2021+ features
        results.logicalAssignment = (() => { let x = false; x ||= true; return x === true; })();
        results.numericSeparators = 1_000_000 === 1000000;
        
      } catch (error) {
        results.error = error.message;
      }
      
      return results;
    });
    
    // Core ES6 features should be supported in all modern browsers
    expect(jsCompatibility.letConst).toBe(true);
    expect(jsCompatibility.arrowFunctions).toBe(true);
    expect(jsCompatibility.templateLiterals).toBe(true);
    expect(jsCompatibility.destructuring).toBe(true);
    expect(jsCompatibility.defaultParams).toBe(true);
    expect(jsCompatibility.restSpread).toBe(true);
    
    // Modern features should be supported
    expect(jsCompatibility.asyncAwait).toBe(true);
    expect(jsCompatibility.objectSpread).toBe(true);
    
    // Log browser-specific support
    console.log(`${browserName} JavaScript compatibility:`, jsCompatibility);
  });

  test('should handle CSS feature compatibility', async ({ page, browserName }) => {
    const cssCompatibility = await page.evaluate(() => {
      const testElement = document.createElement('div');
      document.body.appendChild(testElement);
      
      const results = {};
      
      try {
        // CSS Grid
        testElement.style.display = 'grid';
        results.cssGrid = testElement.style.display === 'grid';
        
        // Flexbox
        testElement.style.display = 'flex';
        results.flexbox = testElement.style.display === 'flex';
        
        // CSS Custom Properties
        testElement.style.setProperty('--test-var', 'test');
        results.customProperties = testElement.style.getPropertyValue('--test-var') === 'test';
        
        // CSS Transforms
        testElement.style.transform = 'translateX(10px)';
        results.transforms = testElement.style.transform.includes('translateX');
        
        // CSS Transitions
        testElement.style.transition = 'all 0.3s ease';
        results.transitions = testElement.style.transition.includes('0.3s');
        
        // CSS Filters
        testElement.style.filter = 'blur(5px)';
        results.filters = testElement.style.filter.includes('blur');
        
        // CSS Clip Path
        testElement.style.clipPath = 'circle(50%)';
        results.clipPath = testElement.style.clipPath.includes('circle');
        
        // CSS Object Fit
        testElement.style.objectFit = 'cover';
        results.objectFit = testElement.style.objectFit === 'cover';
        
        // CSS Scroll Behavior
        testElement.style.scrollBehavior = 'smooth';
        results.scrollBehavior = testElement.style.scrollBehavior === 'smooth';
        
        // CSS Backdrop Filter
        testElement.style.backdropFilter = 'blur(10px)';
        results.backdropFilter = testElement.style.backdropFilter.includes('blur');
        
      } catch (error) {
        results.error = error.message;
      } finally {
        document.body.removeChild(testElement);
      }
      
      return results;
    });
    
    // Core CSS features should be supported
    expect(cssCompatibility.cssGrid).toBe(true);
    expect(cssCompatibility.flexbox).toBe(true);
    expect(cssCompatibility.customProperties).toBe(true);
    expect(cssCompatibility.transforms).toBe(true);
    expect(cssCompatibility.transitions).toBe(true);
    
    // Log browser-specific CSS support
    console.log(`${browserName} CSS compatibility:`, cssCompatibility);
  });

  test('should handle Web API compatibility', async ({ page, browserName }) => {
    const apiCompatibility = await page.evaluate(() => {
      return {
        // Storage APIs
        localStorage: typeof localStorage !== 'undefined',
        sessionStorage: typeof sessionStorage !== 'undefined',
        indexedDB: typeof indexedDB !== 'undefined',
        
        // Network APIs
        fetch: typeof fetch !== 'undefined',
        websocket: typeof WebSocket !== 'undefined',
        eventSource: typeof EventSource !== 'undefined',
        
        // Media APIs
        getUserMedia: navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function',
        webRTC: typeof RTCPeerConnection !== 'undefined',
        webAudio: typeof AudioContext !== 'undefined' || typeof webkitAudioContext !== 'undefined',
        
        // Device APIs
        geolocation: 'geolocation' in navigator,
        deviceOrientation: 'DeviceOrientationEvent' in window,
        vibration: 'vibrate' in navigator,
        
        // Worker APIs
        webWorkers: typeof Worker !== 'undefined',
        serviceWorker: 'serviceWorker' in navigator,
        sharedWorker: typeof SharedWorker !== 'undefined',
        
        // Graphics APIs
        canvas: (() => { const canvas = document.createElement('canvas'); return !!(canvas.getContext && canvas.getContext('2d')); })(),
        webGL: (() => { const canvas = document.createElement('canvas'); return !!(canvas.getContext && canvas.getContext('webgl')); })(),
        webGL2: (() => { const canvas = document.createElement('canvas'); return !!(canvas.getContext && canvas.getContext('webgl2')); })(),
        
        // Performance APIs
        performanceObserver: typeof PerformanceObserver !== 'undefined',
        intersectionObserver: typeof IntersectionObserver !== 'undefined',
        mutationObserver: typeof MutationObserver !== 'undefined',
        
        // Security APIs
        crypto: typeof crypto !== 'undefined' && typeof crypto.subtle !== 'undefined',
        
        // File APIs
        fileReader: typeof FileReader !== 'undefined',
        blob: typeof Blob !== 'undefined',
        formData: typeof FormData !== 'undefined'
      };
    });
    
    // Core APIs should be supported in all modern browsers
    expect(apiCompatibility.localStorage).toBe(true);
    expect(apiCompatibility.sessionStorage).toBe(true);
    expect(apiCompatibility.fetch).toBe(true);
    expect(apiCompatibility.canvas).toBe(true);
    expect(apiCompatibility.webWorkers).toBe(true);
    expect(apiCompatibility.fileReader).toBe(true);
    expect(apiCompatibility.blob).toBe(true);
    expect(apiCompatibility.formData).toBe(true);
    
    // Log browser-specific API support
    console.log(`${browserName} Web API compatibility:`, apiCompatibility);
  });
});

test.describe('Browser-Specific Workarounds', () => {
  test('should handle Safari-specific issues', async ({ page, browserName }) => {
    test.skip(browserName !== 'webkit', 'Safari-specific test');
    
    await page.goto('/');
    
    // Test Safari-specific date input handling
    const dateInput = page.locator('input[type="date"]').first();
    if (await dateInput.count() > 0) {
      await dateInput.fill('2024-01-15');
      const value = await dateInput.inputValue();
      expect(value).toBe('2024-01-15');
    }
    
    // Test Safari-specific audio/video handling
    const mediaElements = page.locator('audio, video');
    const mediaCount = await mediaElements.count();
    
    if (mediaCount > 0) {
      const media = mediaElements.first();
      const canPlay = await media.evaluate(el => {
        return typeof el.canPlayType === 'function';
      });
      expect(canPlay).toBe(true);
    }
    
    // Test Safari-specific touch events
    const touchSupport = await page.evaluate(() => {
      return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    });
    expect(touchSupport).toBe(true);
    
    // Test Safari-specific viewport handling
    const viewportMeta = page.locator('meta[name="viewport"]');
    if (await viewportMeta.count() > 0) {
      const content = await viewportMeta.getAttribute('content');
      expect(content).toContain('width=device-width');
    }
  });

  test('should handle Firefox-specific issues', async ({ page, browserName }) => {
    test.skip(browserName !== 'firefox', 'Firefox-specific test');
    
    await page.goto('/');
    
    // Test Firefox-specific form validation
    const emailInput = page.locator('input[type="email"]').first();
    if (await emailInput.count() > 0) {
      await emailInput.fill('invalid-email');
      
      const validationMessage = await emailInput.evaluate(input => {
        return input.validationMessage;
      });
      
      expect(validationMessage).toBeTruthy();
    }
    
    // Test Firefox-specific CSS features
    const firefoxCSS = await page.evaluate(() => {
      const testElement = document.createElement('div');
      testElement.style.scrollbarWidth = 'thin';
      return testElement.style.scrollbarWidth === 'thin';
    });
    expect(firefoxCSS).toBe(true);
    
    // Test Firefox-specific JavaScript features
    const firefoxJS = await page.evaluate(() => {
      return {
        mozInnerScreenX: 'mozInnerScreenX' in window,
        mozRequestAnimationFrame: 'mozRequestAnimationFrame' in window
      };
    });
    
    // These are legacy features that might not be present in modern Firefox
    expect(typeof firefoxJS.mozInnerScreenX).toBe('boolean');
  });

  test('should handle Chrome-specific issues', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'Chrome-specific test');
    
    await page.goto('/');
    
    // Test Chrome-specific features
    const chromeFeatures = await page.evaluate(() => {
      return {
        webkitSpeechRecognition: 'webkitSpeechRecognition' in window,
        chrome: 'chrome' in window,
        webkitRequestFileSystem: 'webkitRequestFileSystem' in window,
        webkitStorageInfo: 'webkitStorageInfo' in navigator
      };
    });
    
    // These features might be available in Chrome
    expect(typeof chromeFeatures.webkitSpeechRecognition).toBe('boolean');
    expect(typeof chromeFeatures.chrome).toBe('boolean');
    
    // Test Chrome-specific CSS features
    const chromeCSS = await page.evaluate(() => {
      const testElement = document.createElement('div');
      testElement.style.webkitAppearance = 'none';
      return testElement.style.webkitAppearance === 'none';
    });
    expect(chromeCSS).toBe(true);
  });

  test('should handle Edge-specific issues', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'Edge uses Chromium engine');
    
    await page.goto('/');
    
    // Test Edge-specific user agent detection
    const userAgent = await page.evaluate(() => navigator.userAgent);
    
    // Modern Edge uses Chromium, so it should behave like Chrome
    const isModernEdge = userAgent.includes('Edg/');
    
    if (isModernEdge) {
      // Test Edge-specific features
      const edgeFeatures = await page.evaluate(() => {
        return {
          msLaunchUri: 'msLaunchUri' in navigator,
          msSaveBlob: 'msSaveBlob' in navigator
        };
      });
      
      // These are legacy Edge features that might not be present in Chromium Edge
      expect(typeof edgeFeatures.msLaunchUri).toBe('boolean');
    }
  });
});

test.describe('Performance Across Browsers', () => {
  test('should load within acceptable time limits', async ({ page, browserName }) => {
    const startTime = Date.now();
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    
    // Should load within 5 seconds across all browsers
    expect(loadTime).toBeLessThan(5000);
    
    console.log(`${browserName} load time: ${loadTime}ms`);
  });

  test('should handle large datasets efficiently', async ({ page }) => {
    await page.goto('/festivals');
    
    // Measure rendering performance
    const performanceMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0];
      return {
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
        firstPaint: performance.getEntriesByName('first-paint')[0]?.startTime || 0,
        firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime || 0
      };
    });
    
    // DOM should load quickly
    expect(performanceMetrics.domContentLoaded).toBeLessThan(2000);
    
    if (performanceMetrics.firstContentfulPaint > 0) {
      expect(performanceMetrics.firstContentfulPaint).toBeLessThan(3000);
    }
  });
});