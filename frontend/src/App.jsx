import { useState } from 'react'
import MapPicker     from './components/MapPicker'
import SearchBar     from './components/SearchBar'
import Header        from './components/Header'
import Footer        from './components/Footer'
import ControlPanel  from './components/ControlPanel'
import PolygonEditor from './components/PolygonEditor'
import useMobileBottomSheet from './hooks/useMobileBottomSheet'
import useRoofEstimate      from './hooks/useRoofEstimate'
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

      <main className={`app-main ${result?.roof_found ? 'has-result' : ''}`}>
        <div className="left-panel">
          <div className="panel-label">01 — SELECT LOCATION</div>
          <SearchBar setCoords={setCoords} />
          <MapPicker
            coords={coords}
            setCoords={setCoords}
            result={result}
          />
        </div>

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
