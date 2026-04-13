function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`
}

export function OverviewCards({ modelInfo, selectedItem, health }) {
  return (
    <div className="overview-grid">
      <section className="card">
        <div className="card-head"><h2>Model Info</h2><span>Precomputed</span></div>
        <div className="metric-grid">
          <div><label>Model</label><strong>{modelInfo?.model_name || '-'}</strong></div>
          <div><label>R²</label><strong>{modelInfo?.performance?.r2?.toFixed?.(3) ?? '-'}</strong></div>
          <div><label>MAE</label><strong>{modelInfo?.performance?.mae?.toFixed?.(6) ?? '-'}</strong></div>
          <div><label>Training Years</label><strong>{Array.isArray(modelInfo?.train_years) ? modelInfo.train_years.join(' - ') : '-'}</strong></div>
        </div>
      </section>
      <section className="card">
        <div className="card-head"><h2>OpenAI Generation Status</h2><span>Policy Memo</span></div>
        <div className="metric-grid">
          <div><label>API Key</label><strong>{health?.openai?.configured ? 'configured' : 'missing'}</strong></div>
          <div><label>SDK</label><strong>{health?.openai?.sdk_available ? 'available' : 'missing'}</strong></div>
          <div><label>Model</label><strong>{health?.openai?.model || '-'}</strong></div>
          <div><label>Fallback</label><strong>{health?.openai?.fallback_mode ? 'enabled' : 'disabled'}</strong></div>
        </div>
      </section>
      <section className="card">
        <div className="card-head"><h2>Selected Region</h2><span>Current Scenario</span></div>
        {selectedItem ? (
          <div className="metric-grid">
            <div><label>Prefecture</label><strong>{selectedItem.region_name}</strong></div>
            <div><label>Expected Rank</label><strong>{selectedItem.priority_rank} th</strong></div>
            <div><label>Worst-side Rank</label><strong>{selectedItem.robust_priority_rank} th</strong></div>
            <div><label>Aging Rate</label><strong>{pct(selectedItem.aging_rate)}</strong></div>
            <div><label>Vacancy Rate</label><strong>{pct(selectedItem.vacancy_rate)}</strong></div>
            <div><label>2035 Population</label><strong>{Number(selectedItem.population_2035 || 0).toLocaleString()}</strong></div>
          </div>
        ) : <p className="muted">Loading region data.</p>}
      </section>
    </div>
  )
}
