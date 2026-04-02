import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import { COINS, timeAgo, signalColor, signalIcon } from '../utils/formatters'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, LabelList
} from 'recharts'

const MIN_CONFIDENCE = 0.55 // Only trade when confidence > 55%

// Shorten model names for display
function shortModel(name) {
  if (!name) return '—'
  if (name.includes('ollama')) return 'Ollama+ML'
  if (name.includes('sentiment_ensemble')) return 'Sentiment'
  if (name.includes('xgboost')) return 'XGBoost'
  if (name.includes('lstm')) return 'LSTM'
  if (name.includes('autogluon')) return 'AutoGluon'
  return name.slice(0, 12)
}

export default function Predictions() {
  const [coin,       setCoin]       = useState('BTC')
  const [horizon,    setHorizon]    = useState(4)
  const [data,       setData]       = useState([])
  const [modelAcc,   setModelAcc]   = useState([])
  const [loading,    setLoading]    = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      const [preds, acc] = await Promise.all([
        api.predictions({ coin, horizon, limit: 50 }),
        api.modelAccuracy()
      ])
      setData(preds)
      setModelAcc(acc)
      setLoading(false)
    }
    load()
  }, [coin, horizon])

  // All predictions
  const resolved = data.filter(d => d.was_correct !== null && d.was_correct !== undefined)
  const correct  = resolved.filter(d => d.was_correct == 1 || d.was_correct === true).length
  const rawAccuracy = resolved.length ? ((correct / resolved.length) * 100).toFixed(1) : '—'

  // Confidence-gated predictions (only high-confidence trades)
  const gatedAll      = data.filter(d => parseFloat(d.confidence || 0) >= MIN_CONFIDENCE)
  const gatedResolved = gatedAll.filter(d => d.was_correct !== null && d.was_correct !== undefined)
  const gatedCorrect  = gatedResolved.filter(d => d.was_correct == 1 || d.was_correct === true).length
  const gatedAccuracy = gatedResolved.length ? ((gatedCorrect / gatedResolved.length) * 100).toFixed(1) : '—'

  // Accuracy by model
  const byModel = {}
  resolved.forEach(d => {
    const key = shortModel(d.model_name)
    if (!byModel[key]) byModel[key] = { total: 0, correct: 0 }
    byModel[key].total++
    if (d.was_correct == 1 || d.was_correct === true) byModel[key].correct++
  })
  const accChart = Object.entries(byModel).map(([name, v]) => ({
    model: name,
    accuracy: v.total ? parseFloat((v.correct/v.total*100).toFixed(1)) : 0,
    total: v.total,
  }))

  // If no resolved, show "not enough data" chart placeholder with model names
  const pendingModels = {}
  data.forEach(d => {
    const key = shortModel(d.model_name)
    if (!pendingModels[key]) pendingModels[key] = { total: 0, pending: 0 }
    pendingModels[key].total++
    if (d.was_correct === null || d.was_correct === undefined) pendingModels[key].pending++
  })

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
          <div className="kpi-label">High-Conf Trades</div>
          <div className="kpi-value" style={{ color: 'var(--blue)' }}>
            {gatedAll.length}
            <span style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginLeft: 4 }}>(&gt;{(MIN_CONFIDENCE*100).toFixed(0)}% conf)</span>
          </div>
        </div>
        <div className="kpi" style={{ '--accent': gatedResolved.length && parseFloat(gatedAccuracy) >= 55 ? 'var(--green)' : 'var(--orange)' }}>
          <div className="kpi-label">Gated Win Rate</div>
          <div className="kpi-value" style={{ color: gatedResolved.length && parseFloat(gatedAccuracy) >= 55 ? 'var(--green)' : 'var(--orange)' }}>
            {gatedAccuracy === '—' ? '—' : `${gatedAccuracy}%`}
          </div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--yellow)' }}>
          <div className="kpi-label">Horizon</div>
          <div className="kpi-value" style={{ color: 'var(--yellow)' }}>{horizon}h</div>
        </div>
        <div className="kpi" style={{ '--accent': 'var(--purple)' }}>
          <div className="kpi-label">WIN / LOSS</div>
          <div className="kpi-value" style={{ color: 'var(--purple)' }}>
            {gatedCorrect} / {gatedResolved.length - gatedCorrect}
            {resolved.length > gatedResolved.length && (
              <span style={{ fontSize: '0.5rem', color: 'var(--text-muted)', display: 'block' }}>
                {resolved.length - gatedResolved.length} skipped (low conf)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Confidence Gating info bar */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderLeft: '3px solid #4C9BE8', borderRadius: 8,
        padding: '10px 16px', marginBottom: 16,
        fontSize: '0.72rem', color: 'var(--text-2)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ fontSize: '1rem' }}>🎯</span>
        <span>
          <strong style={{ color: '#4C9BE8' }}>Confidence Gating Active</strong> — Only trading when model confidence &gt; {(MIN_CONFIDENCE*100).toFixed(0)}%.
          {' '}Lower-confidence predictions are skipped to improve win rate.
          {gatedAll.length < data.length && (
            <span style={{ color: 'var(--text-muted)' }}>
              {' '}({data.length - gatedAll.length} predictions filtered out)
            </span>
          )}
        </span>
      </div>

      <div className="grid-2 mb-16">
        {/* Model validation accuracy (from training) */}
        <div className="chart-wrap">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div className="card-title" style={{ margin: 0 }}>Model Validation Accuracy</div>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', background: 'var(--bg)', padding: '3px 8px', borderRadius: 4, border: '1px solid var(--border)' }}>
              {coin} · {horizon}h horizon
            </span>
          </div>
          {(() => {
            const filtered = modelAcc.filter(m =>
              m.coin === coin && parseInt(m.horizon_h) === horizon
            ).map(m => ({
              model: m.model_name,
              accuracy: parseFloat((parseFloat(m.accuracy) * 100).toFixed(1)),
            })).sort((a, b) => b.accuracy - a.accuracy)
            
            if (!filtered.length) {
              return (
                <div style={{ height: 180, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                  No trained models for {coin} {horizon}h
                </div>
              )
            }

            const best = Math.max(...filtered.map(f => f.accuracy))
            
            const renderLabel = (props) => {
              const { x, y, width, height, value } = props
              return (
                <text
                  x={x + width + 6}
                  y={y + height / 2}
                  fill="#E8EDF3"
                  fontSize={12}
                  fontWeight={700}
                  fontFamily="var(--font-mono)"
                  dominantBaseline="central"
                >
                  {value}%
                </text>
              )
            }
            
            return (
              <div>
                <ResponsiveContainer width="100%" height={filtered.length * 44 + 35}>
                  <BarChart data={filtered} layout="vertical" margin={{ top: 5, right: 55, left: 5, bottom: 5 }}>
                    <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="#1A284033" />
                    <XAxis type="number" domain={[0, 100]} tick={{ fill: '#6B7FA3', fontSize: 9 }} tickCount={5} axisLine={false} />
                    <YAxis
                      dataKey="model" type="category" width={72}
                      tick={{ fill: '#C8D6E5', fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-mono)' }}
                      axisLine={false} tickLine={false}
                    />
                    <Tooltip
                      formatter={(v) => [`${v}%`, 'Validation Accuracy']}
                      contentStyle={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8, fontSize: '0.75rem' }}
                      cursor={{ fill: '#ffffff08' }}
                    />
                    <Bar dataKey="accuracy" radius={[0, 6, 6, 0]} barSize={24}>
                      {filtered.map((entry, i) => (
                        <Cell
                          key={i}
                          fill={entry.accuracy >= 60 ? '#00D4A8' : entry.accuracy >= 52 ? '#FFB830' : '#FF6B6B'}
                          fillOpacity={entry.accuracy === best ? 1 : 0.75}
                          stroke={entry.accuracy === best ? '#fff' : 'none'}
                          strokeWidth={entry.accuracy === best ? 1.5 : 0}
                        />
                      ))}
                      <LabelList dataKey="accuracy" content={renderLabel} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ textAlign: 'center', fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 2, paddingBottom: 4 }}>
                  🏆 Best: <span style={{ color: '#00D4A8', fontWeight: 700 }}>{filtered[0]?.model}</span> at <span style={{ color: '#00D4A8', fontWeight: 700 }}>{best}%</span> validation accuracy
                </div>
              </div>
            )
          })()}
        </div>

        {/* Recent predictions */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <div className="card-title" style={{ margin: 0 }}>Recent Predictions</div>
          </div>
          <div style={{ maxHeight: 240, overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Direction</th>
                  <th>Conf</th>
                  <th>Trade?</th>
                  <th>Outcome</th>
                  <th>Age</th>
                </tr>
              </thead>
              <tbody>
                {data.slice(0, 20).map((p, i) => {
                  const isCorrect = p.was_correct == 1 || p.was_correct === true
                  const pending = p.was_correct === null || p.was_correct === undefined
                  const dirColor = dirColors[p.predicted_direction] || '#6B7FA3'
                  const conf = parseFloat(p.confidence || 0)
                  const isGated = conf >= MIN_CONFIDENCE
                  return (
                    <tr key={i} style={{ opacity: isGated ? 1 : 0.5 }}>
                      <td style={{ fontSize: '0.68rem', color: 'var(--text-2)' }}>{shortModel(p.model_name)}</td>
                      <td style={{ color: dirColor, fontFamily: 'var(--font-mono)', fontSize: '0.72rem', fontWeight: 700 }}>
                        {p.predicted_direction === 'UP' ? '↑' : p.predicted_direction === 'DOWN' ? '↓' : '→'} {p.predicted_direction}
                      </td>
                      <td style={{
                        fontFamily: 'var(--font-mono)',
                        color: isGated ? '#00D4A8' : 'var(--text-muted)',
                        fontSize: '0.72rem',
                        fontWeight: isGated ? 700 : 400,
                      }}>
                        {(conf*100).toFixed(0)}%
                      </td>
                      <td>
                        {isGated ? (
                          <span style={{ color: '#00D4A8', fontSize: '0.65rem' }}>✓ YES</span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>✗ SKIP</span>
                        )}
                      </td>
                      <td>
                        {pending ? (
                          <span style={{ color: 'var(--yellow)', fontSize: '0.68rem' }}>⏳ PENDING</span>
                        ) : isCorrect ? (
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
