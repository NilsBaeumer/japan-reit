import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { Property } from '@/api/types'
import { formatYen, formatManYen, formatArea, getScoreBgColor } from '@/lib/japanese-format'
import HazardPanel from '@/components/property/HazardPanel'

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
        <button className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90">
          Add to Pipeline
        </button>
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
