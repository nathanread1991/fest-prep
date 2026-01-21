// Festivals page object model
const BasePage = require('./base-page');

class FestivalsPage extends BasePage {
  constructor(page) {
    super(page);
  }

  // Selectors
  get pageTitle() { return this.page.locator('h1, .page-title'); }
  get searchInput() { return this.page.locator('#festival-search, .search-input'); }
  get searchButton() { return this.page.locator('.search-button, [type="submit"]'); }
  get filterSection() { return this.page.locator('.filters, .filter-section'); }
  get genreFilter() { return this.page.locator('#genre-filter, .genre-filter'); }
  get locationFilter() { return this.page.locator('#location-filter, .location-filter'); }
  get dateFilter() { return this.page.locator('#date-filter, .date-filter'); }
  get sortDropdown() { return this.page.locator('#sort-by, .sort-dropdown'); }
  get festivalGrid() { return this.page.locator('.festivals-grid, .festival-list'); }
  get festivalCards() { return this.page.locator('.festival-card'); }
  get loadMoreButton() { return this.page.locator('.load-more, .pagination-next'); }
  get resultsCount() { return this.page.locator('.results-count, .total-results'); }
  get noResultsMessage() { return this.page.locator('.no-results, .empty-state'); }

  // Actions
  async visit() {
    await this.goto('/festivals');
  }

  async searchFestivals(query) {
    await this.searchInput.fill(query);
    await this.searchButton.click();
    await this.waitForPageLoad();
  }

  async filterByGenre(genre) {
    await this.genreFilter.selectOption(genre);
    await this.waitForPageLoad();
  }

  async filterByLocation(location) {
    await this.locationFilter.fill(location);
    await this.page.keyboard.press('Enter');
    await this.waitForPageLoad();
  }

  async filterByDate(dateRange) {
    await this.dateFilter.selectOption(dateRange);
    await this.waitForPageLoad();
  }

  async sortBy(sortOption) {
    await this.sortDropdown.selectOption(sortOption);
    await this.waitForPageLoad();
  }

  async clickFestival(festivalName) {
    await this.page.click(`.festival-card:has-text("${festivalName}")`);
    await this.waitForPageLoad();
  }

  async loadMoreFestivals() {
    const initialCount = await this.festivalCards.count();
    await this.loadMoreButton.click();
    
    // Wait for new festivals to load
    await this.page.waitForFunction(
      (count) => document.querySelectorAll('.festival-card').length > count,
      initialCount,
      { timeout: 10000 }
    );
  }

  // Validation methods
  async getFestivalCards() {
    await this.waitForElement('.festival-card, .no-results');
    return await this.festivalCards.all();
  }

  async getFestivalCount() {
    const cards = await this.getFestivalCards();
    return cards.length;
  }

  async getResultsCountText() {
    if (await this.isElementVisible('.results-count')) {
      return await this.resultsCount.textContent();
    }
    return null;
  }

  async hasNoResults() {
    return await this.isElementVisible('.no-results');
  }

  async getFestivalData(index = 0) {
    const cards = await this.getFestivalCards();
    if (cards.length <= index) return null;

    const card = cards[index];
    const name = await card.locator('.festival-name, h3, h4').textContent();
    const location = await card.locator('.festival-location, .location').textContent();
    const dates = await card.locator('.festival-dates, .dates').textContent();
    const artists = await card.locator('.festival-artists, .artists').textContent();

    return { name, location, dates, artists };
  }

  async validateSearchResults(query) {
    const cards = await this.getFestivalCards();
    const results = [];

    for (const card of cards) {
      const name = await card.locator('.festival-name, h3, h4').textContent();
      const location = await card.locator('.festival-location, .location').textContent();
      
      results.push({
        name,
        location,
        matchesQuery: name.toLowerCase().includes(query.toLowerCase()) || 
                     location.toLowerCase().includes(query.toLowerCase())
      });
    }

    return results;
  }

  async validateSorting(sortBy) {
    const cards = await this.getFestivalCards();
    const values = [];

    for (const card of cards) {
      let value;
      switch (sortBy) {
        case 'name':
          value = await card.locator('.festival-name, h3, h4').textContent();
          break;
        case 'date':
          value = await card.locator('.festival-dates, .dates').textContent();
          break;
        case 'location':
          value = await card.locator('.festival-location, .location').textContent();
          break;
        default:
          value = await card.locator('.festival-name, h3, h4').textContent();
      }
      values.push(value);
    }

    // Check if sorted (basic alphabetical check)
    const sorted = [...values].sort();
    return JSON.stringify(values) === JSON.stringify(sorted);
  }

  async validateFilters(filterType, filterValue) {
    const cards = await this.getFestivalCards();
    const results = [];

    for (const card of cards) {
      let elementToCheck;
      switch (filterType) {
        case 'genre':
          elementToCheck = card.locator('.festival-genres, .genres');
          break;
        case 'location':
          elementToCheck = card.locator('.festival-location, .location');
          break;
        case 'date':
          elementToCheck = card.locator('.festival-dates, .dates');
          break;
        default:
          elementToCheck = card.locator('.festival-name, h3, h4');
      }

      const text = await elementToCheck.textContent();
      results.push({
        text,
        matchesFilter: text.toLowerCase().includes(filterValue.toLowerCase())
      });
    }

    return results;
  }
}

module.exports = FestivalsPage;