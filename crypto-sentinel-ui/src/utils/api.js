const BASE = '/api'

async function get(path, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const url = qs ? `${BASE}${path}?${qs}` : `${BASE}${path}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  health:           ()                           => get('/health'),
  signals:          (p = {})                     => get('/signals', p),
  latestSignals:    ()                           => get('/signals/latest'),
  sentiment:        (coin, hours = 48)           => get('/sentiment', { coin, hours }),
  sentimentHeatmap: (hours = 12)                 => get('/sentiment/heatmap', { hours }),
  prices:           (coin, interval, hours = 48) => get('/prices', { coin, interval, hours }),
  technicals:       (coin, hours = 48)           => get('/technicals', { coin, hours }),
  onchain:          (coin, hours = 168)          => get('/onchain', { coin, hours }),
  whales:           (coin, limit = 20)           => get('/whales', { coin, limit }),
  predictions:      (p = {})                     => get('/predictions', p),
  fearGreed:        (hours = 48)                 => get('/fear-greed', { hours }),
  modelAccuracy:    ()                           => get('/model-accuracy'),
  narratives:       (coin, hours = 24)           => get('/narratives', { coin, hours }),
  news:             (hours = 48, limit = 20, coin = null) => get('/news', coin ? { hours, limit, coin } : { hours, limit }),
  reports:          (limit = 10)                 => get('/reports', { limit }),
}

// Binance live price
export async function livePrices() {
  try {
    const symbols = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT']
    const results = await Promise.all(
      symbols.map(s =>
        fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${s}`)
          .then(r => r.json())
          .catch(() => null)
      )
    )
    return results.filter(Boolean).map(r => ({
      symbol:    r.symbol.replace('USDT', ''),
      price:     parseFloat(r.lastPrice),
      change24h: parseFloat(r.priceChangePercent),
      high24h:   parseFloat(r.highPrice),
      low24h:    parseFloat(r.lowPrice),
      volume24h: parseFloat(r.volume),
    }))
  } catch {
    return []
  }
}
