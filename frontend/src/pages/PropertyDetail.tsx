import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { Property, Deal } from '@/api/types'
import { formatYen, formatManYen, formatArea, getScoreBgColor } from '@/lib/japanese-format'
import HazardPanel from '@/components/property/HazardPanel'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScoreBreakdown {
  property_id: string
  rebuild_score: number | null
  hazard_score: number | null
  infrastructure_score: number | null
  demographic_score: number | null
  value_score: number | null
  condition_score: number | null
  composite_score: number
  weights: Record<string, number>
  scoring_version: string
  scored_at: string | null
}

interface ScoreDimension {
  key: string
  label: string
  weight: number
  weightLabel: string
}

const SCORE_DIMENSIONS: ScoreDimension[] = [
  { key: 'rebuild_score', label: 'Rebuild', weight: 0.25, weightLabel: '25%' },
  { key: 'hazard_score', label: 'Hazard', weight: 0.20, weightLabel: '20%' },
  { key: 'infrastructure_score', label: 'Infrastructure', weight: 0.15, weightLabel: '15%' },
  { key: 'demographic_score', label: 'Demographic', weight: 0.15, weightLabel: '15%' },
  { key: 'value_score', label: 'Value', weight: 0.15, weightLabel: '15%' },
  { key: 'condition_score', label: 'Condition', weight: 0.10, weightLabel: '10%' },
]

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function PropertyDetail() {
  const { id } = useParams<{ id: string }>()

  const { data: property, isLoading } = useQuery({
    queryKey: ['property', id],
    queryFn: () => api.get<Property & { listings: any[] }>(`/properties/${id}`),
    enabled: !!id,
  })

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">Loading property...</div>
  }

  if (!property) {
    return <div className="p-8 text-center text-muted-foreground">Property not found</div>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/search" className="text-sm text-muted-foreground hover:text-primary">
            &larr; Back to search
          </Link>
          <h2 className="text-2xl font-bold tracking-tight mt-2">
            {property.address_ja}
          </h2>
          <div className="flex items-center gap-3 mt-2">
            {property.price && (
              <span className="text-xl font-bold text-primary">
                {formatManYen(property.price)}
              </span>
            )}
            {property.composite_score !== null && (
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${getScoreBgColor(property.composite_score)}`}>
                Score: {property.composite_score}
              </span>
            )}
            <span className={`px-2 py-0.5 rounded-full text-xs ${
              property.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
            }`}>
              {property.status}
            </span>
          </div>
        </div>
        <PipelineButton propertyId={property.id} />
      </div>

      {/* Property Details Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Key Facts */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4">Key Facts</h3>
          <dl className="space-y-3">
            <DetailRow label="Property Type" value={property.property_type || '-'} />
            <DetailRow label="Price" value={property.price ? formatYen(property.price) : '-'} />
            <DetailRow label="Floor Plan" value={property.floor_plan || '-'} />
            <DetailRow label="Land Area" value={property.land_area_sqm ? formatArea(property.land_area_sqm) : '-'} />
            <DetailRow label="Building Area" value={property.building_area_sqm ? formatArea(property.building_area_sqm) : '-'} />
            <DetailRow label="Year Built" value={property.year_built?.toString() || '-'} />
            <DetailRow label="Structure" value={property.structure || '-'} />
            <DetailRow label="Floors" value={property.floors?.toString() || '-'} />
          </dl>
        </div>

        {/* Road & Rebuild */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4">Road & Rebuild Status</h3>
          <dl className="space-y-3">
            <DetailRow label="Road Width" value={property.road_width_m ? `${property.road_width_m}m` : '-'} />
            <DetailRow label="Road Frontage" value={property.road_frontage_m ? `${property.road_frontage_m}m` : '-'} />
            <DetailRow
              label="Rebuild Possible"
              value={
                property.rebuild_possible === null ? 'Unknown' :
                property.rebuild_possible ? 'Yes (OK)' : 'No (NG)'
              }
              highlight={property.rebuild_possible === false ? 'destructive' : property.rebuild_possible ? 'success' : undefined}
            />
            <DetailRow label="Setback Required" value={property.setback_required === null ? '-' : property.setback_required ? 'Yes' : 'No'} />
          </dl>

          <h3 className="text-lg font-semibold mb-4 mt-6">Zoning</h3>
          <dl className="space-y-3">
            <DetailRow label="City Planning Zone" value={property.city_planning_zone || '-'} />
            <DetailRow label="Use Zone" value={property.use_zone || '-'} />
            <DetailRow label="Coverage Ratio" value={property.coverage_ratio ? `${property.coverage_ratio}%` : '-'} />
            <DetailRow label="Floor Area Ratio" value={property.floor_area_ratio ? `${property.floor_area_ratio}%` : '-'} />
          </dl>
        </div>
      </div>

      {/* Score Breakdown */}
      {id && <ScoreBreakdownPanel propertyId={id} />}

      {/* Hazard Assessment */}
      {id && <HazardPanel propertyId={id} />}

      {/* Source Listings */}
      {property.listings && property.listings.length > 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4">Source Listings</h3>
          <div className="space-y-3">
            {property.listings.map((l: any) => (
              <div key={l.id} className="flex items-center justify-between p-3 rounded-md border">
                <div>
                  <span className="font-medium text-sm capitalize">{l.source}</span>
                  {l.raw_title && <p className="text-xs text-muted-foreground mt-1">{l.raw_title}</p>}
                </div>
                <a
                  href={l.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  View on portal &rarr;
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pipeline Button
// ---------------------------------------------------------------------------

function PipelineButton({ propertyId }: { propertyId: string }) {
  const [successDealId, setSuccessDealId] = useState<string | null>(null)

  // Check if property already has a deal
  const { data: existingDeals, isLoading: isCheckingDeals } = useQuery({
    queryKey: ['deals-for-property', propertyId],
    queryFn: () => api.get<Deal[]>('/pipeline/deals'),
    enabled: !!propertyId,
    select: (deals) => deals.filter((d) => d.property_id === propertyId),
  })

  const existingDeal = existingDeals && existingDeals.length > 0 ? existingDeals[0] : null

  // Create deal mutation
  const { mutate: createDeal, isPending, error } = useMutation({
    mutationFn: () =>
      api.post<Deal>('/pipeline/deals', { property_id: propertyId }),
    onSuccess: (deal) => {
      setSuccessDealId(deal.id)
    },
  })

  // Loading state while checking for existing deals
  if (isCheckingDeals) {
    return (
      <button
        disabled
        className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-muted text-muted-foreground rounded-md cursor-not-allowed"
      >
        <Spinner />
        Checking...
      </button>
    )
  }

  // Property already has a deal in pipeline
  if (existingDeal) {
    return (
      <Link
        to="/pipeline"
        className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-primary/10 text-primary border border-primary/20 rounded-md hover:bg-primary/20 transition-colors font-medium"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        View in Pipeline
      </Link>
    )
  }

  // Successfully created
  if (successDealId) {
    return (
      <div className="flex items-center gap-3">
        <span className="inline-flex items-center gap-1.5 text-sm text-green-700 font-medium">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          Added to pipeline
        </span>
        <Link
          to="/pipeline"
          className="inline-flex items-center gap-1 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors font-medium"
        >
          Open Pipeline &rarr;
        </Link>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-end gap-2">
        <button
          onClick={() => createDeal()}
          className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors font-medium"
        >
          Retry
        </button>
        <span className="text-xs text-destructive max-w-[250px] text-right">
          {error instanceof Error ? error.message : 'Failed to add to pipeline'}
        </span>
      </div>
    )
  }

  // Default / creating state
  return (
    <button
      onClick={() => createDeal()}
      disabled={isPending}
      className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors font-medium disabled:opacity-60 disabled:cursor-not-allowed"
    >
      {isPending ? (
        <>
          <Spinner />
          Adding...
        </>
      ) : (
        <>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add to Pipeline
        </>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Score Breakdown Panel
// ---------------------------------------------------------------------------

function ScoreBreakdownPanel({ propertyId }: { propertyId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['scoring', propertyId],
    queryFn: () => api.get<ScoreBreakdown | { detail: string }>(`/scoring/${propertyId}`),
    enabled: !!propertyId,
  })

  if (isLoading) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Score Breakdown</h3>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          Loading scoring data...
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Score Breakdown</h3>
        <p className="text-sm text-destructive">Failed to load scoring data.</p>
      </div>
    )
  }

  // Check for "no score" response
  if (!data || 'detail' in data) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Score Breakdown</h3>
        <p className="text-sm text-muted-foreground">
          No scoring data available for this property.
        </p>
      </div>
    )
  }

  const score = data as ScoreBreakdown

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold">Score Breakdown</h3>
        <div className="flex items-center gap-3">
          {score.scored_at && (
            <span className="text-xs text-muted-foreground">
              v{score.scoring_version} &middot; {new Date(score.scored_at).toLocaleDateString()}
            </span>
          )}
          <span className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreBgColor(score.composite_score)}`}>
            {score.composite_score.toFixed(1)}
          </span>
        </div>
      </div>

      <div className="space-y-4">
        {SCORE_DIMENSIONS.map((dim) => {
          const value = score[dim.key as keyof ScoreBreakdown] as number | null
          return (
            <ScoreBar
              key={dim.key}
              label={dim.label}
              value={value}
              weightLabel={dim.weightLabel}
            />
          )
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-6 pt-4 border-t">
        <span className="text-xs text-muted-foreground">Score ranges:</span>
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-green-500" />
          <span className="text-xs text-muted-foreground">70-100</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-yellow-500" />
          <span className="text-xs text-muted-foreground">40-69</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-red-500" />
          <span className="text-xs text-muted-foreground">0-39</span>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Score Bar
// ---------------------------------------------------------------------------

function ScoreBar({
  label,
  value,
  weightLabel,
}: {
  label: string
  value: number | null
  weightLabel: string
}) {
  const displayValue = value !== null ? Math.round(value) : null
  const barWidth = value !== null ? Math.max(value, 2) : 0 // minimum 2% width for visibility
  const barColor =
    value === null ? 'bg-muted' :
    value >= 70 ? 'bg-green-500' :
    value >= 40 ? 'bg-yellow-500' :
    'bg-red-500'
  const textColor =
    value === null ? 'text-muted-foreground' :
    value >= 70 ? 'text-green-700' :
    value >= 40 ? 'text-yellow-700' :
    'text-red-700'

  return (
    <div className="group">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">{label}</span>
          <span className="text-xs text-muted-foreground">({weightLabel})</span>
        </div>
        <span className={`text-sm font-bold tabular-nums ${textColor}`}>
          {displayValue !== null ? `${displayValue} / 100` : 'N/A'}
        </span>
      </div>
      <div className="h-3 w-full rounded-full bg-muted/60 overflow-hidden">
        {value !== null && (
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${barColor}`}
            style={{ width: `${barWidth}%` }}
          />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Detail Row
// ---------------------------------------------------------------------------

function DetailRow({
  label,
  value,
  highlight,
}: {
  label: string
  value: string
  highlight?: 'success' | 'destructive'
}) {
  return (
    <div className="flex justify-between items-center">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={`text-sm font-medium ${
        highlight === 'success' ? 'text-green-600' :
        highlight === 'destructive' ? 'text-red-600' : ''
      }`}>
        {value}
      </dd>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-current"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
