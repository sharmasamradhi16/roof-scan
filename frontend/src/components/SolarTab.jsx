import { useState } from 'react'
import axios from 'axios'
import SolarProgress from './SolarProgress'
import './SolarTab.css'

import { API_URL } from '../lib/api.js'

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"]

export default function SolarTab({ roofResult }) {
  const [bill, setBill]        = useState('')
  const [loading, setLoading]  = useState(false)
  const [currentStep, setStep] = useState(0)
  const [result, setResult]    = useState(null)
  const [error, setError]      = useState(null)
  const [activePanel, setActivePanel] = useState(0)

  const canCalculate = roofResult?.roof_found && bill && !loading

  const handleCalculate = async () => {
    if (!canCalculate) return
    setLoading(true)
    setError(null)
    setResult(null)
    setStep(1)

    try {
      const { data } = await axios.post(`${API_URL}/solar-estimate`, {
        lat:          roofResult.lat,
        lon:          roofResult.lon,
        area_m2:      roofResult.area_m2,
        monthly_bill: parseFloat(bill),
      })

      const jobId = data.job_id
      const es = new EventSource(`${API_URL}/solar-progress/${jobId}`)

      es.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        if (msg.step === 'done') {
          setResult(msg.result)
          setLoading(false)
          setStep(0)
          setActivePanel(0)
          es.close()
        } else if (msg.step === 'error') {
          setError(msg.message || 'Analysis failed.')
          setLoading(false)
          setStep(0)
          es.close()
        } else {
          setStep(msg.step)
        }
      }

      es.onerror = () => {
        setError('Connection lost. Please try again.')
        setLoading(false)
        setStep(0)
        es.close()
      }

    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start analysis.')
      setLoading(false)
      setStep(0)
    }
  }

  // ── NOT YET ESTIMATED ──
  if (!roofResult?.roof_found) {
    return (
      <div className="solar-tab">
        <div className="solar-locked">
          <div className="solar-locked-icon">☀</div>
          <div className="solar-locked-title">SOLAR ANALYSIS</div>
          <div className="solar-locked-sub">
            First estimate your roof area in the<br/>
            <strong>ROOF</strong> tab to unlock solar analysis
          </div>
        </div>
      </div>
    )
  }

  // ── LOADING ──
  if (loading) {
    return (
      <div className="solar-tab">
        <SolarProgress currentStep={currentStep} />
      </div>
    )
  }

  // ── ERROR ──
  if (error) {
    return (
      <div className="solar-tab">
        <div className="solar-error">
          <div className="solar-error-icon">⚠</div>
          <div className="solar-error-msg">{error}</div>
          <button className="solar-retry-btn"
            onClick={() => setError(null)}>Try Again</button>
        </div>
      </div>
    )
  }

  // ── RESULTS ──
  if (result) {
    const panel = result.panels[activePanel]
    const { L5, L7 } = panel

    return (
      <div className="solar-tab">
        <div className="solar-results">

          {/* Consumption summary */}
          <div className="solar-consumption">
            <div className="sc-header">CONSUMPTION SUMMARY</div>
            <div className="sc-grid">
              <div className="sc-item">
                <span className="sc-lbl">Tariff Rate</span>
                <span className="sc-val accent">Rs {result.tariff}/kWh</span>
              </div>
              <div className="sc-item">
                <span className="sc-lbl">Daily Usage</span>
                <span className="sc-val">{result.daily_units} kWh</span>
              </div>
              <div className="sc-item">
                <span className="sc-lbl">Monthly Usage</span>
                <span className="sc-val">{result.monthly_units} kWh</span>
              </div>
              <div className="sc-item">
                <span className="sc-lbl">Annual Usage</span>
                <span className="sc-val">{result.annual_units} kWh</span>
              </div>
            </div>
          </div>

          {/* Panel selector tabs */}
          <div className="panel-selector">
            <div className="panel-selector-label">SELECT PANEL TYPE</div>
            <div className="panel-tabs">
              {result.panels.map((p, i) => (
                <button
                  key={i}
                  className={`panel-tab ${activePanel === i ? 'active' : ''}`}
                  onClick={() => setActivePanel(i)}
                >
                  <span className="pt-watt">{p.specs.watt}W</span>
                  <span className="pt-name">Mono PERC</span>
                </button>
              ))}
            </div>
          </div>

          {/* Active panel specs */}
          <div className="solar-specs">
            <div className="solar-specs-title">
              {panel.panel_name} — SPECIFICATIONS
            </div>
            <div className="specs-grid">
              <div className="spec-item">
                <span className="spec-label">Rated Power</span>
                <span className="spec-val">{panel.specs.watt}W</span>
              </div>
              <div className="spec-item">
                <span className="spec-label">Capacity</span>
                <span className="spec-val">{panel.specs.kwp} kWp</span>
              </div>
              <div className="spec-item">
                <span className="spec-label">Panel Area</span>
                <span className="spec-val">{panel.specs.area_m2} m²</span>
              </div>
              <div className="spec-item">
                <span className="spec-label">Efficiency</span>
                <span className="spec-val">{panel.specs.efficiency_pct}%</span>
              </div>
              <div className="spec-item">
                <span className="spec-label">Temp Coeff</span>
                <span className="spec-val">{panel.specs.temp_coeff}%/°C</span>
              </div>
              <div className="spec-item">
                <span className="spec-label">Cost/Watt</span>
                <span className="spec-val">Rs {panel.specs.cost_per_w}</span>
              </div>
            </div>
          </div>

          {/* L5 vs L7 comparison */}
          <div className="solar-cards">
            <div className="solar-card conservative">
              <div className="sc-tag">CONSERVATIVE</div>
              <div className="sc-model">L5 Model</div>
              <div className="sc-panels">
                {L5.n_panels}<span>panels</span>
              </div>
              <div className="sc-kwp">{L5.sys_kwp} kWp</div>
              <div className="sc-divider" />
              <div className="sc-row">
                <span>System Cost</span>
                <span>Rs {L5.sys_cost.toLocaleString()}</span>
              </div>
              <div className="sc-row">
                <span>Monthly Gen</span>
                <span>{L5.avg_gen_mon.toLocaleString()} kWh</span>
              </div>
              <div className="sc-row">
                <span>Monthly Savings</span>
                <span>Rs {L5.sav_mon.toLocaleString()}</span>
              </div>
              <div className="sc-row">
                <span>Annual Savings</span>
                <span>Rs {L5.sav_ann.toLocaleString()}</span>
              </div>
              <div className="sc-row highlight">
                <span>Payback Period</span>
                <span>{L5.payback} yrs</span>
              </div>
              <div className="sc-row">
                <span>Demand Coverage</span>
                <span>{L5.coverage}%</span>
              </div>
              <div className="sc-row">
                <span>Loss Factor</span>
                <span>{L5.loss_pct}%</span>
              </div>
              {L5.area_constrained && (
                <div className="sc-warning">⚠ Area constrained</div>
              )}
            </div>

            <div className="solar-card optimistic">
              <div className="sc-tag">OPTIMISTIC</div>
              <div className="sc-model">L7 Model</div>
              <div className="sc-panels">
                {L7.n_panels}<span>panels</span>
              </div>
              <div className="sc-kwp">{L7.sys_kwp} kWp</div>
              <div className="sc-divider" />
              <div className="sc-row">
                <span>System Cost</span>
                <span>Rs {L7.sys_cost.toLocaleString()}</span>
              </div>
              <div className="sc-row">
                <span>Monthly Gen</span>
                <span>{L7.avg_gen_mon.toLocaleString()} kWh</span>
              </div>
              <div className="sc-row">
                <span>Monthly Savings</span>
                <span>Rs {L7.sav_mon.toLocaleString()}</span>
              </div>
              <div className="sc-row">
                <span>Annual Savings</span>
                <span>Rs {L7.sav_ann.toLocaleString()}</span>
              </div>
              <div className="sc-row highlight">
                <span>Payback Period</span>
                <span>{L7.payback} yrs</span>
              </div>
              <div className="sc-row">
                <span>Demand Coverage</span>
                <span>{L7.coverage}%</span>
              </div>
              <div className="sc-row">
                <span>Loss Factor</span>
                <span>{L7.loss_pct}%</span>
              </div>
              {L7.area_constrained && (
                <div className="sc-warning">⚠ Area constrained</div>
              )}
            </div>
          </div>

          {/* Monthly table */}
          <div className="solar-monthly">
            <div className="solar-monthly-title">
              MONTHLY GENERATION & SAVINGS — {panel.panel_name}
            </div>
            <div className="solar-table-wrap">
              <table className="solar-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>L5 Gen (kWh)</th>
                    <th>L5 Savings</th>
                    <th>L7 Gen (kWh)</th>
                    <th>L7 Savings</th>
                  </tr>
                </thead>
                <tbody>
                  {MONTHS.map((m, i) => (
                    <tr key={m}>
                      <td className="month-col">{m}</td>
                      <td>{L5.monthly_gen[i].toLocaleString()}</td>
                      <td className="save-col">
                        Rs {L5.monthly_savings[i].toLocaleString()}
                      </td>
                      <td>{L7.monthly_gen[i].toLocaleString()}</td>
                      <td className="save-col">
                        Rs {L7.monthly_savings[i].toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td>Annual</td>
                    <td>{L5.ann_gen.toLocaleString()}</td>
                    <td className="save-col">
                      Rs {L5.sav_ann.toLocaleString()}
                    </td>
                    <td>{L7.ann_gen.toLocaleString()}</td>
                    <td className="save-col">
                      Rs {L7.sav_ann.toLocaleString()}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Subsidy note */}
          <div className="subsidy-note">
            <span className="subsidy-icon">ℹ</span>
            <span>{result.subsidy_note}</span>
          </div>

          {/* Reset */}
          <div className="solar-reset-wrap">
            <button className="solar-reset-btn"
              onClick={() => { setResult(null); setBill('') }}>
              ↺ New Calculation
            </button>
          </div>

        </div>
      </div>
    )
  }

  // ── INPUT FORM ──
  return (
    <div className="solar-tab">
      <div className="solar-form">

        <div className="solar-info-row">
          <div className="solar-info-item">
            <span className="solar-info-label">LOCATION</span>
            <span className="solar-info-val">
              {roofResult.lat?.toFixed(4)}, {roofResult.lon?.toFixed(4)}
            </span>
          </div>
          <div className="solar-info-item">
            <span className="solar-info-label">ROOF AREA</span>
            <span className="solar-info-val accent">
              {roofResult.area_m2} m²
            </span>
          </div>
        </div>

        <div className="solar-bill-field">
          <label>MONTHLY ELECTRICITY BILL</label>
          <div className="solar-bill-input-wrap">
            <span className="solar-bill-prefix">Rs</span>
            <input
              type="number"
              placeholder="e.g. 3000"
              value={bill}
              onChange={e => setBill(e.target.value)}
              min="1"
            />
          </div>
        </div>

        <div className="solar-hint">
          ℹ Analysis uses NASA satellite weather data + AI loss models
          (L1–L7). Compares all 3 panel types automatically.<br/>
          Takes approximately 2–4 minutes.
        </div>

        <button
          className="solar-calculate-btn"
          onClick={handleCalculate}
          disabled={!canCalculate}
        >
          <span>☀ CALCULATE SOLAR ROI</span>
        </button>

      </div>
    </div>
  )
}
