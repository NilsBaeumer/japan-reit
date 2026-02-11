import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { HazardLayer } from '@/api/types'
import type maplibregl from 'maplibre-gl'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HazardOverlayControlsProps {
  map: maplibregl.Map | null
}

interface LayersResponse {
  layers: HazardLayer[]
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getSourceId(layerId: string): string {
  return `hazard-source-${layerId}`
}

function getLayerId(layerId: string): string {
  return `hazard-layer-${layerId}`
}

function addHazardLayer(map: maplibregl.Map, layerId: string) {
  const sourceId = getSourceId(layerId)
  const mapLayerId = getLayerId(layerId)

  // Skip if already added
  if (map.getSource(sourceId)) return

  map.addSource(sourceId, {
    type: 'raster',
    tiles: [`/api/v1/hazards/tiles/${layerId}/{z}/{x}/{y}.png`],
    tileSize: 256,
  })

  map.addLayer({
    id: mapLayerId,
    type: 'raster',
    source: sourceId,
    paint: {
      'raster-opacity': 0.6,
    },
  })
}

function removeHazardLayer(map: maplibregl.Map, layerId: string) {
  const sourceId = getSourceId(layerId)
  const mapLayerId = getLayerId(layerId)

  if (map.getLayer(mapLayerId)) {
    map.removeLayer(mapLayerId)
  }
  if (map.getSource(sourceId)) {
    map.removeSource(sourceId)
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function HazardOverlayControls({ map }: HazardOverlayControlsProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeLayers, setActiveLayers] = useState<Set<string>>(new Set())

  const { data, isLoading } = useQuery({
    queryKey: ['hazard-layers'],
    queryFn: () => api.get<LayersResponse>('/hazards/layers'),
  })

  const layers = data?.layers ?? []

  // Clean up layers when map changes or component unmounts
  useEffect(() => {
    return () => {
      if (!map) return
      activeLayers.forEach((layerId) => {
        removeHazardLayer(map, layerId)
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map])

  function handleToggle(layerId: string) {
    if (!map) return

    const newActive = new Set(activeLayers)

    if (newActive.has(layerId)) {
      newActive.delete(layerId)
      removeHazardLayer(map, layerId)
    } else {
      newActive.add(layerId)
      addHazardLayer(map, layerId)
    }

    setActiveLayers(newActive)
  }

  return (
    <div className="absolute top-14 right-2 z-10">
      {/* Toggle button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        title="Hazard map overlays"
        className="flex items-center gap-1.5 rounded-md bg-card/95 px-3 py-2 text-xs font-medium shadow-md border hover:bg-accent transition-colors backdrop-blur-sm"
      >
        <HazardIcon />
        Hazard Layers
        <ChevronIcon isOpen={isOpen} />
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div className="mt-1 rounded-lg border bg-card/95 shadow-lg backdrop-blur-sm p-3 min-w-[220px]">
          {isLoading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
              <Spinner />
              Loading layers...
            </div>
          ) : layers.length === 0 ? (
            <p className="text-xs text-muted-foreground py-2">No hazard layers available.</p>
          ) : (
            <div className="space-y-1">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">
                Overlay Layers
              </p>
              {layers.map((layer) => {
                const isActive = activeLayers.has(layer.id)
                return (
                  <button
                    key={layer.id}
                    onClick={() => handleToggle(layer.id)}
                    className={`flex items-center gap-2 w-full rounded-md px-2.5 py-2 text-left text-xs transition-colors ${
                      isActive
                        ? 'bg-primary/10 text-primary border border-primary/30'
                        : 'hover:bg-muted border border-transparent'
                    }`}
                  >
                    <span
                      className={`flex h-4 w-4 items-center justify-center rounded border text-[10px] ${
                        isActive
                          ? 'bg-primary border-primary text-primary-foreground'
                          : 'border-muted-foreground/30'
                      }`}
                    >
                      {isActive && <CheckIcon />}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{layer.name}</div>
                      <div className="text-[10px] text-muted-foreground truncate">
                        {layer.name_ja}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tiny inline SVG icons
// ---------------------------------------------------------------------------

function HazardIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}

function ChevronIcon({ isOpen }: { isOpen: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="10"
      height="10"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function Spinner() {
  return (
    <svg
      className="h-3 w-3 animate-spin text-primary"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
