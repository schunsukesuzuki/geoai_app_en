const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

  if (!response.ok) {
    let message = `Request failed: ${response.status}`
    try {
      const data = await response.json()
      if (data?.detail) message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {}
    throw new Error(message)
  }
  return response.json()
}

export const api = {
  health: () => request('/api/health'),
  modelInfo: () => request('/api/model-info'),
  regions: () => request('/api/regions'),
  metrics: (scenario) => request(`/api/metrics?scenario=${encodeURIComponent(scenario)}`),
  reasoning: (regionCode, scenario) => request(`/api/reasoning?region_code=${encodeURIComponent(regionCode)}&scenario=${encodeURIComponent(scenario)}`),
  summary: (regionCode, scenario) => request('/api/summary', { method: 'POST', body: JSON.stringify({ region_code: regionCode, scenario }) }),
  generateScenarios: (regionId, policy_focus = 'balanced', budget_level = 'medium', constraints = {}) =>
    request('/api/scenarios/generate', { method: 'POST', body: JSON.stringify({ region_id: regionId, policy_focus, budget_level, constraints }) }),
  compareScenarios: (regionId, baselineScenarioId, candidateScenarioIds) =>
    request('/api/scenarios/compare', { method: 'POST', body: JSON.stringify({ region_id: regionId, baseline_scenario_id: baselineScenarioId, candidate_scenario_ids: candidateScenarioIds }) }),
  explanation: (regionId, scenarioId) => request(`/api/explanations/${encodeURIComponent(scenarioId)}?region_id=${encodeURIComponent(regionId)}`),
  explainScenarioAgent: (regionId, baselineScenarioId, candidateScenarioId) =>
    request('/api/agents/explain-scenario', { method: 'POST', body: JSON.stringify({ region_id: regionId, baseline_scenario_id: baselineScenarioId, candidate_scenario_id: candidateScenarioId }) }),
  listAgentRuns: (regionId, limit = 20) => request(`/api/agents/runs?${regionId ? `region_id=${encodeURIComponent(regionId)}&` : ''}limit=${encodeURIComponent(limit)}`),
  createDecision: (payload) => request('/api/decisions', { method: 'POST', body: JSON.stringify(payload) }),
  listDecisions: (regionId) => request(`/api/decisions${regionId ? `?region_id=${encodeURIComponent(regionId)}` : ''}`),

  fetchFacilities: (prefectureCode, type = "hospital") => request(`/api/facilities?prefecture=${encodeURIComponent(prefectureCode)}&type=${encodeURIComponent(type)}`),
  fetchLivingAreas: (prefectureCode, type = "healthcare") => request(`/api/living-areas?prefecture=${encodeURIComponent(prefectureCode)}&type=${encodeURIComponent(type)}`),
  fetchAccessibilitySummary: (prefectureCode, facilityType = "hospital") => request(`/api/accessibility/summary?prefecture=${encodeURIComponent(prefectureCode)}&facility_type=${encodeURIComponent(facilityType)}`),
  fetchHealthcarePriorities: (prefectureCode) => request(`/api/healthcare-priorities?prefecture=${encodeURIComponent(prefectureCode)}`),
  fetchHealthcareTimeline: (prefectureCode, year = 2025) => request(`/api/healthcare-timeline?prefecture=${encodeURIComponent(prefectureCode)}&year=${encodeURIComponent(year)}`),
  fetchSpatialAssets: (prefectureCode, entityType = '', assetType = '') => request(`/api/spatial-assets?prefecture=${encodeURIComponent(prefectureCode)}${entityType ? `&entity_type=${encodeURIComponent(entityType)}` : ''}${assetType ? `&asset_type=${encodeURIComponent(assetType)}` : ''}`),
  fetchSpatialAssetBindings: (entityId) => request(`/api/spatial-assets/bindings?entity_id=${encodeURIComponent(entityId)}`),
  fetchFeatureRefreshCandidates: (prefectureCode, featureType = 'hospital') => request(`/api/feature-refresh/candidates?prefecture=${encodeURIComponent(prefectureCode)}&feature_type=${encodeURIComponent(featureType)}`),
  reviewFeatureRefreshCandidate: (payload) => request('/api/feature-refresh/review', { method: 'POST', body: JSON.stringify(payload) }),
  listAuditEvents: (prefectureCode = '', decisionId = '', limit = 50) => request(`/api/audit/events?${prefectureCode ? `prefecture=${encodeURIComponent(prefectureCode)}&` : ''}${decisionId ? `decision_id=${encodeURIComponent(decisionId)}&` : ''}limit=${encodeURIComponent(limit)}`),
  fetchAuditChain: (entityType, entityId) => request(`/api/audit/chain?entity_type=${encodeURIComponent(entityType)}&entity_id=${encodeURIComponent(entityId)}`),
  fetchAuditSnapshot: (snapshotId) => request(`/api/audit/snapshot?snapshot_id=${encodeURIComponent(snapshotId)}`),
  generateReport: (decisionId, format = 'memo', audience = 'municipal_executive') =>
    request('/api/reports/generate', { method: 'POST', body: JSON.stringify({ decision_id: decisionId, format, audience }) }),
}
