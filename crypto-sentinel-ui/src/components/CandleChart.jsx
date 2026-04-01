import { useEffect, useRef } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'

export default function CandleChart({ data = [], height = 320, coin = 'BTC' }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const seriesRef    = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return

    chartRef.current = createChart(containerRef.current, {
      height,
      layout: {
        background: { color: '#101928' },
        textColor: '#A0AABF',
        fontSize: 11,
        fontFamily: "'Space Mono', monospace",
      },
      grid: {
        vertLines:  { color: '#1A2840' },
        horzLines:  { color: '#1A2840' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine:  { color: '#4C9BE888', labelBackgroundColor: '#101928' },
        horzLine:  { color: '#4C9BE888', labelBackgroundColor: '#101928' },
      },
      rightPriceScale: {
        borderColor: '#1A2840',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#1A2840',
        timeVisible: true,
        secondsVisible: false,
      },
    })

    seriesRef.current = chartRef.current.addCandlestickSeries({
      upColor:          '#00FF9C',
      downColor:        '#FF4C4C',
      borderUpColor:    '#00FF9C',
      borderDownColor:  '#FF4C4C',
      wickUpColor:      '#00D4A8',
      wickDownColor:    '#FF7B54',
    })

    const resizeObs = new ResizeObserver(entries => {
      if (chartRef.current && entries[0]) {
        chartRef.current.applyOptions({ width: entries[0].contentRect.width })
      }
    })
    resizeObs.observe(containerRef.current)

    return () => {
      resizeObs.disconnect()
      chartRef.current?.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !data.length) return
    const sorted = [...data].sort((a, b) => a.timestamp < b.timestamp ? -1 : 1)
    const candles = sorted.map(d => ({
      time:  Math.floor(new Date(d.timestamp).getTime() / 1000),
      open:  parseFloat(d.open),
      high:  parseFloat(d.high),
      low:   parseFloat(d.low),
      close: parseFloat(d.close),
    })).filter(c => c.open && c.high && c.low && c.close)

    if (candles.length) seriesRef.current.setData(candles)
    chartRef.current?.timeScale().fitContent()
  }, [data])

  return (
    <div ref={containerRef} style={{ width: '100%', minHeight: height }} />
  )
}
