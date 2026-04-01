import { useState, useEffect, useCallback } from 'react'
import { api } from '../utils/api'
import { fmtCurrency, signalColor, signalIcon, COINS } from '../utils/formatters'
import { useCurrency } from '../context/CurrencyContext'

// Safe fetch that always reads body as text first — avoids "Unexpected end of JSON"
async function fetchJSON(url, options = {}) {
  let res
  try {
    res = await fetch(url, options)
  } catch (e) {
    throw new Error('API server is offline. Start: cd crypto-sentinel && python -m uvicorn api.main:app --reload --port 8000')
  }
  const raw = await res.text()
  if (!raw || !raw.trim()) {
    throw new Error('API server is offline or restarting. Run uvicorn in a separate terminal.')
  }
  if (raw.trim().startsWith('<')) {
    throw new Error('API not running — got HTML response. Start the FastAPI server.')
  }
  let data
  try {
    data = JSON.parse(raw)
  } catch {
    throw new Error('Invalid JSON from server: ' + raw.slice(0, 200))
  }
  // If server returned an error JSON (status ≠ 2xx), surface the server message
  if (!res.ok) {
    const msg = data?.error || data?.detail || `Server error ${res.status}`
    throw new Error(`[${res.status}] ${msg}`)
  }
  return data
}
import SignalCard from '../components/SignalCard'
import FearGreedGauge from '../components/FearGreedGauge'
import HeatmapGrid from '../components/HeatmapGrid'
import toast from 'react-hot-toast'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

const COIN_ORDER = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']

const TT = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem' }}>
      <div style={{ color: '#6B7FA3', marginBottom: 4 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color, fontFamily: "'Space Mono', monospace" }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
        </div>
      ))}
    </div>
  )
}

// ── Analysis result banner ────────────────────────────────────────────────────
function AnalysisBanner({ result, onDismiss, currCtx }) {
  if (!result) return null
  const color = signalColor(result.signal)
  const icon = signalIcon(result.signal)
  return (
    <div style={{
      background: `linear-gradient(135deg, ${color}18, ${color}06)`,
      border: `1px solid ${color}44`,
      borderLeft: `4px solid ${color}`,
      borderRadius: 10,
      padding: '12px 16px',
      marginBottom: 16,
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
    }}>
      <div>
        <div style={{ fontSize: '0.78rem', fontWeight: 700, color, marginBottom: 4 }}>
          {icon} {result.coin} Analysis Complete — {result.signal}
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-2)', fontFamily: 'var(--font-mono)', lineHeight: 1.6 }}>
          Price: {fmtCurrency(result.price, currCtx)} · Sentiment: {parseFloat(result.sentiment).toFixed(3)} ·
          Confidence: {(result.confidence * 100).toFixed(1)}% · Articles: {result.articles}
        </div>
        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 4, maxWidth: 700 }}>
          📋 {result.reasoning}
        </div>
      </div>
      <button onClick={onDismiss} style={{
        background: 'none', border: 'none', color: 'var(--text-muted)',
        fontSize: '1rem', cursor: 'pointer', paddingLeft: 12, flexShrink: 0,
      }}>✕</button>
    </div>
  )
}

export default function Dashboard() {
  const [signals, setSignals] = useState([])
  const [fearGreed, setFearGreed] = useState([])
  const [heatmap, setHeatmap] = useState([])
  const [sentiment, setSentiment] = useState([])
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState({}) // { coin: bool }
  const [analyzingAll, setAnalyzingAll] = useState(false)
  const [lastResult, setLastResult] = useState(null)

  const currCtx = useCurrency()

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [sig, fg, hm, sent] = await Promise.all([
        api.latestSignals(),
        api.fearGreed(48),
        api.sentimentHeatmap(12),
        api.sentiment('BTC', 48),
      ])
      setSignals(sig)
      setFearGreed(fg)
      setHeatmap(hm)
      setSentiment(sent)
    } catch (e) {
      if (!silent) console.error(e)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
    const id = setInterval(() => loadData(true), 60000)
    return () => clearInterval(id)
  }, [loadData])

  // ── Per-coin Analyze ──────────────────────────────────────────────────────
  const analyzeCoin = async (coin) => {
    setAnalyzing(prev => ({ ...prev, [coin]: true }))
    const toastId = toast.loading(`🔄 Analyzing ${coin}... fetching RSS feeds & computing signal`)
    try {
      const data = await fetchJSON(`/api/analyze/${coin}`)
      if (data.error) throw new Error(data.error)
      setLastResult(data)
      toast.success(`✅ ${coin}: ${data.signal} (${(data.confidence * 100).toFixed(1)}% conf · ${data.articles} articles)`, { id: toastId, duration: 5000 })
      await loadData(true)
    } catch (e) {
      toast.error(e.message, { id: toastId, duration: 7000 })
    } finally {
      setAnalyzing(prev => ({ ...prev, [coin]: false }))
    }
  }

  // ── Run all ───────────────────────────────────────────────────────────────
  const analyzeAll = async () => {
    setAnalyzingAll(true)
    const toastId = toast.loading('🔄 Analyzing all 5 coins... fetching RSS feeds')
    try {
      const data = await fetchJSON('/api/analyze-all')
      const successful = data.results?.filter(r => r.status === 'ok') || []
      toast.success(`✅ Analysis complete: ${successful.length}/5 coins processed`, { id: toastId, duration: 6000 })
      if (successful.length) setLastResult(successful[successful.length - 1])
      await loadData(true)
    } catch (e) {
      toast.error(e.message, { id: toastId, duration: 7000 })
    } finally {
      setAnalyzingAll(false)
    }
  }

  // ── Seed demo data ────────────────────────────────────────────────────────
  const seedDemo = async () => {
    const toastId = toast.loading('🌱 Seeding demo data...')
    try {
      const data = await fetchJSON('/api/seed-demo', { method: 'POST' })
      if (data.status === 'ok') {
        toast.success('✅ Demo data seeded! Refreshing...', { id: toastId })
        await loadData(true)
      } else {
        toast.error('Seed failed: ' + (data.stderr || data.error), { id: toastId })
      }
    } catch (e) {
      toast.error(e.message, { id: toastId, duration: 7000 })
    }
  }

  const latestFG = fearGreed.length ? fearGreed[fearGreed.length - 1] : { index_value: 50, label: 'Neutral' }
  const buyCount = signals.filter(s => s.signal_type?.includes('BUY')).length
  const sellCount = signals.filter(s => s.signal_type?.includes('SELL')).length
  const avgConf = signals.length
    ? (signals.reduce((s, x) => s + parseFloat(x.confidence || 0), 0) / signals.length * 100).toFixed(1)
    : 0

  const sentChart = sentiment.slice(-24).map(d => ({
    time: d.window_start?.slice(11, 16) || '',
    score: parseFloat(d.avg_sentiment || 0),
  }))

  const fgChart = fearGreed.slice(-24).map(d => ({
    time: d.timestamp?.slice(11, 16) || '',
    value: parseInt(d.index_value || 50),
  }))

  const anyAnalyzing = analyzingAll || Object.values(analyzing).some(Boolean)

  return (
    <div>
      {/* ── Page header ── */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>⚡ Live Intelligence Dashboard</h1>
          <p>Real-time composite signals · LLM Sentiment + ML + On-Chain + Technicals</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button className="btn btn-ghost" onClick={seedDemo} style={{ fontSize: '0.75rem' }}>
            🌱 Seed Demo Data
          </button>
          <button
            className="btn btn-primary"
            onClick={analyzeAll}
            disabled={anyAnalyzing}
            style={{ fontSize: '0.78rem', opacity: anyAnalyzing ? 0.7 : 1 }}
          >
            {analyzingAll ? '⏳ Analyzing All...' : '🚀 Run Full Analysis'}
          </button>
        </div>
      </div>

      {/* ── Analysis result banner ── */}
      <AnalysisBanner result={lastResult} onDismiss={() => setLastResult(null)} currCtx={currCtx} />

      {/* ── KPI row ── */}
      <div className="kpi-grid">
        {[
          { label: 'Active Signals', val: signals.length, sub: `${buyCount} BUY · ${sellCount} SELL`, accent: 'var(--green)' },
          { label: 'Avg Confidence', val: `${avgConf}%`, sub: 'across all tracked coins', accent: 'var(--blue)' },
          { label: 'Fear & Greed', val: latestFG.index_value, sub: latestFG.label, accent: 'var(--yellow)' },
          {
            label: 'BTC Sentiment', val: sentiment.length ? parseFloat(sentiment[sentiment.length - 1]?.avg_sentiment || 0).toFixed(3) : '—',
            sub: 'Latest 1h window', accent: 'var(--orange)'
          },
          { label: 'Data Windows', val: sentiment.length, sub: '1h buckets tracked', accent: 'var(--purple)' },
        ].map(k => (
          <div key={k.label} className="kpi" style={{ '--accent': k.accent }}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ color: k.accent }}>
              {loading ? <div className="skeleton" style={{ width: 60, height: 20 }} /> : k.val}
            </div>
            <div className="kpi-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      {/* ── Signal cards ── */}
      <div className="section-title">📡 Live Signal per Coin</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
        {COIN_ORDER.map(coin => {
          const sig = signals.find(s => s.coin === coin)
          const isBusy = analyzing[coin] || analyzingAll
          const info = COINS[coin]

          return (
            <div key={coin} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {/* Analyze button above card */}
              <button
                className="btn"
                onClick={() => analyzeCoin(coin)}
                disabled={isBusy}
                style={{
                  background: isBusy
                    ? 'var(--surface)'
                    : `linear-gradient(135deg, ${info.color}25, ${info.color}10)`,
                  border: `1px solid ${info.color}50`,
                  color: isBusy ? 'var(--text-muted)' : info.color,
                  borderRadius: 8,
                  padding: '7px 0',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  justifyContent: 'center',
                  opacity: isBusy ? 0.7 : 1,
                  transition: 'all 0.2s',
                  cursor: isBusy ? 'not-allowed' : 'pointer',
                }}
              >
                {isBusy ? '⏳ Analyzing...' : `🔍 Analyze ${coin}`}
              </button>

              {/* Signal card or placeholder */}
              {loading ? (
                <div style={{
                  background: 'var(--card)', border: '1px solid var(--border)',
                  borderRadius: 14, height: 240,
                  animation: 'shimmer 1.5s infinite',
                }} />
              ) : sig ? (
                <SignalCard signal={sig} />
              ) : (
                <div style={{
                  background: 'var(--card)',
                  border: `1px dashed ${info.color}30`,
                  borderRadius: 14,
                  height: 180,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  color: 'var(--text-muted)',
                }}>
                  <div style={{ fontSize: '1.5rem', color: info.color, opacity: 0.5 }}>🔮</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: info.color }}>
                    {coin}
                  </div>
                  <div style={{ fontSize: '0.7rem', textAlign: 'center', lineHeight: 1.4 }}>
                    No signal yet
                    <br />
                    <span style={{ color: info.color, opacity: 0.7 }}>Click Analyze {coin}</span>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* ── Charts row ── */}
      <div className="grid-2" style={{ marginBottom: 20 }}>
        {/* Sentiment timeseries */}
        <div className="chart-wrap">
          <div className="card-title">BTC Sentiment Score (48h)</div>
          {sentChart.length === 0 ? (
            <div style={{ height: 200, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--text-muted)' }}>
              <div style={{ fontSize: '0.8rem' }}>No sentiment data. Run analysis to populate.</div>
              <button className="btn btn-ghost" onClick={() => analyzeCoin('BTC')} disabled={analyzing['BTC']} style={{ fontSize: '0.72rem' }}>
                {analyzing['BTC'] ? '⏳...' : '🔍 Analyze BTC Now'}
              </button>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={sentChart}>
                <defs>
                  <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#FF6B35" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#FF6B35" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
                <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 10 }} interval={5} />
                <YAxis domain={[0, 1]} tick={{ fill: '#6B7FA3', fontSize: 10 }} />
                <Tooltip content={<TT />} />
                <ReferenceLine y={0.5} stroke="#4C9BE8" strokeDasharray="4 2" opacity={0.5} />
                <Area type="monotone" dataKey="score" stroke="#FF6B35" fill="url(#sg)"
                  strokeWidth={2} name="Sentiment" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Fear & Greed */}
        <div className="chart-wrap">
          <div className="card-title">Fear & Greed Index</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <FearGreedGauge
              value={parseInt(latestFG.index_value) || 50}
              label={latestFG.label || 'Neutral'}
            />
            {fgChart.length > 0 ? (
              <div style={{ flex: 1 }}>
                <ResponsiveContainer width="100%" height={140}>
                  <AreaChart data={fgChart}>
                    <defs>
                      <linearGradient id="fgg" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#FFB830" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#FFB830" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
                    <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 9 }} interval={4} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#6B7FA3', fontSize: 9 }} />
                    <Tooltip content={<TT />} />
                    <Area type="monotone" dataKey="value" stroke="#FFB830" fill="url(#fgg)"
                      strokeWidth={2} name="F&G" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                Seed demo data to see history
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Heatmap ── */}
      <div className="section-title">🔥 Sentiment Heatmap — All Coins × Time</div>
      <div className="chart-wrap">
        {heatmap.length > 0 ? (
          <HeatmapGrid heatmapData={heatmap} />
        ) : (
          <div style={{ padding: 32, textAlign: 'center' }}>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: 12 }}>
              No sentiment heatmap data. Run analysis for multiple coins to populate.
            </div>
            <button className="btn btn-primary" onClick={analyzeAll} disabled={anyAnalyzing} style={{ fontSize: '0.75rem' }}>
              {analyzingAll ? '⏳ Running...' : '🚀 Run Full Analysis (All Coins)'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
