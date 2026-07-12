import './ResultCard.css'

export default function ResultCard({
  result, loading, error, onSolarClick, onEditPolygon
}) {

  if (loading) {
    return (
      <div className="result-card center">
        <div className="scan-animation">
          <div className="scan-ring" />
          <div className="scan-ring delay1" />
          <div className="scan-ring delay2" />
          <div className="scan-label">SCANNING</div>
        </div>
        <div className="loading-steps">
          <div className="step active">▸ Downloading satellite tiles...</div>
          <div className="step">▸ Running SAM1 inference...</div>
          <div className="step">▸ Calculating roof area...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="result-card center">
        <div className="error-box">
          <div className="error-icon">⚠</div>
          <div className="error-msg">{error}</div>
        </div>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="result-card center">
        <div className="idle-state">
          <div className="idle-icon">⬡</div>
          <div className="idle-title">AWAITING TARGET</div>
          <div className="idle-sub">
            Drop a pin on the map or enter<br/>coordinates to begin analysis
          </div>
        </div>
      </div>
    )
  }

  if (!result.roof_found) {
    return (
      <div className="result-card center">
        <div className="error-box">
          <div className="error-icon">◎</div>
          <div className="error-msg">
            No roof detected at this location.<br/>
            Try adjusting the pin position.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="result-card">

      {/* Area numbers */}
      <div className="result-metrics">
        <div className="metric">
          <div className="metric-value">
            {result.area_m2.toFixed(1)}<span className="unit">m²</span>
          </div>
          <div className="metric-label">ROOF AREA</div>
        </div>
        <div className="metric-divider" />
        <div className="metric">
          <div className="metric-value">
            {result.area_ft2.toFixed(0)}<span className="unit">ft²</span>
          </div>
          <div className="metric-label">ROOF AREA</div>
        </div>
      </div>

      {/* Detail rows */}
      <div className="result-details">
        <div className="detail-row">
          <span className="detail-key">PIXEL COUNT</span>
          <span className="detail-val">
            {result.pixel_count.toLocaleString()} px²
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-key">GROUND RESOLUTION</span>
          <span className="detail-val">
            {result.meters_per_pixel.toFixed(4)} m/px
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-key">LATITUDE</span>
          <span className="detail-val">{result.lat}</span>
        </div>
        <div className="detail-row">
          <span className="detail-key">LONGITUDE</span>
          <span className="detail-val">{result.lon}</span>
        </div>
        <div className="detail-row">
          <span className="detail-key">POLYGON VERTICES</span>
          <span className="detail-val">
            {result.polygon ? result.polygon.length : '—'}
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-key">STATUS</span>
          <span className="detail-val success">✓ ROOF DETECTED</span>
        </div>
      </div>

      {/* Edit polygon button */}
      <div className="edit-polygon-wrap">
        <button className="edit-polygon-btn" onClick={onEditPolygon}>
          ✏ EDIT ROOF POLYGON
        </button>
        <div className="edit-hint">
          Drag vertices · Draw manually · Snap to rectangle
        </div>
      </div>

      {/* Solar CTA */}
      <div className="solar-cta-wrap">
        <button className="solar-cta-btn" onClick={onSolarClick}>
          ☀ ANALYSE SOLAR POTENTIAL
        </button>
      </div>

    </div>
  )
}
