import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { PaginatedResponse, Property, ScrapeSource, Deal } from '@/api/types'
import { formatManYen, getScoreBgColor } from '@/lib/japanese-format'

export default function Dashboard() {
  const { data: properties } = useQuery({
    queryKey: ['properties', 'recent'],
    queryFn: () =>
      api.get<PaginatedResponse<Property>>('/properties?per_page=10&sort_by=created_at&sort_dir=desc'),
  })

  const { data: sources } = useQuery({
    queryKey: ['scraping', 'sources'],
    queryFn: () => api.get<ScrapeSource[]>('/scraping/sources'),
  })

  const { data: deals } = useQuery({
    queryKey: ['pipeline', 'deals'],
    queryFn: () => api.get<Deal[]>('/pipeline/deals'),
  })

  const activeDeals = deals?.filter(d => !['completed', 'abandoned'].includes(d.stage)) || []
  const avgScore = properties?.items.length
    ? Math.round(
        properties.items
          .filter(p => p.composite_score !== null)
          .reduce((sum, p) => sum + (p.composite_score ?? 0), 0) /
        Math.max(1, properties.items.filter(p => p.composite_score !== null).length)
      )
    : null

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">
          Overview of your Japanese real estate investment pipeline
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active Listings"
          value={properties?.total ?? '-'}
          link="/search"
        />
        <StatCard
          label="Data Sources"
          value={sources?.filter(s => s.is_enabled).length ?? '-'}
          subtitle={`${sources?.length ?? 0} total`}
          link="/scraping"
        />
        <StatCard
          label="Pipeline Deals"
          value={activeDeals.length}
          subtitle={deals ? `${deals.length} total` : undefined}
          link="/pipeline"
        />
        <StatCard
          label="Avg Score"
          value={avgScore ?? '-'}
          subtitle="of recent listings"
        />
      </div>

      {/* Recent Properties */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Recent Listings</h3>
          <Link to="/search" className="text-sm text-primary hover:underline">View all</Link>
        </div>
        {properties?.items.length ? (
          <div className="space-y-3">
            {properties.items.map((p) => (
              <Link
                key={p.id}
                to={`/property/${p.id}`}
                className="flex items-center justify-between p-3 rounded-md bg-accent/50 hover:bg-accent transition-colors"
              >
                <div>
                  <p className="font-medium text-sm">{p.address_ja}</p>
                  <p className="text-xs text-muted-foreground">
                    {p.floor_plan || '-'} | {p.land_area_sqm ? `${p.land_area_sqm}m²` : '-'}
                    {p.year_built && ` | Built ${p.year_built}`}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-sm">
                    {p.price ? formatManYen(p.price) : '-'}
                  </p>
                  {p.composite_score !== null && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getScoreBgColor(p.composite_score)}`}>
                      {p.composite_score}
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No properties yet. Start a scraping job to populate listings.
          </p>
        )}
      </div>

      {/* Scraping Sources */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Data Sources</h3>
        {sources?.length ? (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {sources.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between p-3 rounded-md border"
              >
                <div>
                  <p className="font-medium text-sm">{s.display_name}</p>
                  <p className="text-xs text-muted-foreground">
                    Every {s.default_interval_hours}h
                  </p>
                </div>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    s.is_enabled
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {s.is_enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Loading sources...</p>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, subtitle, link }: {
  label: string
  value: string | number
  subtitle?: string
  link?: string
}) {
  const content = (
    <div className={`rounded-lg border bg-card p-6 ${link ? 'hover:bg-accent/30 transition-colors' : ''}`}>
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <p className="text-3xl font-bold mt-2">{value}</p>
      {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
    </div>
  )
  if (link) {
    return <Link to={link}>{content}</Link>
  }
  return content
}
