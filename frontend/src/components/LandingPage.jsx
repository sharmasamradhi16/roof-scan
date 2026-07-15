import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { API_URL } from '../lib/api'
import './LandingPage.css'

const DEBOUNCE_MS = 250
const SUGGEST_TIMEOUT_MS = 6000

export default function LandingPage({ onStart }) {
  const [query, setQuery]             = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)
  const [showDrop, setShowDrop]       = useState(false)
  const [locating, setLocating]       = useState(false)
  const [audience, setAudience]       = useState('homeowner') // 'homeowner' | 'vendor'

  const debounceRef    = useRef(null)
  const wrapperRef      = useRef(null)
  const suggestGenRef   = useRef(0)
  const abortRef        = useRef(null)

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
        setError('Search is unavailable right now — check your connection.')
      } finally {
        if (gen === suggestGenRef.current) setLoading(false)
      }
    }, DEBOUNCE_MS)

    return () => clearTimeout(debounceRef.current)
  }, [query])

  const handleSelect = (item) => {
    const lat = typeof item.lat === 'number' ? item.lat : parseFloat(item.lat)
    const lon = typeof item.lon === 'number' ? item.lon : parseFloat(item.lon)
    setShowDrop(false)
    setSuggestions([])
    onStart({
      lat: parseFloat(lat.toFixed(8)),
      lon: parseFloat(lon.toFixed(8))
    })
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') setShowDrop(false)
    // Enter with exactly one suggestion showing = "just go"
    if (e.key === 'Enter' && suggestions.length > 0) {
      handleSelect(suggestions[0])
    }
  }

  const handleUseMyLocation = () => {
    setError(null)
    setShowDrop(false)

    if (!('geolocation' in navigator)) {
      setError('Geolocation is not supported by this browser — try searching instead.')
      return
    }

    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        onStart({
          lat: parseFloat(pos.coords.latitude.toFixed(8)),
          lon: parseFloat(pos.coords.longitude.toFixed(8))
        })
      },
      (err) => {
        setLocating(false)
        if (err.code === err.PERMISSION_DENIED) {
          setError('Location permission denied — allow access or search your address above.')
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setError('Could not determine your location. Try searching instead.')
        } else if (err.code === err.TIMEOUT) {
          setError('Location request timed out. Try again.')
        } else {
          setError('Could not get your location.')
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    )
  }

  return (
    <div className="landing">
      {/* ── NAV ─────────────────────────────────────────── */}
      <nav className="landing-nav">
        <div className="landing-logo">
          <span className="logo-icon">⬡</span>
          <span className="logo-text">ROOF<span className="accent">SCAN</span></span>
        </div>
        <div className="landing-nav-links">
          <a href="#how-it-works">How it works</a>
          <a href="#audience">Who it's for</a>
          <a href="#faq">FAQ</a>
        </div>
      </nav>

      {/* ── HERO ────────────────────────────────────────── */}
      <section className="landing-hero">
        <div className="hero-badge">☀ Free instant solar &amp; roof analysis</div>
        <h1 className="hero-title">
          Point at a roof.<br />
          Get its <span className="accent">solar potential</span> in seconds.
        </h1>
        <p className="hero-sub">
          Search any address or drop a pin on your home, office, or a client's
          property. RoofScan measures the roof from satellite imagery and tells
          you exactly how much sunlight — and savings — it can capture.
        </p>

        {/* ── Chat-style location entry ── */}
        <div className="hero-input-wrap" ref={wrapperRef}>
          <div className={`hero-input-row ${showDrop ? 'open' : ''}`}>
            <span className="hero-input-icon">🔍</span>
            <input
              type="text"
              className="hero-input"
              placeholder="Search your address, society, or building name…"
              value={query}
              onChange={e => { setQuery(e.target.value); setError(null) }}
              onKeyDown={handleKeyDown}
              onFocus={() => suggestions.length > 0 && setShowDrop(true)}
              autoComplete="off"
            />
            {loading && <span className="hero-spinner" />}
            <button
              type="button"
              className={`hero-locate-btn ${locating ? 'locating' : ''}`}
              onClick={handleUseMyLocation}
              disabled={locating}
              title="Use my current location"
            >
              {locating ? <span className="hero-spinner" /> : '📍'}
              <span className="hero-locate-label">
                {locating ? 'Locating…' : 'Use my location'}
              </span>
            </button>
          </div>

          {showDrop && suggestions.length > 0 && (
            <ul className="hero-suggestions" onPointerDown={(e) => e.stopPropagation()}>
              {suggestions.map((item, i) => (
                <li
                  key={i}
                  className="hero-suggestion-item"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleSelect(item) }}
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

          {error && <div className="hero-error">⚠ {error}</div>}
        </div>

        <div className="hero-hint">
          No sign-up needed — just search a place, or tap “use my location” to jump straight into the scan.
        </div>
      </section>

      {/* ── HOW IT WORKS ────────────────────────────────── */}
      <section className="landing-steps" id="how-it-works">
        <h2 className="section-title">How RoofScan works</h2>
        <p className="section-sub">Three steps, no site visit required.</p>
        <div className="steps-grid">
          <div className="step-card">
            <div className="step-icon-wrap sky">📍</div>
            <div className="step-num-badge">1</div>
            <h3>Locate the roof</h3>
            <p>Search an address or drop a pin — or let us use your device location automatically.</p>
          </div>
          <div className="step-card">
            <div className="step-icon-wrap mint">🛰️</div>
            <div className="step-num-badge">2</div>
            <h3>Scan &amp; outline</h3>
            <p>Our model traces the roof from satellite imagery and gives you an accurate area you can fine-tune by hand.</p>
          </div>
          <div className="step-card">
            <div className="step-icon-wrap sun">☀️</div>
            <div className="step-num-badge">3</div>
            <h3>See solar potential</h3>
            <p>Get usable roof area, sun exposure, estimated panel count, energy yield, and payback — all in one view.</p>
          </div>
        </div>
      </section>

      {/* ── WHAT YOU GET ────────────────────────────────── */}
      <section className="landing-goals">
        <h2 className="section-title">What the analysis covers</h2>
        <p className="section-sub">Everything you need to decide if solar makes sense — before anyone climbs a ladder.</p>
        <div className="goals-grid">
          <div className="goal-pill">
            <span className="goal-icon">📐</span>
            <div><strong>Near-accurate roof area</strong><span>Measured from imagery, editable by hand</span></div>
          </div>
          <div className="goal-pill">
            <span className="goal-icon">🔆</span>
            <div><strong>Solar potential score</strong><span>Usable area after shading &amp; obstructions</span></div>
          </div>
          <div className="goal-pill">
            <span className="goal-icon">🔋</span>
            <div><strong>Panel &amp; system sizing</strong><span>Estimated panel count and system capacity</span></div>
          </div>
          <div className="goal-pill">
            <span className="goal-icon">💰</span>
            <div><strong>Savings &amp; payback</strong><span>Estimated energy yield and cost recovery time</span></div>
          </div>
          <div className="goal-pill">
            <span className="goal-icon">🌱</span>
            <div><strong>Environmental impact</strong><span>Approximate CO₂ offset per year</span></div>
          </div>
          <div className="goal-pill">
            <span className="goal-icon">📄</span>
            <div><strong>Shareable report</strong><span>Export a clean PDF for records or clients</span></div>
          </div>
        </div>
      </section>

      {/* ── AUDIENCE ────────────────────────────────────── */}
      <section className="landing-audience" id="audience">
        <h2 className="section-title">Built for both sides of a solar decision</h2>
        <div className="audience-toggle" role="tablist">
          <button
            className={`audience-tab ${audience === 'homeowner' ? 'active' : ''}`}
            onClick={() => setAudience('homeowner')}
            type="button"
          >🏠 Homeowners &amp; businesses</button>
          <button
            className={`audience-tab ${audience === 'vendor' ? 'active' : ''}`}
            onClick={() => setAudience('vendor')}
            type="button"
          >🧰 Solar vendors &amp; installers</button>
        </div>

        {audience === 'homeowner' ? (
          <div className="audience-panel">
            <ul>
              <li>Check your own roof's solar potential before requesting quotes.</li>
              <li>Understand real usable area — not just rooftop square footage.</li>
              <li>Get a ballpark on savings and payback to compare against vendor quotes.</li>
              <li>Share your scan report directly with installers to speed up quoting.</li>
            </ul>
          </div>
        ) : (
          <div className="audience-panel">
            <ul>
              <li>Pre-qualify leads in seconds — scan a client's address before a site visit.</li>
              <li>Generate consistent, shareable roof reports for every proposal.</li>
              <li>Speed up quoting with instant area, sun exposure, and system-size estimates.</li>
              <li>Fine-tune the auto-detected outline to match real obstructions before quoting.</li>
            </ul>
          </div>
        )}
      </section>

      {/* ── CTA ─────────────────────────────────────────── */}
      <section className="landing-cta">
        <h2>Ready to see your roof's solar potential?</h2>
        <p>Search an address above, or jump straight in with the button below.</p>
        <button
          className="cta-button"
          type="button"
          onClick={() => onStart(null)}
        >
          Start scanning →
        </button>
      </section>

      <footer className="landing-footer" id="faq">
        <span>ROOFSCAN · Satellite Rooftop &amp; Solar Estimator</span>
        <span>Estimates are approximate and for planning purposes — not a substitute for a site survey.</span>
      </footer>
    </div>
  )
}
