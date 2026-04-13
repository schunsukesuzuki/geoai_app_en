export function RecommendationReasonPanel({ explanation, agentExplanation, agentRuns, selectedScenarioName, auditEvents = [], auditChain = null }) {
  if (!explanation) {
    return <section className="card"><p className="muted">Loading explanation data.</p></section>
  }

  const agentOutput = agentExplanation?.output
  const latestRun = agentRuns?.[0]
  const sourceDatasets = (agentOutput?.source_datasets || []).filter((x) => String(x || '').trim() && String(x).trim().toLowerCase() !== 'unknown')

  return (
    <section className="card">
      <div className="card-head"><h2>Why This Recommendation</h2><span>{selectedScenarioName}</span></div>

      <div className="detail-block">
        <h3>Structured Explanation</h3>
        <ul>
          {(explanation.key_drivers || []).map((driver) => (
            <li key={driver.metric}>{driver.label}: {driver.reason} / impact {Number(driver.impact || 0).toFixed(3)}</li>
          ))}
        </ul>
      </div>

      <div className="metric-grid compact">
        <div><label>Improved Metrics</label><strong>{(explanation.improved_metrics || []).slice(0, 3).join(' / ') || '—'}</strong></div>
        <div><label>Worsened Metrics</label><strong>{(explanation.worsened_metrics || []).slice(0, 3).join(' / ') || '—'}</strong></div>
        <div><label>Updated At</label><strong>{explanation.last_updated || '—'}</strong></div>
      </div>

      <div className="detail-block">
        <h3>Agent Explanation</h3>
        {agentOutput ? (
          <>
            <p className="agent-summary">{agentOutput.summary}</p>
            <p className="muted">status: {agentExplanation?.status || 'unknown'} / run_id: {agentExplanation?.agent_run_id || '—'}</p>
            <div className="metric-grid compact">
              <div><label>trade-off</label><div className="agent-cell-value">{agentOutput.key_tradeoff || '—'}</div></div>
              <div><label>confidence</label><div className="agent-cell-value">{agentOutput.confidence_note || '—'}</div></div>
              <div><label>source datasets</label><div className="agent-cell-value">{sourceDatasets.slice(0, 3).join(' / ') || 'SSDSE-E-2025 / SSDSE-B-2025 / prefectures_geojson'}</div></div>
            </div>
            <div className="detail-block">
              <h3>Agent Improved Metrics</h3>
              {(agentOutput.improved_metrics || []).length ? (
                <ul>
                  {(agentOutput.improved_metrics || []).map((item, idx) => {
                    const name = item?.name || item?.metric || `metric_${idx + 1}`
                    const delta = Number(item?.delta ?? 0)
                    const reason = item?.reason || item?.explanation || 'No explanation provided'
                    return <li key={`improved-${name}-${idx}`}>{name}: {delta.toFixed(3)} / {reason}</li>
                  })}
                </ul>
              ) : <p className="muted">No material improvement identified.</p>}
            </div>
            <div className="detail-block">
              <h3>Agent Worsened Metrics</h3>
              {(agentOutput.worsened_metrics || []).length ? (
                <ul>
                  {(agentOutput.worsened_metrics || []).map((item, idx) => {
                    const name = item?.name || item?.metric || `metric_${idx + 1}`
                    const delta = Number(item?.delta ?? 0)
                    const reason = item?.reason || item?.explanation || 'No explanation provided'
                    return <li key={`worsened-${name}-${idx}`}>{name}: {delta.toFixed(3)} / {reason}</li>
                  })}
                </ul>
              ) : <p className="muted">No material worsening identified.</p>}
            </div>
          </>
        ) : <p className="muted">Loading agent explanation.</p>}
      </div>

      <div className="detail-block">
        <h3>Audit Trail</h3>
        {auditEvents.length ? (
          <>
            <ul>
              {auditEvents.slice(0, 5).map((event) => (
                <li key={event.audit_event_id}>
                  <strong>{event.event_type}</strong> / actor: {event.actor_type} / status: {event.status} / at: {event.created_at}
                  {event.snapshot_id ? ` / snapshot: ${event.snapshot_id}` : ''}
                </li>
              ))}
            </ul>
            {auditChain?.chain ? (
              <div className="audit-chain-box">
                <div><label>current chain entity</label><div className="agent-cell-value">{auditChain.entity_type}:{auditChain.entity_id}</div></div>
                <div><label>predecessors</label><div className="agent-cell-value">{(auditChain.chain.predecessor_refs || []).join(' / ') || '—'}</div></div>
                <div><label>successors</label><div className="agent-cell-value">{(auditChain.chain.successor_refs || []).join(' / ') || '—'}</div></div>
                <div><label>related snapshots</label><div className="agent-cell-value">{(auditChain.related_snapshots || []).map((s) => s.snapshot_id).join(' / ') || '—'}</div></div>
              </div>
            ) : null}
          </>
        ) : latestRun ? (
          <ul>
            <li>latest run: {latestRun.agent_run_id}</li>
            <li>created_at: {latestRun.created_at}</li>
            <li>status: {latestRun.status}</li>
            <li>prompt_version: {latestRun.prompt_version}</li>
          </ul>
        ) : <p className="muted">No audit log is available yet.</p>}
      </div>

      <div className="detail-block">
        <h3>Notes</h3>
        <ul>
          {(explanation.confidence_notes || []).map((note, idx) => <li key={idx}>{note}</li>)}
        </ul>
      </div>
    </section>
  )
}
