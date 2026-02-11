/**
 * Japanese-specific formatting utilities.
 */

/** Format yen amount with comma separators */
export function formatYen(amount: number): string {
  return `¥${amount.toLocaleString('ja-JP')}`
}

/** Format amount in 万円 (10,000 yen units) */
export function formatManYen(amount: number): string {
  const man = amount / 10000
  if (Number.isInteger(man)) {
    return `${man}万円`
  }
  return `${man.toFixed(1)}万円`
}

/** Convert square meters to tsubo */
export function sqmToTsubo(sqm: number): number {
  return Math.round((sqm / 3.30579) * 100) / 100
}

/** Format area with both sqm and tsubo */
export function formatArea(sqm: number): string {
  return `${sqm.toFixed(1)}m² (${sqmToTsubo(sqm).toFixed(1)}坪)`
}

/** Format composite score with color class */
export function getScoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground'
  if (score >= 70) return 'text-green-600'
  if (score >= 40) return 'text-yellow-600'
  return 'text-red-600'
}

/** Format score badge background */
export function getScoreBgColor(score: number | null): string {
  if (score === null) return 'bg-muted'
  if (score >= 70) return 'bg-green-100 text-green-800'
  if (score >= 40) return 'bg-yellow-100 text-yellow-800'
  return 'bg-red-100 text-red-800'
}
