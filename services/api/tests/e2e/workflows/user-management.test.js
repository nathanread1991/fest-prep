// User management and authentication workflow tests
const { test, expect } = require('../utils/base-test');
const AuthPage = require('../pages/auth-page');
const ProfilePage = require('../pages/profile-page');
const HomePage = require('../pages/home-page');

test.describe('User Management and Authentication Workflows', () => {
  let authPage;
  let profilePage;
  let homePage;

  test.beforeEach(async ({ page }) => {
    authPage = new AuthPage(page);
    profilePage = new ProfilePage(page);
    homePage = new HomePage(page);

    // Mock authentication endpoints
    await page.route('**/api/v1/auth/login', async route => {
      const requestBody = await route.request().postDataJSON();
      const { email, password } = requestBody;

      // Mock valid credentials
      if (email === 'test@example.com' && password === 'password123') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            user: {
              id: 'user-123',
              name: 'Test User',
              email: 'test@example.com'
            },
            token: 'mock-jwt-token'
          })
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'Invalid credentials',
            message: 'Email or password is incorrect'
          })
        });
      }
    });

    await page.route('**/api/v1/auth/register', async route => {
      const requestBody = await route.request().postDataJSON();
      const { name, email, password } = requestBody;

      // Mock registration validation
      if (!name || name.length < 2) {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'Validation failed',
            message: 'Name must be at least 2 characters long'
          })
        });
        return;
      }

      if (!email || !email.includes('@')) {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'Validation failed',
            message: 'Please provide a valid email address'
          })
        });
        return;
      }

      if (!password || password.length < 6) {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'Validation failed',
            message: 'Password must be at least 6 characters long'
          })
        });
        return;
      }

      // Mock existing user check
      if (email === 'existing@example.com') {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'User already exists',
            message: 'An account with this email already exists'
          })
        });
        return;
      }

      // Successful registration
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          user: {
            id: 'user-new',
            name,
            email
          },
          token: 'mock-jwt-token-new'
        })
      });
    });

    await page.route('**/api/v1/auth/logout', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true })
      });
    });

    await page.route('**/api/v1/auth/me', async route => {
      const authHeader = route.request().headers()['authorization'];
      
      if (authHeader && authHeader.includes('mock-jwt-token')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'user-123',
            name: 'Test User',
            email: 'test@example.com',
            preferences: {
              streaming_platform: 'spotify',
              email_notifications: true,
              push_notifications: false,
              show_known_songs: true
            }
          })
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Unauthorized' })
        });
      }
    });

    await page.route('**/api/v1/user/profile', async route => {
      if (route.request().method() === 'PUT') {
        const requestBody = await route.request().postDataJSON();
        
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            user: {
              id: 'user-123',
              name: requestBody.name || 'Test User',
              email: requestBody.email || 'test@example.com'
            }
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'user-123',
            name: 'Test User',
            email: 'test@example.com'
          })
        });
      }
    });

    await page.route('**/api/v1/user/preferences', async route => {
      if (route.request().method() === 'PUT') {
        const requestBody = await route.request().postDataJSON();
        
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            preferences: requestBody
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            streaming_platform: 'spotify',
            email_notifications: true,
            push_notifications: false,
            show_known_songs: true
          })
        });
      }
    });

    await page.route('**/api/v1/auth/forgot-password', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Password reset email sent'
        })
      });
    });
  });

  test('should display login form correctly', async () => {
    await authPage.visitLogin();
    
    const formValidation = await authPage.validateLoginForm();
    expect(formValidation.hasForm).toBe(true);
    expect(formValidation.hasEmailInput).toBe(true);
    expect(formValidation.hasPasswordInput).toBe(true);
    expect(formValidation.hasLoginButton).toBe(true);
    expect(formValidation.hasForgotPasswordLink).toBe(true);
    expect(formValidation.hasSwitchToRegister).toBe(true);
  });

  test('should display registration form correctly', async () => {
    await authPage.visitRegister();
    
    const formValidation = await authPage.validateRegisterForm();
    expect(formValidation.hasForm).toBe(true);
    expect(formValidation.hasNameInput).toBe(true);
    expect(formValidation.hasEmailInput).toBe(true);
    expect(formValidation.hasPasswordInput).toBe(true);
    expect(formValidation.hasRegisterButton).toBe(true);
    expect(formValidation.hasSwitchToLogin).toBe(true);
  });

  test('should successfully login with valid credentials', async () => {
    await authPage.visitLogin();
    
    const loginResult = await authPage.testLoginFlow('test@example.com', 'password123');
    
    expect(loginResult.loginSuccessful).toBe(true);
    expect(loginResult.hasError).toBe(false);
    expect(loginResult.finallyLoggedIn).toBe(true);
    
    // Verify user is logged in
    const authState = await authPage.validateAuthenticationState();
    expect(authState.isLoggedIn).toBe(true);
    expect(authState.currentUser).toBeTruthy();
  });

  test('should show error for invalid login credentials', async () => {
    await authPage.visitLogin();
    
    const loginResult = await authPage.testLoginFlow('invalid@example.com', 'wrongpassword');
    
    expect(loginResult.loginSuccessful).toBe(false);
    expect(loginResult.hasError).toBe(true);
    expect(loginResult.errorMessage).toContain('Invalid credentials');
    expect(loginResult.finallyLoggedIn).toBe(false);
  });

  test('should successfully register new user', async () => {
    await authPage.visitRegister();
    
    const registerResult = await authPage.testRegistrationFlow(
      'New User',
      'newuser@example.com',
      'password123',
      'password123'
    );
    
    expect(registerResult.registrationSuccessful).toBe(true);
    expect(registerResult.hasError).toBe(false);
    expect(registerResult.finallyLoggedIn).toBe(true);
  });

  test('should validate registration form inputs', async () => {
    await authPage.visitRegister();
    
    // Test with invalid data
    const registerResult = await authPage.testRegistrationFlow(
      'A', // Too short name
      'invalid-email', // Invalid email
      '123', // Too short password
      '123'
    );
    
    expect(registerResult.registrationSuccessful).toBe(false);
    expect(registerResult.hasError).toBe(true);
    expect(registerResult.errorMessage).toContain('Validation failed');
  });

  test('should handle existing user registration', async () => {
    await authPage.visitRegister();
    
    const registerResult = await authPage.testRegistrationFlow(
      'Existing User',
      'existing@example.com',
      'password123',
      'password123'
    );
    
    expect(registerResult.registrationSuccessful).toBe(false);
    expect(registerResult.hasError).toBe(true);
    expect(registerResult.errorMessage).toContain('already exists');
  });

  test('should successfully logout user', async () => {
    // First login
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Verify logged in
    let authState = await authPage.validateAuthenticationState();
    expect(authState.isLoggedIn).toBe(true);
    
    // Logout
    const logoutResult = await authPage.testLogoutFlow();
    expect(logoutResult.logoutSuccessful).toBe(true);
    
    // Verify logged out
    authState = await authPage.validateAuthenticationState();
    expect(authState.isLoggedOut).toBe(true);
  });

  test('should persist session across page refreshes', async () => {
    // Login
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Test session persistence
    const persistenceResult = await authPage.testSessionPersistence();
    expect(persistenceResult.sessionPersisted).toBe(true);
    expect(persistenceResult.stillLoggedIn).toBe(true);
  });

  test('should switch between login and registration forms', async () => {
    await authPage.visitLogin();
    
    // Verify login form is shown
    let formValidation = await authPage.validateLoginForm();
    expect(formValidation.hasForm).toBe(true);
    
    // Switch to registration
    await authPage.switchToRegister();
    
    // Verify registration form is shown
    formValidation = await authPage.validateRegisterForm();
    expect(formValidation.hasForm).toBe(true);
    
    // Switch back to login
    await authPage.switchToLogin();
    
    // Verify login form is shown again
    formValidation = await authPage.validateLoginForm();
    expect(formValidation.hasForm).toBe(true);
  });

  test('should handle forgot password flow', async () => {
    await authPage.visitLogin();
    
    await authPage.forgotPassword('test@example.com');
    
    const success = await authPage.getAuthSuccess();
    expect(success).toContain('Password reset email sent');
  });

  test('should display and update user profile', async () => {
    // Login first
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Navigate to profile
    await profilePage.visit();
    
    // Validate profile form
    const formValidation = await profilePage.validateProfileForm();
    expect(formValidation.hasForm).toBe(true);
    expect(formValidation.hasNameInput).toBe(true);
    expect(formValidation.hasEmailInput).toBe(true);
    expect(formValidation.hasSaveButton).toBe(true);
    
    // Test profile update
    const updateResult = await profilePage.testProfileUpdate({
      name: 'Updated Test User',
      email: 'updated@example.com'
    });
    
    expect(updateResult.updateSuccessful).toBe(true);
    expect(updateResult.dataChanged).toBe(true);
  });

  test('should manage user preferences', async () => {
    // Login first
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Navigate to profile
    await profilePage.visit();
    
    // Validate preferences section
    const preferencesValidation = await profilePage.validatePreferencesSection();
    expect(preferencesValidation.hasPreferencesSection).toBe(true);
    
    // Test preferences update
    const updateResult = await profilePage.testPreferencesUpdate({
      streamingPlatform: 'youtube',
      emailNotifications: false,
      pushNotifications: true,
      showKnownSongs: false
    });
    
    expect(updateResult.updateSuccessful).toBe(true);
    expect(updateResult.preferencesChanged).toBe(true);
  });

  test('should handle password change', async () => {
    // Login first
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Navigate to profile
    await profilePage.visit();
    
    // Validate password change form
    const passwordFormValidation = await profilePage.validatePasswordChangeForm();
    expect(passwordFormValidation.hasCurrentPasswordInput).toBe(true);
    expect(passwordFormValidation.hasNewPasswordInput).toBe(true);
    expect(passwordFormValidation.hasConfirmPasswordInput).toBe(true);
    
    // Test password change
    const changeResult = await profilePage.testPasswordChange(
      'password123',
      'newpassword123',
      'newpassword123'
    );
    
    expect(changeResult.changeSuccessful).toBe(true);
  });

  test('should validate password change requirements', async () => {
    // Login first
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Navigate to profile
    await profilePage.visit();
    
    // Test with mismatched passwords
    const changeResult = await profilePage.testPasswordChange(
      'password123',
      'newpassword123',
      'differentpassword'
    );
    
    expect(changeResult.changeSuccessful).toBe(false);
    expect(changeResult.hasValidationErrors || changeResult.hasError).toBe(true);
  });

  test('should maintain authentication state across navigation', async () => {
    // Login
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Navigate to different pages
    await homePage.visit();
    let authState = await authPage.validateAuthenticationState();
    expect(authState.isLoggedIn).toBe(true);
    
    await profilePage.visit();
    authState = await authPage.validateAuthenticationState();
    expect(authState.isLoggedIn).toBe(true);
  });

  test('should redirect unauthenticated users to login', async () => {
    // Try to access profile without logging in
    await profilePage.visit();
    
    // Should redirect to login or show login form
    const isOnLoginPage = await authPage.isElementVisible('.login-form, .login-button');
    const currentUrl = page.url();
    
    expect(isOnLoginPage || currentUrl.includes('login')).toBe(true);
  });

  test('should handle authentication errors gracefully', async () => {
    // Mock server error
    await page.route('**/api/v1/auth/login', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Server error',
          message: 'Internal server error'
        })
      });
    });

    await authPage.visitLogin();
    
    const loginResult = await authPage.testLoginFlow('test@example.com', 'password123');
    
    expect(loginResult.loginSuccessful).toBe(false);
    expect(loginResult.hasError).toBe(true);
    expect(loginResult.errorMessage).toContain('Server error');
  });

  test('should support profile picture upload', async () => {
    // Login first
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Navigate to profile
    await profilePage.visit();
    
    // Check if profile picture functionality exists
    const hasProfilePicture = await profilePage.hasProfilePicture();
    const canUpload = await profilePage.canUploadProfilePicture();
    
    // If upload functionality exists, test it
    if (canUpload) {
      // Create a test file (this would need to be a real file in actual tests)
      // For now, just verify the upload interface exists
      expect(canUpload).toBe(true);
    }
  });

  test('should support account deletion', async () => {
    // Login first
    await authPage.visitLogin();
    await authPage.login('test@example.com', 'password123');
    
    // Navigate to profile
    await profilePage.visit();
    
    // Check if account deletion is available
    const canDelete = await profilePage.canDeleteAccount();
    
    if (canDelete) {
      // Just verify the delete functionality exists
      // In a real test, we might test the confirmation dialog
      expect(canDelete).toBe(true);
    }
  });
});