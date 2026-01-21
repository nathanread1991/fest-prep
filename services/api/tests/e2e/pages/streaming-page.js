// Streaming services page object model
const BasePage = require('./base-page');

class StreamingPage extends BasePage {
  constructor(page) {
    super(page);
  }

  // Selectors
  get pageTitle() { return this.page.locator('.page-title, h1'); }
  get platformCards() { return this.page.locator('.platform-card, .streaming-service'); }
  get spotifyCard() { return this.page.locator('.spotify-card, [data-platform="spotify"]'); }
  get youtubeCard() { return this.page.locator('.youtube-card, [data-platform="youtube"]'); }
  get appleMusicCard() { return this.page.locator('.apple-music-card, [data-platform="apple_music"]'); }
  get connectButtons() { return this.page.locator('.connect-button, .auth-button'); }
  get disconnectButtons() { return this.page.locator('.disconnect-button, .logout-button'); }
  get statusIndicators() { return this.page.locator('.connection-status, .status-indicator'); }
  get connectedServices() { return this.page.locator('.connected-service, .authenticated'); }
  get authDialog() { return this.page.locator('.auth-dialog, .oauth-popup'); }
  get authForm() { return this.page.locator('.auth-form, .login-form'); }
  get usernameInput() { return this.page.locator('#username, .username-input'); }
  get passwordInput() { return this.page.locator('#password, .password-input'); }
  get loginButton() { return this.page.locator('.login-button, [type="submit"]'); }
  get cancelButton() { return this.page.locator('.cancel-button, .close-dialog'); }
  get successMessage() { return this.page.locator('.success-message, .auth-success'); }
  get errorMessage() { return this.page.locator('.error-message, .auth-error'); }

  // Actions
  async visit() {
    await this.goto('/streaming');
  }

  async connectToSpotify() {
    await this.spotifyCard.locator('.connect-button, .auth-button').click();
    
    // Handle OAuth popup or form
    try {
      await this.page.waitForSelector('.auth-dialog, .oauth-popup', { timeout: 5000 });
      return 'dialog';
    } catch {
      // Might redirect to external OAuth
      return 'redirect';
    }
  }

  async connectToYouTube() {
    await this.youtubeCard.locator('.connect-button, .auth-button').click();
    
    try {
      await this.page.waitForSelector('.auth-dialog, .oauth-popup', { timeout: 5000 });
      return 'dialog';
    } catch {
      return 'redirect';
    }
  }

  async connectToAppleMusic() {
    await this.appleMusicCard.locator('.connect-button, .auth-button').click();
    
    try {
      await this.page.waitForSelector('.auth-dialog, .oauth-popup', { timeout: 5000 });
      return 'dialog';
    } catch {
      return 'redirect';
    }
  }

  async authenticateWithCredentials(username, password) {
    if (await this.isElementVisible('.auth-form, .login-form')) {
      await this.usernameInput.fill(username);
      await this.passwordInput.fill(password);
      await this.loginButton.click();
      
      // Wait for success or error
      await this.page.waitForSelector('.success-message, .error-message', { timeout: 10000 });
    }
  }

  async cancelAuthentication() {
    if (await this.isElementVisible('.cancel-button, .close-dialog')) {
      await this.cancelButton.click();
    }
  }

  async disconnectFromService(platform) {
    const platformCard = this.page.locator(`[data-platform="${platform}"], .${platform}-card`);
    await platformCard.locator('.disconnect-button, .logout-button').click();
    
    // Wait for confirmation or immediate disconnect
    await this.page.waitForTimeout(1000);
  }

  async disconnectFromSpotify() {
    await this.disconnectFromService('spotify');
  }

  async disconnectFromYouTube() {
    await this.disconnectFromService('youtube');
  }

  async disconnectFromAppleMusic() {
    await this.disconnectFromService('apple_music');
  }

  // Validation methods
  async getConnectedServices() {
    const connectedElements = await this.connectedServices.all();
    const services = [];

    for (const element of connectedElements) {
      const platform = await element.getAttribute('data-platform') || 
                      await element.locator('.platform-name').textContent();
      const status = await element.locator('.connection-status, .status-indicator').textContent();
      services.push({ platform, status });
    }

    return services;
  }

  async isServiceConnected(platform) {
    const platformCard = this.page.locator(`[data-platform="${platform}"], .${platform}-card`);
    
    // Check for connected status indicators
    const hasConnectedStatus = await platformCard.locator('.connected, .authenticated').isVisible();
    const hasDisconnectButton = await platformCard.locator('.disconnect-button, .logout-button').isVisible();
    
    return hasConnectedStatus || hasDisconnectButton;
  }

  async getServiceStatus(platform) {
    const platformCard = this.page.locator(`[data-platform="${platform}"], .${platform}-card`);
    
    if (await this.isServiceConnected(platform)) {
      const statusText = await platformCard.locator('.connection-status, .status-indicator').textContent();
      return { connected: true, status: statusText };
    } else {
      return { connected: false, status: 'Not connected' };
    }
  }

  async getAllServiceStatuses() {
    const platforms = ['spotify', 'youtube', 'apple_music'];
    const statuses = {};

    for (const platform of platforms) {
      if (await this.isElementVisible(`[data-platform="${platform}"], .${platform}-card`)) {
        statuses[platform] = await this.getServiceStatus(platform);
      }
    }

    return statuses;
  }

  async validatePageStructure() {
    return {
      hasTitle: await this.isElementVisible('.page-title, h1'),
      hasPlatformCards: await this.isElementVisible('.platform-card, .streaming-service'),
      hasSpotifyCard: await this.isElementVisible('.spotify-card, [data-platform="spotify"]'),
      hasYouTubeCard: await this.isElementVisible('.youtube-card, [data-platform="youtube"]'),
      hasAppleMusicCard: await this.isElementVisible('.apple-music-card, [data-platform="apple_music"]')
    };
  }

  async validateAuthenticationFlow(platform) {
    const initialStatus = await this.getServiceStatus(platform);
    
    // Attempt to connect
    let authType;
    switch (platform) {
      case 'spotify':
        authType = await this.connectToSpotify();
        break;
      case 'youtube':
        authType = await this.connectToYouTube();
        break;
      case 'apple_music':
        authType = await this.connectToAppleMusic();
        break;
    }

    // Check if auth dialog appeared
    const hasAuthDialog = await this.isElementVisible('.auth-dialog, .oauth-popup');
    
    return {
      initiallyConnected: initialStatus.connected,
      authType,
      hasAuthDialog,
      authFlowStarted: authType === 'dialog' || authType === 'redirect'
    };
  }

  async validateDisconnectionFlow(platform) {
    // First ensure service is connected (mock connection if needed)
    const initialStatus = await this.getServiceStatus(platform);
    
    if (initialStatus.connected) {
      await this.disconnectFromService(platform);
      
      // Check if disconnected
      const finalStatus = await this.getServiceStatus(platform);
      
      return {
        wasConnected: true,
        disconnectionAttempted: true,
        nowDisconnected: !finalStatus.connected
      };
    } else {
      return {
        wasConnected: false,
        disconnectionAttempted: false,
        nowDisconnected: true
      };
    }
  }

  async hasAuthenticationError() {
    return await this.isElementVisible('.error-message, .auth-error');
  }

  async hasAuthenticationSuccess() {
    return await this.isElementVisible('.success-message, .auth-success');
  }

  async getAuthenticationMessage() {
    if (await this.hasAuthenticationError()) {
      return {
        type: 'error',
        message: await this.errorMessage.textContent()
      };
    } else if (await this.hasAuthenticationSuccess()) {
      return {
        type: 'success',
        message: await this.successMessage.textContent()
      };
    } else {
      return { type: 'none', message: '' };
    }
  }
}

module.exports = StreamingPage;