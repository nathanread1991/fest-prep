// Festival search and discovery workflow tests
const { test, expect } = require('../utils/base-test');
const HomePage = require('../pages/home-page');
const FestivalsPage = require('../pages/festivals-page');
const FestivalDetailPage = require('../pages/festival-detail-page');

test.describe('Festival Search and Discovery Workflow', () => {
  let homePage;
  let festivalsPage;
  let festivalDetailPage;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    festivalsPage = new FestivalsPage(page);
    festivalDetailPage = new FestivalDetailPage(page);

    // Mock API responses for consistent testing
    await page.route('**/api/v1/festivals**', async route => {
      const url = route.request().url();
      const searchParams = new URL(url).searchParams;
      const query = searchParams.get('q') || '';
      const genre = searchParams.get('genre') || '';
      const location = searchParams.get('location') || '';

      let festivals = [
        {
          id: 'coachella-2024',
          name: 'Coachella Valley Music and Arts Festival',
          dates: ['2024-04-12', '2024-04-14'],
          location: 'Indio, CA',
          venue: 'Empire Polo Club',
          artists: ['Lana Del Rey', 'Tyler, The Creator', 'Doja Cat'],
          genres: ['Pop', 'Hip Hop', 'Alternative']
        },
        {
          id: 'bonnaroo-2024',
          name: 'Bonnaroo Music & Arts Festival',
          dates: ['2024-06-13', '2024-06-16'],
          location: 'Manchester, TN',
          venue: 'Great Stage Park',
          artists: ['Post Malone', 'Red Hot Chili Peppers'],
          genres: ['Rock', 'Hip Hop']
        },
        {
          id: 'lollapalooza-2024',
          name: 'Lollapalooza',
          dates: ['2024-08-01', '2024-08-04'],
          location: 'Chicago, IL',
          venue: 'Grant Park',
          artists: ['The Killers', 'Future', 'Blink-182'],
          genres: ['Rock', 'Electronic', 'Hip Hop']
        }
      ];

      // Apply filters
      if (query) {
        festivals = festivals.filter(f => 
          f.name.toLowerCase().includes(query.toLowerCase()) ||
          f.location.toLowerCase().includes(query.toLowerCase()) ||
          f.artists.some(a => a.toLowerCase().includes(query.toLowerCase()))
        );
      }

      if (genre) {
        festivals = festivals.filter(f => 
          f.genres.some(g => g.toLowerCase().includes(genre.toLowerCase()))
        );
      }

      if (location) {
        festivals = festivals.filter(f => 
          f.location.toLowerCase().includes(location.toLowerCase())
        );
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          festivals,
          total: festivals.length,
          page: 1,
          per_page: 10
        })
      });
    });

    // Mock individual festival details
    await page.route('**/api/v1/festivals/*', async route => {
      const festivalId = route.request().url().split('/').pop();
      const festivals = {
        'coachella-2024': {
          id: 'coachella-2024',
          name: 'Coachella Valley Music and Arts Festival',
          dates: ['2024-04-12', '2024-04-14', '2024-04-19', '2024-04-21'],
          location: 'Indio, CA',
          venue: 'Empire Polo Club',
          description: 'The premier music and arts festival in the California desert.',
          artists: ['Lana Del Rey', 'Tyler, The Creator', 'Doja Cat', 'No Doubt', 'Ice Spice'],
          genres: ['Pop', 'Hip Hop', 'Alternative', 'Electronic'],
          ticket_url: 'https://coachella.com/tickets'
        }
      };

      const festival = festivals[festivalId];
      if (festival) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(festival)
        });
      } else {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Festival not found' })
        });
      }
    });
  });

  test('should search festivals from home page', async () => {
    await homePage.visit();
    
    // Validate home page loads
    const heroValidation = await homePage.validateHeroSection();
    expect(heroValidation.hasTitle).toBe(true);
    expect(heroValidation.hasSubtitle).toBe(true);

    const searchValidation = await homePage.validateSearchForm();
    expect(searchValidation.formVisible).toBe(true);
    expect(searchValidation.inputEnabled).toBe(true);
    expect(searchValidation.buttonEnabled).toBe(true);

    // Perform search
    await homePage.searchFor('Coachella');
    
    // Should navigate to search results
    expect(page.url()).toContain('search');
    
    // Wait for results to load
    await page.waitForSelector('.festival-card, .no-results', { timeout: 10000 });
    
    // Validate search results
    const hasResults = await page.isVisible('.festival-card');
    expect(hasResults).toBe(true);
    
    const coachella = await page.textContent('.festival-card:first-child .festival-name');
    expect(coachella).toContain('Coachella');
  });

  test('should browse festivals page and use filters', async () => {
    await festivalsPage.visit();
    
    // Validate festivals page loads
    await expect(festivalsPage.pageTitle).toBeVisible();
    await expect(festivalsPage.festivalGrid).toBeVisible();
    
    // Check initial festival count
    const initialCount = await festivalsPage.getFestivalCount();
    expect(initialCount).toBeGreaterThan(0);
    
    // Test search functionality
    await festivalsPage.searchFestivals('Bonnaroo');
    
    const searchResults = await festivalsPage.validateSearchResults('Bonnaroo');
    expect(searchResults.length).toBeGreaterThan(0);
    expect(searchResults[0].matchesQuery).toBe(true);
    
    // Clear search and test genre filter
    await festivalsPage.searchFestivals('');
    
    // Test genre filter if available
    if (await festivalsPage.isElementVisible('#genre-filter, .genre-filter')) {
      await festivalsPage.filterByGenre('Rock');
      
      const genreResults = await festivalsPage.validateFilters('genre', 'Rock');
      genreResults.forEach(result => {
        expect(result.matchesFilter).toBe(true);
      });
    }
    
    // Test location filter if available
    if (await festivalsPage.isElementVisible('#location-filter, .location-filter')) {
      await festivalsPage.filterByLocation('Chicago');
      
      const locationResults = await festivalsPage.validateFilters('location', 'Chicago');
      expect(locationResults.length).toBeGreaterThan(0);
    }
  });

  test('should navigate to festival detail page', async () => {
    await festivalsPage.visit();
    
    // Wait for festivals to load
    await festivalsPage.waitForElement('.festival-card');
    
    // Get first festival data
    const festivalData = await festivalsPage.getFestivalData(0);
    expect(festivalData).toBeTruthy();
    expect(festivalData.name).toBeTruthy();
    
    // Click on first festival
    await festivalsPage.clickFestival(festivalData.name);
    
    // Should navigate to festival detail page
    expect(page.url()).toMatch(/\/festivals\/[^\/]+$/);
    
    // Validate festival detail page structure
    const pageStructure = await festivalDetailPage.validatePageStructure();
    expect(pageStructure.hasFestivalName).toBe(true);
    expect(pageStructure.hasDates).toBe(true);
    expect(pageStructure.hasLocation).toBe(true);
    expect(pageStructure.hasArtistsList).toBe(true);
    
    // Validate festival information
    const detailInfo = await festivalDetailPage.getFestivalInfo();
    expect(detailInfo.name).toBeTruthy();
    expect(detailInfo.location).toBeTruthy();
    expect(detailInfo.dates).toBeTruthy();
    
    // Validate artists list
    const artists = await festivalDetailPage.getArtistsList();
    expect(artists.length).toBeGreaterThan(0);
    expect(artists[0].name).toBeTruthy();
  });

  test('should handle empty search results gracefully', async () => {
    await festivalsPage.visit();
    
    // Search for non-existent festival
    await festivalsPage.searchFestivals('NonExistentFestival12345');
    
    // Should show no results message
    const hasNoResults = await festivalsPage.hasNoResults();
    expect(hasNoResults).toBe(true);
    
    // Should not show any festival cards
    const festivalCount = await festivalsPage.getFestivalCount();
    expect(festivalCount).toBe(0);
  });

  test('should validate festival detail page data accuracy', async () => {
    // Navigate directly to a known festival
    await festivalDetailPage.visit('coachella-2024');
    
    // Validate the festival data matches expected values
    const validation = await festivalDetailPage.validateFestivalData({
      name: 'Coachella Valley Music and Arts Festival',
      location: 'Indio, CA',
      dates: '2024-04-12'
    });
    
    expect(validation.nameMatches).toBe(true);
    expect(validation.locationMatches).toBe(true);
    expect(validation.hasRequiredFields).toBe(true);
    
    // Validate artists list
    const artistValidation = await festivalDetailPage.validateArtistsList([
      'Lana Del Rey', 'Tyler, The Creator', 'Doja Cat'
    ]);
    
    expect(artistValidation.expectedFound).toBeGreaterThan(0);
    expect(artistValidation.missingArtists.length).toBe(0);
  });

  test('should handle festival detail page not found', async () => {
    // Navigate to non-existent festival
    await festivalDetailPage.visit('non-existent-festival');
    
    // Should show 404 or error message
    const hasError = await festivalDetailPage.isElementVisible('.error, .not-found');
    expect(hasError).toBe(true);
  });

  test('should support pagination or load more functionality', async () => {
    await festivalsPage.visit();
    
    // Check if load more button exists
    if (await festivalsPage.isElementVisible('.load-more, .pagination-next')) {
      const initialCount = await festivalsPage.getFestivalCount();
      
      await festivalsPage.loadMoreFestivals();
      
      const newCount = await festivalsPage.getFestivalCount();
      expect(newCount).toBeGreaterThan(initialCount);
    }
  });

  test('should maintain search state during navigation', async () => {
    await festivalsPage.visit();
    
    // Perform search
    await festivalsPage.searchFestivals('Coachella');
    
    // Navigate to detail page
    const festivalData = await festivalsPage.getFestivalData(0);
    if (festivalData) {
      await festivalsPage.clickFestival(festivalData.name);
      
      // Go back
      await festivalDetailPage.goBack();
      
      // Search should still be active
      const searchValue = await festivalsPage.searchInput.inputValue();
      expect(searchValue).toBe('Coachella');
    }
  });
});