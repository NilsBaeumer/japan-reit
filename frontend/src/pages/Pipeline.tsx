import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { Deal, DueDiligenceItem } from '@/api/types'
import { formatManYen } from '@/lib/japanese-format'

const STAGES = [
  { id: 'discovery', label: 'Discovery', color: 'bg-blue-100 border-blue-300' },
  { id: 'analysis', label: 'Analysis', color: 'bg-purple-100 border-purple-300' },
  { id: 'due_diligence', label: 'Due Diligence', color: 'bg-yellow-100 border-yellow-300' },
  { id: 'negotiation', label: 'Negotiation', color: 'bg-orange-100 border-orange-300' },
  { id: 'purchase', label: 'Purchase', color: 'bg-teal-100 border-teal-300' },
  { id: 'renovation', label: 'Renovation', color: 'bg-indigo-100 border-indigo-300' },
  { id: 'listing', label: 'Listing', color: 'bg-pink-100 border-pink-300' },
  { id: 'sale', label: 'Sale', color: 'bg-green-100 border-green-300' },
]

const TERMINAL_STAGES = [
  { id: 'completed', label: 'Completed', color: 'bg-emerald-100 border-emerald-300' },
  { id: 'abandoned', label: 'Abandoned', color: 'bg-gray-100 border-gray-300' },
]



const CHECKLIST_CATEGORIES = [
  { id: 'legal', label: 'Legal', icon: '\u2696' },
  { id: 'regulatory', label: 'Regulatory', icon: '\u2611' },
  { id: 'financial', label: 'Financial', icon: '\u00A5' },
  { id: 'physical', label: 'Physical', icon: '\u2692' },
]

function getStageLabelMap(): Record<string, string> {
  const map: Record<string, string> = {}
  for (const s of STAGES) map[s.id] = s.label
  for (const s of TERMINAL_STAGES) map[s.id] = s.label
  return map
}

const STAGE_LABEL_MAP = getStageLabelMap()

export default function Pipeline() {
  const queryClient = useQueryClient()
  const [selectedDealId, setSelectedDealId] = useState<string | null>(null)
  const [terminalExpanded, setTerminalExpanded] = useState(false)

  // --- Editable form state for the detail panel ---
  const [editPurchasePrice, setEditPurchasePrice] = useState('')
  const [editRenovationBudget, setEditRenovationBudget] = useState('')
  const [editTargetSalePrice, setEditTargetSalePrice] = useState('')
  const [editNotes, setEditNotes] = useState('')
  const [formDirty, setFormDirty] = useState(false)

  // --- Data queries ---
  const { data: deals, isLoading: dealsLoading } = useQuery({
    queryKey: ['pipeline', 'deals'],
    queryFn: () => api.get<Deal[]>('/pipeline/deals'),
  })

  const selectedDeal = useMemo(
    () => deals?.find((d) => d.id === selectedDealId) ?? null,
    [deals, selectedDealId],
  )

  const { data: checklist, isLoading: checklistLoading } = useQuery({
    queryKey: ['pipeline', 'checklist', selectedDealId],
    queryFn: () => api.get<DueDiligenceItem[]>(`/pipeline/deals/${selectedDealId}/checklist`),
    enabled: !!selectedDealId,
  })

  // --- Mutations ---
  const stageMutation = useMutation({
    mutationFn: ({ dealId, stage }: { dealId: string; stage: string }) =>
      api.patch<Deal>(`/pipeline/deals/${dealId}`, { stage }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline', 'deals'] })
    },
  })

  const updateDealMutation = useMutation({
    mutationFn: (payload: {
      dealId: string
      purchase_price?: number
      renovation_budget?: number
      target_sale_price?: number
      notes?: string
    }) => {
      const { dealId, ...body } = payload
      return api.patch<Deal>(`/pipeline/deals/${dealId}`, body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline', 'deals'] })
      setFormDirty(false)
    },
  })

  const toggleChecklistMutation = useMutation({
    mutationFn: ({ itemId, isCompleted, notes }: { itemId: string; isCompleted: boolean; notes?: string }) => {
      const params = new URLSearchParams()
      params.set('is_completed', String(isCompleted))
      if (notes !== undefined) params.set('notes', notes)
      return api.patch<{ status: string }>(`/pipeline/checklist/${itemId}?${params.toString()}`, {})
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline', 'checklist', selectedDealId] })
    },
  })

  // --- Derived data ---
  const dealsByStage = STAGES.map((stage) => ({
    ...stage,
    deals: deals?.filter((d) => d.stage === stage.id) || [],
  }))

  const terminalDeals = TERMINAL_STAGES.map((stage) => ({
    ...stage,
    deals: deals?.filter((d) => d.stage === stage.id) || [],
  }))

  const terminalCount = terminalDeals.reduce((sum, s) => sum + s.deals.length, 0)

  // --- Helpers ---
  function selectDeal(deal: Deal) {
    setSelectedDealId(deal.id)
    setEditPurchasePrice(deal.purchase_price?.toString() ?? '')
    setEditRenovationBudget(deal.renovation_budget?.toString() ?? '')
    setEditTargetSalePrice(deal.target_sale_price?.toString() ?? '')
    setEditNotes(deal.notes ?? '')
    setFormDirty(false)
  }

  function moveStage(deal: Deal, direction: 'forward' | 'backward') {
    const currentIdx = STAGES.findIndex((s) => s.id === deal.stage)
    if (currentIdx === -1) return // terminal stage, can't move
    const newIdx = direction === 'forward' ? currentIdx + 1 : currentIdx - 1
    if (newIdx < 0 || newIdx >= STAGES.length) return
    stageMutation.mutate({ dealId: deal.id, stage: STAGES[newIdx].id })
  }

  function moveTo(deal: Deal, stageId: string) {
    stageMutation.mutate({ dealId: deal.id, stage: stageId })
  }

  function handleSave() {
    if (!selectedDeal) return
    const payload: Record<string, unknown> = { dealId: selectedDeal.id }
    const pp = editPurchasePrice.trim()
    if (pp !== '') payload.purchase_price = parseInt(pp, 10)
    const rb = editRenovationBudget.trim()
    if (rb !== '') payload.renovation_budget = parseInt(rb, 10)
    const tsp = editTargetSalePrice.trim()
    if (tsp !== '') payload.target_sale_price = parseInt(tsp, 10)
    payload.notes = editNotes
    updateDealMutation.mutate(payload as any)
  }

  function handleFormChange(setter: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setter(e.target.value)
      setFormDirty(true)
    }
  }

  // --- Checklist grouped by category ---
  const checklistByCategory = useMemo(() => {
    if (!checklist) return {}
    const grouped: Record<string, DueDiligenceItem[]> = {}
    for (const item of checklist) {
      if (!grouped[item.category]) grouped[item.category] = []
      grouped[item.category].push(item)
    }
    return grouped
  }, [checklist])

  // --- Render ---
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Deal Pipeline</h2>
        <p className="text-muted-foreground">
          Track deals from discovery to sale
        </p>
      </div>

      {/* Kanban Board */}
      <div className="flex gap-4 overflow-x-auto pb-4">
        {dealsByStage.map((stage) => (
          <div
            key={stage.id}
            className={`flex-shrink-0 w-72 rounded-lg border ${stage.color} p-3`}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-sm">{stage.label}</h3>
              <span className="text-xs font-medium bg-white/60 px-2 py-0.5 rounded-full">
                {stage.deals.length}
              </span>
            </div>
            <div className="space-y-2 min-h-[100px]">
              {stage.deals.map((deal) => (
                <DealCard
                  key={deal.id}
                  deal={deal}
                  isSelected={deal.id === selectedDealId}
                  stageIndex={STAGES.findIndex((s) => s.id === deal.stage)}
                  totalStages={STAGES.length}
                  onSelect={() => selectDeal(deal)}
                  onMoveForward={() => moveStage(deal, 'forward')}
                  onMoveBackward={() => moveStage(deal, 'backward')}
                  isMoving={stageMutation.isPending}
                />
              ))}
              {stage.deals.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">
                  No deals
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Terminal Stages (Completed / Abandoned) */}
      {terminalCount > 0 && (
        <div className="rounded-lg border bg-card">
          <button
            onClick={() => setTerminalExpanded(!terminalExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50 transition-colors rounded-lg"
          >
            <span>
              Completed & Abandoned ({terminalCount})
            </span>
            <span className={`transition-transform ${terminalExpanded ? 'rotate-180' : ''}`}>
              &#9660;
            </span>
          </button>
          {terminalExpanded && (
            <div className="flex gap-4 overflow-x-auto px-4 pb-4">
              {terminalDeals.map((stage) => (
                <div
                  key={stage.id}
                  className={`flex-shrink-0 w-72 rounded-lg border ${stage.color} p-3`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-sm">{stage.label}</h3>
                    <span className="text-xs font-medium bg-white/60 px-2 py-0.5 rounded-full">
                      {stage.deals.length}
                    </span>
                  </div>
                  <div className="space-y-2 min-h-[60px]">
                    {stage.deals.map((deal) => (
                      <DealCard
                        key={deal.id}
                        deal={deal}
                        isSelected={deal.id === selectedDealId}
                        stageIndex={-1}
                        totalStages={STAGES.length}
                        onSelect={() => selectDeal(deal)}
                        isMoving={false}
                      />
                    ))}
                    {stage.deals.length === 0 && (
                      <p className="text-xs text-muted-foreground text-center py-4">
                        No deals
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Selected Deal Detail Panel */}
      {selectedDeal && (
        <div className="rounded-lg border bg-card p-6 space-y-6">
          {/* Panel header */}
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold">Deal Details</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Property: {selectedDeal.property_id.slice(0, 8)}...
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                getStageColor(selectedDeal.stage)
              }`}>
                {STAGE_LABEL_MAP[selectedDeal.stage] ?? selectedDeal.stage}
              </span>
              <button
                onClick={() => setSelectedDealId(null)}
                className="ml-2 text-muted-foreground hover:text-foreground text-lg leading-none"
                title="Close panel"
              >
                &#10005;
              </button>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {/* Left column: Deal info & editable fields */}
            <div className="space-y-4">
              <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Financial Details
              </h4>

              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">
                    Purchase Price (yen)
                  </label>
                  <input
                    type="number"
                    value={editPurchasePrice}
                    onChange={handleFormChange(setEditPurchasePrice)}
                    placeholder="e.g. 5000000"
                    className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                  {editPurchasePrice && !isNaN(parseInt(editPurchasePrice)) && (
                    <p className="text-xs text-muted-foreground mt-1">
                      = {formatManYen(parseInt(editPurchasePrice))}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm text-muted-foreground mb-1">
                    Renovation Budget (yen)
                  </label>
                  <input
                    type="number"
                    value={editRenovationBudget}
                    onChange={handleFormChange(setEditRenovationBudget)}
                    placeholder="e.g. 2000000"
                    className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                  {editRenovationBudget && !isNaN(parseInt(editRenovationBudget)) && (
                    <p className="text-xs text-muted-foreground mt-1">
                      = {formatManYen(parseInt(editRenovationBudget))}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm text-muted-foreground mb-1">
                    Target Sale Price (yen)
                  </label>
                  <input
                    type="number"
                    value={editTargetSalePrice}
                    onChange={handleFormChange(setEditTargetSalePrice)}
                    placeholder="e.g. 10000000"
                    className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                  {editTargetSalePrice && !isNaN(parseInt(editTargetSalePrice)) && (
                    <p className="text-xs text-muted-foreground mt-1">
                      = {formatManYen(parseInt(editTargetSalePrice))}
                    </p>
                  )}
                </div>

                {/* Profit summary */}
                {editPurchasePrice && editTargetSalePrice && (
                  <ProfitSummary
                    purchase={parseInt(editPurchasePrice) || 0}
                    renovation={parseInt(editRenovationBudget) || 0}
                    target={parseInt(editTargetSalePrice) || 0}
                  />
                )}
              </div>

              <div>
                <label className="block text-sm text-muted-foreground mb-1">
                  Notes
                </label>
                <textarea
                  value={editNotes}
                  onChange={handleFormChange(setEditNotes)}
                  rows={4}
                  placeholder="Deal notes..."
                  className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 resize-y"
                />
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleSave}
                  disabled={!formDirty || updateDealMutation.isPending}
                  className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {updateDealMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
                {updateDealMutation.isSuccess && !formDirty && (
                  <span className="text-xs text-green-600">Saved</span>
                )}
              </div>

              {/* Stage actions */}
              <div className="pt-3 border-t">
                <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Move to Stage
                </h4>
                <div className="flex flex-wrap gap-1">
                  {STAGES.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => moveTo(selectedDeal, s.id)}
                      disabled={selectedDeal.stage === s.id || stageMutation.isPending}
                      className={`px-2 py-1 text-xs rounded border transition-colors ${
                        selectedDeal.stage === s.id
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'hover:bg-muted border-border'
                      } disabled:opacity-50`}
                    >
                      {s.label}
                    </button>
                  ))}
                  <span className="w-px bg-border mx-1" />
                  {TERMINAL_STAGES.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => moveTo(selectedDeal, s.id)}
                      disabled={selectedDeal.stage === s.id || stageMutation.isPending}
                      className={`px-2 py-1 text-xs rounded border transition-colors ${
                        selectedDeal.stage === s.id
                          ? 'bg-primary text-primary-foreground border-primary'
                          : s.id === 'abandoned'
                            ? 'hover:bg-red-50 text-red-600 border-red-200'
                            : 'hover:bg-emerald-50 text-emerald-600 border-emerald-200'
                      } disabled:opacity-50`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Meta info */}
              <div className="pt-3 border-t space-y-1">
                <p className="text-xs text-muted-foreground">
                  Deal ID: {selectedDeal.id.slice(0, 8)}...
                </p>
                <p className="text-xs text-muted-foreground">
                  Property ID: {selectedDeal.property_id}
                </p>
                {selectedDeal.created_at && (
                  <p className="text-xs text-muted-foreground">
                    Created: {new Date(selectedDeal.created_at).toLocaleDateString()}
                  </p>
                )}
                {selectedDeal.updated_at && (
                  <p className="text-xs text-muted-foreground">
                    Updated: {new Date(selectedDeal.updated_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>

            {/* Right column: Due diligence checklist */}
            <div className="space-y-4">
              <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Due Diligence Checklist
              </h4>

              {checklistLoading && (
                <p className="text-sm text-muted-foreground">Loading checklist...</p>
              )}

              {checklist && checklist.length === 0 && (
                <p className="text-sm text-muted-foreground">No checklist items.</p>
              )}

              {checklist && checklist.length > 0 && (
                <div className="space-y-4">
                  {/* Progress bar */}
                  <div>
                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                      <span>Progress</span>
                      <span>
                        {checklist.filter((i) => i.is_completed).length} / {checklist.length}
                      </span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all"
                        style={{
                          width: `${(checklist.filter((i) => i.is_completed).length / checklist.length) * 100}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Categories */}
                  {CHECKLIST_CATEGORIES.map((cat) => {
                    const items = checklistByCategory[cat.id]
                    if (!items || items.length === 0) return null
                    const completedCount = items.filter((i) => i.is_completed).length
                    return (
                      <div key={cat.id} className="rounded-md border p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-sm">{cat.icon}</span>
                          <h5 className="text-sm font-medium capitalize">{cat.label}</h5>
                          <span className="text-xs text-muted-foreground ml-auto">
                            {completedCount}/{items.length}
                          </span>
                        </div>
                        <div className="space-y-2">
                          {items.map((item) => (
                            <ChecklistItem
                              key={item.id}
                              item={item}
                              onToggle={() =>
                                toggleChecklistMutation.mutate({
                                  itemId: item.id,
                                  isCompleted: !item.is_completed,
                                })
                              }
                              isToggling={toggleChecklistMutation.isPending}
                            />
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Loading state */}
      {dealsLoading && (
        <div className="text-center text-muted-foreground py-8">
          Loading deals...
        </div>
      )}
    </div>
  )
}

// --- Sub-components (inline, no separate files) ---

function DealCard({
  deal,
  isSelected,
  stageIndex,
  totalStages,
  onSelect,
  onMoveForward,
  onMoveBackward,
  isMoving,
}: {
  deal: Deal
  isSelected: boolean
  stageIndex: number
  totalStages: number
  onSelect: () => void
  onMoveForward?: () => void
  onMoveBackward?: () => void
  isMoving: boolean
}) {
  const canMoveBack = stageIndex > 0
  const canMoveForward = stageIndex >= 0 && stageIndex < totalStages - 1

  return (
    <div
      className={`p-3 bg-white rounded-md shadow-sm border cursor-pointer hover:shadow-md transition-shadow ${
        isSelected ? 'ring-2 ring-primary border-primary' : ''
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-1">
        <p className="text-xs text-muted-foreground truncate font-mono">
          {deal.property_id.slice(0, 8)}...
        </p>
        {/* Stage transition arrows */}
        {(canMoveBack || canMoveForward) && (
          <div className="flex gap-0.5 flex-shrink-0">
            {canMoveBack && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onMoveBackward?.()
                }}
                disabled={isMoving}
                className="w-5 h-5 flex items-center justify-center rounded text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50 transition-colors"
                title="Move to previous stage"
              >
                &#9664;
              </button>
            )}
            {canMoveForward && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onMoveForward?.()
                }}
                disabled={isMoving}
                className="w-5 h-5 flex items-center justify-center rounded text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50 transition-colors"
                title="Move to next stage"
              >
                &#9654;
              </button>
            )}
          </div>
        )}
      </div>
      {deal.purchase_price != null && (
        <p className="font-bold text-sm mt-1">
          {formatManYen(deal.purchase_price)}
        </p>
      )}
      {deal.notes && (
        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
          {deal.notes}
        </p>
      )}
    </div>
  )
}

function ChecklistItem({
  item,
  onToggle,
  isToggling,
}: {
  item: DueDiligenceItem
  onToggle: () => void
  isToggling: boolean
}) {
  return (
    <label className="flex items-start gap-2 cursor-pointer group">
      <input
        type="checkbox"
        checked={item.is_completed}
        onChange={onToggle}
        disabled={isToggling}
        className="mt-0.5 rounded border-gray-300 text-primary focus:ring-primary/50 disabled:opacity-50"
      />
      <div className="flex-1 min-w-0">
        <p className={`text-sm ${item.is_completed ? 'line-through text-muted-foreground' : ''}`}>
          {item.item_name.replace(/_/g, ' ')}
        </p>
        {item.description && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {item.description}
          </p>
        )}
        {item.completed_at && (
          <p className="text-xs text-green-600 mt-0.5">
            Completed {new Date(item.completed_at).toLocaleDateString()}
          </p>
        )}
      </div>
    </label>
  )
}

function ProfitSummary({
  purchase,
  renovation,
  target,
}: {
  purchase: number
  renovation: number
  target: number
}) {
  const totalCost = purchase + renovation
  const profit = target - totalCost
  const margin = totalCost > 0 ? (profit / totalCost) * 100 : 0

  return (
    <div className="rounded-md border p-3 bg-muted/30 space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">Total Cost</span>
        <span className="font-medium">{formatManYen(totalCost)}</span>
      </div>
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">Gross Profit</span>
        <span className={`font-medium ${profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {profit >= 0 ? '+' : ''}{formatManYen(profit)}
        </span>
      </div>
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">Margin</span>
        <span className={`font-medium ${margin >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {margin.toFixed(1)}%
        </span>
      </div>
    </div>
  )
}

function getStageColor(stageId: string): string {
  const stage = STAGES.find((s) => s.id === stageId) ?? TERMINAL_STAGES.find((s) => s.id === stageId)
  if (!stage) return 'bg-gray-100 text-gray-800'
  // Convert bg-blue-100 border-blue-300 -> bg-blue-100 text-blue-800
  const match = stage.color.match(/bg-(\w+)-100/)
  if (match) return `bg-${match[1]}-100 text-${match[1]}-800`
  return 'bg-gray-100 text-gray-800'
}
