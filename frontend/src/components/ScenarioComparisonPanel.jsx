export function ScenarioComparisonPanel({ scenarios = [], comparison = [], baselineScenarioId = 'baseline', selectedScenarioId, onSelectScenario }) {
  const comparisonById = Object.fromEntries((comparison || []).map((item) => [item.scenario_id, item]))
  return (
    <section className="card">
      <div className="card-head"><h2>Scenario Comparison</h2><span>Compare and choose a policy option</span></div>
      <div className="scenario-card-grid">
        {scenarios.map((scenario) => {
          const diff = comparisonById[scenario.scenario_id]
          const active = selectedScenarioId === scenario.scenario_id
          return (
            <button type="button" key={scenario.scenario_id} className={`scenario-card ${active ? 'active' : ''}`} onClick={() => onSelectScenario(scenario.scenario_id)}>
              <div className="scenario-card-top">
                <strong>{scenario.name}</strong>
                {scenario.scenario_id === baselineScenarioId ? <span className="tag subtle">baseline</span> : null}
                {diff?.recommended ? <span className="tag success">recommended</span> : null}
              </div>
              <p className="scenario-card-text">Total Risk {scenario.projected_metrics.total_risk_score.toFixed(3)} / Rank {scenario.priority_rank}</p>
              <div className="scenario-kpi-row">
                <span>Population Retention {scenario.projected_metrics.population_retention.toFixed(3)}</span>
                <span>Healthcare {scenario.projected_metrics.healthcare_access.toFixed(3)}</span>
              </div>
              {diff ? (
                <div className="scenario-diff-box">
                  <div>Improvement: {(diff.improved_metrics || []).join(', ') || '—'}</div>
                  <div>Worsened: {(diff.worsened_metrics || []).join(', ') || '—'}</div>
                </div>
              ) : null}
            </button>
          )
        })}
      </div>
    </section>
  )
}
