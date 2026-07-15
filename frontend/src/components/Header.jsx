export default function Header({ onHome }) {
  return (
    <header className="app-header">
      <button
        type="button"
        className="header-logo header-logo-btn"
        onClick={onHome}
        title="Back to home"
        aria-label="Back to home"
      >
        <span className="logo-icon">⬡</span>
        <span className="logo-text">ROOF<span className="accent">SCAN</span></span>
      </button>
      <div className="header-tag">Satellite Rooftop &amp; Solar Estimator</div>
    </header>
  )
}
