export function ExportPanel({ report, onGenerateReport, decisions = [] }) {
  return (
    <section className="card">
      <div className="card-head"><h2>Export Panel</h2><span>Policy memos and history</span></div>
      <div className="action-row">
        <button type="button" className="primary-btn" onClick={onGenerateReport}>Generate policy memo</button>
      </div>
      {report ? (
        <div className="detail-block">
          <h3>{report.title}</h3>
          <div className="summary-box">{report.memo || report.summary}</div>
          <div className="table-wrap small">
            <table>
              <thead><tr><th>metric</th><th>baseline</th><th>selected</th><th>delta</th></tr></thead>
              <tbody>
                {(report.comparison_table || []).map((row) => (
                  <tr key={row.metric}><td>{row.metric}</td><td>{row.baseline}</td><td>{row.selected}</td><td>{row.delta}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      <div className="detail-block">
        <h3>Decision history</h3>
        <ul>
          {decisions.slice(0, 5).map((d) => <li key={d.decision_id}>{d.created_at}: {d.selected_scenario_name} / {d.status}</li>)}
        </ul>
      </div>
    </section>
  )
}
