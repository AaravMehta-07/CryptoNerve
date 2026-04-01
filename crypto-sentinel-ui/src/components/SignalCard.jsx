import { signalColor, signalIcon, fmtCurrency, fmtPct, timeAgo, COINS } from '../utils/formatters'
import { useCurrency } from '../context/CurrencyContext'

export default function SignalCard({ signal }) {
  if (!signal) return null
  const { coin, signal_type, confidence, price_at_signal, generated_at,
          sentiment_score, prediction_score, onchain_score, technical_score } = signal

  const currCtx = useCurrency()
  const color = signalColor(signal_type)
  const icon  = signalIcon(signal_type)
  const conf  = parseFloat(confidence) || 0
  const info  = COINS[coin] || { color: '#888', name: coin }

  const strong = signal_type === 'STRONG_BUY' || signal_type === 'STRONG_SELL'

  const components = [
    { label: 'Sentiment', val: parseFloat(sentiment_score) || 0,   color: '#FF6B35' },
    { label: 'ML Pred',   val: parseFloat(prediction_score) || 0,  color: '#4C9BE8' },
    { label: 'On-Chain',  val: parseFloat(onchain_score) || 0,     color: '#00D4A8' },
    { label: 'Technical', val: parseFloat(technical_score) || 0,   color: '#FFB830' },
  ]

  return (
    <div
      className={strong ? (signal_type.includes('BUY') ? 'glow-green' : 'glow-red') : ''}
      style={{
        background: 'var(--card)',
        border: `2px solid ${color}`,
        borderRadius: 14,
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        transition: 'transform 0.2s',
        cursor: 'default',
      }}
      onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-3px)'}
      onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
    >
      {/* Coin + Signal type */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '1rem',
            fontWeight: 700,
            color: info.color,
          }}>{coin}</div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{info.name}</div>
        </div>
        <div className={`badge badge-${signal_type}`} style={{ fontSize: '0.7rem' }}>
          {icon} {signal_type.replace('_', ' ')}
        </div>
      </div>

      {/* Price */}
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '1.25rem',
        fontWeight: 700,
        color: 'var(--text)',
        textAlign: 'center',
        padding: '8px 0',
        borderTop: `1px solid ${color}22`,
        borderBottom: `1px solid ${color}22`,
      }}>
        {fmtCurrency(price_at_signal, currCtx)}
      </div>

      {/* Confidence bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>CONFIDENCE</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color }}>{(conf * 100).toFixed(0)}%</span>
        </div>
        <div className="conf-track">
          <div className="conf-fill" style={{ width: `${conf * 100}%`, background: color }} />
        </div>
      </div>

      {/* Component mini bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {components.map(c => (
          <div key={c.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)', width: 56, flexShrink: 0 }}>{c.label}</span>
            <div style={{ flex: 1, background: 'var(--bg)', height: 3, borderRadius: 2 }}>
              <div style={{ width: `${c.val * 100}%`, height: 3, borderRadius: 2, background: c.color }} />
            </div>
            <span style={{ fontSize: '0.62rem', fontFamily: 'var(--font-mono)', color: c.color, width: 28, textAlign: 'right' }}>
              {c.val.toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      {/* Time */}
      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textAlign: 'center' }}>
        {timeAgo(generated_at)}
      </div>
    </div>
  )
}
