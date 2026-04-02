# Requirements Document

## Introduction

Complete visual rebrand of the Festival Playlist Generator web UI. The current bright, indigo-themed interface will be replaced with a dark, minimal, stage-inspired design system. Brand assets (SVGs, PNGs, hero images, favicons, CSS tokens) from the `gig-prep-brand-assets/` directory will be integrated into the application's static file serving. The redesign covers the global layout (base.html), the home page (index.html), and all inherited pages via the shared template hierarchy.

## Glossary

- **Web_UI**: The Festival Playlist Generator front-end served by FastAPI with Jinja2 templates, consisting of base.html, index.html, and child templates
- **Brand_Token**: A CSS custom property defined in `:root` that stores a design value (colour, font family, spacing) used consistently across all stylesheets
- **Asset_Pipeline**: The process of copying brand asset files from `gig-prep-brand-assets/` into the application's `web/static/` directory structure for serving
- **Hero_Section**: The full-width banner area at the top of the home page containing a background image, dark overlay, gradient fade, and headline text
- **Grain_Overlay**: A subtle noise texture applied globally via a fixed pseudo-element using a tiled PNG at low opacity
- **Sigil**: The SVG icon representing the GIG-PREP brand, used as favicon and decorative element (replacing the previous emoji logo)
- **Content_Grid**: A CSS Grid layout with `2fr 1fr` column ratio used on the home page to arrange main content and sidebar
- **DEV_Banner**: The existing sticky red banner at the top of the page indicating a non-production environment
- **Navigation_Bar**: The header element containing the logo SVG, navigation links, authentication controls, and admin link
- **Card**: A UI component with dark background, subtle border, and consistent padding used to display grouped content

## Requirements

### Requirement 1: Brand Asset Integration

**User Story:** As a developer, I want all brand assets copied into the application's static directory, so that templates can reference them via standard static file URLs.

#### Acceptance Criteria

1. WHEN the Asset_Pipeline is executed, THE Web_UI SHALL contain all SVG files (logo.svg, sigil.svg, sigil-pattern.svg) in `static/brand/svg/`
2. WHEN the Asset_Pipeline is executed, THE Web_UI SHALL contain all PNG files (logo variants, sigil sizes, icon-dark variants, grain textures, og-image) in `static/brand/png/`
3. WHEN the Asset_Pipeline is executed, THE Web_UI SHALL contain all hero images (hero-1920x1080.jpg, hero-1600x900.jpg) in `static/brand/hero/`
4. WHEN the Asset_Pipeline is executed, THE Web_UI SHALL contain the favicon.ico file in `static/brand/ico/`
5. WHEN the Asset_Pipeline is executed, THE Web_UI SHALL contain the site.webmanifest file in `static/brand/`
6. WHEN the Asset_Pipeline is executed, THE Web_UI SHALL contain the brand-tokens.css file in `static/brand/css/`

### Requirement 2: Design Token System

**User Story:** As a developer, I want a centralized CSS custom property system, so that all brand colours, fonts, and spacing values are defined once and reused consistently.

#### Acceptance Criteria

1. THE Web_UI SHALL define the following Brand_Tokens in `:root`: `--bg-primary: #0A0A0A`, `--bg-secondary: #121212`, `--border: #1F1F1F`, `--text-primary: #F2F2F2`, `--text-secondary: #888888`, `--accent: #8A1C1C`
2. THE Web_UI SHALL define font Brand_Tokens: `--font-heading: "Space Grotesk", "Inter", Arial, sans-serif` and `--font-body: "Inter", Arial, sans-serif`
3. THE Web_UI SHALL load Google Fonts for Space Grotesk (weights 500, 700) and Inter (weights 400, 500, 600, 700) via a `<link>` element in base.html
4. THE Web_UI SHALL apply `var(--bg-primary)` as the body background colour and `var(--text-primary)` as the body text colour
5. THE Web_UI SHALL apply `var(--font-body)` as the body font family and `var(--font-heading)` to all heading elements (h1 through h6)

### Requirement 3: Global Dark Theme

**User Story:** As a user, I want a dark-themed interface, so that the visual experience is consistent with the stage-inspired brand identity.

#### Acceptance Criteria

1. THE Web_UI SHALL set the body background to `var(--bg-primary)` (#0A0A0A)
2. THE Web_UI SHALL set all primary text to `var(--text-primary)` (#F2F2F2)
3. THE Web_UI SHALL set all secondary/muted text to `var(--text-secondary)` (#888888)
4. THE Web_UI SHALL remove all bright background colours (#f9fafb, #6366f1, linear gradients with #667eea/#764ba2) from global styles
5. THE Web_UI SHALL set the `<meta name="theme-color">` value to `#0A0A0A`
6. THE Web_UI SHALL apply the Grain_Overlay to the body using `body::before` with `png/grain-256.png` tiled at opacity between 0.04 and 0.06, with `pointer-events: none` and `position: fixed`

### Requirement 4: Navigation Bar Redesign

**User Story:** As a user, I want a redesigned navigation bar with the SVG logo, so that the header reflects the new brand identity.

#### Acceptance Criteria

1. THE Navigation_Bar SHALL display `logo.svg` as an inline SVG or `<img>` element in place of the emoji text logo "🎵 Festival Playlists"
2. THE Navigation_Bar SHALL use `var(--bg-secondary)` (#121212) as its background colour
3. THE Navigation_Bar SHALL use `var(--border)` (#1F1F1F) as a bottom border (1px solid)
4. THE Navigation_Bar SHALL style all navigation links with `var(--text-primary)` colour and hover state using `var(--accent)` (#8A1C1C)
5. THE Navigation_Bar SHALL preserve the existing authentication controls (sign-in button, user menu dropdown) with colours updated to match the dark theme
6. THE Navigation_Bar SHALL preserve the existing admin link, restyled to use `var(--accent)` as its background colour

### Requirement 5: Favicon and Meta Tag Updates

**User Story:** As a user, I want correct favicons and meta tags, so that browser tabs, bookmarks, and social sharing reflect the new brand.

#### Acceptance Criteria

1. THE Web_UI SHALL reference `brand/ico/favicon.ico` as the primary favicon with `sizes="any"`
2. THE Web_UI SHALL reference `brand/png/sigil-32.png` and `brand/png/sigil-16.png` as PNG favicons
3. THE Web_UI SHALL reference `brand/png/icon-dark-180.png` as the Apple touch icon
4. THE Web_UI SHALL reference `brand/site.webmanifest` as the web app manifest
5. THE Web_UI SHALL include an Open Graph image meta tag pointing to `brand/png/og-image-1200x630.jpg`

### Requirement 6: Hero Section

**User Story:** As a user, I want a visually striking hero section on the home page, so that the landing experience communicates the brand's stage-inspired aesthetic.

#### Acceptance Criteria

1. THE Hero_Section SHALL display a background image using `hero-1920x1080.jpg` (desktop) with `hero-1600x900.jpg` as a fallback, applied via CSS `background` on a `::before` pseudo-element
2. THE Hero_Section SHALL apply a dark overlay to the background image using `filter: grayscale(100%) contrast(108%) brightness(42%)` at `opacity: 0.72`
3. THE Hero_Section SHALL apply a gradient fade from transparent to `var(--bg-primary)` at the bottom edge so the hero blends into the page body
4. THE Hero_Section SHALL display headline text using `var(--font-heading)` at a minimum font size of 2.5rem
5. THE Hero_Section SHALL use `position: relative` with `overflow: hidden` so the pseudo-element background is clipped to the section bounds
6. IF the hero background image fails to load, THEN THE Hero_Section SHALL remain visible with a solid `var(--bg-secondary)` background

### Requirement 7: Home Page Content Grid

**User Story:** As a user, I want the home page content organized in a clear grid layout, so that I can quickly find setlists, upcoming shows, and preparation tools.

#### Acceptance Criteria

1. THE Content_Grid SHALL use CSS Grid with column template `2fr 1fr` on viewports wider than 768px
2. THE Content_Grid SHALL collapse to a single column (`1fr`) on viewports 768px and narrower
3. THE Content_Grid left column SHALL contain a "Latest Setlists" section displaying artist name, duration, and last-updated date for each entry
4. THE Content_Grid right column SHALL contain an "Upcoming Shows" section and a "Quick Prep Checklist" section
5. THE Content_Grid SHALL use a gap of 1.5rem between grid cells

### Requirement 8: Card Component Styling

**User Story:** As a user, I want content displayed in visually consistent dark cards, so that information is easy to scan and the interface feels cohesive.

#### Acceptance Criteria

1. THE Card SHALL use `var(--bg-secondary)` (#121212) as its background colour
2. THE Card SHALL use `var(--border)` (#1F1F1F) as a 1px solid border
3. THE Card SHALL use a border-radius between 8px and 12px
4. THE Card SHALL use consistent padding between 1rem and 1.5rem
5. WHEN a user hovers over a Card, THE Card SHALL display a subtle visual change (border colour lightening or slight elevation via box-shadow) to indicate interactivity
6. THE Card SHALL apply to all content containers across the Web_UI including setlist items, show listings, checklist panels, and feature cards

### Requirement 9: Footer Redesign

**User Story:** As a user, I want the footer to match the dark brand theme, so that the page has a consistent visual finish.

#### Acceptance Criteria

1. THE Web_UI footer SHALL use `var(--bg-secondary)` as its background colour
2. THE Web_UI footer SHALL use `var(--text-secondary)` for its text colour
3. THE Web_UI footer SHALL use `var(--border)` as a top border (1px solid)

### Requirement 10: DEV Environment Banner Preservation

**User Story:** As a developer, I want the existing DEV environment banner preserved, so that non-production environments remain clearly identified.

#### Acceptance Criteria

1. THE DEV_Banner SHALL remain sticky at the top of the page with `position: sticky` and `z-index: 9999`
2. THE DEV_Banner SHALL retain its red background colour (#dc3545) and white text
3. THE DEV_Banner SHALL remain visible above the Navigation_Bar and all other page content

### Requirement 11: Inline Style Cleanup

**User Story:** As a developer, I want inline styles in base.html moved to the main stylesheet, so that the template is cleaner and styles are centrally managed.

#### Acceptance Criteria

1. THE Web_UI SHALL move all inline `<style>` blocks from base.html (authentication styles, user menu styles, dropdown styles) into main.css or a dedicated brand stylesheet
2. THE Web_UI SHALL update all moved styles to use Brand_Tokens (CSS custom properties) instead of hardcoded colour values
3. THE Web_UI SHALL preserve the visual appearance and functionality of all authentication UI components (sign-in button, user menu toggle, user dropdown, logout button) after the style migration

### Requirement 12: Container and Layout Constraints

**User Story:** As a user, I want content constrained to a readable width, so that the layout is comfortable on large screens.

#### Acceptance Criteria

1. THE Web_UI `.container` class SHALL set `max-width: 1200px` with `margin: 0 auto`
2. THE Web_UI SHALL maintain horizontal padding of at least 1rem on the container for all viewport sizes

### Requirement 13: Brand Identity Guardrails

**User Story:** As a designer, I want brand guardrails enforced in the implementation, so that the visual identity remains consistent and undistorted.

#### Acceptance Criteria

1. THE Web_UI SHALL preserve the hyphen in "GIG-PREP" in all text references to the brand name
2. THE Web_UI SHALL use the SVG source files (logo.svg, sigil.svg) as the authoritative brand marks, with PNG variants used only as fallbacks for contexts that require raster images (favicons, social sharing)
3. THE Web_UI SHALL apply the Sigil without solid fills, recolouring, or distorted line weights, consistent with the brand asset guardrails
