// Base page object model for common functionality
class BasePage {
  constructor(page) {
    this.page = page;
    this.baseUrl = 'http://localhost:8000';
  }

  // Common selectors
  get header() { return this.page.locator('header.header'); }
  get navigation() { return this.page.locator('nav.nav'); }
  get footer() { return this.page.locator('footer.footer'); }
  get loadingIndicator() { return this.page.locator('.loading'); }
  get errorMessage() { return this.page.locator('.error'); }
  get successMessage() { return this.page.locator('.success'); }

  // Navigation methods
  async goto(path = '/') {
    await this.page.goto(`${this.baseUrl}${path}`);
    await this.waitForPageLoad();
  }

  async waitForPageLoad() {
    await this.page.waitForLoadState('networkidle');
    await this.page.waitForSelector('body', { state: 'visible' });
  }

  async clickNavLink(text) {
    await this.page.click(`nav.nav a:has-text("${text}")`);
    await this.waitForPageLoad();
  }

  async goHome() {
    await this.page.click('.logo a');
    await this.waitForPageLoad();
  }

  // Common interactions
  async search(query) {
    await this.page.fill('#festival-search', query);
    await this.page.click('.search-button');
    await this.waitForPageLoad();
  }

  async waitForElement(selector, options = {}) {
    return await this.page.waitForSelector(selector, {
      state: 'visible',
      timeout: 10000,
      ...options
    });
  }

  async waitForText(text, options = {}) {
    return await this.page.waitForSelector(`text=${text}`, {
      timeout: 10000,
      ...options
    });
  }

  async scrollToElement(selector) {
    await this.page.locator(selector).scrollIntoViewIfNeeded();
  }

  async isElementVisible(selector) {
    try {
      await this.page.waitForSelector(selector, { 
        state: 'visible', 
        timeout: 1000 
      });
      return true;
    } catch {
      return false;
    }
  }

  async getElementText(selector) {
    return await this.page.textContent(selector);
  }

  async getElementAttribute(selector, attribute) {
    return await this.page.getAttribute(selector, attribute);
  }

  // Form helpers
  async fillForm(formData) {
    for (const [selector, value] of Object.entries(formData)) {
      await this.page.fill(selector, value);
    }
  }

  async submitForm(formSelector = 'form') {
    await this.page.click(`${formSelector} [type="submit"]`);
    await this.waitForPageLoad();
  }

  // Error handling
  async checkForErrors() {
    const hasError = await this.isElementVisible('.error');
    if (hasError) {
      const errorText = await this.getElementText('.error');
      throw new Error(`Page error: ${errorText}`);
    }
  }

  async waitForNoLoading() {
    try {
      await this.page.waitForSelector('.loading', { 
        state: 'hidden', 
        timeout: 10000 
      });
    } catch {
      // Loading indicator might not exist, which is fine
    }
  }

  // Accessibility helpers
  async checkAccessibility() {
    // This will be implemented with axe-playwright
    await this.page.evaluate(() => {
      // Basic accessibility checks
      const images = document.querySelectorAll('img');
      images.forEach(img => {
        if (!img.alt && !img.getAttribute('aria-label')) {
          console.warn('Image missing alt text:', img.src);
        }
      });

      const buttons = document.querySelectorAll('button');
      buttons.forEach(button => {
        if (!button.textContent.trim() && !button.getAttribute('aria-label')) {
          console.warn('Button missing accessible text:', button);
        }
      });
    });
  }

  // Mobile helpers
  async simulateMobileViewport() {
    await this.page.setViewportSize({ width: 375, height: 667 });
  }

  async simulateTabletViewport() {
    await this.page.setViewportSize({ width: 768, height: 1024 });
  }

  async simulateDesktopViewport() {
    await this.page.setViewportSize({ width: 1920, height: 1080 });
  }

  // Performance helpers
  async measurePageLoad() {
    const timing = await this.page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0];
      return {
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.fetchStart,
        loadComplete: navigation.loadEventEnd - navigation.fetchStart
      };
    });
    return timing;
  }

  // Local storage helpers
  async setLocalStorage(key, value) {
    await this.page.evaluate(
      ({ key, value }) => localStorage.setItem(key, JSON.stringify(value)),
      { key, value }
    );
  }

  async getLocalStorage(key) {
    return await this.page.evaluate(
      (key) => {
        const value = localStorage.getItem(key);
        return value ? JSON.parse(value) : null;
      },
      key
    );
  }

  async clearLocalStorage() {
    await this.page.evaluate(() => localStorage.clear());
  }
}

module.exports = BasePage;