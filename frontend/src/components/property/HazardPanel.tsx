import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { HazardAssessment } from '@/api/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HazardPanelProps {
  propertyId: string
}

type RiskLevel = 'low' | 'medium' | 'high' | 'very_high'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const JMA_SCALES = ['5-', '5+', '6-', '6+', '7'] as const

function getRiskBadgeClasses(level: string | null): string {
  const normalized = level?.toLowerCase().replace(/\s+/g, '_') ?? ''
  switch (normalized) {
    case 'low':
      return 'bg-green-100 text-green-800'
    case 'medium':
      return 'bg-yellow-100 text-yellow-800'
    case 'high':
      return 'bg-orange-100 text-orange-800'
    case 'very_high':
      return 'bg-red-100 text-red-800'
    default:
      return 'bg-gray-100 text-gray-600'
  }
}

function getRiskLabel(level: string | null): string {
  if (!level) return 'N/A'
  return level
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function getPgaColor(pga: number | null): string {
  if (pga === null) return 'text-muted-foreground'
  if (pga < 0.1) return 'text-green-600'
  if (pga < 0.3) return 'text-yellow-600'
  if (pga < 0.6) return 'text-orange-600'
  return 'text-red-600'
}

function getFloodColor(depth: number | null): string {
  if (depth === null) return 'text-muted-foreground'
  if (depth <= 0) return 'text-green-600'
  if (depth < 0.5) return 'text-yellow-600'
  if (depth < 3) return 'text-orange-600'
  return 'text-red-600'
}

function formatProbability(value: number | undefined): string {
  if (value === undefined || value === null) return '-'
  return `${(value * 100).toFixed(1)}%`
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RiskBadge({ level }: { level: string | null }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRiskBadgeClasses(level)}`}>
      {getRiskLabel(level)}
    </span>
  )
}

function SectionHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      {children}
    </div>
  )
}

function DataRow({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex justify-between items-center py-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-sm font-medium ${className ?? ''}`}>{value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function SeismicSection({ hazard }: { hazard: HazardAssessment }) {
  return (
    <div className="space-y-2">
      <SectionHeader title="Seismic Risk">
        <RiskBadge level={hazard.liquefaction_risk} />
      </SectionHeader>

      <DataRow
        label="PGA (475-yr)"
        value={hazard.pga_475yr !== null ? `${hazard.pga_475yr.toFixed(3)} g` : 'N/A'}
        className={getPgaColor(hazard.pga_475yr)}
      />

      <DataRow
        label="Liquefaction"
        value={getRiskLabel(hazard.liquefaction_risk)}
      />

      {hazard.seismic_intensity_prob && (
        <div className="mt-2">
          <p className="text-xs text-muted-foreground mb-1.5">
            30-year exceedance probability by JMA intensity:
          </p>
          <div className="grid grid-cols-5 gap-1 text-center">
            {JMA_SCALES.map((scale) => (
              <div key={scale} className="rounded-md border bg-muted/40 px-1 py-1.5">
                <div className="text-[10px] text-muted-foreground font-medium">{scale}</div>
                <div className="text-xs font-semibold mt-0.5">
                  {formatProbability(hazard.seismic_intensity_prob?.[scale])}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function FloodSection({ hazard }: { hazard: HazardAssessment }) {
  const floodRisk: RiskLevel | null =
    hazard.flood_depth_max_m === null ? null :
    hazard.flood_depth_max_m <= 0 ? 'low' :
    hazard.flood_depth_max_m < 0.5 ? 'medium' :
    hazard.flood_depth_max_m < 3 ? 'high' : 'very_high'

  return (
    <div className="space-y-2">
      <SectionHeader title="Flood Risk">
        <RiskBadge level={floodRisk} />
      </SectionHeader>

      <DataRow
        label="Max Flood Depth"
        value={hazard.flood_depth_max_m !== null ? `${hazard.flood_depth_max_m.toFixed(1)} m` : 'N/A'}
        className={getFloodColor(hazard.flood_depth_max_m)}
      />

      <DataRow
        label="Flood Zone"
        value={hazard.flood_zone ?? 'N/A'}
      />
    </div>
  )
}

function TsunamiSection({ hazard }: { hazard: HazardAssessment }) {
  return (
    <div className="space-y-2">
      <SectionHeader title="Tsunami Risk">
        <RiskBadge level={hazard.tsunami_risk} />
      </SectionHeader>

      <DataRow
        label="Risk Level"
        value={getRiskLabel(hazard.tsunami_risk)}
      />

      <DataRow
        label="Max Depth"
        value={hazard.tsunami_depth_max_m !== null ? `${hazard.tsunami_depth_max_m.toFixed(1)} m` : 'N/A'}
      />
    </div>
  )
}

function LandslideSection({ hazard }: { hazard: HazardAssessment }) {
  return (
    <div className="space-y-2">
      <SectionHeader title="Landslide Risk">
        <RiskBadge level={hazard.landslide_risk} />
      </SectionHeader>

      <DataRow
        label="Risk Level"
        value={getRiskLabel(hazard.landslide_risk)}
      />

      <DataRow
        label="Steep Slope Zone"
        value={hazard.steep_slope_zone ? 'Yes' : 'No'}
        className={hazard.steep_slope_zone ? 'text-orange-600' : 'text-green-600'}
      />

      <DataRow
        label="Landslide Prevention Zone"
        value={hazard.landslide_prevention_zone ? 'Yes' : 'No'}
        className={hazard.landslide_prevention_zone ? 'text-orange-600' : 'text-green-600'}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function HazardPanel({ propertyId }: HazardPanelProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['hazard', propertyId],
    queryFn: () => api.get<HazardAssessment | { detail: string }>(`/hazards/${propertyId}`),
    enabled: !!propertyId,
  })

  if (isLoading) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Hazard Assessment</h3>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          Loading hazard data...
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Hazard Assessment</h3>
        <p className="text-sm text-destructive">Failed to load hazard data.</p>
      </div>
    )
  }

  // Check for "no assessment" response
  if (!data || 'detail' in data) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Hazard Assessment</h3>
        <p className="text-sm text-muted-foreground">
          No hazard assessment available for this property.
        </p>
      </div>
    )
  }

  const hazard = data as HazardAssessment

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold">Hazard Assessment</h3>
        {hazard.assessed_at && (
          <span className="text-xs text-muted-foreground">
            Assessed: {new Date(hazard.assessed_at).toLocaleDateString()}
          </span>
        )}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <SeismicSection hazard={hazard} />
        <FloodSection hazard={hazard} />
        <TsunamiSection hazard={hazard} />
        <LandslideSection hazard={hazard} />
      </div>

      {hazard.mesh_code && (
        <div className="mt-4 pt-3 border-t text-xs text-muted-foreground">
          Mesh code: {hazard.mesh_code}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tiny inline spinner (matches pattern from PropertyMap)
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-primary"
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
