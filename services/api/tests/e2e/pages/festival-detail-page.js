// Festival detail page object model
const BasePage = require('./base-page');

class FestivalDetailPage extends BasePage {
  constructor(page) {
    super(page);
  }

  // Selectors
  get festivalName() { return this.page.locator('.festival-name, h1'); }
  get festivalDates() { return this.page.locator('.festival-dates, .dates'); }
  get festivalLocation() { return this.page.locator('.festival-location, .location'); }
  get festivalVenue() { return this.page.locator('.festival-venue, .venue'); }
  get festivalDescription() { return this.page.locator('.festival-description, .description'); }
  get artistsList() { return this.page.locator('.artists-list, .lineup'); }
  get artistItems() { return this.page.locator('.artist-item, .artist-card'); }
  get genresList() { return this.page.locator('.genres-list, .genres'); }
  get ticketButton() { return this.page.locator('.ticket-button, .buy-tickets'); }
  get createPlaylistButton() { return this.page.locator('.create-playlist-button, .generate-playlist'); }
  get shareButton() { return this.page.locator('.share-button, .share-festival'); }
  get backButton() { return this.page.locator('.back-button, .breadcrumb a'); }
  get festivalImage() { return this.page.locator('.festival-image, .hero-image'); }
  get mapSection() { return this.page.locator('.map-section, .location-map'); }

  // Actions
  async visit(festivalId) {
    await this.goto(`/festivals/${festivalId}`);
  }

  async clickArtist(artistName) {
    await this.page.click(`.artist-item:has-text("${artistName}"), .artist-card:has-text("${artistName}")`);
    await this.waitForPageLoad();
  }

  async createPlaylist() {
    await this.createPlaylistButton.click();
    await this.waitForPageLoad();
  }

  async buyTickets() {
    // This might open a new tab/window
    const [newPage] = await Promise.all([
      this.page.context().waitForEvent('page'),
      this.ticketButton.click()
    ]);
    return newPage;
  }

  async shareFestival() {
    await this.shareButton.click();
    // Wait for share dialog or copy confirmation
    await this.page.waitForSelector('.share-dialog, .copy-success', { timeout: 5000 });
  }

  async goBack() {
    await this.backButton.click();
    await this.waitForPageLoad();
  }

  // Validation methods
  async getFestivalInfo() {
    const name = await this.festivalName.textContent();
    const dates = await this.festivalDates.textContent();
    const location = await this.festivalLocation.textContent();
    
    let venue = null;
    if (await this.isElementVisible('.festival-venue, .venue')) {
      venue = await this.festivalVenue.textContent();
    }

    let description = null;
    if (await this.isElementVisible('.festival-description, .description')) {
      description = await this.festivalDescription.textContent();
    }

    return { name, dates, location, venue, description };
  }

  async getArtistsList() {
    const artistElements = await this.artistItems.all();
    const artists = [];

    for (const element of artistElements) {
      const name = await element.locator('.artist-name, h3, h4').textContent();
      const genre = await element.locator('.artist-genre, .genre').textContent().catch(() => '');
      artists.push({ name, genre });
    }

    return artists;
  }

  async getGenresList() {
    if (await this.isElementVisible('.genres-list, .genres')) {
      const genresText = await this.genresList.textContent();
      return genresText.split(',').map(g => g.trim());
    }
    return [];
  }

  async hasTicketButton() {
    return await this.isElementVisible('.ticket-button, .buy-tickets');
  }

  async hasCreatePlaylistButton() {
    return await this.isElementVisible('.create-playlist-button, .generate-playlist');
  }

  async hasShareButton() {
    return await this.isElementVisible('.share-button, .share-festival');
  }

  async hasFestivalImage() {
    return await this.isElementVisible('.festival-image, .hero-image');
  }

  async hasMap() {
    return await this.isElementVisible('.map-section, .location-map');
  }

  async validateFestivalData(expectedData) {
    const actualData = await this.getFestivalInfo();
    
    return {
      nameMatches: actualData.name === expectedData.name,
      locationMatches: actualData.location === expectedData.location,
      datesMatch: actualData.dates.includes(expectedData.dates) || 
                  expectedData.dates.includes(actualData.dates),
      hasRequiredFields: !!(actualData.name && actualData.location && actualData.dates)
    };
  }

  async validateArtistsList(expectedArtists) {
    const actualArtists = await this.getArtistsList();
    const actualNames = actualArtists.map(a => a.name.toLowerCase());
    
    const results = {
      totalFound: actualArtists.length,
      expectedFound: 0,
      missingArtists: [],
      extraArtists: actualNames.filter(name => 
        !expectedArtists.some(expected => 
          name.includes(expected.toLowerCase())
        )
      )
    };

    expectedArtists.forEach(expected => {
      const found = actualNames.some(actual => 
        actual.includes(expected.toLowerCase())
      );
      if (found) {
        results.expectedFound++;
      } else {
        results.missingArtists.push(expected);
      }
    });

    return results;
  }

  async validatePageStructure() {
    return {
      hasFestivalName: await this.isElementVisible('.festival-name, h1'),
      hasDates: await this.isElementVisible('.festival-dates, .dates'),
      hasLocation: await this.isElementVisible('.festival-location, .location'),
      hasArtistsList: await this.isElementVisible('.artists-list, .lineup'),
      hasCreatePlaylistButton: await this.hasCreatePlaylistButton(),
      hasTicketButton: await this.hasTicketButton(),
      hasShareButton: await this.hasShareButton()
    };
  }
}

module.exports = FestivalDetailPage;