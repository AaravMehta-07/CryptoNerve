import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import { COINS, timeAgo, signalColor, signalIcon } from '../utils/formatters'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts'

export default function Predictions() {
  const [coin,    setCoin]    = useState('BTC')
  const [horizon, setHorizon] = useState(4)
  const [data,    setData]    = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      const preds = await api.predictions({ coin, horizon, limit: 50 })
      setData(preds)
      setLoading(false)
    }
    load()
  }, [coin, horizon])

  const resolved = data.filter(d => d.was_correct !== null && d.was_correct !== undefined)
  const correct  = resolved.filter(d => d.was_correct == 1 || d.was_correct === true).length
  const accuracy = resolved.length ? ((correct / resolved.length) * 100).toFixed(1) : '—'

  const byModel = {}
  resolved.forEach(d => {
    if (!byModel[d.model_name]) byModel[d.model_name] = { total: 0, correct: 0 }
    byModel[d.model_name].total++
    if (d.was_correct == 1 || d.was_correct === true) byModel[d.model_name].correct++
  })
  const accChart = Object.entries(byModel).map(([name, v]) => ({
    model: name, accuracy: v.total ? parseFloat((v.correct/v.total*100).toFixed(1)) : 0,
  }))

  const dirColors = { UP: '#00FF9C', DOWN: '#FF4C4C', SIDEWAYS: '#4C9BE8' }

  return (
    <div>
      <div className="page-header">
        <h1>🤖 AI Predictions</h1>
        <p>XGBoost + LSTM + AutoGluon ensemble · Directional price predictions</p>
      </div>

      <div className="flex items-center gap-12 mb-16">
        <div className="pill-tabs">
          {Object.keys(COINS).map(c => (
            <button key={c} className={`pill-tab ${coin===c?'active':''}`} onClick={() => setCoin(c)}>{c}</button>
          ))}
        </div>
        <div style={{ width: 1, height: 20, background: 'var(--border)' }} />
        <div className="pill-tabs">
          {[1, 4, 24].map(h => (
            <button key={h} className={`pill-tab ${horizon===h?'active':''}`} onClick={() => setHorizon(h)}>{h}h</button>
          ))}
        </div>
      </div>

      {/* KPIs */}
      <div className="kpi-grid mb-16">
        <div className="kpi" style={{ '--accent': 'var(--green)' }}>
          <div className="kpi-label">Total Predictions</div>
          <div className="kpi-value" style={{ color: 'var(--green)' }}>{data.length}</div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--blue)' }}>
          <div className="kpi-label">Resolved</div>
          <div className="kpi-value" style={{ color: 'var(--blue)' }}>{resolved.length}</div>
        </div>
        <div className="kpi" style={{ '--accent': resolved.length && accuracy >= 60 ? 'var(--green)' : 'var(--orange)' }}>
          <div className="kpi-label">Accuracy</div>
          <div className="kpi-value" style={{ color: resolved.length && parseFloat(accuracy) >= 60 ? 'var(--green)' : 'var(--orange)' }}>
            {accuracy === '—' ? '—' : `${accuracy}%`}
          </div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--yellow)' }}>
          <div className="kpi-label">Horizon</div>
          <div className="kpi-value" style={{ color: 'var(--yellow)' }}>{horizon}h</div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--purple)' }}>
          <div className="kpi-label">WIN / LOSS</div>
          <div className="kpi-value" style={{ color: 'var(--purple)' }}>{correct} / {resolved.length - correct}</div>
        </div>
      </div>

      <div className="grid-2 mb-16">
        {/* Accuracy by model */}
        <div className="chart-wrap">
          <div className="card-title">Accuracy by Model</div>
          {accChart.length ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={accChart} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#6B7FA3', fontSize: 10 }} />
                <YAxis dataKey="model" type="category" width={80} tick={{ fill: '#A0AABF', fontSize: 9 }} />
                <Tooltip formatter={(v) => [`${v}%`, 'Accuracy']} contentStyle={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8 }} />
                <Bar dataKey="accuracy" radius={[0, 4, 4, 0]}>
                  {accChart.map((entry, i) => (
                    <Cell key={i} fill={entry.accuracy >= 60 ? '#00D4A8' : entry.accuracy >= 50 ? '#FFB830' : '#FF4C4C'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              No resolved predictions yet
            </div>
          )}
        </div>

        {/* Recent predictions */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <div className="card-title" style={{ margin: 0 }}>Recent Predictions</div>
          </div>
          <div style={{ maxHeight: 220, overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Direction</th>
                  <th>Conf</th>
                  <th>Outcome</th>
                  <th>Age</th>
                </tr>
              </thead>
              <tbody>
                {data.slice(0, 20).map((p, i) => {
                  const correct = p.was_correct == 1 || p.was_correct === true
                  const pending = p.was_correct === null || p.was_correct === undefined
                  const dirColor = dirColors[p.predicted_direction] || '#6B7FA3'
                  return (
                    <tr key={i}>
                      <td style={{ fontSize: '0.68rem', color: 'var(--text-2)' }}>{p.model_name?.slice(0,8)}</td>
                      <td style={{ color: dirColor, fontFamily: 'var(--font-mono)', fontSize: '0.72rem', fontWeight: 700 }}>
                        {p.predicted_direction === 'UP' ? '↑' : p.predicted_direction === 'DOWN' ? '↓' : '→'} {p.predicted_direction}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)', fontSize: '0.72rem' }}>
                        {(parseFloat(p.confidence||0)*100).toFixed(0)}%
                      </td>
                      <td>
                        {pending ? (
                          <span style={{ color: 'var(--yellow)', fontSize: '0.68rem' }}>⏳ PENDING</span>
                        ) : correct ? (
                          <span style={{ color: 'var(--green)', fontSize: '0.68rem' }}>✓ WIN</span>
                        ) : (
                          <span style={{ color: 'var(--red)', fontSize: '0.68rem' }}>✗ LOSS</span>
                        )}
                      </td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>{timeAgo(p.predicted_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
