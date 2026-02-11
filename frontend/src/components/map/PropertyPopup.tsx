/**
 * Creates HTML content for MapLibre popups.
 *
 * MapLibre GL JS popups accept raw HTML strings, so this module provides
 * a helper that builds the popup markup for a single property feature.
 */

interface PopupProperties {
  id: string
  price: number | null
  address: string
  score: number | null
  floor_plan: string | null
  land_area: number | null
  year_built: number | null
  rebuild_possible: boolean | null
}

/** Format a price in man-yen (10 000 yen units). */
function formatPrice(price: number | null): string {
  if (price === null) return '-'
  const man = price / 10000
  return Number.isInteger(man) ? `${man.toLocaleString()}万円` : `${man.toLocaleString(undefined, { maximumFractionDigits: 1 })}万円`
}

/** Return a coloured HTML badge for the composite score. */
function scoreBadge(score: number | null): string {
  if (score === null) {
    return '<span style="display:inline-block;padding:2px 8px;border-radius:9999px;font-size:11px;background:#e5e7eb;color:#6b7280;">N/A</span>'
  }
  let bg: string
  let fg: string
  if (score >= 70) {
    bg = '#dcfce7'; fg = '#166534'
  } else if (score >= 40) {
    bg = '#fef9c3'; fg = '#854d0e'
  } else {
    bg = '#fee2e2'; fg = '#991b1b'
  }
  return `<span style="display:inline-block;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600;background:${bg};color:${fg};">${score}</span>`
}

/** Return rebuild status label. */
function rebuildLabel(rebuild: boolean | null): string {
  if (rebuild === null) return '<span style="color:#6b7280;">?</span>'
  if (rebuild) return '<span style="color:#16a34a;font-weight:600;">OK</span>'
  return '<span style="color:#dc2626;font-weight:600;">NG</span>'
}

/**
 * Build the popup HTML string for a property feature.
 *
 * The returned markup is self-contained and does not depend on any external
 * stylesheet beyond basic browser defaults.
 */
export function createPopupHTML(properties: PopupProperties): string {
  const rows: string[] = []

  rows.push(`<div style="font-family:system-ui,-apple-system,sans-serif;min-width:220px;max-width:300px;font-size:13px;line-height:1.5;">`)

  // Address
  rows.push(`<div style="font-weight:700;font-size:14px;margin-bottom:6px;color:#111827;">${escapeHtml(properties.address)}</div>`)

  // Price + Score row
  rows.push(`<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">`)
  rows.push(`<span style="font-size:15px;font-weight:700;color:#7c3aed;">${formatPrice(properties.price)}</span>`)
  rows.push(scoreBadge(properties.score))
  rows.push(`</div>`)

  // Details table
  rows.push(`<table style="width:100%;border-collapse:collapse;margin-bottom:8px;">`)

  if (properties.floor_plan) {
    rows.push(tableRow('Floor Plan', escapeHtml(properties.floor_plan)))
  }
  if (properties.land_area !== null) {
    rows.push(tableRow('Land Area', `${properties.land_area.toFixed(1)}m&sup2;`))
  }
  if (properties.year_built !== null) {
    rows.push(tableRow('Year Built', String(properties.year_built)))
  }
  rows.push(tableRow('Rebuild', rebuildLabel(properties.rebuild_possible)))

  rows.push(`</table>`)

  // Link to detail page
  rows.push(`<a href="/property/${encodeURIComponent(properties.id)}" style="display:inline-block;margin-top:4px;font-size:12px;color:#2563eb;text-decoration:none;font-weight:500;">View details &rarr;</a>`)

  rows.push(`</div>`)

  return rows.join('')
}

function tableRow(label: string, value: string): string {
  return `<tr>
    <td style="padding:2px 8px 2px 0;color:#6b7280;white-space:nowrap;">${label}</td>
    <td style="padding:2px 0;font-weight:500;color:#111827;">${value}</td>
  </tr>`
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}
