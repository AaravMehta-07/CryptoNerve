import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import { signalColor, signalIcon, fmtCurrency, timeAgo, COINS } from '../utils/formatters'
import { useCurrency } from '../context/CurrencyContext'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip
} from 'recharts'

const SIGNAL_COLORS = {
  STRONG_BUY: '#00FF9C', BUY: '#00D4A8', HOLD: '#4C9BE8', SELL: '#FF7B54', STRONG_SELL: '#FF4C4C'
}

export default function Signals() {
  const [signals,  setSignals]  = useState([])
  const [selected, setSelected] = useState(null)
  const [coin,     setCoin]     = useState('ALL')
  const [loading,  setLoading]  = useState(true)
  const currCtx = useCurrency()

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      const data = await api.signals(coin !== 'ALL' ? { coin, limit: 30 } : { limit: 30 })
      setSignals(data)
      if (data.length) setSelected(data[0])
      setLoading(false)
    }
    load()
  }, [coin])

  const radarData = selected ? [
    { subject: 'LLM Sentiment', val: parseFloat(selected.sentiment_score  || 0.5) },
    { subject: 'ML Prediction', val: parseFloat(selected.prediction_score || 0.5) },
    { subject: 'On-Chain',      val: parseFloat(selected.onchain_score    || 0.5) },
    { subject: 'Technicals',    val: parseFloat(selected.technical_score  || 0.5) },
  ] : []

  return (
    <div>
      <div className="page-header">
        <h1>📡 Signals & Alerts</h1>
        <p>Composite buy/sell signals · ML + LLM + On-Chain + Technical analysis</p>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-8 mb-16">
        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Filter by coin:</span>
        <div className="pill-tabs">
          {['ALL', 'BTC', 'ETH', 'SOL', 'XRP', 'DOGE'].map(c => (
            <button key={c} className={`pill-tab ${coin === c ? 'active' : ''}`}
              onClick={() => setCoin(c)}>{c}</button>
          ))}
        </div>
      </div>

      <div className="grid-2" style={{ gap: 20 }}>
        {/* Signal log */}
        <div>
          <div className="section-title">Signal Log</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {loading ? [0,1,2,3,4].map(i => (
              <div key={i} className="card" style={{ height: 64 }}>
                <div className="skeleton" style={{ width: '60%', marginBottom: 6 }} />
                <div className="skeleton" style={{ width: '40%' }} />
              </div>
            )) : signals.map((sig, i) => {
              const color = signalColor(sig.signal_type)
              const conf  = parseFloat(sig.confidence || 0)
              const active = selected?.id === sig.id
              return (
                <div key={sig.id || i}
                  className="card"
                  style={{
                    cursor: 'pointer',
                    borderColor: active ? color : 'var(--border)',
                    background: active ? `${color}0C` : 'var(--card)',
                    transition: 'all 0.15s',
                  }}
                  onClick={() => setSelected(sig)}
                >
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-8">
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        color: COINS[sig.coin]?.color || 'var(--text)',
                        fontSize: '0.85rem',
                        width: 36
                      }}>{sig.coin}</span>
                      <span className={`badge badge-${sig.signal_type}`}>
                        {signalIcon(sig.signal_type)} {sig.signal_type?.replace('_', ' ')}
                      </span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-2)' }}>
                        {fmtCurrency(sig.price_at_signal, currCtx)}
                      </div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                        {timeAgo(sig.generated_at)}
                      </div>
                    </div>
                  </div>
                  <div className="conf-track" style={{ marginTop: 8 }}>
                    <div className="conf-fill" style={{ width: `${conf * 100}%`, background: color }} />
                  </div>
                  <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: 2 }}>
                    {(conf * 100).toFixed(0)}% confidence
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Signal detail */}
        <div>
          <div className="section-title">Signal Breakdown</div>
          {selected ? (
            <div className="card" style={{ borderColor: signalColor(selected.signal_type) }}>
              {/* Header */}
              <div className="flex justify-between items-center mb-12">
                <div>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '1.2rem',
                    fontWeight: 700,
                    color: COINS[selected.coin]?.color || 'var(--text)',
                  }}>{selected.coin}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {COINS[selected.coin]?.name}
                  </div>
                </div>
                <div className={`badge badge-${selected.signal_type}`} style={{ fontSize: '0.82rem', padding: '4px 14px' }}>
                  {signalIcon(selected.signal_type)} {selected.signal_type?.replace('_', ' ')}
                </div>
              </div>

              {/* Price + confidence */}
              <div className="flex gap-16 mb-12">
                <div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>PRICE AT SIGNAL</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', color: 'var(--text)' }}>
                    {fmtCurrency(selected.price_at_signal, currCtx)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>CONFIDENCE</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', color: signalColor(selected.signal_type) }}>
                    {(parseFloat(selected.confidence || 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>GENERATED</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>
                    {timeAgo(selected.generated_at)}
                  </div>
                </div>
              </div>

              {/* Radar */}
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#1A2840" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#A0AABF', fontSize: 10 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 1]} tick={{ fill: '#6B7FA3', fontSize: 9 }} />
                  <Radar name="Scores" dataKey="val" stroke={signalColor(selected.signal_type)}
                         fill={signalColor(selected.signal_type)} fillOpacity={0.2} strokeWidth={2} />
                  <Tooltip
                    formatter={(v) => [v.toFixed(3), '']}
                    contentStyle={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8 }}
                    labelStyle={{ color: '#6B7FA3' }}
                  />
                </RadarChart>
              </ResponsiveContainer>

              {/* Component scores */}
              {[
                { label: 'LLM Sentiment', val: selected.sentiment_score,  color: '#FF6B35' },
                { label: 'ML Prediction', val: selected.prediction_score, color: '#4C9BE8' },
                { label: 'On-Chain',      val: selected.onchain_score,    color: '#00D4A8' },
                { label: 'Technicals',    val: selected.technical_score,  color: '#FFB830' },
              ].map(c => {
                const v = parseFloat(c.val || 0.5)
                return (
                  <div key={c.label} style={{ marginBottom: 8 }}>
                    <div className="flex justify-between mb-8">
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-2)' }}>{c.label}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: c.color }}>
                        {(v * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="conf-track">
                      <div className="conf-fill" style={{ width: `${v * 100}%`, background: c.color }} />
                    </div>
                  </div>
                )
              })}

              {/* Reasoning */}
              {selected.reasoning && (
                <div style={{
                  marginTop: 12,
                  background: 'var(--bg)',
                  border: `1px solid ${signalColor(selected.signal_type)}33`,
                  borderLeft: `3px solid ${signalColor(selected.signal_type)}`,
                  borderRadius: 8,
                  padding: '10px 14px',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  color: '#00D4A8',
                  whiteSpace: 'pre-wrap',
                  maxHeight: 120,
                  overflowY: 'auto',
                }}>
                  {selected.reasoning}
                </div>
              )}
            </div>
          ) : (
            <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
              Select a signal from the log
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
