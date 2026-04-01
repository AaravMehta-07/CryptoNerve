import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import { COINS } from '../utils/formatters'
import HeatmapGrid from '../components/HeatmapGrid'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend
} from 'recharts'

const TT = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem' }}>
      <div style={{ color: '#6B7FA3', marginBottom: 4 }}>{label}</div>
      {payload.map(p => <div key={p.name} style={{ color: p.color, fontFamily: "'Space Mono',monospace" }}>{p.name}: {p.value?.toFixed?.(3) ?? p.value}</div>)}
    </div>
  )
}

export default function Sentiment() {
  const [coin,       setCoin]       = useState('BTC')
  const [sentData,   setSentData]   = useState([])
  const [narratives, setNarratives] = useState([])
  const [heatmap,    setHeatmap]    = useState([])
  const [loading,    setLoading]    = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      const [s, n, h] = await Promise.all([
        api.sentiment(coin, 72),
        api.narratives(coin, 24),
        api.sentimentHeatmap(12),
      ])
      setSentData(s)
      setNarratives(n)
      setHeatmap(h)
      setLoading(false)
    }
    load()
  }, [coin])

  const chartData = sentData.slice(-48).map(d => ({
    time:       d.window_start?.slice(11, 16) || '',
    sentiment:  parseFloat(d.avg_sentiment  || 0),
    velocity:   parseFloat(d.sentiment_velocity || 0),
    bullish:    parseInt(d.bullish_count || 0),
    bearish:    parseInt(d.bearish_count || 0),
    volume:     parseInt(d.total_posts   || 0),
  }))

  const latest = sentData.length ? sentData[sentData.length - 1] : null

  return (
    <div>
      <div className="page-header">
        <h1>💬 Sentiment Analysis</h1>
        <p>LLM-powered social sentiment · Reddit · News · NLP pipeline</p>
      </div>

      {/* Coin selector */}
      <div className="flex items-center gap-8 mb-16">
        <div className="pill-tabs">
          {Object.keys(COINS).map(c => (
            <button key={c} className={`pill-tab ${coin === c ? 'active' : ''}`} onClick={() => setCoin(c)}>{c}</button>
          ))}
        </div>
      </div>

      {/* KPIs */}
      {latest && (
        <div className="kpi-grid mb-16">
          {[
            { label: 'Sentiment Score', val: parseFloat(latest.avg_sentiment||0).toFixed(3),   accent: parseFloat(latest.avg_sentiment||0) > 0.5 ? 'var(--green)' : 'var(--red)' },
            { label: 'Sentiment Velocity', val: parseFloat(latest.sentiment_velocity||0).toFixed(3), accent: 'var(--blue)' },
            { label: 'Bullish Posts',   val: latest.bullish_count  || 0, accent: 'var(--green)' },
            { label: 'Bearish Posts',   val: latest.bearish_count  || 0, accent: 'var(--red)' },
            { label: 'Total Volume',    val: latest.total_posts    || 0, accent: 'var(--orange)' },
          ].map(k => (
            <div key={k.label} className="kpi" style={{ '--accent': k.accent }}>
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value" style={{ color: k.accent }}>{k.val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Charts */}
      <div className="grid-2 mb-16">
        {/* Sentiment score */}
        <div className="chart-wrap">
          <div className="card-title">{coin} Sentiment Score (72h)</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="sg1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#FF6B35" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#FF6B35" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
              <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 10 }} interval={5} />
              <YAxis domain={[0, 1]} tick={{ fill: '#6B7FA3', fontSize: 10 }} />
              <Tooltip content={<TT />} />
              <ReferenceLine y={0.5} stroke="#4C9BE8" strokeDasharray="4 2" opacity={0.5} />
              <Area type="monotone" dataKey="sentiment" stroke="#FF6B35" fill="url(#sg1)" strokeWidth={2} name="Score" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Bull vs Bear volume */}
        <div className="chart-wrap">
          <div className="card-title">Bull vs Bear Volume</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData.slice(-24)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
              <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 10 }} interval={4} />
              <YAxis tick={{ fill: '#6B7FA3', fontSize: 10 }} />
              <Tooltip content={<TT />} />
              <Legend wrapperStyle={{ fontSize: '0.72rem', color: '#A0AABF' }} />
              <Bar dataKey="bullish" name="Bullish" fill="#00D4A840" stroke="#00D4A8" stackId="a" />
              <Bar dataKey="bearish" name="Bearish" fill="#FF4C4C40" stroke="#FF4C4C" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Velocity chart */}
      <div className="chart-wrap mb-16">
        <div className="card-title">Sentiment Velocity (rate of change)</div>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
            <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 9 }} interval={5} />
            <YAxis tick={{ fill: '#6B7FA3', fontSize: 9 }} />
            <Tooltip content={<TT />} />
            <ReferenceLine y={0} stroke="#6B7FA3" opacity={0.5} />
            <Line type="monotone" dataKey="velocity" stroke="#4C9BE8" strokeWidth={1.5} name="Velocity" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Narratives */}
      <div className="section-title">🗞️ Trending Narratives (24h)</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', marginBottom: 20 }}>
        {narratives.map((n, i) => (
          <span key={i} className="narrative-tag">
            #{n.narrative} <span style={{ opacity: 0.8, marginLeft: 4 }}>{n.mentions}</span>
          </span>
        ))}
        {!narratives.length && <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No narratives available</span>}
      </div>

      {/* Heatmap */}
      <div className="section-title">🔥 Cross-Coin Sentiment Heatmap</div>
      <div className="chart-wrap">
        <HeatmapGrid heatmapData={heatmap} />
      </div>
    </div>
  )
}
