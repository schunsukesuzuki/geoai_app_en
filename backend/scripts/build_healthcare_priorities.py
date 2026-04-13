from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from typing import Any
from shapely.geometry import shape, Point

BASE_DIR = Path(__file__).resolve().parents[1] / 'app' / 'data'
LIVING_AREAS_DIR = BASE_DIR / 'living_areas'
FACILITIES_DIR = BASE_DIR / 'facilities'
ORIGINS_DIR = BASE_DIR / 'origins'
ACCESSIBILITY_DIR = BASE_DIR / 'accessibility'
OUTPUT_DIR = BASE_DIR / 'healthcare_priorities'
METRICS_FILE = BASE_DIR / 'region_metrics.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def estimate_travel_time_min(origin: dict[str, Any], facility: dict[str, Any]) -> float:
    km = haversine_km(origin['latitude'], origin['longitude'], facility['latitude'], facility['longitude'])
    # Coarse road-path inflation + average effective speed.
    road_km = km * 1.35
    return road_km / 40.0 * 60.0


def load_items(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, dict):
        if 'items' in payload and isinstance(payload['items'], list):
            return payload['items']
        if 'features' in payload and isinstance(payload['features'], list):
            return payload['features']
    return payload if isinstance(payload, list) else []


def build_profiles_for_prefecture(prefecture_code: str, metrics_by_code: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    living_path = LIVING_AREAS_DIR / f'{prefecture_code}_healthcare.geojson'
    fac_path = FACILITIES_DIR / f'{prefecture_code}_hospital.json'
    orig_path = ORIGINS_DIR / f'{prefecture_code}_municipality_centroids.json'
    acc_path = ACCESSIBILITY_DIR / f'{prefecture_code}_hospital_summary.json'

    if not living_path.exists():
        return [], []

    living_payload = load_json(living_path)
    features = living_payload.get('features', []) if isinstance(living_payload, dict) else []
    facilities = load_items(fac_path) if fac_path.exists() else []
    origins = load_items(orig_path) if orig_path.exists() else []
    pref_summary = load_json(acc_path) if acc_path.exists() else {}
    pref_metrics = metrics_by_code.get(prefecture_code, {})

    total_origins = max(1, len(origins))
    total_hospitals = max(1, len(facilities))

    profiles: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    for idx, feature in enumerate(features):
        props = feature.get('properties', {})
        geom = feature.get('geometry')
        poly = shape(geom) if geom else None
        area_name = props.get('name')
        municipalities = props.get('municipalities') or []

        area_facilities = []
        for fac in facilities:
            if fac.get('living_area_name') == area_name:
                area_facilities.append(fac)
                continue
            if poly is not None and poly.contains(Point(fac['longitude'], fac['latitude'])):
                area_facilities.append(fac)
        if not area_facilities and facilities:
            # fallback to representative assignment for proxy slices
            if idx < len(facilities):
                area_facilities = [facilities[idx]]
            else:
                area_facilities = [facilities[0]]

        area_origins = []
        if poly is not None:
            for origin in origins:
                if poly.contains(Point(origin['longitude'], origin['latitude'])):
                    area_origins.append(origin)
        if not area_origins:
            # If the polygon is too coarse / proxy-like, allocate origins using representative point proximity.
            rep_fac = area_facilities[0] if area_facilities else None
            if rep_fac and origins:
                # assign nearest origins to each living area representative using Voronoi-like partition
                # build representative set once lazily
                reps = []
                for j, feat2 in enumerate(features):
                    props2 = feat2.get('properties', {})
                    name2 = props2.get('name')
                    facs2 = [f for f in facilities if f.get('living_area_name') == name2]
                    if not facs2 and facilities:
                        facs2 = [facilities[min(j, len(facilities)-1)]]
                    if facs2:
                        reps.append((name2, facs2[0]))
                for origin in origins:
                    nearest_name = min(
                        reps,
                        key=lambda pair: estimate_travel_time_min(origin, pair[1])
                    )[0]
                    if nearest_name == area_name:
                        area_origins.append(origin)

        if not area_origins and origins:
            # ultimate fallback: split by contiguous chunks to avoid identical empty areas
            chunk = max(1, len(origins) // max(1, len(features)))
            area_origins = origins[idx*chunk:(idx+1)*chunk] or [origins[min(idx, len(origins)-1)]]

        travel_times = []
        for origin in area_origins:
            nearest = min(estimate_travel_time_min(origin, fac) for fac in facilities) if facilities else None
            if nearest is not None:
                travel_times.append(nearest)
        if not travel_times:
            travel_times = [pref_summary.get('avg_travel_time_min') or 30.0]

        travel_times_sorted = sorted(travel_times)
        p90_idx = min(len(travel_times_sorted)-1, int(0.9 * (len(travel_times_sorted)-1)))
        avg_travel = sum(travel_times_sorted) / len(travel_times_sorted)
        p90_travel = travel_times_sorted[p90_idx]
        covered = [t for t in travel_times_sorted if t <= 30.0]
        coverage_ratio = len(covered) / len(travel_times_sorted)
        underserved = len(travel_times_sorted) - len(covered)

        origin_share = len(area_origins) / total_origins
        hospital_share = len(area_facilities) / total_hospitals
        muni_share = len(municipalities) / max(1, sum(len((f.get('properties', {}) or {}).get('municipalities') or []) for f in features)) if municipalities else origin_share

        population_2035_pref = float(pref_metrics.get('population_2035') or 0.0)
        aging_pref = float(pref_metrics.get('aging_rate') or 0.0)
        decline_pref = float(pref_metrics.get('predicted_annual_decline_rate') or 0.0)
        access_pref = float(pref_metrics.get('medical_access_risk') or 0.0)
        fiscal_pref = float(pref_metrics.get('service_capacity_pressure') or 0.0)

        local_stress = clamp((avg_travel - 20.0) / 30.0, 0.0, 1.0)
        low_coverage = clamp((0.8 - coverage_ratio) / 0.8, 0.0, 1.0)
        hospital_gap = clamp((0.18 - hospital_share) / 0.18, 0.0, 1.0) if len(features) > 1 else 0.0

        population_share = clamp(0.65 * origin_share + 0.35 * muni_share, 0.05, 0.60)
        population_2035 = round(population_2035_pref * population_share)
        aging_ratio = round(clamp(aging_pref + 0.04 * local_stress + 0.02 * low_coverage - 0.015 * hospital_share, 0.18, 0.50), 4)
        annual_decline_rate = round(clamp(decline_pref * (0.9 + 0.35 * local_stress + 0.15 * low_coverage), 0.003, 0.03), 5)
        local_access_risk = round(clamp(0.45 * access_pref + 0.35 * local_stress + 0.20 * low_coverage, 0.1, 0.95), 4)
        fiscal_pressure = round(clamp(0.75 * fiscal_pref + 0.20 * origin_share + 0.12 * hospital_share, 0.1, 0.95), 4)
        hospital_density = round(len(area_facilities) / max(1, len(area_origins)), 3)
        capacity_proxy = round(len(area_facilities) * (1.0 + 0.4 * hospital_share + 0.2 * origin_share), 2)

        profile = {
            'living_area_id': props.get('living_area_id'),
            'prefecture_code': prefecture_code,
            'name': area_name,
            'hospital_count': len(area_facilities),
            'hospital_density': hospital_density,
            'capacity_proxy': capacity_proxy,
            'coverage_ratio_30m': round(coverage_ratio, 4),
            'avg_travel_time_min': round(avg_travel, 1),
            'p90_travel_time_min': round(p90_travel, 1),
            'underserved_origin_count': underserved,
            'population_2035': population_2035,
            'aging_ratio': aging_ratio,
            'annual_decline_rate': annual_decline_rate,
            'medical_access_risk': local_access_risk,
            'fiscal_pressure': fiscal_pressure,
        }
        profiles.append(profile)

        reinvest_score = (
            0.30 * (1.0 - coverage_ratio)
            + 0.22 * clamp((p90_travel - 30.0) / 40.0, 0.0, 1.0)
            + 0.18 * clamp(underserved / max(1, len(area_origins)), 0.0, 1.0)
            + 0.18 * clamp((aging_ratio - 0.28) / 0.20, 0.0, 1.0)
            + 0.12 * clamp(population_share / 0.25, 0.0, 1.0)
        )
        shrink_score = (
            0.28 * clamp((annual_decline_rate - 0.015) / 0.015, 0.0, 1.0)
            + 0.24 * clamp((0.12 - population_share) / 0.12, 0.0, 1.0)
            + 0.24 * clamp((hospital_share - origin_share) / 0.20, 0.0, 1.0)
            + 0.24 * clamp((coverage_ratio - 0.78) / 0.22, 0.0, 1.0)
        )
        maintain_score = (
            0.40 * coverage_ratio
            + 0.25 * (1.0 - clamp((avg_travel - 20.0) / 20.0, 0.0, 1.0))
            + 0.20 * clamp((0.02 - annual_decline_rate) / 0.02, 0.0, 1.0)
            + 0.15 * hospital_share
        )

        rationale_tags = []
        if coverage_ratio < 0.75:
            rationale_tags.append('low_coverage')
        if p90_travel > 35:
            rationale_tags.append('long_tail_access')
        if underserved >= max(2, len(area_origins) * 0.4):
            rationale_tags.append('underserved_origins')
        if aging_ratio >= 0.34:
            rationale_tags.append('high_aging')
        if annual_decline_rate >= 0.018:
            rationale_tags.append('rapid_decline')
        if hospital_share > origin_share + 0.08:
            rationale_tags.append('supply_overhang')

        label = 'maintain'
        score = round(maintain_score, 3)
        summary_reason = 'Access is broadly maintained; treat status quo as the default.'
        if shrink_score >= 0.62 and coverage_ratio >= 0.78 and annual_decline_rate >= 0.018 and population_share <= 0.12:
            label = 'shrink_candidate'
            score = round(shrink_score, 3)
            summary_reason = 'Demand shrinkage is strong; carefully assess as a consolidation / shrinkage candidate.'
        elif reinvest_score >= max(0.45, maintain_score):
            label = 'reinvest'
            score = round(reinvest_score, 3)
            summary_reason = 'Large room for access improvement and strong demand pressure; prioritize reinvestment.'
        else:
            if not rationale_tags:
                rationale_tags.append('stable_access')

        decisions.append({
            'living_area_id': props.get('living_area_id'),
            'prefecture_code': prefecture_code,
            'name': area_name,
            'priority_label': label,
            'priority_score': score,
            'rationale_tags': rationale_tags,
            'summary_reason': summary_reason,
        })

    # Sort by action severity for UI readability
    label_rank = {'reinvest': 0, 'shrink_candidate': 1, 'maintain': 2}
    decisions.sort(key=lambda x: (label_rank.get(x['priority_label'], 9), -x['priority_score'], x['name'] or ''))
    return profiles, decisions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefecture', default=None)
    args = parser.parse_args()

    metrics = load_json(METRICS_FILE)
    metrics_by_code = {m['region_code']: m for m in metrics}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    codes = [args.prefecture] if args.prefecture else [f'{i:02d}' for i in range(1, 48)]
    for code in codes:
        profiles, decisions = build_profiles_for_prefecture(code, metrics_by_code)
        save_json(OUTPUT_DIR / f'{code}_living_area_healthcare_profiles.json', {'items': profiles})
        save_json(OUTPUT_DIR / f'{code}_living_area_priority_decisions.json', {'items': decisions})
        print(f'Wrote priorities for {code}: profiles={len(profiles)} decisions={len(decisions)}')

if __name__ == '__main__':
    main()
