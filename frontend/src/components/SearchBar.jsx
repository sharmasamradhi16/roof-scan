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
      </div>

      {showDrop && suggestions.length > 0 && (
        <ul className="suggestions-drop">
          {suggestions.map((item, i) => (
            <li
              key={i}
              className="suggestion-item"
              onPointerDown={(e) => {
                e.preventDefault()
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

      {error && <div className="search-error">⚠ {error}</div>}
      {found && !showDrop && (
        <div className="search-success">✓ {found}</div>
      )}
    </div>
  )
}
