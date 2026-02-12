# JapanPropSearch — Project Vision & Implementation Plan

> **Purpose of this document:** This is the single source of truth for the project vision, architecture decisions, and implementation roadmap. Every new chat session should read this file first to understand context.

### Rules for AI Sessions (MUST FOLLOW)

1. **Read this file first.** Before doing anything, read PROJECT_VISION.md to understand what exists and what's next.
2. **Never start Block X+1 until Block X is verified complete.** Even if the user says "continue with V", first check: is the previous block actually done? Run the site, check the build, verify the feature works. If not, fix it first.
3. **Update this file after every completed task.** Mark tasks as done with date. Add quality notes. Move status indicators. A future AI must be able to pick up exactly where you left off.
4. **Remove stale content.** If something is outdated or redundant, delete or condense it. Don't let this file bloat with noise that confuses future sessions.
5. **Dependencies are hard requirements.** The task order exists for a reason. Don't skip ahead — the foundation must exist before building on top of it.
6. **Quality gate before moving on.** After finishing a task: does the build pass? Does the feature work visually? Is the UX acceptable? Only then mark it done and proceed.
7. **Be honest about what's broken.** If a "done" task has known issues, note them clearly with `**Known issues:**` so they get fixed properly.
8. **Two codebases exist:**
   - **Next.js consumer app:** `C:\Users\nilsb\Documents\japan-prop-search\` (deployed to Vercel)
   - **Python scraper microservice:** `C:\Users\nilsb\Documents\Japan Scrapping Tool\backend\` (to be deployed to Vultr)

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

### Current Status: `BLOCK O ~90% COMPLETE — 10,600+ live properties, Vercel site loading, scheduler enabled`
### Live URL: `https://japan-prop-search.vercel.app`
### Backend API: `http://45.77.13.15/api/v1/properties` (10,600+ properties serving)
### Reality Check: `~30% toward AkiyaMart-level product (was 25%)`

### Session Log (2026-02-12): Block O Execution — From 60 Demo to 10,600+ Real Properties

**Sessions covered:** 4 continuous sessions (context compacted 3 times)

#### What Was Accomplished:
1. **Deployed scraper to Vultr VPS** (45.77.13.15) — Docker Compose with backend + nginx frontend
2. **Fixed Akiya Banks scraper** — Complete URL rewrite (old patterns 404'd), card+detail parsing working
3. **Fixed SUUMO scraper** — Removed broken `cn=50` param, fixed `pj→page` pagination, added `property_unit` card selector
4. **Fixed model conflicts** — Old SQLAlchemy models replaced with aliases to new Drizzle-compatible schema
5. **Fixed transaction failures** — Added per-listing savepoints (`session.begin_nested()`) so one bad listing doesn't kill the batch
6. **Fixed NoneType scoring** — Comparison operators failed on None scores
7. **Fixed prefecture FK constraint** — `prefecture_code` was inserting names ("長野県") not JIS codes ("20"). Added `_PREFECTURE_CODE_BY_NAME` reverse lookup
8. **Fixed municipality FK constraint** — `municipality_code` was inserting city names ("山形市") not JIS codes. Added `.isdigit()` validation guard
9. **Fixed SUUMO 12-hour idle loop** — Base `run()` slept `crawl_delay_seconds` (30s) between each listing's `scrape_detail()` even though it returns None. 1500×30s=12.5hrs. Overrode `run()` to return search results directly
10. **Fixed SUUMO address extraction** — Card selector missed addresses. Now falls back to `raw_data["所在地"]` + extracts prefecture from address
11. **Fixed Properties API 500 error** — `_property_to_dict` referenced old schema fields. Updated to new field names
12. **Added batch commits** — Commit every 25 listings to prevent losing all progress on container restart
13. **Created Supabase Storage bucket** `property-images` — images uploading successfully
14. **Backfilled 5,948 SUUMO properties** — Updated address_ja and prefecture_code from raw_data
15. **Scraped all 47 prefectures** via Akiya Banks + 9 prefectures via SUUMO

#### Final Numbers:
| Metric | Start of Block O | End of Sessions |
|---|---|---|
| Properties | 60 (demo) | **10,615** |
| Images | 0 | **24,496** |
| Prefectures covered | 0 | **42** |
| Property listings | 0 | **11,770** |
| Backend API | Not deployed | **Serving 200 OK** |

#### What Worked Well:
- **Akiya Banks scraper** — Reliable, fast (httpx + 3s delay), good data quality. Detail pages provide rich data (address, area, year built, images, rebuild status, road width). Successfully scraped all 47 prefectures. ~3,500 properties from this source alone
- **SUUMO scraper** — Once fixed, extremely productive. 1,500 listings per prefecture × 5 major prefectures = 7,500 listings. Search cards alone provide sufficient data (price, address, area, floor plan, year built). No need for detail page scraping
- **Savepoint isolation** — Critical fix. Without it, one FK violation killed entire batches of 100+ listings. With savepoints, failures are per-listing and the rest succeed
- **Batch commits** — Saved us from losing progress multiple times when container restarted mid-scrape
- **Image upload to Supabase Storage** — Working end-to-end, properties have 5-20 images each from Akiya Banks
- **Parallel scraping** — Running 10+ scrape jobs concurrently across prefectures works well, no resource issues on the 1GB VPS

#### What Went Wrong / Lessons Learned:
- **FK constraints not discovered early** — Both `prefecture_code` and `municipality_code` have FK constraints to lookup tables. The scraper inserted human-readable names instead of JIS codes. Cost 3 full deploy cycles and ~1hr debugging. **Lesson:** Always check FK constraints on the target schema before writing data
- **SUUMO detail scraping is impractical** — Playwright opens a full browser per page with 30s safety delay. 1,500 listings × 30s = 12+ hours. And we didn't even realize `scrape_detail` returning None still triggered the 30s sleep per listing. **Lesson:** Override the base class `run()` method when skipping detail scraping
- **Container restarts lose all in-progress work** — Each `docker compose up --build` kills running scrape tasks. Without batch commits, a scrape processing 300 listings at 250/300 loses everything. **Lesson:** Always commit incrementally
- **Old schema vs new schema mismatch** — The codebase has two competing sets of models (old `Property` with `price`/`latitude` and new `NewProperty` with `price_jpy`/`lat`). API endpoints referenced old field names causing 500 errors. Multiple files still import from `models/property.py` which is now just an alias. **Lesson:** After a schema migration, grep for ALL references to old field names
- **3 of 5 scrapers are broken** — HOME'S (CloudFront 403 WAF), at_home (405 anti-bot + wrong URLs + broken selectors), BIT Auction (404 search URL + requires JS navigation). Only Akiya Banks and SUUMO actually work. **Lesson:** Don't count scrapers that haven't been tested against live sites
- **SUUMO search cards don't use CSS classes for address** — The `.dottable-vm` selector only works on some card layouts. The address is in `raw_data["所在地"]` but wasn't being extracted to `address_ja`. 5,948 properties were inserted with "Unknown" address. **Lesson:** Always verify data quality on the first batch, don't just check counts

16. **Fixed Vercel explore page** — BaseMap `onLoad` handler triggers initial data fetch (previously waited for user pan/zoom). Normalized price field shape mismatch between API `price: {jpy, converted}` and hook expecting `priceJpy`
17. **Enabled scheduler** — 24h interval, iterates all 47 prefectures per source, max 3 concurrent per source. Disabled broken scrapers (homes, athome, bit_auction)
18. **Verified Block N schema** — password_hash, role, contact_submissions already present. `drizzle-kit push` was blocked because it wanted to delete scraper tables
19. **Started geocoding** — geocode_all.py running via Nominatim for 9,839 properties missing coordinates. ~10% have coords so far, climbing steadily
20. **Cleaned 155 addresses** — Removed newlines/tabs from SUUMO addresses for better geocoding

#### What's Not Complete:
- **O-02**: Admin role not set on user account
- **O-05**: Google Translate API key not configured — no English translations
- **O-11**: Google OAuth not configured in production
- **O-12**: Data quality monitoring needed
- **1,310 akiya properties still have "Unknown" address** — card selector misses some akiya-athome layouts
- **~0 properties have English translations** (no Google Translate key)
- **Geocoding in progress** — ~10% of 10,615 have coords, geocode_all.py running (~5hr ETA)
- **3 broken scrapers** (homes, athome, bit_auction) disabled but not fixed

---

### BLOCK A — Project Skeleton ✅ COMPLETE
**What exists:** Next.js 16.1.6 + React 19 + TailwindCSS v4 (CSS-based config). 17 Radix UI components (shadcn pattern). Marketing layout (header+footer) + App layout (sidebar+header). 13 routes across marketing and app groups. Inter font, cn() utility, .env.example. Build passes clean.

---

### BLOCK B — Database & Data Layer ✅ COMPLETE
**What exists:** Drizzle ORM with 17+ tables in `schema.ts` (480 lines). Supabase project created (Tokyo region, project `oeephlppujidspbpujte`). B-01 done. 47 prefectures, 13 municipalities with real bbox, 5 listing sources seeded. 60 demo properties. Currency util: JPY↔USD/EUR/GBP/AUD. Uses lat/lng double precision with composite index (simple range queries, PostGIS can be added later for performance). Lazy DB via Proxy pattern for build safety.
**DONE:** Block N schema changes (password_hash, role, contact_submissions) verified present in Supabase — O-01 complete.

---

### BLOCK C — Core API Routes ✅ COMPLETE
**What exists:** 6 API route files. `GET /api/prefectures`, `GET /api/municipalities`, `GET /api/listings` (bbox search + filters + pagination + currency conversion), `GET /api/listings/[id]` (detail + view count), `GET /api/places/find` (location→bbox), `GET /api/listings/geojson` (GeoJSON for map, capped at 2000 features). Simple lat/lng range queries (no PostGIS yet). Listings route includes source badges + thumbnail aggregation.
**API format:** `GET /api/listings?swLat=&swLng=&neLat=&neLng=&maxPrice=&currency=&rooms=&landRights=&sort=&page=&limit=`

---

### BLOCK D — Map Explore Page ✅ COMPLETE
**What exists:** Full MapLibre GL + react-map-gl map (70% width) + sidebar (30%). `useExplore` hook manages all state: bbox, filters, URL sync, pagination, fetching. Clustered markers color-coded by price (green <3M, blue 3-10M, amber 10-30M, red >30M). Click popups. Filter panel (currency, sort, price range, rooms, land rights, structure, min score). LocationSearch via /api/places/find. Mobile bottom sheet. "Search this area" button. Map-list hover interaction.
**Known issues (to fix in Block P):** Plain OSM tiles (ugly), generic circle markers, mobile bottom sheet simplified (no drag).

---

### BLOCK E — Listing Detail Page ✅ COMPLETE
**What exists:** Server→client component split. Image gallery with lightbox + keyboard nav. 9-cell facts grid. Hazard panel (5 risk categories, color-coded). Recharts RadarChart (6-dimension scores). Source badges. Description/Area Info tabs. Mini map. Currency selector. SEO metadata + JSON-LD. Similar properties (N-10).
**Known issues (to fix in Block Q):** No hero image section, price not prominent enough, no sticky mobile CTA bar.

---

### BLOCK F — Marketing & SEO Pages ⚠️ PARTIAL
**Done:** Homepage (5 sections: hero, how it works, features, pricing preview, CTA). Pricing (3 tiers). FAQ (16 questions). About page. Contact page (N-11). robots.ts + sitemap.ts (dynamic with property URLs).
**Deferred (→ Block R):** F-04 city landing pages, F-05 prefecture landing pages, F-06 ISR static generation — all need real data in DB first.

---

### BLOCK G — Authentication & User System ⚠️ PARTIAL
**Done:** NextAuth.js v5 beta, JWT sessions, Google OAuth + Credentials providers, auto-create users in FREE_MODE. getDbOrDummy() for build safety. Auth middleware protects 6 routes. Settings page (profile save, account deletion). `canAccess(plan, feature)` gate (always true in FREE_MODE). Admin role with 403 enforcement (N-09). Bcrypt password hashing (N-08).
**Deferred (→ Block T):** G-11 Stripe subscription activation. Google OAuth not yet configured in production (needs Google Cloud Console setup — see Block O-11).

---

### BLOCK H — Wishlists & Alerts ⚠️ PARTIAL
**Done:** Full CRUD wishlists + alerts. WishlistButton (icon/labeled variants). `/api/wishlists/check?propertyId=` for membership. "Save this search" on Explore. Wishlist detail page.
**Key detail:** Alerts API uses `queryJson` field name (matches Drizzle schema `jsonb("query_json")`) — NOT `query`.
**Deferred (→ Block S):** H-09/H-10 alert email worker + template — needs email provider setup.

---

### BLOCK I — Deal Pipeline & Financial Tools ✅ COMPLETE
**What exists:** Financial calculator (`src/lib/financial.ts`, 290 lines) with all Japanese tax rules: broker commission (standard + low-price rule), stamp tax (reduced rates through 2027-03), registration tax, acquisition tax, holding costs (fixed asset 1.4% + city planning 0.3%), capital gains tax (short-term 39.63% / long-term 20.315%), ROI projection with breakeven calculation.
Scoring engine (`src/lib/scoring.ts`, 200 lines): 6 dimensions — rebuild(25%), hazard(20%), infrastructure(15%), demographic(15%), value(15%), condition(10%).
Pipeline Kanban: 6 stages (discovery → analysis → offer → due_diligence → closing → completed). Due diligence checklist (categorized). CSV export. "Start Deal" on listing detail.

---

### BLOCK J — Polish, Performance & Launch Readiness ✅ COMPLETE
**What exists:** Error boundaries, skeleton loaders, 404/500 pages. next.config.ts with image optimization (avif/webp, Supabase remote patterns), security headers, caching (marketing s-maxage=86400, API s-maxage=60). GA4 analytics (conditional on NEXT_PUBLIC_GA_ID). Cookie consent banner. Input validation utilities. Privacy policy + terms of service. Accessibility (skip-to-content, ARIA labels).
**Known issues (found in Block P audit):** Color contrast fails WCAG AA (muted-foreground at 40% lightness = 3.8:1, needs 4.5:1). Mobile nav incomplete. Typography hierarchy flat.
---

### BLOCK K — Scraper Integration ✅ COMPLETE (deployed and running)
**What exists:** Python scraper deployed to Vultr VPS (45.77.13.15) via Docker Compose. New SQLAlchemy models (`models/new_schema.py`) matching Drizzle schema. `SupabasePropertyService` handles upserts with savepoint isolation, deduplication by source+source_listing_id, price_per_sqm computation, inline scoring. `TranslateService` (Google Cloud Translation API v2 — key not yet configured). `ImageUploadService` (Supabase Storage bucket `property-images` — working, 24K+ images). Remote trigger (`POST /api/v1/scraping/jobs`, X-API-Key auth). Scheduler code ready but not enabled. Batch commits every 25 listings.
**Working scrapers:** Akiya Banks (httpx, all 47 prefectures), SUUMO (Playwright search + skip detail)
**Broken scrapers:** HOME'S (CloudFront WAF 403), at_home (anti-bot 405), BIT Auction (search URL 404)

---

### BLOCK L — User Dashboard ✅ COMPLETE
**What exists:** `/api/dashboard` aggregates stats in parallel. 4 stat cards (wishlists, alerts, deals, plan). Recently viewed (localStorage, max 20). Pipeline activity (last 5 deals). Personalized greeting.
**Known issues (to fix in Block Q):** Shows admin data, needs consumer-focused redesign.

---

### BLOCK N — Market-Ready Improvements ✅ COMPLETE
**What was added:** Scraper pipeline creates hazard/score stubs with inline scoring on new properties. Bcrypt password hashing (N-08). Admin role with 403 enforcement (N-09). Similar properties API + UI (N-10). Contact page with DB storage (N-11). ScraperAdmin enhanced with per-source stats, live job polling, history (N-12). Dynamic sitemap with property URLs (N-05). Profile save + account deletion wired (N-06/N-07).
**PENDING:** Schema changes (password_hash, role, contact_submissions) need `db:push` — see Block O-01. 39 pages build clean.

---

## 7b. Gap Analysis — Where We Are vs. AkiyaMart Benchmark

> **This section was added 2026-02-12 after deep analysis of https://www.akiya-mart.com and brutal audit of our own UI/UX.**

### AkiyaMart Profile (The Target)
- **Founded:** 2023 by Take Kurosawa & Joey Stockermans (met at ICU Tokyo 2010)
- **Scale:** 900K+ listings, "170K+ properties under $100K USD"
- **Revenue model:** 3 products — Discovery (search SaaS), Direct (agent-matched buying $3K fee), Care (post-purchase management $1K/yr)
- **Pricing:** Free (limited) / Basic $6/mo / Pro $15/mo ($11/mo annual)
- **Architecture:** Marketing site + `app.akiya-mart.com` subdomain for listings
- **TrustPilot:** 3.2/5 (only 3 reviews, 67% 1-star — paywall frustration)
- **Self-described:** "50% of the way there"

### What AkiyaMart Does Well (Must Match)
1. **Map-first UX** — The map IS the product, not a sidebar afterthought
2. **Scale numbers as hooks** — "900K+ listings" in hero creates authority
3. **English-first** — Users never see Japanese, everything translated
4. **Hazard data on listings** — Tsunami, earthquake, landslide, flood per property
5. **Airbnb eligibility insights** — Investment angle built into search
6. **SEO landing pages** — Programmatic `/prefecture/{slug}` and `/city/{slug}` for every location
7. **Three-product funnel** — Search → Buy → Manage (full lifecycle)
8. **Promo codes** through partners — Drives signups via influencer/podcast network
9. **Podcast content** — "Buying a House in Japan" builds trust and authority
10. **Historical sold data** — Price transparency for investors

### What AkiyaMart Does Poorly (Our Opportunities)
1. **No property scoring** — They show raw data but compute NO scores. Our 6-dimension scoring is genuinely unique
2. **No financial calculator/deal pipeline** — Zero investor tools. We have both
3. **Aggressive paywall** — "Pointless sign-up" is their #1 complaint. We can be more generous
4. **Generic SaaS design** — No Japanese aesthetic, no visual differentiation. We have wabi-sabi design system
5. **Hazard data paywalled** — Basic risk info should be free. We show it free = trust builder
6. **No renovation cost estimates** — Major gap for akiya buyers
7. **Tiny agent network** — Only 2-3 agents, not scalable
8. **No blog/written content** — Missing SEO-rich articles
9. **No comparison tool** — Can't compare properties side by side
10. **Separate subdomain** — Split app.akiya-mart.com confuses the experience

### Brutal Honest Assessment: Our Current State

**What we've built (Blocks A-N):**
- Next.js 16 consumer app with 39 pages (deployed to Vercel)
- Python scraper microservice with 5 scrapers (SUUMO, HOME'S, at home, Akiya Banks, BIT Auction)
- React+Vite admin dashboard (internal tool at `frontend/`)
- Full data model (properties, scoring, hazards, financials, deals, wishlists, alerts)
- Authentication, feature gates, subscription schema

**What's actually working for a real user visiting the site (updated 2026-02-12):**
- ✅ **10,615 real listings** with prices, addresses, areas, floor plans, year built
- ✅ **24,496 real images** uploaded to Supabase Storage
- ✅ **42 prefectures** covered — nationwide data
- ✅ Backend API at `http://45.77.13.15/api/v1/properties` serving data correctly
- ✅ Vite React frontend at `http://45.77.13.15` shows all properties
- ⚠️ Vercel Next.js site shows loading state — needs debugging (data IS in Supabase)
- ❌ No English translations (no Google Translate key configured)
- ❌ No geocoded coordinates on SUUMO listings (~7K properties have no lat/lng)
- ❌ No Google OAuth configured
- ❌ No SEO landing pages (F-04/F-05 deferred)
- ❌ No email alerts (H-09/H-10 deferred)
- ❌ No Stripe payments (G-11 deferred)
- ❌ Schema changes from Block N not pushed (password_hash, role columns)

**UI/UX Audit Scores (consumer product perspective):**

| Component | Score | Critical Issues |
|---|---|---|
| Overall design | 3/10 | Looks like admin tool, not consumer product |
| Color contrast | 3/10 | Muted foreground fails WCAG AA (3.8:1, needs 4.5:1) |
| Typography | 3/10 | Everything is `text-sm`, no hierarchy, no custom fonts |
| Dashboard | 3/10 | Exposes scraper controls, zero emotional hooks |
| Property Search | 2/10 | Feels like SQL query builder, filters dump all at once |
| Property Detail | 3/10 | Data-rich but emotionally flat, no hero image section |
| Map | 5/10 | Functional but plain OSM tiles, generic circle markers |
| Mobile | 2/10 | No mobile navigation at all (sidebar hidden, no hamburger) |
| Psychological hooks | 0/10 | Zero urgency, social proof, FOMO, personalization |
| Hazard Panel | 4/10 | Best component, but too technical for consumers |

### The Gap: What Gets Us From 10% → AkiyaMart Level

```
PHASE 1: FOUNDATION (Blocks O-P)     → Gets us from 10% to 30%
  - Live data pipeline flowing
  - UI/UX overhaul (contrast, typography, animations)
  - Mobile navigation working

PHASE 2: CONSUMER EXPERIENCE (Blocks Q-R) → Gets us from 30% to 55%
  - Reframe from admin tool → consumer product
  - SEO landing pages generating organic traffic
  - Property detail pages that sell
  - Search UX that delights

PHASE 3: GROWTH ENGINE (Blocks S-T)   → Gets us from 55% to 75%
  - Email alerts working
  - Stripe payments live
  - Content strategy (blog/guides)
  - Advanced features (Airbnb insights, price history)

PHASE 4: SCALE & POLISH (Blocks U-V)  → Gets us from 75% to 90%+
  - 100K+ listings (continuous scraping)
  - Performance optimization at scale
  - A/B testing, conversion optimization
  - Agent network (buying service)
```

---

### BLOCK O — Live Data Pipeline (CRITICAL — Nothing Else Matters Without This)
*Zero users will stay on a site with demo data. This is the #1 blocker.*

#### O-00: Pre-deployment code fixes ✅ DONE (2026-02-12)
**What was fixed before deployment:**
- Added `UniqueConstraint("source_id", "source_listing_id")` on `NewPropertyListing` — prevents duplicate listings at DB level
- Fixed CORS: removed wildcard `*`, now reads from `CORS_ORIGINS` env var (configurable per environment)
- Added production env var validation at startup — fails fast if `DATABASE_URL` or `SCRAPER_API_KEY` missing
- Updated Celery tasks (`scraping_tasks.py`) to use `SupabasePropertyService` instead of legacy `PropertyService`
- Removed local PostgreSQL from `docker-compose.prod.yml` — backend connects directly to Supabase
- Rewrote `deploy.sh` — interactive setup prompts for Supabase credentials, generates `.env.production`
- Updated `.env.example` files with all required/optional vars including `CORS_ORIGINS`
- Verified image upload correctly returns full public URL (Next.js uses `storagePath` directly as `<img src>`)

| # | Task | Status | Notes |
|---|---|---|---|
| O-00 | Pre-deployment code fixes (CORS, UniqueConstraint, env validation) | ✅ DONE | Session 1 |
| O-01 | Push Block N schema changes to Supabase (`npm run db:push`) | ✅ DONE | Verified manually — password_hash, role, contact_submissions all present |
| O-02 | Set admin role on user account | `pending` | SQL: `UPDATE users SET role = 'admin'` |
| O-03 | Deploy Python scraper to Vultr | ✅ DONE | Docker Compose, multiple redeploys |
| O-04 | Configure Supabase connection on Vultr | ✅ DONE | .env.production with PgBouncer port 6543 |
| O-05 | Configure Google Translate API key | `pending` | No translations yet — all address_en/description_en are NULL |
| O-06 | Configure Supabase Storage bucket | ✅ DONE | `property-images` bucket created, 24,496 images uploaded |
| O-07 | Run first real scrape | ✅ DONE | Akiya Tokyo: 8 listings → verified in DB |
| O-08 | Verify properties on Vercel site | ✅ DONE | Fixed: BaseMap onLoad handler + price field normalization. 761 properties with coords display on map |
| O-09 | Scale to 1,000+ listings | ✅ EXCEEDED | **10,615+ properties** across 42+ prefectures via Akiya Banks (all 47 prefs) + SUUMO (9+ prefs) |
| O-10 | Enable scheduler | ✅ DONE | SCHEDULER_ENABLED=true, 24h interval, iterates all 47 prefectures per source, max 3 concurrent per source |
| O-11 | Set up Google OAuth | `pending` | Needs Google Cloud Console setup |
| O-12 | Monitor data quality | ⚠️ PARTIAL | 88% have address, ~7% have coordinates (geocoding running), ~0% English translations |
| O-13 | Geocoding | ⚠️ IN PROGRESS | geocode_all.py running on VPS via Nominatim. 9,839 properties pending. ~2.7hr ETA |

**Block O Success Criteria — Revised Assessment:**
- ✅ 1,000+ real property listings with images in Supabase → **EXCEEDED: 10,615+ properties, 24,496 images**
- ❌ Translations working → **Not yet: no Google Translate API key configured**
- ✅ Images uploaded to Supabase Storage → **Working: Akiya Banks images upload to `property-images` bucket**
- ✅ Scheduler running every 24 hours → **Enabled: iterates all 47 prefectures for suumo + akiya sources**
- ❌ Google OAuth login working → **Not configured**
- ✅ Admin can trigger scrapes → **Works via API and via scheduled jobs**
- ✅ Vercel site loads properties → **Fixed: map shows ~761 geocoded properties, sidebar lists them**

**What to do next session (Block O wrap-up + Block P start):**
1. `O-05`: Get Google Translate API key, add to `.env.production`, re-scrape to get translations
2. `O-11`: Set up Google OAuth (Google Cloud Console → Vercel env vars)
3. Verify geocoding completed (~2.7hr runtime) and check final coordinate coverage
4. Investigate 1,310 "Unknown" address properties — may need address extraction fix
5. Disabled broken scrapers (homes, athome, bit_auction) — need to investigate/fix later
6. Start Block P — UI/UX overhaul (the site looks like an admin tool, not a consumer product)

---

### BLOCK P — UI/UX Overhaul: From Admin Tool to Consumer Product
*The current UI fails WCAG contrast, has no mobile nav, and looks like Grafana. This block transforms it into something users trust and enjoy.*

| # | Task | Status | Effort |
|---|---|---|---|
| **P-01** | **Fix color contrast (CRITICAL ACCESSIBILITY):** Increase `--muted-foreground` from 40% to 28% lightness. Increase `--border` visibility. Audit all text/bg combinations for 4.5:1 WCAG AA compliance | `pending` | 1 hr |
| **P-02** | **Typography overhaul:** Import Inter font (Google Fonts via next/font). Create clear hierarchy: hero (text-5xl), page title (text-3xl), section title (text-xl font-semibold), body (text-base), small (text-sm). Price displays should be text-4xl bold (biggest thing on any listing) | `pending` | 2 hrs |
| **P-03** | **Mobile navigation:** Add hamburger menu button in Header → opens full-screen mobile nav overlay (Radix Dialog/Sheet). Add bottom tab bar for primary nav (Explore, Search, Wishlist, Pipeline, Profile). Test on 375px/414px/768px | `pending` | 3 hrs |
| **P-04** | **Micro-animations:** Add `transition-all duration-200` to all interactive elements. Stat card number count-up on load (react-countup). Card hover elevation (translateY -2px + shadow increase). Skeleton shimmer effect. Page fade-in transitions | `pending` | 2 hrs |
| **P-05** | **Color warmth:** Shift background from cold gray (220 20% 97%) to warm off-white (#FAFAF8). Shift borders to warm (#E5E2DB). Shift accent from generic purple to deep indigo (#2D4A7A). Apply full Japanese aesthetic palette from Section 6 | `pending` | 2 hrs |
| **P-06** | **Card redesign:** White bg + warm 1px border + subtle shadow-sm. Rounded-xl (12px). Generous internal padding (p-6 minimum). Image area at top (16:10 ratio, object-cover). Hover: shadow-md + slight lift | `pending` | 2 hrs |
| **P-07** | **Map visual upgrade:** Replace plain OSM tiles with Maptiler Streets (free tier, much prettier). Custom property markers (house icon instead of circles, color-coded by score: green 70+, amber 40-69, red 0-39). Larger, more readable popup cards. Satellite view toggle button | `pending` | 3 hrs |
| **P-08** | **Score badges redesign:** Pill-shaped badges with softer colors (bg-emerald-50/text-emerald-700 instead of harsh bg-green-500). Score number prominent, label secondary. Consistent across all views (card, detail, popup) | `pending` | 1 hr |
| **P-09** | **Hazard simplification for consumers:** Add simplified risk summary at top ("Earthquake risk: Medium, Flood risk: Low") with traffic-light icons. Keep detailed data in expandable "Show technical details" accordion below. Add tooltips explaining jargon ("What is PGA?", "What is liquefaction?") | `pending` | 2 hrs |
| **P-10** | **Empty states:** Replace plain "No data" text with illustrated empty states (simple SVG illustrations). Add helpful CTA in each: "Start exploring properties →", "Create your first wishlist →", "No hazard data yet — we're working on it" | `pending` | 2 hrs |
| **P-11** | **Loading experience:** Replace plain spinners with branded skeleton screens. Map: subtle pulsing Japan outline while loading tiles. Lists: realistic card skeletons (gray rectangles matching card layout). Add progress bar for scrape jobs | `pending` | 1 hr |
| **P-12** | **Button hierarchy:** Primary (solid indigo, white text). Secondary (outline indigo). Ghost (transparent, text only). Destructive (muted red). All with consistent padding, rounded-lg, hover states, focus rings. Minimum 44px touch target on mobile | `pending` | 1 hr |

**P-01 Details (Contrast Fix):**
```css
/* BEFORE (fails WCAG AA at 3.8:1): */
--muted-foreground: 215.4 16.3% 40%;

/* AFTER (passes at 5.2:1): */
--muted-foreground: 215.4 16.3% 28%;

/* Also fix border visibility: */
--border: 220 13% 78%;  /* was 83% — too invisible */
```

**P-05 Details (Japanese Aesthetic Colors):**
```css
:root {
  --bg-primary: #FAFAF8;       /* warm off-white, like washi paper */
  --bg-secondary: #F5F3EF;     /* slightly darker warm gray */
  --bg-card: #FFFFFF;           /* pure white for cards */
  --text-primary: #1A1A1A;     /* near-black */
  --text-secondary: #6B6B6B;   /* warm gray — passes AA on white */
  --text-muted: #8B8B8B;       /* lighter warm gray — passes AA on white for large text */
  --accent-primary: #2D4A7A;   /* deep indigo (藍) */
  --accent-light: #4A6FA5;     /* lighter indigo */
  --accent-subtle: #E8EDF4;    /* very light indigo wash */
  --success: #4A7A5C;          /* muted green, like matcha */
  --warning: #B8860B;          /* gold, like kintsugi */
  --danger: #8B3A3A;           /* muted red, like torii */
  --border: #E5E2DB;           /* warm light border */
}
```

---

### BLOCK Q — Consumer Experience Transformation
*Reframe every page from "admin dashboard" to "product people want to use". Add psychological hooks, trust signals, and conversion pathways.*

| # | Task | Status | Effort |
|---|---|---|---|
| **Q-01** | **Homepage redesign (THE most important page):** Full-width hero with stunning Japanese landscape photo (Unsplash/royalty-free), overlay headline "Discover Your Japanese Property", stat counters ("X,XXX listings · 47 prefectures · 5 data sources"). "How It Works" 3-step (Search → Analyze → Invest). Feature grid (6 cards with icons). Pricing preview. Social proof section. Final CTA | `pending` | 4 hrs |
| **Q-02** | **Hero stat counters:** Query actual DB count on homepage load. Display "X,XXX Properties" (real number), "47 Prefectures", "6-Dimension Scoring", "Free Hazard Data". Numbers should count-up animate on scroll-into-view | `pending` | 1 hr |
| **Q-03** | **Property Search UX redesign:** Progressive disclosure — show 3 basic filters (location, price range, sort) by default. "More filters" button reveals advanced panel (rooms, structure, land rights, rebuild, min score). Replace hardcoded price options with range slider. Rename "Rebuild OK/NG" → "Can Rebuild / Cannot Rebuild". Make sort dropdown human-readable ("Newest First", "Lowest Price", "Highest Score") | `pending` | 3 hrs |
| **Q-04** | **Property Detail page redesign (THE sales page):** Hero image gallery (full-width, 16:9, swipeable). Price as largest element (text-4xl bold). Score badge prominent next to price. "Save to Wishlist" heart + "Start a Deal" CTA side by side. Key facts as icon grid (not plain text). Tabbed sections: Overview / Hazards / Scores / Location / Similar. Sticky bottom bar on mobile (Price + CTA button always visible) | `pending` | 5 hrs |
| **Q-05** | **Add urgency & FOMO hooks:** "New" badge on listings < 7 days old. "Price reduced" badge when price drops between scrapes. "X investors viewed this week" counter (can start with view_count). "Only X properties in this area" scarcity when < 10 results. "Last updated X hours ago" freshness indicator on each listing | `pending` | 3 hrs |
| **Q-06** | **Add trust signals:** "Data from X official sources" with source logos (SUUMO, HOME'S, etc). "Hazard data from J-SHIS (Government)" attribution. "Prices verified against X listings" on price. "Updated every 6 hours" freshness promise. Source badge on each listing linking to original portal | `pending` | 2 hrs |
| **Q-07** | **Dashboard redesign (for consumers, not admins):** Remove all scraper controls from default view (move to /admin route, admin-only). Show: "Welcome back, {name}" greeting. "Your saved properties" (wishlist preview). "Recent price changes" in saved searches. "Your deal pipeline" summary. "Recommended for you" properties (same prefecture as saved). Quick stats: total saved, active alerts, active deals | `pending` | 3 hrs |
| **Q-08** | **Search result cards redesign:** Property image (full-width top, 16:10 ratio). Price large + bold below image. Address line. Key specs row (🛏 3LDK · 📐 120m² · 📅 1985). Score pill badge (colored). Source badges (small dots). Heart button (top-right corner of image). "New" or "Price Drop" badge (top-left of image) | `pending` | 3 hrs |
| **Q-09** | **"Save this search" and alert prompts:** After user performs 3+ searches, show subtle banner: "Want to get notified about new listings like these? Save this search →". On listing detail, show: "Get alerts when similar properties are listed →". Make the alert creation flow 2 clicks (name auto-generated from filters) | `pending` | 2 hrs |
| **Q-10** | **Currency/Price UX:** Show JPY primary + converted price secondary on every price display (e.g., "¥6,000,000 (~$38,390 USD)"). Currency selector in header (persistent via localStorage). Add "万円" display option (e.g., "600万円") as Japanese users expect | `pending` | 2 hrs |
| **Q-11** | **Score explanation for consumers:** On property detail, add "What does this score mean?" expandable section. Plain English explanations: "This property scores 72/100. It's in a low-risk area for natural disasters (85/100), the building can be legally rebuilt (90/100), but the neighborhood is declining in population (45/100)." Generate from score dimensions | `pending` | 2 hrs |

**Q-01 Details (Homepage — must create desire):**
```
Section 1 — Hero (full viewport height)
┌─────────────────────────────────────────────────────┐
│  [Stunning photo: misty Japanese countryside/akiya]  │
│                                                       │
│     Discover Your Japanese Property                   │
│     Search thousands of translated listings with      │
│     hazard data, investment scoring, and deal tools   │
│                                                       │
│     [Start Exploring →]    [View Pricing]             │
│                                                       │
│  ┌──────┐  ┌──────────┐  ┌────────────┐  ┌────────┐ │
│  │ 2,340│  │ 47       │  │ 6-Dimension│  │ Free   │ │
│  │ Props│  │Prefectures│  │  Scoring   │  │ Hazard │ │
│  └──────┘  └──────────┘  └────────────┘  └────────┘ │
└─────────────────────────────────────────────────────┘

Section 2 — How It Works (3 steps)
┌─────────┐  ┌─────────┐  ┌─────────┐
│ 🔍      │  │ 📊      │  │ 🏠      │
│ Search  │  │ Analyze │  │ Invest  │
│ Browse  │  │ Score,  │  │ Pipeline│
│ map +   │  │ hazard, │  │ calc,   │
│ filters │  │ compare │  │ deals   │
└─────────┘  └─────────┘  └─────────┘

Section 3 — Why Us (differentiators vs AkiyaMart)
- 6-Dimension Scoring (they don't have this)
- Free Hazard Overlays (they paywall this)
- Investment Calculator (they don't have this)
- Multi-Source Transparency (they don't show sources)
- Deal Pipeline (they don't have this)
- Japanese Aesthetic (they look generic)

Section 4 — Featured Properties (6 real listings, auto-refreshed)
[PropertyCard] [PropertyCard] [PropertyCard]
[PropertyCard] [PropertyCard] [PropertyCard]

Section 5 — Pricing Preview (3 tiers, compact)

Section 6 — Final CTA
"Ready to find your Japanese property?"
[Start Exploring Free →]
```

**Q-04 Details (Property Detail — the page that converts):**
```
┌─────────────────────────────────────────────┐
│ ← Back to Search                             │
├─────────────────────────────────────────────┤
│ [IMAGE GALLERY — full width, 16:9, swipe]    │
│ [img1]  [img2]  [img3]  [img4]  [+12 more]  │
├─────────────────────────────────────────────┤
│                                               │
│  ¥6,000,000          Score: 72/100            │
│  (~$38,390 USD)      ████████░░ Good          │
│                                               │
│  📍 Hokkaido, Yubari-shi                     │
│  🏠 3LDK · 120m² land · 80m² building       │
│  📅 Built 1985 · Wood frame                  │
│                                               │
│  [♥ Save to Wishlist]  [📋 Start a Deal]     │
│                                               │
├─ [Overview] [Hazards] [Scores] [Location] ───┤
│                                               │
│  Key Facts (icon grid)                        │
│  ┌────────┬─────────┬──────────┐             │
│  │ Price  │ Land    │ Building │             │
│  │ ¥6M   │ 120m²   │ 80m²    │             │
│  ├────────┼─────────┼──────────┤             │
│  │ Built  │ Plan    │ Structure│             │
│  │ 1985   │ 3LDK   │ Wood    │             │
│  ├────────┼─────────┼──────────┤             │
│  │ Rights │ Road    │ Rebuild  │             │
│  │ Free-  │ 4.0m   │ ✅ Yes  │             │
│  │ hold   │        │         │             │
│  └────────┴─────────┴──────────┘             │
│                                               │
│  What This Score Means                        │
│  "This property scores well for investment... │
│   Low natural disaster risk, rebuildable,     │
│   but aging infrastructure nearby."           │
│                                               │
│  Source: SUUMO → [View original listing]      │
│                                               │
├─────────────────────────────────────────────┤
│  Similar Properties (horizontal scroll)       │
│  [Card] [Card] [Card] [Card] →               │
└─────────────────────────────────────────────┘

Mobile: Sticky bottom bar
┌─────────────────────────────────────────────┐
│  ¥6,000,000  │  [♥ Save]  [Start Deal →]   │
└─────────────────────────────────────────────┘
```

---

### BLOCK R — SEO & Marketing Engine
*AkiyaMart gets organic traffic from prefecture/city landing pages. We need these to compete.*

| # | Task | Status | Effort |
|---|---|---|---|
| **R-01** | **Prefecture landing pages (`/prefecture/[slug]`):** Server-rendered with ISR (revalidate 24h). Hero image per prefecture (Unsplash). Stats bar (listing count, avg price, population). 6-12 teaser PropertyCards. "Search all properties in {Prefecture} →" CTA. Internal links to cities within prefecture | `pending` | 4 hrs |
| **R-02** | **City landing pages (`/city/[slug]`):** Same pattern as R-01 but city-level. Auto-generate for every municipality with 5+ listings. Include area description, nearby stations, lifestyle info | `pending` | 3 hrs |
| **R-03** | **SEO content generation:** For each prefecture/city, generate English descriptions (area overview, climate, transport, lifestyle, investment outlook). Can use AI-assisted generation + manual review. Store in DB alongside municipality data | `pending` | 4 hrs |
| **R-04** | **Dynamic sitemap update:** Add all `/prefecture/*` and `/city/*` URLs to sitemap.ts. Include lastmod from most recent listing update. Priority: prefecture=0.8, city=0.7, listing=0.6 | `pending` | 1 hr |
| **R-05** | **Structured data (JSON-LD):** Add `RealEstateListing` schema to listing detail. Add `ItemList` schema to search results. Add `FAQPage` schema to FAQ. Add `Organization` schema to about page. Verify with Google Rich Results Test | `pending` | 2 hrs |
| **R-06** | **Open Graph / social sharing:** Dynamic OG images for listings (property photo + price + score overlay). Prefecture/city pages get hero image as OG. Verify sharing looks good on Twitter, Facebook, LINE | `pending` | 3 hrs |
| **R-07** | **Blog/guides infrastructure:** Create `/blog` route with MDX or CMS-driven content. Initial articles: "Complete Guide to Buying Akiya in Japan", "Understanding Japanese Property Hazard Data", "How Our 6-Dimension Score Works", "Japanese Real Estate Costs Explained" | `pending` | 4 hrs |
| **R-08** | **Internal linking strategy:** Homepage → featured prefectures → cities → listings. Each listing → similar listings + same city. Blog posts → relevant search queries. Footer → all prefectures. Breadcrumbs on every page | `pending` | 2 hrs |

**R-01 Details (Prefecture pages — SEO powerhouse):**
```
/prefecture/hokkaido
┌─────────────────────────────────────────────┐
│ [Hero: Hokkaido landscape photo]             │
│                                               │
│  Properties in Hokkaido (北海道)              │
│  "Japan's northern frontier — vast landscapes│
│   affordable housing, and outdoor lifestyle"  │
│                                               │
│  ┌──────┐ ┌────────┐ ┌──────────┐           │
│  │ 1,234│ │ Avg    │ │ Pop      │           │
│  │ Props│ │ ¥2.8M  │ │ 5.2M    │           │
│  └──────┘ └────────┘ └──────────┘           │
├─────────────────────────────────────────────┤
│  Featured Listings                            │
│  [Card] [Card] [Card]                        │
│  [Card] [Card] [Card]                        │
│                                               │
│  [Search all 1,234 properties in Hokkaido →] │
├─────────────────────────────────────────────┤
│  Cities in Hokkaido                           │
│  Sapporo (456) · Hakodate (89) · Asahikawa  │
│  (67) · Otaru (45) · Obihiro (34) ...       │
├─────────────────────────────────────────────┤
│  About Hokkaido                               │
│  [Area description, climate, transport,       │
│   investment outlook, lifestyle info]         │
└─────────────────────────────────────────────┘
```

---

### BLOCK S — Email Alerts & Notification System
*Users who save searches and get alerts convert at 5-10x the rate of casual browsers.*

| # | Task | Status | Effort |
|---|---|---|---|
| **S-01** | **Choose and configure email provider:** Resend (recommended — React Email integration, generous free tier). Set up account, verify domain, get API key | `pending` | 30 min |
| **S-02** | **Alert email template:** React Email template for property alert digest. Shows: alert name, X new listings matching your search, property cards (image, price, score, link), "View all on map →" CTA. Styled with our Japanese aesthetic colors | `pending` | 2 hrs |
| **S-03** | **Alert worker (cron):** Supabase Edge Function or Next.js API cron (Vercel cron). Runs daily at 9am UTC. For each active alert: query new listings since last_sent_at matching alert's bbox + filters. If new results > 0, send email. Update last_sent_at | `pending` | 3 hrs |
| **S-04** | **Instant alerts (Pro feature):** For Pro users with frequency=instant, trigger email within 1 hour of new matching listing being scraped. Use Supabase Realtime or webhook from scraper | `pending` | 3 hrs |
| **S-05** | **Email preferences page:** In settings, allow users to manage: email frequency, unsubscribe from all, email address for alerts. One-click unsubscribe link in every email | `pending` | 2 hrs |
| **S-06** | **Welcome email:** Send on signup: welcome message, "Here's what you can do", link to explore, link to set up first alert | `pending` | 1 hr |
| **S-07** | **Price drop notifications:** Track price changes between scrapes. When a wishlisted property drops in price, send targeted email: "A property you saved just dropped ¥X!" | `pending` | 2 hrs |

---

### BLOCK T — Payments & Subscription Activation
*Revenue requires working payments. AkiyaMart charges $6-15/mo.*

| # | Task | Status | Effort |
|---|---|---|---|
| **T-01** | **Stripe account setup:** Create Stripe account, get API keys, configure webhook endpoint | `pending` | 30 min |
| **T-02** | **Stripe products & prices:** Create 3 products (Free/Basic/Pro) with monthly + annual price variants. Match our pricing: Free $0, Basic $9/mo ($79/yr), Pro $29/mo ($249/yr) | `pending` | 30 min |
| **T-03** | **Checkout flow:** Pricing page CTA → Stripe Checkout Session → redirect to /dashboard on success. Handle both monthly and annual billing | `pending` | 3 hrs |
| **T-04** | **Webhook handler:** POST /api/billing/webhook — handle checkout.session.completed, subscription.updated, subscription.deleted, invoice.payment_failed. Update subscriptions table accordingly | `pending` | 3 hrs |
| **T-05** | **Customer portal:** Allow users to manage billing, cancel, update payment method via Stripe Customer Portal. Link from settings page | `pending` | 1 hr |
| **T-06** | **Feature gate enforcement:** Disable FREE_MODE. Enforce canAccess() checks: Free users get 5 listing views/day, limited wishlists, basic hazard data. Show upgrade prompts when hitting limits | `pending` | 3 hrs |
| **T-07** | **Upgrade prompts (soft paywall):** When free user hits a limit, show modal: "Upgrade to Basic for unlimited listings" with feature comparison and checkout button. Don't block aggressively (avoid AkiyaMart's "pointless signup" mistake) | `pending` | 2 hrs |
| **T-08** | **Free trial:** 7-day Pro trial for new signups. Show "X days left in trial" badge. Downgrade to Free automatically after trial expires | `pending` | 2 hrs |

---

### BLOCK U — Advanced Features (Differentiation)
*These features put us AHEAD of AkiyaMart, not just matching them.*

| # | Task | Status | Effort |
|---|---|---|---|
| **U-01** | **Property comparison tool:** Checkbox on property cards → "Compare (2/3)" floating button → comparison table (side-by-side: price, area, score, hazards, key facts) | `pending` | 4 hrs |
| **U-02** | **Price history tracking:** Store price on each scrape. When price changes, record in `price_history` table. Show chart on listing detail (line graph: price over time). "Price dropped ¥X since first listed" badge | `pending` | 3 hrs |
| **U-03** | **Neighborhood insights:** On listing detail, show 1km radius data: population density (from mesh data), nearest station + walk time, school count, medical facilities, convenience stores. Use MLIT Reinfolib data we already have client for | `pending` | 4 hrs |
| **U-04** | **Airbnb eligibility estimate:** Based on use_zone, check if short-term rental is possible under minpaku law. Show "Airbnb Eligible: Likely/Unlikely/Restricted" badge with explanation. Use zone classification data from property + legal framework rules | `pending` | 3 hrs |
| **U-05** | **Renovation cost estimator:** Based on building_area, year_built, structure: estimate renovation cost range. "Basic refresh: ¥2-4M, Full renovation: ¥5-10M, Rebuild: ¥15-25M". Add to financial calculator as optional input | `pending` | 2 hrs |
| **U-06** | **Area investment score:** Per-municipality: combine population trend (declining/stable/growing), average price trend, vacancy rate, infrastructure score → "Investment Outlook: Growing/Stable/Declining" | `pending` | 3 hrs |
| **U-07** | **Sold data / historical transactions:** Display MLIT transaction data for same area on listing detail. "Recent sales nearby: ¥X.XM avg (X transactions in 2025)". Confidence signal for pricing | `pending` | 3 hrs |
| **U-08** | **Walking directions / Street View link:** Generate Google Maps walking directions link to nearest station. Generate Google Street View link at property coordinates. Show on listing detail | `pending` | 1 hr |
| **U-09** | **PDF property report:** Generate downloadable PDF per listing: all property data, scores, hazards, map, comparables. Pro feature. Useful for sharing with advisors/agents | `pending` | 4 hrs |

---

### BLOCK V — Scale, Performance & Growth
*Getting from 1,000 to 100,000+ listings and optimizing for real traffic.*

| # | Task | Status | Effort |
|---|---|---|---|
| **V-01** | **Scale scraping to all 47 prefectures:** Run all 5 scrapers across all regions. Target: 50K+ listings in first month, 100K+ in 3 months. Monitor rate limits and adjust crawl delays | `pending` | ongoing |
| **V-02** | **Deduplication pipeline:** Same property on multiple portals → merge into single property with multiple listings. Match by: fuzzy address + geo proximity (within 50m) + similar price (±20%). Flag for review if uncertain | `pending` | 4 hrs |
| **V-03** | **Map performance at scale:** Implement server-side clustering for 100K+ markers. Use vector tiles instead of GeoJSON for map data. Lazy-load markers as viewport changes. Target: < 200ms map refresh | `pending` | 4 hrs |
| **V-04** | **Search performance:** Add PostGIS `ST_MakeEnvelope` queries (replace simple lat/lng range). Add composite indexes on (prefecture_code, price_jpy, composite_score). Full-text search on address_en. Target: < 100ms search response | `pending` | 3 hrs |
| **V-05** | **Image CDN:** Serve property images through Vercel Image Optimization or Cloudflare CDN. Auto-generate thumbnails (400px), medium (800px), full (1600px). Lazy load below-fold images | `pending` | 2 hrs |
| **V-06** | **Stale listing detection:** Mark listings as "delisted" when scraper can't find them after 3 consecutive runs. Show "This listing may no longer be available" warning. Don't delete — keep for historical data | `pending` | 2 hrs |
| **V-07** | **Error monitoring:** Set up Sentry for both Next.js and Python scraper. Alert on: scraper failures, API errors > 1% rate, DB connection issues | `pending` | 2 hrs |
| **V-08** | **A/B test infrastructure:** Simple feature flag system for testing: different hero text, CTA colors, paywall thresholds. Track conversion events in GA4 | `pending` | 3 hrs |
| **V-09** | **Brand & domain:** Finalize brand name, purchase domain, design logo (can use AI-assisted: Midjourney/DALL-E for initial concepts). Move from placeholder ◉ to real logo. Set up custom domain on Vercel | `pending` | manual |
| **V-10** | **Buying service page (AkiyaMart Direct equivalent):** Landing page for agent-matched buying service. Intake form (budget, preferred area, timeline). Agent matching flow. This is future revenue but page should exist early for validation | `pending` | 4 hrs |

---

### Dependency Graph (Blocks O-V)

```
O (Live Data) ──────────┬──→ Q (Consumer UX — needs real data for stats/featured)
                        │          ↑
P (UI/UX Overhaul) ─────┘  (Q needs P's design foundation)
                        │
                        ├──→ R (SEO Pages — needs O data + Q components)
                        ├──→ S (Email Alerts — needs O listings to alert about)
                        ├──→ U (Advanced Features — needs O data)
                        └──→ V (Scale — needs O pipeline running)

                   Q ───→ T (Payments — needs consumer UX before charging)
```

**Key rule:** O and P can run in parallel. Everything else needs O. Q needs both O and P. R and T need Q.

### Priority Execution Order (What To Do Next)

```
SESSION 1 (URGENT — unblocks everything):
  O-01 through O-08: Get real data flowing
  Result: 100+ real listings visible on live site

SESSION 2 (CRITICAL — make it not embarrassing):
  P-01 through P-05: Fix contrast, typography, colors, mobile nav
  Result: Site passes WCAG AA, looks professional, works on mobile

SESSION 3 (HIGH — consumer experience):
  Q-01, Q-04, Q-08: Homepage, property detail, search cards redesign
  O-09, O-10: Scale to 1,000+ listings, enable scheduler
  Result: Looks like a real product, not an admin tool

SESSION 4 (HIGH — SEO & growth):
  R-01 through R-04: Prefecture/city landing pages + sitemap
  Q-02, Q-05, Q-06: Stat counters, urgency hooks, trust signals
  Result: Organic traffic starts flowing, users trust the product

SESSION 5 (MEDIUM — retention & conversion):
  S-01 through S-03: Email alerts working
  Q-07, Q-09, Q-11: Dashboard redesign, alert prompts, score explanations
  Result: Users return, engagement metrics improve

SESSION 6 (MEDIUM — revenue):
  T-01 through T-08: Stripe payments, feature gates, upgrade prompts
  Result: Revenue-generating product

SESSION 7+ (ONGOING — differentiation & scale):
  U-01 through U-09: Advanced features
  V-01 through V-10: Scale & performance
  R-07, R-08: Blog content, internal linking
  Result: Competitive with AkiyaMart, unique features they lack
```

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

**Status:** Code complete (Block K), NOT yet deployed to Vultr with production env vars.
**Location:** `C:\Users\nilsb\Documents\Japan Scrapping Tool\backend\`

### What's Built:
- **5 Scrapers:** SUUMO (30s delay), HOME'S (5s), at home (5s), Akiya Banks (3s), BIT Auction (8s)
- **Database:** SQLAlchemy async, Supabase PostgreSQL connection (auto-converts `postgres://` → `postgresql+asyncpg://`)
- **Translation:** Google Cloud Translation API v2, auto-translates during scrape pipeline
- **Image Upload:** Downloads from portal URLs → uploads to Supabase Storage bucket `property-images`
- **Deduplication:** By source+source_listing_id, computes price_per_sqm
- **Scoring stubs:** New properties auto-get hazard/score records with basic inline scoring
- **Scheduler:** Configurable via `SCHEDULER_ENABLED` + `SCHEDULER_INTERVAL_HOURS` (default 6h)

### Scraper API:
```
POST /api/scrape/trigger          — Start scrape job (requires X-API-Key)
GET  /api/scrape/status/{job_id}  — Job status + task running state
GET  /api/scrape/history          — Recent 20 jobs
GET  /health                      — DB, sources, property count, service flags
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

**Ported to TypeScript (Next.js):**
- [x] Scoring engine → `src/lib/scoring.ts` (Block I-03)
- [x] Financial calculator → `src/lib/financial.ts` (Block I-02)
- [x] Currency conversion → `src/lib/currency.ts` (Block B-12)

**Stays in Python (Vultr microservice):**
- [x] All 5 scrapers (SUUMO, AtHome, Homes, BIT Auction, Akiya Banks)
- [x] Playwright browser automation
- [x] Deduplication service (SupabasePropertyService)
- [x] Google Translate integration (TranslateService)
- [x] Image upload pipeline (ImageUploadService)
- [ ] Geocoding service (Nominatim) — stubbed, not yet active
- [ ] Hazard API clients (J-SHIS, reinfolib) — enrichment tasks stubbed
- [ ] Address normalization — not yet needed
- [ ] Mesh code calculation — not yet needed

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

### Branding & Identity
- [ ] **Brand name:** Currently "JapanPropSearch" (placeholder). Need final name. Ideas: AkiyaScope, JapanNest, PropWa (和), HouseWa
- [ ] **Domain:** Need to purchase domain matching brand name
- [ ] **Logo/branding:** Need logo design. Currently using ◉ text symbol. Consider: minimal Japanese-inspired mark, kanji element, or geometric house icon
- [ ] **Hero images:** Need 10-15 high-quality Japanese real estate/landscape photos (Unsplash collections: "japanese countryside", "akiya", "traditional japanese house"). Need per-prefecture hero images for SEO pages

### Technical Decisions
- [ ] **Email provider:** Resend (recommended — React Email, good free tier, $0 for first 100/day) vs. SendGrid vs. AWS SES
- [ ] **Map tiles:** Current OSM raster (ugly) vs. MapTiler Streets free (pretty, 100K loads/mo) vs. Mapbox free (50K loads/mo). MapTiler recommended
- [ ] **Supabase schema push:** Block N added password_hash, role, contact_submissions — `db:push` NOT YET RUN
- [ ] **Scraper deployment:** Vultr VPS needs: git pull, env vars configured, service restarted — NOT YET DONE
- [ ] **Pricing strategy:** Our $9/$29 vs. AkiyaMart's $6/$15. We have more features but less data. Consider launching lower to build user base, raise later

### Content Strategy
- [ ] **City/prefecture descriptions:** Need English content for 47 prefectures + top 100 cities for SEO landing pages
- [ ] **Blog articles:** Need 5-10 foundational articles for SEO (akiya buying guide, hazard data guide, scoring explanation, cost breakdown, foreigner buying FAQ)
- [ ] **Social media:** Which platforms? (Reddit r/japanlife, Twitter/X, YouTube, podcasting)

### Resolved
- [x] **Legal:** ~~Privacy policy, terms of service text~~ → **Done** (J-10). Pages at `/privacy` and `/terms`
- [x] **Analytics:** ~~Google Analytics vs. Plausible~~ → **Chose GA4** (J-07). Conditional on NEXT_PUBLIC_GA_ID env var
- [x] **Supabase project:** Created in Tokyo region (project `oeephlppujidspbpujte`), 60 demo properties seeded

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

> **Updated 2026-02-12:** Full roadmap based on AkiyaMart benchmark analysis and UI/UX audit.
> **See Section 7b for complete gap analysis and Blocks O-V for detailed task lists.**

### NEXT SESSION TODO (Start Here — Block O)

**Goal: Get real data flowing. Nothing else matters until users see real listings.**

#### Step 1: Infrastructure (15 min)
```bash
# Push schema changes to Supabase
cd C:\Users\nilsb\Documents\japan-prop-search
npm run db:push

# Set yourself as admin
# In Supabase SQL Editor:
UPDATE users SET role = 'admin' WHERE email = 'your-email@example.com';
```

#### Step 2: Deploy Scraper to Vultr (15 min)
```bash
ssh your-vultr-server
cd /path/to/scraper
git pull

# Set environment variables:
export DATABASE_URL="postgresql://..."          # Supabase connection string
export GOOGLE_TRANSLATE_API_KEY="..."           # For English translations
export SUPABASE_URL="https://xxx.supabase.co"  # For image uploads
export SUPABASE_SERVICE_ROLE_KEY="..."          # For image uploads
export SCRAPER_API_KEY="..."                    # For remote trigger auth

# Restart service
```

#### Step 3: First Real Scrape (30 min)
- Trigger SUUMO scrape for Tokyo via admin panel or API
- Watch job status polling in real-time
- Verify: properties appear on map, images load, translations work

#### Step 4: Scale Up (2 hrs)
- Run all 5 scrapers across 5-10 prefectures
- Target: 1,000+ real listings
- Enable scheduler (SCHEDULER_ENABLED=true)
- Set up Google OAuth

### After Data Is Flowing — UI/UX Overhaul (Block P)
1. Fix color contrast (fails WCAG AA — biggest accessibility issue)
2. Typography hierarchy (everything is text-sm, needs scale)
3. Mobile navigation (currently broken — no hamburger/bottom nav)
4. Warm Japanese aesthetic colors (replace cold grays)
5. Micro-animations (hover, count-up, transitions)

### After UI Is Decent — Consumer Experience (Block Q)
1. Homepage that creates desire (hero stats, featured listings)
2. Property detail page that sells (hero images, price prominent, score explanation)
3. Search cards that attract (image-first, specs row, urgency badges)
4. Remove admin controls from consumer views

### Full Roadmap
See Blocks O through V in Section 7b for 80+ detailed tasks across 6 phases:
- **Phase 1 (O+P):** Live data + UI fix → 10% to 30%
- **Phase 2 (Q+R):** Consumer UX + SEO → 30% to 55%
- **Phase 3 (S+T):** Alerts + Payments → 55% to 75%
- **Phase 4 (U+V):** Advanced features + Scale → 75% to 90%+

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

*Last updated: 2026-02-12*
*Version: 7.0 — Added AkiyaMart benchmark analysis, UI/UX audit, gap analysis, and Blocks O-V roadmap (80+ tasks across 6 phases). Previous: Block N complete.*
