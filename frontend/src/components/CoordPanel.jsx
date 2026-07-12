import './CoordPanel.css'

export default function CoordPanel({ coords, setCoords }) {
  return (
    <div className="coord-panel">
      <div className="coord-row">
        <div className="coord-field">
          <label>LATITUDE</label>
          <input
            type="number"
            step="0.00000001"
            value={coords.lat}
            onChange={e => setCoords(c => ({ ...c, lat: parseFloat(e.target.value) || 0 }))}
            placeholder="18.47418..."
          />
        </div>
        <div className="coord-field">
          <label>LONGITUDE</label>
          <input
            type="number"
            step="0.00000001"
            value={coords.lon}
            onChange={e => setCoords(c => ({ ...c, lon: parseFloat(e.target.value) || 0 }))}
            placeholder="73.88185..."
          />
        </div>
      </div>
      <div className="coord-hint">↖ Or click directly on the map to set location</div>
    </div>
  )
}
