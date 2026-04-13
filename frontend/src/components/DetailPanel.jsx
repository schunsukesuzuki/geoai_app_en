function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`
}

function fmtNumber(value, digits = 1) {
  return value === null || value === undefined || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(digits)
}

function labelMeta(label) {
  if (label === 'reinvest') return { text: 'reinvest', className: 'priority-pill reinvest' }
  if (label === 'shrink_candidate') return { text: 'shrink candidate', className: 'priority-pill shrink' }
  return { text: 'maintain', className: 'priority-pill maintain' }
}

export function DetailPanel({ item, reasoning, summaryState, loadingSummary, healthcareSpatialSummary = null, healthcarePriorities = [], featureRefreshCandidates = [], onReviewFeatureRefreshCandidate = () => {}, selectedYear = 2025, availableYears = [2025, 2030, 2035, 2040], onYearChange = () => {}, spatialAssets = [], spatialAssetBindings = [], spatialAssetBindingSummary = { hospital: 0, healthcare: 0 }, hospitals = [], healthcareAreas = [], sampleHospitalAsset = null, sampleHealthcareAsset = null, onOpenHospital3D = () => {}, onOpenHealthcare3D = () => {}, is3DViewerOpen = false }) {
  if (!item) {
    return <section className="card"><p className="muted">Please select a region.</p></section>
  }

  const comparisonRows = reasoning?.comparison?.scenario_comparison || []
  const hasHealthcareSpatialSummary = Boolean(healthcareSpatialSummary)
  const spatialDataAvailable = healthcareSpatialSummary?.data_available !== false
  const spatialLoading = healthcareSpatialSummary?.loading === true
  const summaryMatchesSelection = !healthcareSpatialSummary?.prefecture_code || healthcareSpatialSummary?.prefecture_code === item.region_code
  const currentHospitalIds = new Set((hospitals || []).map((row) => row.facility_id).filter(Boolean))
  const currentHealthcareAreaIds = new Set((healthcareAreas || []).map((row) => row.living_area_id).filter(Boolean))
  const currentHospitalBindings = (spatialAssetBindings || []).filter((row) => currentHospitalIds.has(row.entity_id))
  const currentHealthcareBindings = (spatialAssetBindings || []).filter((row) => currentHealthcareAreaIds.has(row.entity_id))
  const boundAssetIds = new Set((spatialAssetBindings || []).map((row) => row.asset_id).filter(Boolean))
  const hospitalGlbAssets = spatialAssets.filter((asset) => asset.asset_type === "glb" && asset.entity_type === "hospital")
  const contextMeshAssets = spatialAssets.filter((asset) => asset.asset_type === "mesh" && asset.entity_type === "healthcare_living_area")
  const pointCloudAssets = spatialAssets.filter((asset) => asset.asset_type === "point_cloud")
  const lastObserved = spatialAssets.map((asset) => asset.observed_at).filter(Boolean).sort().slice(-1)[0] || null
  const registryStatus = spatialAssets.length ? 'registered' : 'not registered'
  return (
    <section className="card detail-panel">
      <div className="card-head"><h2>{item.region_name} Details</h2><span>Drivers, comparison, and memo</span></div>
      <div className="kpi-grid">
        <div className="kpi"><label>Expected Risk</label><strong>{item.total_risk_score.toFixed(3)}</strong></div>
        <div className="kpi"><label>p90</label><strong>{item.risk_distribution?.p90?.toFixed?.(3) ?? '-'}</strong></div>
        <div className="kpi"><label>Uncertainty</label><strong>{reasoning?.uncertainty?.overall_label || item.uncertainty?.overall_label || '-'}</strong></div>
        <div className="kpi"><label>2035 Population</label><strong>{Number(item.population_2035).toLocaleString()}</strong></div>
      </div>

      <div className="detail-block">
        <h3>Key Drivers</h3>
        <ul>
          {(reasoning?.primary_factors || []).map((factor) => (
            <li key={factor.key}>{factor.factor}: Value {factor.value.toFixed(3)} / Weighted {factor.weighted.toFixed(3)}</li>
          ))}
        </ul>
      </div>

      <div className="detail-block">
        <h3>Base Metrics</h3>
        <div className="metric-grid compact">
          <div><label>Aging Rate</label><strong>{pct(item.aging_rate)}</strong></div>
          <div><label>Vacancy Rate</label><strong>{pct(item.vacancy_rate)}</strong></div>
          <div><label>Depopulation Index</label><strong>{item.depopulation_index.toFixed(3)}</strong></div>
          <div><label>Healthcare Access</label><strong>{item.medical_access_risk.toFixed(3)}</strong></div>
          <div><label>Family Support Access</label><strong>{item.childcare_access_score.toFixed(3)}</strong></div>
          <div><label>Annual Decline Rate</label><strong>{pct(item.predicted_annual_decline_rate)}</strong></div>
        </div>
      </div>



      <div className="detail-block">
        <div className="timeline-head">
          <h3>Healthcare Timeline</h3>
          <div className="control inline-control">
            <label>Year</label>
            <select value={selectedYear} onChange={(e) => onYearChange(Number(e.target.value))}>
              {availableYears.map((year) => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </div>
        </div>
        <p className="muted">Shows the healthcare state and prioritization for the selected year.</p>
      </div>

      {hasHealthcareSpatialSummary ? (
        <div className="detail-block">
          <h3>Healthcare Spatial Summary {healthcareSpatialSummary?.prefecture_name ? `(${healthcareSpatialSummary.prefecture_name})` : `(${item.region_name})`} / {selectedYear}</h3>
          {spatialLoading || !summaryMatchesSelection ? (
            <p className="muted">Loading the healthcare slice for the selected prefecture.</p>
          ) : spatialDataAvailable ? (
            <>
              <div className="metric-grid compact spatial-grid">
                <div><label>Hospital count</label><strong>{healthcareSpatialSummary?.facility_count ?? '—'}</strong></div>
                <div><label>Coverage ratio (30m)</label><strong>{healthcareSpatialSummary?.covered_population_ratio == null ? '—' : pct(healthcareSpatialSummary.covered_population_ratio)}</strong></div>
                <div><label>Avg travel time</label><strong>{healthcareSpatialSummary?.avg_travel_time_min == null ? '—' : `${fmtNumber(healthcareSpatialSummary.avg_travel_time_min, 1)} min`}</strong></div>
                <div><label>p90 travel time</label><strong>{healthcareSpatialSummary?.p90_travel_time_min == null ? '—' : `${fmtNumber(healthcareSpatialSummary.p90_travel_time_min, 1)} min`}</strong></div>
                <div><label>Underserved sampled cells</label><strong>{healthcareSpatialSummary?.underserved_origin_count ?? '—'}</strong></div>
                <div><label>Origin model</label><strong className="detail-body-text">{healthcareSpatialSummary?.origin_type || '—'}</strong></div>
              </div>
              <p className="muted">{healthcareSpatialSummary?.origin_type === 'municipality_centroid_road_network_timeline' ? 'The healthcare slice is shown as a year-indexed state. It is a timeline that applies maintain / reinvest / shrink_candidate actions forward from the 2025 baseline.' : (healthcareSpatialSummary?.origin_type === 'sampled_origin_graph_proxy' ? 'For the nationwide demo, nearest-hospital travel time is approximated with a simple graph built from prefecture polygons and hospital points. Aomori Prefecture keeps a real hospital subset.' : (healthcareSpatialSummary?.data_basis === 'real_hospital_subset_plus_official_medical_area_names' ? 'Aomori Prefecture uses a slice based on a real hospital subset and official healthcare-area names.' : 'For the nationwide demo, prefectures other than Aomori use proxy healthcare slices generated from prefecture polygons and the existing medical_access_risk indicator.'))}</p>
            </>
          ) : (
            <p className="muted">{healthcareSpatialSummary?.error || 'Healthcare spatial slice not yet available for this prefecture.'}</p>
          )}
        </div>
      ) : null}

      <div className="detail-block">
        <h3>Healthcare Prioritization / {selectedYear}</h3>
        {healthcarePriorities?.length ? (
          <div className="table-wrap small">
            <table>
              <thead>
                <tr>
                  <th>Living area</th>
                  <th>Label</th>
                  <th>Action</th>
                  <th>Score</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {healthcarePriorities.map((row) => {
                  const meta = labelMeta(row.priority_label)
                  return (
                    <tr key={row.living_area_id}>
                      <td>{row.name || row.living_area_id}</td>
                      <td><span className={meta.className}>{meta.text}</span></td>
                      <td><span className="priority-action">{row.applied_action || row.priority_label}</span></td>
                      <td>{fmtNumber(row.priority_score, 3)}</td>
                      <td><div>{row.summary_reason}</div><div className="muted small-text">{(row.rationale_tags || []).join(', ') || '—'}</div></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">Healthcare prioritization not yet available for this prefecture.</p>
        )}
      </div>

      <div className="detail-block">
        <h3>3D / Reality Assets</h3>
        <div className="metric-grid compact spatial-grid">
          <div><label>Hospital GLB assets</label><strong>{hospitalGlbAssets.length ? `${hospitalGlbAssets.length} available` : 'unavailable'}</strong></div>
          <div><label>Healthcare context mesh</label><strong>{contextMeshAssets.length ? `${contextMeshAssets.length} available` : 'unavailable'}</strong></div>
          <div><label>Point cloud</label><strong>{pointCloudAssets.length ? `${pointCloudAssets.length} available` : 'unavailable'}</strong></div>
          <div><label>Last observed</label><strong className="detail-body-text">{lastObserved || '—'}</strong></div>
          <div><label>Asset bindings (sample hospital)</label><strong>{currentHospitalBindings.length || spatialAssetBindingSummary.hospital || 0}</strong></div>
          <div><label>Healthcare bindings</label><strong>{currentHealthcareBindings.length || spatialAssetBindingSummary.healthcare || 0}</strong></div>
          <div><label>Asset registry status</label><strong className="detail-body-text">{registryStatus}</strong></div>
        </div>
        <div className="asset-actions">
          <button type="button" className="secondary-btn" disabled={!sampleHospitalAsset} onClick={onOpenHospital3D}>Open sample hospital 3D</button>
          <button type="button" className="secondary-btn" disabled={!sampleHealthcareAsset} onClick={onOpenHealthcare3D}>Open healthcare 3D</button>
          {is3DViewerOpen ? <span className="muted small-text">3D viewer is open.</span> : null}
        </div>
        <p className="muted">Bindings between current 2D entities and 3D / reality assets are managed through the registry. In the CesiumJS viewer, sample hospital / healthcare assets tied to the selected prefecture can be shown in the side panel. If GLB or mesh assets are placeholders, simple 3D geometry is drawn from the registry bounding box.</p>
      </div>

      <div className="detail-block">
        <h3>Feature Refresh Candidates</h3>
        {featureRefreshCandidates?.length ? (
          <div className="table-wrap small">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Confidence</th>
                  <th>Reason</th>
                  <th>Status</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {featureRefreshCandidates.map((row) => (
                  <tr key={row.candidate_id}>
                    <td>{row.candidate_type}</td>
                    <td>{fmtNumber(row.confidence, 3)}</td>
                    <td><div>{row.summary_reason}</div><div className="muted small-text">{(row.reason_tags || []).join(', ') || '—'}</div></td>
                    <td><span className={`refresh-status ${row.status || 'pending'}`}>{row.status || 'pending'}</span></td>
                    <td>
                      <div className="refresh-actions">
                        <button type="button" disabled={row.status === 'approved'} onClick={() => onReviewFeatureRefreshCandidate(row.candidate_id, 'approved')}>Approve</button>
                        <button type="button" className="secondary" disabled={row.status === 'rejected'} onClick={() => onReviewFeatureRefreshCandidate(row.candidate_id, 'rejected')}>Reject</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No pending healthcare feature refresh candidates for this prefecture.</p>
        )}
      </div>

      <div className="detail-block">
        <h3>Major Shocks</h3>
        <ul>
          {(reasoning?.shock_sensitivity || item.shock_sensitivity || []).slice(0, 3).map((shock) => (
            <li key={shock.shock_key}>{shock.shock_label}: Score {shock.score.toFixed(3)} / Expected Uplift {shock.expected_risk_uplift.toFixed(3)}</li>
          ))}
        </ul>
      </div>

      <div className="detail-block">
        <h3>Scenario Comparison</h3>
        <div className="table-wrap small">
          <table>
            <thead>
              <tr>
                <th>Scenario</th>
                <th>Expected Value</th>
                <th>p90</th>
                <th>Delta</th>
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map((row) => (
                <tr key={row.scenario}>
                  <td>{row.scenario_label}</td>
                  <td>{row.total_risk_score.toFixed(3)}</td>
                  <td>{row.risk_distribution.p90.toFixed(3)}</td>
                  <td>{row.risk_delta_vs_baseline.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted">
          Best by Expected Value: {reasoning?.comparison?.recommended_scenario_label || '-'} / Best by p90: {reasoning?.comparison?.robust_recommended_scenario_label || '-'}
        </p>
      </div>

      <div className="detail-block">
        <div className="panel-card-header">
          <h3>Policy Memo</h3>
          {summaryState?.source ? <span className="summary-source">source: {summaryState.source}{summaryState.model ? ` / ${summaryState.model}` : ''}</span> : null}
        </div>
        <div className="summary-box">
          {loadingSummary ? 'Generating with OpenAI...' : null}
          {!loadingSummary && summaryState?.error ? <div className="error-text">{summaryState.error}</div> : null}
          {!loadingSummary && !summaryState?.error ? (summaryState?.summary || 'Not generated yet.') : null}
        </div>
      </div>
    </section>
  )
}
