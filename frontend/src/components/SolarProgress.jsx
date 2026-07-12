import './SolarProgress.css'

const STEPS = [
  { id: 1, label: "Fetching daily weather data" },
  { id: 2, label: "Fetching hourly weather data" },
  { id: 3, label: "Running loss models (L1-L4)" },
  { id: 4, label: "Training AI loss models (L5 & L7)" },
  { id: 5, label: "Calculating solar sizing & ROI" },
]

export default function SolarProgress({ currentStep }) {
  return (
    <div className="solar-progress">
      <div className="sp-header">
        <div className="sp-sun">☀</div>
        <div className="sp-title">Analysing Solar Potential</div>
        <div className="sp-sub">This takes 2–4 minutes</div>
      </div>
      <div className="sp-steps">
        {STEPS.map(s => {
          const done    = currentStep > s.id
          const active  = currentStep === s.id
          const pending = currentStep < s.id
          return (
            <div key={s.id} className={`sp-step ${done ? 'done' : active ? 'active' : 'pending'}`}>
              <div className="sp-icon">
                {done   ? '✓' :
                 active ? <span className="sp-spinner" /> :
                          '○'}
              </div>
              <div className="sp-label">{s.label}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
