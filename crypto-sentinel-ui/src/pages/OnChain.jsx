import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import { COINS, fmtShortCurrency, timeAgo } from '../utils/formatters'
import { useCurrency } from '../context/CurrencyContext'
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

const TT = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem' }}>
      <div style={{ color: '#6B7FA3', marginBottom: 4 }}>{label}</div>
      {payload.map(p => <div key={p.name} style={{ color: p.color || '#E8EAED', fontFamily: "'Space Mono',monospace" }}>{p.name}: {p.value?.toFixed?.(2) ?? p.value}</div>)}
    </div>
  )
}

export default function OnChain() {
  const [coin, setCoin] = useState('BTC')
  const [data, setData] = useState([])
  const [whales, setWhales] = useState([])
  const [loading, setLoading] = useState(true)
  const currCtx = useCurrency()

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      const [oc, wh] = await Promise.all([
        api.onchain(coin, 168),
        api.whales(coin, 15),
      ])
      setData(oc)
      setWhales(wh)
      setLoading(false)
    }
    load()
  }, [coin])

  const latest = data.length ? data[data.length - 1] : {}

  const chartData = data.slice(-48).map(d => ({
    time: d.timestamp?.slice(11, 16) || '',
    inflow: parseFloat(d.exchange_inflow_usd || 0) / 1e6,
    outflow: parseFloat(d.exchange_outflow_usd || 0) / 1e6,
    netFlow: parseFloat(d.net_flow_usd || 0) / 1e6,
    whaleTx: parseInt(d.whale_tx_count || 0),
    whaleAct: parseFloat(d.whale_activity_score || 0),
  }))

  return (
    <div>
      <div className="page-header">
        <h1>🐋 On-Chain Intelligence</h1>
        <p>Exchange flows · Whale transactions · On-chain activity scoring</p>
      </div>

      <div className="flex items-center gap-8 mb-16">
        <div className="pill-tabs">
          {Object.keys(COINS).map(c => (
            <button key={c} className={`pill-tab ${coin === c ? 'active' : ''}`} onClick={() => setCoin(c)}>{c}</button>
          ))}
        </div>
      </div>

      {/* KPIs */}
      <div className="kpi-grid mb-16">
        {[
          { label: 'Exchange Inflow', val: fmtShortCurrency(latest.exchange_inflow_usd, currCtx), accent: 'var(--red)' },
          { label: 'Exchange Outflow', val: fmtShortCurrency(latest.exchange_outflow_usd, currCtx), accent: 'var(--green)' },
          {
            label: 'Net Flow', val: fmtShortCurrency(latest.net_flow_usd, currCtx),
            accent: parseFloat(latest.net_flow_usd || 0) >= 0 ? 'var(--green)' : 'var(--red)'
          },
          { label: 'Whale Tx Count', val: latest.whale_tx_count || 0, accent: 'var(--blue)' },
          { label: 'Whale Activity', val: parseFloat(latest.whale_activity_score || 0).toFixed(2), accent: 'var(--orange)' },
        ].map(k => (
          <div key={k.label} className="kpi" style={{ '--accent': k.accent }}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ color: k.accent }}>{k.val}</div>
          </div>
        ))}
      </div>

      <div className="grid-2 mb-16">
        {/* Exchange flows */}
        <div className="chart-wrap">
          <div className="card-title">Exchange Flows ($M)</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData.slice(-24)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
              <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 9 }} interval={4} />
              <YAxis tick={{ fill: '#6B7FA3', fontSize: 9 }} />
              <Tooltip content={<TT />} />
              <Bar dataKey="inflow" name="Inflow ($M)" fill="#FF4C4C50" stroke="#FF4C4C" />
              <Bar dataKey="outflow" name="Outflow ($M)" fill="#00FF9C50" stroke="#00FF9C" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Whale activity */}
        <div className="chart-wrap">
          <div className="card-title">Whale Activity Score (7d)</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="wag" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4C9BE8" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#4C9BE8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
              <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 9 }} interval={8} />
              <YAxis domain={[0, 1]} tick={{ fill: '#6B7FA3', fontSize: 9 }} />
              <Tooltip content={<TT />} />
              <Area type="monotone" dataKey="whaleAct" stroke="#4C9BE8" fill="url(#wag)" strokeWidth={2} name="Whale Activity" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Whale transactions table */}
      <div className="section-title">🐋 Recent Whale Transactions</div>
      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Direction</th>
                <th>Value ({currCtx.currency})</th>
                <th>Exchange From</th>
                <th>Exchange To</th>
                <th>Time</th>
                <th>TX Hash</th>
              </tr>
            </thead>
            <tbody>
              {whales.length ? whales.map((w, i) => {
                const isIn = w.direction === 'in'
                const color = isIn ? 'var(--green)' : 'var(--red)'
                return (
                  <tr key={i}>
                    <td><span className="badge" style={{ color: 'var(--blue)', borderColor: 'var(--blue)', background: 'rgba(76,155,232,0.1)' }}>{w.tx_type || 'TRANSFER'}</span></td>
                    <td style={{ color, fontFamily: 'var(--font-mono)', fontSize: '0.75rem', fontWeight: 700 }}>
                      {isIn ? '▲ IN' : '▼ OUT'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>{fmtShortCurrency(w.value_usd, currCtx)}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{w.is_exchange_from ? '✓ Exchange' : '—'}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{w.is_exchange_to ? '✓ Exchange' : '—'}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{timeAgo(w.block_time)}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                      {w.tx_hash ? w.tx_hash.slice(0, 10) + '...' : '—'}
                    </td>
                  </tr>
                )
              }) : (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)' }}>
                    No whale transactions found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
