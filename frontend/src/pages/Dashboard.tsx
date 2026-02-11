import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { PaginatedResponse, Property, ScrapeSource, ScrapeJob, Deal } from '@/api/types'
import { formatManYen, getScoreBgColor } from '@/lib/japanese-format'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEAL_STAGES = [
  { id: 'discovery', label: 'Discovery' },
  { id: 'analysis', label: 'Analysis' },
  { id: 'due_diligence', label: 'Due Diligence' },
  { id: 'negotiation', label: 'Negotiation' },
  { id: 'purchase', label: 'Purchase' },
  { id: 'renovation', label: 'Renovation' },
  { id: 'listing', label: 'Listing' },
  { id: 'sale', label: 'Sale' },
]

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '-'
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 0) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

function buildStageBreakdown(deals: Deal[]): string {
  const active = deals.filter(d => !['completed', 'abandoned'].includes(d.stage))
  if (active.length === 0) return 'No active deals'
  const counts: Record<string, number> = {}
  for (const d of active) {
    const stage = DEAL_STAGES.find(s => s.id === d.stage)
    const label = stage?.label ?? d.stage
    counts[label] = (counts[label] || 0) + 1
  }
  return Object.entries(counts)
    .map(([label, count]) => `${count} in ${label.toLowerCase()}`)
    .join(', ')
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const queryClient = useQueryClient()

  // --- Data queries ---
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

  const { data: recentJobs } = useQuery({
    queryKey: ['scraping', 'jobs', 'dashboard'],
    queryFn: () => api.get<ScrapeJob[]>('/scraping/jobs?limit=5'),
    refetchInterval: 15_000,
  })

  // --- Quick Action mutations ---
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)
  const [quickPrefecture, setQuickPrefecture] = useState('14')

  const suumoScrape = useMutation({
    mutationFn: () => api.post('/scraping/jobs', { source_id: 'suumo', prefecture_code: quickPrefecture, search_params: { price_max: 15000000 } }),
    onSuccess: () => {
      setActionFeedback({ type: 'success', msg: 'SUUMO scrape job started' })
      queryClient.invalidateQueries({ queryKey: ['scraping'] })
      setTimeout(() => setActionFeedback(null), 4000)
    },
    onError: (err: Error) => {
      setActionFeedback({ type: 'error', msg: err.message })
      setTimeout(() => setActionFeedback(null), 5000)
    },
  })

  const runScoring = useMutation({
    mutationFn: () => api.post('/scoring/run', {}),
    onSuccess: () => {
      setActionFeedback({ type: 'success', msg: 'Scoring batch started' })
      queryClient.invalidateQueries({ queryKey: ['properties'] })
      setTimeout(() => setActionFeedback(null), 4000)
    },
    onError: (err: Error) => {
      setActionFeedback({ type: 'error', msg: err.message })
      setTimeout(() => setActionFeedback(null), 5000)
    },
  })

  // --- Derived stats ---
  const activeDeals = deals?.filter(d => !['completed', 'abandoned'].includes(d.stage)) || []

  const scoredProperties = properties?.items.filter(p => p.composite_score !== null) ?? []
  const avgScore = scoredProperties.length
    ? Math.round(scoredProperties.reduce((sum, p) => sum + (p.composite_score ?? 0), 0) / scoredProperties.length)
    : null

  const avgPrice = properties?.items.length
    ? Math.round(
        properties.items
          .filter(p => p.price !== null)
          .reduce((sum, p) => sum + (p.price ?? 0), 0) /
        Math.max(1, properties.items.filter(p => p.price !== null).length)
      )
    : null

  const enabledSources = sources?.filter(s => s.is_enabled).length ?? 0
  const runningSources = recentJobs?.filter(j => j.status === 'running').length ?? 0

  const activeCount = properties?.items.filter(p => p.status === 'active').length ?? 0

  const lastCompletedJob = recentJobs?.find(j => j.status === 'completed')
  const hasRunningJobs = runningSources > 0

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">
          Overview of your Japanese real estate investment pipeline
        </p>
      </div>

      {/* ================================================================ */}
      {/* STAT CARDS                                                       */}
      {/* ================================================================ */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {/* Total Properties */}
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
            </svg>
          }
          iconBg="bg-blue-50 text-blue-600"
          label="Total Properties"
          value={properties?.total ?? '-'}
          subtitle={`${activeCount} active`}
          link="/search"
        />

        {/* Average Price */}
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          iconBg="bg-emerald-50 text-emerald-600"
          label="Average Price"
          value={avgPrice ? formatManYen(avgPrice) : '-'}
          subtitle="of recent listings"
        />

        {/* Average Score */}
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
            </svg>
          }
          iconBg="bg-amber-50 text-amber-600"
          label="Avg Score"
          value={avgScore ?? '-'}
          subtitle={scoredProperties.length > 0 ? `${scoredProperties.length} scored` : 'no scores yet'}
          badge={avgScore !== null ? { value: avgScore, color: getScoreBgColor(avgScore) } : undefined}
        />

        {/* Pipeline Deals */}
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
            </svg>
          }
          iconBg="bg-purple-50 text-purple-600"
          label="Pipeline Deals"
          value={activeDeals.length}
          subtitle={deals ? buildStageBreakdown(deals) : undefined}
          link="/pipeline"
        />

        {/* Scraping Sources */}
        <StatCard
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
            </svg>
          }
          iconBg="bg-teal-50 text-teal-600"
          label="Scraping Sources"
          value={enabledSources}
          subtitle={runningSources > 0 ? `${runningSources} running` : `${sources?.length ?? 0} total`}
          link="/scraping"
          pulse={runningSources > 0}
        />
      </div>

      {/* ================================================================ */}
      {/* QUICK ACTIONS                                                    */}
      {/* ================================================================ */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
        <div className="flex flex-wrap items-center gap-3">
          {/* Start SUUMO Scrape */}
          <select
            value={quickPrefecture}
            onChange={(e) => setQuickPrefecture(e.target.value)}
            className="px-3 py-2.5 text-sm rounded-md border border-border bg-background"
          >
            <option value="13">東京都</option>
            <option value="14">神奈川県</option>
            <option value="12">千葉県</option>
            <option value="11">埼玉県</option>
            <option value="27">大阪府</option>
            <option value="23">愛知県</option>
            <option value="26">京都府</option>
            <option value="28">兵庫県</option>
            <option value="40">福岡県</option>
            <option value="01">北海道</option>
            <option value="22">静岡県</option>
            <option value="34">広島県</option>
          </select>
          <button
            onClick={() => suumoScrape.mutate()}
            disabled={suumoScrape.isPending}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zm3.75 11.625a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
            </svg>
            {suumoScrape.isPending ? 'Starting...' : 'Scrape SUUMO'}
          </button>

          {/* Run Scoring */}
          <button
            onClick={() => runScoring.mutate()}
            disabled={runScoring.isPending}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
            </svg>
            {runScoring.isPending ? 'Running...' : 'Run Scoring'}
          </button>

          {/* Export CSV */}
          <a
            href="/api/v1/export/properties/csv"
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md border border-border hover:bg-accent transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Export CSV
          </a>

          {/* Feedback toast */}
          {actionFeedback && (
            <span
              className={`ml-auto text-sm font-medium px-3 py-1.5 rounded-md ${
                actionFeedback.type === 'success'
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}
            >
              {actionFeedback.msg}
            </span>
          )}
        </div>
      </div>

      {/* ================================================================ */}
      {/* RECENT PROPERTIES TABLE                                          */}
      {/* ================================================================ */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Recent Listings</h3>
          <Link to="/search" className="text-sm text-primary hover:underline">View all</Link>
        </div>
        {properties?.items.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="pb-2 pr-3 font-medium text-muted-foreground">Address</th>
                  <th className="pb-2 pr-3 font-medium text-muted-foreground">Details</th>
                  <th className="pb-2 pr-3 font-medium text-muted-foreground text-center">Rebuild</th>
                  <th className="pb-2 pr-3 font-medium text-muted-foreground text-right">Price</th>
                  <th className="pb-2 pr-3 font-medium text-muted-foreground text-center">Score</th>
                  <th className="pb-2 font-medium text-muted-foreground text-right">Listed</th>
                </tr>
              </thead>
              <tbody>
                {properties.items.map((p) => (
                  <tr key={p.id} className="border-b last:border-0 hover:bg-accent/40 transition-colors group">
                    <td className="py-3 pr-3">
                      <Link to={`/property/${p.id}`} className="font-medium text-sm hover:text-primary transition-colors">
                        {p.address_ja}
                      </Link>
                    </td>
                    <td className="py-3 pr-3 text-xs text-muted-foreground whitespace-nowrap">
                      {p.floor_plan || '-'} | {p.land_area_sqm ? `${p.land_area_sqm}m\u00B2` : '-'}
                      {p.year_built && ` | ${p.year_built}`}
                    </td>
                    <td className="py-3 pr-3 text-center">
                      {p.rebuild_possible === null ? (
                        <span className="inline-block h-2.5 w-2.5 rounded-full bg-gray-300" title="Unknown" />
                      ) : p.rebuild_possible ? (
                        <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" title="Rebuild OK" />
                      ) : (
                        <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" title="No rebuild" />
                      )}
                    </td>
                    <td className="py-3 pr-3 text-right font-bold text-sm whitespace-nowrap">
                      {p.price ? formatManYen(p.price) : '-'}
                    </td>
                    <td className="py-3 pr-3 text-center">
                      {p.composite_score !== null ? (
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${getScoreBgColor(p.composite_score)}`}>
                          {p.composite_score}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="py-3 text-right text-xs text-muted-foreground whitespace-nowrap">
                      {timeAgo(p.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No properties yet. Start a scraping job to populate listings.
          </p>
        )}
      </div>

      {/* ================================================================ */}
      {/* SYSTEM STATUS                                                    */}
      {/* ================================================================ */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">System Status</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          {/* Database */}
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0 h-8 w-8 rounded-md bg-blue-50 text-blue-600 flex items-center justify-center">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
              </svg>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Database</p>
              <p className="text-sm font-medium">{properties?.total ?? '-'} properties</p>
            </div>
          </div>

          {/* Last Scrape */}
          <div className="flex items-center gap-3">
            <div className={`flex-shrink-0 h-8 w-8 rounded-md flex items-center justify-center ${
              hasRunningJobs ? 'bg-green-50 text-green-600' : 'bg-gray-50 text-gray-500'
            }`}>
              <svg className={`h-4 w-4 ${hasRunningJobs ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182M4.031 9.865l3.182-3.182" />
              </svg>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Last Scrape</p>
              <p className="text-sm font-medium">
                {hasRunningJobs
                  ? 'Running now'
                  : lastCompletedJob?.completed_at
                    ? timeAgo(lastCompletedJob.completed_at)
                    : 'Never'}
              </p>
            </div>
          </div>

          {/* Scheduler */}
          <div className="flex items-center gap-3">
            <div className={`flex-shrink-0 h-8 w-8 rounded-md flex items-center justify-center ${
              hasRunningJobs ? 'bg-green-50 text-green-600' : 'bg-gray-50 text-gray-500'
            }`}>
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Scheduler</p>
              <p className="text-sm font-medium">
                {hasRunningJobs ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                    Active
                  </span>
                ) : (
                  <span className="text-muted-foreground">Idle</span>
                )}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// StatCard Component
// ---------------------------------------------------------------------------

function StatCard({
  icon,
  iconBg,
  label,
  value,
  subtitle,
  link,
  badge,
  pulse,
}: {
  icon: React.ReactNode
  iconBg: string
  label: string
  value: string | number
  subtitle?: string
  link?: string
  badge?: { value: number; color: string }
  pulse?: boolean
}) {
  const content = (
    <div className={`rounded-lg border bg-card p-5 ${link ? 'hover:bg-accent/30 transition-colors cursor-pointer' : ''}`}>
      <div className="flex items-start justify-between">
        <div className={`flex-shrink-0 h-10 w-10 rounded-lg ${iconBg} flex items-center justify-center`}>
          {icon}
        </div>
        {badge && (
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${badge.color}`}>
            {badge.value}
          </span>
        )}
        {pulse && (
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
          </span>
        )}
      </div>
      <p className="text-2xl font-bold mt-3">{value}</p>
      <p className="text-sm font-medium text-muted-foreground mt-0.5">{label}</p>
      {subtitle && (
        <p className="text-xs text-muted-foreground mt-1 truncate">{subtitle}</p>
      )}
    </div>
  )

  if (link) {
    return <Link to={link}>{content}</Link>
  }
  return content
}
