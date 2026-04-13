from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / 'app' / 'data'
FAC_DIR = DATA_DIR / 'facilities'
LA_DIR = DATA_DIR / 'living_areas'
ACC_DIR = DATA_DIR / 'accessibility'


def polygon_area_centroid(ring):
    if len(ring) < 4:
        pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
        if not pts:
            return 0.0, (0.0, 0.0)
        return 0.0, (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    area = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    area *= 0.5
    if abs(area) < 1e-12:
        pts = ring[:-1]
        return 0.0, (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return abs(area), (cx / (6 * area), cy / (6 * area))


def rings_from_geometry(geom):
    if geom['type'] == 'Polygon':
        return geom['coordinates']
    if geom['type'] == 'MultiPolygon':
        rings = []
        for poly in geom['coordinates']:
            rings.extend(poly)
        return rings
    return []


def largest_ring(geom):
    best_area = -1.0
    best_ring = []
    best_centroid = (0.0, 0.0)
    for ring in rings_from_geometry(geom):
        area, pt = polygon_area_centroid(ring)
        if area > best_area:
            best_area = area
            best_ring = ring
            best_centroid = pt
    return best_ring, best_centroid, max(best_area, 0.0)


def proxy_hospital_count(population_2035):
    pop = max(0.0, float(population_2035 or 0.0))
    count = round(pop / 250000.0)
    return max(3, min(int(count), 60))


def generate_proxy_hospitals(pref_code, pref_name, ring, centroid, count):
    if not ring:
        ring = [[centroid[0], centroid[1]]]
    coords = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring[:]
    if not coords:
        coords = [[centroid[0], centroid[1]]]
    cx, cy = centroid
    n = len(coords)
    facilities = []
    for idx in range(count):
        vertex = coords[(idx * max(1, n // count)) % n]
        vx, vy = vertex
        lon = cx + 0.35 * (vx - cx)
        lat = cy + 0.35 * (vy - cy)
        facilities.append({
            'facility_id': f'hospital_proxy_{pref_code}_{idx+1:03d}',
            'facility_type': 'hospital',
            'name': f'{pref_name} Representative Medical Hub{idx+1}（proxy）',
            'prefecture_code': pref_code,
            'municipality_code': None,
            'latitude': round(lat, 6),
            'longitude': round(lon, 6),
            'source_dataset': 'prefecture polygon representative points + region medical_access_risk',
            'living_area_name': f'{pref_name}Healthcare Area (proxy)',
            'raw_properties': {
                'proxy_mode': True,
                'source_note': 'Representative healthcare hub proxy derived from prefecture polygon geometry for nationwide demo.',
                'proxy_index': idx + 1,
                'proxy_count': count,
            },
        })
    return facilities


def main() -> None:
    FAC_DIR.mkdir(exist_ok=True)
    LA_DIR.mkdir(exist_ok=True)
    ACC_DIR.mkdir(exist_ok=True)

    prefectures = json.load(open(DATA_DIR / 'prefectures.json', encoding='utf-8'))
    metrics = json.load(open(DATA_DIR / 'region_metrics.json', encoding='utf-8'))
    metric_by_code = {m['region_code']: m for m in metrics}
    name_to_code = {m['region_name']: m['region_code'] for m in metrics}

    # preserve the committed real Aomori slice when available
    aomori_fac = json.load(open(DATA_DIR / 'facilities_aomori_hospital.json', encoding='utf-8'))
    aomori_la = json.load(open(DATA_DIR / 'living_areas_aomori_healthcare.geojson', encoding='utf-8'))
    aomori_acc = json.load(open(DATA_DIR / 'accessibility_summary_aomori_hospital.json', encoding='utf-8'))

    for feature in prefectures.get('features', []):
        pref_name = feature.get('properties', {}).get('N03_001')
        pref_code = name_to_code.get(pref_name)
        if not pref_code:
            continue

        if pref_code == '02':
            enriched = dict(aomori_acc)
            enriched['prefecture_name'] = pref_name
            enriched['data_available'] = True
            enriched['data_basis'] = 'real_hospital_subset_plus_official_medical_area_names'
            json.dump(aomori_fac, open(FAC_DIR / f'{pref_code}_hospital.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            json.dump(aomori_la, open(LA_DIR / f'{pref_code}_healthcare.geojson', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            json.dump(enriched, open(ACC_DIR / f'{pref_code}_hospital_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            continue

        geom = feature['geometry']
        ring, centroid, _ = largest_ring(geom)

        metric_row = metric_by_code[pref_code]
        risk = float(metric_row.get('medical_access_risk', 0.5))
        origin_cells = max(180, int(220 + metric_row.get('population_2035', 0) / 25000))
        coverage = max(0.2, min(0.95, round(1.0 - risk * 0.72, 4)))
        avg_time = round(12.0 + risk * 34.0, 1)
        p90_time = round(avg_time + 7.5 + risk * 9.0, 1)
        underserved = int(round((1.0 - coverage) * origin_cells))
        facility_count = proxy_hospital_count(metric_row.get('population_2035', 0))
        hospitals = generate_proxy_hospitals(pref_code, pref_name, ring, centroid, facility_count)

        facilities_payload = {
            'items': hospitals
        }
        living_areas_payload = {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'properties': {
                    'living_area_id': f'healthcare_{pref_code}_001',
                    'living_area_type': 'healthcare',
                    'prefecture_code': pref_code,
                    'source_dataset': 'prefecture polygon shell (proxy healthcare area)',
                    'name': f'{pref_name}Healthcare Area (proxy)',
                    'representative_hospital': hospitals[0]['name'],
                    'geometry_note': 'Prefecture shell used as proxy healthcare area in nationwide demo.',
                    'proxy_mode': True,
                },
                'geometry': geom,
            }],
        }
        accessibility_payload = {
            'prefecture_code': pref_code,
            'prefecture_name': pref_name,
            'facility_type': 'hospital',
            'threshold_min': 30,
            'covered_population_ratio': coverage,
            'avg_travel_time_min': avg_time,
            'p90_travel_time_min': p90_time,
            'underserved_origin_count': underserved,
            'facility_count': facility_count,
            'origin_type': 'prefecture_polygon_proxy',
            'origin_cell_count': origin_cells,
            'method_note': 'Nationwide demo proxy derived from prefecture geometry and existing medical_access_risk metric.',
            'medical_area_breakdown': [{
                'living_area_id': f'healthcare_{pref_code}_001',
                'name': f'{pref_name}Healthcare Area (proxy)',
                'representative_hospital': hospitals[0]['name'],
                'sampled_cell_count': origin_cells,
            }],
            'data_available': True,
            'data_basis': 'prefecture_geometry_plus_existing_medical_access_risk_proxy',
        }

        json.dump(facilities_payload, open(FAC_DIR / f'{pref_code}_hospital.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        json.dump(living_areas_payload, open(LA_DIR / f'{pref_code}_healthcare.geojson', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        json.dump(accessibility_payload, open(ACC_DIR / f'{pref_code}_hospital_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print('Generated nationwide healthcare slices.')


if __name__ == '__main__':
    main()
