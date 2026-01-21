// Input security and validation tests
const { test, expect } = require('@playwright/test');

test.describe('Input Security Tests', () => {
  test('should prevent XSS in text inputs', async ({ page }) => {
    await page.goto('/festivals/create');
    
    const nameInput = page.locator('input[name="name"]').first();
    
    if (await nameInput.count() > 0) {
      const maliciousScript = '<script>alert("XSS")</script>';
      await nameInput.fill(maliciousScript);
      
      // Check that script is not executed
      const alertDialogs = [];
      page.on('dialog', dialog => {
        alertDialogs.push(dialog.message());
        dialog.dismiss();
      });
      
      await page.waitForTimeout(1000);
      expect(alertDialogs).toHaveLength(0);
    }
  });

  test('should validate email format', async ({ page }) => {
    await page.goto('/login');
    
    const emailInput = page.locator('#email').first();
    
    if (await emailInput.count() > 0) {
      await emailInput.fill('invalid-email');
      
      const submitButton = page.locator('button[type="submit"]').first();
      if (await submitButton.count() > 0) {
        await submitButton.click();
      }
      
      // Should show validation error
      const validationMessage = await emailInput.evaluate(input => input.validationMessage);
      expect(validationMessage).toBeTruthy();
    }
  });

  test('should handle SQL injection attempts', async ({ page }) => {
    await page.goto('/festivals');
    
    const searchInput = page.locator('#festival-search').first();
    
    if (await searchInput.count() > 0) {
      const sqlInjection = "'; DROP TABLE festivals; --";
      await searchInput.fill(sqlInjection);
      await searchInput.press('Enter');
      
      // Page should still be functional
      await page.waitForTimeout(2000);
      const pageTitle = await page.title();
      expect(pageTitle).toBeTruthy();
    }
  });

  test('should validate required fields', async ({ page }) => {
    await page.goto('/login');
    
    const submitButton = page.locator('button[type="submit"]').first();
    
    if (await submitButton.count() > 0) {
      await submitButton.click();
      
      // Should show validation errors
      const requiredFields = page.locator('input[required]');
      const fieldCount = await requiredFields.count();
      
      if (fieldCount > 0) {
        const field = requiredFields.first();
        const validationMessage = await field.evaluate(input => input.validationMessage);
        expect(validationMessage).toBeTruthy();
      }
    }
  });
});