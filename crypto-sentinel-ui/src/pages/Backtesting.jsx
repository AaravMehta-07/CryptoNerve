import { useState } from 'react'
import { COINS, fmtCurrency } from '../utils/formatters'
import { useCurrency } from '../context/CurrencyContext'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import toast from 'react-hot-toast'

export default function Backtesting() {
  const [coin, setCoin] = useState('BTC')
  const [days, setDays] = useState(30)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const currCtx = useCurrency()

  const runBacktest = async () => {
    setRunning(true)
    setResult(null)
    toast('⏳ Running backtest on ' + coin + ' (' + days + 'd)...', { icon: '🔄' })
    try {
      const res = await fetch(`/api/signals?coin=${coin}&limit=200`)
      const signals = await res.json()
      if (signals.length < 5) {
        toast.error('Not enough signal data. Let the pipeline run first.')
        setRunning(false)
        return
      }
      // Client-side backtest simulation
      const result = simulateBacktest(signals, days)
      setResult(result)
      toast.success(`Backtest complete! ${result.total_return_pct > 0 ? '📈' : '📉'} ${result.total_return_pct.toFixed(2)}% return`)
    } catch (e) {
      toast.error('Backtest error: ' + e.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>⏳ Strategy Backtesting</h1>
        <p>Simulate historical trading using composite signal strategy</p>
      </div>

      {/* Config */}
      <div className="card mb-16" style={{ marginBottom: 20 }}>
        <div className="flex items-center gap-16">
          <div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6, letterSpacing: 1 }}>COIN</div>
            <div className="pill-tabs">
              {Object.keys(COINS).map(c => (
                <button key={c} className={`pill-tab ${coin === c ? 'active' : ''}`} onClick={() => setCoin(c)}>{c}</button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6, letterSpacing: 1 }}>PERIOD</div>
            <div className="pill-tabs">
              {[7, 14, 30, 60, 90].map(d => (
                <button key={d} className={`pill-tab ${days === d ? 'active' : ''}`} onClick={() => setDays(d)}>{d}d</button>
              ))}
            </div>
          </div>
          <button
            className="btn btn-primary"
            onClick={runBacktest}
            disabled={running}
            style={{ marginLeft: 'auto', opacity: running ? 0.7 : 1 }}
          >
            {running ? '⏳ Running...' : '🚀 Run Backtest'}
          </button>
        </div>
      </div>

      {/* Disclaimer */}
      <div style={{
        background: 'rgba(255,184,48,0.06)',
        border: '1px solid rgba(255,184,48,0.2)',
        borderRadius: 8,
        padding: '10px 14px',
        fontSize: '0.75rem',
        color: 'var(--yellow)',
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        ⚠️ Backtesting uses historical signals from the DB. Past performance does not indicate future results. Educational use only.
      </div>

      {result && <BacktestResult result={result} currCtx={currCtx} />}

      {!result && !running && (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: '2rem', marginBottom: 12 }}>⏳</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Configure parameters above and run backtest to see results
          </div>
        </div>
      )}
    </div>
  )
}

function simulateBacktest(signals, days) {
  const initial = 10000
  let equity = initial
  const cutoff = Date.now() - days * 86400000
  const filtered = signals
    .filter(s => new Date(s.generated_at).getTime() >= cutoff)
    .sort((a, b) => new Date(a.generated_at) - new Date(b.generated_at))

  const trades = []
  const equityCurve = [{ time: filtered[0]?.generated_at?.slice(0, 10) || '—', equity }]
  let wins = 0, losses = 0
  let peakEquity = equity, maxDrawdown = 0

  for (let i = 0; i < filtered.length - 1; i++) {
    const sig = filtered[i]
    const next = filtered[i + 1]
    const isBuy = sig.signal_type?.includes('BUY')
    const isSell = sig.signal_type?.includes('SELL')
    if (!isBuy && !isSell) continue

    const entry = parseFloat(sig.price_at_signal || 0)
    const exit_ = parseFloat(next.price_at_signal || 0)
    if (!entry || !exit_) continue

    const pctChange = (exit_ - entry) / entry
    const pnl = equity * 0.3 * (isBuy ? pctChange : -pctChange)

    equity += pnl
    if (equity > peakEquity) peakEquity = equity
    const dd = (peakEquity - equity) / peakEquity * 100
    if (dd > maxDrawdown) maxDrawdown = dd

    if (pnl > 0) wins++; else losses++

    trades.push({
      entry_time: sig.generated_at?.slice(0, 16),
      exit_time: next.generated_at?.slice(0, 16),
      entry_price: entry,
      exit_price: exit_,
      signal_type: sig.signal_type,
      pnl,
      pnl_pct: pctChange * 100,
    })
    equityCurve.push({ time: next.generated_at?.slice(0, 10) || '—', equity })
  }

  const returns = trades.map(t => t.pnl_pct / 100)
  const mu = returns.reduce((s, r) => s + r, 0) / Math.max(returns.length, 1)
  const sigma = Math.sqrt(returns.reduce((s, r) => s + (r - mu) ** 2, 0) / Math.max(returns.length - 1, 1))
  const sharpe = sigma > 0 ? (mu / sigma) * Math.sqrt(252) : 0

  return {
    initial_capital: initial,
    final_capital: equity,
    total_return_pct: (equity - initial) / initial * 100,
    total_trades: trades.length,
    win_rate: trades.length ? wins / trades.length * 100 : 0,
    max_drawdown_pct: maxDrawdown,
    sharpe_ratio: sharpe,
    equity_curve: equityCurve,
    trades: trades.slice(0, 20),
  }
}

function BacktestResult({ result, currCtx }) {
  const retColor = result.total_return_pct >= 0 ? 'var(--green)' : 'var(--red)'

  const TT = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
      <div style={{ background: '#0D1421', border: '1px solid #1A2840', borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem' }}>
        <div style={{ color: '#6B7FA3', marginBottom: 4 }}>{label}</div>
        {payload.map(p => <div key={p.name} style={{ color: p.color, fontFamily: "'Space Mono',monospace" }}>
          {fmtCurrency(p.value, currCtx, 0)}
        </div>)}
      </div>
    )
  }

  return (
    <div>
      <div className="kpi-grid mb-16">
        {[
          { label: 'Total Return', val: `${result.total_return_pct.toFixed(2)}%`, accent: retColor },
          { label: 'Final Capital', val: fmtCurrency(result.final_capital, currCtx, 0), accent: 'var(--text)' },
          { label: 'Sharpe Ratio', val: result.sharpe_ratio.toFixed(2), accent: result.sharpe_ratio >= 1 ? 'var(--green)' : result.sharpe_ratio >= 0 ? 'var(--yellow)' : 'var(--red)' },
          { label: 'Win Rate', val: `${result.win_rate.toFixed(1)}%`, accent: result.win_rate >= 55 ? 'var(--green)' : 'var(--orange)' },
          { label: 'Max Drawdown', val: `–${result.max_drawdown_pct.toFixed(2)}%`, accent: 'var(--red)' },
          { label: 'Total Trades', val: result.total_trades, accent: 'var(--blue)' },
        ].map(k => (
          <div key={k.label} className="kpi" style={{ '--accent': k.accent }}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ color: k.accent }}>{k.val}</div>
          </div>
        ))}
      </div>

      {/* Equity curve */}
      <div className="chart-wrap mb-16">
        <div className="card-title">Portfolio Equity Curve</div>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={result.equity_curve}>
            <defs>
              <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={retColor} stopOpacity={0.25} />
                <stop offset="95%" stopColor={retColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1A2840" />
            <XAxis dataKey="time" tick={{ fill: '#6B7FA3', fontSize: 9 }} interval="preserveStartEnd" />
            <YAxis tick={{ fill: '#6B7FA3', fontSize: 9 }} tickFormatter={v => `${currCtx.symbol}${currCtx.convert(v).toFixed(0)}`} />
            <Tooltip content={<TT />} />
            <ReferenceLine y={10000} stroke="#6B7FA3" strokeDasharray="4 2" opacity={0.5} />
            <Area type="monotone" dataKey="equity" stroke={retColor} fill="url(#eqGrad)" strokeWidth={2} name="Equity" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Trade log */}
      <div className="section-title">📋 Trade Log (last 20)</div>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Entry</th>
                <th>Exit</th>
                <th>Signal</th>
                <th>Entry $</th>
                <th>Exit $</th>
                <th>P&L</th>
                <th>P&L %</th>
              </tr>
            </thead>
            <tbody>
              {result.trades.map((t, i) => {
                const pnlColor = t.pnl >= 0 ? 'var(--green)' : 'var(--red)'
                return (
                  <tr key={i}>
                    <td style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{t.entry_time}</td>
                    <td style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{t.exit_time}</td>
                    <td><span className={`badge badge-${t.signal_type}`} style={{ fontSize: '0.62rem' }}>{t.signal_type?.replace('_', ' ')}</span></td>
                    <td className="mono">{fmtCurrency(t.entry_price, currCtx)}</td>
                    <td className="mono">{fmtCurrency(t.exit_price, currCtx)}</td>
                    <td style={{ color: pnlColor, fontFamily: 'var(--font-mono)', fontSize: '0.75rem', fontWeight: 700 }}>
                      {t.pnl >= 0 ? '+' : ''}{t.pnl.toFixed(2)}
                    </td>
                    <td style={{ color: pnlColor, fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                      {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(2)}%
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
