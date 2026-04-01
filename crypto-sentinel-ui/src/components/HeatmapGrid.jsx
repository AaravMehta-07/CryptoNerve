import { COINS } from '../utils/formatters'

const COIN_ORDER = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']

/**
 * heatmapData: [{coin, time_bucket, avg_sentiment}]
 */
export default function HeatmapGrid({ heatmapData = [] }) {
  if (!heatmapData.length) {
    return (
      <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
        No sentiment heatmap data available.
      </div>
    )
  }

  // Build sorted time buckets
  const timeBuckets = [...new Set(heatmapData.map(d => d.time_bucket))].sort()
  const last12 = timeBuckets.slice(-12) // show 12 hourly buckets

  // Build lookup: coin+time → sentiment
  const lookup = {}
  heatmapData.forEach(d => { lookup[`${d.coin}|${d.time_bucket}`] = parseFloat(d.avg_sentiment) })

  const sentColor = v => {
    if (v >= 0.7) return { bg: 'rgba(0,255,156,0.30)', text: '#00FF9C' }
    if (v >= 0.6) return { bg: 'rgba(0,212,168,0.20)', text: '#00D4A8' }
    if (v >= 0.5) return { bg: 'rgba(76,155,232,0.15)', text: '#4C9BE8' }
    if (v >= 0.4) return { bg: 'rgba(255,123,84,0.18)', text: '#FF7B54' }
                  return { bg: 'rgba(255,76,76,0.25)',  text: '#FF4C4C' }
  }

  const labelOf = (v) => {
    if (v >= 0.65) return '▲ BULL'
    if (v >= 0.55) return '↑ POS'
    if (v >= 0.45) return '— NEU'
    if (v >= 0.35) return '↓ NEG'
    return '▼ BEAR'
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 500 }}>
        <thead>
          <tr>
            <th style={{
              padding: '6px 10px', textAlign: 'left',
              fontSize: '0.65rem', color: 'var(--text-muted)',
              letterSpacing: 1, textTransform: 'uppercase',
              borderBottom: '1px solid var(--border)',
            }}>Coin</th>
            {last12.map(t => (
              <th key={t} style={{
                padding: '6px 4px', textAlign: 'center',
                fontSize: '0.6rem', color: 'var(--text-muted)',
                letterSpacing: 0.5,
                borderBottom: '1px solid var(--border)',
              }}>
                {t.slice(11, 16)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {COIN_ORDER.map(coin => {
            const info = COINS[coin] || {}
            return (
              <tr key={coin}>
                {/* Coin label */}
                <td style={{
                  padding: '6px 10px',
                  borderBottom: '1px solid rgba(26,40,64,0.4)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{
                      width: 7, height: 7, borderRadius: '50%',
                      background: info.color || '#888',
                      boxShadow: `0 0 4px ${info.color || '#888'}`,
                    }} />
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: info.color || 'var(--text)',
                    }}>{coin}</span>
                  </div>
                </td>

                {/* Sentiment cells */}
                {last12.map(t => {
                  const v = lookup[`${coin}|${t}`]
                  if (v == null) return (
                    <td key={t} style={{ padding: '4px 3px', borderBottom: '1px solid rgba(26,40,64,0.4)' }}>
                      <div style={{
                        background: 'var(--surface)',
                        borderRadius: 4,
                        height: 32,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.6rem',
                        color: 'var(--text-muted)',
                      }}>—</div>
                    </td>
                  )
                  const { bg, text } = sentColor(v)
                  return (
                    <td key={t} style={{ padding: '4px 3px', borderBottom: '1px solid rgba(26,40,64,0.4)' }}>
                      <div
                        title={`${coin} @ ${t}: ${(v * 100).toFixed(1)}%`}
                        style={{
                          background: bg,
                          borderRadius: 4,
                          height: 32,
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: 'default',
                          transition: 'filter 0.2s',
                        }}
                        onMouseEnter={e => e.currentTarget.style.filter = 'brightness(1.4)'}
                        onMouseLeave={e => e.currentTarget.style.filter = 'brightness(1)'}
                      >
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', fontWeight: 700, color: text }}>
                          {v.toFixed(2)}
                        </span>
                        <span style={{ fontSize: '0.52rem', color: text, opacity: 0.8 }}>
                          {labelOf(v)}
                        </span>
                      </div>
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
