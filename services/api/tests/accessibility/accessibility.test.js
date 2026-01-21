// Accessibility compliance tests
const { test, expect } = require('@playwright/test');

test.describe('Accessibility Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.describe('Keyboard Navigation', () => {
    test('should support tab navigation through all interactive elements', async ({ page }) => {
      // Get all focusable elements
      const focusableElements = await page.locator('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])').all();
      
      if (focusableElements.length === 0) {
        // If no focusable elements found, check if page loaded correctly
        const bodyContent = await page.locator('body').textContent();
        if (!bodyContent || bodyContent.trim().length === 0) {
          test.skip('Page appears to be empty or not loaded');
        } else {
          test.skip('No focusable elements found on page');
        }
      }
      
      // Start from the first element
      await page.keyboard.press('Tab');
      
      for (let i = 0; i < Math.min(focusableElements.length, 10); i++) {
        const focusedElement = page.locator(':focus');
        
        // Check if any element has focus
        const hasFocus = await focusedElement.count() > 0;
        if (hasFocus) {
          await expect(focusedElement.first()).toBeVisible();
        }
        
        // Move to next element
        await page.keyboard.press('Tab');
      }
    });

    test('should support reverse tab navigation', async ({ page }) => {
      // Navigate to the end first
      const focusableElements = await page.locator('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])').all();
      
      if (focusableElements.length === 0) {
        test.skip('No focusable elements found on page');
      }
      
      // Tab to a few elements forward
      for (let i = 0; i < Math.min(3, focusableElements.length); i++) {
        await page.keyboard.press('Tab');
      }
      
      // Then tab backward
      await page.keyboard.press('Shift+Tab');
      const focusedElement = page.locator(':focus');
      
      const hasFocus = await focusedElement.count() > 0;
      if (hasFocus) {
        await expect(focusedElement.first()).toBeVisible();
      }
    });

    test('should support Enter key activation for buttons', async ({ page }) => {
      const buttons = page.locator('button:visible, [role="button"]:visible');
      const buttonCount = await buttons.count();
      
      if (buttonCount > 0) {
        const firstButton = buttons.first();
        await firstButton.focus();
        
        // Listen for click events
        let buttonClicked = false;
        await page.evaluate(() => {
          window.testButtonClicked = false;
          document.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON' || e.target.getAttribute('role') === 'button') {
              window.testButtonClicked = true;
            }
          });
        });
        
        await page.keyboard.press('Enter');
        
        const clicked = await page.evaluate(() => window.testButtonClicked);
        expect(clicked).toBe(true);
      } else {
        test.skip('No buttons found on page');
      }
    });

    test('should support Space key activation for buttons', async ({ page }) => {
      const buttons = page.locator('button:visible, [role="button"]:visible');
      const buttonCount = await buttons.count();
      
      if (buttonCount > 0) {
        const firstButton = buttons.first();
        await firstButton.focus();
        
        // Listen for click events
        await page.evaluate(() => {
          window.testSpaceClicked = false;
          document.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON' || e.target.getAttribute('role') === 'button') {
              window.testSpaceClicked = true;
            }
          });
        });
        
        await page.keyboard.press('Space');
        
        const clicked = await page.evaluate(() => window.testSpaceClicked);
        expect(clicked).toBe(true);
      } else {
        test.skip('No buttons found on page');
      }
    });

    test('should support arrow key navigation in menus', async ({ page }) => {
      // Test navigation menu if present
      const navMenu = page.locator('.nav-menu, [role="menu"], [role="menubar"], nav ul');
      
      if (await navMenu.count() > 0 && await navMenu.first().isVisible()) {
        const menuItems = navMenu.first().locator('a, button, [role="menuitem"]');
        const itemCount = await menuItems.count();
        
        if (itemCount > 1) {
          await menuItems.first().focus();
          
          // Test arrow down
          await page.keyboard.press('ArrowDown');
          const focusedAfterDown = page.locator(':focus');
          
          // Should focus on next item (implementation dependent)
          const hasFocus = await focusedAfterDown.count() > 0;
          if (hasFocus) {
            await expect(focusedAfterDown.first()).toBeVisible();
          }
        }
      } else {
        test.skip('No navigation menu found on page');
      }
    });

    test('should support Escape key to close modals/dropdowns', async ({ page }) => {
      // Look for modal triggers
      const modalTriggers = page.locator('[data-modal], [aria-haspopup="dialog"], .modal-trigger, [data-testid*="modal"]');
      const modalCount = await modalTriggers.count();
      
      if (modalCount > 0) {
        const trigger = modalTriggers.first();
        await trigger.click();
        
        // Wait for modal to appear
        await page.waitForTimeout(500);
        
        const modal = page.locator('[role="dialog"], .modal:visible, [data-testid*="modal"]:visible');
        if (await modal.count() > 0 && await modal.first().isVisible()) {
          await page.keyboard.press('Escape');
          
          // Wait for modal to close
          await page.waitForTimeout(500);
          
          // Modal should be closed or hidden
          const isStillVisible = await modal.first().isVisible().catch(() => false);
          expect(isStillVisible).toBe(false);
        }
      } else {
        test.skip('No modal triggers found on page');
      }
    });
  });

  test.describe('Screen Reader Support', () => {
    test('should have proper heading hierarchy', async ({ page }) => {
      const headings = await page.locator('h1, h2, h3, h4, h5, h6').all();
      
      if (headings.length === 0) {
        test.skip('No headings found on page');
      }
      
      // Should have at least one h1
      const h1Count = await page.locator('h1').count();
      expect(h1Count).toBeGreaterThanOrEqual(1);
      
      // Check heading levels don't skip
      const headingLevels = [];
      for (const heading of headings) {
        const tagName = await heading.evaluate(el => el.tagName.toLowerCase());
        const level = parseInt(tagName.charAt(1));
        headingLevels.push(level);
      }
      
      // First heading should be h1
      expect(headingLevels[0]).toBe(1);
      
      // Check for proper nesting (no skipping levels)
      for (let i = 1; i < headingLevels.length; i++) {
        const currentLevel = headingLevels[i];
        const previousLevel = headingLevels[i - 1];
        
        // Should not skip more than one level
        if (currentLevel > previousLevel) {
          expect(currentLevel - previousLevel).toBeLessThanOrEqual(1);
        }
      }
    });

    test('should have proper ARIA labels and descriptions', async ({ page }) => {
      // Check for ARIA labels on interactive elements
      const interactiveElements = page.locator('button, input, select, textarea, [role="button"], [role="link"], [role="tab"], [role="menuitem"]');
      const elementCount = await interactiveElements.count();
      
      if (elementCount === 0) {
        test.skip('No interactive elements found on page');
      }
      
      for (let i = 0; i < Math.min(elementCount, 10); i++) {
        const element = interactiveElements.nth(i);
        
        const hasAriaLabel = await element.getAttribute('aria-label');
        const hasAriaLabelledBy = await element.getAttribute('aria-labelledby');
        const hasAriaDescribedBy = await element.getAttribute('aria-describedby');
        const hasTitle = await element.getAttribute('title');
        const textContent = await element.textContent();
        const hasPlaceholder = await element.getAttribute('placeholder');
        
        // Element should have some form of accessible name
        const hasAccessibleName = hasAriaLabel || hasAriaLabelledBy || hasTitle || hasPlaceholder || (textContent && textContent.trim().length > 0);
        
        if (!hasAccessibleName) {
          const tagName = await element.evaluate(el => el.tagName.toLowerCase());
          const role = await element.getAttribute('role');
          console.warn(`Element ${tagName}${role ? `[role="${role}"]` : ''} lacks accessible name`);
        }
        
        expect(hasAccessibleName).toBe(true);
      }
    });

    test('should have proper form labels', async ({ page }) => {
      const inputs = page.locator('input, select, textarea');
      const inputCount = await inputs.count();
      
      if (inputCount === 0) {
        test.skip('No form inputs found on page');
      }
      
      for (let i = 0; i < inputCount; i++) {
        const input = inputs.nth(i);
        const inputId = await input.getAttribute('id');
        const inputType = await input.getAttribute('type');
        
        // Skip hidden inputs
        if (inputType === 'hidden') continue;
        
        let hasAccessibleLabel = false;
        
        if (inputId) {
          // Check for associated label
          const label = page.locator(`label[for="${inputId}"]`);
          const hasLabel = await label.count() > 0;
          hasAccessibleLabel = hasLabel;
        }
        
        // Check for ARIA labels
        const hasAriaLabel = await input.getAttribute('aria-label');
        const hasAriaLabelledBy = await input.getAttribute('aria-labelledby');
        const hasPlaceholder = await input.getAttribute('placeholder');
        
        // Input should have a label or ARIA label
        hasAccessibleLabel = hasAccessibleLabel || hasAriaLabel || hasAriaLabelledBy || hasPlaceholder;
        
        if (!hasAccessibleLabel) {
          const inputName = await input.getAttribute('name') || 'unnamed';
          console.warn(`Input field "${inputName}" lacks accessible label`);
        }
        
        expect(hasAccessibleLabel).toBe(true);
      }
    });

    test('should have proper ARIA roles for custom components', async ({ page }) => {
      // Check for proper roles on custom interactive elements
      const customButtons = page.locator('[role="button"]:not(button)');
      const customButtonCount = await customButtons.count();
      
      for (let i = 0; i < customButtonCount; i++) {
        const customButton = customButtons.nth(i);
        
        // Should have tabindex
        const tabindex = await customButton.getAttribute('tabindex');
        expect(tabindex).not.toBeNull();
        expect(parseInt(tabindex)).toBeGreaterThanOrEqual(0);
      }
      
      // Check for proper roles on navigation
      const navigation = page.locator('nav, [role="navigation"]');
      if (await navigation.count() > 0) {
        const nav = navigation.first();
        const role = await nav.getAttribute('role');
        const tagName = await nav.evaluate(el => el.tagName.toLowerCase());
        
        // Should be nav element or have navigation role
        const hasProperRole = tagName === 'nav' || role === 'navigation';
        expect(hasProperRole).toBe(true);
      }
      
      // Check for proper landmark roles
      const landmarks = page.locator('[role="main"], [role="banner"], [role="contentinfo"], [role="complementary"], main, header, footer, aside');
      const landmarkCount = await landmarks.count();
      
      if (landmarkCount > 0) {
        for (let i = 0; i < landmarkCount; i++) {
          const landmark = landmarks.nth(i);
          const role = await landmark.getAttribute('role');
          const tagName = await landmark.evaluate(el => el.tagName.toLowerCase());
          
          // Verify semantic HTML or proper ARIA roles
          const semanticTags = ['main', 'header', 'footer', 'aside', 'nav', 'section'];
          const landmarkRoles = ['main', 'banner', 'contentinfo', 'complementary', 'navigation'];
          
          const hasProperLandmark = semanticTags.includes(tagName) || landmarkRoles.includes(role);
          expect(hasProperLandmark).toBe(true);
        }
      }
    });

    test('should have proper live regions for dynamic content', async ({ page }) => {
      // Look for elements that might contain dynamic content
      const liveRegions = page.locator('[aria-live], [role="status"], [role="alert"], [role="log"]');
      const liveRegionCount = await liveRegions.count();
      
      if (liveRegionCount > 0) {
        for (let i = 0; i < liveRegionCount; i++) {
          const region = liveRegions.nth(i);
          const ariaLive = await region.getAttribute('aria-live');
          const role = await region.getAttribute('role');
          
          // Should have appropriate live region settings
          const hasProperLiveRegion = ariaLive || ['status', 'alert', 'log'].includes(role);
          expect(hasProperLiveRegion).toBe(true);
          
          // If aria-live is present, should have valid values
          if (ariaLive) {
            expect(['polite', 'assertive', 'off']).toContain(ariaLive);
          }
        }
      }
      
      // Check for notification areas
      const notifications = page.locator('.notification, .alert, .toast, [data-testid*="notification"]');
      const notificationCount = await notifications.count();
      
      if (notificationCount > 0) {
        for (let i = 0; i < notificationCount; i++) {
          const notification = notifications.nth(i);
          const ariaLive = await notification.getAttribute('aria-live');
          const role = await notification.getAttribute('role');
          
          // Notifications should be announced to screen readers
          const hasLiveRegion = ariaLive || ['alert', 'status'].includes(role);
          if (!hasLiveRegion) {
            console.warn('Notification element lacks live region attributes');
          }
        }
      }
    });

    test('should have proper table accessibility', async ({ page }) => {
      const tables = page.locator('table');
      const tableCount = await tables.count();
      
      if (tableCount === 0) {
        test.skip('No tables found on page');
      }
      
      for (let i = 0; i < tableCount; i++) {
        const table = tables.nth(i);
        
        // Check for table caption or aria-label
        const caption = table.locator('caption');
        const hasCaption = await caption.count() > 0;
        const ariaLabel = await table.getAttribute('aria-label');
        const ariaLabelledBy = await table.getAttribute('aria-labelledby');
        
        const hasAccessibleName = hasCaption || ariaLabel || ariaLabelledBy;
        expect(hasAccessibleName).toBe(true);
        
        // Check for proper header structure
        const headers = table.locator('th');
        const headerCount = await headers.count();
        
        if (headerCount > 0) {
          for (let j = 0; j < headerCount; j++) {
            const header = headers.nth(j);
            const scope = await header.getAttribute('scope');
            
            // Headers should have scope attribute for complex tables
            if (headerCount > 1) {
              expect(['col', 'row', 'colgroup', 'rowgroup']).toContain(scope);
            }
          }
        }
      }
    });
  });

  test.describe('Color Contrast and Visual Accessibility', () => {
    test('should have sufficient color contrast for text', async ({ page }) => {
      // Get all text elements
      const textElements = page.locator('p, h1, h2, h3, h4, h5, h6, span, div, a, button, label, li');
      const elementCount = await textElements.count();
      
      if (elementCount === 0) {
        test.skip('No text elements found on page');
      }
      
      for (let i = 0; i < Math.min(elementCount, 20); i++) {
        const element = textElements.nth(i);
        
        if (await element.isVisible()) {
          const styles = await element.evaluate(el => {
            const computed = window.getComputedStyle(el);
            return {
              color: computed.color,
              backgroundColor: computed.backgroundColor,
              fontSize: parseFloat(computed.fontSize)
            };
          });
          
          // This is a simplified contrast check
          // In a real implementation, you'd use a proper contrast calculation
          const hasText = await element.textContent();
          if (hasText && hasText.trim().length > 0) {
            // Ensure text is not transparent
            expect(styles.color).not.toBe('rgba(0, 0, 0, 0)');
            expect(styles.color).not.toBe('transparent');
            
            // Check for common accessibility issues
            const isLightGray = styles.color.includes('rgb(128, 128, 128)') || styles.color.includes('#808080');
            const hasWhiteBackground = styles.backgroundColor.includes('rgb(255, 255, 255)') || styles.backgroundColor.includes('#ffffff');
            
            // Light gray on white background is often insufficient contrast
            if (isLightGray && hasWhiteBackground) {
              console.warn(`Potential low contrast: light gray text on white background`);
            }
          }
        }
      }
    });

    test('should not rely solely on color for information', async ({ page }) => {
      // Check for error messages that might rely only on color
      const errorElements = page.locator('.error, .danger, [aria-invalid="true"], .warning, .success');
      const errorCount = await errorElements.count();
      
      for (let i = 0; i < errorCount; i++) {
        const errorElement = errorElements.nth(i);
        
        if (await errorElement.isVisible()) {
          const textContent = await errorElement.textContent();
          const hasIcon = await errorElement.locator('svg, i, .icon, [data-icon]').count() > 0;
          const hasAriaLabel = await errorElement.getAttribute('aria-label');
          const hasAriaDescribedBy = await errorElement.getAttribute('aria-describedby');
          
          // Error should have text content, icon, or ARIA label
          const hasNonColorIndicator = (textContent && textContent.trim().length > 0) || hasIcon || hasAriaLabel || hasAriaDescribedBy;
          
          if (!hasNonColorIndicator) {
            const className = await errorElement.getAttribute('class') || 'unknown';
            console.warn(`Element with class "${className}" may rely solely on color`);
          }
          
          expect(hasNonColorIndicator).toBe(true);
        }
      }
      
      // Check for required form fields
      const requiredFields = page.locator('[required], [aria-required="true"], .required');
      const requiredCount = await requiredFields.count();
      
      for (let i = 0; i < requiredCount; i++) {
        const field = requiredFields.nth(i);
        
        if (await field.isVisible()) {
          const hasAsterisk = await page.locator('*').filter({ hasText: '*' }).count() > 0;
          const hasAriaRequired = await field.getAttribute('aria-required');
          const hasRequiredAttribute = await field.getAttribute('required');
          const hasRequiredLabel = await field.evaluate(el => {
            const id = el.id;
            if (id) {
              const label = document.querySelector(`label[for="${id}"]`);
              return label && (label.textContent.includes('*') || label.textContent.toLowerCase().includes('required'));
            }
            return false;
          });
          
          // Required fields should have non-color indicators
          const hasNonColorRequiredIndicator = hasAsterisk || hasAriaRequired === 'true' || hasRequiredAttribute !== null || hasRequiredLabel;
          expect(hasNonColorRequiredIndicator).toBe(true);
        }
      }
    });

    test('should support high contrast mode', async ({ page }) => {
      // Test with forced colors (simulating high contrast mode)
      await page.emulateMedia({ colorScheme: 'dark', forcedColors: 'active' });
      
      // Check that content is still visible
      const mainContent = page.locator('main, .main-content, body');
      await expect(mainContent.first()).toBeVisible();
      
      // Check that interactive elements are still distinguishable
      const buttons = page.locator('button:visible, [role="button"]:visible');
      const buttonCount = await buttons.count();
      
      if (buttonCount > 0) {
        const button = buttons.first();
        await expect(button).toBeVisible();
        
        // Button should have some form of border or background
        const styles = await button.evaluate(el => {
          const computed = window.getComputedStyle(el);
          return {
            border: computed.border,
            backgroundColor: computed.backgroundColor,
            outline: computed.outline,
            borderWidth: computed.borderWidth
          };
        });
        
        const hasBorder = styles.border !== 'none' && styles.border !== '0px none' && styles.borderWidth !== '0px';
        const hasBackground = styles.backgroundColor !== 'rgba(0, 0, 0, 0)' && styles.backgroundColor !== 'transparent';
        const hasOutline = styles.outline !== 'none' && styles.outline !== '0px none';
        
        expect(hasBorder || hasBackground || hasOutline).toBe(true);
      }
      
      // Reset media emulation
      await page.emulateMedia({ colorScheme: 'light', forcedColors: 'none' });
    });

    test('should have proper focus indicators', async ({ page }) => {
      const focusableElements = page.locator('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])');
      const elementCount = await focusableElements.count();
      
      if (elementCount === 0) {
        test.skip('No focusable elements found on page');
      }
      
      for (let i = 0; i < Math.min(elementCount, 5); i++) {
        const element = focusableElements.nth(i);
        
        if (await element.isVisible()) {
          await element.focus();
          
          // Check for focus styles
          const focusStyles = await element.evaluate(el => {
            const computed = window.getComputedStyle(el);
            return {
              outline: computed.outline,
              outlineWidth: computed.outlineWidth,
              outlineStyle: computed.outlineStyle,
              boxShadow: computed.boxShadow,
              border: computed.border,
              borderColor: computed.borderColor
            };
          });
          
          // Should have some form of focus indicator
          const hasOutline = focusStyles.outline !== 'none' && focusStyles.outlineWidth !== '0px';
          const hasBoxShadow = focusStyles.boxShadow !== 'none' && !focusStyles.boxShadow.includes('rgba(0, 0, 0, 0)');
          const hasBorderChange = focusStyles.border !== 'none' && focusStyles.borderColor !== 'transparent';
          
          const hasFocusIndicator = hasOutline || hasBoxShadow || hasBorderChange;
          
          if (!hasFocusIndicator) {
            const tagName = await element.evaluate(el => el.tagName.toLowerCase());
            console.warn(`${tagName} element lacks visible focus indicator`);
          }
          
          expect(hasFocusIndicator).toBe(true);
        }
      }
    });

    test('should have adequate text size and spacing', async ({ page }) => {
      const textElements = page.locator('p, span, div, a, button, label, li');
      const elementCount = await textElements.count();
      
      if (elementCount === 0) {
        test.skip('No text elements found on page');
      }
      
      for (let i = 0; i < Math.min(elementCount, 10); i++) {
        const element = textElements.nth(i);
        
        if (await element.isVisible()) {
          const hasText = await element.textContent();
          
          if (hasText && hasText.trim().length > 0) {
            const styles = await element.evaluate(el => {
              const computed = window.getComputedStyle(el);
              return {
                fontSize: parseFloat(computed.fontSize),
                lineHeight: parseFloat(computed.lineHeight),
                letterSpacing: computed.letterSpacing
              };
            });
            
            // Minimum font size should be 12px for body text
            expect(styles.fontSize).toBeGreaterThanOrEqual(12);
            
            // Line height should be at least 1.2 times font size
            if (styles.lineHeight > 0) {
              expect(styles.lineHeight).toBeGreaterThanOrEqual(styles.fontSize * 1.2);
            }
          }
        }
      }
    });
  });

  test.describe('Focus Management', () => {
    test('should have visible focus indicators', async ({ page }) => {
      const focusableElements = page.locator('button, input, select, textarea, a[href], [role="button"], [role="link"], [tabindex]:not([tabindex="-1"])');
      const elementCount = await focusableElements.count();
      
      if (elementCount === 0) {
        test.skip('No focusable elements found on page');
      }
      
      for (let i = 0; i < Math.min(elementCount, 5); i++) {
        const element = focusableElements.nth(i);
        
        if (await element.isVisible()) {
          // Get styles before focus
          const beforeFocusStyles = await element.evaluate(el => {
            const computed = window.getComputedStyle(el);
            return {
              outline: computed.outline,
              boxShadow: computed.boxShadow,
              borderColor: computed.borderColor
            };
          });
          
          await element.focus();
          
          // Get styles after focus
          const afterFocusStyles = await element.evaluate(el => {
            const computed = window.getComputedStyle(el);
            return {
              outline: computed.outline,
              outlineWidth: computed.outlineWidth,
              outlineStyle: computed.outlineStyle,
              boxShadow: computed.boxShadow,
              border: computed.border,
              borderColor: computed.borderColor
            };
          });
          
          // Should have some form of focus indicator
          const hasOutline = afterFocusStyles.outline !== 'none' && afterFocusStyles.outlineWidth !== '0px';
          const hasBoxShadow = afterFocusStyles.boxShadow !== 'none' && afterFocusStyles.boxShadow !== beforeFocusStyles.boxShadow;
          const hasBorderChange = afterFocusStyles.borderColor !== beforeFocusStyles.borderColor;
          
          const hasFocusIndicator = hasOutline || hasBoxShadow || hasBorderChange;
          
          if (!hasFocusIndicator) {
            const tagName = await element.evaluate(el => el.tagName.toLowerCase());
            const role = await element.getAttribute('role');
            console.warn(`${tagName}${role ? `[role="${role}"]` : ''} element lacks visible focus indicator`);
          }
          
          expect(hasFocusIndicator).toBe(true);
        }
      }
    });

    test('should manage focus in modals', async ({ page }) => {
      // Look for modal triggers
      const modalTriggers = page.locator('[data-modal], [aria-haspopup="dialog"], .modal-trigger, [data-testid*="modal"]');
      const triggerCount = await modalTriggers.count();
      
      if (triggerCount > 0) {
        const trigger = modalTriggers.first();
        await trigger.focus();
        await trigger.click();
        
        // Wait for modal
        await page.waitForTimeout(500);
        
        const modal = page.locator('[role="dialog"], .modal:visible, [data-testid*="modal"]:visible');
        if (await modal.count() > 0 && await modal.first().isVisible()) {
          // Focus should be trapped in modal
          const focusableInModal = modal.first().locator('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])');
          const modalFocusableCount = await focusableInModal.count();
          
          if (modalFocusableCount > 0) {
            // Check if focus is within modal
            const focusedElement = page.locator(':focus');
            const focusedCount = await focusedElement.count();
            
            if (focusedCount > 0) {
              const isWithinModal = await modal.first().locator(':focus').count() > 0;
              expect(isWithinModal).toBe(true);
            }
          }
        }
      } else {
        test.skip('No modal triggers found on page');
      }
    });

    test('should restore focus after modal closes', async ({ page }) => {
      const modalTriggers = page.locator('[data-modal], [aria-haspopup="dialog"], .modal-trigger, [data-testid*="modal"]');
      const triggerCount = await modalTriggers.count();
      
      if (triggerCount > 0) {
        const trigger = modalTriggers.first();
        await trigger.focus();
        
        // Verify trigger has focus
        const triggerHasFocus = await trigger.evaluate(el => document.activeElement === el);
        
        await trigger.click();
        
        // Wait for modal
        await page.waitForTimeout(500);
        
        const modal = page.locator('[role="dialog"], .modal:visible, [data-testid*="modal"]:visible');
        if (await modal.count() > 0 && await modal.first().isVisible()) {
          // Close modal (ESC key)
          await page.keyboard.press('Escape');
          
          // Wait for modal to close
          await page.waitForTimeout(500);
          
          // Focus should return to trigger (if it was focused before)
          if (triggerHasFocus) {
            const focusReturnedToTrigger = await trigger.evaluate(el => document.activeElement === el);
            expect(focusReturnedToTrigger).toBe(true);
          }
        }
      } else {
        test.skip('No modal triggers found on page');
      }
    });

    test('should handle focus for dynamic content', async ({ page }) => {
      // Look for elements that might add dynamic content
      const dynamicTriggers = page.locator('[data-toggle], [aria-expanded], .accordion-trigger, .dropdown-toggle');
      const triggerCount = await dynamicTriggers.count();
      
      if (triggerCount > 0) {
        const trigger = dynamicTriggers.first();
        
        if (await trigger.isVisible()) {
          await trigger.focus();
          await trigger.click();
          
          // Wait for content to appear
          await page.waitForTimeout(300);
          
          // Check if aria-expanded changed
          const ariaExpanded = await trigger.getAttribute('aria-expanded');
          if (ariaExpanded === 'true') {
            // Content should be accessible
            const expandedContent = page.locator('[aria-expanded="true"] + *, [aria-expanded="true"] ~ *').first();
            if (await expandedContent.count() > 0) {
              await expect(expandedContent).toBeVisible();
            }
          }
        }
      } else {
        test.skip('No dynamic content triggers found on page');
      }
    });

    test('should maintain logical tab order', async ({ page }) => {
      const focusableElements = page.locator('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])');
      const elementCount = await focusableElements.count();
      
      if (elementCount < 2) {
        test.skip('Need at least 2 focusable elements to test tab order');
      }
      
      // Test tab order for first few elements
      const elementsToTest = Math.min(elementCount, 5);
      const positions = [];
      
      for (let i = 0; i < elementsToTest; i++) {
        const element = focusableElements.nth(i);
        
        if (await element.isVisible()) {
          const boundingBox = await element.boundingBox();
          if (boundingBox) {
            positions.push({
              index: i,
              x: boundingBox.x,
              y: boundingBox.y
            });
          }
        }
      }
      
      // Check if elements are in logical visual order (top to bottom, left to right)
      for (let i = 1; i < positions.length; i++) {
        const current = positions[i];
        const previous = positions[i - 1];
        
        // Current element should be below or to the right of previous
        const isLogicalOrder = current.y > previous.y || (current.y === previous.y && current.x >= previous.x);
        
        if (!isLogicalOrder) {
          console.warn(`Tab order may not follow visual order: element ${current.index} appears before element ${previous.index} visually`);
        }
      }
    });

    test('should skip hidden elements in tab order', async ({ page }) => {
      // Create a hidden element to test
      await page.evaluate(() => {
        const hiddenButton = document.createElement('button');
        hiddenButton.textContent = 'Hidden Button';
        hiddenButton.style.display = 'none';
        hiddenButton.id = 'test-hidden-button';
        document.body.appendChild(hiddenButton);
      });
      
      const hiddenButton = page.locator('#test-hidden-button');
      
      // Tab through elements
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');
      
      // Hidden button should not receive focus
      const hiddenButtonHasFocus = await hiddenButton.evaluate(el => document.activeElement === el);
      expect(hiddenButtonHasFocus).toBe(false);
      
      // Clean up
      await page.evaluate(() => {
        const element = document.getElementById('test-hidden-button');
        if (element) element.remove();
      });
    });
  });

  test.describe('Alternative Text and Media', () => {
    test('should have alt text for all images', async ({ page }) => {
      const images = page.locator('img');
      const imageCount = await images.count();
      
      for (let i = 0; i < imageCount; i++) {
        const image = images.nth(i);
        const alt = await image.getAttribute('alt');
        const role = await image.getAttribute('role');
        
        // Image should have alt attribute (can be empty for decorative images)
        expect(alt).not.toBeNull();
        
        // If role is presentation, alt can be empty
        if (role === 'presentation' || role === 'none') {
          expect(alt).toBe('');
        }
      }
    });

    test('should have captions or transcripts for video content', async ({ page }) => {
      const videos = page.locator('video');
      const videoCount = await videos.count();
      
      for (let i = 0; i < videoCount; i++) {
        const video = videos.nth(i);
        
        // Check for track elements (captions/subtitles)
        const tracks = video.locator('track');
        const trackCount = await tracks.count();
        
        if (trackCount > 0) {
          const track = tracks.first();
          const kind = await track.getAttribute('kind');
          const src = await track.getAttribute('src');
          
          expect(['captions', 'subtitles', 'descriptions']).toContain(kind);
          expect(src).not.toBeNull();
        }
      }
    });
  });

  test.describe('Error Handling and Feedback', () => {
    test('should provide accessible error messages', async ({ page }) => {
      await page.goto('/login');
      
      // Try to submit form without filling required fields
      const submitButton = page.locator('button[type="submit"], input[type="submit"]');
      if (await submitButton.count() > 0) {
        await submitButton.first().click();
        
        // Wait for validation
        await page.waitForTimeout(1000);
        
        // Check for error messages
        const errorMessages = page.locator('.error, [role="alert"], [aria-invalid="true"]');
        const errorCount = await errorMessages.count();
        
        if (errorCount > 0) {
          for (let i = 0; i < errorCount; i++) {
            const error = errorMessages.nth(i);
            
            // Error should be visible
            await expect(error).toBeVisible();
            
            // Error should have text content
            const errorText = await error.textContent();
            expect(errorText).toBeTruthy();
            expect(errorText.trim().length).toBeGreaterThan(0);
            
            // Check if error is associated with a form field
            const ariaDescribedBy = await error.getAttribute('aria-describedby');
            const id = await error.getAttribute('id');
            
            if (id) {
              // Look for form field that references this error
              const associatedField = page.locator(`[aria-describedby*="${id}"]`);
              const fieldCount = await associatedField.count();
              
              if (fieldCount > 0) {
                // Field should be marked as invalid
                const ariaInvalid = await associatedField.first().getAttribute('aria-invalid');
                expect(ariaInvalid).toBe('true');
              }
            }
          }
        }
      }
    });

    test('should provide success feedback', async ({ page }) => {
      // Look for success messages or notifications
      const successElements = page.locator('.success, [role="status"], .notification-success');
      const successCount = await successElements.count();
      
      if (successCount > 0) {
        for (let i = 0; i < successCount; i++) {
          const success = successElements.nth(i);
          
          if (await success.isVisible()) {
            // Success message should have text content
            const successText = await success.textContent();
            expect(successText).toBeTruthy();
            expect(successText.trim().length).toBeGreaterThan(0);
            
            // Should have appropriate ARIA role
            const role = await success.getAttribute('role');
            const ariaLive = await success.getAttribute('aria-live');
            
            const hasProperRole = role === 'status' || role === 'alert' || ariaLive;
            expect(hasProperRole).toBe(true);
          }
        }
      }
    });
  });

  test.describe('Mobile Accessibility', () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
    });

    test('should have appropriate touch targets', async ({ page }) => {
      const touchTargets = page.locator('button, a, input, select, textarea, [role="button"], [role="link"]');
      const targetCount = await touchTargets.count();
      
      for (let i = 0; i < Math.min(targetCount, 10); i++) {
        const target = touchTargets.nth(i);
        
        if (await target.isVisible()) {
          const boundingBox = await target.boundingBox();
          
          // Touch targets should be at least 44x44 pixels
          expect(boundingBox.width).toBeGreaterThanOrEqual(44);
          expect(boundingBox.height).toBeGreaterThanOrEqual(44);
        }
      }
    });

    test('should support screen reader gestures', async ({ page }) => {
      // This is a simplified test - real screen reader testing requires actual AT
      const headings = page.locator('h1, h2, h3, h4, h5, h6');
      const headingCount = await headings.count();
      
      if (headingCount > 0) {
        // Headings should be properly structured for navigation
        for (let i = 0; i < headingCount; i++) {
          const heading = headings.nth(i);
          const headingText = await heading.textContent();
          
          expect(headingText).toBeTruthy();
          expect(headingText.trim().length).toBeGreaterThan(0);
        }
      }
    });
  });
});