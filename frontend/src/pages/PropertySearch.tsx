import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { PaginatedResponse, Property, GeoJSONFeatureCollection } from '@/api/types'
import { formatManYen, getScoreBgColor } from '@/lib/japanese-format'
import PropertyMap from '@/components/map/PropertyMap'

export default function PropertySearch() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [viewMode, setViewMode] = useState<'table' | 'map'>('table')

  const page = Number(searchParams.get('page') || '1')
  const priceMin = searchParams.get('price_min') || ''
  const priceMax = searchParams.get('price_max') || '15000000'
  const minScore = searchParams.get('min_score') || ''
  const rebuildFilter = searchParams.get('rebuild') || ''
  const sortBy = searchParams.get('sort_by') || 'created_at'
  const sortDir = searchParams.get('sort_dir') || 'desc'

  const queryString = new URLSearchParams({
    page: String(page),
    per_page: '50',
    price_max: priceMax,
    sort_by: sortBy,
    sort_dir: sortDir,
    ...(priceMin && { price_min: priceMin }),
    ...(minScore && { min_score: minScore }),
    ...(rebuildFilter && { rebuild_possible: rebuildFilter }),
  }).toString()

  const { data, isLoading } = useQuery({
    queryKey: ['properties', queryString],
    queryFn: () => api.get<PaginatedResponse<Property>>(`/properties?${queryString}`),
  })

  // GeoJSON query for map view (uses same filters, no pagination)
  const geoQueryString = new URLSearchParams({
    price_max: priceMax,
    ...(priceMin && { price_min: priceMin }),
    ...(minScore && { min_score: minScore }),
    ...(rebuildFilter && { rebuild_possible: rebuildFilter }),
  }).toString()

  const { data: geojson, isLoading: isMapLoading } = useQuery({
    queryKey: ['properties-geojson', geoQueryString],
    queryFn: () => api.get<GeoJSONFeatureCollection>(`/properties/geojson?${geoQueryString}`),
    enabled: viewMode === 'map',
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Property Search</h2>
          <p className="text-muted-foreground">
            {data ? `${data.total} properties found` : 'Searching...'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode('table')}
            className={`px-3 py-1.5 text-sm rounded-md border ${
              viewMode === 'table' ? 'bg-primary text-primary-foreground' : 'bg-background'
            }`}
          >
            Table
          </button>
          <button
            onClick={() => setViewMode('map')}
            className={`px-3 py-1.5 text-sm rounded-md border ${
              viewMode === 'map' ? 'bg-primary text-primary-foreground' : 'bg-background'
            }`}
          >
            Map
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 p-4 rounded-lg border bg-card">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Min Price</label>
          <select
            value={priceMin}
            onChange={(e) => {
              const params = new URLSearchParams(searchParams)
              if (e.target.value) params.set('price_min', e.target.value)
              else params.delete('price_min')
              params.set('page', '1')
              setSearchParams(params)
            }}
            className="block mt-1 px-3 py-1.5 text-sm border rounded-md bg-background"
          >
            <option value="">No min</option>
            <option value="100000">10万円</option>
            <option value="500000">50万円</option>
            <option value="1000000">100万円</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Max Price</label>
          <select
            value={priceMax}
            onChange={(e) => {
              const params = new URLSearchParams(searchParams)
              params.set('price_max', e.target.value)
              params.set('page', '1')
              setSearchParams(params)
            }}
            className="block mt-1 px-3 py-1.5 text-sm border rounded-md bg-background"
          >
            <option value="500000">50万円</option>
            <option value="1000000">100万円</option>
            <option value="1500000">150万円</option>
            <option value="3000000">300万円</option>
            <option value="5000000">500万円</option>
            <option value="10000000">1,000万円</option>
            <option value="15000000">1,500万円</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Min Score</label>
          <select
            value={minScore}
            onChange={(e) => {
              const params = new URLSearchParams(searchParams)
              if (e.target.value) params.set('min_score', e.target.value)
              else params.delete('min_score')
              params.set('page', '1')
              setSearchParams(params)
            }}
            className="block mt-1 px-3 py-1.5 text-sm border rounded-md bg-background"
          >
            <option value="">Any</option>
            <option value="30">30+</option>
            <option value="50">50+</option>
            <option value="70">70+</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Rebuild</label>
          <select
            value={rebuildFilter}
            onChange={(e) => {
              const params = new URLSearchParams(searchParams)
              if (e.target.value) params.set('rebuild', e.target.value)
              else params.delete('rebuild')
              params.set('page', '1')
              setSearchParams(params)
            }}
            className="block mt-1 px-3 py-1.5 text-sm border rounded-md bg-background"
          >
            <option value="">Any</option>
            <option value="true">Rebuild OK</option>
            <option value="false">Rebuild NG</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Sort</label>
          <select
            value={`${sortBy}:${sortDir}`}
            onChange={(e) => {
              const [sb, sd] = e.target.value.split(':')
              const params = new URLSearchParams(searchParams)
              params.set('sort_by', sb)
              params.set('sort_dir', sd)
              setSearchParams(params)
            }}
            className="block mt-1 px-3 py-1.5 text-sm border rounded-md bg-background"
          >
            <option value="created_at:desc">Newest first</option>
            <option value="created_at:asc">Oldest first</option>
            <option value="price:asc">Price: low to high</option>
            <option value="price:desc">Price: high to low</option>
            <option value="composite_score:desc">Score: high to low</option>
            <option value="land_area_sqm:desc">Land area: largest</option>
          </select>
        </div>
      </div>

      {/* Results */}
      {viewMode === 'table' ? (
        <div className="rounded-lg border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-3 font-medium">Address</th>
                <th className="text-right p-3 font-medium">Price</th>
                <th className="text-center p-3 font-medium">Layout</th>
                <th className="text-right p-3 font-medium">Land</th>
                <th className="text-center p-3 font-medium">Year</th>
                <th className="text-center p-3 font-medium">Score</th>
                <th className="text-center p-3 font-medium">Rebuild</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-muted-foreground">
                    Loading...
                  </td>
                </tr>
              ) : data?.items.length ? (
                data.items.map((p) => (
                  <tr key={p.id} className="border-b hover:bg-accent/30 transition-colors">
                    <td className="p-3">
                      <Link
                        to={`/property/${p.id}`}
                        className="text-primary hover:underline font-medium"
                      >
                        {p.address_ja}
                      </Link>
                    </td>
                    <td className="p-3 text-right font-mono">
                      {p.price ? formatManYen(p.price) : '-'}
                    </td>
                    <td className="p-3 text-center">{p.floor_plan || '-'}</td>
                    <td className="p-3 text-right">
                      {p.land_area_sqm ? `${p.land_area_sqm}m²` : '-'}
                    </td>
                    <td className="p-3 text-center">{p.year_built || '-'}</td>
                    <td className="p-3 text-center">
                      {p.composite_score !== null ? (
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getScoreBgColor(p.composite_score)}`}>
                          {p.composite_score}
                        </span>
                      ) : '-'}
                    </td>
                    <td className="p-3 text-center">
                      {p.rebuild_possible === null ? '?' :
                        p.rebuild_possible ? (
                          <span className="text-green-600">OK</span>
                        ) : (
                          <span className="text-red-600">NG</span>
                        )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-muted-foreground">
                    No properties found. Run a scraping job first.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="flex items-center justify-between p-3 border-t">
              <p className="text-sm text-muted-foreground">
                Page {data.page} of {data.pages} ({data.total} total)
              </p>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => {
                    const params = new URLSearchParams(searchParams)
                    params.set('page', String(page - 1))
                    setSearchParams(params)
                  }}
                  className="px-3 py-1 text-sm border rounded-md disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  disabled={page >= data.pages}
                  onClick={() => {
                    const params = new URLSearchParams(searchParams)
                    params.set('page', String(page + 1))
                    setSearchParams(params)
                  }}
                  className="px-3 py-1 text-sm border rounded-md disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-lg border bg-card overflow-hidden" style={{ height: '650px' }}>
          <PropertyMap geojson={geojson ?? null} isLoading={isMapLoading} />
        </div>
      )}
    </div>
  )
}
