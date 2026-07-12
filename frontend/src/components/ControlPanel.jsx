import { useState } from 'react'
import CoordPanel from './CoordPanel'
import ResultCard from './ResultCard'
import SolarTab   from './SolarTab'

export default function ControlPanel({
  coords,
  setCoords,
  result,
  loading,
  error,
  onEstimate,
  onEditPolygon,     // NEW — passed down from App.jsx
  isMobileSheet,
  sheetStyle,
  handlePointerDown,
  handleTouchStart,
}) {
  const [activeTab, setTab] = useState('roof')

  return (
    <div
      className={`right-panel ${isMobileSheet ? 'mobile-sheet' : ''}`}
      style={sheetStyle}
    >
      <button
        className="sheet-toggle"
        type="button"
        onPointerDown={handlePointerDown}
        onTouchStart={handleTouchStart}
        aria-label="Drag panel handle"
      >
        <span className="sheet-handle" />
      </button>

      {/* Tab bar */}
      <div className="tab-bar">
        <button
          className={`tab-btn ${activeTab === 'roof' ? 'active' : ''}`}
          onClick={() => setTab('roof')}
        >
          🏠 ROOF
        </button>
        <button
          className={`tab-btn ${activeTab === 'solar' ? 'active' : ''} ${!result?.roof_found ? 'disabled' : ''}`}
          onClick={() => result?.roof_found && setTab('solar')}
        >
          ☀ SOLAR
        </button>
      </div>

      {/* ROOF TAB */}
      {activeTab === 'roof' && (
        <>
          <div className="panel-label">02 — COORDINATES</div>
          <CoordPanel coords={coords} setCoords={setCoords} />
          <div className="panel-label result-label">03 — ANALYSIS RESULT</div>
          <div className="result-scroll">
            <ResultCard
              result={result}
              loading={loading}
              error={error}
              onSolarClick={() => setTab('solar')}
              onEditPolygon={onEditPolygon}
            />
          </div>
          <div className="estimate-footer">
            <button
              className={`estimate-btn ${loading ? 'loading' : ''}`}
              onClick={onEstimate}
              disabled={loading}
            >
              {loading ? (
                <span className="btn-inner">
                  <span className="spinner" />
                  ANALYZING ROOFTOP...
                </span>
              ) : (
                <span className="btn-inner">
                  ⬡ ESTIMATE ROOF AREA
                </span>
              )}
            </button>
          </div>
        </>
      )}

      {/* SOLAR TAB */}
      {activeTab === 'solar' && (
        <>
          <div className="panel-label">☀ — SOLAR POTENTIAL ANALYSIS</div>
          <div className="result-scroll">
            <SolarTab roofResult={result} />
          </div>
        </>
      )}
    </div>
  )
}
