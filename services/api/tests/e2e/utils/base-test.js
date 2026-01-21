// Base test utilities for Playwright E2E tests
const { test: base, expect } = require('@playwright/test');
const { injectAxe, checkA11y } = require('axe-playwright');

// Extend base test with custom fixtures
const test = base.extend({
  // Auto-inject axe for accessibility testing
  page: async ({ page }, use) => {
    await injectAxe(page);
    await use(page);
  },

  // Custom context with mobile user agent for mobile tests
  mobileContext: async ({ browser }, use) => {
    const context = await browser.newContext({
      ...devices['iPhone 12'],
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
    });
    await use(context);
    await context.close();
  }
});

// Custom assertions
expect.extend({
  async toBeAccessible(page, options = {}) {
    try {
      await checkA11y(page, null, {
        detailedReport: true,
        detailedReportOptions: { html: true },
        ...options
      });
      return { pass: true, message: () => 'Page is accessible' };
    } catch (error) {
      return {
        pass: false,
        message: () => `Accessibility violations found: ${error.message}`
      };
    }
  },

  async toHaveLoadTime(page, maxTime) {
    const navigationTiming = await page.evaluate(() => {
      const timing = performance.getEntriesByType('navigation')[0];
      return timing ? timing.loadEventEnd - timing.fetchStart : 0;
    });

    const pass = navigationTiming <= maxTime;
    return {
      pass,
      message: () => pass 
        ? `Page loaded in ${navigationTiming}ms (within ${maxTime}ms limit)`
        : `Page loaded in ${navigationTiming}ms (exceeds ${maxTime}ms limit)`
    };
  }
});

// Test utilities
class TestUtils {
  static async waitForNetworkIdle(page, timeout = 5000) {
    await page.waitForLoadState('networkidle', { timeout });
  }

  static async mockApiResponse(page, url, response) {
    await page.route(url, route => {
      route.fulfill({
        status: response.status || 200,
        contentType: 'application/json',
        body: JSON.stringify(response.data || response)
      });
    });
  }

  static async mockApiError(page, url, status = 500, message = 'Server Error') {
    await page.route(url, route => {
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify({ error: message })
      });
    });
  }

  static async simulateSlowNetwork(page, delay = 1000) {
    await page.route('**/*', async route => {
      await new Promise(resolve => setTimeout(resolve, delay));
      await route.continue();
    });
  }

  static async simulateOffline(page) {
    await page.context().setOffline(true);
  }

  static async simulateOnline(page) {
    await page.context().setOffline(false);
  }

  static async getConsoleErrors(page) {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    return errors;
  }

  static async checkForJavaScriptErrors(page) {
    const errors = await this.getConsoleErrors(page);
    expect(errors).toHaveLength(0);
  }

  static async fillFormField(page, selector, value) {
    await page.fill(selector, '');
    await page.fill(selector, value);
    await page.blur(selector);
  }

  static async selectOption(page, selector, value) {
    await page.selectOption(selector, value);
  }

  static async uploadFile(page, selector, filePath) {
    await page.setInputFiles(selector, filePath);
  }

  static async takeScreenshot(page, name) {
    await page.screenshot({ 
      path: `test-results/screenshots/${name}.png`,
      fullPage: true 
    });
  }

  static async measurePerformance(page) {
    return await page.evaluate(() => {
      const timing = performance.getEntriesByType('navigation')[0];
      return {
        domContentLoaded: timing.domContentLoadedEventEnd - timing.fetchStart,
        loadComplete: timing.loadEventEnd - timing.fetchStart,
        firstPaint: performance.getEntriesByName('first-paint')[0]?.startTime || 0,
        firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime || 0
      };
    });
  }
}

module.exports = { test, expect, TestUtils };