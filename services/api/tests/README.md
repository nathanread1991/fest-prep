# Festival Playlist Generator - UI Testing Framework

## Overview

This comprehensive UI testing framework implements all requirements from task 16 and covers Requirements 21-25 from the project specification. The framework includes end-to-end tests, component tests, accessibility tests, security tests, performance tests, and more.

## Test Structure

### 1. End-to-End Workflow Tests (`tests/e2e/`)
- **Festival Search and Discovery** (`workflows/festival-search.test.js`)
  - Festival search functionality with various inputs
  - Festival filtering and sorting capabilities
  - Festival detail page navigation and display
- **Playlist Generation** (`workflows/playlist-generation.test.js`)
  - Complete festival playlist creation process
  - Single artist playlist generation workflow
  - Playlist customization and song management
  - Streaming service integration and authentication
- **User Management** (`workflows/user-management.test.js`)
  - User registration and login processes
  - Profile management and preferences
  - Session handling and logout functionality

### 2. Interactive Component Tests (`tests/component/`)
- **Song Management** (`song-checklist.test.js`)
  - Song checklist functionality (check/uncheck songs)
  - Song filtering and toggle visibility features
  - Real-time updates without page refresh
  - Song preference persistence across sessions
- **Form and Input Components** (`form-components.test.js`)
  - Form submissions and input validation
  - Error handling and user feedback messages
  - Autocomplete and search functionality
  - File upload and data import features
- **Navigation and Routing** (`navigation-routing.test.js`)
  - Page navigation and URL routing
  - Breadcrumb and menu functionality
  - Back/forward browser navigation
  - Deep linking and bookmark functionality

### 3. Responsive Design Tests (`tests/responsive/`)
- **Responsive Design** (`responsive-design.test.js`)
  - Mobile, tablet, and desktop layouts
  - Touch interactions and gesture support
  - Responsive navigation and menu behavior
  - Image and media responsiveness
  - Orientation changes and viewport transitions

### 4. Accessibility Tests (`tests/accessibility/`)
- **Accessibility Compliance** (`accessibility.test.js`)
  - Keyboard navigation throughout the application
  - Screen reader compatibility and ARIA attributes
  - Color contrast and visual accessibility
  - Focus management and tab order
  - Alternative text and media accessibility

### 5. Cross-Browser Tests (`tests/cross-browser/`)
- **Browser Compatibility** (`browser-compatibility.test.js`)
  - Functionality across Chrome, Firefox, Safari, Edge
  - JavaScript compatibility across browser versions
  - CSS rendering consistency
  - Browser-specific features and APIs

### 6. Performance Tests (`tests/performance/`)
- **Performance and Loading** (`performance.test.js`)
  - Page load times under 3 seconds
  - Slow network conditions and limited bandwidth
  - Memory usage and memory leak prevention
  - Progressive Web App (PWA) functionality

### 7. Security Tests (`tests/security/`)
- **Input Security** (`input-security.test.js`)
  - Protection against XSS attacks in user inputs
  - Input sanitization and validation rules
  - CSRF protection in form submissions
  - SQL injection protection in search inputs
- **Authentication Security** (`auth-security.test.js`)
  - Secure authentication state management
  - Session timeout and automatic logout
  - Secure handling of sensitive data
  - Logout functionality and session cleanup

### 8. Offline and Network Tests (`tests/offline/`)
- **Offline Functionality** (`offline-functionality.test.js`)
  - Service worker behavior and caching
  - Offline data access and playlist viewing
  - Offline-to-online synchronization
  - Network error handling and retry mechanisms

### 9. Real-time Features Tests (`tests/realtime/`)
- **WebSocket and Real-time** (`websocket-realtime.test.js`)
  - Real-time updates and notifications
  - WebSocket connection handling and reconnection
  - Collaborative features and live updates
  - Connection failure recovery

## Test Infrastructure

### Configuration Files
- `playwright.config.js` - Playwright E2E test configuration
- `jest.config.js` - Jest unit/component test configuration
- `.eslintrc.js` - ESLint configuration for code quality

### Setup Files
- `tests/setup/jest.setup.js` - Jest setup and browser API mocks
- `tests/setup/test-data.js` - Mock test data for consistent testing
- `tests/setup/mock-services.js` - Mock services for testing isolation

### Page Object Models (`tests/e2e/pages/`)
- `base-page.js` - Base page object with common functionality
- `home-page.js` - Home page interactions
- `festivals-page.js` - Festival listing and search
- `festival-detail-page.js` - Individual festival details
- `playlist-page.js` - Playlist management
- `streaming-page.js` - Streaming service integration
- `auth-page.js` - Authentication flows
- `profile-page.js` - User profile management

### Utilities
- `tests/e2e/utils/base-test.js` - Base test utilities for Playwright

## Requirements Coverage

### Requirement 21: Core UI Functionality
- ✅ 21.1: UI testing infrastructure setup
- ✅ 21.2: Festival search and discovery validation
- ✅ 21.3: Playlist generation workflow testing
- ✅ 21.4: Song management component testing
- ✅ 21.6: Responsive design testing
- ✅ 21.7: Form validation testing
- ✅ 21.8: Offline functionality testing
- ✅ 21.9: Accessibility compliance testing
- ✅ 21.10: Real-time features testing

### Requirement 22: Interactive Components
- ✅ 22.1: Component testing framework
- ✅ 22.2: Navigation component testing
- ✅ 22.3: Song checklist interaction testing
- ✅ 22.4: Form component testing
- ✅ 22.9: Accessibility in components

### Requirement 23: Cross-Browser and Performance
- ✅ 23.1: Cross-browser compatibility testing
- ✅ 23.2: Performance testing under 3 seconds
- ✅ 23.3: JavaScript compatibility testing
- ✅ 23.4: CSS rendering consistency
- ✅ 23.5: Responsive design validation
- ✅ 23.6: Memory usage testing
- ✅ 23.8: PWA and offline testing
- ✅ 23.9: Service worker testing

### Requirement 24: Security Testing
- ✅ 24.1: Input validation and XSS protection
- ✅ 24.2: SQL injection protection
- ✅ 24.3: CSRF protection testing
- ✅ 24.4: Authentication security
- ✅ 24.5: Session management security
- ✅ 24.10: Secure data handling

### Requirement 25: End-to-End Workflows
- ✅ 25.1: Festival search workflow
- ✅ 25.2: Playlist creation workflow
- ✅ 25.3: Streaming integration workflow
- ✅ 25.4: User management workflow
- ✅ 25.9: Network resilience testing

## Running Tests

### Prerequisites
```bash
npm install
```

### Component Tests (Jest)
```bash
# Run all component tests
npm test

# Run specific test file
npm test tests/component/form-components.test.js

# Run with coverage
npm run test:coverage
```

### End-to-End Tests (Playwright)
```bash
# Run all E2E tests
npx playwright test

# Run specific test file
npx playwright test tests/e2e/workflows/festival-search.test.js

# Run with UI mode
npx playwright test --ui

# Run in headed mode
npx playwright test --headed
```

### Specific Test Categories
```bash
# Accessibility tests
npx playwright test tests/accessibility/

# Performance tests
npx playwright test tests/performance/

# Security tests
npx playwright test tests/security/

# Cross-browser tests
npx playwright test tests/cross-browser/
```

## Test Data and Mocking

The framework includes comprehensive mocking for:
- Browser APIs (localStorage, sessionStorage, geolocation)
- Network requests and API responses
- Streaming service integrations
- User authentication flows
- Real-time WebSocket connections

## Continuous Integration

Tests are configured for CI/CD with:
- Parallel test execution
- Multiple browser testing
- Screenshot and video capture on failures
- Test result reporting in multiple formats
- Coverage reporting

## Best Practices Implemented

1. **Page Object Model** - Maintainable and reusable page interactions
2. **Test Data Management** - Consistent and isolated test data
3. **Mock Services** - Reliable testing without external dependencies
4. **Accessibility First** - WCAG compliance testing throughout
5. **Performance Monitoring** - Continuous performance validation
6. **Security Testing** - Proactive security vulnerability detection
7. **Cross-Browser Coverage** - Consistent experience across browsers
8. **Mobile-First Testing** - Responsive design validation

## Future Enhancements

- Visual regression testing with screenshot comparisons
- API contract testing integration
- Load testing for high-traffic scenarios
- Automated accessibility auditing
- Performance budgets and monitoring
- Test result analytics and reporting

This comprehensive testing framework ensures the Festival Playlist Generator provides a robust, accessible, secure, and performant user experience across all supported platforms and devices.