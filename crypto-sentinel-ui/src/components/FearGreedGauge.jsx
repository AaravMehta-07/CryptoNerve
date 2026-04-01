export default function FearGreedGauge({ value = 50, label = 'Neutral' }) {
  // SVG arc gauge
  const size = 180
  const cx = size / 2
  const cy = size / 2 + 10
  const R  = 70
  const strokeW = 14

  // Map value [0-100] → angle [-180°, 0°] in radians
  const startAngle = -180
  const endAngle   = 0
  const valueAngle = startAngle + (value / 100) * 180
  const toRad = d => (d * Math.PI) / 180

  const arcPath = (start, end) => {
    const s = { x: cx + R * Math.cos(toRad(start)), y: cy + R * Math.sin(toRad(start)) }
    const e = { x: cx + R * Math.cos(toRad(end)),   y: cy + R * Math.sin(toRad(end)) }
    const large = end - start > 180 ? 1 : 0
    return `M ${s.x} ${s.y} A ${R} ${R} 0 ${large} 1 ${e.x} ${e.y}`
  }

  const zones = [
    [startAngle, startAngle + 36],  // Extreme Fear
    [startAngle + 36, startAngle + 72],  // Fear
    [startAngle + 72, startAngle + 108], // Neutral
    [startAngle + 108, startAngle + 144], // Greed
    [startAngle + 144, endAngle],   // Extreme Greed
  ]
  const zoneColors = ['#FF4C4C', '#FF7B54', '#FFB830', '#00D4A8', '#00FF9C']

  const getColor = () => {
    if (value <= 25) return '#FF4C4C'
    if (value <= 45) return '#FF7B54'
    if (value <= 55) return '#FFB830'
    if (value <= 75) return '#00D4A8'
    return '#00FF9C'
  }
  const color = getColor()

  // Needle endpoint
  const needleX = cx + (R - 4) * Math.cos(toRad(valueAngle))
  const needleY = cy + (R - 4) * Math.sin(toRad(valueAngle))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${size * 0.65}`} overflow="visible">
        {/* Background track */}
        <path
          d={arcPath(startAngle, endAngle)}
          stroke="var(--border)"
          strokeWidth={strokeW}
          fill="none"
          strokeLinecap="round"
        />
        {/* Colored zone arcs */}
        {zones.map((z, i) => (
          <path
            key={i}
            d={arcPath(z[0], z[1])}
            stroke={zoneColors[i]}
            strokeWidth={strokeW - 4}
            fill="none"
            opacity={0.25}
          />
        ))}
        {/* Active fill arc */}
        <path
          d={arcPath(startAngle, valueAngle)}
          stroke={color}
          strokeWidth={strokeW}
          fill="none"
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
        {/* Needle dot */}
        <circle cx={cx} cy={cy} r={6} fill="var(--card)" stroke={color} strokeWidth={2} />
        <line
          x1={cx} y1={cy}
          x2={needleX} y2={needleY}
          stroke={color} strokeWidth={2.5} strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}
        />
        {/* Center dot */}
        <circle cx={cx} cy={cy} r={3} fill={color} />
      </svg>

      {/* Value display */}
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '2rem',
        fontWeight: 700,
        color,
        marginTop: -8,
        textShadow: `0 0 20px ${color}66`,
      }}>
        {value}
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '0.72rem',
        fontWeight: 700,
        color,
        letterSpacing: 2,
        marginTop: 2,
        textTransform: 'uppercase',
      }}>
        {label}
      </div>

      {/* Zone labels */}
      <div style={{ display: 'flex', gap: 4, marginTop: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
        {['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'].map((z, i) => (
          <span key={z} style={{
            fontSize: '0.58rem',
            padding: '2px 6px',
            borderRadius: 10,
            color: zoneColors[i],
            background: `${zoneColors[i]}15`,
            border: `1px solid ${zoneColors[i]}30`,
          }}>
            {z}
          </span>
        ))}
      </div>
    </div>
  )
}
