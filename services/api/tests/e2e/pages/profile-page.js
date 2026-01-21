// User profile page object model
const BasePage = require('./base-page');

class ProfilePage extends BasePage {
  constructor(page) {
    super(page);
  }

  // Selectors
  get profileForm() { return this.page.locator('.profile-form, #profile-form'); }
  get nameInput() { return this.page.locator('#name, .name-input'); }
  get emailInput() { return this.page.locator('#email, .email-input'); }
  get currentPasswordInput() { return this.page.locator('#current-password, .current-password-input'); }
  get newPasswordInput() { return this.page.locator('#new-password, .new-password-input'); }
  get confirmPasswordInput() { return this.page.locator('#confirm-password, .confirm-password-input'); }
  get saveButton() { return this.page.locator('.save-button, [type="submit"]'); }
  get cancelButton() { return this.page.locator('.cancel-button, .reset-button'); }
  get deleteAccountButton() { return this.page.locator('.delete-account, .danger-button'); }
  get preferencesSection() { return this.page.locator('.preferences-section, .user-preferences'); }
  get streamingPlatformSelect() { return this.page.locator('#streaming-platform, .platform-select'); }
  get notificationSettings() { return this.page.locator('.notification-settings, .notifications'); }
  get emailNotifications() { return this.page.locator('#email-notifications, .email-notifications-toggle'); }
  get pushNotifications() { return this.page.locator('#push-notifications, .push-notifications-toggle'); }
  get showKnownSongsToggle() { return this.page.locator('#show-known-songs, .show-known-toggle'); }
  get successMessage() { return this.page.locator('.success-message, .save-success'); }
  get errorMessage() { return this.page.locator('.error-message, .save-error'); }
  get validationErrors() { return this.page.locator('.field-error, .validation-error'); }
  get profilePicture() { return this.page.locator('.profile-picture, .avatar'); }
  get uploadButton() { return this.page.locator('.upload-button, .change-avatar'); }
  get fileInput() { return this.page.locator('input[type="file"]'); }

  // Actions
  async visit() {
    await this.goto('/profile');
  }

  async updateProfile(profileData) {
    if (profileData.name) {
      await this.nameInput.fill(profileData.name);
    }
    
    if (profileData.email) {
      await this.emailInput.fill(profileData.email);
    }
    
    await this.saveButton.click();
    
    // Wait for save to complete
    await this.page.waitForSelector('.success-message, .error-message', { timeout: 10000 });
  }

  async changePassword(currentPassword, newPassword, confirmPassword) {
    await this.currentPasswordInput.fill(currentPassword);
    await this.newPasswordInput.fill(newPassword);
    await this.confirmPasswordInput.fill(confirmPassword);
    
    await this.saveButton.click();
    
    // Wait for password change to complete
    await this.page.waitForSelector('.success-message, .error-message', { timeout: 10000 });
  }

  async updatePreferences(preferences) {
    if (preferences.streamingPlatform) {
      await this.streamingPlatformSelect.selectOption(preferences.streamingPlatform);
    }
    
    if (preferences.emailNotifications !== undefined) {
      const isChecked = await this.emailNotifications.isChecked();
      if (isChecked !== preferences.emailNotifications) {
        await this.emailNotifications.click();
      }
    }
    
    if (preferences.pushNotifications !== undefined) {
      const isChecked = await this.pushNotifications.isChecked();
      if (isChecked !== preferences.pushNotifications) {
        await this.pushNotifications.click();
      }
    }
    
    if (preferences.showKnownSongs !== undefined) {
      const isChecked = await this.showKnownSongsToggle.isChecked();
      if (isChecked !== preferences.showKnownSongs) {
        await this.showKnownSongsToggle.click();
      }
    }
    
    await this.saveButton.click();
    
    // Wait for preferences to save
    await this.page.waitForSelector('.success-message, .error-message', { timeout: 10000 });
  }

  async uploadProfilePicture(filePath) {
    if (await this.isElementVisible('.upload-button, .change-avatar')) {
      await this.uploadButton.click();
    }
    
    await this.fileInput.setInputFiles(filePath);
    
    // Wait for upload to complete
    await this.page.waitForSelector('.success-message, .error-message', { timeout: 15000 });
  }

  async deleteAccount() {
    await this.deleteAccountButton.click();
    
    // Handle confirmation dialog
    await this.page.waitForSelector('.confirm-dialog, .delete-confirmation', { timeout: 5000 });
    await this.page.click('.confirm-delete, .yes-button');
    
    // Wait for deletion to complete
    await this.page.waitForSelector('.login-form, .goodbye-message', { timeout: 10000 });
  }

  async cancelChanges() {
    await this.cancelButton.click();
  }

  // Validation methods
  async getProfileData() {
    const name = await this.nameInput.inputValue();
    const email = await this.emailInput.inputValue();
    
    return { name, email };
  }

  async getPreferences() {
    const preferences = {};
    
    if (await this.isElementVisible('#streaming-platform, .platform-select')) {
      preferences.streamingPlatform = await this.streamingPlatformSelect.inputValue();
    }
    
    if (await this.isElementVisible('#email-notifications, .email-notifications-toggle')) {
      preferences.emailNotifications = await this.emailNotifications.isChecked();
    }
    
    if (await this.isElementVisible('#push-notifications, .push-notifications-toggle')) {
      preferences.pushNotifications = await this.pushNotifications.isChecked();
    }
    
    if (await this.isElementVisible('#show-known-songs, .show-known-toggle')) {
      preferences.showKnownSongs = await this.showKnownSongsToggle.isChecked();
    }
    
    return preferences;
  }

  async hasSuccessMessage() {
    return await this.isElementVisible('.success-message, .save-success');
  }

  async hasErrorMessage() {
    return await this.isElementVisible('.error-message, .save-error');
  }

  async getSuccessMessage() {
    if (await this.hasSuccessMessage()) {
      return await this.successMessage.textContent();
    }
    return null;
  }

  async getErrorMessage() {
    if (await this.hasErrorMessage()) {
      return await this.errorMessage.textContent();
    }
    return null;
  }

  async getValidationErrors() {
    const errors = [];
    const errorElements = await this.validationErrors.all();
    
    for (const element of errorElements) {
      const text = await element.textContent();
      errors.push(text);
    }
    
    return errors;
  }

  async validateProfileForm() {
    return {
      hasForm: await this.isElementVisible('.profile-form, #profile-form'),
      hasNameInput: await this.isElementVisible('#name, .name-input'),
      hasEmailInput: await this.isElementVisible('#email, .email-input'),
      hasSaveButton: await this.isElementVisible('.save-button, [type="submit"]'),
      hasCancelButton: await this.isElementVisible('.cancel-button, .reset-button')
    };
  }

  async validatePasswordChangeForm() {
    return {
      hasCurrentPasswordInput: await this.isElementVisible('#current-password, .current-password-input'),
      hasNewPasswordInput: await this.isElementVisible('#new-password, .new-password-input'),
      hasConfirmPasswordInput: await this.isElementVisible('#confirm-password, .confirm-password-input')
    };
  }

  async validatePreferencesSection() {
    return {
      hasPreferencesSection: await this.isElementVisible('.preferences-section, .user-preferences'),
      hasStreamingPlatformSelect: await this.isElementVisible('#streaming-platform, .platform-select'),
      hasNotificationSettings: await this.isElementVisible('.notification-settings, .notifications'),
      hasEmailNotificationsToggle: await this.isElementVisible('#email-notifications, .email-notifications-toggle'),
      hasPushNotificationsToggle: await this.isElementVisible('#push-notifications, .push-notifications-toggle'),
      hasShowKnownSongsToggle: await this.isElementVisible('#show-known-songs, .show-known-toggle')
    };
  }

  async testProfileUpdate(newData) {
    const initialData = await this.getProfileData();
    
    await this.updateProfile(newData);
    
    const hasSuccess = await this.hasSuccessMessage();
    const hasError = await this.hasErrorMessage();
    const finalData = await this.getProfileData();
    
    return {
      initialData,
      finalData,
      updateSuccessful: hasSuccess && !hasError,
      dataChanged: JSON.stringify(initialData) !== JSON.stringify(finalData),
      hasSuccess,
      hasError,
      successMessage: await this.getSuccessMessage(),
      errorMessage: await this.getErrorMessage()
    };
  }

  async testPreferencesUpdate(newPreferences) {
    const initialPreferences = await this.getPreferences();
    
    await this.updatePreferences(newPreferences);
    
    const hasSuccess = await this.hasSuccessMessage();
    const hasError = await this.hasErrorMessage();
    const finalPreferences = await this.getPreferences();
    
    return {
      initialPreferences,
      finalPreferences,
      updateSuccessful: hasSuccess && !hasError,
      preferencesChanged: JSON.stringify(initialPreferences) !== JSON.stringify(finalPreferences),
      hasSuccess,
      hasError,
      successMessage: await this.getSuccessMessage(),
      errorMessage: await this.getErrorMessage()
    };
  }

  async testPasswordChange(currentPassword, newPassword, confirmPassword) {
    await this.changePassword(currentPassword, newPassword, confirmPassword);
    
    const hasSuccess = await this.hasSuccessMessage();
    const hasError = await this.hasErrorMessage();
    const validationErrors = await this.getValidationErrors();
    
    return {
      changeSuccessful: hasSuccess && !hasError,
      hasSuccess,
      hasError,
      hasValidationErrors: validationErrors.length > 0,
      successMessage: await this.getSuccessMessage(),
      errorMessage: await this.getErrorMessage(),
      validationErrors
    };
  }

  async hasProfilePicture() {
    return await this.isElementVisible('.profile-picture, .avatar');
  }

  async canUploadProfilePicture() {
    return await this.isElementVisible('.upload-button, .change-avatar, input[type="file"]');
  }

  async canDeleteAccount() {
    return await this.isElementVisible('.delete-account, .danger-button');
  }
}

module.exports = ProfilePage;