import { useState } from 'react'
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

  const { result, setResult, loading, error, estimateRoof } = useRoofEstimate()

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
        <div className="left-panel">
          <div className="panel-label">01 — SELECT LOCATION</div>
          <SearchBar setCoords={setCoords} />
          <MapPicker
            coords={coords}
            setCoords={setCoords}
            result={result}
          />
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
          setCoords={setCoords}
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
