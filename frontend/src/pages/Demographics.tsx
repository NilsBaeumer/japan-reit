import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { formatManYen } from '@/lib/japanese-format'

interface MarketStats {
  total_properties: number
  active_properties: number
  avg_price: number | null
  avg_score: number | null
  price_distribution: { label: string; min: number; max: number; count: number }[]
  rebuild_ok: number
  rebuild_ng: number
  rebuild_unknown: number
}

export default function Demographics() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['demographics', 'stats'],
    queryFn: () => api.get<MarketStats>('/demographics/stats'),
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Market Analysis</h2>
        <p className="text-muted-foreground">
          Market statistics, price distribution, and property analysis
        </p>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading statistics...</p>
      ) : stats ? (
        <>
          {/* Summary Stats */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border bg-card p-6">
              <p className="text-sm font-medium text-muted-foreground">Total Properties</p>
              <p className="text-3xl font-bold mt-2">{stats.total_properties.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground mt-1">{stats.active_properties} active</p>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <p className="text-sm font-medium text-muted-foreground">Avg Price</p>
              <p className="text-3xl font-bold mt-2">
                {stats.avg_price ? formatManYen(stats.avg_price) : '-'}
              </p>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <p className="text-sm font-medium text-muted-foreground">Avg Score</p>
              <p className="text-3xl font-bold mt-2">{stats.avg_score ?? '-'}</p>
              <p className="text-xs text-muted-foreground mt-1">out of 100</p>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <p className="text-sm font-medium text-muted-foreground">Rebuild OK Rate</p>
              <p className="text-3xl font-bold mt-2">
                {stats.active_properties > 0
                  ? `${Math.round((stats.rebuild_ok / stats.active_properties) * 100)}%`
                  : '-'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {stats.rebuild_ok} OK / {stats.rebuild_ng} NG / {stats.rebuild_unknown} Unknown
              </p>
            </div>
          </div>

          {/* Price Distribution */}
          <div className="rounded-lg border bg-card p-6">
            <h3 className="text-lg font-semibold mb-4">Price Distribution</h3>
            <div className="space-y-3">
              {stats.price_distribution.map((bucket) => {
                const maxCount = Math.max(...stats.price_distribution.map(b => b.count), 1)
                const widthPct = Math.max(2, (bucket.count / maxCount) * 100)
                return (
                  <div key={bucket.label} className="flex items-center gap-4">
                    <div className="w-28 text-sm text-muted-foreground flex-shrink-0">
                      {bucket.label}
                    </div>
                    <div className="flex-1">
                      <div
                        className="bg-primary/70 rounded h-6 flex items-center px-2 text-xs text-primary-foreground font-medium"
                        style={{ width: `${widthPct}%`, minWidth: '30px' }}
                      >
                        {bucket.count}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Rebuild Status */}
          <div className="rounded-lg border bg-card p-6">
            <h3 className="text-lg font-semibold mb-4">Rebuild Status Breakdown</h3>
            <div className="flex gap-6">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-green-500" />
                <span className="text-sm">Rebuild OK: {stats.rebuild_ok}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-red-500" />
                <span className="text-sm">Rebuild NG: {stats.rebuild_ng}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-gray-400" />
                <span className="text-sm">Unknown: {stats.rebuild_unknown}</span>
              </div>
            </div>
            {stats.active_properties > 0 && (
              <div className="flex gap-0 mt-4 rounded overflow-hidden h-8">
                {stats.rebuild_ok > 0 && (
                  <div
                    className="bg-green-500 flex items-center justify-center text-xs text-white font-medium"
                    style={{ width: `${(stats.rebuild_ok / stats.active_properties) * 100}%` }}
                  >
                    {Math.round((stats.rebuild_ok / stats.active_properties) * 100)}%
                  </div>
                )}
                {stats.rebuild_ng > 0 && (
                  <div
                    className="bg-red-500 flex items-center justify-center text-xs text-white font-medium"
                    style={{ width: `${(stats.rebuild_ng / stats.active_properties) * 100}%` }}
                  >
                    {Math.round((stats.rebuild_ng / stats.active_properties) * 100)}%
                  </div>
                )}
                {stats.rebuild_unknown > 0 && (
                  <div
                    className="bg-gray-400 flex items-center justify-center text-xs text-white font-medium"
                    style={{ width: `${(stats.rebuild_unknown / stats.active_properties) * 100}%` }}
                  >
                    {Math.round((stats.rebuild_unknown / stats.active_properties) * 100)}%
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Export */}
          <div className="rounded-lg border bg-card p-6">
            <h3 className="text-lg font-semibold mb-4">Export Data</h3>
            <div className="flex gap-4">
              <a
                href="/api/v1/export/properties/csv"
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              >
                Export Properties CSV
              </a>
              <a
                href="/api/v1/export/deals/csv"
                className="px-4 py-2 text-sm border rounded-md hover:bg-accent"
              >
                Export Deals CSV
              </a>
            </div>
          </div>
        </>
      ) : (
        <p className="text-muted-foreground">Failed to load statistics.</p>
      )}
    </div>
  )
}
