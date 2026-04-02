import { useState } from 'react'
import { COINS, fmtCurrency } from '../utils/formatters'
import { useCurrency } from '../context/CurrencyContext'
import { api } from '../utils/api'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import toast from 'react-hot-toast'

export default function Backtesting() {
  const [coin, setCoin] = useState('BTC')
  const [days, setDays] = useState(90)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [elapsed, setElapsed] = useState(null)
  const currCtx = useCurrency()

  const runBacktest = async () => {
    setRunning(true)
    setResult(null)
    setElapsed(null)
    toast('⏳ Running server-side backtest on ' + coin + ' (' + days + 'd)... This may take 30-60s', { icon: '🔄', duration: 8000 })
    const t0 = Date.now()
    try {
      const data = await api.backtest(coin, days)
      if (data.error) {
        toast.error('Backtest error: ' + data.error)
        setRunning(false)
        return
      }
      setResult(data)
      setElapsed(((Date.now() - t0) / 1000).toFixed(1))
      toast.success(`Backtest complete! ${data.total_return_pct > 0 ? '📈' : '📉'} ${data.total_return_pct.toFixed(2)}% return (${data.total_trades} trades)`)
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
        <p>Walk-forward backtest using ML Ensemble + Sentiment + Technicals + On-Chain scoring</p>
      </div>

      {/* Config */}
      <div className="card mb-16" style={{ marginBottom: 20 }}>
        <div className="flex items-center gap-16" style={{ flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6, letterSpacing: 1, textTransform: 'uppercase' }}>Coin</div>
            <div className="pill-tabs">
              {Object.keys(COINS).map(c => (
                <button key={c} className={`pill-tab ${coin === c ? 'active' : ''}`} onClick={() => setCoin(c)}>{c}</button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6, letterSpacing: 1, textTransform: 'uppercase' }}>Period</div>
            <div className="pill-tabs">
              {[30, 60, 90, 120, 180].map(d => (
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

      {/* Methodology badge */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(76,155,232,0.08), rgba(0,212,168,0.05))',
        border: '1px solid rgba(76,155,232,0.2)',
        borderRadius: 10,
        padding: '12px 16px',
        fontSize: '0.78rem',
        color: 'var(--text-2)',
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}>
        <span style={{ fontSize: '1.1rem' }}>🧠</span>
        <div>
          <strong style={{ color: 'var(--blue)' }}>Composite Scoring Engine</strong> — Each candle scored using:
          <span style={{ color: '#FF6B35', marginLeft: 4 }}>LLM Sentiment (50%)</span> ·
          <span style={{ color: '#FFB830', marginLeft: 4 }}>Technicals (25%)</span> ·
          <span style={{ color: '#4C9BE8', marginLeft: 4 }}>On-Chain (15%)</span> ·
          <span style={{ color: '#00D4A8', marginLeft: 4 }}>ML Ensemble (10%)</span>
        </div>
      </div>

      {/* Disclaimer */}
      <div style={{
        background: 'rgba(255,184,48,0.06)',
        border: '1px solid rgba(255,184,48,0.2)',
        borderRadius: 8,
        padding: '10px 14px',
        fontSize: '0.72rem',
        color: 'var(--yellow)',
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        ⚠️ Backtesting uses historical data and trained models. Past performance does not indicate future results. Educational use only.
      </div>

      {result && <BacktestResult result={result} currCtx={currCtx} elapsed={elapsed} />}

      {!result && !running && (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: '2.5rem', marginBottom: 16, opacity: 0.7 }}>📊</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Configure parameters above and run backtest to see results
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', marginTop: 8 }}>
            The server will replay historical candles through the full ML + Sentiment pipeline
          </div>
        </div>
      )}

      {running && (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <div className="loading-spinner" style={{ margin: '0 auto 16px' }} />
          <div style={{ color: 'var(--blue)', fontSize: '0.9rem', fontWeight: 600, marginBottom: 6 }}>
            Running walk-forward backtest...
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
            Building features → ML ensemble batch prediction → Composite scoring → Trade simulation
          </div>
        </div>
      )}
    </div>
  )
}

function BacktestResult({ result, currCtx, elapsed }) {
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
      {/* Engine badge */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, flexWrap: 'wrap'
      }}>
        <span className={`badge ${result.ml_models_used ? 'badge-BUY' : 'badge-HOLD'}`}
          style={{ fontSize: '0.7rem', padding: '3px 10px' }}>
          {result.ml_models_used ? '🧠 ML Ensemble Active' : '📐 Rule-Based Fallback'}
        </span>
        <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
          {result.candles_analyzed.toLocaleString()} candles analyzed · {result.days} days · {result.coin}
        </span>
        {elapsed && (
          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
            ⏱ {elapsed}s
          </span>
        )}
      </div>

      <div className="kpi-grid mb-16">
        {[
          { label: 'Total Return', val: `${result.total_return_pct >= 0 ? '+' : ''}${result.total_return_pct.toFixed(2)}%`, accent: retColor },
          { label: 'Final Capital', val: fmtCurrency(result.final_capital, currCtx, 0), accent: 'var(--text)' },
          { label: 'Sharpe Ratio', val: result.sharpe_ratio.toFixed(2), accent: result.sharpe_ratio >= 1 ? 'var(--green)' : result.sharpe_ratio >= 0 ? 'var(--yellow)' : 'var(--red)' },
          { label: 'Win Rate', val: `${result.win_rate.toFixed(1)}%`, accent: result.win_rate >= 55 ? 'var(--green)' : 'var(--orange)' },
          { label: 'Max Drawdown', val: `–${result.max_drawdown_pct.toFixed(2)}%`, accent: 'var(--red)' },
          { label: 'Trades', val: `${result.total_trades}  (${result.wins}W / ${result.losses}L)`, accent: 'var(--blue)' },
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
        {result.equity_curve.length > 2 ? (
          <ResponsiveContainer width="100%" height={260}>
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
        ) : (
          <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
            Not enough data points for equity chart
          </div>
        )}
      </div>

      {/* Trade log */}
      <div className="section-title">📋 Trade Log (last 30)</div>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Entry</th>
                <th>Exit</th>
                <th>Signal</th>
                <th>ML</th>
                <th>Entry $</th>
                <th>Exit $</th>
                <th>P&L</th>
                <th>P&L %</th>
                <th>Conf</th>
              </tr>
            </thead>
            <tbody>
              {result.trades.map((t, i) => {
                const pnlColor = t.pnl >= 0 ? 'var(--green)' : 'var(--red)'
                const mlColor = t.ml_direction === 'UP' ? '#00FF9C' : t.ml_direction === 'DOWN' ? '#FF4C4C' : '#6B7FA3'
                return (
                  <tr key={i}>
                    <td style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{t.entry_time?.slice(5, 16)}</td>
                    <td style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{t.exit_time?.slice(5, 16)}</td>
                    <td><span className={`badge badge-${t.signal_type}`} style={{ fontSize: '0.58rem', padding: '1px 6px' }}>{t.signal_type?.replace('_', ' ')}</span></td>
                    <td style={{ color: mlColor, fontFamily: 'var(--font-mono)', fontSize: '0.68rem', fontWeight: 700 }}>
                      {t.ml_direction === 'UP' ? '↑' : t.ml_direction === 'DOWN' ? '↓' : '→'}
                    </td>
                    <td className="mono" style={{ fontSize: '0.7rem' }}>{fmtCurrency(t.entry_price, currCtx)}</td>
                    <td className="mono" style={{ fontSize: '0.7rem' }}>{fmtCurrency(t.exit_price, currCtx)}</td>
                    <td style={{ color: pnlColor, fontFamily: 'var(--font-mono)', fontSize: '0.72rem', fontWeight: 700 }}>
                      {t.pnl >= 0 ? '+' : ''}{t.pnl.toFixed(2)}
                    </td>
                    <td style={{ color: pnlColor, fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>
                      {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(2)}%
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--text-2)' }}>
                      {(t.confidence * 100).toFixed(0)}%
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
