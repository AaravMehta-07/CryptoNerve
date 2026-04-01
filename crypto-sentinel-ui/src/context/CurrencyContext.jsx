import { createContext, useContext, useState, useCallback, useEffect } from 'react'

// 1 USD = approx INR (updated live from open exchange)
// We'll fetch live rate, fallback to 83.5
const FALLBACK_RATE = 83.5

const CurrencyContext = createContext(null)

export function CurrencyProvider({ children }) {
  const [currency, setCurrency] = useState('USD') // 'USD' | 'INR'
  const [usdToInr, setUsdToInr] = useState(FALLBACK_RATE)
  const [rateLoaded, setRateLoaded] = useState(false)

  // Fetch live USD/INR rate once
  const fetchRate = useCallback(async () => {
    if (rateLoaded) return
    try {
      // Use a free, no-auth exchange rate API
      const res = await fetch('https://open.er-api.com/v6/latest/USD')
      const json = await res.json()
      if (json?.rates?.INR) {
        setUsdToInr(json.rates.INR)
      }
    } catch {
      // silently use fallback
    } finally {
      setRateLoaded(true)
    }
  }, [rateLoaded])

  const toggle = useCallback(() => {
    fetchRate()
    setCurrency(c => c === 'USD' ? 'INR' : 'USD')
  }, [fetchRate])

  // Prefetch rate on mount so it's ready before first toggle
  useEffect(() => { fetchRate() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const convert = useCallback((usdValue) => {
    if (currency === 'INR') return usdValue * usdToInr
    return usdValue
  }, [currency, usdToInr])

  const symbol = currency === 'USD' ? '$' : '₹'

  return (
    <CurrencyContext.Provider value={{ currency, toggle, convert, symbol, usdToInr }}>
      {children}
    </CurrencyContext.Provider>
  )
}

export function useCurrency() {
  const ctx = useContext(CurrencyContext)
  if (!ctx) throw new Error('useCurrency must be used inside CurrencyProvider')
  return ctx
}
