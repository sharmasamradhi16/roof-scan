import { useEffect, useRef, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import axios from 'axios'
import { API_URL } from '../lib/api'
import 'maplibre-gl/dist/maplibre-gl.css'
import './PolygonEditor.css'

export default function PolygonEditor({ roofResult, onDone, onCancel }) {
  const mapContainer = useRef(null)
  const mapRef       = useRef(null)
  const markersRef   = useRef([])
  const drawMkrsRef  = useRef([])

  const [polygon,     setPolygon]     = useState(roofResult.polygon || [])
  const [mode,        setMode]        = useState('adjust')
  const [drawing,     setDrawing]     = useState([])
  const [area,        setArea]        = useState(roofResult.area_m2)
  const [areaFt,      setAreaFt]      = useState(roofResult.area_ft2)
  const [loading,     setLoading]     = useState(false)
  const [snapLoading, setSnapLoading] = useState(false)
  const [status,      setStatus]      = useState('')

  const ref_lat = roofResult.lat
  const ref_lon = roofResult.lon

  // ── Build GeoJSON ──────────────────────────────────────
  function buildPolygonGeoJSON(pts) {
    if (!pts || pts.length < 3) {
      return { type: 'FeatureCollection', features: [] }
    }
    return {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [[
            ...pts.map(p => [p[1], p[0]]),
            [pts[0][1], pts[0][0]],
          ]],
        },
      }],
    }
  }

  function updateMapPolygon(pts) {
    if (!mapRef.current) return
    const src = mapRef.current.getSource('edit-polygon')
    if (src) src.setData(buildPolygonGeoJSON(pts))
  }

  // ── Update the green SAM overlay to match edited polygon ──
  // Redraws overlay as a filled polygon directly on the map
  function updateOverlayPolygon(pts) {
    if (!mapRef.current || !pts || pts.length < 3) return
    const map = mapRef.current

    const geojson = {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [[
            ...pts.map(p => [p[1], p[0]]),
            [pts[0][1], pts[0][0]],
          ]],
        },
      }],
    }

    if (map.getSource('overlay-polygon')) {
      map.getSource('overlay-polygon').setData(geojson)
    } else {
      map.addSource('overlay-polygon', { type: 'geojson', data: geojson })
      map.addLayer({
        id:   'overlay-fill',
        type: 'fill',
        source: 'overlay-polygon',
        paint: { 'fill-color': '#00ff00', 'fill-opacity': 0.35 },
      })
      map.addLayer({
        id:   'overlay-line',
        type: 'line',
        source: 'overlay-polygon',
        paint: { 'line-color': '#006400', 'line-width': 2 },
      })
    }
  }

  // ── Init map ───────────────────────────────────────────
  useEffect(() => {
    if (mapRef.current) return

    const center = polygon.length > 0
      ? [
          polygon.reduce((s, p) => s + p[1], 0) / polygon.length,
          polygon.reduce((s, p) => s + p[0], 0) / polygon.length,
        ]
      : [ref_lon, ref_lat]

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          satellite: {
            type: 'raster',
            tiles: ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'],
            tileSize: 256, attribution: '© Google',
            // Cap at the tile source's real max zoom so MapLibre over-scales
            // the last tile instead of requesting nonexistent z21+ tiles
            // (which render as blank/white). See MapPicker.jsx for detail.
            maxzoom: 20,
          },
        },
        layers: [{
          id: 'satellite', type: 'raster', source: 'satellite',
          minzoom: 0, maxzoom: 24,
        }],
      },
      center, zoom: 19, pitch: 0, bearing: 0,
      maxZoom: 22,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    map.on('load', () => {
      // Editable polygon outline
      map.addSource('edit-polygon', {
        type: 'geojson',
        data: buildPolygonGeoJSON(polygon),
      })
      map.addLayer({
        id: 'edit-fill', type: 'fill', source: 'edit-polygon',
        paint: { 'fill-color': '#c2410c', 'fill-opacity': 0.15 },
      })
      map.addLayer({
        id: 'edit-outline', type: 'line', source: 'edit-polygon',
        paint: { 'line-color': '#c2410c', 'line-width': 2, 'line-dasharray': [3, 1] },
      })

      mapRef.current = map

      // Show initial green overlay + vertex markers
      updateOverlayPolygon(polygon)
      renderVertexMarkers(polygon)
    })

    return () => {
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
    }
  }, [])

  // ── Render draggable vertex markers ───────────────────
  const renderVertexMarkers = useCallback((pts) => {
    if (!mapRef.current) return
    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    pts.forEach((pt, i) => {
      const el = document.createElement('div')
      el.className = 'vertex-marker'
      el.innerHTML = '<div class="vm-dot"></div>'

      const marker = new maplibregl.Marker({
        element: el, draggable: true, anchor: 'center',
      })
        .setLngLat([pt[1], pt[0]])
        .addTo(mapRef.current)

      // Live update both outlines while dragging
      marker.on('drag', () => {
        const ll     = marker.getLngLat()
        const newPts = pts.map((p, idx) =>
          idx === i ? [ll.lat, ll.lng] : p
        )
        updateMapPolygon(newPts)
        updateOverlayPolygon(newPts)
      })

      // Commit on release + recalculate
      marker.on('dragend', () => {
        const ll = marker.getLngLat()
        setPolygon(prev => {
          const newPts = [...prev]
          newPts[i]    = [ll.lat, ll.lng]
          recalculate(newPts)
          return newPts
        })
      })

      // Double-click to delete vertex
      el.addEventListener('dblclick', (e) => {
        e.stopPropagation()
        setPolygon(prev => {
          if (prev.length <= 3) {
            setStatus('Need at least 3 vertices')
            return prev
          }
          const newPts = prev.filter((_, idx) => idx !== i)
          updateMapPolygon(newPts)
          updateOverlayPolygon(newPts)
          renderVertexMarkers(newPts)
          recalculate(newPts)
          return newPts
        })
      })

      markersRef.current.push(marker)
    })
  }, [])

  // Re-render markers when polygon state changes
  useEffect(() => {
    if (!mapRef.current) return
    updateMapPolygon(polygon)
    updateOverlayPolygon(polygon)
    renderVertexMarkers(polygon)
  }, [polygon, renderVertexMarkers])

  // ── Draw mode ──────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current) return
    const map = mapRef.current

    const onMapClick = (e) => {
      if (mode !== 'draw') return
      const newPt  = [e.lngLat.lat, e.lngLat.lng]
      const newDrw = [...drawing, newPt]
      setDrawing(newDrw)
      updateMapPolygon(newDrw)
      updateOverlayPolygon(newDrw)

      const el = document.createElement('div')
      el.className = 'draw-marker'
      el.innerHTML = `<div class="dm-dot"></div>
                      <div class="dm-num">${newDrw.length}</div>`
      const m = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([e.lngLat.lng, e.lngLat.lat])
        .addTo(map)
      drawMkrsRef.current.push(m)
    }

    map.on('click', onMapClick)
    return () => map.off('click', onMapClick)
  }, [mode, drawing])

  // ── Recalculate area via backend ───────────────────────
  const recalculate = useCallback(async (pts) => {
    if (!pts || pts.length < 3) return
    setLoading(true)
    setStatus('Recalculating...')
    try {
      const { data } = await axios.post(`${API_URL}/recalculate`, {
        polygon: pts, ref_lat, ref_lon,
      })
      setArea(data.area_m2)
      setAreaFt(data.area_ft2)
      setStatus('✓ Area updated')
      setTimeout(() => setStatus(''), 2000)
    } catch {
      setStatus('Recalculate failed')
    } finally {
      setLoading(false)
    }
  }, [ref_lat, ref_lon])

  // ── Snap to rectangle ──────────────────────────────────
  const handleSnap = async () => {
    if (polygon.length < 3) return
    setSnapLoading(true)
    setStatus('Fitting rectangle...')
    try {
      const { data } = await axios.post(`${API_URL}/snap-rectangle`, {
        polygon, ref_lat, ref_lon,
      })
      setPolygon(data.polygon)
      setArea(data.area_m2)
      setAreaFt(data.area_ft2)
      setStatus('✓ Straight edges applied ✓')
      setTimeout(() => setStatus(''), 3000)
    } catch {
      setStatus('Snap failed')
    } finally {
      setSnapLoading(false)
    }
  }

  // ── Finish draw ────────────────────────────────────────
  const handleFinishDraw = () => {
    if (drawing.length < 3) { setStatus('Need at least 3 points'); return }
    drawMkrsRef.current.forEach(m => m.remove())
    drawMkrsRef.current = []
    setPolygon(drawing)
    setDrawing([])
    setMode('adjust')
    recalculate(drawing)
  }

  const handleCancelDraw = () => {
    drawMkrsRef.current.forEach(m => m.remove())
    drawMkrsRef.current = []
    setDrawing([])
    setMode('adjust')
    updateMapPolygon(polygon)
    updateOverlayPolygon(polygon)
  }

  // ── Reset ──────────────────────────────────────────────
  const handleReset = () => {
    const orig = roofResult.polygon || []
    setPolygon(orig)
    setArea(roofResult.area_m2)
    setAreaFt(roofResult.area_ft2)
    drawMkrsRef.current.forEach(m => m.remove())
    drawMkrsRef.current = []
    setDrawing([])
    setMode('adjust')
    setStatus('Reset to SAM original')
    setTimeout(() => setStatus(''), 2000)
  }

  const handleDone = () => onDone({ polygon, area_m2: area, area_ft2: areaFt })

  return (
    <div className="polygon-editor">

      {/* Toolbar */}
      <div className="pe-toolbar">
        <div className="pe-title">✏ EDIT ROOF POLYGON</div>
        <div className="pe-tools">
          {mode === 'adjust' && (
            <>
              <button className="pe-tool-btn active">↖ Adjust</button>
              <button className="pe-tool-btn" onClick={() => {
                drawMkrsRef.current.forEach(m => m.remove())
                drawMkrsRef.current = []
                setDrawing([])
                setMode('draw')
              }}>✎ Draw New</button>
              <button
                className="pe-tool-btn rect"
                onClick={handleSnap}
                disabled={snapLoading || polygon.length < 3}
              >
                {snapLoading ? '...' : '⬛ Rectangle'}
              </button>
              <button className="pe-tool-btn reset" onClick={handleReset}>
                ↺ Reset
              </button>
            </>
          )}
          {mode === 'draw' && (
            <>
              <div className="pe-draw-info">
                Click map to add points
                <span className="pe-draw-count">{drawing.length}</span>
              </div>
              <button
                className="pe-tool-btn active"
                onClick={handleFinishDraw}
                disabled={drawing.length < 3}
              >
                ✓ Finish ({drawing.length})
              </button>
              <button className="pe-tool-btn reset" onClick={handleCancelDraw}>
                ✕ Cancel
              </button>
            </>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="pe-map-wrap">
        <div ref={mapContainer} className="pe-map" />
        <div className={`pe-map-hint ${mode === 'draw' ? 'draw-active' : ''}`}>
          {mode === 'adjust'
            ? 'Drag orange dots · Double-click to remove · ⬛ for straight edges'
            : 'Click on map to add polygon points'}
        </div>
      </div>

      {/* Bottom bar */}
      <div className="pe-bottom">
        <div className="pe-area-display">
          <div className="pe-area-row">
            <div className="pe-area-val">
              {loading ? '...' : (area?.toFixed(1) ?? '—')}
              <span className="pe-unit">m²</span>
            </div>
            <div className="pe-area-divider" />
            <div className="pe-area-val secondary">
              {loading ? '...' : (areaFt?.toFixed(0) ?? '—')}
              <span className="pe-unit">ft²</span>
            </div>
          </div>
          {status && <div className="pe-status">{status}</div>}
        </div>
        <div className="pe-actions">
          <button className="pe-cancel-btn" onClick={onCancel}>✕ Cancel</button>
          <button className="pe-done-btn" onClick={handleDone}>✓ Use This Area</button>
        </div>
      </div>

    </div>
  )
}
