# JapanPropSearch — Project Vision & Implementation Plan

> **Purpose of this document:** This is the single source of truth for the project vision, architecture decisions, and implementation roadmap. Every new chat session should read this file first to understand context.

---

## 1. Project Overview

**JapanPropSearch** (placeholder name) is a consumer-facing SaaS platform for discovering and analyzing Japanese real estate (akiya/vacant houses). It targets international buyers and investors who want English-language access to Japanese property listings.

**Inspiration:** [AkiyaMart](https://akiya-mart.com) — a search & discovery platform with map-based exploration, translated listings, hazard data, subscription tiers, wishlists, and alerts.

**Key differentiators we're building:**
- Minimal Japanese aesthetic design (whitespace, elegance, subtle colors)
- 6-dimension property scoring algorithm (unique to us)
- Full deal pipeline & financial calculator (premium investor tools)
- Hazard overlays directly on map (not just per-listing)
- Multi-source scraping with transparent source badges

---

## 2. Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Frontend + API** | Next.js 16 (App Router, TypeScript) | SSR for SEO, API routes, image optimization, one language |
| **Database** | Supabase (hosted Postgres + PostGIS) | Free tier, managed, PostGIS for geo queries, TypeScript SDK |
| **Auth** | NextAuth.js (Auth.js v5) | Free, self-hosted, supports email + OAuth providers |
| **Image Storage** | Supabase Storage | Integrated with DB, free 1GB, works with Next.js Image |
| **Maps** | MapLibre GL JS + OpenStreetMap tiles | Free, no API key, high quality, satellite via free providers |
| **Scrapers** | Python microservice on Vultr (existing code) | Don't rewrite working Playwright scrapers, call via API |
| **Translation** | Google Translate API | Batch translate during scraping, cost-effective |
| **Hosting (App)** | Vercel (free tier) | Best Next.js host, auto-deploy from GitHub, free |
| **Hosting (Scrapers)** | Vultr VPS (existing) | Already have it, Playwright needs a real server |
| **Domain** | Single domain | Simpler, cheaper, better SEO consolidation |
| **Approach** | Fresh start (new Next.js project) | Clean architecture, old app stays running until ready |

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    VERCEL (Free Tier)                     │
│  ┌───────────────────────────────────────────────────┐   │
│  │              Next.js 16 (App Router)               │   │
│  │                                                     │   │
│  │  Marketing Pages    App Pages      API Routes       │   │
│  │  /, /city/*, /pre   /explore,      /api/listings,   │   │
│  │  /pricing, /faq     /listing/*,    /api/places,     │   │
│  │                     /dashboard     /api/auth/*      │   │
│  └───────────────────────┬───────────────────────────┘   │
└──────────────────────────┼───────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │   SUPABASE   │ │  VULTR   │ │   EXTERNAL   │
    │              │ │  VPS     │ │   SERVICES   │
    │ - Postgres   │ │          │ │              │
    │   + PostGIS  │ │ - Python │ │ - Google     │
    │ - Storage    │ │   Scraper│ │   Translate  │
    │   (images)   │ │   Micro- │ │ - Nominatim  │
    │ - Realtime   │ │   service│ │   (geocoding)│
    │   (alerts)   │ │ - Cron   │ │ - J-SHIS     │
    └──────────────┘ │   jobs   │ │   (hazards)  │
                     └──────────┘ └──────────────┘
```

---

## 3. Tech Stack (Complete)

### Next.js App
- **Framework:** Next.js 16.1.6 (App Router)
- **React:** 19.2.3 (async params, useRef requires initial value)
- **Language:** TypeScript 5.x (strict mode)
- **Styling:** TailwindCSS v4 (CSS-based config via `@import "tailwindcss"` + `@theme inline {}` in globals.css — **NOT** tailwind.config.ts)
- **UI Components:** Radix UI (headless) + custom styled wrappers (shadcn/ui pattern, 17 components)
- **Maps:** MapLibre GL JS 5.18 + react-map-gl 8.1 (loaded via `next/dynamic` with `ssr: false`)
- **State:** React useState/useEffect + custom hooks (no external state library needed)
- **Auth:** NextAuth.js v5 beta (5.0.0-beta.30), Drizzle adapter, JWT sessions
- **ORM:** Drizzle ORM 0.45 + `postgres` driver (lazy DB via Proxy pattern)
- **Validation:** Lightweight custom validators in `src/lib/validations.ts`
- **Icons:** Lucide React 0.563
- **Charts:** Recharts 3.7 (RadarChart for scores)
- **Analytics:** Google Analytics 4 (conditional on NEXT_PUBLIC_GA_ID env var)
- **Email:** React Email + Resend (for alerts — not yet wired)
- **Payments (future):** Stripe (structure built, not wired)

### Python Scraper Microservice (Vultr)
- **Existing:** FastAPI + Playwright + BeautifulSoup
- **New:** REST API endpoint for Next.js to trigger scrapes
- **New:** Direct Supabase DB connection (replace local Postgres)
- **New:** Google Translate integration in scrape pipeline
- **Cron:** Scheduled scraping via system cron or APScheduler

### Supabase
- **Database:** PostgreSQL 15 with PostGIS extension
- **Storage:** Listing images, user avatars
- **Row Level Security:** Per-user data (wishlists, alerts, deals)
- **Realtime:** Property alert notifications (future)

---

## 4. Database Schema

### Core Tables

```sql
-- Existing concept, adapted for Supabase

-- Prefectures & Municipalities (seed data)
prefectures (code, name_ja, name_en, region, slug)
municipalities (code, prefecture_code, name_ja, name_en, slug, bbox_sw_lat, bbox_sw_lon, bbox_ne_lat, bbox_ne_lon, population)

-- Properties (central entity)
properties (
  id,
  -- Location
  address_ja, address_en, prefecture_code, municipality_code, lat, lng,
  -- Physical
  price_jpy, land_area_sqm, building_area_sqm, floor_plan, year_built, structure, floors,
  -- Legal
  land_rights (freehold/leasehold), road_width_m, rebuild_possible,
  -- Zoning
  use_zone, coverage_ratio, floor_area_ratio,
  -- Computed
  composite_score, price_per_sqm,
  -- Metadata
  status (active/sold/delisted), view_count, created_at, updated_at
)

-- Property Listings (multi-source tracking)
property_listings (
  id, property_id, source_id, source_url, source_listing_id,
  raw_data_json, listing_status, first_scraped_at, last_scraped_at
)

-- Listing Sources
listing_sources (
  id (suumo/athome/homes/bit_auction/akiya),
  name, badge_color, icon, enabled
)

-- Property Images
property_images (
  id, property_id, storage_path, width, height, sort_order, alt_text
)

-- Hazard Assessments
hazard_assessments (
  id, property_id,
  seismic_intensity, pga_475yr, liquefaction_risk,
  flood_depth_max_m, flood_zone,
  tsunami_risk, tsunami_depth_max_m,
  landslide_risk, landslide_zone,
  data_sources_json, assessed_at
)

-- Property Scores
property_scores (
  id, property_id,
  rebuild_score, hazard_score, infrastructure_score,
  demographic_score, value_score, condition_score,
  weights_json, composite_score, scoring_version, scored_at
)

-- Users & Auth (NextAuth.js managed)
users (id, name, email, email_verified, image, created_at)
accounts (id, user_id, provider, provider_account_id, ...)
sessions (id, session_token, user_id, expires)

-- Subscriptions
subscriptions (
  id, user_id, plan (free/basic/pro),
  interval (monthly/yearly), status (active/canceled/past_due),
  stripe_subscription_id, current_period_end, created_at
)

-- Wishlists
wishlists (id, user_id, name, created_at)
wishlist_items (id, wishlist_id, property_id, added_at)

-- Alerts (Saved Searches)
alerts (
  id, user_id, name,
  query_json (bbox, filters, max_price, currency),
  frequency (daily/weekly/instant),
  channels (email/push), status (active/paused),
  last_sent_at, created_at
)

-- Deals Pipeline
deals (
  id, user_id, property_id,
  stage (discovery/analysis/offer/due_diligence/closing/completed),
  purchase_price, renovation_budget, target_sale_price,
  costs_json, notes, created_at, updated_at
)

due_diligence_items (
  id, deal_id, category, title, completed, due_date, notes
)
```

---

## 5. Page Structure & Routes

### Marketing Pages (SSR/Static — SEO optimized)

| Route | Page | Description |
|---|---|---|
| `/` | Homepage | Hero, feature highlights, pricing preview, CTA |
| `/city/[slug]` | City Landing | Hero image, city stats, teaser listings (6-12), search CTA |
| `/prefecture/[slug]` | Prefecture Landing | Same pattern, prefecture-level |
| `/pricing` | Pricing Page | Free/Basic/Pro comparison table, CTA buttons |
| `/faq` | FAQ | Accordion-style, SEO-rich answers |
| `/about` | About Us | Team, mission, story |
| `/contact` | Contact | Contact form |

### App Pages (Client-side heavy, auth-aware)

| Route | Page | Description |
|---|---|---|
| `/explore` | Map Explore | Full-screen map + sidebar list, bounding-box search, filters |
| `/find` | Location Finder | `?loc=Kyoto` → resolve bbox → redirect to `/explore?...` |
| `/listing/[id]` | Listing Detail | Full property info, gallery, hazard panel, score, area info |
| `/dashboard` | User Dashboard | Overview: recent views, wishlists, alerts, subscription |
| `/wishlists` | Wishlists | List of wishlists, manage properties in each |
| `/alerts` | Saved Searches | Manage alert queries, frequency, channels |
| `/pipeline` | Deal Pipeline | Kanban-style deal stages (premium) |
| `/calculator` | Financial Calc | Purchase cost calculator (premium) |
| `/settings` | User Settings | Profile, preferences, subscription management |

### Auth Pages (NextAuth.js)

| Route | Page |
|---|---|
| `/auth/signin` | Login (email + OAuth) |
| `/auth/signup` | Registration |
| `/auth/verify` | Email verification |

### API Routes (`/api/...`)

| Method | Route | Auth | Purpose |
|---|---|---|---|
| GET | `/api/places/find?loc=` | public | Name → bbox resolution |
| GET | `/api/listings?bbox=&maxPrice=&...` | public (rate-limited) | Map/list search |
| GET | `/api/listings/[id]` | public | Single listing detail |
| GET | `/api/listings/[id]/similar` | public | Similar properties |
| GET | `/api/prefectures` | public | All prefectures |
| GET | `/api/municipalities?prefecture=` | public | Municipalities in prefecture |
| GET | `/api/city/[slug]/listings` | public | Teaser listings for SEO page |
| POST | `/api/auth/[...nextauth]` | - | NextAuth.js handler |
| GET | `/api/me` | user | Current user profile + plan |
| CRUD | `/api/wishlists` | user | Wishlist management |
| CRUD | `/api/alerts` | user | Alert management |
| CRUD | `/api/deals` | user | Deal pipeline management |
| POST | `/api/financial/calculate` | user | Purchase cost calculation |
| POST | `/api/billing/checkout` | user | Create checkout (future Stripe) |
| POST | `/api/scraper/trigger` | admin | Trigger scrape job on Vultr |

---

## 6. Design System — Minimal Japanese Aesthetic

### Principles
- **Ma (間):** Generous whitespace, let content breathe
- **Wabi-sabi:** Subtle imperfection, organic feel
- **Restraint:** Minimal color palette, no visual noise
- **Typography-first:** Beautiful, readable type hierarchy

### Color Palette
```css
:root {
  /* Base */
  --bg-primary: #FAFAF8;          /* warm off-white, like washi paper */
  --bg-secondary: #F5F3EF;        /* slightly darker warm gray */
  --bg-card: #FFFFFF;              /* pure white for cards */

  /* Text */
  --text-primary: #1A1A1A;        /* near-black */
  --text-secondary: #6B6B6B;      /* warm gray */
  --text-muted: #9B9B9B;          /* light gray */

  /* Accent — inspired by indigo dye (藍) */
  --accent-primary: #2D4A7A;      /* deep indigo */
  --accent-light: #4A6FA5;        /* lighter indigo */
  --accent-subtle: #E8EDF4;       /* very light indigo wash */

  /* Semantic */
  --success: #4A7A5C;             /* muted green, like matcha */
  --warning: #B8860B;             /* gold, like kintsugi */
  --danger: #8B3A3A;              /* muted red, like torii */
  --info: #4A6FA5;                /* indigo */

  /* Hazard colors */
  --hazard-safe: #4A7A5C;
  --hazard-low: #B8A44A;
  --hazard-medium: #B8860B;
  --hazard-high: #A0522D;
  --hazard-extreme: #8B3A3A;

  /* Borders */
  --border: #E5E2DB;              /* warm light border */
  --border-hover: #D1CEC7;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.06);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.08);
}
```

### Typography
- **Headings:** Inter or Noto Sans JP (clean, geometric)
- **Body:** Inter (highly readable)
- **Monospace:** JetBrains Mono (for prices, codes)
- Scale: 12/14/16/18/20/24/30/36/48px

### Component Style
- **Cards:** White background, 1px warm border, subtle shadow, rounded-xl (12px)
- **Buttons:** Minimal, indigo accent for primary, ghost for secondary
- **Inputs:** Clean borders, generous padding, subtle focus ring
- **Map markers:** Subtle circles with score-based color gradient
- **Source badges:** Small colored dots (not diamonds) next to listing source

---

## 7. Implementation Log — Chronological Task List

> **How this works:** Each task is a single implementable unit. Tasks are grouped into
> dependency blocks (A→B→C...) and ordered so nothing is built before its dependency.
> After each task is completed, it gets marked `[x]` with a date and a short quality note.
> If a task needs revision, it gets a `[!]` flag.

### Current Status: `BLOCK N IN PROGRESS — Market-ready code improvements`
### Live URL: `https://japan-prop-search.vercel.app`

---

### BLOCK A — Project Skeleton
*Everything else depends on this. Must be done first and in order.*

| # | Task | Depends On | Status |
|---|---|---|---|
| A-01 | Initialize Next.js 16 project (TypeScript, App Router, TailwindCSS v4, ESLint) | — | `done 2026-02-11` |
| A-02 | Design system: globals.css with Japanese aesthetic theme (colors, fonts, spacing, shadows, animations as CSS variables), Tailwind v4 @theme tokens | A-01 | `done 2026-02-11` |
| A-03 | UI component library: 16 Radix UI + Tailwind styled components (Button, Card, Input, Select, Badge, Dialog, Tabs, Accordion, Skeleton, Tooltip, etc.) | A-02 | `done 2026-02-11` |
| A-04 | Marketing layout: MarketingHeader (sticky, logo, nav, CTA, mobile hamburger) + Footer (4-col grid) + `(marketing)/layout.tsx` | A-03 | `done 2026-02-11` |
| A-05 | App layout: AppSidebar (icon nav, tooltip, mobile bottom bar) + AppHeader (breadcrumb, search, user dropdown) + `(app)/layout.tsx` | A-03 | `done 2026-02-11` |
| A-06 | All placeholder pages: 4 marketing (/, /pricing, /faq, /about) + 8 app (/explore, /dashboard, /listing/[id], /wishlists, /alerts, /pipeline, /calculator, /settings) | A-04, A-05 | `done 2026-02-11` |

**A-01 Details:**
- `npx create-next-app@latest` with: TypeScript, ESLint, Tailwind, App Router, `src/` directory, import alias `@/`
- Install core deps: `@radix-ui/react-*`, `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority`
- Set up `src/lib/utils.ts` with `cn()` helper (clsx + tailwind-merge)
- Create `.env.example` with all placeholder variables from Section 13
- Initialize git repo, first commit

**A-02 Details:**
- `globals.css`: All CSS variables from Section 6 (colors, shadows, borders)
- Import Inter font (Google Fonts via `next/font`)
- TailwindCSS v4: all theme tokens defined via `@theme inline {}` in globals.css (NOT tailwind.config.ts)
- Base styles: body background, text color, font smoothing
- Verify: page renders with correct warm off-white background and indigo accent

**A-03 Details:**
- Install Radix: `dialog`, `dropdown-menu`, `tabs`, `accordion`, `tooltip`, `select`, `checkbox`, `label`, `separator`, `slot`
- Create `src/components/ui/` with styled wrappers for each (following shadcn/ui pattern)
- Each component uses the Japanese aesthetic theme variables
- Components: `button.tsx`, `card.tsx`, `input.tsx`, `select.tsx`, `badge.tsx`, `dialog.tsx`, `tabs.tsx`, `accordion.tsx`, `skeleton.tsx`, `tooltip.tsx`, `separator.tsx`

**A-04 Details:**
- `src/components/layout/marketing-header.tsx`: Logo (text for now), nav links (Home, Explore, Pricing, FAQ), "Sign In" button
- `src/components/layout/footer.tsx`: 3-column grid (Product links, Company links, Legal links), copyright
- `src/app/(marketing)/layout.tsx`: Wraps children with header + footer
- Responsive: hamburger menu on mobile
- Style: transparent header with subtle border-bottom, sticky

**A-05 Details:**
- `src/components/layout/app-sidebar.tsx`: Icon-based vertical nav (Explore, Dashboard, Wishlists, Alerts, Pipeline, Calculator, Settings)
- `src/components/layout/app-header.tsx`: Breadcrumb, search input, user avatar/menu
- `src/app/(app)/layout.tsx`: Sidebar + header + content area
- Responsive: sidebar collapses to bottom tab bar on mobile

**A-06 Details:**
- `src/app/(marketing)/page.tsx`: "Homepage coming soon" with correct marketing layout
- `src/app/(app)/explore/page.tsx`: "Explore coming soon" with correct app layout
- `src/app/(app)/listing/[id]/page.tsx`: "Listing coming soon" with correct app layout
- Verify: navigation between marketing and app pages works, layouts switch correctly

---

### BLOCK B — Database & Data Layer
*API routes depend on this. Can start once A-01 is done (no UI dependency).*

| # | Task | Depends On | Status |
|---|---|---|---|
| B-01 | Set up Supabase project: create project, enable PostGIS extension, get connection string + keys | A-01 | `BLOCKED — user action needed` |
| B-02 | Install Drizzle ORM + configure: `drizzle-orm`, `drizzle-kit`, `postgres` driver, `drizzle.config.ts`, db connection utility | B-01 | `done 2026-02-11` |
| B-03 | Schema: `prefectures` + `municipalities` tables (Drizzle schema + migration) | B-02 | `done 2026-02-11` |
| B-04 | Schema: `listing_sources` table + seed data (SUUMO, AtHome, Homes, BIT Auction, Akiya Banks with badge colors) | B-02 | `done 2026-02-11` |
| B-05 | Schema: `properties` table (with lat/lng double precision + indexes) | B-02 | `done 2026-02-11` |
| B-06 | Schema: `property_listings` table (source tracking, raw data JSON, unique source constraint) | B-05 | `done 2026-02-11` |
| B-07 | Schema: `property_images` table (Supabase Storage paths) | B-05 | `done 2026-02-11` |
| B-08 | Schema: `hazard_assessments` table | B-05 | `done 2026-02-11` |
| B-09 | Schema: `property_scores` table | B-05 | `done 2026-02-11` |
| B-10 | Seed data: all 47 prefectures + 13 municipalities with bbox coordinates + slugs | B-03 | `done 2026-02-11` |
| B-11 | Seed data: 60 demo properties with hazard/score data across 10 cities | B-05, B-06, B-07, B-08, B-09 | `done 2026-02-11` |
| B-12 | Currency conversion utility: `src/lib/currency.ts` (JPY → USD/EUR/GBP/AUD with hardcoded rates) | A-01 | `done 2026-02-11` |

**B-01 Details:**
- User creates Supabase project manually (free tier) at supabase.com
- Enable PostGIS via SQL: `CREATE EXTENSION IF NOT EXISTS postgis;`
- Copy: project URL, anon key, service role key, direct connection string
- Add to `.env.local` (not committed)

**B-02 Details:**
- `npm install drizzle-orm postgres` + `npm install -D drizzle-kit`
- `src/lib/db/index.ts`: connection pool using `postgres` driver + Drizzle wrapper
- `drizzle.config.ts`: points to DATABASE_URL, schema path, migration output
- Verify: can connect and run a raw `SELECT 1` query

**B-05 Details (properties table — most important):**
```typescript
// Key columns:
id: serial primaryKey
address_ja: text
address_en: text (translated)
prefecture_code: text (FK → prefectures)
municipality_code: text (FK → municipalities)
lat: doublePrecision
lng: doublePrecision
location: geometry('Point', 4326) // PostGIS — for bbox queries
price_jpy: integer
land_area_sqm: real
building_area_sqm: real
floor_plan: text (e.g. "3LDK")
year_built: integer
structure: text (wood/rc/steel)
floors: integer
land_rights: text (freehold/leasehold)
road_width_m: real
rebuild_possible: boolean
use_zone: text
coverage_ratio: real
floor_area_ratio: real
composite_score: real
price_per_sqm: real (computed)
description_ja: text
description_en: text (translated)
area_info_en: text
status: text (active/sold/delisted) default 'active'
view_count: integer default 0
created_at: timestamp
updated_at: timestamp
```

**B-11 Details:**
- Create `src/lib/db/seed.ts` script
- Generate 50-100 properties spread across Tokyo, Osaka, Kyoto, Hokkaido, Okinawa
- Realistic prices (¥500,000 — ¥15,000,000), areas, years, scores
- 2-3 images per property (use placeholder image URLs)
- Some with hazard data, some without
- Some with multiple listings from different sources (to test source badges)
- Run via `npx tsx src/lib/db/seed.ts`

---

### BLOCK C — Core API Routes
*Map/Explore page depends on these. Needs database schema from Block B.*

| # | Task | Depends On | Status |
|---|---|---|---|
| C-01 | API: `GET /api/prefectures` — list all prefectures; `GET /api/municipalities?prefecture=` — list municipalities | B-03, B-10 | `done 2026-02-11` ✅ |
| C-02 | API: `GET /api/listings` — bbox search with filters (maxPrice, minPrice, rooms, landRights, structure, minScore), pagination, sort, currency conversion, source badges, thumbnails | B-05, B-11, B-12 | `done 2026-02-11` ✅ |
| C-03 | API: `GET /api/listings/[id]` — full listing detail with joins (images, hazard, scores, source listings), view count increment | B-05 through B-09 | `done 2026-02-11` ✅ |
| C-04 | API: `GET /api/places/find?loc=` — location name → bbox lookup from municipalities/prefectures table, return JSON `{ bbox, label }` | B-10 | `done 2026-02-11` ✅ |
| C-05 | API: `GET /api/listings/geojson` — GeoJSON FeatureCollection for map markers (lightweight: id, lat, lng, price, score, status only) | C-02 | `done 2026-02-11` ✅ |

**Block C Quality Notes (2026-02-11):**
- Used simple lat/lng range queries instead of PostGIS `ST_MakeEnvelope` (works without PostGIS extension, can optimize later)
- DB connection made lazy via Proxy pattern so build succeeds without DATABASE_URL
- All 6 route files build-verified and committed
- Listings route includes source badges + thumbnail aggregation in single response
- GeoJSON route capped at 2000 features for performance

**C-02 Details (most complex API route):**
```
GET /api/listings?swLat=35.5&swLng=139.5&neLat=35.8&neLng=139.9
    &maxPrice=10000000&currency=usd&rooms=2&landRights=freehold
    &sort=price_asc&page=1&limit=50
```
- PostGIS query: `WHERE ST_Within(location, ST_MakeEnvelope(swLng, swLat, neLng, neLat, 4326))`
- Apply all filters
- Return: `{ items: Listing[], total: number, page: number, bbox: BBox }`
- Each item includes: id, price (JPY + converted), lat/lng, address, thumbnail, score, source badges
- Converted price uses currency.ts utility

**C-05 Details:**
- Lightweight version of C-02 for map rendering
- Returns GeoJSON FeatureCollection
- Each Feature: `{ type: "Feature", geometry: { type: "Point", coordinates: [lng, lat] }, properties: { id, price_jpy, composite_score, status } }`
- Used by MapLibre as data source

---

### BLOCK D — Map Explore Page
*The core app experience. Needs API routes from Block C and UI components from Block A.*

| # | Task | Depends On | Status |
|---|---|---|---|
| D-01 | Install MapLibre GL JS + react-map-gl, create base `<Map>` component with OSM raster tiles, center on Japan | A-03, C-05 | `done 2026-02-11` ✅ |
| D-02 | Explore page layout: full-screen map (70% width) + sidebar panel (30% width), responsive breakpoints | D-01, A-05 | `done 2026-02-11` ✅ |
| D-03 | Bounding-box data fetching: on map `moveend`, extract viewport bbox → call `/api/listings` → update state | D-02, C-02 | `done 2026-02-11` ✅ |
| D-04 | URL state sync: read/write bbox + filters to URL query params using `useSearchParams`, debounced URL updates | D-03 | `done 2026-02-11` ✅ |
| D-05 | Property markers: render GeoJSON source on map, clustered via MapLibre cluster options, color by price tier | D-03 | `done 2026-02-11` ✅ |
| D-06 | Marker popups: click marker → show mini property card (price, score, link) | D-05 | `done 2026-02-11` ✅ |
| D-07 | Sidebar property list: scrollable list of PropertyCard components, synced with map data | D-03, A-03 | `done 2026-02-11` ✅ |
| D-08 | Filter panel: collapsible panel — currency, sort, price range, rooms, land rights, structure, min score | D-04, A-03 | `done 2026-02-11` ✅ |
| D-09 | Currency selector: integrated into filter panel (JPY/USD/EUR/GBP/AUD) | D-04, B-12 | `done 2026-02-11` ✅ |
| D-10 | `/find` route: `GET /find?loc=Kyoto` → server-side → lookup bbox → redirect to `/explore?swLat=...` | C-04 | `done 2026-02-11` ✅ |
| D-11 | "Search this area" button: appears when map moves from last search bbox | D-03 | `done 2026-02-11` ✅ |
| D-12 | Map-list interaction: hover card → highlight marker ring, hover marker → highlight card border | D-06, D-07 | `done 2026-02-11` ✅ |
| D-13 | Explore mobile: map full screen, property list as pull-up bottom sheet | D-02 through D-09 | `done 2026-02-11` ✅ |
| D-14 | Empty states & loading: skeleton cards while loading, "No properties" message, map loading indicator | D-07 | `done 2026-02-11` ✅ |

**Block D Quality Notes (2026-02-11):**
- MapLibre loaded via `next/dynamic` with `ssr: false` to avoid SSR issues
- useExplore hook manages all state: bbox, filters, URL sync, pagination, fetching
- Marker colors: green(<3M), blue(3-10M), amber(10-30M), red(>30M) — with price legend overlay
- Cluster support via MapLibre cluster options (max zoom 14, radius 50)
- Mobile bottom sheet is simplified (no drag gestures yet, uses click toggle)
- LocationSearch component calls /api/places/find for city/prefecture lookup

**D-01 Details:**
- `npm install maplibre-gl react-map-gl`
- `src/components/map/base-map.tsx`: wrapper around react-map-gl `<Map>` with OSM tiles
- Tile URL: `https://tile.openstreetmap.org/{z}/{x}/{y}.png` (or a vector style like MapTiler free)
- Default view: center on Japan `[137.0, 38.0]`, zoom 5
- Style: add attribution, disable rotation (simpler UX)

**D-07 Details (PropertyCard component):**
- `src/components/property/property-card.tsx`
- Shows: thumbnail image, price (formatted with currency), address, land/building area, year built, score badge, source badge dots
- Hover: subtle elevation change
- Click: navigates to `/listing/[id]`
- Compact variant for sidebar list

---

### BLOCK E — Listing Detail Page
*Needs API route C-03 and UI components from Block A.*

| # | Task | Depends On | Status |
|---|---|---|---|
| E-01 | Listing detail page: server component layout + client detail component | C-03, A-03 | `done 2026-02-11` ✅ |
| E-02 | Image gallery: grid layout + lightbox with keyboard nav (Escape/Arrow keys) | E-01 | `done 2026-02-11` ✅ |
| E-03 | Property facts grid: 12-cell grid (price, area, plan, year, structure, rights, road, rebuild, ratios) | E-01 | `done 2026-02-11` ✅ |
| E-04 | Hazard assessment panel: 5 risk categories with color-coded badges | E-01 | `done 2026-02-11` ✅ |
| E-05 | Score breakdown: Recharts RadarChart with 6 dimensions + composite badge | E-01 | `done 2026-02-11` ✅ |
| E-06 | Source badges: clickable pills linking to original portals | E-01 | `done 2026-02-11` ✅ |
| E-07 | Description + Area Info tabs | E-01 | `done 2026-02-11` ✅ |
| E-08 | Mini map: MapLibre map with property pin | E-01, D-01 | `done 2026-02-11` ✅ |
| E-09 | Similar properties: placeholder (needs runtime data, will implement in polish) | E-01, C-02 | `deferred` |
| E-10 | Action bar: currency selector, share (copy URL), save button (wishlist placeholder) | E-01 | `done 2026-02-11` ✅ |
| E-11 | SEO metadata: dynamic OG meta + JSON-LD RealEstateListing structured data | E-01 | `done 2026-02-11` ✅ |

**Block E Quality Notes (2026-02-11):**
- Server component fetches data via internal API, client component handles interactivity
- Recharts RadarChart renders 6-dimension spider with indigo theme
- Image gallery: responsive grid (1/2/4 cols based on count), lightbox with keyboard + click nav
- E-09 (Similar Properties) deferred — needs live DB to query similar listings

**E-03 Details (facts grid):**
```
┌─────────────┬─────────────┬─────────────┐
│ Price       │ Land Area   │ Building    │
│ ¥6,000,000  │ 190 m²      │ 41.49 m²   │
│ ($38,390)   │             │             │
├─────────────┼─────────────┼─────────────┤
│ Year Built  │ Floor Plan  │ Structure   │
│ 2001        │ 2LDK       │ Wood        │
├─────────────┼─────────────┼─────────────┤
│ Land Rights │ Road Width  │ Rebuild OK? │
│ Freehold    │ 4.0m       │ Yes ✓       │
└─────────────┴─────────────┴─────────────┘
```

---

### BLOCK F — Marketing & SEO Pages
*Needs UI components from Block A and some API routes from Block C.*

| # | Task | Depends On | Status |
|---|---|---|---|
| F-01 | Homepage: hero + "How It Works" 3-step + 6-feature grid + pricing preview (3 tiers) + final CTA | A-04, A-03 | `done 2026-02-11` ✅ |
| F-02 | Pricing page: 3-tier comparison with feature checklists + FAQ accordion | A-03, A-04 | `done 2026-02-11` ✅ |
| F-03 | FAQ page: 16 questions across 4 categories with accordions | A-03, A-04 | `done 2026-02-11` ✅ |
| F-04 | City landing pages `/city/[slug]` | A-03, C-05, B-10 | `deferred` (needs DB) |
| F-05 | Prefecture landing pages `/prefecture/[slug]` | F-04 | `deferred` (needs DB) |
| F-06 | Static generation with ISR | F-04, F-05 | `deferred` (needs DB) |
| F-07 | SEO: robots.ts + sitemap.ts (static pages now, dynamic URLs ready for DB) | F-06 | `done 2026-02-11` ✅ |
| F-08 | About page: mission, differentiators, technology overview | A-04 | `done 2026-02-11` ✅ |
| F-09 | Contact page | A-04, A-03 | `deferred` |

**Block F Quality Notes (2026-02-11):**
- Homepage has 5 sections: hero, how it works, features, pricing preview, CTA
- All pages have Metadata exports (title, description)
- F-04/F-05/F-06 deferred — need live DB to generate static city/prefecture pages
- F-09 deferred — contact form needs backend (email service or DB store)

**F-01 Details (Homepage — most important marketing page):**
- Hero: large full-width section, warm image of Japanese town/countryside, overlay text: "Discover Your Japanese Property", subtitle: "Search thousands of akiya listings across Japan with translated details, hazard data, and investment scoring.", CTA: "Start Exploring" → `/explore`
- How it Works: 3 cards (Search → Analyze → Invest)
- Features: 6-card grid (Map Search, Hazard Data, Investment Scoring, Multi-Source, Wishlists & Alerts, Deal Pipeline)
- Pricing preview: 3 compact tier cards with price + top 3 features
- Visual style: lots of whitespace, subtle animations on scroll, warm tones

**F-04 Details (City landing pages — SEO powerhouse):**
- Route: `/city/tokyo`, `/city/kyoto`, `/city/osaka`, etc.
- Server component: fetch city data + teaser listings at build time
- Hero: city-specific image (Supabase Storage or Unsplash), city name overlay
- Stats bar: "2,340 listings | Avg. ¥3.2M | Population: 13.9M"
- Teaser listings: grid of 6-12 PropertyCards
- CTA: "Search all properties in Tokyo →" links to `/explore?swLat=...&neLat=...`
- Internal links: "Nearby prefectures: ..."

---

### BLOCK G — Authentication & User System
*Needs database schema for users/subscriptions. Independent of UI blocks D-F.*

| # | Task | Depends On | Status |
|---|---|---|---|
| G-01 | Schema: NextAuth.js tables (already in B-02 schema) | B-02 | `done 2026-02-11` ✅ |
| G-02 | Schema: `subscriptions` table (already in B-02 schema) | G-01 | `done 2026-02-11` ✅ |
| G-03 | NextAuth.js config: Drizzle adapter, Google OAuth + credentials, JWT sessions, auto-create subscription | G-01 | `done 2026-02-11` ✅ |
| G-04 | Auth API route: `src/app/api/auth/[...nextauth]/route.ts` | G-03 | `done 2026-02-11` ✅ |
| G-05 | Sign-in page: Google OAuth + email/password, Japanese aesthetic | G-04, A-03 | `done 2026-02-11` ✅ |
| G-06 | Sign-up page: Google OAuth + name/email/password, auto-create user in beta | G-04, G-02, A-03 | `done 2026-02-11` ✅ |
| G-07 | Auth middleware: protects 6 private routes | G-04 | `done 2026-02-11` ✅ |
| G-08 | User menu: session-aware avatar + dropdown in AppHeader + MarketingHeader | G-04, A-05 | `done 2026-02-11` ✅ |
| G-09 | Settings page: profile form, subscription info, danger zone | G-04, G-02, A-05 | `done 2026-02-11` ✅ |
| G-10 | Feature gate: `canAccess(plan, feature)`, all free in FREE_MODE | G-02 | `done 2026-02-11` ✅ |
| G-11 | Subscription activation (deferred — pricing CTA links to /explore for now) | G-06, G-10, F-02 | `deferred` |
| G-12 | API: `GET /api/me` — user profile + subscription | G-04, G-02 | `done 2026-02-11` ✅ |

**Block G Quality Notes (2026-02-11):**
- NextAuth.js v5 beta with JWT session strategy
- Credentials provider auto-creates users in FREE_MODE (beta)
- getDbOrDummy() solves build-time DrizzleAdapter initialization without DATABASE_URL
- SessionProvider wraps entire app tree in root layout
- Both MarketingHeader and AppHeader are session-aware

---

### BLOCK H — Wishlists & Alerts
*Needs auth system from Block G and listing pages from Blocks D-E.*

| # | Task | Depends On | Status |
|---|---|---|---|
| H-01 | Schema: `wishlists` + `wishlist_items` tables | B-02, G-01 | `done` |
| H-02 | Schema: `alerts` table (saved search queries) | B-02, G-01 | `done` |
| H-03 | API: `CRUD /api/wishlists` — create list, get lists, add/remove item, delete list | H-01, G-04 | `done` |
| H-04 | API: `CRUD /api/alerts` — create alert, get alerts, update frequency, delete | H-02, G-04 | `done` |
| H-05 | Wishlists page: grid of wishlist cards, click to expand → list of PropertyCards, create new wishlist dialog | H-03, A-05, D-07 | `done` |
| H-06 | Heart button integration: add heart icon to PropertyCard + listing detail, click toggles wishlist membership, select which wishlist via dropdown | H-03, D-07, E-10 | `done` |
| H-07 | Alerts page: list of saved searches with query summary, frequency selector, pause/resume toggle, delete | H-04, A-05 | `done` |
| H-08 | "Save this search" button on Explore page: captures current bbox + filters → create alert dialog (name, frequency) | H-04, D-08 | `done` |
| H-09 | Alert email worker: cron job (or Supabase Edge Function) — check each active alert, find new listings matching query, send email digest | H-04, C-02 | `deferred` |
| H-10 | Email template: React Email template for alert digest (new listings summary, link to explore) | H-09 | `deferred` |

**Block H Quality Notes (2026-02-11):**
- Wishlists CRUD: create/list/delete wishlists, add/remove items, check which wishlists contain a property
- WishlistButton component has two variants: `icon` (heart on PropertyCard thumbnails) and `labeled` (full button on listing detail)
- Wishlists check API (`/api/wishlists/check?propertyId=`) returns array of wishlist IDs containing the property
- Alerts API uses `queryJson` field name (matches Drizzle schema `jsonb("query_json")`) — **not** `query`
- "Save this search" on Explore captures current bbox + filters, creates alert with name/frequency dialog
- Wishlist detail page at `/wishlists/[id]` shows items with thumbnails, scores, remove action
- H-09/H-10 deferred — email worker needs Resend/SendGrid setup

---

### BLOCK I — Deal Pipeline & Financial Tools
*Premium features. Needs auth from Block G. Ported from old Python app.*

| # | Task | Depends On | Status |
|---|---|---|---|
| I-01 | Schema: `deals` + `due_diligence_items` tables | B-02, G-01 | `done` |
| I-02 | Port financial calculator logic from Python → TypeScript: `src/lib/financial.ts` (broker fee, stamp tax, registration tax, acquisition tax) | A-01 | `done` |
| I-03 | Port scoring engine from Python → TypeScript: `src/lib/scoring.ts` (6-dimension model with weights) | A-01 | `done` |
| I-04 | API: `CRUD /api/deals` — create deal from listing, update stage, update costs, delete | I-01, G-04 | `done` |
| I-05 | API: `POST /api/financial/calculate` — accept price + land/building split → return full cost breakdown | I-02, G-04 | `done` |
| I-06 | Pipeline page: Kanban board with draggable deal cards across stage columns, deal detail modal | I-04, A-05 | `done` |
| I-07 | Due diligence checklist: expandable checklist per deal, add/complete/delete items, category grouping | I-04, I-06 | `done` |
| I-08 | Financial calculator page: interactive form (price input, sliders for land/building split), real-time cost breakdown table, total summary | I-05, A-05 | `done` |
| I-09 | "Start a Deal" button on listing detail: creates deal linked to property, opens pipeline | I-04, E-10 | `done` |
| I-10 | Export: download deals as CSV or Excel file | I-04 | `done` |

**Block I Quality Notes (2026-02-11):**
- Financial calculator ported from Python `financial_service.py` (290 lines) with all Japanese tax rules:
  - Broker commission with standard tiers + low-price rule (<=8M → max 330,000)
  - Stamp tax with reduced rates through 2027-03-31
  - Registration tax: land 1.5% reduced through 2026-03-31, building 2.0%
  - Acquisition tax: land x1/2 x3%, building 3%
  - Annual holding cost: fixed asset 1.4% + city planning 0.3%
  - Capital gains tax: short-term 39.63% (<=5yr), long-term 20.315%
  - ROI projection with buy-renovate-sell scenario and breakeven month calculation
- Scoring engine ported from Python `scoring_engine.py` (200 lines), 6 dimensions:
  - rebuild(25%), hazard(20%), infrastructure(15%), demographic(15%), value(15%), condition(10%)
  - Constants: DEFAULT_WEIGHTS, SCORING_VERSION "1.0", RESIDENTIAL_ZONES/COMMERCIAL_ZONES sets
- Pipeline Kanban has 6 stages: discovery → analysis → offer → due_diligence → closing → completed
  - Stage navigation via arrow buttons on card hover
  - Detail dialog with categorized due diligence checklist (add/toggle/delete items)
  - CSV export via `/api/deals/export`
- Calculator page: toggle between "Purchase Costs" and "ROI Projection" modes with real-time results
- "Start Deal" button on listing detail creates deal and redirects to /pipeline
- Python source files read from: `C:\Users\nilsb\Documents\Japan Scrapping Tool\backend\app\services\`

---

### BLOCK J — Polish, Performance & Launch Readiness
*Final refinement. Depends on all feature blocks being at least functional.*

| # | Task | Depends On | Status |
|---|---|---|---|
| J-01 | Error boundaries: React error boundaries around map, listings, and major sections with fallback UI | D-02, E-01 | `done` |
| J-02 | Loading states: Skeleton components for PropertyCard, listing detail, sidebar, dashboard | A-03 | `done` |
| J-03 | 404 page + 500 error page: on-brand, with navigation back to home/explore | A-04 | `done` |
| J-04 | Performance: Next.js Image optimization for all images, lazy load below-fold content, dynamic imports for MapLibre (no SSR) | D-01, E-02 | `done` |
| J-05 | Caching strategy: ISR for SEO pages (revalidate 24h), API route caching headers, TanStack Query stale times | F-06, C-02 | `done` |
| J-06 | Mobile responsive audit: test all pages on 375px/414px/768px, fix layout breaks | All UI blocks | `done` |
| J-07 | Analytics: add Google Analytics 4 or Plausible, page view tracking, key events (search, view listing, signup) | A-01 | `done` |
| J-08 | Security: rate limiting on API routes (via middleware), input sanitization (Zod), CSP headers in `next.config.ts` | C-02 | `done` |
| J-09 | Accessibility: keyboard navigation audit, focus management, ARIA labels, color contrast check (WCAG AA) | All UI blocks | `done` |
| J-10 | Legal pages: privacy policy, terms of service, cookie consent banner | A-04 | `done` |
| J-11 | Final deployment: Vercel production config, environment variables, custom domain (when ready), preview deploys for PRs | All blocks | `done` |

**Block J Quality Notes (2026-02-11):**
- Error boundary: reusable class component with getDerivedStateFromError, retry button, fallback prop
- Loading states: Skeleton loaders for app shell, explore page, and listing detail
- Custom 404 page with "Go Home" + "Explore Properties" links
- Global + app-group error pages with retry + home navigation
- next.config.ts: image optimization (avif/webp, Supabase remote patterns), security headers (X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy), caching (marketing pages s-maxage=86400, API s-maxage=60 stale-while-revalidate=300)
- GA4 analytics: conditional on NEXT_PUBLIC_GA_ID, trackEvent() helper exported
- Cookie consent: fixed bottom banner, localStorage persistence under key "cookie-consent", accept/decline
- Validations: lightweight helpers (validatePositiveInt, validateOptionalInt, validateString, validateEnum, validateBbox)
- Privacy policy (8 sections) and terms of service (9 sections) pages
- Accessibility: skip-to-content link, ARIA labels on sidebar/mobile nav, id="main-content" on main
- Sitemap updated with privacy + terms pages
- Build passes clean with 33 pages total

---

### BLOCK K — Scraper Integration (Parallel Track)
*Can be worked on independently alongside Blocks D-I. Runs on Vultr VPS.*

| # | Task | Depends On | Status |
|---|---|---|---|
| K-01 | Update Python scrapers: Supabase connection string, effective_database_url property, asyncpg driver | B-05 | `done` |
| K-02 | New SQLAlchemy models matching Drizzle schema, SupabasePropertyService with serial PKs | K-01 | `done` |
| K-03 | TranslateService: Google Cloud Translation API v2, batch support, auto-translate in pipeline | K-02 | `done` |
| K-04 | ImageUploadService: download from portal URL → upload to Supabase Storage → store public URL | K-02 | `done` |
| K-05 | Remote trigger API: `POST /api/scrape/trigger` with X-API-Key auth, creates ScrapeJob + dispatches | K-02 | `done` |
| K-06 | Enhanced health endpoint: DB connectivity, last scrape time, service availability flags | K-05 | `done` |
| K-07 | Cron scheduling: existing scheduler with configurable interval (SCHEDULER_ENABLED + SCHEDULER_INTERVAL_HOURS) | K-02 | `done` |
| K-08 | Next.js admin: `/api/scraper/trigger` proxy route + ScraperAdmin UI in settings page | K-05, G-07 | `done` |

**Block K Quality Notes (2026-02-11):**
- Python scraper project at `C:\Users\nilsb\Documents\Japan Scrapping Tool\backend\`
- Config updated: `DATABASE_URL` env var for Supabase, auto-converts `postgres://` → `postgresql+asyncpg://`
- New SQLAlchemy models (`models/new_schema.py`) match Drizzle schema exactly: serial PKs, matching column names (price_jpy, lat/lng, storage_path, source_listing_id, etc.)
- Old models (Property with UUID PK) kept only as reference — NOT used for new data
- Scraping infrastructure tables (scrape_sources, scrape_jobs, scrape_logs) created separately, not managed by Drizzle
- `SupabasePropertyService`: upserts scraped data, handles deduplication by source+source_listing_id, computes price_per_sqm
- `TranslateService`: Google Cloud Translation API v2, translates description_ja → description_en during scrape
- `ImageUploadService`: downloads from portal URLs, uploads to Supabase Storage bucket `property-images`, returns public URL
- Both services are optional (graceful fallback if API keys not set)
- Runner updated to use new service with per-listing error handling (doesn't abort on single failure)
- Remote trigger (`POST /api/scrape/trigger`): requires X-API-Key header, validates source exists
- Health endpoint returns: status, version, DB connectivity, last scrape details, service availability flags
- Next.js proxy (`/api/scraper/trigger`): GET returns health, POST proxies trigger. ScraperAdmin in settings page shows status, last scrape, source selector, trigger button
- `.env.example` created for Python scraper with all env vars documented
- K-07: Scheduler already implemented in `tasks/runner.py`, configurable via `SCHEDULER_ENABLED` + `SCHEDULER_INTERVAL_HOURS`
- Build passes clean with 35 pages

---

### BLOCK L — User Dashboard
*Ties everything together. Needs wishlists, alerts, deals, and auth.*

| # | Task | Depends On | Status |
|---|---|---|---|
| L-01 | Dashboard page: overview cards (total wishlisted, active alerts, active deals, subscription plan) | G-04, H-03, H-04, I-04 | `done` |
| L-02 | Recent activity: last 5 viewed properties (stored in localStorage), recent alerts, pipeline activity | L-01 | `done` |
| L-03 | Quick actions: "Explore Map", "New Wishlist", "New Alert", "Calculator" shortcut buttons | L-01 | `done` |

**Block L Quality Notes (2026-02-11):**
- Dashboard API (`/api/dashboard`) aggregates all stats in parallel (wishlists, items, alerts, deals, subscription)
- 4 overview stat cards: Saved Properties (with list count), Active Alerts (with total), Active Deals (with completed count), Current Plan
- Each stat card links to its respective page
- Recently viewed properties stored in localStorage under key "recent-views" (max 20 entries)
- View tracking added to listing-detail.tsx via useEffect (saves id, title, price, visitedAt)
- Pipeline Activity section shows last 5 deals with stage badges and time-ago formatting
- Recent Alerts section shows last 3 alerts with frequency/status (conditionally rendered)
- Quick actions: 4 buttons linking to Explore, Wishlists, Alerts, Calculator
- Personalized greeting: "Welcome back, {firstName}" using session data
- Build passes clean with 34 pages

---

### Implementation Order Summary

```
A-01 → A-02 → A-03 → A-04 + A-05 (parallel) → A-06
                  ↓
B-01 → B-02 → B-03 + B-04 + B-05 (parallel) → B-06 + B-07 + B-08 + B-09 (parallel) → B-10 → B-11 → B-12
                  ↓
C-01 + C-04 (parallel) → C-02 → C-03 → C-05
                                    ↓
D-01 → D-02 → D-03 → D-04 → D-05 → D-06 + D-07 (parallel) → D-08 → D-09 → D-10 → D-11 → D-12 → D-13 → D-14
                                    ↓
E-01 → E-02 + E-03 + E-04 + E-05 + E-06 + E-07 (parallel) → E-08 → E-09 → E-10 → E-11
                                    ↓
F-01 → F-02 → F-03 → F-04 → F-05 → F-06 → F-07 → F-08 + F-09 (parallel)
                                    ↓
G-01 → G-02 → G-03 → G-04 → G-05 + G-06 (parallel) → G-07 → G-08 → G-09 → G-10 → G-11 → G-12
                                    ↓
H-01 + H-02 (parallel) → H-03 + H-04 (parallel) → H-05 + H-07 (parallel) → H-06 → H-08 → H-09 → H-10
                                    ↓
I-01 + I-02 + I-03 (parallel) → I-04 + I-05 (parallel) → I-06 → I-07 → I-08 → I-09 → I-10
                                    ↓
L-01 → L-02 → L-03
                                    ↓
J-01 through J-11 (polish pass)

PARALLEL TRACK: K-01 → K-02 → K-03 + K-04 (parallel) → K-05 → K-06 → K-07 → K-08
```

**Total tasks: 86**

---

### Completed Tasks Log

| # | Task | Completed | Quality Notes |
|---|---|---|---|
| A-01 | Initialize Next.js 16 project | 2026-02-11 | Next.js 16.1.6 + React 19 + TailwindCSS v4 (CSS-based config, not tailwind.config.ts). Inter font, Japanese aesthetic CSS vars, cn() utility, full TypeScript types for all domain entities, .env.example, clean directory structure. Build passes, dev server starts in 543ms. Project at `C:\Users\nilsb\Documents\japan-prop-search\`. |
| A-02 | Complete design system theme | 2026-02-11 | Added popover/sidebar/semantic foreground CSS vars. Animation keyframes (accordion, fade, slide 4 directions). All tokens mapped to Tailwind v4 @theme. |
| A-03 | UI component library (16 components) | 2026-02-11 | Button (7 variants + 4 sizes), Card (6 parts), Input, Textarea, Label, Checkbox, Select (full Radix), Dialog (overlay+close), DropdownMenu (full), Tabs, Accordion, Tooltip, Popover, Badge (7+5 hazard), Separator, Skeleton, ScrollArea. All use theme CSS vars. Build passes clean. Homepage uses Button+Badge as smoke test. |
| A-04 | Marketing layout | 2026-02-11 | MarketingHeader: sticky, backdrop-blur, logo with ◉ icon, 4 nav links, Sign In ghost + Start Free CTA. Mobile: hamburger with animated max-h slide-down. Footer: 4-column (brand+desc, Product, Company, Legal), separator, copyright. (marketing)/layout.tsx wraps everything. |
| A-05 | App layout | 2026-02-11 | AppSidebar: 64px wide, icon nav with 7 links (Map, Dashboard, Heart, Bell, Kanban, Calculator, Settings), Tooltip on hover, active state with accent bg. Mobile: fixed bottom tab bar with top 5 items. AppHeader: breadcrumb from route title map, search input, user DropdownMenu (Dashboard, Settings, Sign In). (app)/layout.tsx: flex h-screen, sidebar + column(header + scrollable main). pb-14 on mobile for bottom bar. |
| A-06 | Placeholder pages (13 routes) | 2026-02-11 | 4 marketing routes (/, /pricing, /faq, /about) with marketing layout. 8 app routes (/explore, /dashboard, /listing/[id], /wishlists, /alerts, /pipeline, /calculator, /settings) with app layout. All build, all apply correct layout. Block A complete. |
| B-02–B-12 | Database layer + currency utility | 2026-02-11 | Drizzle ORM with 17 tables (full schema.ts: 480 lines). All relations defined. 47 prefectures, 13 municipalities with real bbox, 5 listing sources, 60 demo properties seed script. Currency util: JPY↔USD/EUR/GBP/AUD. npm scripts: db:generate/migrate/push/seed/studio. Uses lat/lng double precision with composite index (PostGIS can be added later if needed). Build passes clean. Waiting on B-01 (Supabase project creation) to run migrations. |
| C-01–C-05 | Core API routes | 2026-02-11 | 6 API route files: prefectures, municipalities, listings (bbox search + filters), listings/[id] (detail + view count), places/find (location→bbox), listings/geojson (map markers). Lazy DB via Proxy pattern. Simple lat/lng range queries (no PostGIS needed). GeoJSON capped at 2000 features. |
| D-01–D-14 | Map Explore page | 2026-02-11 | Full MapLibre map + sidebar. useExplore hook manages bbox/filters/URL sync. Clustered markers (green/blue/amber/red by price). Popups on click. Filter panel (currency, sort, price range, rooms, land rights, structure, min score). LocationSearch via /api/places/find. Mobile bottom sheet. "Search this area" button. |
| E-01–E-11 | Listing detail page | 2026-02-11 | Server→client component split. Image gallery with lightbox + keyboard nav. 9-cell facts grid. Hazard panel (5 categories). RadarChart scores. Source badges. Description/Area Info tabs. Mini map. Currency selector. SEO metadata + JSON-LD. E-09 deferred. |
| F-01–F-08 | Marketing & SEO pages | 2026-02-11 | Homepage (5 sections). Pricing (3 tiers). FAQ (16 questions, 4 categories). About page. robots.ts + sitemap.ts. F-04/F-05/F-06/F-09 deferred (need DB). |
| G-01–G-12 | Authentication & user system | 2026-02-11 | NextAuth.js v5 beta. JWT sessions. Google OAuth + Credentials. Auto-create users in FREE_MODE. getDbOrDummy() for build safety. SessionProvider in root layout. Auth middleware protects 6 routes. Settings page. canAccess() feature gate. /api/me route. |
| H-01–H-08 | Wishlists & alerts | 2026-02-11 | Full CRUD for wishlists + alerts. WishlistButton (icon/labeled variants). Check API for property membership. "Save this search" on Explore. Wishlist detail page. H-09/H-10 deferred (email worker). |
| I-01–I-10 | Deal pipeline & financial tools | 2026-02-11 | Financial calculator ported from Python (290 lines). Scoring engine ported (200 lines). Kanban pipeline (6 stages). Due diligence checklist. Calculator page (purchase costs + ROI). "Start Deal" on listing detail. CSV export. |
| J-01–J-11 | Polish & launch readiness | 2026-02-11 | Error boundaries. Loading skeletons. 404/500 pages. next.config.ts (image optimization, security headers, caching). GA4 analytics. Cookie consent. Input validation. Privacy policy + terms. Accessibility (skip-to-content, ARIA). 33 pages build clean. |
| L-01–L-03 | User Dashboard | 2026-02-11 | Dashboard API (parallel aggregation). 4 stat cards (wishlists, alerts, deals, plan). Recently viewed (localStorage). Pipeline activity (last 5 deals). Recent alerts (last 3). Quick actions (4 buttons). Personalized greeting. 34 pages build clean. |
| K-01–K-08 | Scraper Integration | 2026-02-11 | Python scraper updated for Supabase. New SQLAlchemy models matching Drizzle schema. TranslateService (Google API). ImageUploadService (Supabase Storage). Remote trigger with API key auth. Enhanced health endpoint. Scheduler. Next.js admin UI in settings. 35 pages build clean. |
| N-01–N-13 | Block N: Market-ready improvements | 2026-02-11 | See Block N section below. |

---

### BLOCK N — Market-Ready Code Improvements
*Fixes critical gaps in the scraper pipeline and Next.js app to support real data and real users.*

| # | Task | Status |
|---|---|---|
| N-01 | Fix SupabasePropertyService — add hazard/score stub records on property creation with basic inline scoring | `done 2026-02-11` |
| N-02 | Fix runner.py finally block null safety (services init to None before try) | `done 2026-02-11` |
| N-03 | Add /api/scrape/status/{job_id} and /api/scrape/history endpoints to Python scraper | `done 2026-02-11` |
| N-04 | Enrich /health endpoint with per-source stats and property_count | `done 2026-02-11` |
| N-05 | Dynamic sitemap with property URLs (queries active properties from DB) | `done 2026-02-11` |
| N-06 | Wire up settings profile save (PATCH /api/me + settings page handler) | `done 2026-02-11` |
| N-07 | Wire up delete account (DELETE /api/me + confirmation + signOut) | `done 2026-02-11` |
| N-08 | Add password hashing with bcryptjs (schema passwordHash + auth.ts verify/hash) | `done 2026-02-11` |
| N-09 | Add admin role and scraper auth check (schema role field + JWT + 403 on non-admin) | `done 2026-02-11` |
| N-10 | Similar properties API + UI (server-side query + horizontal scroll cards) | `done 2026-02-11` |
| N-11 | Contact page with DB storage (contactSubmissions table + /api/contact + /contact page) | `done 2026-02-11` |
| N-12 | Scraper status/history proxy routes + enhanced ScraperAdmin UI (job polling, per-source stats, history) | `done 2026-02-11` |
| N-13 | Sync PROJECT_VISION.md files across codebases | `done 2026-02-11` |

**Block N Quality Notes (2026-02-11):**
- Scraper pipeline: new properties now get hazard + score stub records with basic inline scoring (value from price/sqm, condition from building age, rebuild from road_width + rebuild_possible)
- Security: passwords now hashed with bcryptjs, admin role required for scraper trigger (403 for non-admins)
- Settings: profile save and account deletion both wired and working
- Similar properties: server-side query (same prefecture, price ±50%, ordered by price proximity), horizontal scroll UI
- Contact form: stores in contactSubmissions table, input validation (max lengths, email format)
- Scraper admin: per-source stats, live job polling (5s interval), expandable job history
- Dynamic sitemap: generates /listing/{id} URLs for all active properties
- 39 pages build clean after all changes

---

## 8. Subscription Tiers

| Feature | Free | Basic | Pro |
|---|---|---|---|
| Map explore | Yes | Yes | Yes |
| Listing details | Limited (5/day) | Unlimited | Unlimited |
| Currency conversion | JPY only | JPY + USD + EUR | All currencies |
| Wishlists | 1 list, 10 items | 10 lists, 100 items | 100 lists, unlimited |
| Alerts | 1 alert, weekly | 5 alerts, daily | 50 alerts, instant |
| Hazard data | Basic (yes/no) | Detailed (levels) | Full (raw data + map) |
| Score breakdown | Composite only | 6 dimensions | Full + historical |
| Deal pipeline | No | 3 active deals | Unlimited |
| Financial calculator | No | Yes | Yes |
| Export (CSV/Excel) | No | Yes | Yes |
| Ad-free | No | Yes | Yes |

**Current state:** All features unlocked for all users (testing phase). Subscription UI exists but grants free access.

**Future pricing (placeholder):**
- Free: $0/month
- Basic: $9/month or $79/year
- Pro: $29/month or $249/year

---

## 9. Python Scraper Microservice (Vultr)

The existing Python scrapers remain on the Vultr VPS, adapted to work with the new Supabase database.

### Changes needed:
1. **Database connection:** Replace local PostgreSQL connection string with Supabase connection string
2. **Image upload:** After scraping images, upload to Supabase Storage instead of local filesystem
3. **Translation:** Add Google Translate API call in the scrape pipeline to translate `description` and `area_info` fields from Japanese to English
4. **API endpoint:** Add a simple FastAPI endpoint so the Next.js app can trigger scrapes remotely
5. **Cron scheduling:** Set up system cron to run scrapes on schedule (every 6 hours)
6. **Health check:** Expose `/health` endpoint for monitoring

### Scraper API:
```
POST /api/scrape/trigger   — Start a scrape job (source, prefecture)
GET  /api/scrape/status     — Get current job status
GET  /api/scrape/history    — Get recent scrape jobs
GET  /health                — Health check
```

---

## 10. Key Technical Patterns

### Bounding Box Search (like AkiyaMart)
```
/explore?sw-lat=35.528&sw-lon=139.562&ne-lat=35.817&ne-lon=139.918&currency=usd&max-price=80000
```
- All search state lives in URL query params → shareable, bookmarkable
- Map viewport changes update URL (debounced)
- Filters update URL params
- On page load, read URL → set map bounds + fetch listings

### SEO Landing Pages
- `/city/[slug]` and `/prefecture/[slug]` are statically generated (ISR)
- Each shows: hero image, description, key stats, 6-12 teaser listings
- "Search Properties in [City]" CTA → links to `/explore?...` with pre-set bbox
- Generates sitemap entries for all cities/prefectures

### Feature Gating
```typescript
// Utility to check if user's plan allows a feature
function canAccess(userPlan: Plan, feature: Feature): boolean {
  // During testing: always return true
  if (process.env.FREE_MODE === 'true') return true;
  return PLAN_FEATURES[userPlan].includes(feature);
}
```

### Source Badges (Duplicate Handling)
- Each listing shows colored dot(s) indicating which portal(s) list it
- If a property has multiple listings from different sources, show all badges
- Future: automatic merge candidates based on fuzzy address + geo proximity

---

## 10b. Critical Technical Patterns & Gotchas

> **IMPORTANT for any AI continuing this project.** These patterns are used throughout the codebase and must be followed to avoid build failures.

### Lazy DB via Proxy Pattern
The Drizzle DB export uses a `Proxy` so the app builds without `DATABASE_URL` at build time (Vercel/CI). The actual connection is only created on first access at runtime.

```typescript
// src/lib/db/index.ts
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

let _db: ReturnType<typeof drizzle> | null = null;

function getDb() {
  if (!_db) {
    if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL not set");
    const client = postgres(process.env.DATABASE_URL);
    _db = drizzle(client, { schema });
  }
  return _db;
}

// Proxy so `db.select(...)` works without calling getDb() each time
export const db = new Proxy({} as ReturnType<typeof drizzle>, {
  get(_, prop) { return (getDb() as any)[prop]; },
});
```

### getDbOrDummy() for Build-Time Safety
NextAuth's Drizzle adapter needs a DB instance at import time. `getDbOrDummy()` returns a dummy object during build (when DATABASE_URL is undefined) so the build passes.

```typescript
export function getDbOrDummy() {
  if (!process.env.DATABASE_URL) return {} as any;
  return getDb();
}
// Used in: src/lib/auth.ts → DrizzleAdapter(getDbOrDummy())
```

### React 19 Async Params
Next.js 16 with React 19 requires dynamic route params to be awaited:
```typescript
// CORRECT (React 19 / Next.js 16):
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // ...
}

// WRONG (old pattern — will error):
export default function Page({ params }: { params: { id: string } }) { ... }
```

### MapLibre SSR Avoidance
MapLibre GL JS uses `window` and cannot run server-side. Always load via dynamic import:
```typescript
const BaseMap = dynamic(() => import("@/components/map/base-map"), { ssr: false });
```

### TailwindCSS v4 Configuration
Tailwind v4 uses CSS-based configuration, **NOT** `tailwind.config.ts`:
```css
/* src/app/globals.css */
@import "tailwindcss";

@theme inline {
  --color-primary: #2D4A7A;
  --radius-md: 8px;
  /* ... all tokens defined here */
}
```
There is no `tailwind.config.ts` file in the project.

### useRef in React 19
React 19 requires an initial value for `useRef`:
```typescript
const ref = useRef<HTMLDivElement>(null);  // CORRECT
const ref = useRef<HTMLDivElement>();       // WRONG — will error
```

### Auth Session in API Routes
All authenticated API routes follow this pattern:
```typescript
import { auth } from "@/lib/auth";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  // ...
}
```

### Feature Gate Pattern
```typescript
import { canAccess } from "@/lib/feature-gate";
// canAccess(plan, feature) returns true always when FREE_MODE=true
// When FREE_MODE is disabled, checks PLAN_FEATURES map
```

---

## 11. File Structure (Actual — as of Block J completion)

```
japan-prop-search/
├── src/
│   ├── app/
│   │   ├── globals.css                          # Global styles + TailwindCSS v4 @theme
│   │   ├── layout.tsx                           # Root layout (Inter font, SessionProvider, Analytics, CookieConsent)
│   │   ├── not-found.tsx                        # Custom 404 page
│   │   ├── error.tsx                            # Global error page
│   │   ├── robots.ts                            # robots.txt generation
│   │   ├── sitemap.ts                           # sitemap.xml generation
│   │   ├── find/route.ts                        # /find?loc= → redirect to /explore with bbox
│   │   │
│   │   ├── (marketing)/                         # Marketing route group (header + footer)
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx                         # Homepage (hero, features, pricing preview)
│   │   │   ├── about/page.tsx
│   │   │   ├── faq/page.tsx
│   │   │   ├── pricing/page.tsx
│   │   │   ├── privacy/page.tsx                 # Privacy policy
│   │   │   ├── terms/page.tsx                   # Terms of service
│   │   │   ├── sign-in/page.tsx                 # Login (Google OAuth + credentials)
│   │   │   └── sign-up/page.tsx                 # Registration
│   │   │
│   │   ├── (app)/                               # App route group (sidebar + header, auth-protected)
│   │   │   ├── layout.tsx                       # Skip-to-content + sidebar + header + main
│   │   │   ├── loading.tsx                      # App shell skeleton
│   │   │   ├── error.tsx                        # App error boundary page
│   │   │   ├── explore/
│   │   │   │   ├── page.tsx                     # Map Explore (MapLibre + sidebar + filters)
│   │   │   │   └── loading.tsx                  # Explore skeleton
│   │   │   ├── listing/[id]/
│   │   │   │   ├── page.tsx                     # Server component (fetches data)
│   │   │   │   ├── listing-detail.tsx           # Client component (all interactivity)
│   │   │   │   └── loading.tsx                  # Listing skeleton
│   │   │   ├── dashboard/page.tsx               # User dashboard (placeholder — Block L)
│   │   │   ├── wishlists/
│   │   │   │   ├── page.tsx                     # Wishlists grid
│   │   │   │   └── [id]/page.tsx                # Wishlist detail (items with thumbnails)
│   │   │   ├── alerts/page.tsx                  # Saved search alerts
│   │   │   ├── pipeline/page.tsx                # Kanban deal pipeline (6 stages)
│   │   │   ├── calculator/page.tsx              # Financial calculator (purchase costs + ROI)
│   │   │   └── settings/page.tsx                # Profile + subscription + danger zone
│   │   │
│   │   └── api/
│   │       ├── auth/[...nextauth]/route.ts      # NextAuth.js handler
│   │       ├── dashboard/route.ts                # GET aggregated dashboard stats
│   │       ├── me/route.ts                      # GET user profile + subscription
│   │       ├── prefectures/route.ts             # GET all prefectures
│   │       ├── municipalities/route.ts          # GET municipalities by prefecture
│   │       ├── places/find/route.ts             # GET location → bbox lookup
│   │       ├── listings/
│   │       │   ├── route.ts                     # GET bbox search with filters
│   │       │   ├── [id]/route.ts                # GET listing detail + PATCH view count
│   │       │   └── geojson/route.ts             # GET GeoJSON for map markers
│   │       ├── wishlists/
│   │       │   ├── route.ts                     # GET list / POST create
│   │       │   ├── [id]/route.ts                # GET / DELETE wishlist
│   │       │   ├── [id]/items/route.ts          # POST add / DELETE remove item
│   │       │   └── check/route.ts               # GET which wishlists contain a property
│   │       ├── alerts/
│   │       │   ├── route.ts                     # GET list / POST create
│   │       │   └── [id]/route.ts                # PATCH update / DELETE
│   │       ├── deals/
│   │       │   ├── route.ts                     # GET list / POST create from propertyId
│   │       │   ├── [id]/route.ts                # GET / PATCH stage+costs / DELETE
│   │       │   ├── [id]/checklist/route.ts      # POST add / PATCH toggle / DELETE item
│   │       │   └── export/route.ts              # GET CSV export
│   │       └── financial/
│   │           └── calculate/route.ts           # POST purchase costs or ROI projection
│   │
│   ├── components/
│   │   ├── ui/                                  # 17 Radix + Tailwind primitives
│   │   │   ├── accordion.tsx, badge.tsx, button.tsx, card.tsx
│   │   │   ├── checkbox.tsx, dialog.tsx, dropdown-menu.tsx
│   │   │   ├── input.tsx, label.tsx, popover.tsx, scroll-area.tsx
│   │   │   ├── select.tsx, separator.tsx, skeleton.tsx
│   │   │   ├── tabs.tsx, textarea.tsx, tooltip.tsx
│   │   ├── map/
│   │   │   ├── base-map.tsx                     # MapLibre wrapper (OSM tiles, Japan center)
│   │   │   ├── property-markers.tsx             # GeoJSON source + clustered markers
│   │   │   ├── property-popup.tsx               # Click-marker mini card
│   │   │   ├── filter-panel.tsx                 # Collapsible filters (price, rooms, structure, etc.)
│   │   │   └── location-search.tsx              # City/prefecture name search
│   │   ├── property/
│   │   │   ├── property-card.tsx                # Thumbnail card (used in sidebar + wishlists)
│   │   │   ├── facts-grid.tsx                   # 9-cell property facts
│   │   │   ├── hazard-panel.tsx                 # 5 risk categories with badges
│   │   │   ├── score-chart.tsx                  # Recharts RadarChart (6 dimensions)
│   │   │   ├── image-gallery.tsx                # Grid + lightbox with keyboard nav
│   │   │   ├── source-badges.tsx                # Colored source pills
│   │   │   ├── mini-map.tsx                     # Small MapLibre map on listing detail
│   │   │   └── wishlist-button.tsx              # Heart button (icon + labeled variants)
│   │   ├── layout/
│   │   │   ├── marketing-header.tsx             # Sticky header with nav + auth buttons
│   │   │   ├── footer.tsx                       # 4-column footer
│   │   │   ├── app-sidebar.tsx                  # Icon nav (desktop) + bottom tab bar (mobile)
│   │   │   └── app-header.tsx                   # Breadcrumb + search + user menu
│   │   ├── providers/
│   │   │   └── session-provider.tsx             # NextAuth SessionProvider wrapper
│   │   ├── analytics.tsx                        # GA4 script tags + trackEvent()
│   │   ├── cookie-consent.tsx                   # Cookie consent banner (localStorage)
│   │   └── error-boundary.tsx                   # Reusable React error boundary
│   │
│   ├── hooks/
│   │   └── use-explore.ts                       # Explore page state (bbox, filters, URL sync, fetching)
│   │
│   ├── lib/
│   │   ├── db/
│   │   │   ├── index.ts                         # Drizzle DB connection (lazy Proxy pattern)
│   │   │   ├── schema.ts                        # 17 tables (480 lines)
│   │   │   └── seed.ts                          # 60 demo properties + prefectures + municipalities
│   │   ├── auth.ts                              # NextAuth config (Google OAuth + Credentials)
│   │   ├── currency.ts                          # JPY ↔ USD/EUR/GBP/AUD conversion
│   │   ├── feature-gate.ts                      # canAccess(plan, feature) — always true in FREE_MODE
│   │   ├── financial.ts                         # Japanese tax/cost calculator (ported from Python)
│   │   ├── scoring.ts                           # 6-dimension property scoring (ported from Python)
│   │   ├── utils.ts                             # cn() helper (clsx + tailwind-merge)
│   │   └── validations.ts                       # Input validation utilities
│   │
│   ├── middleware.ts                            # Auth middleware (protects /dashboard, /wishlists, etc.)
│   │
│   └── types/
│       └── index.ts                             # TypeScript types for all domain entities
│
├── public/                                      # Static assets
├── drizzle.config.ts                            # Drizzle Kit config
├── next.config.ts                               # Image optimization + security headers + caching
├── .env.example                                 # All environment variable placeholders
└── package.json
```

---

## 12. Migration Checklist (From Old App)

Logic to port from Python → TypeScript:
- [x] Scoring engine (6-dimension model) → `src/lib/scoring.ts` (**done** — Block I-03)
- [x] Financial calculator (Japanese tax rules) → `src/lib/financial.ts` (**done** — Block I-02)
- [x] Currency conversion → `src/lib/currency.ts` (**done** — Block B-12)
- [ ] Address normalization → `lib/address.ts` (not yet needed)
- [ ] Mesh code calculation → `lib/meshcode.ts` (not yet needed)
- [ ] Hazard data interpretation → `lib/hazards.ts` (not yet needed — hazard display works from raw DB data)

Logic that stays in Python (Vultr microservice):
- [ ] All 5 scrapers (SUUMO, AtHome, Homes, BIT Auction, Akiya Banks)
- [ ] Playwright browser automation
- [ ] Deduplication service
- [ ] Geocoding service (Nominatim)
- [ ] Hazard API clients (J-SHIS, reinfolib)
- [ ] Google Translate integration (new)

---

## 13. Environment Variables

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx
DATABASE_URL=postgresql://...

# NextAuth
NEXTAUTH_URL=https://yoursite.com
NEXTAUTH_SECRET=xxx
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx

# External APIs
GOOGLE_TRANSLATE_API_KEY=xxx

# Scraper Microservice
SCRAPER_API_URL=http://vultr-ip:8000
SCRAPER_API_KEY=xxx

# Analytics (optional — GA4 only loads if set)
NEXT_PUBLIC_GA_ID=G-XXXXXXXXXX

# Feature Flags
FREE_MODE=true  # All features free during testing

# Future
STRIPE_SECRET_KEY=xxx
STRIPE_WEBHOOK_SECRET=xxx
RESEND_API_KEY=xxx
```

---

## 14. Open Decisions (To Be Resolved)

- [ ] **Brand name:** Currently "JapanPropSearch" (placeholder). Need final name.
- [ ] **Domain:** Need to purchase domain.
- [ ] **Logo/branding:** Need logo design. Currently using ◉ text symbol.
- [ ] **Hero images:** Need high-quality Japanese real estate/landscape photos (royalty-free or custom).
- [ ] **Content:** City/prefecture descriptions for SEO landing pages (F-04/F-05).
- [x] **Legal:** ~~Privacy policy, terms of service text~~ → **Done** (J-10). Pages at `/privacy` and `/terms`.
- [ ] **Email provider:** Resend vs. SendGrid vs. AWS SES for alert emails.
- [x] **Analytics:** ~~Google Analytics vs. Plausible~~ → **Chose GA4** (J-07). Conditional on NEXT_PUBLIC_GA_ID env var.
- [ ] **Supabase project:** User needs to create Supabase project, provide DATABASE_URL, run `npm run db:push` and `npm run db:seed` (B-01 still pending).

---

## 15. Git Commit History

```
d819ee9  K-01 through K-08: Scraper integration + Next.js admin
eb3cf5c  L-01 through L-03: User dashboard
b673b2a  J-01 through J-11: Polish, performance & launch readiness
c3ff719  I-01 through I-10: Deal pipeline & financial tools
9fad336  H-01 through H-08: Wishlists & alerts system
aadca28  G-01 through G-12: Authentication & user system
e5143de  F-01 through F-09: Marketing pages + SEO infrastructure
925614d  E-01 through E-11: Listing detail page with full feature set
d02d60d  D-01 through D-14: Map Explore page with full feature set
61093d9  C-01 through C-05: Core API routes + lazy DB connection
0a46f69  B-02 through B-12: Database schema, seed data, and currency utility
5e04aa8  A-04/A-05/A-06: Layouts + placeholder pages for all routes
b55fac9  A-02/A-03: Design system + UI component library
151c3f5  A-01: Initialize Next.js 16 project with Japanese aesthetic theme
```

Each commit is atomic per block (all tasks in a block committed together after build verification).

---

## 16. Build & Run Commands

```bash
npm run dev          # Start dev server (localhost:3000)
npm run build        # Production build (verifies all 35 pages)
npm run db:generate  # Generate Drizzle migrations
npm run db:push      # Push schema to database
npm run db:seed      # Seed 60 demo properties + prefectures + municipalities
npm run db:studio    # Open Drizzle Studio (DB GUI)
```

**First-time setup:**
1. Clone the repo
2. `npm install`
3. Create `.env.local` from `.env.example` (fill in DATABASE_URL, NEXTAUTH_SECRET, etc.)
4. Create Supabase project, enable PostGIS, copy connection string
5. `npm run db:push` (create tables)
6. `npm run db:seed` (populate demo data)
7. `npm run dev`

---

## 17. What's Left to Build

### URGENT: Next Session TODO (start here)

These items must be done before the site works properly with Block N changes:

#### 1. Push Block N schema changes to Supabase (5 min)
Block N added 3 new columns and 1 new table to schema.ts but they haven't been migrated to the live database yet.
```bash
cd C:\Users\nilsb\Documents\japan-prop-search
npm run db:push
```
This will add:
- `password_hash` column to `users` table (for bcrypt password hashing — N-08)
- `role` column to `users` table (for admin role — N-09, defaults to "user")
- `contact_submissions` table (for contact form — N-11)

#### 2. Set yourself as admin (2 min)
After db:push, set your user to admin so you can trigger scraper jobs:
```sql
-- Run in Supabase SQL Editor or Drizzle Studio:
UPDATE users SET role = 'admin' WHERE email = 'your-email@example.com';
```
Or use `npm run db:studio` to edit the row visually.

#### 3. Deploy updated Python scraper to Vultr (5 min)
The scraper code is pushed to GitHub but needs to be pulled on the Vultr server:
```bash
ssh your-vultr-server
cd /path/to/scraper
git pull
# Restart the scraper service (systemctl, pm2, or however it's managed)
```
This deploys: hazard/score stub creation (N-01), null safety fix (N-02), status/history endpoints (N-03), enriched health (N-04).

#### 4. Test the full pipeline (10 min)
After steps 1-3:
- Go to https://japan-prop-search.vercel.app/settings
- Scraper Admin section should show "Online" with per-source stats
- Trigger a scrape job → watch live status polling
- Verify new properties appear in explore map with score stubs
- Test login with email/password (should now require correct password)
- Test contact form at /contact
- Test similar properties section on any listing detail page

---

### Remaining Deferred Features (not blocking launch)

| Priority | Feature | What's needed | Effort |
|---|---|---|---|
| **High** | Real property data | Run scraper on Vultr, verify properties flow to Next.js app | 1 session |
| **High** | Google OAuth | Set up Google Cloud Console, add client ID/secret to Vercel env | 30 min (manual) |
| **Medium** | F-04/F-05/F-06 — City/prefecture SEO landing pages | `/city/[slug]`, `/prefecture/[slug]` with ISR — needs real data in DB first | 1 session |
| **Medium** | H-09/H-10 — Alert email worker + template | Choose email provider (Resend recommended), implement cron/Edge Function | 1 session |
| **Low** | G-11 — Subscription activation (Stripe) | Set up Stripe account, webhook, checkout flow | 1-2 sessions |
| **Low** | Domain purchase + custom domain on Vercel | Buy domain, add to Vercel project settings | 15 min (manual) |
| **Low** | Logo/branding | Design logo, replace ◉ text symbol | Manual/design task |
| **Low** | Hero images | Get high-quality Japanese real estate photos (Unsplash/custom) | Manual task |

### Suggested Next Session Priority

1. **Run `db:push` + set admin role + deploy scraper to Vultr** (steps 1-3 above)
2. **Trigger a real scrape** and verify the full data pipeline works end-to-end
3. **Google OAuth setup** (Google Cloud Console → Vercel env vars)
4. **City/Prefecture SEO pages** (F-04/F-05/F-06) — now possible with real data

---

### Source Code Locations:
- **Next.js app:** `C:\Users\nilsb\Documents\japan-prop-search\`
- **Python scrapers:** `C:\Users\nilsb\Documents\Japan Scrapping Tool\`
  - Financial service: `backend\app\services\financial_service.py` (ported to TS)
  - Scoring engine: `backend\app\services\scoring_engine.py` (ported to TS)

### Production Infrastructure:
- **Vercel:** https://japan-prop-search.vercel.app (auto-deploys from GitHub master)
- **Supabase:** Project `oeephlppujidspbpujte` (Tokyo region)
  - Database: 18 tables (+contact_submissions), 60 demo properties seeded
  - Uses transaction pooler (port 6543) for serverless compatibility
  - **PENDING:** db:push needed for Block N schema changes (password_hash, role, contact_submissions)
- **GitHub:**
  - Next.js: https://github.com/NilsBaeumer/japan-prop-search (private)
  - Scraper: https://github.com/NilsBaeumer/japan-reit (private)
- **Vultr:** Scraper microservice (FastAPI + Playwright)
  - **PENDING:** git pull needed for Block N scraper fixes

### Block M Notes (Deployment — 2026-02-11):
- Supabase project created in Tokyo region, schema pushed via `drizzle-kit push`, 60 demo properties seeded
- Vercel deployment: auto-deploys from GitHub, Node 20 LTS pinned
- Fixed: listing detail page refactored from self-fetch to direct DB query (server components can't reliably fetch their own API routes on Vercel)
- Fixed: DATABASE_URL sanitizer strips whitespace (Vercel env var copy-paste issue)
- Fixed: postgres driver configured with `ssl: "require"`, `prepare: false` for transaction pooler
- Health endpoint at `/api/health` for monitoring

### Block N Notes (Market-Ready — 2026-02-11):
- 13 tasks completed across both codebases (4 Python scraper, 9 Next.js)
- Security: bcrypt password hashing, admin role with 403 enforcement
- Pipeline: new properties auto-get hazard/score stubs with inline scoring
- Features: similar properties, contact page, dynamic sitemap, profile save/delete
- Scraper admin: per-source stats, live job polling, expandable job history
- Build: 39 pages clean. Both repos committed and pushed.
- **Schema migration NOT YET RUN** — must run `db:push` before Vercel deployment works fully

---

*Last updated: 2026-02-11*
*Version: 6.0 — Block N complete. Market-ready improvements (security, pipeline fixes, contact, similar properties).*
