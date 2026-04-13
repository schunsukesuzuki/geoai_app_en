from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"
PRIORITIES_DIR = DATA_DIR / "healthcare_priorities"
TIMELINE_DIR = DATA_DIR / "healthcare_timeline"
YEARS = [2025, 2030, 2035, 2040]


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(value, upper))


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def compute_priority(state: dict) -> dict:
    coverage = float(state.get("coverage_ratio_30m") or 0.0)
    avg_time = float(state.get("avg_travel_time_min") or 999.0)
    p90 = float(state.get("p90_travel_time_min") or 999.0)
    underserved = float(state.get("underserved_origin_count") or 0.0)
    aging = float(state.get("aging_ratio") or 0.0)
    decline = float(state.get("annual_decline_rate") or 0.0)
    population = float(state.get("population") or 0.0)
    hospital_count = float(state.get("hospital_count") or 0.0)
    hospital_density = float(state.get("hospital_density") or 0.0)
    fiscal = float(state.get("fiscal_pressure") or 0.0)

    rationale = []
    score = 0.35 * (1 - coverage) + 0.2 * min(avg_time / 60.0, 1.0) + 0.15 * min(p90 / 80.0, 1.0) + 0.15 * min(aging / 0.45, 1.0) + 0.1 * min(decline / 0.03, 1.0) + 0.05 * min(fiscal / 0.6, 1.0)

    if coverage < 0.75:
        rationale.append("low_coverage")
    if p90 > 35:
        rationale.append("long_tail_access")
    if underserved >= 8:
        rationale.append("underserved_origins")
    if aging >= 0.37:
        rationale.append("high_aging")
    if decline >= 0.017:
        rationale.append("rapid_decline")

    shrink_signal = (decline >= 0.02 and population < 120000 and hospital_count >= 2 and coverage >= 0.72 and hospital_density >= 0.07)
    if shrink_signal:
        label = "shrink_candidate"
        score = max(score, 0.62)
        rationale.append("supply_overhang")
        reason = "Given population decline and spare capacity, treat this as a phased consolidation candidate."
    elif coverage < 0.78 or p90 > 34 or underserved >= 6:
        label = "reinvest"
        score = max(score, 0.55)
        reason = "Large room for access improvement and strong demand pressure; prioritize reinvestment."
    else:
        label = "maintain"
        if hospital_density >= 0.1:
            rationale.append("supply_stable")
        reason = "Access is broadly maintained; treat status quo as the default."

    return {
        "priority_label": label,
        "priority_score": round(clamp(score, 0.0, 0.99), 3),
        "rationale_tags": rationale,
        "summary_reason": reason,
    }


def backcast_population(pop_2035: float, annual_decline_rate: float) -> float:
    rate = max(0.0, min(annual_decline_rate, 0.08))
    denom = (1.0 - rate) ** 10
    if denom <= 0.01:
        return pop_2035
    return pop_2035 / denom


def transition(state: dict, action: str, years: int = 5) -> dict:
    rate = max(0.0, min(float(state.get("annual_decline_rate") or 0.0), 0.08))
    pop = float(state.get("population") or 0.0) * ((1.0 - rate) ** years)
    aging = float(state.get("aging_ratio") or 0.0)
    coverage = float(state.get("coverage_ratio_30m") or 0.0)
    avg_time = float(state.get("avg_travel_time_min") or 999.0)
    p90 = float(state.get("p90_travel_time_min") or 999.0)
    underserved = int(round(float(state.get("underserved_origin_count") or 0.0)))
    hospital_count = int(state.get("hospital_count") or 0)
    capacity = float(state.get("capacity_proxy") or max(hospital_count, 1))
    fiscal = float(state.get("fiscal_pressure") or 0.0)

    if action == "reinvest":
        coverage = clamp(coverage + 0.04, 0.0, 1.0)
        avg_time = max(5.0, avg_time - 2.4)
        p90 = max(avg_time + 2.0, p90 - 4.5)
        underserved = max(0, underserved - 2)
        capacity *= 1.08
        fiscal = clamp(fiscal + 0.015, 0.0, 1.0)
        aging = clamp(aging + 0.008, 0.0, 0.7)
    elif action == "shrink_candidate":
        if hospital_count > 1:
            hospital_count -= 1
        coverage = clamp(coverage - 0.05, 0.0, 1.0)
        avg_time = avg_time + 3.0
        p90 = p90 + 5.0
        underserved = underserved + 3
        capacity *= 0.94
        fiscal = clamp(fiscal - 0.015, 0.0, 1.0)
        aging = clamp(aging + 0.012, 0.0, 0.7)
    else:
        coverage = clamp(coverage - 0.01, 0.0, 1.0)
        avg_time = avg_time + 0.8
        p90 = p90 + 1.5
        underserved = underserved + 1
        capacity *= 1.0
        fiscal = clamp(fiscal + 0.005, 0.0, 1.0)
        aging = clamp(aging + 0.010, 0.0, 0.7)

    med_risk = clamp(0.45 * (1.0 - coverage) + 0.2 * min(avg_time / 60.0, 1.0) + 0.15 * min(p90 / 80.0, 1.0) + 0.12 * min(aging / 0.5, 1.0) + 0.08 * min(rate / 0.03, 1.0), 0.0, 1.0)

    next_state = dict(state)
    next_state.update({
        "population": round(pop),
        "aging_ratio": round(aging, 4),
        "coverage_ratio_30m": round(coverage, 4),
        "avg_travel_time_min": round(avg_time, 1),
        "p90_travel_time_min": round(p90, 1),
        "underserved_origin_count": int(underserved),
        "hospital_count": int(hospital_count),
        "capacity_proxy": round(capacity, 3),
        "fiscal_pressure": round(fiscal, 4),
        "medical_access_risk": round(med_risk, 4),
    })
    return next_state


def build_prefecture(pref_code: str, profiles_path: Path, decisions_path: Path) -> None:
    profiles = load_json(profiles_path, {"items": []}).get("items", [])
    if not profiles:
        return
    decisions = load_json(decisions_path, {"items": []}).get("items", [])
    action_map = {d["living_area_id"]: d.get("priority_label", "maintain") for d in decisions}

    year_states = {}
    current = []
    for p in profiles:
        baseline = dict(p)
        baseline["population"] = round(backcast_population(float(p.get("population_2035") or 0.0), float(p.get("annual_decline_rate") or 0.0)))
        baseline["year"] = 2025
        baseline["origin_model"] = "municipality_centroid_road_network_timeline"
        dec = compute_priority(baseline)
        dec["applied_action"] = action_map.get(p["living_area_id"], dec["priority_label"])
        baseline.update(dec)
        current.append(baseline)
    year_states[2025] = current

    prev = current
    for year in [2030, 2035, 2040]:
        next_items = []
        for st in prev:
            action = st.get("applied_action") or st.get("priority_label") or "maintain"
            nxt = transition(st, action, 5)
            nxt["year"] = year
            dec = compute_priority(nxt)
            dec["applied_action"] = action
            nxt.update(dec)
            next_items.append(nxt)
        year_states[year] = next_items
        prev = next_items

    summary_by_year = {}
    for year, items in year_states.items():
        total_pop = sum(float(x.get("population") or 0.0) for x in items) or 1.0
        summary_by_year[str(year)] = {
            "prefecture_code": pref_code,
            "year": year,
            "facility_type": "hospital",
            "threshold_min": 30,
            "covered_population_ratio": round(sum(float(x.get("coverage_ratio_30m") or 0.0) * float(x.get("population") or 0.0) for x in items) / total_pop, 4),
            "avg_travel_time_min": round(sum(float(x.get("avg_travel_time_min") or 0.0) * float(x.get("population") or 0.0) for x in items) / total_pop, 1),
            "p90_travel_time_min": round(sum(float(x.get("p90_travel_time_min") or 0.0) * float(x.get("population") or 0.0) for x in items) / total_pop, 1),
            "underserved_origin_count": int(sum(int(x.get("underserved_origin_count") or 0) for x in items)),
            "facility_count": int(sum(int(x.get("hospital_count") or 0) for x in items)),
            "origin_type": "municipality_centroid_road_network_timeline",
            "origin_model": "municipality_centroid_road_network_timeline",
            "data_available": True,
            "data_basis": "graph_based_summary_with_rule_based_timeline_transition",
        }

    out = {
        "prefecture_code": pref_code,
        "available_years": YEARS,
        "summary_by_year": summary_by_year,
        "items_by_year": {str(year): items for year, items in year_states.items()},
    }
    TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
    (TIMELINE_DIR / f"{pref_code}_healthcare_states.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
    for profile_path in sorted(PRIORITIES_DIR.glob("*_living_area_healthcare_profiles.json")):
        pref_code = profile_path.name.split("_", 1)[0]
        decisions_path = PRIORITIES_DIR / f"{pref_code}_living_area_priority_decisions.json"
        build_prefecture(pref_code, profile_path, decisions_path)


if __name__ == "__main__":
    main()
