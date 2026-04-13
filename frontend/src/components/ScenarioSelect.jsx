const options = [
  ['baseline', 'Status Quo'],
  ['medical', 'Medical Hub Reinforcement'],
  ['housing', 'Vacant Housing Renewal Priority'],
  ['family', 'Family Support Focus'],
  ['compact', 'Hub Consolidation / Compactization'],
]

export function ScenarioSelect({ value, onChange }) {
  return (
    <label className="control">
      <span>Scenario</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(([scenario, label]) => (
          <option key={scenario} value={scenario}>{label}</option>
        ))}
      </select>
    </label>
  )
}
