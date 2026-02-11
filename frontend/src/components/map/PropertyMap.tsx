import { useRef, useEffect, useCallback, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { GeoJSONFeatureCollection } from '@/api/types'
import { createPopupHTML } from './PropertyPopup'
import HazardOverlayControls from './HazardOverlayControls'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PropertyMapProps {
  geojson: GeoJSONFeatureCollection | null
  isLoading?: boolean
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const JAPAN_CENTER: [number, number] = [138, 36.5] // [lng, lat]
const DEFAULT_ZOOM = 5

const SOURCE_ID = 'properties'
const CLUSTER_LAYER = 'clusters'
const CLUSTER_COUNT_LAYER = 'cluster-count'
const UNCLUSTERED_LAYER = 'unclustered-point'

const EMPTY_FC: GeoJSONFeatureCollection = {
  type: 'FeatureCollection',
  features: [],
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PropertyMap({ geojson, isLoading }: PropertyMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null)

  // ---- Initialise MapLibre map ----
  useEffect(() => {
    if (!containerRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          },
        },
        layers: [
          {
            id: 'osm-tiles',
            type: 'raster',
            source: 'osm',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: JAPAN_CENTER,
      zoom: DEFAULT_ZOOM,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    map.on('load', () => {
      addSourceAndLayers(map)
      attachInteractions(map)
      setMapInstance(map)
    })

    mapRef.current = map

    // Handle window resize
    const handleResize = () => map.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      popupRef.current?.remove()
      setMapInstance(null)
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---- Update data when geojson prop changes ----
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const update = () => {
      const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined
      if (source) {
        source.setData((geojson ?? EMPTY_FC) as unknown as GeoJSON.FeatureCollection)
      }
    }

    if (map.isStyleLoaded()) {
      update()
    } else {
      map.once('load', update)
    }
  }, [geojson])

  // ---- Fit to data ----
  const fitToData = useCallback(() => {
    const map = mapRef.current
    if (!map || !geojson || geojson.features.length === 0) return

    const bounds = new maplibregl.LngLatBounds()
    for (const feature of geojson.features) {
      const [lng, lat] = feature.geometry.coordinates
      bounds.extend([lng, lat])
    }

    map.fitBounds(bounds, { padding: 60, maxZoom: 14 })
  }, [geojson])

  // ---- Render ----
  return (
    <div className="relative h-full w-full">
      {/* Map container */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/60 backdrop-blur-sm">
          <div className="flex items-center gap-2 rounded-lg bg-card px-4 py-3 shadow-md border">
            <Spinner />
            <span className="text-sm text-muted-foreground">Loading properties...</span>
          </div>
        </div>
      )}

      {/* Fit-to-data button */}
      {geojson && geojson.features.length > 0 && (
        <button
          onClick={fitToData}
          title="Fit map to show all properties"
          className="absolute bottom-4 left-4 z-10 flex items-center gap-1.5 rounded-md bg-card px-3 py-2 text-xs font-medium shadow-md border hover:bg-accent transition-colors"
        >
          <FitIcon />
          Fit to data
        </button>
      )}

      {/* Feature count badge */}
      {geojson && (
        <div className="absolute top-2 left-2 z-10 rounded-md bg-card/90 px-2.5 py-1 text-xs font-medium shadow border">
          {geojson.features.length} {geojson.features.length === 1 ? 'property' : 'properties'}
        </div>
      )}

      {/* Hazard overlay controls */}
      <HazardOverlayControls map={mapInstance} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Map setup helpers (called once on load)
// ---------------------------------------------------------------------------

function addSourceAndLayers(map: maplibregl.Map) {
  // Clustered GeoJSON source
  map.addSource(SOURCE_ID, {
    type: 'geojson',
    data: EMPTY_FC as unknown as GeoJSON.FeatureCollection,
    cluster: true,
    clusterMaxZoom: 14,
    clusterRadius: 50,
  })

  // ---- Cluster circles ----
  map.addLayer({
    id: CLUSTER_LAYER,
    type: 'circle',
    source: SOURCE_ID,
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': [
        'step',
        ['get', 'point_count'],
        '#7c3aed', // violet-600 for small clusters
        10,
        '#6d28d9', // violet-700
        50,
        '#5b21b6', // violet-800
        200,
        '#4c1d95', // violet-900
      ],
      'circle-radius': [
        'step',
        ['get', 'point_count'],
        18,  // base radius
        10,
        22,
        50,
        28,
        200,
        34,
      ],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
    },
  })

  // ---- Cluster count labels ----
  map.addLayer({
    id: CLUSTER_COUNT_LAYER,
    type: 'symbol',
    source: SOURCE_ID,
    filter: ['has', 'point_count'],
    layout: {
      'text-field': '{point_count_abbreviated}',
      'text-size': 13,
      'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
    },
    paint: {
      'text-color': '#ffffff',
    },
  })

  // ---- Individual (unclustered) points ----
  map.addLayer({
    id: UNCLUSTERED_LAYER,
    type: 'circle',
    source: SOURCE_ID,
    filter: ['!', ['has', 'point_count']],
    paint: {
      // Color based on rebuild_possible: green = true, red = false, gray = null
      'circle-color': [
        'case',
        ['==', ['get', 'rebuild_possible'], true],
        '#16a34a', // green-600
        ['==', ['get', 'rebuild_possible'], false],
        '#dc2626', // red-600
        '#9ca3af', // gray-400 (null / unknown)
      ],
      'circle-radius': [
        'interpolate',
        ['linear'],
        ['zoom'],
        5, 5,
        10, 7,
        15, 10,
      ],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
    },
  })
}

function attachInteractions(map: maplibregl.Map) {
  // ---- Cluster click: zoom into cluster ----
  map.on('click', CLUSTER_LAYER, (e) => {
    const features = map.queryRenderedFeatures(e.point, { layers: [CLUSTER_LAYER] })
    if (!features.length) return
    const feature = features[0]
    const clusterId = feature.properties?.cluster_id as number | undefined
    if (clusterId === undefined) return

    const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource
    source.getClusterExpansionZoom(clusterId).then((zoom) => {
      const geometry = feature.geometry as GeoJSON.Point
      map.easeTo({
        center: geometry.coordinates as [number, number],
        zoom: zoom,
      })
    })
  })

  // ---- Unclustered point click: show popup ----
  map.on('click', UNCLUSTERED_LAYER, (e) => {
    const features = map.queryRenderedFeatures(e.point, { layers: [UNCLUSTERED_LAYER] })
    if (!features.length) return
    const feature = features[0]
    const geometry = feature.geometry as GeoJSON.Point
    const coords = geometry.coordinates.slice() as [number, number]
    const props = feature.properties as Record<string, unknown>

    // MapLibre stringifies nested properties, so we parse carefully
    const popupProps = {
      id: String(props.id ?? ''),
      price: props.price === null || props.price === undefined ? null : Number(props.price),
      address: String(props.address ?? ''),
      score: props.score === null || props.score === undefined ? null : Number(props.score),
      floor_plan: props.floor_plan === null || props.floor_plan === undefined || props.floor_plan === 'null' ? null : String(props.floor_plan),
      land_area: props.land_area === null || props.land_area === undefined ? null : Number(props.land_area),
      year_built: props.year_built === null || props.year_built === undefined ? null : Number(props.year_built),
      rebuild_possible:
        props.rebuild_possible === true || props.rebuild_possible === 'true' ? true :
        props.rebuild_possible === false || props.rebuild_possible === 'false' ? false :
        null,
    }

    // Ensure the popup appears above the point if the map is wrapped
    while (Math.abs(e.lngLat.lng - coords[0]) > 180) {
      coords[0] += e.lngLat.lng > coords[0] ? 360 : -360
    }

    new maplibregl.Popup({ closeButton: true, maxWidth: '320px' })
      .setLngLat(coords)
      .setHTML(createPopupHTML(popupProps))
      .addTo(map)
  })

  // ---- Cursor changes ----
  for (const layer of [CLUSTER_LAYER, UNCLUSTERED_LAYER]) {
    map.on('mouseenter', layer, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', layer, () => {
      map.getCanvas().style.cursor = ''
    })
  }
}

// ---------------------------------------------------------------------------
// Tiny inline SVG icons (avoids extra imports)
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-primary"
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

function FitIcon() {
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
      <path d="M15 3h6v6" />
      <path d="M9 21H3v-6" />
      <path d="M21 3l-7 7" />
      <path d="M3 21l7-7" />
    </svg>
  )
}
