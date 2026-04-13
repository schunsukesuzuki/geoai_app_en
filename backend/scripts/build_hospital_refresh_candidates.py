from __future__ import annotations

import json
from pathlib import Path
from math import radians, sin, cos, asin, sqrt

BASE_DIR = Path(__file__).resolve().parents[1] / 'app' / 'data'
FACILITIES_DIR = BASE_DIR / 'facilities'
REFRESH_DIR = BASE_DIR / 'feature_refresh'
REFRESH_DIR.mkdir(parents=True, exist_ok=True)


def haversine_km(lat1, lon1, lat2, lon2):
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


def normalize_name(name: str | None) -> str:
    if not name:
        return ''
    value = str(name)
    for token in ['Hospital', 'Clinic', 'Clinic', 'Medical Office', 'Medical Corporation', ' (update candidate)', 'update candidate', ' ', '　']:
        value = value.replace(token, '')
    return value


def main() -> None:
    observed = []
    candidates = []
    base_by_pref = {}
    for file in sorted(FACILITIES_DIR.glob('*_hospital.json')):
        pref = file.stem.split('_')[0]
        items = json.loads(file.read_text(encoding='utf-8')).get('items', [])
        if not items:
            continue
        base_by_pref[pref] = items
        for i, item in enumerate(items[: min(4, len(items))]):
            obs = dict(item)
            obs['observed_feature_id'] = f"obs_{item['facility_id']}"
            obs['observed_source'] = 'public_hospital_refresh_observation'
            obs['observed_at'] = '2026-04-13T12:00:00+09:00'
            if i == 0:
                obs['latitude'] = round(item['latitude'] + 0.008, 7)
                obs['longitude'] = round(item['longitude'] + 0.008, 7)
            elif i == 1:
                obs['name'] = f"{item.get('name', '')} (update candidate)"
            observed.append(obs)
        seed = items[0]
        observed.append({
            'observed_feature_id': f'obs_new_{pref}',
            'feature_type': 'hospital',
            'prefecture_code': pref,
            'name': f"{seed.get('name', 'Representative')}new building candidate",
            'latitude': round(seed['latitude'] + 0.02, 7),
            'longitude': round(seed['longitude'] - 0.015, 7),
            'observed_source': 'public_hospital_refresh_observation',
            'observed_at': '2026-04-13T12:00:00+09:00',
            'raw_properties': {'candidate_note': 'synthetic observed refresh candidate derived from public slice'},
        })

    matched_base = set()
    for ob in observed:
        pref = ob['prefecture_code']
        best = None
        best_score = -10**9
        oname = normalize_name(ob.get('name'))
        for base in base_by_pref.get(pref, []):
            bname = normalize_name(base.get('name'))
            sim = 1.0 if oname and bname and (oname in bname or bname in oname) else 0.0
            dist = haversine_km(ob['latitude'], ob['longitude'], base['latitude'], base['longitude'])
            score = sim * 10 - dist
            if score > best_score:
                best_score = score
                best = (base, sim, dist)
        if best and best[1] > 0 and best[2] < 0.5:
            base = best[0]
            matched_base.add(base['facility_id'])
            if ob.get('name') == base.get('name'):
                continue
            candidate_type = 'attribute_change'
            confidence = 0.82
            tags = ['name_changed', 'same_location', 'same_prefecture']
            reason = 'Candidate for a name or attribute update.'
        elif best and best[1] > 0 and best[2] < 5.0:
            base = best[0]
            matched_base.add(base['facility_id'])
            candidate_type = 'moved'
            confidence = max(0.6, min(0.94, 0.95 - best[2] / 10))
            tags = ['name_match', 'spatial_shift', 'same_prefecture']
            reason = 'Facility with the same name exceeds the spatial-shift threshold; relocation candidate.'
        else:
            base = None
            candidate_type = 'new'
            confidence = 0.88 if pref == '02' else 0.74
            tags = ['no_base_match', 'same_prefecture']
            reason = 'No close match exists in the base layer; new facility candidate.'
        candidates.append({
            'candidate_id': f"cand_{pref}_{len(candidates)+1:04d}",
            'prefecture_code': pref,
            'feature_type': 'hospital',
            'candidate_type': candidate_type,
            'base_feature_id': base.get('facility_id') if base else None,
            'observed_feature_id': ob.get('observed_feature_id'),
            'confidence': round(confidence, 3),
            'reason_tags': tags,
            'summary_reason': reason,
            'proposed_name': ob.get('name'),
            'proposed_latitude': ob.get('latitude'),
            'proposed_longitude': ob.get('longitude'),
            'base_name': base.get('name') if base else None,
            'base_latitude': base.get('latitude') if base else None,
            'base_longitude': base.get('longitude') if base else None,
            'status': 'pending',
            'created_at': '2026-04-13T12:00:00+09:00',
            'observed_source': ob.get('observed_source'),
        })

    for pref, items in base_by_pref.items():
        if int(pref) % 7 != 0:
            continue
        unmatched = [item for item in items if item['facility_id'] not in matched_base]
        if not unmatched:
            continue
        base = unmatched[-1]
        candidates.append({
            'candidate_id': f"cand_{pref}_{len(candidates)+1:04d}",
            'prefecture_code': pref,
            'feature_type': 'hospital',
            'candidate_type': 'retired',
            'base_feature_id': base.get('facility_id'),
            'observed_feature_id': None,
            'confidence': 0.63,
            'reason_tags': ['missing_in_observed_source', 'no_close_match'],
            'summary_reason': 'Matching facility not found in the refresh observation source; retirement candidate.',
            'proposed_name': base.get('name'),
            'proposed_latitude': base.get('latitude'),
            'proposed_longitude': base.get('longitude'),
            'base_name': base.get('name'),
            'base_latitude': base.get('latitude'),
            'base_longitude': base.get('longitude'),
            'status': 'pending',
            'created_at': '2026-04-13T12:00:00+09:00',
            'observed_source': 'public_hospital_refresh_observation',
        })

    (REFRESH_DIR / 'observed_hospitals.json').write_text(json.dumps({'items': observed}, ensure_ascii=False, indent=2), encoding='utf-8')
    (REFRESH_DIR / 'hospital_refresh_candidates.json').write_text(json.dumps({'items': candidates}, ensure_ascii=False, indent=2), encoding='utf-8')
    updates_path = REFRESH_DIR / 'hospital_approved_updates.json'
    if not updates_path.exists():
        updates_path.write_text(json.dumps({'items': []}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
