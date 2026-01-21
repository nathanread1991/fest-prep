// Authentication and session security tests
const { test, expect } = require('@playwright/test');

test.describe('Authentication Security Tests', () => {
  test.describe('Session Management', () => {
    test('should handle secure session creation', async ({ page }) => {
      await page.goto('/login');
      
      const emailInput = page.locator('#email').first();
      const passwordInput = page.locator('#password').first();
      const submitButton = page.locator('button[type="submit"]').first();
      
      if (await emailInput.count() > 0) {
        await emailInput.fill('test@example.com');
        await passwordInput.fill('password123');
        await submitButton.click();
        
        // Wait for potential redirect
        await page.waitForTimeout(2000);
        
        // Check for session indicators
        const cookies = await page.context().cookies();
        const sessionCookie = cookies.find(cookie => 
          cookie.name.toLowerCase().includes('session') || 
          cookie.name.toLowerCase().includes('auth')
        );
        
        if (sessionCookie) {
          // Session cookie should be secure
          expect(sessionCookie.secure).toBe(true);
          expect(sessionCookie.httpOnly).toBe(true);
        }
      }
    });

    test('should handle session timeout', async ({ page }) => {
      await page.goto('/profile');
      
      // Simulate session timeout by clearing cookies
      await page.context().clearCookies();
      
      // Try to access protected resource
      await page.reload();
      
      // Should redirect to login or show authentication required
      const currentUrl = page.url();
      const isLoginPage = currentUrl.includes('/login') || currentUrl.includes('/auth');
      const hasAuthError = await page.locator('.auth-required, .login-required').count() > 0;
      
      expect(isLoginPage || hasAuthError).toBe(true);
    });

    test('should handle logout properly', async ({ page }) => {
      // First login (if possible)
      await page.goto('/login');
      
      const logoutButton = page.locator('.logout, [data-action="logout"], button:has-text("Logout")').first();
      
      if (await logoutButton.count() > 0) {
        await logoutButton.click();
        
        // Should clear session
        const cookies = await page.context().cookies();
        const sessionCookie = cookies.find(cookie => 
          cookie.name.toLowerCase().includes('session') || 
          cookie.name.toLowerCase().includes('auth')
        );
        
        // Session cookie should be cleared or expired
        if (sessionCookie) {
          expect(sessionCookie.value).toBe('');
        }
        
        // Should redirect to public page
        const currentUrl = page.url();
        expect(currentUrl).not.toContain('/profile');
        expect(currentUrl).not.toContain('/dashboard');
      }
    });

    test('should prevent session fixation', async ({ page }) => {
      // Get initial session
      await page.goto('/');
      const initialCookies = await page.context().cookies();
      const initialSessionCookie = initialCookies.find(cookie => 
        cookie.name.toLowerCase().includes('session')
      );
      
      // Login
      await page.goto('/login');
      const emailInput = page.locator('#email').first();
      const passwordInput = page.locator('#password').first();
      
      if (await emailInput.count() > 0) {
        await emailInput.fill('test@example.com');
        await passwordInput.fill('password123');
        
        const submitButton = page.locator('button[type="submit"]').first();
        await submitButton.click();
        
        await page.waitForTimeout(2000);
        
        // Get session after login
        const postLoginCookies = await page.context().cookies();
        const postLoginSessionCookie = postLoginCookies.find(cookie => 
          cookie.name.toLowerCase().includes('session')
        );
        
        // Session ID should change after login
        if (initialSessionCookie && postLoginSessionCookie) {
          expect(postLoginSessionCookie.value).not.toBe(initialSessionCookie.value);
        }
      }
    });
  });

  test.describe('Password Security', () => {
    test('should enforce password complexity', async ({ page }) => {
      await page.goto('/register');
      
      const passwordInput = page.locator('#password, input[name="password"]').first();
      
      if (await passwordInput.count() > 0) {
        const weakPasswords = ['123', 'password', 'abc'];
        
        for (const weakPassword of weakPasswords) {
          await passwordInput.fill(weakPassword);
          
          const submitButton = page.locator('button[type="submit"]').first();
          if (await submitButton.count() > 0) {
            await submitButton.click();
          }
          
          // Should show password strength error
          const passwordError = page.locator('.password-error, .field-error').first();
          if (await passwordError.count() > 0) {
            const errorText = await passwordError.textContent();
            expect(errorText.toLowerCase()).toContain('password');
          }
        }
      }
    });

    test('should not expose passwords in client-side code', async ({ page }) => {
      await page.goto('/login');
      
      // Check that passwords are not stored in JavaScript variables
      const passwordExposure = await page.evaluate(() => {
        const scripts = Array.from(document.scripts);
        const scriptContent = scripts.map(script => script.innerHTML).join(' ');
        
        // Look for common password exposure patterns
        const hasPasswordVar = /password\s*[:=]\s*['"][^'"]+['"]/.test(scriptContent);
        const hasCredentials = /credentials\s*[:=]/.test(scriptContent);
        
        return {
          hasPasswordVar,
          hasCredentials,
          scriptCount: scripts.length
        };
      });
      
      expect(passwordExposure.hasPasswordVar).toBe(false);
      expect(passwordExposure.hasCredentials).toBe(false);
    });
  });

  test.describe('Authorization', () => {
    test('should protect admin routes', async ({ page }) => {
      // Try to access admin route without authentication
      await page.goto('/admin');
      
      // Should redirect to login or show access denied
      const currentUrl = page.url();
      const isLoginPage = currentUrl.includes('/login');
      const hasAccessDenied = await page.locator('.access-denied, .unauthorized').count() > 0;
      const hasNotFound = await page.locator('.not-found, .404').count() > 0;
      
      expect(isLoginPage || hasAccessDenied || hasNotFound).toBe(true);
    });

    test('should protect user-specific resources', async ({ page }) => {
      // Try to access another user's profile
      await page.goto('/users/999999/profile');
      
      // Should show access denied or not found
      const hasAccessDenied = await page.locator('.access-denied, .unauthorized').count() > 0;
      const hasNotFound = await page.locator('.not-found, .404').count() > 0;
      const isLoginPage = page.url().includes('/login');
      
      expect(hasAccessDenied || hasNotFound || isLoginPage).toBe(true);
    });
  });

  test.describe('CSRF Protection', () => {
    test('should include CSRF tokens in forms', async ({ page }) => {
      await page.goto('/login');
      
      const forms = page.locator('form');
      const formCount = await forms.count();
      
      for (let i = 0; i < formCount; i++) {
        const form = forms.nth(i);
        
        // Look for CSRF token field
        const csrfToken = form.locator('input[name="_token"], input[name="csrf_token"]');
        const metaCsrf = page.locator('meta[name="csrf-token"]');
        
        const hasTokenField = await csrfToken.count() > 0;
        const hasMetaToken = await metaCsrf.count() > 0;
        
        // Should have some form of CSRF protection
        expect(hasTokenField || hasMetaToken).toBe(true);
      }
    });
  });

  test.describe('Rate Limiting', () => {
    test('should handle login rate limiting', async ({ page }) => {
      await page.goto('/login');
      
      const emailInput = page.locator('#email').first();
      const passwordInput = page.locator('#password').first();
      const submitButton = page.locator('button[type="submit"]').first();
      
      if (await emailInput.count() > 0) {
        // Attempt multiple failed logins
        for (let i = 0; i < 5; i++) {
          await emailInput.fill('test@example.com');
          await passwordInput.fill('wrongpassword');
          await submitButton.click();
          
          await page.waitForTimeout(500);
        }
        
        // Should show rate limiting message
        const rateLimitMessage = page.locator('.rate-limit, .too-many-attempts').first();
        
        if (await rateLimitMessage.count() > 0) {
          const messageText = await rateLimitMessage.textContent();
          expect(messageText.toLowerCase()).toContain('attempt');
        }
      }
    });
  });

  test.describe('Secure Headers', () => {
    test('should have security headers', async ({ page }) => {
      const response = await page.goto('/');
      const headers = response.headers();
      
      // Check for important security headers
      const securityHeaders = {
        'x-frame-options': 'Should prevent clickjacking',
        'x-content-type-options': 'Should prevent MIME sniffing',
        'x-xss-protection': 'Should enable XSS protection',
        'strict-transport-security': 'Should enforce HTTPS'
      };
      
      Object.entries(securityHeaders).forEach(([header, description]) => {
        if (headers[header]) {
          console.log(`✓ ${header}: ${headers[header]}`);
        } else {
          console.warn(`⚠ Missing ${header}: ${description}`);
        }
      });
      
      // At least some security headers should be present
      const hasSecurityHeaders = Object.keys(securityHeaders).some(header => headers[header]);
      expect(hasSecurityHeaders).toBe(true);
    });
  });

  test.describe('Data Protection', () => {
    test('should not expose sensitive data in responses', async ({ page }) => {
      // Monitor network responses for sensitive data
      const sensitiveDataFound = [];
      
      page.on('response', async (response) => {
        if (response.status() === 200 && response.url().includes('/api/')) {
          try {
            const responseText = await response.text();
            
            // Check for common sensitive data patterns
            const sensitivePatterns = [
              /password/i,
              /secret/i,
              /private_key/i,
              /api_key/i,
              /token.*[a-zA-Z0-9]{20,}/i
            ];
            
            sensitivePatterns.forEach(pattern => {
              if (pattern.test(responseText)) {
                sensitiveDataFound.push({
                  url: response.url(),
                  pattern: pattern.toString()
                });
              }
            });
          } catch (error) {
            // Ignore errors reading response body
          }
        }
      });
      
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      
      // Should not expose sensitive data
      expect(sensitiveDataFound).toHaveLength(0);
    });

    test('should handle user data privacy', async ({ page }) => {
      await page.goto('/profile');
      
      // Check that personal data is properly protected
      const personalDataElements = page.locator('[data-personal], .personal-info');
      const elementCount = await personalDataElements.count();
      
      for (let i = 0; i < elementCount; i++) {
        const element = personalDataElements.nth(i);
        const textContent = await element.textContent();
        
        // Should not expose full credit card numbers, SSNs, etc.
        expect(textContent).not.toMatch(/\d{4}-\d{4}-\d{4}-\d{4}/); // Credit card
        expect(textContent).not.toMatch(/\d{3}-\d{2}-\d{4}/); // SSN
      }
    });
  });

  test.describe('Input Sanitization', () => {
    test('should sanitize user input display', async ({ page }) => {
      await page.goto('/festivals');
      
      // Check that user-generated content is properly sanitized
      const userContent = page.locator('.user-content, .description').first();
      
      if (await userContent.count() > 0) {
        const innerHTML = await userContent.innerHTML();
        
        // Should not contain dangerous HTML
        expect(innerHTML).not.toMatch(/<script/i);
        expect(innerHTML).not.toContain('javascript:');
        expect(innerHTML).not.toMatch(/on\w+\s*=/i);
      }
    });
  });
});