import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import { COINS, fmtCurrency } from '../utils/formatters'
import { useCurrency } from '../context/CurrencyContext'
import CandleChart from '../components/CandleChart'
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart
} from 'recharts'

const TT = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem' }}>
      <div style={{ color: '#6B7FA3', marginBottom: 4 }}>{label}</div>
      {payload.map(p => <div key={p.name} style={{ color: p.color || '#E8EAED', fontFamily: "'Space Mono',monospace" }}>{p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}</div>)}
    </div>
  )
}

export default function Technicals() {
  const [coin,     setCoin]     = useState('BTC')
  const [interval, setInterval_] = useState('15m')
  const [prices,   setPrices]   = useState([])
  const [tech,     setTech]     = useState([])
  const [loading,  setLoading]  = useState(true)
  const currCtx = useCurrency()

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      const [p, t] = await Promise.all([
        api.prices(coin, interval, 48),
        api.technicals(coin, 48),
      ])
      setPrices(p)
      setTech(t)
      setLoading(false)
    }
    load()
  }, [coin, interval])

  const latest = tech.length ? tech[tech.length - 1] : {}

  // RSI + MACD chart data
  const techChart = tech.slice(-48).map(d => ({
    time:      d.timestamp?.slice(11, 16) || '',
    rsi:       parseFloat(d.rsi           || 50),
    macd:      parseFloat(d.macd          || 0),
    signal:    parseFloat(d.macd_signal   || 0),
    histogram: parseFloat(d.macd_histogram|| 0),
  }))

  const rsiColor = (v) => v > 70 ? '#FF4C4C' : v < 30 ? '#00FF9C' : '#4C9BE8'

  return (
    <div>
      <div className="page-header">
        <h1>📊 Price & Technicals</h1>
        <p>Candlestick chart · RSI · MACD · Bollinger Bands</p>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-12 mb-16">
        <div className="pill-tabs">
          {Object.keys(COINS).map(c => (
            <button key={c} className={`pill-tab ${coin === c ? 'active' : ''}`} onClick={() => setCoin(c)}>{c}</button>
          ))}
        </div>
        <div style={{ width: 1, height: 20, background: 'var(--border)' }} />
        <div className="pill-tabs">
          {['5m','15m','1h','4h'].map(i => (
            <button key={i} className={`pill-tab ${interval === i ? 'active' : ''}`} onClick={() => setInterval_(i)}>{i}</button>
          ))}
        </div>
      </div>

      {/* Technical KPIs */}
      <div className="kpi-grid mb-16">
        {[
          { label: 'RSI (14)',    val: parseFloat(latest.rsi || 50).toFixed(1),          accent: rsiColor(parseFloat(latest.rsi || 50)) },
          { label: 'MACD',       val: parseFloat(latest.macd || 0).toFixed(4),            accent: parseFloat(latest.macd||0) >= 0 ? 'var(--green)' : 'var(--red)' },
          { label: 'MACD Signal',val: parseFloat(latest.macd_signal||0).toFixed(4),       accent: 'var(--blue)' },
          { label: 'BB Upper',   val: fmtCurrency(latest.bb_upper, currCtx),                     accent: 'var(--red)' },
          { label: 'BB Lower',   val: fmtCurrency(latest.bb_lower, currCtx),                     accent: 'var(--green)' },
          { label: 'ATR',        val: parseFloat(latest.atr || 0).toFixed(2),             accent: 'var(--yellow)' },
        ].map(k => (
          <div key={k.label} className="kpi" style={{ '--accent': k.accent }}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ color: k.accent, fontSize: '1.2rem' }}>{k.val || '—'}</div>
          </div>
        ))}
      </div>

      {/* Candlestick */}
      <div className="chart-wrap mb-16">
        <div className="card-title">{coin}/{interval} Candlestick</div>
        {loading ? (
          <div style={{ height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            Loading chart data...
          </div>
        ) : (
          <CandleChart data={prices} height={320} coin={coin} />
        )}
      </div>

      {/* RSI */}
      <div className="grid-2 mb-16">
        <div className="chart-wrap">
          <div className="card-title">RSI (14)</div>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={techChart}>
              <defs>
                <linearGradient id="rsiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4C9BE8" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#4C9BE8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
              <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 9 }} interval={8} />
              <YAxis domain={[0, 100]} tick={{ fill: '#6B7FA3', fontSize: 9 }} />
              <Tooltip content={<TT />} />
              <ReferenceLine y={70} stroke="#FF4C4C" strokeDasharray="4 2" opacity={0.6} label={{ value: 'OB', fill: '#FF4C4C', fontSize: 9 }} />
              <ReferenceLine y={30} stroke="#00FF9C" strokeDasharray="4 2" opacity={0.6} label={{ value: 'OS', fill: '#00FF9C', fontSize: 9 }} />
              <Area type="monotone" dataKey="rsi" stroke="#4C9BE8" fill="url(#rsiGrad)" strokeWidth={2} name="RSI" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* MACD */}
        <div className="chart-wrap">
          <div className="card-title">MACD</div>
          <ResponsiveContainer width="100%" height={160}>
            <ComposedChart data={techChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
              <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 9 }} interval={8} />
              <YAxis tick={{ fill: '#6B7FA3', fontSize: 9 }} />
              <Tooltip content={<TT />} />
              <ReferenceLine y={0} stroke="#6B7FA3" opacity={0.4} />
              <Bar dataKey="histogram" name="Histogram"
                fill="#4C9BE840" stroke="#4C9BE8" strokeWidth={0} />
              <Line type="monotone" dataKey="macd"   stroke="#00D4A8" strokeWidth={2} name="MACD"   dot={false} />
              <Line type="monotone" dataKey="signal" stroke="#FF6B35" strokeWidth={1.5} name="Signal" dot={false} strokeDasharray="4 2" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
