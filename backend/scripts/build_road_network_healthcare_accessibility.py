from __future__ import annotations

import json
import math
import heapq
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"
NETWORK_DIR = DATA_DIR / "network"
ORIGINS_DIR = DATA_DIR / "origins"
FAC_DIR = DATA_DIR / "facilities"
ACC_DIR = DATA_DIR / "accessibility"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    if geom["type"] == "MultiPolygon":
        rings = []
        for poly in geom["coordinates"]:
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


def point_in_ring(lon: float, lat: float, ring):
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        intersect = ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def haversine_km(lon1, lat1, lon2, lat2):
    r = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))


def sample_origins(pref_code: str, ring, centroid, target_count: int):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    width = maxx - minx
    height = maxy - miny
    cols = max(4, int(math.sqrt(target_count * max(width, 1e-6) / max(height, 1e-6))))
    rows = max(4, int(math.ceil(target_count / cols)))
    dx = width / cols if cols else 1
    dy = height / rows if rows else 1
    origins = []
    oid = 1
    for r in range(rows):
        for c in range(cols):
            lon = minx + (c + 0.5) * dx
            lat = miny + (r + 0.5) * dy
            if point_in_ring(lon, lat, ring):
                origins.append({
                    "origin_id": f"{pref_code}_origin_{oid:04d}",
                    "origin_type": "sampled_prefecture_cell",
                    "prefecture_code": pref_code,
                    "municipality_code": None,
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "population_weight": 1.0,
                })
                oid += 1
    if not origins:
        origins.append({
            "origin_id": f"{pref_code}_origin_0001",
            "origin_type": "sampled_prefecture_cell",
            "prefecture_code": pref_code,
            "municipality_code": None,
            "latitude": round(centroid[1], 6),
            "longitude": round(centroid[0], 6),
            "population_weight": 1.0,
        })
    return origins


def anchor_points_from_ring(pref_code: str, ring, centroid, count=16):
    coords = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring[:]
    if not coords:
        coords = [[centroid[0], centroid[1]]]
    n = len(coords)
    anchors = []
    for i in range(count):
        p = coords[(i * max(1, n // count)) % n]
        anchors.append({
            "node_id": f"{pref_code}_anchor_{i+1:03d}",
            "prefecture_code": pref_code,
            "latitude": round(p[1], 6),
            "longitude": round(p[0], 6),
            "raw_properties": {"node_type": "anchor"},
        })
    anchors.append({
        "node_id": f"{pref_code}_anchor_centroid",
        "prefecture_code": pref_code,
        "latitude": round(centroid[1], 6),
        "longitude": round(centroid[0], 6),
        "raw_properties": {"node_type": "anchor_centroid"},
    })
    return anchors


def classify_edge_speed(km: float, a_type: str, b_type: str):
    if "anchor" in (a_type, b_type) and km > 20:
        return "primary", 60.0
    if km > 12:
        return "secondary", 45.0
    return "residential", 28.0


def build_graph(pref_code: str, origins, facilities, anchors):
    nodes = []
    for o in origins:
        nodes.append({
            "node_id": o["origin_id"],
            "prefecture_code": pref_code,
            "latitude": o["latitude"],
            "longitude": o["longitude"],
            "raw_properties": {"node_type": "origin"},
        })
    for f in facilities:
        nodes.append({
            "node_id": f["facility_id"],
            "prefecture_code": pref_code,
            "latitude": f["latitude"],
            "longitude": f["longitude"],
            "raw_properties": {"node_type": "hospital"},
        })
    nodes.extend(anchors)

    type_by_id = {n["node_id"]: n.get("raw_properties", {}).get("node_type", "generic") for n in nodes}

    edge_map = {}
    def add_edge(a, b):
        if a["node_id"] == b["node_id"]:
            return
        key = tuple(sorted((a["node_id"], b["node_id"])))
        if key in edge_map:
            return
        km = haversine_km(a["longitude"], a["latitude"], b["longitude"], b["latitude"])
        road_class, speed = classify_edge_speed(km, type_by_id[a["node_id"]], type_by_id[b["node_id"]])
        travel = (km / max(speed, 1.0)) * 60.0
        edge_map[key] = {
            "edge_id": f"edge_{key[0]}__{key[1]}",
            "source_node_id": key[0],
            "target_node_id": key[1],
            "prefecture_code": pref_code,
            "mode": "road_graph_proxy",
            "length_m": round(km * 1000.0, 1),
            "road_class": road_class,
            "estimated_speed_kmh": speed,
            "travel_time_min": round(travel, 3),
            "is_active": True,
            "raw_properties": {"synthetic": True},
        }

    # connect anchors in a ring and to centroid
    anchor_list = anchors[:-1]
    centroid_anchor = anchors[-1]
    for i in range(len(anchor_list)):
        add_edge(anchor_list[i], anchor_list[(i + 1) % len(anchor_list)])
        add_edge(anchor_list[i], centroid_anchor)

    # connect each hospital/origin to nearest anchors and nearest peers
    base_nodes = [n for n in nodes if type_by_id[n["node_id"]] != "anchor_centroid"]
    for node in base_nodes:
        dists = []
        for a in anchors:
            km = haversine_km(node["longitude"], node["latitude"], a["longitude"], a["latitude"])
            dists.append((km, a))
        dists.sort(key=lambda x: x[0])
        for _, a in dists[:2]:
            add_edge(node, a)

    # hospitals connect to 3 nearest hospitals
    hospital_nodes = [n for n in nodes if type_by_id[n["node_id"]] == "hospital"]
    for node in hospital_nodes:
        dists = []
        for other in hospital_nodes:
            if other["node_id"] == node["node_id"]:
                continue
            km = haversine_km(node["longitude"], node["latitude"], other["longitude"], other["latitude"])
            dists.append((km, other))
        dists.sort(key=lambda x: x[0])
        for _, other in dists[:3]:
            add_edge(node, other)

    return nodes, list(edge_map.values())


def multi_source_dijkstra(nodes, edges, hospital_ids):
    adj = {}
    for n in nodes:
        adj[n["node_id"]] = []
    for e in edges:
        u, v, w = e["source_node_id"], e["target_node_id"], float(e["travel_time_min"])
        adj.setdefault(u, []).append((v, w))
        adj.setdefault(v, []).append((u, w))
    dist = {nid: float("inf") for nid in adj}
    pq = []
    for hid in hospital_ids:
        if hid in dist:
            dist[hid] = 0.0
            heapq.heappush(pq, (0.0, hid))
    while pq:
        d, u = heapq.heappop(pq)
        if d != dist[u]:
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def quantile(values, q):
    if not values:
        return None
    values = sorted(values)
    idx = max(0, min(len(values) - 1, int(round((len(values) - 1) * q))))
    return values[idx]


def build_summary(pref_code: str, pref_name: str, origins, facilities, dist_by_node):
    origin_times = [float(dist_by_node.get(o["origin_id"], float("inf"))) for o in origins]
    finite = [v for v in origin_times if math.isfinite(v)]
    covered = sum(1 for v in finite if v <= 30.0)
    count = len(origins)
    return {
        "prefecture_code": pref_code,
        "prefecture_name": pref_name,
        "facility_type": "hospital",
        "threshold_min": 30,
        "covered_population_ratio": round(covered / count, 4) if count else None,
        "avg_travel_time_min": round(sum(finite) / len(finite), 1) if finite else None,
        "p90_travel_time_min": round(quantile(finite, 0.9), 1) if finite else None,
        "underserved_origin_count": sum(1 for v in origin_times if (not math.isfinite(v)) or v > 30.0),
        "facility_count": len(facilities),
        "origin_type": "sampled_origin_graph_proxy",
        "origin_cell_count": len(origins),
        "method_note": "Graph-based proxy built from real prefecture geometry and facility points, using synthetic road-like edges and shortest-path travel time.",
        "data_available": True,
        "data_basis": "real_prefecture_geometry_plus_facility_points_graph_proxy",
    }


def main():
    NETWORK_DIR.mkdir(exist_ok=True)
    ORIGINS_DIR.mkdir(exist_ok=True)
    ACC_DIR.mkdir(exist_ok=True)
    prefectures = load_json(DATA_DIR / "prefectures.json")
    metrics = load_json(DATA_DIR / "region_metrics.json")
    name_to_code = {m["region_name"]: m["region_code"] for m in metrics}
    features = prefectures.get("features", [])
    for feat in features:
        props = feat.get("properties", {})
        pref_name = props.get("N03_001") or props.get("name")
        pref_code = name_to_code.get(pref_name, "")
        if not pref_code:
            continue
        fac_path = FAC_DIR / f"{pref_code}_hospital.json"
        if not fac_path.exists():
            continue
        facilities = load_json(fac_path).get("items", [])
        geom = feat["geometry"]
        ring, centroid, area = largest_ring(geom)
        target_count = max(60, min(220, int(area * 2500)))
        origins = sample_origins(pref_code, ring, centroid, target_count)
        anchors = anchor_points_from_ring(pref_code, ring, centroid, count=16)
        nodes, edges = build_graph(pref_code, origins, facilities, anchors)
        dist_by_node = multi_source_dijkstra(nodes, edges, {f["facility_id"] for f in facilities})
        summary = build_summary(pref_code, pref_name, origins, facilities, dist_by_node)
        # preserve stronger Aomori data-basis note
        if pref_code == "02":
            summary["data_basis"] = "real_hospital_subset_plus_official_medical_area_names_graph_proxy"
        with (NETWORK_DIR / f"{pref_code}_road_nodes.json").open("w", encoding="utf-8") as f:
            json.dump({"items": nodes}, f, ensure_ascii=False, indent=2)
        with (NETWORK_DIR / f"{pref_code}_road_edges.json").open("w", encoding="utf-8") as f:
            json.dump({"items": edges}, f, ensure_ascii=False, indent=2)
        with (ORIGINS_DIR / f"{pref_code}_municipality_centroids.json").open("w", encoding="utf-8") as f:
            json.dump({"items": origins}, f, ensure_ascii=False, indent=2)
        acc_path = ACC_DIR / f"{pref_code}_hospital_summary.json"
        existing = load_json(acc_path) if acc_path.exists() else {}
        existing.update(summary)
        with acc_path.open("w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    print("Generated graph-based healthcare accessibility summaries.")


if __name__ == "__main__":
    main()
