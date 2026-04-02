import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend
} from 'recharts'

const fmtPct = v => { const n = parseFloat(v || 0); return n > 0 ? `${(n*100).toFixed(1)}%` : '—' }
const fmtNum = v => { const n = parseFloat(v || 0); return n > 0 ? n.toFixed(2) : '—' }

export default function Performance() {
  const [data, setData] = useState([])

  useEffect(() => {
    api.modelAccuracy().then(setData).catch(console.error)
  }, [])

  const coins  = [...new Set(data.map(d => d.coin))]
  const models = [...new Set(data.map(d => d.model_name))]

  // Group by coin — average accuracy per model across horizons
  const barData = coins.map(c => {
    const row = { coin: c }
    models.forEach(m => {
      const entries = data.filter(d => d.coin === c && d.model_name === m)
      if (entries.length) {
        row[m] = entries.reduce((s, d) => s + parseFloat(d.accuracy || 0), 0) / entries.length
      }
    })
    return row
  })

  const MODEL_COLORS = ['#00D4A8', '#FF6B35', '#4C9BE8', '#FFB830', '#8B5CF6']

  const overallAcc = data.length
    ? (data.reduce((s, d) => s + parseFloat(d.accuracy || 0), 0) / data.length * 100).toFixed(1)
    : '—'

  const bestModel = data.reduce((best, d) => (!best || parseFloat(d.accuracy) > parseFloat(best.accuracy)) ? d : best, null)

  // Radar: average accuracy per model
  const radarData = ['Accuracy'].map(metric => {
    const row = { metric }
    models.forEach(m => {
      const entries = data.filter(d => d.model_name === m)
      row[m] = entries.length ? entries.reduce((s, d) => s + parseFloat(d.accuracy || 0), 0) / entries.length : 0
    })
    return row
  })

  // Sort data by accuracy descending for the table
  const sortedData = [...data].sort((a, b) => parseFloat(b.accuracy || 0) - parseFloat(a.accuracy || 0))

  return (
    <div>
      <div className="page-header">
        <h1>🎯 Model Performance</h1>
        <p>XGBoost · LSTM · AutoGluon ensemble — real validation accuracy from trained models</p>
      </div>

      {/* KPIs */}
      <div className="kpi-grid mb-16">
        <div className="kpi" style={{ '--accent': 'var(--green)' }}>
          <div className="kpi-label">Avg Accuracy</div>
          <div className="kpi-value" style={{ color: 'var(--green)' }}>{overallAcc !== '—' ? `${overallAcc}%` : '—'}</div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--blue)' }}>
          <div className="kpi-label">Models Tracked</div>
          <div className="kpi-value" style={{ color: 'var(--blue)' }}>{models.length}</div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--orange)' }}>
          <div className="kpi-label">Best Model</div>
          <div className="kpi-value" style={{ color: 'var(--orange)', fontSize: '1rem' }}>
            {bestModel?.model_name || '—'}
          </div>
          {bestModel && <div className="kpi-sub">{bestModel.coin} {bestModel.horizon_h || ''}h — {(parseFloat(bestModel.accuracy)*100).toFixed(1)}% acc</div>}
        </div>
        <div className="kpi" style={{ '--accent': 'var(--purple)' }}>
          <div className="kpi-label">Coin Coverage</div>
          <div className="kpi-value" style={{ color: 'var(--purple)' }}>{coins.length}</div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--yellow)' }}>
          <div className="kpi-label">Total Evaluations</div>
          <div className="kpi-value" style={{ color: 'var(--yellow)' }}>{data.length}</div>
        </div>
      </div>

      <div className="grid-2 mb-16">
        {/* Accuracy by Coin + Model */}
        <div className="chart-wrap">
          <div className="card-title">Avg Accuracy by Coin & Model</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
              <XAxis dataKey="coin" tick={{ fill: '#A0AABF', fontSize: 11 }} />
              <YAxis domain={[0.4, 0.75]} tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fill: '#6B7FA3', fontSize: 9 }} />
              <Tooltip formatter={(v) => [`${(v*100).toFixed(1)}%`, '']} contentStyle={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8, fontSize: '0.75rem' }} />
              <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#A0AABF' }} />
              {models.map((m, i) => (
                <Bar key={m} dataKey={m} fill={MODEL_COLORS[i % MODEL_COLORS.length]} radius={[3,3,0,0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Model accuracy table */}
        <div className="chart-wrap">
          <div className="card-title">Model Validation Results (All Horizons)</div>
          <div style={{ overflowX: 'auto', maxHeight: 320, overflowY: 'auto' }}>
            <table className="data-table" style={{ fontSize: '0.72rem' }}>
              <thead>
                <tr>
                  <th>Coin</th>
                  <th>Model</th>
                  <th>Horizon</th>
                  <th>Val Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {sortedData.map((d, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--text-2)', fontWeight: 600 }}>{d.coin}</td>
                    <td style={{ color: 'var(--text-2)', fontWeight: 500 }}>{d.model_name}</td>
                    <td className="mono" style={{ color: 'var(--text-muted)' }}>{d.horizon_h || '1'}h</td>
                    <td style={{ color: parseFloat(d.accuracy) >= 0.6 ? 'var(--green)' : parseFloat(d.accuracy) >= 0.55 ? 'var(--orange)' : 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      {(parseFloat(d.accuracy||0)*100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
