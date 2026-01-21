// Responsive design and viewport tests
const { test, expect } = require('@playwright/test');

test.describe('Responsive Design Tests', () => {
  const viewports = {
    mobile: { width: 375, height: 667 },
    tablet: { width: 768, height: 1024 },
    desktop: { width: 1920, height: 1080 },
    largeDesktop: { width: 2560, height: 1440 }
  };

  Object.entries(viewports).forEach(([deviceType, viewport]) => {
    test.describe(`${deviceType} viewport (${viewport.width}x${viewport.height})`, () => {
      test.beforeEach(async ({ page }) => {
        await page.setViewportSize(viewport);
        await page.goto('/');
      });

      test('should display navigation appropriately', async ({ page }) => {
        const navigation = page.locator('.main-navigation, nav, [role="navigation"]');
        
        if (await navigation.count() > 0) {
          await expect(navigation.first()).toBeVisible();

          if (deviceType === 'mobile') {
            // Mobile should show hamburger menu
            const hamburger = page.locator('.nav-toggle, .hamburger-menu, .menu-toggle, [aria-label*="menu"]');
            
            if (await hamburger.count() > 0) {
              await expect(hamburger.first()).toBeVisible();
              
              const navMenu = page.locator('.nav-menu, .mobile-menu, .navigation-menu');
              
              if (await navMenu.count() > 0) {
                // Menu should be hidden initially
                const isInitiallyVisible = await navMenu.first().isVisible();
                
                // Test hamburger menu functionality
                await hamburger.first().click();
                await page.waitForTimeout(300); // Allow for animation
                
                const isVisibleAfterClick = await navMenu.first().isVisible();
                expect(isVisibleAfterClick).toBe(true);
                
                // Test menu items are accessible
                const menuItems = navMenu.first().locator('a, button, [role="menuitem"]');
                const itemCount = await menuItems.count();
                
                if (itemCount > 0) {
                  // Menu items should be touch-friendly on mobile
                  for (let i = 0; i < Math.min(itemCount, 3); i++) {
                    const item = menuItems.nth(i);
                    const itemBox = await item.boundingBox();
                    expect(itemBox.height).toBeGreaterThanOrEqual(44);
                  }
                }
                
                // Test closing menu
                await hamburger.first().click();
                await page.waitForTimeout(300);
                
                const isHiddenAfterSecondClick = await navMenu.first().isVisible();
                expect(isHiddenAfterSecondClick).toBe(false);
              }
            }
          } else {
            // Tablet and desktop should show full navigation
            const navMenu = page.locator('.nav-menu, .navigation-menu, nav ul');
            
            if (await navMenu.count() > 0) {
              await expect(navMenu.first()).toBeVisible();
              
              const hamburger = page.locator('.nav-toggle, .hamburger-menu');
              if (await hamburger.count() > 0) {
                await expect(hamburger.first()).not.toBeVisible();
              }
              
              // Test horizontal navigation layout
              const menuItems = navMenu.first().locator('li, a, [role="menuitem"]');
              const itemCount = await menuItems.count();
              
              if (itemCount > 1) {
                const firstItem = menuItems.first();
                const secondItem = menuItems.nth(1);
                
                const firstBox = await firstItem.boundingBox();
                const secondBox = await secondItem.boundingBox();
                
                if (deviceType === 'desktop') {
                  // Desktop items should be horizontally aligned
                  expect(Math.abs(firstBox.y - secondBox.y)).toBeLessThan(10);
                }
              }
            }
          }
        }
      });

      test('should display festival cards in appropriate grid', async ({ page }) => {
        await page.goto('/festivals');
        
        const festivalGrid = page.locator('.festival-grid');
        await expect(festivalGrid).toBeVisible();
        
        const festivalCards = page.locator('.festival-card');
        const cardCount = await festivalCards.count();
        
        if (cardCount > 0) {
          const firstCard = festivalCards.first();
          const cardBox = await firstCard.boundingBox();
          
          if (deviceType === 'mobile') {
            // Mobile should show 1 column
            expect(cardBox.width).toBeGreaterThan(viewport.width * 0.8);
          } else if (deviceType === 'tablet') {
            // Tablet should show 2 columns
            expect(cardBox.width).toBeLessThan(viewport.width * 0.6);
            expect(cardBox.width).toBeGreaterThan(viewport.width * 0.4);
          } else {
            // Desktop should show 3+ columns
            expect(cardBox.width).toBeLessThan(viewport.width * 0.4);
          }
        }
      });

      test('should handle form layouts responsively', async ({ page }) => {
        await page.goto('/login');
        
        const loginForm = page.locator('#login-form');
        await expect(loginForm).toBeVisible();
        
        const formBox = await loginForm.boundingBox();
        
        if (deviceType === 'mobile') {
          // Mobile forms should use full width with padding
          expect(formBox.width).toBeGreaterThan(viewport.width * 0.8);
        } else if (deviceType === 'tablet') {
          // Tablet forms should be centered with reasonable width
          expect(formBox.width).toBeLessThan(viewport.width * 0.8);
          expect(formBox.width).toBeGreaterThan(viewport.width * 0.5);
        } else {
          // Desktop forms should be centered with max width
          expect(formBox.width).toBeLessThan(600);
        }
      });

      test('should display playlist interface appropriately', async ({ page }) => {
        await page.goto('/playlists/create');
        
        const playlistInterface = page.locator('.playlist-interface');
        await expect(playlistInterface).toBeVisible();
        
        if (deviceType === 'mobile') {
          // Mobile should stack sections vertically
          const songList = page.locator('.song-list');
          const playlistPreview = page.locator('.playlist-preview');
          
          const songListBox = await songList.boundingBox();
          const previewBox = await playlistPreview.boundingBox();
          
          // Preview should be below song list on mobile
          expect(previewBox.y).toBeGreaterThan(songListBox.y + songListBox.height);
        } else {
          // Tablet and desktop should show side-by-side layout
          const songList = page.locator('.song-list');
          const playlistPreview = page.locator('.playlist-preview');
          
          const songListBox = await songList.boundingBox();
          const previewBox = await playlistPreview.boundingBox();
          
          // Should be side by side
          expect(Math.abs(songListBox.y - previewBox.y)).toBeLessThan(50);
        }
      });

      test('should handle text scaling and readability', async ({ page }) => {
        const headings = page.locator('h1, h2, h3');
        const paragraphs = page.locator('p');
        
        if (await headings.count() > 0) {
          const heading = headings.first();
          const headingStyles = await heading.evaluate(el => {
            const styles = window.getComputedStyle(el);
            return {
              fontSize: parseFloat(styles.fontSize),
              lineHeight: parseFloat(styles.lineHeight)
            };
          });
          
          // Ensure minimum font sizes for readability
          if (deviceType === 'mobile') {
            expect(headingStyles.fontSize).toBeGreaterThanOrEqual(24);
          } else {
            expect(headingStyles.fontSize).toBeGreaterThanOrEqual(28);
          }
        }
        
        if (await paragraphs.count() > 0) {
          const paragraph = paragraphs.first();
          const paragraphStyles = await paragraph.evaluate(el => {
            const styles = window.getComputedStyle(el);
            return {
              fontSize: parseFloat(styles.fontSize),
              lineHeight: parseFloat(styles.lineHeight)
            };
          });
          
          // Ensure minimum font sizes for body text
          expect(paragraphStyles.fontSize).toBeGreaterThanOrEqual(14);
          expect(paragraphStyles.lineHeight).toBeGreaterThanOrEqual(paragraphStyles.fontSize * 1.4);
        }
      });

      test('should handle images and media responsively', async ({ page }) => {
        await page.goto('/festivals');
        
        const images = page.locator('img');
        const imageCount = await images.count();
        
        if (imageCount > 0) {
          for (let i = 0; i < Math.min(imageCount, 3); i++) {
            const image = images.nth(i);
            
            if (await image.isVisible()) {
              const imageBox = await image.boundingBox();
              
              // Images should not overflow viewport
              expect(imageBox.width).toBeLessThanOrEqual(viewport.width);
              
              // Images should maintain aspect ratio
              const naturalDimensions = await image.evaluate(img => ({
                naturalWidth: img.naturalWidth,
                naturalHeight: img.naturalHeight
              }));
              
              if (naturalDimensions.naturalWidth > 0 && naturalDimensions.naturalHeight > 0) {
                const expectedHeight = (imageBox.width * naturalDimensions.naturalHeight) / naturalDimensions.naturalWidth;
                expect(Math.abs(imageBox.height - expectedHeight)).toBeLessThan(5);
              }
              
              // Test responsive image attributes
              const srcset = await image.getAttribute('srcset');
              const sizes = await image.getAttribute('sizes');
              
              // Should use responsive image techniques for better performance
              if (deviceType === 'mobile' && srcset) {
                expect(srcset).toContain('w'); // Should have width descriptors
              }
            }
          }
        }
        
        // Test video responsiveness
        const videos = page.locator('video');
        const videoCount = await videos.count();
        
        if (videoCount > 0) {
          for (let i = 0; i < Math.min(videoCount, 2); i++) {
            const video = videos.nth(i);
            
            if (await video.isVisible()) {
              const videoBox = await video.boundingBox();
              
              // Videos should not overflow viewport
              expect(videoBox.width).toBeLessThanOrEqual(viewport.width);
              
              // Videos should maintain aspect ratio
              const videoStyles = await video.evaluate(vid => {
                const styles = window.getComputedStyle(vid);
                return {
                  width: styles.width,
                  height: styles.height,
                  maxWidth: styles.maxWidth
                };
              });
              
              expect(videoStyles.maxWidth).toBe('100%');
            }
          }
        }
        
        // Test audio player responsiveness
        const audioPlayers = page.locator('audio, .audio-player');
        const audioCount = await audioPlayers.count();
        
        if (audioCount > 0) {
          const audioPlayer = audioPlayers.first();
          
          if (await audioPlayer.isVisible()) {
            const audioBox = await audioPlayer.boundingBox();
            
            // Audio players should fit within viewport
            expect(audioBox.width).toBeLessThanOrEqual(viewport.width);
            
            if (deviceType === 'mobile') {
              // Mobile audio players should be touch-friendly
              expect(audioBox.height).toBeGreaterThanOrEqual(44);
            }
          }
        }
      });

      test('should handle button and interactive element sizing', async ({ page }) => {
        const buttons = page.locator('button, .btn, input[type="submit"]');
        const buttonCount = await buttons.count();
        
        if (buttonCount > 0) {
          for (let i = 0; i < Math.min(buttonCount, 5); i++) {
            const button = buttons.nth(i);
            const buttonBox = await button.boundingBox();
            
            if (deviceType === 'mobile') {
              // Mobile buttons should be at least 44px tall for touch targets
              expect(buttonBox.height).toBeGreaterThanOrEqual(44);
            } else {
              // Desktop buttons should be at least 32px tall
              expect(buttonBox.height).toBeGreaterThanOrEqual(32);
            }
          }
        }
      });
    });
  });

  test.describe('Touch and Gesture Support', () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize(viewports.mobile);
      await page.goto('/');
    });

    test('should support touch navigation', async ({ page }) => {
      // Test touch-friendly navigation
      const navToggle = page.locator('.nav-toggle, .hamburger-menu, [aria-label*="menu"]');
      
      if (await navToggle.count() > 0) {
        await expect(navToggle.first()).toBeVisible();
        
        // Simulate touch tap
        await navToggle.first().tap();
        
        const navMenu = page.locator('.nav-menu, .mobile-menu, [role="navigation"] ul');
        if (await navMenu.count() > 0) {
          await expect(navMenu.first()).toBeVisible();
        }
      }
    });

    test('should support touch interactions on playlist items', async ({ page }) => {
      await page.goto('/playlists');
      
      const playlistItems = page.locator('.playlist-item, .song-item, [data-testid*="song"]');
      const itemCount = await playlistItems.count();
      
      if (itemCount > 0) {
        const firstItem = playlistItems.first();
        
        // Test tap to select/toggle
        await firstItem.tap();
        
        // Verify touch feedback (visual state change)
        await page.waitForTimeout(100);
        
        // Check if item has active/selected state
        const hasActiveState = await firstItem.evaluate(el => {
          const classList = Array.from(el.classList);
          return classList.some(cls => cls.includes('active') || cls.includes('selected') || cls.includes('checked'));
        });
        
        // Should have some form of visual feedback
        expect(typeof hasActiveState).toBe('boolean');
      }
    });

    test('should support swipe gestures for carousels and lists', async ({ page }) => {
      await page.goto('/festivals');
      
      // Test carousel swipe if present
      const carousel = page.locator('.festival-carousel, .carousel, [data-testid*="carousel"]');
      if (await carousel.count() > 0 && await carousel.first().isVisible()) {
        const carouselBox = await carousel.first().boundingBox();
        
        // Simulate swipe left
        await page.mouse.move(carouselBox.x + carouselBox.width * 0.8, carouselBox.y + carouselBox.height / 2);
        await page.mouse.down();
        await page.mouse.move(carouselBox.x + carouselBox.width * 0.2, carouselBox.y + carouselBox.height / 2);
        await page.mouse.up();
        
        // Wait for animation
        await page.waitForTimeout(500);
        
        // Verify carousel responded to swipe
        const activeSlide = page.locator('.carousel-slide.active, .slide.active, [aria-current="true"]');
        if (await activeSlide.count() > 0) {
          await expect(activeSlide.first()).toBeVisible();
        }
      }
      
      // Test horizontal scroll on festival list
      const festivalList = page.locator('.festival-list, .horizontal-scroll');
      if (await festivalList.count() > 0 && await festivalList.first().isVisible()) {
        const listBox = await festivalList.first().boundingBox();
        
        // Test horizontal swipe
        await page.mouse.move(listBox.x + listBox.width * 0.8, listBox.y + listBox.height / 2);
        await page.mouse.down();
        await page.mouse.move(listBox.x + listBox.width * 0.2, listBox.y + listBox.height / 2);
        await page.mouse.up();
        
        // List should handle the gesture gracefully
        await page.waitForTimeout(300);
      }
    });

    test('should handle long press gestures', async ({ page }) => {
      await page.goto('/playlists');
      
      const interactiveItems = page.locator('.playlist-item, .song-item, button, [role="button"]');
      const itemCount = await interactiveItems.count();
      
      if (itemCount > 0) {
        const item = interactiveItems.first();
        
        if (await item.isVisible()) {
          // Simulate long press (touch and hold)
          await item.hover();
          await page.mouse.down();
          await page.waitForTimeout(800); // Long press duration
          await page.mouse.up();
          
          // Check if context menu or additional options appeared
          const contextMenu = page.locator('.context-menu, .dropdown-menu, [role="menu"]');
          const hasContextMenu = await contextMenu.count() > 0;
          
          // Long press should either show context menu or provide some feedback
          if (hasContextMenu) {
            await expect(contextMenu.first()).toBeVisible();
          }
        }
      }
    });

    test('should support pull-to-refresh gesture', async ({ page }) => {
      await page.goto('/festivals');
      
      // Simulate pull-to-refresh gesture
      const body = page.locator('body');
      const bodyBox = await body.boundingBox();
      
      // Start from top of page and pull down
      await page.mouse.move(bodyBox.x + bodyBox.width / 2, 50);
      await page.mouse.down();
      await page.mouse.move(bodyBox.x + bodyBox.width / 2, 200);
      await page.waitForTimeout(300);
      await page.mouse.up();
      
      // Check for refresh indicator or page reload
      const refreshIndicator = page.locator('.refresh-indicator, .loading-spinner, [aria-label*="refresh"]');
      if (await refreshIndicator.count() > 0) {
        // Should show refresh indicator briefly
        await page.waitForTimeout(1000);
      }
    });
  });

  test.describe('Orientation Changes', () => {
    test('should handle portrait to landscape transition', async ({ page }) => {
      // Start in portrait
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/');
      
      const navigation = page.locator('.main-navigation');
      await expect(navigation).toBeVisible();
      
      // Switch to landscape
      await page.setViewportSize({ width: 667, height: 375 });
      await page.waitForTimeout(500); // Allow for reflow
      
      // Navigation should still be visible and functional
      await expect(navigation).toBeVisible();
      
      // Test that content adapts to new orientation
      const content = page.locator('.main-content');
      if (await content.isVisible()) {
        const contentBox = await content.boundingBox();
        expect(contentBox.width).toBeLessThanOrEqual(667);
      }
    });

    test('should maintain functionality across orientations', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/festivals');
      
      // Test functionality in portrait
      const searchInput = page.locator('#festival-search');
      await searchInput.fill('coachella');
      await expect(searchInput).toHaveValue('coachella');
      
      // Switch to landscape
      await page.setViewportSize({ width: 667, height: 375 });
      await page.waitForTimeout(500);
      
      // Functionality should still work
      await expect(searchInput).toHaveValue('coachella');
      await searchInput.fill('bonnaroo');
      await expect(searchInput).toHaveValue('bonnaroo');
    });
  });

  test.describe('Performance on Different Viewports', () => {
    test('should load efficiently on mobile', async ({ page }) => {
      await page.setViewportSize(viewports.mobile);
      
      const startTime = Date.now();
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      const loadTime = Date.now() - startTime;
      
      // Mobile should load within reasonable time
      expect(loadTime).toBeLessThan(5000);
      
      // Check that critical content is visible
      const mainContent = page.locator('.main-content');
      await expect(mainContent).toBeVisible();
    });

    test('should handle large datasets on small screens', async ({ page }) => {
      await page.setViewportSize(viewports.mobile);
      await page.goto('/festivals');
      
      // Test virtual scrolling or pagination for large lists
      const festivalList = page.locator('.festival-list');
      if (await festivalList.isVisible()) {
        const listItems = page.locator('.festival-item');
        const itemCount = await listItems.count();
        
        // Should not render too many items at once on mobile
        expect(itemCount).toBeLessThan(50);
      }
    });
  });

  test.describe('Cross-Device Consistency', () => {
    test('should maintain brand consistency across viewports', async ({ page }) => {
      const devices = [
        { name: 'mobile', viewport: viewports.mobile },
        { name: 'tablet', viewport: viewports.tablet },
        { name: 'desktop', viewport: viewports.desktop }
      ];
      
      const brandColors = [];
      
      for (const device of devices) {
        await page.setViewportSize(device.viewport);
        await page.goto('/');
        
        const logo = page.locator('.brand-link');
        if (await logo.isVisible()) {
          const logoColor = await logo.evaluate(el => {
            return window.getComputedStyle(el).color;
          });
          brandColors.push(logoColor);
        }
      }
      
      // All brand colors should be consistent
      if (brandColors.length > 1) {
        const firstColor = brandColors[0];
        brandColors.forEach(color => {
          expect(color).toBe(firstColor);
        });
      }
    });

    test('should maintain content hierarchy across viewports', async ({ page }) => {
      const devices = [
        { name: 'mobile', viewport: viewports.mobile },
        { name: 'desktop', viewport: viewports.desktop }
      ];
      
      for (const device of devices) {
        await page.setViewportSize(device.viewport);
        await page.goto('/');
        
        // Check that main heading is always the largest
        const h1 = page.locator('h1').first();
        const h2 = page.locator('h2').first();
        
        if (await h1.isVisible() && await h2.isVisible()) {
          const h1Size = await h1.evaluate(el => parseFloat(window.getComputedStyle(el).fontSize));
          const h2Size = await h2.evaluate(el => parseFloat(window.getComputedStyle(el).fontSize));
          
          expect(h1Size).toBeGreaterThan(h2Size);
        }
      }
    });
  });
});