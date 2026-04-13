import { useCallback, useMemo, useRef, useState } from 'react'
import { makeQuantileScale } from '../utils/colorScale'

function flattenCoordinates(geometry) {
  if (!geometry) return []
  if (geometry.type === 'Polygon') {
    return geometry.coordinates.flat(1)
  }
  if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates.flat(2)
  }
  return []
}

function computeBounds(features) {
  let minLon = Infinity
  let minLat = Infinity
  let maxLon = -Infinity
  let maxLat = -Infinity

  features.forEach((feature) => {
    flattenCoordinates(feature.geometry).forEach(([lon, lat]) => {
      if (lon < minLon) minLon = lon
      if (lat < minLat) minLat = lat
      if (lon > maxLon) maxLon = lon
      if (lat > maxLat) maxLat = lat
    })
  })

  return { minLon, minLat, maxLon, maxLat }
}

function makeProjector(bounds, width, height) {
  const lonSpan = bounds.maxLon - bounds.minLon
  const latSpan = bounds.maxLat - bounds.minLat
  const scale = Math.min(width / lonSpan, height / latSpan) * 0.92
  const mapWidth = lonSpan * scale
  const mapHeight = latSpan * scale
  const xOffset = (width - mapWidth) / 2
  const yOffset = (height - mapHeight) / 2

  return ([lon, lat]) => {
    const x = xOffset + (lon - bounds.minLon) * scale
    const y = height - (yOffset + (lat - bounds.minLat) * scale)
    return [x, y]
  }
}

function geometryToPath(geometry, project) {
  if (!geometry) return ''

  const polygonToPath = (polygon) => polygon.map((ring) => ring.map((coord, index) => {
    const [x, y] = project(coord)
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
  }).join(' ') + ' Z').join(' ')

  if (geometry.type === 'Polygon') {
    return polygonToPath(geometry.coordinates)
  }

  if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates.map((polygon) => polygonToPath(polygon)).join(' ')
  }

  return ''
}

export function RegionGeoMap({
  regions,
  metrics,
  selectedRegionCode,
  onSelectRegion,
  showHospitals = false,
  showHealthcareAreas = false,
  onToggleHospitals = () => {},
  onToggleHealthcareAreas = () => {},
  hospitals = [],
  healthcareAreas = [],
}) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef({ active: false, startX: 0, startY: 0, originX: 0, originY: 0, moved: false })
  const metricMap = useMemo(() => new Map(metrics.map((item) => [item.region_code, item])), [metrics])
  const colorScale = useMemo(
    () => makeQuantileScale(metrics.map((item) => item.total_risk_score)),
    [metrics],
  )

  const prepared = useMemo(() => {
    const features = Array.isArray(regions?.features) ? regions.features : []
    if (!features.length) return null

    const width = 760
    const height = 920
    const bounds = computeBounds(features)
    const project = makeProjector(bounds, width, height)

    const shapes = features.map((feature) => {
      const regionCode = feature.properties?.region_code
      const regionName = feature.properties?.region_name || regionCode
      const metric = metricMap.get(regionCode)
      const score = metric?.total_risk_score ?? 0
      return {
        regionCode,
        regionName,
        score,
        path: geometryToPath(feature.geometry, project),
      }
    })

    const healthcarePaths = (Array.isArray(healthcareAreas) ? healthcareAreas : []).map((area) => ({
      id: area.living_area_id,
      name: area.name,
      path: geometryToPath(area.geometry, project),
      note: area.geometry_note,
      representativeHospital: area.representative_hospital,
    }))

    const hospitalPoints = (Array.isArray(hospitals) ? hospitals : []).map((facility) => {
      const [x, y] = project([facility.longitude, facility.latitude])
      return { ...facility, x, y }
    })

    return { width, height, shapes, healthcarePaths, hospitalPoints }
  }, [regions, metricMap, healthcareAreas, hospitals])


  const clampZoom = useCallback((value) => Math.min(4, Math.max(1, value)), [])

  const zoomIn = useCallback(() => {
    setZoom((current) => clampZoom(Number((current * 1.2).toFixed(3))))
  }, [clampZoom])

  const zoomOut = useCallback(() => {
    setZoom((current) => clampZoom(Number((current / 1.2).toFixed(3))))
  }, [clampZoom])

  const resetView = useCallback(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
    dragRef.current = { active: false, startX: 0, startY: 0, originX: 0, originY: 0, moved: false }
    setIsDragging(false)
  }, [])

  const beginDrag = useCallback((event) => {
    dragRef.current = {
      active: true,
      startX: event.clientX,
      startY: event.clientY,
      originX: pan.x,
      originY: pan.y,
      moved: false,
    }
    setIsDragging(true)
  }, [pan.x, pan.y])

  const updateDrag = useCallback((event) => {
    if (!dragRef.current.active) return
    const deltaX = event.clientX - dragRef.current.startX
    const deltaY = event.clientY - dragRef.current.startY
    if (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3) {
      dragRef.current.moved = true
    }
    setPan({
      x: dragRef.current.originX + deltaX,
      y: dragRef.current.originY + deltaY,
    })
  }, [])

  const endDrag = useCallback(() => {
    dragRef.current.active = false
    setIsDragging(false)
  }, [])

  const handleWheel = useCallback((event) => {
    event.preventDefault()
    const scaleFactor = event.deltaY < 0 ? 1.04 : 1 / 1.04
    setZoom((current) => clampZoom(Number((current * scaleFactor).toFixed(3))))
  }, [clampZoom])

  const handleRegionSelect = useCallback((regionCode) => {
    if (dragRef.current.moved) return
    onSelectRegion(regionCode)
  }, [onSelectRegion])

  if (!prepared?.shapes?.length) {
    return (
      <section className="card map-card">
        <div className="card-head">
          <div>
            <h2>Prefecture Map</h2>
            <span>The map cannot be displayed because the GeoJSON could not be loaded.</span>
          </div>
        </div>
      </section>
    )
  }

  const { width, height, shapes, healthcarePaths, hospitalPoints } = prepared
  const hasHealthcareSlice = hospitalPoints.length > 0 || healthcarePaths.length > 0

  return (
    <section className="card map-card">
      <div className="card-head">
        <div>
          <h2>Prefecture Map</h2>
          <span>Click the map to select a prefecture and generate a policy memo.</span>
        </div>
      </div>

      <div className="map-toolbar">
        <div className="map-toolbar-actions">
          <button type="button" className="toggle-chip" onClick={zoomOut} aria-label="Zoom out">−</button>
          <button type="button" className="toggle-chip" onClick={zoomIn} aria-label="Zoom in">＋</button>
          <button type="button" className="toggle-chip" onClick={resetView}>Reset view</button>
        </div>
        <button type="button" className={showHospitals ? 'toggle-chip active' : 'toggle-chip'} onClick={onToggleHospitals} disabled={!hasHealthcareSlice}>
          Show hospitals
        </button>
        <button type="button" className={showHealthcareAreas ? 'toggle-chip active' : 'toggle-chip'} onClick={onToggleHealthcareAreas} disabled={!hasHealthcareSlice}>
          Show healthcare living areas
        </button>
        <span className="map-slice-note">Nationwide healthcare slice</span>
      </div>

      <div
        className={isDragging ? "map-shell is-dragging" : "map-shell"}
        onWheel={handleWheel}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="japan-map"
          role="img"
          aria-label="Prefecture risk map"
          onMouseDown={beginDrag}
          onMouseMove={updateDrag}
          onMouseUp={endDrag}
          onMouseLeave={endDrag}
        >
          <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
          {shapes.map((shape) => {
            const isActive = shape.regionCode === selectedRegionCode
            return (
              <path
                key={shape.regionCode}
                d={shape.path}
                className={isActive ? 'map-region active' : 'map-region'}
                fill={colorScale.color(shape.score)}
                onClick={() => handleRegionSelect(shape.regionCode)}
              >
                <title>{`${shape.regionName} | Total Risk ${shape.score.toFixed(3)}`}</title>
              </path>
            )
          })}

          {showHealthcareAreas ? healthcarePaths.map((area) => (
            <path key={area.id} d={area.path} className="living-area-path">
              <title>{`${area.name}${area.representativeHospital ? ` | Representative Hospital: ${area.representativeHospital}` : ''}`}</title>
            </path>
          )) : null}

          {showHospitals ? hospitalPoints.map((facility) => (
            <g key={facility.facility_id}>
              <circle cx={facility.x} cy={facility.y} r={Math.max(3.2, 5.5 / Math.sqrt(zoom))} className="hospital-dot" />
              <title>{`${facility.name} | ${facility.facility_type}`}</title>
            </g>
          )) : null}
          </g>
        </svg>
      </div>

      <div className="legend-row">
        <span>Low Risk</span>
        <div className="legend-bar" />
        <span>High Risk</span>
      </div>
      <p className="muted">Relative quantile scale: colorized at the lower 20% / 40% / 60% / 80% cutoffs.</p>
      <p className="muted">You can overlay the healthcare slice for the selected prefecture. Aomori Prefecture uses a real hospital subset, while other prefectures use geometry / metric-based proxy hubs for the nationwide demo. Drag to move and use the mouse wheel or buttons to zoom.</p>
    </section>
  )
}
