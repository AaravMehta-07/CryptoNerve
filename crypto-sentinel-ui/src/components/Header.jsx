import { useState, useEffect } from 'react'
import Ticker from './Ticker'
import { useCurrency } from '../context/CurrencyContext'

export default function Header() {
  const [time, setTime] = useState(new Date())
  const [apiOk, setApiOk] = useState(null)
  const [retryIn, setRetryIn] = useState(5)
  const { currency, toggle, usdToInr } = useCurrency()

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    let countdown = null

    const check = () => {
      fetch('/api/health')
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(() => { setApiOk(true); setRetryIn(5); clearInterval(countdown) })
        .catch(() => {
          setApiOk(false)
          let t = 5
          setRetryIn(t)
          clearInterval(countdown)
          countdown = setInterval(() => {
            t -= 1
            setRetryIn(t)
            if (t <= 0) { clearInterval(countdown); check() }
          }, 1000)
        })
    }

    check()
    const poll = setInterval(() => check(), 30000)
    return () => { clearInterval(poll); clearInterval(countdown) }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const utc = time.toUTCString().slice(5, 25)

  return (
    <>
      <header style={{
        background: 'linear-gradient(90deg, #060D18 0%, #080E1A 100%)',
        borderBottom: '1px solid var(--border)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}>
        {/* Top bar */}
        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 20px',
          borderBottom: '1px solid var(--border)',
        }}>
          {/* Left: label */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: 'var(--green)', boxShadow: '0 0 8px var(--green)',
              animation: 'glowPulse 2s infinite',
            }} />
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: '0.68rem',
              letterSpacing: 2, color: 'var(--text-muted)', textTransform: 'uppercase',
            }}>
              Crypto Sentinel · AI Market Intelligence Terminal
            </span>
          </div>

          {/* Right: controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            {/* Currency toggle */}
            <button
              onClick={toggle}
              title={`Switch to ${currency === 'USD' ? 'INR' : 'USD'} · 1 USD = ₹${usdToInr.toFixed(1)}`}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: currency === 'INR'
                  ? 'linear-gradient(135deg, rgba(4,116,214,0.25), rgba(4,116,214,0.08))'
                  : 'linear-gradient(135deg, rgba(255,184,48,0.2), rgba(255,184,48,0.06))',
                border: `1px solid ${currency === 'INR' ? 'rgba(4,116,214,0.5)' : 'rgba(255,184,48,0.45)'}`,
                borderRadius: 8, padding: '4px 11px', cursor: 'pointer',
                fontFamily: 'var(--font-mono)', fontSize: '0.72rem', fontWeight: 700,
                color: currency === 'INR' ? '#4C9BE8' : '#FFB830',
                letterSpacing: 1, transition: 'all 0.2s',
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}
            >
              {currency === 'USD' ? '$ USD' : '₹ INR'}
              <span style={{ fontSize: '0.6rem', opacity: 0.7 }}>⇄</span>
            </button>

            {/* API status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: apiOk === null ? 'var(--yellow)' : apiOk ? 'var(--green)' : 'var(--red)',
                boxShadow: apiOk ? '0 0 6px var(--green)' : undefined,
              }} />
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                API {apiOk === null ? 'CHECKING' : apiOk ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>

            {/* Clock */}
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: '0.75rem',
              color: 'var(--text-2)', letterSpacing: 1,
            }}>
              🕐 {utc} UTC
            </div>

            {/* Badge */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(255,107,53,0.15), rgba(232,76,0,0.05))',
              border: '1px solid rgba(255,107,53,0.3)', borderRadius: 6,
              padding: '3px 10px', fontSize: '0.62rem',
              fontFamily: 'var(--font-mono)', color: 'var(--orange)', letterSpacing: 1,
            }}>
              NMIMS INNOVATHON 2026
            </div>
          </div>
        </div>

        {/* Ticker */}
        <Ticker />
      </header>

      {/* API offline banner — auto-retries every 5s */}
      {apiOk === false && (
        <div style={{
          background: 'linear-gradient(90deg, rgba(255,60,60,0.13), rgba(255,100,50,0.07))',
          borderBottom: '1px solid rgba(255,60,60,0.35)',
          padding: '7px 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          position: 'sticky', top: 0, zIndex: 49,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>
            <span style={{ color: 'var(--red)', fontSize: '0.9rem' }}>⚠</span>
            <span style={{ color: '#FF6060', fontWeight: 600 }}>API server is offline.</span>
            <span style={{ color: 'var(--text-muted)' }}>
              Double-click{' '}
              <code style={{ background: 'rgba(255,255,255,0.07)', padding: '1px 6px', borderRadius: 4 }}>
                start.bat
              </code>{' '}
              at the project root to auto-launch all services.
            </span>
          </div>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
            Retrying in {retryIn}s…
          </span>
        </div>
      )}
    </>
  )
}
