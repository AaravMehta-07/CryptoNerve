import { useState, useEffect, useRef } from 'react'
import { fmtCurrency, fmtPct, COINS } from '../utils/formatters'
import { useCurrency } from '../context/CurrencyContext'

const COIN_ORDER = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']

// Binance WS stream names
const BINANCE_STREAMS = {
  BTC:  'btcusdt@ticker',
  ETH:  'ethusdt@ticker',
  SOL:  'solusdt@ticker',
  XRP:  'xrpusdt@ticker',
  DOGE: 'dogeusdt@ticker',
}

const WS_URL = `wss://stream.binance.com:9443/stream?streams=${Object.values(BINANCE_STREAMS).join('/')}`

// Map stream name → coin symbol
const STREAM_TO_COIN = Object.fromEntries(
  Object.entries(BINANCE_STREAMS).map(([coin, stream]) => [stream, coin])
)

export default function Ticker() {
  const [prices, setPrices] = useState({})
  const [flash,  setFlash]  = useState({}) // { BTC: 'up' | 'down' }
  const [status, setStatus] = useState('connecting') // connecting | live | error
  const wsRef = useRef(null)
  const prevRef = useRef({})
  const currCtx = useCurrency()

  useEffect(() => {
    let ws
    let retryTimeout

    const connect = () => {
      setStatus('connecting')
      ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => setStatus('live')

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data)
          const data = msg.data
          if (!data || !data.s) return

          // Binance symbol like BTCUSDT → strip USDT
          const sym = data.s.replace('USDT', '')
          const price  = parseFloat(data.c)  // close (current) price
          const change = parseFloat(data.P)  // 24h change %
          const high   = parseFloat(data.h)
          const low    = parseFloat(data.l)
          const vol    = parseFloat(data.q)  // 24h quote volume USD

          // Flash direction
          const prev = prevRef.current[sym]?.price
          if (prev !== undefined && price !== prev) {
            const dir = price > prev ? 'up' : 'down'
            setFlash(f => ({ ...f, [sym]: dir }))
            setTimeout(() => setFlash(f => ({ ...f, [sym]: null })), 600)
          }

          prevRef.current[sym] = { price }
          setPrices(p => ({ ...p, [sym]: { price, change24h: change, high, low, vol } }))
        } catch {}
      }

      ws.onerror = () => setStatus('error')

      ws.onclose = () => {
        setStatus('error')
        retryTimeout = setTimeout(connect, 5000) // auto-reconnect in 5s
      }
    }

    connect()

    return () => {
      clearTimeout(retryTimeout)
      ws?.close()
    }
  }, [])

  return (
    <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', overflow: 'hidden' }}>
      {COIN_ORDER.map(coin => {
        const info     = COINS[coin]
        const d        = prices[coin]
        const isUp     = d ? d.change24h >= 0 : true
        const chColor  = isUp ? 'var(--green)' : 'var(--red)'
        const flashDir = flash[coin]

        // Flash bg
        const flashBg = flashDir === 'up'
          ? 'rgba(0,255,156,0.07)'
          : flashDir === 'down'
            ? 'rgba(255,76,76,0.07)'
            : 'transparent'

        return (
          <div
            key={coin}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '6px 14px',
              borderRight: '1px solid var(--border)',
              background: flashBg,
              transition: 'background 0.15s, transform 0.1s',
              cursor: 'default',
              position: 'relative',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--card)'}
            onMouseLeave={e => e.currentTarget.style.background = flashBg}
          >
            {/* Coin dot + name */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: info.color,
                boxShadow: `0 0 ${status === 'live' ? '7px' : '3px'} ${info.color}`,
                flexShrink: 0,
                transition: 'box-shadow 0.3s',
              }} />
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: '0.78rem',
                fontWeight: 700, color: info.color,
              }}>{coin}</span>
            </div>

            {/* Price + change */}
            {d ? (
              <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: '0.82rem',
                  fontWeight: 700,
                  color: flashDir === 'up' ? 'var(--green)' : flashDir === 'down' ? 'var(--red)' : 'var(--text)',
                  transition: 'color 0.3s',
                }}>
                  {fmtCurrency(d.price, currCtx)}
                </div>
                <div style={{
                  fontSize: '0.68rem', fontFamily: 'var(--font-mono)',
                  color: chColor, fontWeight: 600,
                }}>
                  {isUp ? '▲' : '▼'} {Math.abs(d.change24h).toFixed(2)}%
                </div>
              </div>
            ) : (
              <div style={{ marginLeft: 'auto' }}>
                <div className="skeleton" style={{ width: 60, height: 12, marginBottom: 4 }} />
                <div className="skeleton" style={{ width: 40, height: 10 }} />
              </div>
            )}
          </div>
        )
      })}

      {/* Status pill */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 5,
        padding: '0 12px', flexShrink: 0,
        fontFamily: 'var(--font-mono)', fontSize: '0.60rem',
        color: status === 'live' ? 'var(--green)' : status === 'connecting' ? 'var(--yellow)' : 'var(--red)',
      }}>
        <div style={{
          width: 5, height: 5, borderRadius: '50%',
          background: status === 'live' ? 'var(--green)' : status === 'connecting' ? 'var(--yellow)' : 'var(--red)',
          boxShadow: status === 'live' ? '0 0 6px var(--green)' : undefined,
          animation: status === 'live' ? 'glowPulse 1.5s infinite' : undefined,
        }} />
        {status === 'live' ? 'LIVE' : status === 'connecting' ? 'CONN...' : 'RETRY'}
      </div>
    </div>
  )
}
