// Authentication page object model
const BasePage = require('./base-page');

class AuthPage extends BasePage {
  constructor(page) {
    super(page);
  }

  // Selectors
  get loginForm() { return this.page.locator('.login-form, #login-form'); }
  get registerForm() { return this.page.locator('.register-form, #register-form'); }
  get emailInput() { return this.page.locator('#email, .email-input'); }
  get passwordInput() { return this.page.locator('#password, .password-input'); }
  get confirmPasswordInput() { return this.page.locator('#confirm-password, .confirm-password-input'); }
  get nameInput() { return this.page.locator('#name, .name-input'); }
  get loginButton() { return this.page.locator('.login-button, [type="submit"]'); }
  get registerButton() { return this.page.locator('.register-button, .signup-button'); }
  get forgotPasswordLink() { return this.page.locator('.forgot-password, .reset-password-link'); }
  get switchToRegisterLink() { return this.page.locator('.switch-to-register, .signup-link'); }
  get switchToLoginLink() { return this.page.locator('.switch-to-login, .login-link'); }
  get errorMessage() { return this.page.locator('.error-message, .auth-error'); }
  get successMessage() { return this.page.locator('.success-message, .auth-success'); }
  get loadingIndicator() { return this.page.locator('.loading, .auth-loading'); }
  get logoutButton() { return this.page.locator('.logout-button, .sign-out'); }
  get userMenu() { return this.page.locator('.user-menu, .profile-menu'); }
  get userProfile() { return this.page.locator('.user-profile, .profile-info'); }

  // Actions
  async visitLogin() {
    await this.goto('/login');
  }

  async visitRegister() {
    await this.goto('/register');
  }

  async login(email, password) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
    
    // Wait for login to complete
    await this.page.waitForSelector('.success-message, .error-message, .user-menu', { timeout: 10000 });
  }

  async register(name, email, password, confirmPassword = null) {
    await this.nameInput.fill(name);
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    
    if (confirmPassword && await this.isElementVisible('#confirm-password, .confirm-password-input')) {
      await this.confirmPasswordInput.fill(confirmPassword);
    }
    
    await this.registerButton.click();
    
    // Wait for registration to complete
    await this.page.waitForSelector('.success-message, .error-message, .user-menu', { timeout: 10000 });
  }

  async logout() {
    // Open user menu if it exists
    if (await this.isElementVisible('.user-menu, .profile-menu')) {
      await this.userMenu.click();
    }
    
    await this.logoutButton.click();
    
    // Wait for logout to complete
    await this.page.waitForSelector('.login-form, .login-button', { timeout: 10000 });
  }

  async switchToRegister() {
    await this.switchToRegisterLink.click();
    await this.waitForElement('.register-form, #register-form');
  }

  async switchToLogin() {
    await this.switchToLoginLink.click();
    await this.waitForElement('.login-form, #login-form');
  }

  async forgotPassword(email) {
    await this.forgotPasswordLink.click();
    
    // Fill email in forgot password form
    if (await this.isElementVisible('#email, .email-input')) {
      await this.emailInput.fill(email);
      await this.page.click('.reset-button, [type="submit"]');
    }
    
    await this.page.waitForSelector('.success-message, .error-message', { timeout: 10000 });
  }

  // Validation methods
  async isLoggedIn() {
    return await this.isElementVisible('.user-menu, .logout-button, .user-profile');
  }

  async isLoggedOut() {
    return await this.isElementVisible('.login-form, .login-button');
  }

  async getCurrentUser() {
    if (await this.isLoggedIn()) {
      // Try to get user info from profile or menu
      if (await this.isElementVisible('.user-profile, .profile-info')) {
        const name = await this.page.textContent('.user-name, .profile-name').catch(() => '');
        const email = await this.page.textContent('.user-email, .profile-email').catch(() => '');
        return { name, email };
      } else if (await this.isElementVisible('.user-menu')) {
        const menuText = await this.userMenu.textContent();
        return { name: menuText, email: '' };
      }
    }
    return null;
  }

  async getAuthError() {
    if (await this.isElementVisible('.error-message, .auth-error')) {
      return await this.errorMessage.textContent();
    }
    return null;
  }

  async getAuthSuccess() {
    if (await this.isElementVisible('.success-message, .auth-success')) {
      return await this.successMessage.textContent();
    }
    return null;
  }

  async hasValidationErrors() {
    return await this.isElementVisible('.field-error, .validation-error, .invalid-feedback');
  }

  async getValidationErrors() {
    const errors = [];
    const errorElements = await this.page.locator('.field-error, .validation-error, .invalid-feedback').all();
    
    for (const element of errorElements) {
      const text = await element.textContent();
      errors.push(text);
    }
    
    return errors;
  }

  async validateLoginForm() {
    return {
      hasForm: await this.isElementVisible('.login-form, #login-form'),
      hasEmailInput: await this.isElementVisible('#email, .email-input'),
      hasPasswordInput: await this.isElementVisible('#password, .password-input'),
      hasLoginButton: await this.isElementVisible('.login-button, [type="submit"]'),
      hasForgotPasswordLink: await this.isElementVisible('.forgot-password, .reset-password-link'),
      hasSwitchToRegister: await this.isElementVisible('.switch-to-register, .signup-link')
    };
  }

  async validateRegisterForm() {
    return {
      hasForm: await this.isElementVisible('.register-form, #register-form'),
      hasNameInput: await this.isElementVisible('#name, .name-input'),
      hasEmailInput: await this.isElementVisible('#email, .email-input'),
      hasPasswordInput: await this.isElementVisible('#password, .password-input'),
      hasConfirmPasswordInput: await this.isElementVisible('#confirm-password, .confirm-password-input'),
      hasRegisterButton: await this.isElementVisible('.register-button, .signup-button'),
      hasSwitchToLogin: await this.isElementVisible('.switch-to-login, .login-link')
    };
  }

  async validateAuthenticationState() {
    const isLoggedIn = await this.isLoggedIn();
    const isLoggedOut = await this.isLoggedOut();
    const currentUser = await this.getCurrentUser();
    
    return {
      isLoggedIn,
      isLoggedOut,
      currentUser,
      hasValidState: isLoggedIn !== isLoggedOut // Should be mutually exclusive
    };
  }

  async testLoginFlow(email, password) {
    const initialState = await this.validateAuthenticationState();
    
    await this.login(email, password);
    
    const finalState = await this.validateAuthenticationState();
    const error = await this.getAuthError();
    const success = await this.getAuthSuccess();
    
    return {
      initiallyLoggedIn: initialState.isLoggedIn,
      finallyLoggedIn: finalState.isLoggedIn,
      loginSuccessful: !initialState.isLoggedIn && finalState.isLoggedIn,
      hasError: !!error,
      hasSuccess: !!success,
      errorMessage: error,
      successMessage: success
    };
  }

  async testRegistrationFlow(name, email, password, confirmPassword) {
    const initialState = await this.validateAuthenticationState();
    
    await this.register(name, email, password, confirmPassword);
    
    const finalState = await this.validateAuthenticationState();
    const error = await this.getAuthError();
    const success = await this.getAuthSuccess();
    const validationErrors = await this.getValidationErrors();
    
    return {
      initiallyLoggedIn: initialState.isLoggedIn,
      finallyLoggedIn: finalState.isLoggedIn,
      registrationSuccessful: !initialState.isLoggedIn && finalState.isLoggedIn,
      hasError: !!error,
      hasSuccess: !!success,
      hasValidationErrors: validationErrors.length > 0,
      errorMessage: error,
      successMessage: success,
      validationErrors
    };
  }

  async testLogoutFlow() {
    const initialState = await this.validateAuthenticationState();
    
    if (initialState.isLoggedIn) {
      await this.logout();
      
      const finalState = await this.validateAuthenticationState();
      
      return {
        initiallyLoggedIn: true,
        finallyLoggedOut: finalState.isLoggedOut,
        logoutSuccessful: finalState.isLoggedOut
      };
    } else {
      return {
        initiallyLoggedIn: false,
        finallyLoggedOut: true,
        logoutSuccessful: false // Can't logout if not logged in
      };
    }
  }

  async testSessionPersistence() {
    // Check if logged in
    const initialState = await this.validateAuthenticationState();
    
    if (initialState.isLoggedIn) {
      // Refresh page
      await this.page.reload();
      await this.waitForPageLoad();
      
      // Check if still logged in
      const afterRefreshState = await this.validateAuthenticationState();
      
      return {
        wasLoggedIn: true,
        stillLoggedIn: afterRefreshState.isLoggedIn,
        sessionPersisted: afterRefreshState.isLoggedIn
      };
    } else {
      return {
        wasLoggedIn: false,
        stillLoggedIn: false,
        sessionPersisted: true // Not logged in is the expected state
      };
    }
  }
}

module.exports = AuthPage;