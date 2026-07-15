import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import './MapPicker.css'

export default function MapPicker({ coords, setCoords, result }) {
  const mapContainer = useRef(null)
  const mapRef = useRef(null)
  const markerRef = useRef(null)

  useEffect(() => {
    if (mapRef.current) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'satellite': {
            type: 'raster',
            tiles: ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'],
            tileSize: 256,
            attribution: '© Google Satellite'
          }
        },
        layers: [{
          id: 'satellite',
          type: 'raster',
          source: 'satellite',
          minzoom: 0,
          maxzoom: 21
        }]
      },
      center: [coords.lon, coords.lat],
      zoom: 17,
      pitch: 45,
      bearing: 0,
      antialias: true,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.addControl(new maplibregl.ScaleControl(), 'bottom-left')

    // Add 3D globe projection
    map.on('style.load', () => {
      try {
        map.setProjection({ type: 'globe' })
      } catch(e) {
        // globe not supported, flat is fine
      }
    })

    // Marker
    const el = document.createElement('div')
    el.className = 'custom-marker'
    el.innerHTML = `
      <div class="marker-pin"></div>
      <div class="marker-pulse"></div>
    `

    const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
      .setLngLat([coords.lon, coords.lat])
      .addTo(map)

    markerRef.current = marker

    // Click to move pin
    map.on('click', (e) => {
      // See SearchBar.handleSelect — on mobile, tapping a search suggestion
      // can occasionally also dispatch a stray click on the map canvas
      // beneath the dropdown. Ignore map clicks that land immediately
      // after a search selection so they can't silently move the pin
      // back to wherever the finger happened to be.
      const sinceSelect = Date.now() - (window.__roofscanLastSearchSelect || 0)
      if (sinceSelect < 500) return

      const lat = parseFloat(e.lngLat.lat.toFixed(8))
      const lon = parseFloat(e.lngLat.lng.toFixed(8))
      marker.setLngLat([lon, lat])
      setCoords({ lat, lon })
    })

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Update marker when coords change from input fields
  useEffect(() => {
    if (markerRef.current && mapRef.current) {
      markerRef.current.setLngLat([coords.lon, coords.lat])
      mapRef.current.flyTo({
        center: [coords.lon, coords.lat],
        zoom: 18,
        speed: 1.2
      })
    }
  }, [coords.lat, coords.lon])

// --- NEW CODE BLOCK: Image Overlay Logic ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // If there is no result (or a new search started), hide the layer
    if (!result || !result.image_base64) {
      if (map.getSource('roof-overlay')) {
        map.setLayoutProperty('roof-layer', 'visibility', 'none');
      }
      return;
    }

    // 1. Math to find the exact tile coordinates the backend used (Zoom 20)
    const zoom = 20;
    const n = Math.pow(2, zoom);
    const latRad = (result.lat * Math.PI) / 180;
    const xtile = Math.floor(((result.lon + 180.0) / 360.0) * n);
    const ytile = Math.floor(
      ((1.0 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2.0) * n
    );

    // 2. The backend downloaded a 4x4 tile grid (1024px / 256px = 4)
    const start_x = xtile - 2; 
    const start_y = ytile - 2;

    // Helper to convert XYZ tiles back to Longitude/Latitude
    const tile2lngLat = (x, y, z) => {
      const n = Math.pow(2, z);
      const lon = (x / n) * 360.0 - 180.0;
      const latRad = Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n)));
      const lat = (latRad * 180.0) / Math.PI;
      return [lon, lat];
    };

    // 3. Get the 4 corners of the image
    const tl = tile2lngLat(start_x, start_y, zoom);         // Top Left
    const tr = tile2lngLat(start_x + 4, start_y, zoom);     // Top Right
    const br = tile2lngLat(start_x + 4, start_y + 4, zoom); // Bottom Right
    const bl = tile2lngLat(start_x, start_y + 4, zoom);     // Bottom Left

    const coordinates = [tl, tr, br, bl];

    // 4. Update or Create the MapLibre Image Layer
    if (map.getSource('roof-overlay')) {
      // Update existing layer
      map.getSource('roof-overlay').updateImage({
        url: result.image_base64,
        coordinates: coordinates
      });
      map.setLayoutProperty('roof-layer', 'visibility', 'visible');
    } else {
      // Create new layer on first run
      map.addSource('roof-overlay', {
        type: 'image',
        url: result.image_base64,
        coordinates: coordinates
      });
      map.addLayer({
        id: 'roof-layer',
        type: 'raster',
        source: 'roof-overlay',
        paint: {
          'raster-opacity': 0.85, // Slightly transparent so it blends well
          'raster-fade-duration': 300 // Smooth fade-in
        }
      });
    }
  }, [result]);
  // --- END NEW CODE BLOCK ---

  return (
    <div className="map-wrapper">
      <div className="map-hint">🌐 Scroll to zoom · Click to drop pin · Drag to rotate</div>
      <div ref={mapContainer} className="map-container" />
    </div>
  )
}
