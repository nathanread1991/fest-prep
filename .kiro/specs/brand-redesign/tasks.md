# Implementation Plan: Brand Redesign

## Overview

Rebrand the Festival Playlist Generator web UI from bright indigo to a dark, stage-inspired design system. Work proceeds in layers: copy brand assets, introduce CSS tokens, overhaul the stylesheet, update templates, then validate with property-based and unit tests. All changes are front-end only (CSS, HTML, static files).

## Tasks

- [x] 1. Copy brand assets into the application static directory
  - [x] 1.1 Copy asset directories from `gig-prep-brand-assets/` to `gigprep/services/api/festival_playlist_generator/web/static/brand/`
    - Copy `svg/`, `png/`, `hero/`, `ico/` directories preserving structure
    - Copy `css/brand-tokens.css` to `static/brand/css/` (do NOT copy `asset-usage.css`)
    - Copy `site.webmanifest` to `static/brand/`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 1.2 Update `site.webmanifest` icon paths for static file serving
    - Change icon `src` values from `/assets/png/` to `/static/brand/png/`
    - Set `name` and `short_name` to `"GIG-PREP"`
    - Set `theme_color` and `background_color` to `#0A0A0A`
    - _Requirements: 1.5, 5.4, 13.1_


- [x] 2. Establish CSS token system and overhaul main.css
  - [x] 2.1 Add `brand-tokens.css` link and Google Fonts link to `base.html` `<head>`
    - Add Google Fonts `<link>` for Space Grotesk (500, 700) and Inter (400, 500, 600, 700)
    - Add `<link rel="stylesheet" href="/static/brand/css/brand-tokens.css">` before the existing `main.css` link
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.2 Overhaul `main.css` body, reset, and typography rules
    - Update `body` to use `var(--bg-primary)`, `var(--text-primary)`, `var(--font-body)` with hardcoded fallbacks
    - Update all heading rules (h1–h6) to use `var(--font-heading)`
    - Add `body::before` grain overlay rule using `/static/brand/png/grain-256.png` at opacity 0.05, `position: fixed`, `pointer-events: none`, `z-index: 9998`
    - Remove all legacy bright colours (`#f9fafb`, `#6366f1`, `#5856eb`, `#667eea`, `#764ba2`, `#e0e7ff`) from global rules
    - _Requirements: 2.4, 2.5, 3.1, 3.2, 3.4, 3.6_

  - [x] 2.3 Overhaul `main.css` header/nav rules
    - Set `.header` background to `var(--bg-secondary)` with `border-bottom: 1px solid var(--border)`
    - Set nav link colour to `var(--text-primary)` with hover `var(--accent)`
    - Set admin link and auth button backgrounds to `var(--accent)`
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 2.4 Overhaul `main.css` card component rules
    - Apply `background: var(--bg-secondary)`, `border: 1px solid var(--border)`, `border-radius: 10px`, `padding: 1.25rem` to all card-like selectors (`.card`, `.feature-card`, `.festival-card`, `.service-card`, `.search-filters`, `.playlist-header`, `.songs-container`, `.overview-card`, `.help-section`, `.quick-actions-section`)
    - Add hover state with lightened border or subtle box-shadow
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 2.5 Overhaul `main.css` footer rules
    - Set `.footer` background to `var(--bg-secondary)`, text to `var(--text-secondary)`, top border to `1px solid var(--border)`
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 2.6 Add hero section CSS rules to `main.css`
    - Add `.hero` with `position: relative`, `overflow: hidden`, fallback `background-color: var(--bg-secondary)`
    - Add `.hero::before` with background image `hero-1920x1080.jpg`, grayscale/contrast/brightness filter, opacity 0.72
    - Add `.hero::after` with gradient fade from transparent to `var(--bg-primary)`
    - Style hero headline with `var(--font-heading)` at minimum 2.5rem
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 2.7 Add content grid CSS rules to `main.css`
    - Add `.content-grid` with `display: grid`, `grid-template-columns: 2fr 1fr`, `gap: 1.5rem`
    - Add media query at `max-width: 768px` collapsing to `1fr`
    - _Requirements: 7.1, 7.2, 7.5_

  - [x] 2.8 Add search form dark theme rules to `main.css`
    - Style `.search-input-group`, `.search-input`, `.search-button` with dark tokens
    - _Requirements: 3.1, 3.3_

  - [x] 2.9 Add `.container` layout constraint rules to `main.css`
    - Set `max-width: 1200px`, `margin: 0 auto`, minimum `padding: 0 1rem`
    - _Requirements: 12.1, 12.2_

  - [x] 2.10 Add DEV banner CSS class to `main.css`
    - Move DEV banner inline styles to a `.dev-banner` class: `position: sticky`, `top: 0`, `z-index: 9999`, red background `#dc3545`, white text
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 2.11 Migrate inline `<style>` blocks from `base.html` into `main.css`
    - Move all auth/dropdown/user-menu styles (~160 lines) from `base.html` `<style>` block into `main.css`
    - Replace all hardcoded colours with token references: `#6366f1` → `var(--accent)`, white backgrounds → `var(--bg-secondary)`, `#1f2937` → `var(--text-primary)`, `#e2e8f0` → `var(--border)`
    - Remove the `<style>` and `</style>` tags from `base.html`
    - _Requirements: 11.1, 11.2, 11.3_
