function clamp01(x) {
  return Math.max(0, Math.min(1, x))
}

export function makeQuantileScale(values) {
  const sorted = values
    .map((v) => Number(v))
    .filter((v) => Number.isFinite(v))
    .sort((a, b) => a - b)

  if (!sorted.length) {
    return {
      q20: 0,
      q40: 0,
      q60: 0,
      q80: 0,
      min: 0,
      max: 0,
      normalize: () => 0,
      color: () => '#cbd5e1',
    }
  }

  const pick = (p) => {
    const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor((sorted.length - 1) * p)))
    return sorted[idx]
  }

  const min = sorted[0]
  const max = sorted[sorted.length - 1]
  const q20 = pick(0.2)
  const q40 = pick(0.4)
  const q60 = pick(0.6)
  const q80 = pick(0.8)

  const normalize = (value) => {
    const v = Number(value)
    if (!Number.isFinite(v)) return 0
    const denom = Math.max(max - min, 1e-9)
    return clamp01((v - min) / denom)
  }

  const color = (value) => {
    const v = Number(value)
    if (!Number.isFinite(v)) return '#cbd5e1'
    if (v >= q80) return '#b91c1c'
    if (v >= q60) return '#ef4444'
    if (v >= q40) return '#f97316'
    if (v >= q20) return '#facc15'
    return '#86efac'
  }

  return { q20, q40, q60, q80, min, max, normalize, color }
}

export function heatColorFromNormalized(ratio) {
  const r = clamp01(ratio)
  const hue = 120 - r * 120
  const lightness = 82 - r * 18
  return `hsl(${hue}, 72%, ${lightness}%)`
}
