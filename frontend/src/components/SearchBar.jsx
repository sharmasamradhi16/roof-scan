import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { API_URL } from '../lib/api'
import './SearchBar.css'

const DEBOUNCE_MS = 250
const SUGGEST_TIMEOUT_MS = 6000

export default function SearchBar({ setCoords }) {
  const [query, setQuery]           = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)
  const [found, setFound]           = useState(null)
  const [showDrop, setShowDrop]     = useState(false)
  const [locating, setLocating]     = useState(false)
  const [geoError, setGeoError]     = useState(null)

  const debounceRef = useRef(null)
  const wrapperRef  = useRef(null)
  const suggestGenRef = useRef(0)
  const abortRef = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDrop(false)
      }
    }
    // Use capture + a small "ignore if inside wrapper" check is already handled
    // above, but on touch devices `pointerdown` fires (and can close the
    // dropdown / unmount the <li>) a beat before `click` fires on the same
    // target. When that happens the tap "falls through" to whatever is now
    // underneath the finger — which, on the mobile layout, is the map. The
    // wrapperRef.contains check already protects taps inside the dropdown,
    // so this was actually safe — the real fix is on the <li> itself (see
    // handleSelect / onPointerDown below), which stops propagation before
    // this handler can even run.
    document.addEventListener('mousedown', handler)
    document.addEventListener('pointerdown', handler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('pointerdown', handler)
    }
  }, [])

  useEffect(() => {
    if (query.trim().length < 3) {
      clearTimeout(debounceRef.current)
      suggestGenRef.current += 1
      abortRef.current?.abort()
      setSuggestions([])
      setShowDrop(false)
      setLoading(false)
      return
    }

    clearTimeout(debounceRef.current)
    const q = query.trim()
    debounceRef.current = setTimeout(async () => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      const gen = ++suggestGenRef.current
      setLoading(true)
      setError(null)
      try {
        const res = await axios.post(
          `${API_URL}/suggest`,
          { query: q },
          { timeout: SUGGEST_TIMEOUT_MS, signal: controller.signal }
        )
        if (gen !== suggestGenRef.current) return
        const list = Array.isArray(res.data?.results) ? res.data.results : []
        setSuggestions(list)
        setShowDrop(list.length > 0)
      } catch (err) {
        if (axios.isCancel(err) || err?.code === 'ERR_CANCELED') return
        if (gen !== suggestGenRef.current) return
        setSuggestions([])
        setShowDrop(false)
        setError('Search service unavailable. Check backend connection.')
      } finally {
        if (gen === suggestGenRef.current) setLoading(false)
      }
    }, DEBOUNCE_MS)

    return () => clearTimeout(debounceRef.current)
  }, [query])

  const handleSelect = (item) => {
    const lat = typeof item.lat === 'number' ? item.lat : parseFloat(item.lat)
    const lon = typeof item.lon === 'number' ? item.lon : parseFloat(item.lon)
    // Flag this as a "search selection" moment. MapPicker briefly ignores
    // its own click-to-move-pin handler right after one of these, so that
    // if a touch tap on a suggestion also produces a stray click event on
    // the map underneath (a known mobile browser quirk with absolutely
    // positioned overlays atop canvas-based maps), it can't silently
    // override the location the person actually chose.
    window.__roofscanLastSearchSelect = Date.now()
    setCoords({
      lat: parseFloat(lat.toFixed(8)),
      lon: parseFloat(lon.toFixed(8))
    })
    setQuery(item.short_label)
    setFound(item.display_name)
    setSuggestions([])
    setShowDrop(false)
    setError(null)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') setShowDrop(false)
  }

  const handleUseMyLocation = () => {
    setGeoError(null)
    setError(null)
    setFound(null)
    setShowDrop(false)

    if (!('geolocation' in navigator)) {
      setGeoError('Geolocation is not supported by this browser.')
      return
    }

    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = parseFloat(pos.coords.latitude.toFixed(8))
        const lon = parseFloat(pos.coords.longitude.toFixed(8))

        // Same guard used for search selections — protects against a
        // stray map click landing right after this and silently moving
        // the pin away from the GPS fix.
        window.__roofscanLastSearchSelect = Date.now()
        setCoords({ lat, lon })
        setLocating(false)

        // Best-effort label via reverse geocode so the input shows
        // something readable instead of raw coordinates. If it fails,
        // fall back to the coordinates themselves — the pin has already
        // moved either way, so this is cosmetic only.
        try {
          const res = await axios.post(
            `${API_URL}/reverse`,
            { lat, lon },
            { timeout: SUGGEST_TIMEOUT_MS }
          )
          const label = res.data?.display_name || res.data?.short_label
          if (label) {
            setQuery(res.data?.short_label || label)
            setFound(label)
            return
          }
        } catch {
          // ignore — fall through to coordinate label below
        }
        setQuery(`${lat}, ${lon}`)
        setFound('Current location')
      },
      (err) => {
        setLocating(false)
        if (err.code === err.PERMISSION_DENIED) {
          setGeoError('Location permission denied. Allow location access in your browser settings to use this.')
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setGeoError('Could not determine your location. Try again or search manually.')
        } else if (err.code === err.TIMEOUT) {
          setGeoError('Location request timed out. Try again.')
        } else {
          setGeoError('Could not get your location.')
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    )
  }

  return (
    <div className="searchbar-wrapper" ref={wrapperRef}>
      <div className={`searchbar-row ${showDrop ? 'open' : ''}`}>
        <div className="search-icon">⌖</div>
        <input
          type="text"
          className="search-input"
          placeholder="Search address, building, society..."
          value={query}
          onChange={e => {
            setQuery(e.target.value)
            setError(null)
            setFound(null)
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowDrop(true)}
          autoComplete="off"
        />
        {loading && <span className="search-spinner" />}
        <button
          type="button"
          className={`locate-btn ${locating ? 'locating' : ''}`}
          onClick={handleUseMyLocation}
          disabled={locating}
          title="Use my current location"
          aria-label="Use my current location"
        >
          {locating ? <span className="search-spinner" /> : '📍'}
        </button>
      </div>

      {showDrop && suggestions.length > 0 && (
        <ul className="suggestions-drop" onPointerDown={(e) => e.stopPropagation()}>
          {suggestions.map((item, i) => (
            <li
              key={i}
              className="suggestion-item"
              onMouseDown={(e) => e.preventDefault()}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                handleSelect(item)
              }}
            >
              <span className="sug-icon">📍</span>
              <div className="sug-text">
                <div className="sug-label">{item.short_label}</div>
                <div className="sug-full">{item.display_name}</div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {geoError && <div className="search-error">⚠ {geoError}</div>}
      {error && <div className="search-error">⚠ {error}</div>}
      {found && !showDrop && !geoError && (
        <div className="search-success">✓ {found}</div>
      )}
    </div>
  )
}
