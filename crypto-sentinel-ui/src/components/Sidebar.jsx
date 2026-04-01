import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/dashboard',   icon: '⚡', label: 'Live Dashboard' },
  { to: '/signals',     icon: '📡', label: 'Signals & Alerts' },
  { to: '/sentiment',   icon: '💬', label: 'Sentiment' },
  { to: '/technicals',  icon: '📊', label: 'Price & Technicals' },
  { to: '/onchain',     icon: '🐋', label: 'On-Chain Intel' },
  { to: '/predictions', icon: '🤖', label: 'AI Predictions' },
  { to: '/performance', icon: '🎯', label: 'Model Performance' },
  { to: '/backtesting', icon: '⏳', label: 'Backtesting' },
  { to: '/reports',     icon: '📝', label: 'AI Reports' },
]

export default function Sidebar() {
  return (
    <aside style={{
      width: 'var(--sidebar-w)',
      background: 'linear-gradient(180deg,#060D18 0%, #080D18 100%)',
      borderRight: '1px solid var(--border)',
      position: 'fixed',
      top: 0, left: 0, bottom: 0,
      display: 'flex',
      flexDirection: 'column',
      zIndex: 100,
      overflowY: 'auto',
    }}>
      {/* Logo */}
      <div style={{
        padding: '20px 16px 16px',
        borderBottom: '1px solid var(--border)',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: '2.2rem', marginBottom: 6 }}>🛡️</div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.6rem',
          letterSpacing: 3,
          color: '#6B7FA3',
          textTransform: 'uppercase',
        }}>
          CRYPTO SENTINEL
        </div>
        <div style={{ fontSize: '0.55rem', color: '#3A4A60', marginTop: 2 }}>
          LLM Intelligence Terminal v1.0
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 8px' }}>
        <div style={{
          fontSize: '0.58rem',
          letterSpacing: 2,
          color: 'var(--text-muted)',
          padding: '4px 10px 8px',
          textTransform: 'uppercase',
        }}>
          Navigation
        </div>
        {NAV.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 12px',
              borderRadius: 8,
              marginBottom: 2,
              fontSize: '0.8rem',
              fontWeight: isActive ? 600 : 400,
              color: isActive ? 'var(--green)' : 'var(--text-2)',
              background: isActive ? 'rgba(0,255,156,0.08)' : 'transparent',
              border: `1px solid ${isActive ? 'rgba(0,255,156,0.2)' : 'transparent'}`,
              transition: 'all 0.15s',
              textDecoration: 'none',
            })}
          >
            <span style={{ fontSize: '0.95rem', width: 18, textAlign: 'center' }}>{icon}</span>
            <span>{label}</span>
            {/* Active indicator dot */}
            {false && <span style={{
              width: 5, height: 5, borderRadius: '50%',
              background: 'var(--green)',
              marginLeft: 'auto',
              boxShadow: '0 0 6px var(--green)',
            }} />}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div style={{
        padding: '12px 14px',
        borderTop: '1px solid var(--border)',
        fontSize: '0.6rem',
        color: 'var(--text-muted)',
        textAlign: 'center',
        lineHeight: 1.6,
      }}>
        ⚠️ Simulation only · Not financial advice
        <br />
        <span style={{ color: 'var(--text-muted)', opacity: 0.6 }}>
          NMIMS INNOVATHON 2026
        </span>
      </div>
    </aside>
  )
}
