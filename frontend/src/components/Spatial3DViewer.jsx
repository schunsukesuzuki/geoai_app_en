import { useEffect, useMemo, useRef, useState } from 'react'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'

function centerFromBbox(bbox) {
  if (!bbox) return { lon: 139.767, lat: 35.681, height: 2000 }
  const minX = Number(bbox.min_x ?? bbox.west ?? 139.767)
  const maxX = Number(bbox.max_x ?? bbox.east ?? minX)
  const minY = Number(bbox.min_y ?? bbox.south ?? 35.681)
  const maxY = Number(bbox.max_y ?? bbox.north ?? minY)
  return {
    lon: (minX + maxX) / 2,
    lat: (minY + maxY) / 2,
    height: 2000,
  }
}

function dimensionsFromBbox(bbox, assetType) {
  if (!bbox) return new Cesium.Cartesian3(250, 250, assetType === 'mesh' ? 120 : 80)
  const minX = Number(bbox.min_x ?? bbox.west ?? 0)
  const maxX = Number(bbox.max_x ?? bbox.east ?? minX)
  const minY = Number(bbox.min_y ?? bbox.south ?? 0)
  const maxY = Number(bbox.max_y ?? bbox.north ?? minY)
  const center = centerFromBbox(bbox)
  const metersPerLon = 111320 * Math.cos(Cesium.Math.toRadians(center.lat))
  const width = Math.max(120, Math.abs(maxX - minX) * metersPerLon)
  const depth = Math.max(120, Math.abs(maxY - minY) * 111320)
  const height = assetType === 'mesh' ? 180 : 90
  return new Cesium.Cartesian3(width, depth, height)
}

function assetSummary(asset) {
  if (!asset) return 'No asset selected.'
  const mode = asset.metadata?.placeholder ? 'placeholder geometry from registry bbox' : 'registered asset'
  return `${asset.asset_type || 'asset'} / ${mode}`
}

export function Spatial3DViewer({ isVisible = false, selectedAsset = null, selectedEntityName = '', onClose = () => {} }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const [viewerError, setViewerError] = useState('')

  const displayName = useMemo(() => {
    if (!selectedAsset) return 'No selection'
    return selectedEntityName || selectedAsset.metadata?.label || selectedAsset.asset_id || 'Selected asset'
  }, [selectedAsset, selectedEntityName])

  useEffect(() => {
    if (!isVisible || !containerRef.current || viewerRef.current) return

    const viewer = new Cesium.Viewer(containerRef.current, {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      terrain: undefined,
      shouldAnimate: false,
    })

    viewer.scene.globe.enableLighting = true
    viewer.scene.skyAtmosphere.show = true
    viewerRef.current = viewer

    return () => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy()
      }
      viewerRef.current = null
    }
  }, [isVisible])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !selectedAsset || !isVisible) return

    setViewerError('')
    viewer.entities.removeAll()

    const center = centerFromBbox(selectedAsset.bbox)
    const position = Cesium.Cartesian3.fromDegrees(center.lon, center.lat, 0)
    const bboxDimensions = dimensionsFromBbox(selectedAsset.bbox, selectedAsset.asset_type)
    const placeholder = selectedAsset.metadata?.placeholder !== false

    if (!placeholder && selectedAsset.storage_uri && /\.(glb|gltf)$/i.test(selectedAsset.storage_uri)) {
      try {
        viewer.entities.add({
          name: displayName,
          position,
          model: {
            uri: selectedAsset.storage_uri,
            minimumPixelSize: 72,
            maximumScale: 5000,
          },
          label: {
            text: displayName,
            font: '14px sans-serif',
            showBackground: true,
            backgroundColor: Cesium.Color.fromAlpha(Cesium.Color.BLACK, 0.65),
            fillColor: Cesium.Color.WHITE,
            horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            pixelOffset: new Cesium.Cartesian2(0, -24),
          },
        })
      } catch (err) {
        setViewerError(err?.message || 'Failed to load 3D model. Falling back to placeholder geometry.')
      }
    }

    if (viewer.entities.values.length === 0) {
      viewer.entities.add({
        name: displayName,
        position,
        box: {
          dimensions: bboxDimensions,
          material: selectedAsset.asset_type === 'mesh'
            ? Cesium.Color.fromCssColorString('#60a5fa').withAlpha(0.72)
            : Cesium.Color.fromCssColorString('#34d399').withAlpha(0.72),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString('#0f172a'),
        },
        label: {
          text: `${displayName}\n${assetSummary(selectedAsset)}`,
          font: '14px sans-serif',
          showBackground: true,
          backgroundColor: Cesium.Color.fromAlpha(Cesium.Color.BLACK, 0.68),
          fillColor: Cesium.Color.WHITE,
          horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(0, -40),
        },
      })
    }

    viewer.flyTo(viewer.entities, {
      duration: 0.8,
      offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-28), Math.max(bboxDimensions.x, bboxDimensions.y) * 4),
    })
  }, [selectedAsset, isVisible, displayName])

  if (!isVisible) return null

  return (
    <section className="card viewer3d-card">
      <div className="panel-card-header viewer3d-head">
        <div>
          <h2>3D Viewer</h2>
          <p className="muted viewer3d-subtitle">CesiumJS side viewer for selected registered assets.</p>
        </div>
        <button type="button" className="secondary-btn" onClick={onClose}>Close 3D View</button>
      </div>
      <div className="viewer3d-meta">
        <div><label>Entity</label><strong>{displayName}</strong></div>
        <div><label>Asset type</label><strong>{selectedAsset?.asset_type || '—'}</strong></div>
        <div><label>Version</label><strong>{selectedAsset?.version || '—'}</strong></div>
        <div><label>Last observed</label><strong>{selectedAsset?.observed_at || '—'}</strong></div>
        <div><label>Source system</label><strong>{selectedAsset?.source_system || '—'}</strong></div>
        <div><label>Rendering mode</label><strong>{selectedAsset?.metadata?.placeholder ? 'bbox placeholder geometry' : 'registered 3D asset'}</strong></div>
      </div>
      {viewerError ? <div className="error-banner">{viewerError}</div> : null}
      <div ref={containerRef} className="viewer3d-container" />
    </section>
  )
}
