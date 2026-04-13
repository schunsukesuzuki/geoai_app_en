import { useState } from 'react'

export function DecisionBar({ regionId, selectedScenarioId, onSubmitDecision, latestDecision }) {
  const [status, setStatus] = useState('approved')
  const [comment, setComment] = useState('')
  const [tags, setTags] = useState('')

  const submit = () => {
    if (!regionId || !selectedScenarioId) return
    onSubmitDecision({
      region_id: regionId,
      selected_scenario_id: selectedScenarioId,
      status,
      reviewer_comment: comment,
      rationale_tags: tags.split(',').map((x) => x.trim()).filter(Boolean),
    })
  }

  return (
    <section className="card">
      <div className="card-head"><h2>Decision Action</h2><span>Approval Flow</span></div>
      <div className="decision-grid">
        <label className="control"><span>Status</span><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="approved">approved</option><option value="pending">pending</option><option value="rejected">rejected</option></select></label>
        <label className="control"><span>Rationale tags</span><input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="healthcare, compact-city" /></label>
      </div>
      <label className="control"><span>Reviewer comment</span><textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={4} placeholder="Reason for approve / hold / send back" /></label>
      <div className="action-row">
        <button type="button" className="primary-btn" onClick={submit}>Record decision</button>
        {latestDecision?.summary ? <span className="muted">{latestDecision.summary}</span> : null}
      </div>
    </section>
  )
}
