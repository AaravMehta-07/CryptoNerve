import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend
} from 'recharts'

export default function Performance() {
  const [data, setData] = useState([])

  useEffect(() => {
    api.modelAccuracy().then(setData).catch(console.error)
  }, [])

  // Group by coin for multi-series bar
  const coins  = [...new Set(data.map(d => d.coin))]
  const models = [...new Set(data.map(d => d.model_name))]

  const barData = coins.map(c => {
    const row = { coin: c }
    data.filter(d => d.coin === c).forEach(d => {
      row[d.model_name] = parseFloat(d.accuracy || 0)
    })
    return row
  })

  const MODEL_COLORS = ['#00D4A8', '#FF6B35', '#4C9BE8', '#FFB830', '#8B5CF6']

  const overallAcc = data.length
    ? (data.reduce((s, d) => s + parseFloat(d.accuracy || 0), 0) / data.length * 100).toFixed(1)
    : '—'

  const bestModel = data.reduce((best, d) => (!best || parseFloat(d.accuracy) > parseFloat(best.accuracy)) ? d : best, null)

  // Radar data per model (average across coins)
  const radarData = models.map(m => {
    const rows = data.filter(d => d.model_name === m)
    const avg = k => rows.length ? rows.reduce((s, d) => s + parseFloat(d[k] || 0), 0) / rows.length : 0
    return {
      subject: m.slice(0, 10),
      accuracy: avg('accuracy'),
      precision: avg('precision'),
      recall: avg('recall'),
      f1: avg('f1_score'),
      sharpe: Math.min(avg('sharpe') / 3, 1), // normalize
    }
  })

  return (
    <div>
      <div className="page-header">
        <h1>🎯 Model Performance</h1>
        <p>XGBoost · LSTM · AutoGluon ensemble accuracy metrics</p>
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
            {bestModel?.model_name?.slice(0, 10) || '—'}
          </div>
          {bestModel && <div className="kpi-sub">{(parseFloat(bestModel.accuracy)*100).toFixed(1)}% acc</div>}
        </div>
        <div className="kpi" style={{ '--accent': 'var(--purple)' }}>
          <div className="kpi-label">Coin Coverage</div>
          <div className="kpi-value" style={{ color: 'var(--purple)' }}>{coins.length}</div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--yellow)' }}>
          <div className="kpi-label">Records</div>
          <div className="kpi-value" style={{ color: 'var(--yellow)' }}>{data.length}</div>
        </div>
      </div>

      <div className="grid-2 mb-16">
        {/* Accuracy by Coin + Model */}
        <div className="chart-wrap">
          <div className="card-title">Accuracy by Coin & Model</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
              <XAxis dataKey="coin" tick={{ fill: '#A0AABF', fontSize: 11 }} />
              <YAxis domain={[0, 1]} tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fill: '#6B7FA3', fontSize: 9 }} />
              <Tooltip formatter={(v) => [`${(v*100).toFixed(1)}%`, '']} contentStyle={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#A0AABF' }} />
              {models.map((m, i) => (
                <Bar key={m} dataKey={m} fill={MODEL_COLORS[i % MODEL_COLORS.length]} radius={[3,3,0,0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Model radar */}
        <div className="chart-wrap">
          <div className="card-title">Multi-metric Radar Comparison</div>
          {radarData.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={[{ subject: 'Accuracy', val: 0.7 }]}>
                <PolarGrid stroke="#1A2840" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: '#A0AABF', fontSize: 9 }} />
                <PolarRadiusAxis angle={90} domain={[0,1]} tick={{ fill: '#6B7FA3', fontSize: 8 }} />
              </RadarChart>
            </ResponsiveContainer>
          ) : null}
          {/* Simplified: just show metrics table */}
          <div style={{ overflowX: 'auto', marginTop: 8 }}>
            <table className="data-table" style={{ fontSize: '0.72rem' }}>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Accuracy</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1</th>
                  <th>Sharpe</th>
                </tr>
              </thead>
              <tbody>
                {data.map((d, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--text-2)', fontWeight: 500 }}>{d.model_name}</td>
                    <td style={{ color: parseFloat(d.accuracy) >= 0.6 ? 'var(--green)' : 'var(--orange)', fontFamily: 'var(--font-mono)' }}>
                      {(parseFloat(d.accuracy||0)*100).toFixed(1)}%
                    </td>
                    <td className="mono">{(parseFloat(d.precision||0)*100).toFixed(1)}%</td>
                    <td className="mono">{(parseFloat(d.recall||0)*100).toFixed(1)}%</td>
                    <td className="mono">{(parseFloat(d.f1_score||0)*100).toFixed(1)}%</td>
                    <td className="mono" style={{ color: parseFloat(d.sharpe||0) > 1 ? 'var(--green)' : 'var(--text-muted)' }}>
                      {parseFloat(d.sharpe||0).toFixed(2)}
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
