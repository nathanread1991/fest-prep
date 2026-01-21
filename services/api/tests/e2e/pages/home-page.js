// Home page object model
const BasePage = require('./base-page');

class HomePage extends BasePage {
  constructor(page) {
    super(page);
  }

  // Selectors
  get heroSection() { return this.page.locator('.hero'); }
  get heroTitle() { return this.page.locator('.hero-title'); }
  get heroSubtitle() { return this.page.locator('.hero-subtitle'); }
  get searchForm() { return this.page.locator('#festival-search-form'); }
  get searchInput() { return this.page.locator('#festival-search'); }
  get searchButton() { return this.page.locator('.search-button'); }
  get quickActions() { return this.page.locator('.quick-actions'); }
  get findFestivalsButton() { return this.page.locator('button:has-text("Find Festivals")'); }
  get searchArtistsButton() { return this.page.locator('button:has-text("Search Artists")'); }
  get featuresSection() { return this.page.locator('.features'); }
  get featureCards() { return this.page.locator('.feature-card'); }
  get recentFestivalsSection() { return this.page.locator('.recent-festivals'); }
  get popularFestivals() { return this.page.locator('#popular-festivals'); }
  get festivalCards() { return this.page.locator('.festival-card'); }

  // Actions
  async visit() {
    await this.goto('/');
  }

  async searchFor(query) {
    await this.searchInput.fill(query);
    await this.searchButton.click();
    await this.waitForPageLoad();
  }

  async clickFindFestivals() {
    await this.findFestivalsButton.click();
    // Should focus the search input and change placeholder
    await this.page.waitForFunction(() => {
      const input = document.querySelector('#festival-search');
      return input && input.placeholder.includes('festivals');
    });
  }

  async clickSearchArtists() {
    await this.searchArtistsButton.click();
    // Should focus the search input and change placeholder
    await this.page.waitForFunction(() => {
      const input = document.querySelector('#festival-search');
      return input && input.placeholder.includes('artists');
    });
  }

  async clickFestivalCard(festivalName) {
    await this.page.click(`.festival-card:has-text("${festivalName}")`);
    await this.waitForPageLoad();
  }

  async waitForFestivalsToLoad() {
    // Wait for either festivals to load or "no results" message
    await this.page.waitForSelector(
      '.festival-card, .no-results, .error',
      { timeout: 10000 }
    );
  }

  async getFestivalCards() {
    await this.waitForFestivalsToLoad();
    return await this.festivalCards.all();
  }

  async getFeatureCards() {
    return await this.featureCards.all();
  }

  async isSearchFocused() {
    return await this.searchInput.evaluate(el => el === document.activeElement);
  }

  async getSearchPlaceholder() {
    return await this.searchInput.getAttribute('placeholder');
  }

  // Validation methods
  async validateHeroSection() {
    await this.heroSection.waitFor({ state: 'visible' });
    await this.heroTitle.waitFor({ state: 'visible' });
    await this.heroSubtitle.waitFor({ state: 'visible' });
    
    const title = await this.heroTitle.textContent();
    const subtitle = await this.heroSubtitle.textContent();
    
    return {
      hasTitle: title && title.length > 0,
      hasSubtitle: subtitle && subtitle.length > 0,
      title,
      subtitle
    };
  }

  async validateSearchForm() {
    await this.searchForm.waitFor({ state: 'visible' });
    await this.searchInput.waitFor({ state: 'visible' });
    await this.searchButton.waitFor({ state: 'visible' });
    
    const isInputEnabled = await this.searchInput.isEnabled();
    const isButtonEnabled = await this.searchButton.isEnabled();
    
    return {
      formVisible: true,
      inputEnabled: isInputEnabled,
      buttonEnabled: isButtonEnabled
    };
  }

  async validateQuickActions() {
    await this.quickActions.waitFor({ state: 'visible' });
    await this.findFestivalsButton.waitFor({ state: 'visible' });
    await this.searchArtistsButton.waitFor({ state: 'visible' });
    
    return {
      quickActionsVisible: true,
      findFestivalsVisible: true,
      searchArtistsVisible: true
    };
  }

  async validateFeaturesSection() {
    await this.featuresSection.waitFor({ state: 'visible' });
    const cards = await this.getFeatureCards();
    
    const features = [];
    for (const card of cards) {
      const icon = await card.locator('.feature-icon').textContent();
      const title = await card.locator('.feature-title').textContent();
      const description = await card.locator('.feature-description').textContent();
      
      features.push({ icon, title, description });
    }
    
    return {
      sectionVisible: true,
      featureCount: features.length,
      features
    };
  }

  async validatePopularFestivals() {
    await this.recentFestivalsSection.waitFor({ state: 'visible' });
    await this.waitForFestivalsToLoad();
    
    const hasError = await this.isElementVisible('.error');
    const hasNoResults = await this.isElementVisible('.no-results');
    const cards = await this.getFestivalCards();
    
    return {
      sectionVisible: true,
      hasError,
      hasNoResults,
      festivalCount: cards.length
    };
  }
}

module.exports = HomePage;