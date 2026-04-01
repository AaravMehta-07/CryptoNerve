// fmtPrice — always USD (kept for backward-compat in non-currency-aware spots)
export function fmtPrice(v, decimals = 2) {
  if (v == null || isNaN(v)) return '—'
  const n = parseFloat(v)
  if (n >= 1000) return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return '$' + n.toFixed(decimals)
}

// fmtCurrency — currency-aware: pass in { currency, convert, symbol } from useCurrency()
export function fmtCurrency(v, { currency, convert, symbol }, decimals) {
  if (v == null || isNaN(v)) return '—'
  const usdVal = parseFloat(v)
  const displayVal = convert(usdVal)

  if (currency === 'INR') {
    // INR typically uses Indian numbering (lakhs/crores)
    if (displayVal >= 1e7) return symbol + (displayVal / 1e7).toFixed(2) + ' Cr'
    if (displayVal >= 1e5) return symbol + (displayVal / 1e5).toFixed(2) + ' L'
    if (displayVal >= 1000) return symbol + displayVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    const dec = decimals !== undefined ? decimals : (displayVal < 1 ? 4 : 2)
    return symbol + displayVal.toFixed(dec)
  }
  // USD
  const dec = decimals !== undefined ? decimals : 2
  if (displayVal >= 1000) return symbol + displayVal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return symbol + displayVal.toFixed(dec)
}

// fmtShortCurrency — compact format (K/M/B or L/Cr) with currency
export function fmtShortCurrency(v, { currency, convert, symbol }) {
  if (v == null || isNaN(v)) return '—'
  const displayVal = convert(parseFloat(v))
  if (currency === 'INR') {
    if (Math.abs(displayVal) >= 1e7) return symbol + (displayVal / 1e7).toFixed(2) + 'Cr'
    if (Math.abs(displayVal) >= 1e5) return symbol + (displayVal / 1e5).toFixed(2) + 'L'
    if (Math.abs(displayVal) >= 1e3) return symbol + (displayVal / 1e3).toFixed(1) + 'K'
    return symbol + displayVal.toFixed(2)
  }
  if (Math.abs(displayVal) >= 1e9) return symbol + (displayVal / 1e9).toFixed(2) + 'B'
  if (Math.abs(displayVal) >= 1e6) return symbol + (displayVal / 1e6).toFixed(2) + 'M'
  if (Math.abs(displayVal) >= 1e3) return symbol + (displayVal / 1e3).toFixed(1) + 'K'
  return symbol + displayVal.toFixed(2)
}

export function fmtPct(v, decimals = 2) {
  if (v == null || isNaN(v)) return '—'
  const n = parseFloat(v)
  return (n >= 0 ? '+' : '') + n.toFixed(decimals) + '%'
}

export function fmtShort(v) {
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B'
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toFixed(2)
}

export function timeAgo(ts) {
  if (!ts) return '—'
  const diff = Date.now() - new Date(ts).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

export function signalColor(type) {
  const map = {
    STRONG_BUY: '#00FF9C', BUY: '#00D4A8',
    HOLD: '#4C9BE8',
    SELL: '#FF7B54', STRONG_SELL: '#FF4C4C',
  }
  return map[type] || '#6B7FA3'
}

export function signalIcon(type) {
  const map = {
    STRONG_BUY: '🚀', BUY: '📈',
    HOLD: '⏸', SELL: '📉', STRONG_SELL: '🔴',
  }
  return map[type] || '?'
}

export const COINS = {
  BTC:  { name: 'Bitcoin',  color: '#F7931A', symbol: 'BTCUSDT' },
  ETH:  { name: 'Ethereum', color: '#627EEA', symbol: 'ETHUSDT' },
  SOL:  { name: 'Solana',   color: '#00FFA3', symbol: 'SOLUSDT' },
  XRP:  { name: 'XRP',      color: '#00AAE4', symbol: 'XRPUSDT' },
  DOGE: { name: 'Dogecoin', color: '#C2A633', symbol: 'DOGEUSDT' },
}
