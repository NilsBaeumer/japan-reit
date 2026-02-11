export interface Prefecture {
  code: string
  name_ja: string
  name_en: string
  region: string
}

export interface Municipality {
  code: string
  prefecture_code: string
  name_ja: string
  name_en: string | null
}

export interface Property {
  id: string
  municipality_code: string | null
  address_ja: string
  property_type: string
  price: number | null
  land_area_sqm: number | null
  building_area_sqm: number | null
  floor_plan: string | null
  year_built: number | null
  structure: string | null
  floors: number | null
  road_width_m: number | null
  road_frontage_m: number | null
  setback_required: boolean | null
  rebuild_possible: boolean | null
  city_planning_zone: string | null
  use_zone: string | null
  coverage_ratio: number | null
  floor_area_ratio: number | null
  composite_score: number | null
  status: string
  first_seen_at: string | null
  last_seen_at: string | null
  created_at: string | null
  listings?: PropertyListing[]
}

export interface PropertyListing {
  id: string
  source: string
  source_url: string
  raw_price: number | null
  raw_title: string | null
  listing_status: string
  first_scraped_at: string | null
  last_scraped_at: string | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection'
  features: GeoJSONFeature[]
}

export interface GeoJSONFeature {
  type: 'Feature'
  geometry: {
    type: 'Point'
    coordinates: [number, number]
  }
  properties: {
    id: string
    price: number | null
    score: number | null
    address: string
    floor_plan: string | null
    land_area: number | null
    year_built: number | null
    rebuild_possible: boolean | null
  }
}

export interface Deal {
  id: string
  property_id: string
  purchase_price: number | null
  stage: string
  renovation_budget: number | null
  target_sale_price: number | null
  notes: string | null
  created_at: string | null
  updated_at: string | null
}

export interface DueDiligenceItem {
  id: string
  category: string
  item_name: string
  description: string | null
  is_completed: boolean
  completed_at: string | null
  due_date: string | null
  notes: string | null
}

export interface ScrapeJob {
  id: string
  source_id: string
  status: string
  prefecture_code: string | null
  municipality_code: string | null
  listings_found: number
  listings_new: number
  listings_updated: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

export interface ScrapeSource {
  id: string
  display_name: string
  base_url: string | null
  is_enabled: boolean
  default_interval_hours: number
}

export interface HazardAssessment {
  property_id: string
  seismic_intensity_prob: Record<string, number> | null
  pga_475yr: number | null
  liquefaction_risk: string | null
  flood_depth_max_m: number | null
  flood_zone: string | null
  tsunami_risk: string | null
  tsunami_depth_max_m: number | null
  landslide_risk: string | null
  steep_slope_zone: boolean
  landslide_prevention_zone: boolean
  mesh_code: string | null
  assessed_at: string | null
}

export interface HazardLayer {
  id: string
  name: string
  name_ja: string
  tile_url: string
}

export interface PurchaseCosts {
  purchase_price: number
  assessed_value_used: number
  broker_commission: {
    standard_excl_tax: number
    standard_incl_tax: number
    low_price_rule_applies: boolean
    actual_commission_incl_tax: number
    note: string
  }
  stamp_tax: number
  registration_tax: {
    land_transfer: number
    building_transfer: number
    total: number
  }
  acquisition_tax: {
    land: number
    building: number
    total: number
  }
  judicial_scrivener_fee: number
  total_purchase_costs: number
  total_with_price: number
  cost_ratio: number
}
