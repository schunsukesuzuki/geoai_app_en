export function RankingTable({ items, selectedRegionCode, onSelectRegion }) {
  return (
    <section className="card">
      <div className="card-head"><h2>Priority Ranking</h2><span>Top 20</span></div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Prefecture</th>
              <th>Total Risk</th>
              <th>p90</th>
              <th>Annual Decline</th>
              <th>2035 Population</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 20).map((item) => (
              <tr
                key={item.region_code}
                className={item.region_code === selectedRegionCode ? 'selected' : ''}
                onClick={() => onSelectRegion(item.region_code)}
              >
                <td>{item.priority_rank}</td>
                <td>{item.region_name}</td>
                <td>{item.total_risk_score.toFixed(3)}</td>
                <td>{item.risk_distribution?.p90?.toFixed?.(3) ?? '-'}</td>
                <td>{(item.predicted_annual_decline_rate * 100).toFixed(2)}%</td>
                <td>{Number(item.population_2035).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
