import { useEffect, useState } from 'react'
import MapPicker     from './components/MapPicker'
import SearchBar     from './components/SearchBar'
import Header        from './components/Header'
import Footer        from './components/Footer'
import ControlPanel  from './components/ControlPanel'
import PolygonEditor from './components/PolygonEditor'
import useMobileBottomSheet from './hooks/useMobileBottomSheet'
import useRoofEstimate      from './hooks/useRoofEstimate'
import useResizablePanels   from './hooks/useResizablePanels'
import './App.css'

export default function App() {
  const [coords, setCoords]     = useState({ lat: 18.4742, lon: 73.8819 })
  const [showEditor, setEditor] = useState(false)

  // Once a roof has been found, the map "locks": it keeps a constant size
  // and gets a translucent cover with an "Edit Pin" button, instead of
  // shrinking to make room for the analysis panel. That shrinking was
  // what left a white gap on mobile — the bottom sheet is `position:
  // fixed` and floats over everything, so the map's flex sibling had
  // nothing left to size itself against. Locking sidesteps that: the map
  // never resizes at all once a result exists.
  const [mapLocked, setMapLocked] = useState(false)

  const { result, setResult, loading, error, estimateRoof } = useRoofEstimate()

  // Wrap setCoords so picking a new spot (search or map click) always
  // re-opens the live map — the pin only ever moves while the map is
  // visible, so "locked" and "pin just moved" can't be true together.
  const handleSetCoords = (next) => {
    setCoords(next)
    setMapLocked(false)
  }

  const {
    isMobileSheet,
    sheetStyle,
    handlePointerDown,
    handleTouchStart,
  } = useMobileBottomSheet()

  const {
    shellRef,
    dragging,
    rightWidth,
    hasCustomWidth,
    onPointerDownDivider,
    resetWidth,
  } = useResizablePanels(!!result?.roof_found)

  // Called when user clicks "Use This Area" in PolygonEditor
  const handleEditorDone = ({ polygon, area_m2, area_ft2 }) => {
    setResult(prev => ({ ...prev, polygon, area_m2, area_ft2 }))
    setEditor(false)
  }

  // Lock the map once a roof is found; unlock it while a fresh estimate
  // is running so the person can see the map clearly while it works.
  useEffect(() => {
    if (result?.roof_found) setMapLocked(true)
  }, [result])

  useEffect(() => {
    if (loading) setMapLocked(false)
  }, [loading])

  return (
    <div className="app-shell">

      {/* Polygon editor — full screen overlay */}
      {showEditor && result?.roof_found && (
        <PolygonEditor
          roofResult={result}
          onDone={handleEditorDone}
          onCancel={() => setEditor(false)}
        />
      )}

      <Header />

      <div className="step-guide">
        <div className={`step-item ${!result ? 'current' : result ? 'done' : ''}`}>
          <span className="step-num">1</span>
          <span className="step-text">Pick a location &amp; estimate roof</span>
        </div>
        <span className="step-arrow">→</span>
        <div className={`step-item ${result?.roof_found && !showEditor ? 'current' : ''} ${result?.polygon ? 'done' : ''}`}>
          <span className="step-num">2</span>
          <span className="step-text">Review / edit the roof outline</span>
        </div>
        <span className="step-arrow">→</span>
        <div className={`step-item ${result?.roof_found ? '' : 'locked'}`}>
          <span className="step-num">3</span>
          <span className="step-text">Get solar potential estimate</span>
        </div>
      </div>

      <main
        ref={shellRef}
        className={`app-main ${result?.roof_found ? 'has-result' : ''} ${dragging ? 'resizing' : ''}`}
        style={!isMobileSheet ? { gridTemplateColumns: `1fr 10px ${rightWidth}px` } : undefined}
      >
        <div className={`left-panel ${mapLocked ? 'map-locked' : ''}`}>
          <div className="panel-label">01 — SELECT LOCATION</div>
          <SearchBar setCoords={handleSetCoords} />
          <div className="map-area">
            <MapPicker
              coords={coords}
              setCoords={handleSetCoords}
              result={result}
            />
            {mapLocked && (
              <div className="map-lock-overlay">
                <button
                  className="edit-pin-btn"
                  onClick={() => setMapLocked(false)}
                  type="button"
                >
                  📍 EDIT PIN LOCATION
                </button>
                <div className="map-lock-hint">Roof found — map locked to keep this compact</div>
              </div>
            )}
          </div>
        </div>

        {!isMobileSheet && (
          <div
            className="panel-divider"
            onPointerDown={onPointerDownDivider}
            onDoubleClick={resetWidth}
            title={hasCustomWidth ? 'Drag to resize · double-click to reset' : 'Drag to resize this panel'}
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize panels"
          >
            <span className="panel-divider-grip" />
          </div>
        )}

        <ControlPanel
          coords={coords}
          setCoords={handleSetCoords}
          result={result}
          loading={loading}
          error={error}
          onEstimate={() => estimateRoof(coords)}
          onEditPolygon={() => setEditor(true)}
          isMobileSheet={isMobileSheet}
          sheetStyle={sheetStyle}
          handlePointerDown={handlePointerDown}
          handleTouchStart={handleTouchStart}
        />
      </main>

      <Footer />
    </div>
  )
}
