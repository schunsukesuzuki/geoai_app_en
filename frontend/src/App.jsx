import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ScenarioSelect } from './components/ScenarioSelect'
import { OverviewCards } from './components/OverviewCards'
import { RegionHeatGrid } from './components/RegionHeatGrid'
import { RegionGeoMap } from './components/RegionGeoMap'
import { RankingTable } from './components/RankingTable'
import { DetailPanel } from './components/DetailPanel'
import { ScenarioComparisonPanel } from './components/ScenarioComparisonPanel'
import { RecommendationReasonPanel } from './components/RecommendationReasonPanel'
import { DecisionBar } from './components/DecisionBar'
import { ExportPanel } from './components/ExportPanel'
import { Spatial3DViewer } from './components/Spatial3DViewer'

function AppBody() {
  const [scenario, setScenario] = useState('baseline')
  const [health, setHealth] = useState(null)
  const [modelInfo, setModelInfo] = useState(null)
  const [regions, setRegions] = useState(null)
  const [metrics, setMetrics] = useState([])
  const [selectedRegionCode, setSelectedRegionCode] = useState('')
  const [reasoning, setReasoning] = useState(null)
  const [summaryState, setSummaryState] = useState({ summary: '', source: '', model: '', error: '' })
  const [scenarios, setScenarios] = useState([])
  const [comparison, setComparison] = useState([])
  const [selectedScenarioId, setSelectedScenarioId] = useState('baseline')
  const [explanation, setExplanation] = useState(null)
  const [agentExplanation, setAgentExplanation] = useState(null)
  const [agentRuns, setAgentRuns] = useState([])
  const [auditEvents, setAuditEvents] = useState([])
  const [auditChain, setAuditChain] = useState(null)
  const [latestDecision, setLatestDecision] = useState(null)
  const [decisions, setDecisions] = useState([])
  const [report, setReport] = useState(null)
  const [loadingPage, setLoadingPage] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState('')
  const [showHospitals, setShowHospitals] = useState(true)
  const [showHealthcareAreas, setShowHealthcareAreas] = useState(true)
  const [hospitals, setHospitals] = useState([])
  const [healthcareAreas, setHealthcareAreas] = useState([])
  const [healthcareAccessibilitySummary, setHealthcareAccessibilitySummary] = useState(null)
  const [healthcarePriorities, setHealthcarePriorities] = useState([])
  const [featureRefreshCandidates, setFeatureRefreshCandidates] = useState([])
  const [selectedYear, setSelectedYear] = useState(2025)
  const [availableYears, setAvailableYears] = useState([2025, 2030, 2035, 2040])
  const [spatialAssets, setSpatialAssets] = useState([])
  const [spatialAssetBindings, setSpatialAssetBindings] = useState([])
  const [spatialAssetBindingSummary, setSpatialAssetBindingSummary] = useState({ hospital: 0, healthcare: 0 })
  const [is3DViewerOpen, setIs3DViewerOpen] = useState(false)
  const [selected3DAsset, setSelected3DAsset] = useState(null)
  const [selected3DEntityName, setSelected3DEntityName] = useState('')

  useEffect(() => {
    let alive = true
    async function loadStatic() {
      try {
        const [healthRes, modelInfoRes, regionsRes] = await Promise.all([api.health(), api.modelInfo(), api.regions()])
        if (!alive) return
        setHealth(healthRes)
        setModelInfo(modelInfoRes)
        setRegions(regionsRes)
      } catch (err) {
        if (!alive) return
        setError(err.message)
        setHealth({ status: 'error', openai: { configured: false, model: '' } })
      }
    }
    loadStatic()
    return () => { alive = false }
  }, [])

  useEffect(() => {
    let alive = true
    setLoadingPage(true)
    setError('')
    async function loadMetrics() {
      try {
        const res = await api.metrics(scenario)
        if (!alive) return
        const items = Array.isArray(res.items) ? res.items : []
        setMetrics(items)
        const defaultCode = items[0]?.region_code || ''
        setSelectedRegionCode((prev) => items.some((x) => x.region_code === prev) ? prev : defaultCode)
      } catch (err) {
        if (!alive) return
        setError(err.message)
        setMetrics([])
        setSelectedRegionCode('')
      } finally {
        if (alive) setLoadingPage(false)
      }
    }
    loadMetrics()
    return () => { alive = false }
  }, [scenario])

  useEffect(() => {
    if (!selectedRegionCode) return
    let alive = true
    setLoadingDetail(true)
    setSummaryState({ summary: '', source: '', model: '', error: '' })
    async function loadDetail() {
      try {
        const [reasoningRes, summaryRes, scenarioRes, decisionRes] = await Promise.all([
          api.reasoning(selectedRegionCode, scenario),
          api.summary(selectedRegionCode, scenario).catch((err) => ({ error: err.message })),
          api.generateScenarios(selectedRegionCode),
          api.listDecisions(selectedRegionCode),
        ])
        if (!alive) return
        setReasoning(reasoningRes)
        setSummaryState(summaryRes.error ? { summary: '', source: '', model: '', error: summaryRes.error } : { summary: summaryRes.summary || '', source: summaryRes.source || '', model: summaryRes.model || '', error: '' })
        setScenarios(scenarioRes.scenarios || [])
        setComparison([])
        setSelectedScenarioId(scenario)
        setDecisions(decisionRes.items || [])
      } catch (err) {
        if (!alive) return
        setError(err.message)
      } finally {
        if (alive) setLoadingDetail(false)
      }
    }
    loadDetail()
    return () => { alive = false }
  }, [selectedRegionCode, scenario])

  useEffect(() => {
    if (!selectedRegionCode || scenarios.length === 0) return
    let alive = true
    async function loadWorkflow() {
      try {
        const candidateIds = scenarios.map((s) => s.scenario_id)
        const [compareRes, explanationRes, agentRes, agentRunsRes] = await Promise.all([
          api.compareScenarios(selectedRegionCode, 'baseline', candidateIds),
          api.explanation(selectedRegionCode, selectedScenarioId),
          api.explainScenarioAgent(selectedRegionCode, 'baseline', selectedScenarioId),
          api.listAgentRuns(selectedRegionCode, 10),
        ])
        if (!alive) return
        setComparison(compareRes.comparisons || [])
        setExplanation(explanationRes)
        setAgentExplanation(agentRes)
        setAgentRuns(agentRunsRes.items || [])
      } catch (err) {
        if (!alive) return
        setError(err.message)
      }
    }
    loadWorkflow()
    return () => { alive = false }
  }, [selectedRegionCode, scenarios, selectedScenarioId])

  useEffect(() => {
    let alive = true
    async function loadSpatialLayers() {
      if (!selectedRegionCode) {
        setHospitals([])
        setHealthcareAreas([])
        return
      }

      setHospitals([])
      setHealthcareAreas([])

      try {
        const [facilitiesRes, livingAreasRes] = await Promise.all([
          api.fetchFacilities(selectedRegionCode, 'hospital'),
          api.fetchLivingAreas(selectedRegionCode, 'healthcare'),
        ])
        if (!alive) return
        setHospitals(facilitiesRes.items || [])
        setHealthcareAreas(livingAreasRes.items || [])
      } catch (err) {
        if (!alive) return
        setError(err.message)
        setHospitals([])
        setHealthcareAreas([])
      }
    }
    loadSpatialLayers()
    return () => { alive = false }
  }, [selectedRegionCode])


  useEffect(() => {
    let alive = true
    async function loadSpatialAssets() {
      if (!selectedRegionCode) {
        setIs3DViewerOpen(false)
        setSelected3DAsset(null)
        setSelected3DEntityName('')
        setSpatialAssets([])
        setSpatialAssetBindings([])
        setSpatialAssetBindingSummary({ hospital: 0, healthcare: 0 })
        return
      }
      try {
        const assetsRes = await api.fetchSpatialAssets(selectedRegionCode)
        if (!alive) return
        const assets = assetsRes.items || []
        setSpatialAssets(assets)

        const firstHospital = hospitals?.[0]?.facility_id
        const firstHealthcareArea = healthcareAreas?.[0]?.living_area_id
        const bindingRequests = []
        if (firstHospital) {
          bindingRequests.push(api.fetchSpatialAssetBindings(firstHospital).catch(() => ({ items: [] })))
        }
        if (firstHealthcareArea) {
          bindingRequests.push(api.fetchSpatialAssetBindings(firstHealthcareArea).catch(() => ({ items: [] })))
        }

        if (bindingRequests.length) {
          const responses = await Promise.all(bindingRequests)
          if (!alive) return
          const merged = responses.flatMap((res) => res.items || [])
          setSpatialAssetBindings(merged)
          const hospitalCount = merged.filter((item) => item?.metadata?.entity_type === 'hospital' || item?.binding_type === 'primary_visual').length
          const healthcareCount = merged.filter((item) => item?.metadata?.entity_type === 'healthcare_living_area' || item?.binding_type === 'context_mesh').length
          setSpatialAssetBindingSummary({ hospital: hospitalCount, healthcare: healthcareCount })
        } else {
          setSpatialAssetBindings([])
          setSpatialAssetBindingSummary({ hospital: 0, healthcare: 0 })
        }
      } catch (err) {
        if (!alive) return
        setError(err.message)
        setSpatialAssets([])
        setSpatialAssetBindings([])
        setSpatialAssetBindingSummary({ hospital: 0, healthcare: 0 })
      }
    }
    loadSpatialAssets()
    return () => { alive = false }
  }, [selectedRegionCode, hospitals, healthcareAreas])

  useEffect(() => {
    let alive = true
    async function loadHealthcareTimeline() {
      if (!selectedRegionCode) {
        setHealthcareAccessibilitySummary(null)
        setHealthcarePriorities([])
        setAvailableYears([2025, 2030, 2035, 2040])
        return
      }

      setHealthcarePriorities([])
      setHealthcareAccessibilitySummary({
        prefecture_code: selectedRegionCode,
        data_available: null,
        loading: true,
        year: selectedYear,
      })

      try {
        const timelineRes = await api.fetchHealthcareTimeline(selectedRegionCode, selectedYear)
        if (!alive) return
        setAvailableYears(timelineRes.available_years || [2025, 2030, 2035, 2040])
        setHealthcareAccessibilitySummary({ ...(timelineRes.summary || {}), loading: false, year: timelineRes.year })
        setHealthcarePriorities(timelineRes.items || [])
      } catch (err) {
        if (!alive) return
        setError(err.message)
        setHealthcarePriorities([])
        setHealthcareAccessibilitySummary({
          prefecture_code: selectedRegionCode,
          data_available: false,
          loading: false,
          year: selectedYear,
          error: err.message,
        })
      }
    }
    loadHealthcareTimeline()
    return () => { alive = false }
  }, [selectedRegionCode, selectedYear])

  useEffect(() => {
    let alive = true
    async function loadFeatureRefreshCandidates() {
      if (!selectedRegionCode) {
        setFeatureRefreshCandidates([])
        return
      }
      try {
        const res = await api.fetchFeatureRefreshCandidates(selectedRegionCode, 'hospital')
        if (!alive) return
        setFeatureRefreshCandidates(res.items || [])
      } catch (err) {
        if (!alive) return
        setError(err.message)
        setFeatureRefreshCandidates([])
      }
    }
    loadFeatureRefreshCandidates()
    return () => { alive = false }
  }, [selectedRegionCode])

  useEffect(() => {
    let alive = true
    async function loadAudit() {
      if (!selectedRegionCode) {
        setAuditEvents([])
        setAuditChain(null)
        return
      }
      try {
        const decisionId = latestDecision?.decision_id || decisions?.[0]?.decision_id || ''
        const eventsRes = await api.listAuditEvents(selectedRegionCode, decisionId, 20)
        if (!alive) return
        setAuditEvents(eventsRes.items || [])
        if (decisionId) {
          const chainRes = await api.fetchAuditChain('decision', decisionId)
          if (!alive) return
          setAuditChain(chainRes)
        } else {
          setAuditChain(null)
        }
      } catch (err) {
        if (!alive) return
        setError(err.message)
        setAuditEvents([])
        setAuditChain(null)
      }
    }
    loadAudit()
    return () => { alive = false }
  }, [selectedRegionCode, latestDecision, decisions])

  const selectedItem = useMemo(() => metrics.find((item) => item.region_code === selectedRegionCode) || null, [metrics, selectedRegionCode])
  const selectedScenarioName = useMemo(() => scenarios.find((s) => s.scenario_id === selectedScenarioId)?.name || selectedScenarioId, [scenarios, selectedScenarioId])


  const sampleHospitalAsset = useMemo(() => spatialAssets.find((asset) => asset.asset_type === 'glb' && asset.entity_type === 'hospital') || null, [spatialAssets])
  const sampleHealthcareAsset = useMemo(() => spatialAssets.find((asset) => (asset.asset_type === 'mesh' || asset.asset_type === 'glb' || asset.asset_type === 'gltf') && asset.entity_type === 'healthcare_living_area') || null, [spatialAssets])

  function open3DAsset(asset, fallbackLabel = '') {
    if (!asset) return
    setSelected3DAsset(asset)
    setSelected3DEntityName(asset.metadata?.label || fallbackLabel || asset.asset_id || 'Selected asset')
    setIs3DViewerOpen(true)
  }

  async function handleSubmitDecision(payload) {
    try {
      const res = await api.createDecision(payload)
      setLatestDecision(res)
      const refreshed = await api.listDecisions(selectedRegionCode)
      setDecisions(refreshed.items || [])
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleGenerateReport() {
    try {
      const decisionId = latestDecision?.decision_id || decisions[0]?.decision_id
      if (!decisionId) return
      const res = await api.generateReport(decisionId)
      setReport(res)
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleReviewFeatureRefreshCandidate(candidateId, decision) {
    try {
      await api.reviewFeatureRefreshCandidate({ candidate_id: candidateId, decision, reviewer_comment: '' })
      const refreshed = await api.fetchFeatureRefreshCandidates(selectedRegionCode, 'hospital')
      setFeatureRefreshCandidates(refreshed.items || [])
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">React + FastAPI + Docker Compose</p>
          <h1>Regional Risk Simulator</h1>
          <p className="hero-copy">An extended minimal workflow for prefecture-level compound risk across population decline, aging, vacant housing, and healthcare access: forecast -> compare -> explain -> approve -> export.</p>
        </div>
        <div className="hero-controls">
          <ScenarioSelect value={scenario} onChange={setScenario} />
          <div className="health-pill">API: {health?.status || 'checking'}</div>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}
      {loadingPage ? <div className="loading-banner">Loading data...</div> : null}

      <OverviewCards modelInfo={modelInfo} selectedItem={selectedItem} health={health} />

      <div className="content-grid">
        <RegionGeoMap
          regions={regions}
          metrics={metrics}
          selectedRegionCode={selectedRegionCode}
          onSelectRegion={setSelectedRegionCode}
          showHospitals={showHospitals}
          showHealthcareAreas={showHealthcareAreas}
          onToggleHospitals={() => setShowHospitals((v) => !v)}
          onToggleHealthcareAreas={() => setShowHealthcareAreas((v) => !v)}
          hospitals={hospitals}
          healthcareAreas={healthcareAreas}
        />
        <DetailPanel item={selectedItem} reasoning={reasoning} summaryState={summaryState} loadingSummary={loadingDetail} healthcareSpatialSummary={healthcareAccessibilitySummary} healthcarePriorities={healthcarePriorities} featureRefreshCandidates={featureRefreshCandidates} onReviewFeatureRefreshCandidate={handleReviewFeatureRefreshCandidate} selectedYear={selectedYear} availableYears={availableYears} onYearChange={setSelectedYear} spatialAssets={spatialAssets} spatialAssetBindings={spatialAssetBindings} spatialAssetBindingSummary={spatialAssetBindingSummary} hospitals={hospitals} healthcareAreas={healthcareAreas} sampleHospitalAsset={sampleHospitalAsset} sampleHealthcareAsset={sampleHealthcareAsset} onOpenHospital3D={() => open3DAsset(sampleHospitalAsset, 'Sample hospital')} onOpenHealthcare3D={() => open3DAsset(sampleHealthcareAsset, 'Healthcare context')} is3DViewerOpen={is3DViewerOpen} />
      </div>

      <Spatial3DViewer
        isVisible={is3DViewerOpen}
        selectedAsset={selected3DAsset}
        selectedEntityName={selected3DEntityName}
        onClose={() => setIs3DViewerOpen(false)}
      />

      <ScenarioComparisonPanel scenarios={scenarios} comparison={comparison} selectedScenarioId={selectedScenarioId} onSelectScenario={setSelectedScenarioId} />

      <div className="content-grid">
        <RecommendationReasonPanel explanation={explanation} agentExplanation={agentExplanation} agentRuns={agentRuns} selectedScenarioName={selectedScenarioName} auditEvents={auditEvents} auditChain={auditChain} />
        <DecisionBar regionId={selectedRegionCode} selectedScenarioId={selectedScenarioId} onSubmitDecision={handleSubmitDecision} latestDecision={latestDecision} />
      </div>

      <ExportPanel report={report} onGenerateReport={handleGenerateReport} decisions={decisions} />

      <div className="content-grid secondary-grid">
        <RegionHeatGrid items={metrics} selectedRegionCode={selectedRegionCode} onSelectRegion={setSelectedRegionCode} />
        <RankingTable items={metrics} selectedRegionCode={selectedRegionCode} onSelectRegion={setSelectedRegionCode} />
      </div>
    </div>
  )
}

export default function App() {
  return (<ErrorBoundary><AppBody /></ErrorBoundary>)
}
