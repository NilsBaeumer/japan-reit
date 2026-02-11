import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { PurchaseCosts } from '@/api/types'
import { formatYen } from '@/lib/japanese-format'

export default function FinancialCalc() {
  const [purchasePrice, setPurchasePrice] = useState(1500000)
  const [assessedValue, setAssessedValue] = useState<number | null>(null)
  const [renovationBudget, setRenovationBudget] = useState(500000)
  const [targetSalePrice, setTargetSalePrice] = useState(3000000)
  const [holdingMonths, setHoldingMonths] = useState(12)

  const purchaseMutation = useMutation({
    mutationFn: (data: { purchase_price: number; assessed_value?: number }) =>
      api.post<PurchaseCosts>('/financial/purchase-costs', data),
  })

  const roiMutation = useMutation({
    mutationFn: (data: any) => api.post<any>('/financial/roi-projection', data),
  })

  const calculate = () => {
    purchaseMutation.mutate({
      purchase_price: purchasePrice,
      ...(assessedValue && { assessed_value: assessedValue }),
    })
    roiMutation.mutate({
      purchase_price: purchasePrice,
      ...(assessedValue && { assessed_value: assessedValue }),
      renovation_budget: renovationBudget,
      target_sale_price: targetSalePrice,
      holding_months: holdingMonths,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Financial Calculator</h2>
        <p className="text-muted-foreground">
          Calculate transaction costs, ROI, and tax implications for Japanese real estate deals
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input */}
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <h3 className="text-lg font-semibold">Deal Parameters</h3>

          <div>
            <label className="text-sm font-medium">Purchase Price (¥)</label>
            <input
              type="number"
              value={purchasePrice}
              onChange={(e) => setPurchasePrice(Number(e.target.value))}
              className="mt-1 w-full px-3 py-2 border rounded-md bg-background text-sm"
              step={100000}
            />
            <p className="text-xs text-muted-foreground mt-1">{formatYen(purchasePrice)}</p>
          </div>

          <div>
            <label className="text-sm font-medium">Assessed Value (¥, optional)</label>
            <input
              type="number"
              value={assessedValue || ''}
              onChange={(e) => setAssessedValue(e.target.value ? Number(e.target.value) : null)}
              placeholder="Default: 70% of purchase price"
              className="mt-1 w-full px-3 py-2 border rounded-md bg-background text-sm"
              step={100000}
            />
          </div>

          <div>
            <label className="text-sm font-medium">Renovation Budget (¥)</label>
            <input
              type="number"
              value={renovationBudget}
              onChange={(e) => setRenovationBudget(Number(e.target.value))}
              className="mt-1 w-full px-3 py-2 border rounded-md bg-background text-sm"
              step={100000}
            />
          </div>

          <div>
            <label className="text-sm font-medium">Target Sale Price (¥)</label>
            <input
              type="number"
              value={targetSalePrice}
              onChange={(e) => setTargetSalePrice(Number(e.target.value))}
              className="mt-1 w-full px-3 py-2 border rounded-md bg-background text-sm"
              step={100000}
            />
          </div>

          <div>
            <label className="text-sm font-medium">Holding Period (months)</label>
            <input
              type="number"
              value={holdingMonths}
              onChange={(e) => setHoldingMonths(Number(e.target.value))}
              className="mt-1 w-full px-3 py-2 border rounded-md bg-background text-sm"
              min={1}
              max={120}
            />
            <p className="text-xs text-muted-foreground mt-1">
              {holdingMonths <= 60 ? 'Short-term (39.63% capital gains tax)' : 'Long-term (20.315% capital gains tax)'}
            </p>
          </div>

          <button
            onClick={calculate}
            className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 font-medium"
          >
            Calculate
          </button>
        </div>

        {/* Results */}
        <div className="space-y-4">
          {/* Purchase Costs */}
          {purchaseMutation.data && (
            <div className="rounded-lg border bg-card p-6">
              <h3 className="text-lg font-semibold mb-4">Purchase Costs</h3>
              <dl className="space-y-2">
                <CostRow label="Purchase Price" value={purchaseMutation.data.purchase_price} />
                <CostRow
                  label="Broker Commission"
                  value={purchaseMutation.data.broker_commission.actual_commission_incl_tax}
                  note={purchaseMutation.data.broker_commission.note}
                  highlight={purchaseMutation.data.broker_commission.low_price_rule_applies}
                />
                <CostRow label="Stamp Tax" value={purchaseMutation.data.stamp_tax} />
                <CostRow label="Registration Tax" value={purchaseMutation.data.registration_tax.total} />
                <CostRow label="Acquisition Tax" value={purchaseMutation.data.acquisition_tax.total} />
                <CostRow label="Judicial Scrivener" value={purchaseMutation.data.judicial_scrivener_fee} />
                <div className="border-t pt-2 mt-2">
                  <CostRow label="Total Costs" value={purchaseMutation.data.total_purchase_costs} bold />
                  <CostRow label="Total with Price" value={purchaseMutation.data.total_with_price} bold />
                  <p className="text-xs text-muted-foreground mt-1">
                    Cost ratio: {purchaseMutation.data.cost_ratio}% of purchase price
                  </p>
                </div>
              </dl>
            </div>
          )}

          {/* ROI Projection */}
          {roiMutation.data && (
            <div className="rounded-lg border bg-card p-6">
              <h3 className="text-lg font-semibold mb-4">ROI Projection</h3>
              <dl className="space-y-2">
                <CostRow label="Total Invested" value={roiMutation.data.investment_summary.total_invested} />
                <CostRow label="Net Proceeds" value={roiMutation.data.sale_summary.net_proceeds} />
                <div className="border-t pt-2 mt-2">
                  <CostRow
                    label="Net Profit"
                    value={roiMutation.data.returns.net_profit}
                    bold
                    highlight={roiMutation.data.returns.net_profit > 0}
                  />
                  <div className="flex justify-between items-center mt-1">
                    <span className="text-sm font-bold">ROI</span>
                    <span className={`text-lg font-bold ${
                      roiMutation.data.returns.roi_percent > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {roiMutation.data.returns.roi_percent}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <span className="text-sm text-muted-foreground">Annualized ROI</span>
                    <span className="text-sm font-medium">
                      {roiMutation.data.returns.annualized_roi_percent}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <span className="text-sm text-muted-foreground">Break-even Sale Price</span>
                    <span className="text-sm font-medium">
                      {formatYen(roiMutation.data.returns.breakeven_sale_price)}
                    </span>
                  </div>
                </div>
              </dl>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function CostRow({
  label,
  value,
  note,
  bold,
  highlight,
}: {
  label: string
  value: number
  note?: string
  bold?: boolean
  highlight?: boolean
}) {
  return (
    <div>
      <div className="flex justify-between items-center">
        <span className={`text-sm ${bold ? 'font-bold' : 'text-muted-foreground'}`}>{label}</span>
        <span className={`text-sm font-mono ${bold ? 'font-bold' : ''} ${
          highlight === true ? 'text-green-600' : highlight === false ? 'text-red-600' : ''
        }`}>
          {formatYen(value)}
        </span>
      </div>
      {note && (
        <p className="text-xs text-yellow-600 mt-0.5">{note}</p>
      )}
    </div>
  )
}
