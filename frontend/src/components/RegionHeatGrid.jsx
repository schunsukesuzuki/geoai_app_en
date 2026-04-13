import { useMemo } from 'react'
import { heatColorFromNormalized, makeQuantileScale } from '../utils/colorScale'

const groups = {
  'Hokkaido / Tohoku': ['01','02','03','04','05','06','07'],
  'Kanto': ['08','09','10','11','12','13','14'],
  'Chubu': ['15','16','17','18','19','20','21','22','23'],
  'Kinki': ['24','25','26','27','28','29','30'],
  'Chugoku / Shikoku': ['31','32','33','34','35','36','37','38','39'],
  'Kyushu / Okinawa': ['40','41','42','43','44','45','46','47'],
}

export function RegionHeatGrid({ items, selectedRegionCode, onSelectRegion }) {
  const byCode = Object.fromEntries(items.map((item) => [item.region_code, item]))
  const scale = useMemo(
    () => makeQuantileScale(items.map((item) => item.total_risk_score)),
    [items],
  )

  return (
    <section className="card">
      <div className="card-head"><h2>Regional Heat Grid</h2><span>Quantile-based relative coloring</span></div>
      <div className="heat-groups">
        {Object.entries(groups).map(([group, codes]) => (
          <div key={group} className="heat-group">
            <h3>{group}</h3>
            <div className="tile-grid">
              {codes.map((code) => {
                const item = byCode[code]
                if (!item) return null
                return (
                  <button
                    key={code}
                    type="button"
                    className={`tile ${selectedRegionCode === code ? 'active' : ''}`}
                    style={{ background: heatColorFromNormalized(scale.normalize(item.total_risk_score)) }}
                    onClick={() => onSelectRegion(code)}
                    title={`${item.region_name} / ${item.total_risk_score.toFixed(3)}`}
                  >
                    <span className="tile-name">{item.region_name}</span>
                    <span className="tile-meta">#{item.priority_rank}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="legend-row">
        <span>Low Risk</span>
        <div className="legend-bar" />
        <span>High Risk</span>
      </div>
      <p className="muted">Colored by relative position within the national prefecture distribution.</p>
    </section>
  )
}
