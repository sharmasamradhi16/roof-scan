import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"]

// Colors matching L2 Warm Cream Terracotta theme
const COLOR = {
  accent:    [194, 65,  12],   // terracotta
  accent2:   [21,  128, 61],   // green
  text:      [28,  20,  16],   // dark brown
  muted:     [156, 132, 114],  // warm grey
  surface:   [243, 237, 227],  // cream
  surface2:  [235, 226, 212],  // darker cream
  border:    [221, 208, 188],  // border
  white:     [255, 255, 255],
  warning:   [146, 64,  14],   // amber dark
  warnbg:    [255, 248, 240],  // amber light bg
}

function addPageBorder(doc) {
  doc.setDrawColor(...COLOR.border)
  doc.setLineWidth(0.3)
  doc.rect(8, 8, doc.internal.pageSize.width - 16, doc.internal.pageSize.height - 16)
}

function addHeader(doc, pageNum) {
  const W = doc.internal.pageSize.width

  // Top bar
  doc.setFillColor(...COLOR.surface)
  doc.rect(0, 0, W, 22, 'F')
  doc.setDrawColor(...COLOR.border)
  doc.setLineWidth(0.3)
  doc.line(0, 22, W, 22)

  // Logo
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(14)
  doc.setTextColor(...COLOR.accent)
  doc.text('ROOF', 14, 14)
  const roofW = doc.getTextWidth('ROOF')
  doc.setTextColor(...COLOR.muted)
  doc.text('SCAN', 14 + roofW, 14)

  // Tagline
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(7)
  doc.setTextColor(...COLOR.muted)
  doc.text('SATELLITE ROOFTOP AREA ESTIMATOR', W - 14, 10, { align: 'right' })
  doc.text('SOLAR ROI ANALYSIS REPORT', W - 14, 16, { align: 'right' })

  // Page number (except page 1)
  if (pageNum > 1) {
    doc.setFontSize(7)
    doc.setTextColor(...COLOR.muted)
    doc.text(`Page ${pageNum}`, W / 2, 17, { align: 'center' })
  }
}

function addFooter(doc) {
  const W = doc.internal.pageSize.width
  const H = doc.internal.pageSize.height

  doc.setFillColor(...COLOR.surface2)
  doc.rect(0, H - 12, W, 12, 'F')
  doc.setDrawColor(...COLOR.border)
  doc.line(0, H - 12, W, H - 12)

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(6.5)
  doc.setTextColor(...COLOR.muted)
  doc.text('MaskDINO · Detectron2 · NASA POWER · pvlib · Web Mercator (WGS84)', 14, H - 4)
  doc.text(`Generated: ${new Date().toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' })}`, W - 14, H - 4, { align: 'right' })
}

function sectionTitle(doc, y, title) {
  const W = doc.internal.pageSize.width
  doc.setFillColor(...COLOR.accent)
  doc.rect(14, y, W - 28, 7, 'F')
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(8)
  doc.setTextColor(...COLOR.white)
  doc.text(title.toUpperCase(), 18, y + 4.8)
  return y + 12
}

function infoBox(doc, x, y, w, h, label, value, valueColor) {
  doc.setFillColor(...COLOR.surface)
  doc.setDrawColor(...COLOR.border)
  doc.setLineWidth(0.2)
  doc.roundedRect(x, y, w, h, 2, 2, 'FD')

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(6.5)
  doc.setTextColor(...COLOR.muted)
  doc.text(label.toUpperCase(), x + 4, y + 5)

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9)
  doc.setTextColor(...(valueColor || COLOR.text))
  doc.text(String(value), x + 4, y + 11)
}

export function generateSolarPDF(result) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const W   = doc.internal.pageSize.width
  let   y   = 28

  // ── PAGE 1 ────────────────────────────────────────────────
  addPageBorder(doc)
  addHeader(doc, 1)
  addFooter(doc)

  // Report title
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(18)
  doc.setTextColor(...COLOR.accent)
  doc.text('Solar ROI Analysis Report', W / 2, y + 6, { align: 'center' })

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  doc.setTextColor(...COLOR.muted)
  doc.text(`Prepared for coordinates: ${result.lat.toFixed(6)}°N, ${result.lon.toFixed(6)}°E`, W / 2, y + 13, { align: 'center' })
  y += 22

  // ── SECTION 1: Location & Roof ──
  y = sectionTitle(doc, y, '1. Location & Roof Details')

  const boxW = (W - 28 - 9) / 4
  infoBox(doc, 14,           y, boxW, 18, 'Latitude',    `${result.lat.toFixed(6)}°`)
  infoBox(doc, 14 + boxW + 3, y, boxW, 18, 'Longitude', `${result.lon.toFixed(6)}°`)
  infoBox(doc, 14 + (boxW+3)*2, y, boxW, 18, 'Roof Area', `${result.area_m2} m²`, COLOR.accent)
  infoBox(doc, 14 + (boxW+3)*3, y, boxW, 18, 'Data Year', '2024')
  y += 24

  // ── SECTION 2: Consumption ──
  y = sectionTitle(doc, y, '2. Electricity Consumption')

  const bW2 = (W - 28 - 12) / 4
  infoBox(doc, 14,              y, bW2, 18, 'Monthly Bill',  `Rs ${result.monthly_bill.toLocaleString()}`)
  infoBox(doc, 14 + bW2 + 4,   y, bW2, 18, 'Tariff Rate',   `Rs ${result.tariff}/kWh`, COLOR.accent)
  infoBox(doc, 14 + (bW2+4)*2, y, bW2, 18, 'Monthly Usage', `${result.monthly_units} kWh`)
  infoBox(doc, 14 + (bW2+4)*3, y, bW2, 18, 'Annual Usage',  `${result.annual_units} kWh`)
  y += 24

  // ── SECTION 3: Panel Comparison (all 3 panels) ──
  y = sectionTitle(doc, y, '3. Panel Comparison Summary')

  // Table: all panels, L5+L7 side by side
  const panelRows = result.panels.map(p => [
    p.panel_name,
    `${p.specs.watt}W`,
    `${p.specs.efficiency_pct}%`,
    `Rs ${p.specs.cost_per_w}/W`,
    // L5
    `${p.L5.n_panels}`,
    `${p.L5.sys_kwp} kWp`,
    `Rs ${p.L5.sys_cost.toLocaleString()}`,
    `${p.L5.payback} yrs`,
    // L7
    `${p.L7.n_panels}`,
    `${p.L7.sys_kwp} kWp`,
    `Rs ${p.L7.sys_cost.toLocaleString()}`,
    `${p.L7.payback} yrs`,
  ])

  autoTable(doc, {
    startY: y,
    head: [[
      { content: 'Panel', rowSpan: 2 },
      { content: 'Watt', rowSpan: 2 },
      { content: 'Eff.', rowSpan: 2 },
      { content: 'Cost/W', rowSpan: 2 },
      { content: 'Conservative (L5)', colSpan: 4 },
      { content: 'Optimistic (L7)', colSpan: 4 },
    ],[
      'Panels','kWp','Cost','Payback',
      'Panels','kWp','Cost','Payback',
    ]],
    body: panelRows,
    margin: { left: 14, right: 14 },
    styles: {
      fontSize: 7.5,
      cellPadding: 2.5,
      font: 'helvetica',
      textColor: COLOR.text,
      lineColor: COLOR.border,
      lineWidth: 0.2,
    },
    headStyles: {
      fillColor: COLOR.surface2,
      textColor: COLOR.accent,
      fontStyle: 'bold',
      fontSize: 7,
    },
    alternateRowStyles: { fillColor: COLOR.surface },
    columnStyles: {
      0: { cellWidth: 32 },
      4: { textColor: COLOR.accent, fontStyle: 'bold' },
      8: { textColor: COLOR.accent2, fontStyle: 'bold' },
    },
  })

  y = doc.lastAutoTable.finalY + 10

  // ── SECTION 4: AI Loss Models ──
  if (y > 220) {
    doc.addPage()
    addPageBorder(doc)
    addHeader(doc, 2)
    addFooter(doc)
    y = 30
  }

  y = sectionTitle(doc, y, '4. AI Loss Model Summary')

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  doc.setTextColor(...COLOR.text)

  const lossDesc = [
    ['L1', 'SAPM', 'Sandia Array Performance Model — physics-based IV curve model'],
    ['L2', 'CEC Single-Diode', 'California Energy Commission single-diode equivalent circuit'],
    ['L3', 'SAM-Style', 'SAM engineering model — soiling, temp, humidity, fixed losses'],
    ['L4', 'PVWatts', 'NREL PVWatts flat 14.1% baseline reference'],
    ['L5', 'Encoder-Decoder (AI)', 'Neural network consensus of L1+L2+L3 — CONSERVATIVE sizing'],
    ['L6', 'Physics Formula', 'Physics-guided coupling of soiling, temp and humidity losses'],
    ['L7', 'Physics AI (ED)', 'Physics encoder-decoder on environmental features — OPTIMISTIC sizing'],
  ]

  autoTable(doc, {
    startY: y,
    head: [['Model', 'Method', 'Description']],
    body: lossDesc,
    margin: { left: 14, right: 14 },
    styles: {
      fontSize: 7.5,
      cellPadding: 2.5,
      textColor: COLOR.text,
      lineColor: COLOR.border,
      lineWidth: 0.2,
    },
    headStyles: { fillColor: COLOR.surface2, textColor: COLOR.accent, fontStyle: 'bold', fontSize: 7 },
    alternateRowStyles: { fillColor: COLOR.surface },
    columnStyles: {
      0: { cellWidth: 12, fontStyle: 'bold', textColor: COLOR.accent },
      1: { cellWidth: 38 },
    },
  })

  y = doc.lastAutoTable.finalY + 10

  // ── PAGES 3+: One page per panel ──
  result.panels.forEach((panel, pi) => {
    doc.addPage()
    addPageBorder(doc)
    addHeader(doc, 3 + pi)
    addFooter(doc)
    y = 30

    // Panel header
    doc.setFillColor(...COLOR.surface2)
    doc.roundedRect(14, y, W - 28, 14, 3, 3, 'F')
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(13)
    doc.setTextColor(...COLOR.accent)
    doc.text(`Panel ${pi + 1}: ${panel.panel_name}`, 20, y + 9)
    y += 20

    // Panel specs row
    const sW = (W - 28 - 15) / 6
    const specItems = [
      ['Rated Power',   `${panel.specs.watt}W`],
      ['Capacity',      `${panel.specs.kwp} kWp`],
      ['Panel Area',    `${panel.specs.area_m2} m²`],
      ['Efficiency',    `${panel.specs.efficiency_pct}%`],
      ['Temp Coeff',    `${panel.specs.temp_coeff}%/°C`],
      ['Cost/Watt',     `Rs ${panel.specs.cost_per_w}`],
    ]
    specItems.forEach((s, i) => {
      infoBox(doc, 14 + i * (sW + 3), y, sW, 16, s[0], s[1], COLOR.accent)
    })
    y += 22

    // L5 vs L7 side-by-side
    const halfW = (W - 28 - 4) / 2

    // L5 block
    doc.setFillColor(...COLOR.surface)
    doc.setDrawColor(...COLOR.border)
    doc.setLineWidth(0.3)
    doc.roundedRect(14, y, halfW, 62, 3, 3, 'FD')

    doc.setFillColor(...COLOR.accent)
    doc.roundedRect(14, y, halfW, 10, 3, 3, 'F')
    doc.rect(14, y + 7, halfW, 3, 'F')
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8)
    doc.setTextColor(...COLOR.white)
    doc.text('CONSERVATIVE — L5 Model', 18, y + 6.5)

    const l5Items = [
      ['Number of Panels',   `${panel.L5.n_panels} panels`],
      ['System Size',        `${panel.L5.sys_kwp} kWp`],
      ['System Cost',        `Rs ${panel.L5.sys_cost.toLocaleString()}`],
      ['Loss Factor',        `${panel.L5.loss_pct}%`],
      ['Monthly Generation', `${panel.L5.avg_gen_mon.toLocaleString()} kWh`],
      ['Monthly Savings',    `Rs ${panel.L5.sav_mon.toLocaleString()}`],
      ['Annual Savings',     `Rs ${panel.L5.sav_ann.toLocaleString()}`],
      ['Demand Coverage',    `${panel.L5.coverage}%`],
      ['Payback Period',     `${panel.L5.payback} years`],
    ]

    let iy = y + 14
    l5Items.forEach(item => {
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7.5)
      doc.setTextColor(...COLOR.muted)
      doc.text(item[0], 18, iy)
      doc.setFont('helvetica', 'bold')
      doc.setTextColor(item[0] === 'Payback Period' ? COLOR.accent[0] : COLOR.text[0],
                       item[0] === 'Payback Period' ? COLOR.accent[1] : COLOR.text[1],
                       item[0] === 'Payback Period' ? COLOR.accent[2] : COLOR.text[2])
      doc.text(item[1], 14 + halfW - 4, iy, { align: 'right' })
      iy += 5.5
    })

    // L7 block
    const l7x = 14 + halfW + 4
    doc.setFillColor(255, 248, 245)
    doc.setDrawColor(...COLOR.border)
    doc.roundedRect(l7x, y, halfW, 62, 3, 3, 'FD')

    doc.setFillColor(...COLOR.accent2)
    doc.roundedRect(l7x, y, halfW, 10, 3, 3, 'F')
    doc.rect(l7x, y + 7, halfW, 3, 'F')
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8)
    doc.setTextColor(...COLOR.white)
    doc.text('OPTIMISTIC — L7 Model', l7x + 4, y + 6.5)

    const l7Items = [
      ['Number of Panels',   `${panel.L7.n_panels} panels`],
      ['System Size',        `${panel.L7.sys_kwp} kWp`],
      ['System Cost',        `Rs ${panel.L7.sys_cost.toLocaleString()}`],
      ['Loss Factor',        `${panel.L7.loss_pct}%`],
      ['Monthly Generation', `${panel.L7.avg_gen_mon.toLocaleString()} kWh`],
      ['Monthly Savings',    `Rs ${panel.L7.sav_mon.toLocaleString()}`],
      ['Annual Savings',     `Rs ${panel.L7.sav_ann.toLocaleString()}`],
      ['Demand Coverage',    `${panel.L7.coverage}%`],
      ['Payback Period',     `${panel.L7.payback} years`],
    ]

    iy = y + 14
    l7Items.forEach(item => {
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7.5)
      doc.setTextColor(...COLOR.muted)
      doc.text(item[0], l7x + 4, iy)
      doc.setFont('helvetica', 'bold')
      doc.setTextColor(item[0] === 'Payback Period' ? COLOR.accent2[0] : COLOR.text[0],
                       item[0] === 'Payback Period' ? COLOR.accent2[1] : COLOR.text[1],
                       item[0] === 'Payback Period' ? COLOR.accent2[2] : COLOR.text[2])
      doc.text(item[1], l7x + halfW - 4, iy, { align: 'right' })
      iy += 5.5
    })

    y += 68

    if (panel.L5.area_constrained || panel.L7.area_constrained) {
      doc.setFillColor(255, 248, 240)
      doc.setDrawColor(245, 196, 154)
      doc.setLineWidth(0.3)
      doc.roundedRect(14, y, W - 28, 8, 2, 2, 'FD')
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(7.5)
      doc.setTextColor(...COLOR.warning)
      doc.text('⚠  System is area-constrained — roof area is insufficient for full demand coverage.', 18, y + 5)
      y += 12
    }

    // Monthly table for this panel
    y = sectionTitle(doc, y, `Monthly Generation & Savings — ${panel.panel_name}`)

    const monthRows = MONTHS.map((m, i) => [
      m,
      panel.L5.monthly_gen[i].toLocaleString(),
      `Rs ${panel.L5.monthly_savings[i].toLocaleString()}`,
      panel.L7.monthly_gen[i].toLocaleString(),
      `Rs ${panel.L7.monthly_savings[i].toLocaleString()}`,
    ])

    monthRows.push([
      'ANNUAL TOTAL',
      panel.L5.ann_gen.toLocaleString(),
      `Rs ${panel.L5.sav_ann.toLocaleString()}`,
      panel.L7.ann_gen.toLocaleString(),
      `Rs ${panel.L7.sav_ann.toLocaleString()}`,
    ])

    autoTable(doc, {
      startY: y,
      head: [[
        'Month',
        'L5 Generation (kWh)',
        'L5 Savings (Rs)',
        'L7 Generation (kWh)',
        'L7 Savings (Rs)',
      ]],
      body: monthRows,
      margin: { left: 14, right: 14 },
      styles: {
        fontSize: 8,
        cellPadding: 2.5,
        textColor: COLOR.text,
        lineColor: COLOR.border,
        lineWidth: 0.2,
        halign: 'right',
      },
      headStyles: {
        fillColor: COLOR.surface2,
        textColor: COLOR.accent,
        fontStyle: 'bold',
        fontSize: 7.5,
        halign: 'center',
      },
      alternateRowStyles: { fillColor: COLOR.surface },
      columnStyles: {
        0: { halign: 'left', fontStyle: 'bold', textColor: COLOR.muted },
        2: { textColor: COLOR.accent2 },
        4: { textColor: COLOR.accent2 },
      },
      didParseCell: (data) => {
        if (data.row.index === 12) {
          data.cell.styles.fontStyle = 'bold'
          data.cell.styles.fillColor = COLOR.surface2
          data.cell.styles.textColor = COLOR.accent
        }
      },
    })
  })

  // ── LAST PAGE: Disclaimer ──
  doc.addPage()
  addPageBorder(doc)
  addHeader(doc, 3 + result.panels.length)
  addFooter(doc)
  y = 30

  y = sectionTitle(doc, y, 'Important Notes & Disclaimer')

  const notes = [
    ['Tariff Rate', `A fixed tariff of Rs ${result.tariff}/kWh has been used for all savings calculations.`],
    ['Government Subsidy', 'Payback period calculations DO NOT include government subsidies. Actual payback will be significantly shorter once applicable subsidies are applied. Please consult your local DISCOM or government portal for current subsidy schemes.'],
    ['Loss Models', 'L5 (Conservative) uses an AI encoder-decoder trained on SAPM, CEC, and SAM models. L7 (Optimistic) uses a physics-guided AI encoder-decoder on environmental features. Both models are trained on NASA POWER 2024 hourly data for your specific location.'],
    ['Peak Sizing', 'System sizing is based on the PEAK monthly solar yield (best month) to ensure the system meets demand even in the most productive period.'],
    ['Roof Area', `An 80% usable area factor is applied to the detected roof area of ${result.area_m2} m². Each panel occupies 3 m² of roof space.`],
    ['Weather Data', 'Solar irradiance, temperature, wind speed, humidity, and precipitation data are sourced from NASA POWER API for the year 2024.'],
    ['Accuracy', 'This report provides estimates for planning purposes. Actual generation may vary depending on shading, panel orientation, installation quality, and local weather conditions.'],
  ]

  notes.forEach(([title, body]) => {
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8)
    doc.setTextColor(...COLOR.accent)
    doc.text(`• ${title}`, 18, y)
    y += 5

    const lines = doc.splitTextToSize(body, W - 36)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)
    doc.setTextColor(...COLOR.text)
    doc.text(lines, 22, y)
    y += lines.length * 4.5 + 4
  })

  // Subsidy highlight box
  y += 4
  doc.setFillColor(255, 248, 240)
  doc.setDrawColor(245, 196, 154)
  doc.setLineWidth(0.4)
  doc.roundedRect(14, y, W - 28, 16, 3, 3, 'FD')
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(8.5)
  doc.setTextColor(...COLOR.warning)
  doc.text('⚠  SUBSIDY DISCLAIMER', 20, y + 6)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(7.5)
  const subLines = doc.splitTextToSize(
    'The payback periods shown in this report are calculated WITHOUT government subsidy. Actual payback will be shorter once subsidy is applied. Check with your local electricity board for current subsidy rates.',
    W - 40
  )
  doc.text(subLines, 20, y + 11)

  // Save
  const fname = `RoofScan_Solar_Report_${result.lat.toFixed(4)}_${result.lon.toFixed(4)}.pdf`
  doc.save(fname)
}
