from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "app" / "data"
FACILITIES_DIR = DATA_DIR / "facilities"
LIVING_AREAS_DIR = DATA_DIR / "living_areas"
ASSETS_FILE = DATA_DIR / "spatial_assets.json"
BINDINGS_FILE = DATA_DIR / "entity_asset_bindings.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_items(path: Path):
    payload = load_json(path)
    if isinstance(payload, dict):
        return payload.get("items", []) if isinstance(payload.get("items", []), list) else []
    if isinstance(payload, list):
        return payload
    return []


def iter_healthcare_features(path: Path):
    payload = load_json(path)
    if isinstance(payload, dict):
        return payload.get("features", []) if isinstance(payload.get("features", []), list) else []
    return []


def main() -> None:
    observed_at = datetime.now(timezone.utc).date().isoformat()
    assets = []
    bindings = []

    for facility_file in sorted(FACILITIES_DIR.glob("*_hospital.json")):
        prefecture_code = facility_file.stem.split("_")[0]
        for item in load_items(facility_file):
            if not isinstance(item, dict):
                continue
            entity_id = item.get("facility_id")
            if not entity_id:
                continue
            lon = float(item.get("longitude", 0.0))
            lat = float(item.get("latitude", 0.0))
            asset_id = f"asset_{entity_id}_glb_v1"
            assets.append({
                "asset_id": asset_id,
                "asset_type": "glb",
                "storage_uri": f"assets/hospitals/{entity_id}.glb",
                "coordinate_reference": "EPSG:4326",
                "bbox": {"min_x": round(lon-0.001,6), "min_y": round(lat-0.001,6), "max_x": round(lon+0.001,6), "max_y": round(lat+0.001,6)},
                "version": "v1",
                "observed_at": observed_at,
                "source_system": "spatial_asset_registry",
                "prefecture_code": prefecture_code,
                "entity_type": "hospital",
                "metadata": {"label": item.get("name") or entity_id, "feature_type": "hospital", "placeholder": True},
            })
            bindings.append({
                "binding_id": f"bind_{entity_id}_primary_visual",
                "entity_id": entity_id,
                "asset_id": asset_id,
                "binding_type": "primary_visual",
                "active_from": observed_at,
                "active_to": None,
                "metadata": {"prefecture_code": prefecture_code, "entity_type": "hospital"},
            })

    for area_file in sorted(LIVING_AREAS_DIR.glob("*_healthcare.geojson")):
        prefecture_code = area_file.stem.split("_")[0]
        for feature in iter_healthcare_features(area_file):
            if not isinstance(feature, dict):
                continue
            props = feature.get("properties", {}) or {}
            entity_id = props.get("living_area_id")
            name = props.get("name") or entity_id
            if not entity_id:
                continue
            asset_id = f"asset_{entity_id}_context_mesh_v1"
            geometry = feature.get("geometry") or {}
            coords = []
            if geometry.get("type") == "Polygon":
                coords = geometry.get("coordinates", [[]])[0]
            elif geometry.get("type") == "MultiPolygon":
                coords = geometry.get("coordinates", [[[]]])[0][0]
            xs = [pt[0] for pt in coords if isinstance(pt, list) and len(pt) >= 2]
            ys = [pt[1] for pt in coords if isinstance(pt, list) and len(pt) >= 2]
            bbox = {"min_x": round(min(xs),6), "min_y": round(min(ys),6), "max_x": round(max(xs),6), "max_y": round(max(ys),6)} if xs and ys else None
            assets.append({
                "asset_id": asset_id,
                "asset_type": "mesh",
                "storage_uri": f"assets/healthcare_context/{entity_id}.glb",
                "coordinate_reference": "EPSG:4326",
                "bbox": bbox,
                "version": "v1",
                "observed_at": observed_at,
                "source_system": "spatial_asset_registry",
                "prefecture_code": prefecture_code,
                "entity_type": "healthcare_living_area",
                "metadata": {"label": f"{name} context mesh", "feature_type": "healthcare_living_area", "placeholder": True},
            })
            bindings.append({
                "binding_id": f"bind_{entity_id}_context_mesh",
                "entity_id": entity_id,
                "asset_id": asset_id,
                "binding_type": "context_mesh",
                "active_from": observed_at,
                "active_to": None,
                "metadata": {"prefecture_code": prefecture_code, "entity_type": "healthcare_living_area"},
            })

    ASSETS_FILE.write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding='utf-8')
    BINDINGS_FILE.write_text(json.dumps(bindings, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Wrote {len(assets)} assets and {len(bindings)} bindings")

if __name__ == "__main__":
    main()
