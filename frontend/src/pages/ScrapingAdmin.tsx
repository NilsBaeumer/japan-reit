import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { ScrapeSource, ScrapeJob } from '@/api/types'

const PREFECTURES = [
  { code: '13', name: 'Tokyo' },
  { code: '14', name: 'Kanagawa' },
  { code: '27', name: 'Osaka' },
  { code: '12', name: 'Chiba' },
  { code: '11', name: 'Saitama' },
  { code: '23', name: 'Aichi' },
  { code: '26', name: 'Kyoto' },
  { code: '28', name: 'Hyogo' },
] satisfies readonly { code: string; name: string }[]

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-700',
    running: 'bg-blue-100 text-blue-700 animate-pulse',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
        styles[status] ?? 'bg-gray-100 text-gray-700'
      }`}
    >
      {status === 'running' && (
        <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-blue-500 animate-ping" />
      )}
      {status}
    </span>
  )
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start) return '-'
  const s = new Date(start).getTime()
  const e = end ? new Date(end).getTime() : Date.now()
  const seconds = Math.round((e - s) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remaining = seconds % 60
  return `${minutes}m ${remaining}s`
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export default function ScrapingAdmin() {
  const queryClient = useQueryClient()
  const [selectedSource, setSelectedSource] = useState('')
  const [selectedPrefecture, setSelectedPrefecture] = useState('')
  const [schedulerInterval, setSchedulerInterval] = useState(6)
  const [jobStatusFilter, setJobStatusFilter] = useState('')
  const [jobSourceFilter, setJobSourceFilter] = useState('')

  // ---------- Queries ----------

  const { data: sources, isLoading: sourcesLoading } = useQuery({
    queryKey: ['scraping', 'sources'],
    queryFn: () => api.get<ScrapeSource[]>('/scraping/sources'),
  })

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['scraping', 'jobs', jobStatusFilter, jobSourceFilter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: '50' })
      if (jobStatusFilter) params.set('status', jobStatusFilter)
      if (jobSourceFilter) params.set('source_id', jobSourceFilter)
      return api.get<ScrapeJob[]>(`/scraping/jobs?${params.toString()}`)
    },
    refetchInterval: 10_000,
  })

  // ---------- Mutations ----------

  const createJob = useMutation({
    mutationFn: (data: { source_id: string; prefecture_code?: string }) =>
      api.post('/scraping/jobs', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scraping', 'jobs'] })
      setSelectedSource('')
      setSelectedPrefecture('')
    },
  })

  const startScheduler = useMutation({
    mutationFn: (intervalHours: number) =>
      api.post(`/scraping/scheduler/start?interval_hours=${intervalHours}`, {}),
  })

  const stopScheduler = useMutation({
    mutationFn: () => api.post('/scraping/scheduler/stop', {}),
  })

  // ---------- Helpers ----------

  const sourceNameMap = new Map(sources?.map((s) => [s.id, s.display_name]) ?? [])
  const prefectureNameMap = new Map(PREFECTURES.map((p) => [p.code, p.name]))

  const runningJobsCount = jobs?.filter((j) => j.status === 'running').length ?? 0
  const completedJobsCount = jobs?.filter((j) => j.status === 'completed').length ?? 0
  const failedJobsCount = jobs?.filter((j) => j.status === 'failed').length ?? 0

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Scraping Admin</h2>
        <p className="text-muted-foreground">
          Manage data sources, schedule scraping jobs, and monitor progress
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border bg-card p-6">
          <p className="text-sm font-medium text-muted-foreground">Sources</p>
          <p className="text-3xl font-bold mt-2">{sources?.length ?? '-'}</p>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <p className="text-sm font-medium text-muted-foreground">Running Jobs</p>
          <p className="text-3xl font-bold mt-2 text-blue-600">{runningJobsCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <p className="text-sm font-medium text-muted-foreground">Completed</p>
          <p className="text-3xl font-bold mt-2 text-green-600">{completedJobsCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-6">
          <p className="text-sm font-medium text-muted-foreground">Failed</p>
          <p className="text-3xl font-bold mt-2 text-red-600">{failedJobsCount}</p>
        </div>
      </div>

      {/* Data Sources Cards */}
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-4">Data Sources</h3>
        {sourcesLoading ? (
          <p className="text-sm text-muted-foreground">Loading sources...</p>
        ) : sources?.length ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {sources.map((s) => (
              <div
                key={s.id}
                className="rounded-lg border p-4 space-y-3 transition-colors hover:bg-accent/30"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-sm">{s.display_name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5 break-all">
                      {s.base_url || 'No URL configured'}
                    </p>
                  </div>
                  <span
                    className={`flex-shrink-0 ml-2 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      s.is_enabled
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {s.is_enabled ? 'Active' : 'Disabled'}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Every {s.default_interval_hours}h
                  </span>
                  <span className="text-muted-foreground/50">|</span>
                  <span className="font-mono text-[10px]">{s.id.slice(0, 8)}...</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No sources configured.</p>
        )}
      </div>

      {/* New Job Form + Scheduler Controls */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Launch Scrape Job */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4">Launch Scrape Job</h3>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Source</label>
              <select
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
                className="block w-full mt-1 px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="">Select a source...</option>
                {sources?.map((s) => (
                  <option key={s.id} value={s.id} disabled={!s.is_enabled}>
                    {s.display_name} {!s.is_enabled ? '(disabled)' : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Prefecture (optional)</label>
              <select
                value={selectedPrefecture}
                onChange={(e) => setSelectedPrefecture(e.target.value)}
                className="block w-full mt-1 px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="">All prefectures</option>
                {PREFECTURES.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.name} ({p.code})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  if (!selectedSource) return
                  createJob.mutate({
                    source_id: selectedSource,
                    ...(selectedPrefecture && { prefecture_code: selectedPrefecture }),
                  })
                }}
                disabled={!selectedSource || createJob.isPending}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm font-medium disabled:opacity-50 transition-colors"
              >
                {createJob.isPending ? 'Creating...' : 'Start Scrape'}
              </button>
              {createJob.isSuccess && (
                <span className="text-sm text-green-600 font-medium">Job created!</span>
              )}
              {createJob.isError && (
                <span className="text-sm text-red-600 font-medium">
                  {(createJob.error as Error).message}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Scheduler Controls */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-4">Scheduler Controls</h3>
          <p className="text-sm text-muted-foreground mb-4">
            The scheduler automatically runs scraping jobs at the configured interval across all
            enabled sources.
          </p>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Interval (hours)</label>
              <input
                type="number"
                min={1}
                max={168}
                value={schedulerInterval}
                onChange={(e) => setSchedulerInterval(Number(e.target.value))}
                className="block w-full mt-1 px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => startScheduler.mutate(schedulerInterval)}
                disabled={startScheduler.isPending}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium disabled:opacity-50 transition-colors"
              >
                {startScheduler.isPending ? 'Starting...' : 'Start Scheduler'}
              </button>
              <button
                onClick={() => stopScheduler.mutate()}
                disabled={stopScheduler.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm font-medium disabled:opacity-50 transition-colors"
              >
                {stopScheduler.isPending ? 'Stopping...' : 'Stop Scheduler'}
              </button>
            </div>
            {startScheduler.isSuccess && (
              <p className="text-sm text-green-600 font-medium">
                Scheduler started (every {schedulerInterval}h)
              </p>
            )}
            {startScheduler.isError && (
              <p className="text-sm text-red-600 font-medium">
                {(startScheduler.error as Error).message}
              </p>
            )}
            {stopScheduler.isSuccess && (
              <p className="text-sm text-green-600 font-medium">Scheduler stopped</p>
            )}
            {stopScheduler.isError && (
              <p className="text-sm text-red-600 font-medium">
                {(stopScheduler.error as Error).message}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
          <div>
            <h3 className="text-lg font-semibold">Recent Jobs</h3>
            <p className="text-xs text-muted-foreground">Auto-refreshes every 10 seconds</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <select
              value={jobSourceFilter}
              onChange={(e) => setJobSourceFilter(e.target.value)}
              className="px-3 py-1.5 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              <option value="">All sources</option>
              {sources?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name}
                </option>
              ))}
            </select>
            <select
              value={jobStatusFilter}
              onChange={(e) => setJobStatusFilter(e.target.value)}
              className="px-3 py-1.5 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left p-2 font-medium">Source</th>
                <th className="text-center p-2 font-medium">Status</th>
                <th className="text-left p-2 font-medium">Prefecture</th>
                <th className="text-center p-2 font-medium">Found</th>
                <th className="text-center p-2 font-medium">New</th>
                <th className="text-center p-2 font-medium">Updated</th>
                <th className="text-left p-2 font-medium">Started</th>
                <th className="text-left p-2 font-medium">Duration</th>
                <th className="text-left p-2 font-medium">Error</th>
              </tr>
            </thead>
            <tbody>
              {jobsLoading ? (
                <tr>
                  <td colSpan={9} className="p-4 text-center text-muted-foreground">
                    Loading jobs...
                  </td>
                </tr>
              ) : jobs?.length ? (
                jobs.map((j) => (
                  <tr
                    key={j.id}
                    className="border-b hover:bg-accent/30 transition-colors"
                  >
                    <td className="p-2 font-medium">
                      {sourceNameMap.get(j.source_id) ?? j.source_id.slice(0, 8)}
                    </td>
                    <td className="p-2 text-center">
                      <StatusBadge status={j.status} />
                    </td>
                    <td className="p-2 text-muted-foreground">
                      {j.prefecture_code
                        ? `${prefectureNameMap.get(j.prefecture_code) ?? ''} (${j.prefecture_code})`
                        : '-'}
                    </td>
                    <td className="p-2 text-center font-mono">{j.listings_found}</td>
                    <td className="p-2 text-center font-mono text-green-600">
                      {j.listings_new > 0 ? `+${j.listings_new}` : j.listings_new}
                    </td>
                    <td className="p-2 text-center font-mono text-blue-600">
                      {j.listings_updated > 0 ? `~${j.listings_updated}` : j.listings_updated}
                    </td>
                    <td className="p-2 text-xs text-muted-foreground whitespace-nowrap">
                      {formatTimestamp(j.started_at ?? j.created_at)}
                    </td>
                    <td className="p-2 text-xs text-muted-foreground whitespace-nowrap">
                      {j.status === 'running'
                        ? formatDuration(j.started_at, null)
                        : formatDuration(j.started_at, j.completed_at)}
                    </td>
                    <td className="p-2 text-xs text-red-600 max-w-[250px] truncate" title={j.error_message ?? undefined}>
                      {j.error_message || '-'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="p-8 text-center text-muted-foreground">
                    No jobs found. Create a scrape job above to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
