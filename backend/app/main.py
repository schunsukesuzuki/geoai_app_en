from __future__ import annotations

import importlib.metadata
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

app = FastAPI(title="Regional Risk Simulator API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SummaryRequest(BaseModel):
    scenario: Literal["baseline", "medical", "housing", "family", "compact"]
    region_code: str


class RebuildRequest(BaseModel):
    fetch_public_data: bool = True


SCENARIO_LABELS = {
    "baseline": "Status Quo",
    "medical": "Medical Hub Reinforcement",
    "housing": "Vacant Housing Renewal Priority",
    "family": "Family Support Focus",
    "compact": "Hub Consolidation / Compactization",
}

SCENARIO_DESCRIPTIONS = {
    "baseline": "Scenario used as the baseline under the current policy level.",
    "medical": "Scenario prioritizing the prevention of healthcare access deterioration and strengthening hub functions.",
    "housing": "Scenario prioritizing vacant-house renewal and the reuse of existing housing stock.",
    "family": "Scenario prioritizing family support and mitigation of out-migration.",
    "compact": "Scenario combining functional concentration in priority districts with phased downsizing elsewhere.",
}

POLICY_LIBRARY = {
    "baseline": [
        "Shift from symptomatic measures to structural measures, starting with the highest-risk prefectures.",
        "Build region-specific policy directions over 5-10 years instead of relying on one-year measures.",
        "Under status quo, responses tend to stay local and require a redefinition of priorities.",
    ],
    "medical": [
        "Preserve living areas by prioritizing clinics and home-visit care deployment.",
        "Implement healthcare access improvements first in prefectures with higher aging rates.",
        "Design medical hubs together with public transit and mobility routes.",
    ],
    "housing": [
        "Prioritize the renovation and adaptive reuse of vacant houses to restore residential function.",
        "Use vacant homes near hospitals and public facilities as relocation options for older residents.",
        "Separate demolition from reuse and start with marketable housing stock.",
    ],
    "family": [
        "Improve childcare and education access to reduce youth out-migration.",
        "Concentrate relocation support for family households in transit-convenient districts.",
        "Bundle schools and daily services to create settlement incentives.",
    ],
    "compact": [
        "Concentrate healthcare and daily-life functions in priority districts to reduce maintenance cost.",
        "For shrinkage-candidate districts, present phased transition plans and build consensus.",
        "Show reinvestment areas and shrinkage areas on the same map to support accountability.",
    ],
}

WEIGHTS = {
    "aging_rate": 0.30,
    "vacancy_rate": 0.20,
    "depopulation_index": 0.25,
    "medical_access_risk": 0.25,
}

SHOCK_LIBRARY = {
    "energy_price": {
        "label": "Energy Price Shock",
        "description": "Case where higher fuel prices increase mobility, logistics, and hospital-visit costs.",
        "severity": 0.89,
    },
    "food_price": {
        "label": "Food Price Shock",
        "description": "Case where food-price increases worsen household burden and living costs.",
        "severity": 0.73,
    },
    "migration_pressure": {
        "label": "In-migration / Administrative Load Shock",
        "description": "Case where sudden in-migration raises housing, administrative, and daily-service pressure.",
        "severity": 0.69,
    },
}


def clamp(value: float, lower: float = 0.0, upper: float = 1.5) -> float:
    return max(lower, min(value, upper))


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


REGIONS: Dict[str, Any] = {}
REGION_METRICS: List[Dict[str, Any]] = []
MODEL_INFO: Dict[str, Any] = {}
SOURCE_METADATA: Dict[str, Any] = {"sources": []}

DECISIONS_FILE = DATA_DIR / "decisions.json"
AGENT_RUNS_FILE = DATA_DIR / "agent_runs.json"
FACILITIES_DIR = DATA_DIR / "facilities"
LIVING_AREAS_DIR = DATA_DIR / "living_areas"
ACCESSIBILITY_DIR = DATA_DIR / "accessibility"
NETWORK_DIR = DATA_DIR / "network"
ORIGINS_DIR = DATA_DIR / "origins"
HEALTHCARE_PRIORITIES_DIR = DATA_DIR / "healthcare_priorities"
HEALTHCARE_TIMELINE_DIR = DATA_DIR / "healthcare_timeline"
FEATURE_REFRESH_DIR = DATA_DIR / "feature_refresh"
SPATIAL_ASSETS_FILE = DATA_DIR / "spatial_assets.json"
ENTITY_ASSET_BINDINGS_FILE = DATA_DIR / "entity_asset_bindings.json"
AUDIT_EVENTS_FILE = DATA_DIR / "audit_events.json"
AUDIT_SNAPSHOTS_FILE = DATA_DIR / "audit_snapshots.json"
DECISION_CHAIN_LINKS_FILE = DATA_DIR / "decision_chain_links.json"


class ScenarioGenerateRequest(BaseModel):
    region_id: str
    policy_focus: str = "balanced"
    budget_level: str = "medium"
    constraints: Dict[str, Any] = {}


class ScenarioCompareRequest(BaseModel):
    region_id: str
    baseline_scenario_id: str = "baseline"
    candidate_scenario_ids: List[str]


class DecisionCreateRequest(BaseModel):
    region_id: str
    selected_scenario_id: str
    status: Literal["approved", "pending", "rejected"]
    reviewer_comment: str = ""
    rationale_tags: List[str] = []


class ReportGenerateRequest(BaseModel):
    decision_id: str
    format: Literal["memo", "comparison"] = "memo"
    audience: str = "municipal_executive"


class ExplainScenarioAgentRequest(BaseModel):
    region_id: str
    baseline_scenario_id: str = "baseline"
    candidate_scenario_id: str




class FeatureRefreshReviewRequest(BaseModel):
    candidate_id: str
    decision: Literal["approved", "rejected"]
    reviewer_comment: str = ""


def resolve_feature_refresh_candidates_file(feature_type: str = "hospital") -> Path:
    return FEATURE_REFRESH_DIR / f"{feature_type}_refresh_candidates.json"


def resolve_feature_refresh_observed_file(feature_type: str = "hospital") -> Path:
    return FEATURE_REFRESH_DIR / f"observed_{feature_type}s.json"


def resolve_feature_refresh_updates_file(feature_type: str = "hospital") -> Path:
    return FEATURE_REFRESH_DIR / f"{feature_type}_approved_updates.json"


def get_feature_refresh_candidates_slice(prefecture_code: str, feature_type: str = "hospital") -> Dict[str, Any]:
    payload = load_optional_json(resolve_feature_refresh_candidates_file(feature_type), {"items": []})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    filtered = [item for item in items if item.get("prefecture_code") == prefecture_code and item.get("feature_type") == feature_type]
    return {"prefecture_code": prefecture_code, "feature_type": feature_type, "items": filtered, "data_available": bool(filtered)}


def load_feature_refresh_candidates(feature_type: str = "hospital") -> Dict[str, Any]:
    return load_optional_json(resolve_feature_refresh_candidates_file(feature_type), {"items": []})


def save_feature_refresh_candidates(payload: Dict[str, Any], feature_type: str = "hospital") -> None:
    resolve_feature_refresh_candidates_file(feature_type).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_feature_refresh_updates(feature_type: str = "hospital") -> Dict[str, Any]:
    return load_optional_json(resolve_feature_refresh_updates_file(feature_type), {"items": []})


def save_feature_refresh_updates(payload: Dict[str, Any], feature_type: str = "hospital") -> None:
    resolve_feature_refresh_updates_file(feature_type).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def reload_data_artifacts() -> None:
    global REGIONS, REGION_METRICS, MODEL_INFO, SOURCE_METADATA
    REGIONS = load_json(DATA_DIR / "regions.geojson")
    REGION_METRICS = load_json(DATA_DIR / "region_metrics.json")
    MODEL_INFO = load_json(DATA_DIR / "model_info.json")
    metadata_candidates = [DATA_DIR / "source_metadata.json", DATA_DIR / "raw" / "source_metadata.json"]
    for candidate in metadata_candidates:
        if candidate.exists():
            SOURCE_METADATA = load_json(candidate)
            break
    else:
        SOURCE_METADATA = {"sources": []}


def get_modifiers(scenario: str) -> Dict[str, float]:
    if scenario == "baseline":
        return {"aging": 1.0, "vacancy": 1.0, "depop": 1.0, "medical": 1.0, "childcare": 1.0}
    if scenario == "medical":
        return {"aging": 0.95, "vacancy": 1.0, "depop": 0.97, "medical": 0.78, "childcare": 1.0}
    if scenario == "housing":
        return {"aging": 0.98, "vacancy": 0.78, "depop": 0.92, "medical": 0.97, "childcare": 1.0}
    if scenario == "family":
        return {"aging": 0.97, "vacancy": 0.95, "depop": 0.82, "medical": 0.96, "childcare": 0.76}
    if scenario == "compact":
        return {"aging": 0.94, "vacancy": 0.88, "depop": 0.86, "medical": 0.84, "childcare": 0.94}
    raise HTTPException(status_code=400, detail="Unknown scenario")


def weighted_score(item: Dict[str, Any]) -> float:
    return (
        item["aging_rate"] * WEIGHTS["aging_rate"]
        + item["vacancy_rate"] * WEIGHTS["vacancy_rate"]
        + item["depopulation_index"] * WEIGHTS["depopulation_index"]
        + item["medical_access_risk"] * WEIGHTS["medical_access_risk"]
    )


def get_scenario_intensity(scenario: str) -> float:
    modifiers = get_modifiers(scenario)
    return round(
        abs(1 - modifiers["aging"])
        + abs(1 - modifiers["vacancy"])
        + abs(1 - modifiers["depop"])
        + abs(1 - modifiers["medical"])
        + abs(1 - modifiers["childcare"]),
        4,
    )


def build_shock_profile(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    scores = [
        (
            "energy_price",
            SHOCK_LIBRARY["energy_price"]["label"],
            item.get("energy_price_shock", 0.0),
            SHOCK_LIBRARY["energy_price"]["severity"],
            round(item.get("energy_price_shock", 0.0) * SHOCK_LIBRARY["energy_price"]["severity"], 4),
        ),
        (
            "food_price",
            SHOCK_LIBRARY["food_price"]["label"],
            item.get("food_price_shock", 0.0),
            SHOCK_LIBRARY["food_price"]["severity"],
            round(item.get("food_price_shock", 0.0) * SHOCK_LIBRARY["food_price"]["severity"], 4),
        ),
        (
            "migration_pressure",
            SHOCK_LIBRARY["migration_pressure"]["label"],
            item.get("service_capacity_pressure", 0.0),
            SHOCK_LIBRARY["migration_pressure"]["severity"],
            round(item.get("service_capacity_pressure", 0.0) * SHOCK_LIBRARY["migration_pressure"]["severity"], 4),
        ),
    ]
    ranked = sorted(scores, key=lambda x: x[4], reverse=True)
    return [
        {
            "shock_key": key,
            "shock_label": label,
            "description": SHOCK_LIBRARY[key]["description"],
            "score": score,
            "severity": severity,
            "expected_risk_uplift": uplift,
        }
        for key, label, score, severity, uplift in ranked
    ]


def build_uncertainty_summary(item: Dict[str, Any], scenario: str, total_risk_score: float) -> Dict[str, Any]:
    data_quality = clamp(1 - float(item.get("data_quality_score", 0.8)), 0.0, 1.0)
    model = clamp(float(item.get("model_uncertainty", 0.03)) * 8.0, 0.0, 1.0)
    external = clamp(float(item.get("external_volatility", 0.5)), 0.0, 1.0)
    overall = round(0.35 * data_quality + 0.35 * model + 0.30 * external, 4)
    if overall < 0.28:
        label = "Low"
    elif overall < 0.48:
        label = "Medium"
    else:
        label = "High"
    width = round(
        item.get("prediction_interval", 0.0)
        + 0.06 * overall
        + 0.02 * get_scenario_intensity(scenario)
        + 0.015 * total_risk_score,
        4,
    )
    return {
        "data_quality": round(data_quality, 4),
        "model": round(model, 4),
        "external": round(external, 4),
        "overall_score": overall,
        "overall_label": label,
        "overall_width": width,
        "external_shock_exposure": round(mean([item.get("energy_price_shock", 0.0), item.get("food_price_shock", 0.0), item.get("service_capacity_pressure", 0.0)]), 4),
        "estimated_relative_width": round(width / max(total_risk_score, 0.001), 4),
    }


def stable_seed(*parts: str) -> int:
    text = "|".join(parts)
    return abs(hash(text)) % (2**32)


def simulate_risk_distribution(item: Dict[str, Any], scenario: str, base_score: float) -> Dict[str, float]:
    seed = stable_seed(item["region_code"], scenario)
    random.seed(seed)
    uncertainty = build_uncertainty_summary(item, scenario, base_score)
    width = max(uncertainty["overall_width"], 0.005)
    samples = []
    for _ in range(300):
        noise = random.gauss(0.0, width / 2.8)
        shock = random.uniform(0.0, width / 3.0)
        samples.append(max(0.0, base_score + noise + shock))
    samples.sort()

    def percentile(p: float) -> float:
        index = int((len(samples) - 1) * p)
        return round(samples[index], 4)

    return {
        "mean": round(sum(samples) / len(samples), 4),
        "std": round((sum((x - (sum(samples) / len(samples))) ** 2 for x in samples) / len(samples)) ** 0.5, 4),
        "p10": percentile(0.10),
        "p50": percentile(0.50),
        "p90": percentile(0.90),
    }


def calculate_scenario_metrics(scenario: str) -> List[Dict[str, Any]]:
    modifiers = get_modifiers(scenario)
    rows: List[Dict[str, Any]] = []
    for item in REGION_METRICS:
        row = dict(item)
        adjusted = {
            "aging_rate": clamp(row["aging_rate"] * modifiers["aging"]),
            "vacancy_rate": clamp(row["vacancy_rate"] * modifiers["vacancy"]),
            "depopulation_index": clamp(row["depopulation_index"] * modifiers["depop"]),
            "medical_access_risk": clamp(row["medical_access_risk"] * modifiers["medical"]),
            "childcare_access_score": clamp(row["childcare_access_score"] * modifiers["childcare"]),
        }
        row.update(adjusted)
        total = round(weighted_score(row), 4)
        distribution = simulate_risk_distribution(row, scenario, total)
        uncertainty = build_uncertainty_summary(row, scenario, total)
        row["total_risk_score"] = total
        row["risk_distribution"] = distribution
        row["uncertainty"] = uncertainty
        row["shock_sensitivity"] = build_shock_profile(row)
        rows.append(row)

    rows.sort(key=lambda x: (x["total_risk_score"], x["risk_distribution"]["p90"]), reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["priority_rank"] = idx
    robust_rows = sorted(rows, key=lambda x: x["risk_distribution"]["p90"], reverse=True)
    robust_rank_map = {row["region_code"]: idx for idx, row in enumerate(robust_rows, start=1)}
    for row in rows:
        row["robust_priority_rank"] = robust_rank_map[row["region_code"]]
    return rows


def explain_drivers(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    factors = [
        ("Aging Rate", "aging_rate", item.get("aging_rate", 0.0), item.get("aging_rate", 0.0) * WEIGHTS["aging_rate"]),
        ("Vacancy Rate", "vacancy_rate", item.get("vacancy_rate", 0.0), item.get("vacancy_rate", 0.0) * WEIGHTS["vacancy_rate"]),
        ("Depopulation Index", "depopulation_index", item.get("depopulation_index", 0.0), item.get("depopulation_index", 0.0) * WEIGHTS["depopulation_index"]),
        ("Healthcare Access", "medical_access_risk", item.get("medical_access_risk", 0.0), item.get("medical_access_risk", 0.0) * WEIGHTS["medical_access_risk"]),
        ("Family Support Access", "childcare_access_score", 1 - item.get("childcare_access_score", 0.0), (1 - item.get("childcare_access_score", 0.0)) * 0.15),
    ]
    factors.sort(key=lambda x: x[3], reverse=True)
    return [
        {"factor": factor, "key": key, "value": round(value, 4), "weighted": round(weighted, 4)}
        for factor, key, value, weighted in factors
    ]


def build_scenario_comparison(region_code: str) -> Dict[str, Any]:
    scenario_rows = []
    for scenario, label in SCENARIO_LABELS.items():
        item = next((r for r in calculate_scenario_metrics(scenario) if r["region_code"] == region_code), None)
        if item is None:
            continue
        drivers = explain_drivers(item)[:3]
        scenario_rows.append(
            {
                "scenario": scenario,
                "scenario_label": label,
                "description": SCENARIO_DESCRIPTIONS[scenario],
                "total_risk_score": item["total_risk_score"],
                "priority_rank": item["priority_rank"],
                "robust_priority_rank": item["robust_priority_rank"],
                "population_2035": item["population_2035"],
                "top_driver": drivers[0]["factor"],
                "top_drivers": drivers,
                "risk_distribution": item["risk_distribution"],
                "uncertainty": item["uncertainty"],
                "top_shocks": item["shock_sensitivity"][:2],
            }
        )
    if not scenario_rows:
        raise HTTPException(status_code=404, detail="Region not found")
    baseline = next(x for x in scenario_rows if x["scenario"] == "baseline")
    for row in scenario_rows:
        row["risk_delta_vs_baseline"] = round(row["total_risk_score"] - baseline["total_risk_score"], 4)
        row["p90_delta_vs_baseline"] = round(row["risk_distribution"]["p90"] - baseline["risk_distribution"]["p90"], 4)
    recommended = min(scenario_rows, key=lambda x: x["total_risk_score"])
    robust_recommended = min(scenario_rows, key=lambda x: x["risk_distribution"]["p90"])
    gap = round(baseline["total_risk_score"] - recommended["total_risk_score"], 4)
    robust_gap = round(baseline["risk_distribution"]["p90"] - robust_recommended["risk_distribution"]["p90"], 4)
    alternatives = []
    for row in sorted(scenario_rows, key=lambda x: x["total_risk_score"]):
        alternatives.append(
            {
                "scenario": row["scenario"],
                "scenario_label": row["scenario_label"],
                "expected_risk": row["total_risk_score"],
                "expected_p90": row["risk_distribution"]["p90"],
                "rank": row["priority_rank"],
                "robust_rank": row["robust_priority_rank"],
                "delta_vs_baseline": row["risk_delta_vs_baseline"],
                "p90_delta_vs_baseline": row["p90_delta_vs_baseline"],
                "why": POLICY_LIBRARY[row["scenario"]][0],
            }
        )
    return {
        "recommended_scenario": recommended["scenario"],
        "recommended_scenario_label": recommended["scenario_label"],
        "robust_recommended_scenario": robust_recommended["scenario"],
        "robust_recommended_scenario_label": robust_recommended["scenario_label"],
        "baseline_risk": baseline["total_risk_score"],
        "baseline_p90": baseline["risk_distribution"]["p90"],
        "recommended_risk": recommended["total_risk_score"],
        "recommended_p90": robust_recommended["risk_distribution"]["p90"],
        "improvement_vs_baseline": gap,
        "robust_improvement_vs_baseline": robust_gap,
        "rationale": f"By expected value, {recommended['scenario_label']}、 under worst-case resilience, {robust_recommended['scenario_label']} is best.",
        "robustness_note": f"The p90 improvement margin is {robust_gap:.4f}。",
        "scenario_comparison": scenario_rows,
        "policy_options": alternatives[:3],
    }


@app.on_event("startup")
def startup_log() -> None:
    reload_data_artifacts()
    if not DECISIONS_FILE.exists():
        DECISIONS_FILE.write_text("[]", encoding="utf-8")
    for path in [AGENT_RUNS_FILE, AUDIT_EVENTS_FILE, AUDIT_SNAPSHOTS_FILE, DECISION_CHAIN_LINKS_FILE]:
        if not path.exists():
            path.write_text("[]", encoding="utf-8")
    try:
        sdk_version = importlib.metadata.version("openai")
    except Exception:
        sdk_version = "unknown"
    print("openai_version=", sdk_version)
    print("openai_model=", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    print("openai_key_present=", bool(os.getenv("OPENAI_API_KEY", "").strip()))



def load_optional_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return load_json(path)
    except Exception:
        return default
    return default


def resolve_facility_file(prefecture_code: str, facility_type: str) -> Path:
    return FACILITIES_DIR / f"{prefecture_code}_{facility_type}.json"


def resolve_living_area_file(prefecture_code: str, living_area_type: str) -> Path:
    return LIVING_AREAS_DIR / f"{prefecture_code}_{living_area_type}.geojson"


def resolve_accessibility_file(prefecture_code: str, facility_type: str) -> Path:
    return ACCESSIBILITY_DIR / f"{prefecture_code}_{facility_type}_summary.json"


def get_facility_slice(prefecture_code: str, facility_type: str = "hospital") -> List[Dict[str, Any]]:
    payload = load_optional_json(resolve_facility_file(prefecture_code, facility_type), {"items": []})
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    return items if isinstance(items, list) else []


def get_healthcare_areas(prefecture_code: str, living_area_type: str = "healthcare") -> Dict[str, Any]:
    payload = load_optional_json(resolve_living_area_file(prefecture_code, living_area_type), {"type": "FeatureCollection", "features": []})
    return payload if isinstance(payload, dict) else {"type": "FeatureCollection", "features": []}


def build_empty_accessibility_summary(prefecture_code: str, facility_type: str) -> Dict[str, Any]:
    return {
        "prefecture_code": prefecture_code,
        "facility_type": facility_type,
        "threshold_min": 30,
        "covered_population_ratio": None,
        "avg_travel_time_min": None,
        "p90_travel_time_min": None,
        "underserved_origin_count": None,
        "facility_count": 0,
        "data_available": False,
        "data_basis": "unavailable",
    }




def resolve_network_nodes_file(prefecture_code: str) -> Path:
    return NETWORK_DIR / f"{prefecture_code}_road_nodes.json"


def resolve_network_edges_file(prefecture_code: str) -> Path:
    return NETWORK_DIR / f"{prefecture_code}_road_edges.json"


def resolve_origins_file(prefecture_code: str) -> Path:
    return ORIGINS_DIR / f"{prefecture_code}_municipality_centroids.json"


def get_network_slice(prefecture_code: str) -> Dict[str, Any]:
    nodes = load_optional_json(resolve_network_nodes_file(prefecture_code), {"items": []})
    edges = load_optional_json(resolve_network_edges_file(prefecture_code), {"items": []})
    node_items = nodes.get("items", []) if isinstance(nodes, dict) else []
    edge_items = edges.get("items", []) if isinstance(edges, dict) else []
    return {
        "prefecture_code": prefecture_code,
        "nodes": node_items,
        "edges": edge_items,
        "meta": {"node_count": len(node_items), "edge_count": len(edge_items)},
    }


def get_origin_slice(prefecture_code: str) -> Dict[str, Any]:
    payload = load_optional_json(resolve_origins_file(prefecture_code), {"items": []})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return {"prefecture_code": prefecture_code, "items": items}

def resolve_healthcare_priority_file(prefecture_code: str, kind: str) -> Path:
    return HEALTHCARE_PRIORITIES_DIR / f"{prefecture_code}_{kind}.json"

def get_healthcare_priorities_slice(prefecture_code: str) -> Dict[str, Any]:
    payload = load_optional_json(resolve_healthcare_priority_file(prefecture_code, "living_area_priority_decisions"), {"items": []})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return {"prefecture_code": prefecture_code, "items": items, "data_available": bool(items)}


def resolve_healthcare_timeline_file(prefecture_code: str) -> Path:
    return HEALTHCARE_TIMELINE_DIR / f"{prefecture_code}_healthcare_states.json"


def get_healthcare_timeline_slice(prefecture_code: str, year: int) -> Dict[str, Any]:
    payload = load_optional_json(resolve_healthcare_timeline_file(prefecture_code), {})
    if not isinstance(payload, dict) or not payload:
        return {
            "prefecture_code": prefecture_code,
            "year": year,
            "available_years": [2025, 2030, 2035, 2040],
            "summary": build_empty_accessibility_summary(prefecture_code, "hospital"),
            "items": [],
            "data_available": False,
        }
    years = payload.get("available_years", [2025, 2030, 2035, 2040])
    year_key = str(year)
    summary = (payload.get("summary_by_year") or {}).get(year_key) or build_empty_accessibility_summary(prefecture_code, "hospital")
    items = (payload.get("items_by_year") or {}).get(year_key, [])
    return {
        "prefecture_code": prefecture_code,
        "year": year,
        "available_years": years,
        "summary": summary,
        "items": items,
        "data_available": bool(items),
    }



def get_spatial_assets_slice(prefecture_code: str, entity_type: str | None = None, asset_type: str | None = None) -> Dict[str, Any]:
    items = load_optional_json(SPATIAL_ASSETS_FILE, [])
    if not isinstance(items, list):
        items = []
    filtered = [item for item in items if item.get("prefecture_code") == prefecture_code]
    if entity_type:
        filtered = [item for item in filtered if item.get("entity_type") == entity_type]
    if asset_type:
        filtered = [item for item in filtered if item.get("asset_type") == asset_type]
    return {"prefecture_code": prefecture_code, "items": filtered, "data_available": bool(filtered)}


def get_entity_asset_bindings(entity_id: str) -> Dict[str, Any]:
    items = load_optional_json(ENTITY_ASSET_BINDINGS_FILE, [])
    if not isinstance(items, list):
        items = []
    filtered = [item for item in items if item.get("entity_id") == entity_id]
    return {"entity_id": entity_id, "items": filtered, "data_available": bool(filtered)}

def get_accessibility_summary_slice(prefecture_code: str, facility_type: str = "hospital") -> Dict[str, Any]:
    payload = load_optional_json(resolve_accessibility_file(prefecture_code, facility_type), {})
    if not isinstance(payload, dict) or not payload:
        return build_empty_accessibility_summary(prefecture_code, facility_type)
    payload.setdefault("data_available", True)
    return payload


@app.get("/")
def root() -> Dict[str, str]:
    return {"name": "Regional Risk Simulator API", "status": "ok"}


@app.get("/api/health")
def health() -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    return {
        "status": "ok",
        "openai": {
            "configured": bool(api_key),
            "sdk_available": OpenAI is not None,
            "model": model,
            "fallback_mode": False,
        },
        "rebuild": {
            "supported": True,
            "scripts_present": (Path("/app/scripts/fetch_public_data.py").exists() and Path("/app/scripts/build_region_metrics.py").exists()),
        },
    }


@app.get("/api/regions")
def get_regions() -> Dict[str, Any]:
    return REGIONS


@app.get("/api/model-info")
def get_model_info() -> Dict[str, Any]:
    payload = dict(MODEL_INFO)
    payload["sources"] = SOURCE_METADATA.get("sources", [])
    return payload


@app.get("/api/facilities")
def get_facilities(prefecture: str, type: str = "hospital") -> Dict[str, Any]:
    return {"items": get_facility_slice(prefecture, type)}


@app.get("/api/living-areas")
def get_living_areas(prefecture: str, type: str = "healthcare") -> Dict[str, Any]:
    payload = get_healthcare_areas(prefecture, type)
    features = payload.get("features", []) if isinstance(payload, dict) else []
    items = []
    for feature in features:
        props = feature.get("properties", {})
        items.append({
            "living_area_id": props.get("living_area_id"),
            "living_area_type": props.get("living_area_type", type),
            "prefecture_code": props.get("prefecture_code", prefecture),
            "name": props.get("name"),
            "geometry": feature.get("geometry"),
            "source_dataset": props.get("source_dataset", "healthcare area slice"),
            "representative_hospital": props.get("representative_hospital"),
            "municipalities": props.get("municipalities", []),
            "geometry_note": props.get("geometry_note", ""),
            "proxy_mode": props.get("proxy_mode", False),
        })
    return {"items": items}


@app.get("/api/accessibility/summary")
def get_accessibility_summary(prefecture: str, facility_type: str = "hospital") -> Dict[str, Any]:
    return get_accessibility_summary_slice(prefecture, facility_type)




@app.get("/api/network/prefecture/{prefecture_code}")
def get_network(prefecture_code: str) -> Dict[str, Any]:
    return get_network_slice(prefecture_code)


@app.get("/api/accessibility/origins")
def get_accessibility_origins(prefecture: str, facility_type: str = "hospital") -> Dict[str, Any]:
    return get_origin_slice(prefecture)





@app.get("/api/spatial-assets")
def get_spatial_assets(prefecture: str, entity_type: str | None = None, asset_type: str | None = None) -> Dict[str, Any]:
    return get_spatial_assets_slice(prefecture, entity_type, asset_type)


@app.get("/api/spatial-assets/bindings")
def get_spatial_asset_bindings(entity_id: str) -> Dict[str, Any]:
    return get_entity_asset_bindings(entity_id)

@app.get("/api/feature-refresh/candidates")
def get_feature_refresh_candidates(prefecture: str, feature_type: str = "hospital") -> Dict[str, Any]:
    return get_feature_refresh_candidates_slice(prefecture, feature_type)


@app.post("/api/feature-refresh/review")
def review_feature_refresh_candidate(req: FeatureRefreshReviewRequest) -> Dict[str, Any]:
    payload = load_feature_refresh_candidates("hospital")
    items = payload.get("items", []) if isinstance(payload, dict) else []
    target = next((item for item in items if item.get("candidate_id") == req.candidate_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Feature refresh candidate not found")
    target["status"] = req.decision
    target["reviewer_comment"] = req.reviewer_comment
    target["reviewed_at"] = datetime.now(timezone.utc).astimezone().isoformat()
    save_feature_refresh_candidates({"items": items}, "hospital")

    updates = load_feature_refresh_updates("hospital")
    update_items = updates.get("items", []) if isinstance(updates, dict) else []
    approved_update = None
    if req.decision == "approved":
        applied_action = {"new": "add", "moved": "move", "retired": "retire", "attribute_change": "patch"}.get(target.get("candidate_type"), "patch")
        existing = next((u for u in update_items if u.get("candidate_id") == req.candidate_id), None)
        if existing is None:
            approved_update = {
                "update_id": f"upd_{uuid4().hex[:12]}",
                "candidate_id": req.candidate_id,
                "prefecture_code": target.get("prefecture_code"),
                "feature_type": target.get("feature_type", "hospital"),
                "applied_action": applied_action,
                "approved_at": datetime.now(timezone.utc).astimezone().isoformat(),
                "reviewer_comment": req.reviewer_comment,
            }
            update_items.append(approved_update)
            save_feature_refresh_updates({"items": update_items}, "hospital")
        else:
            approved_update = existing
    snapshot = create_audit_snapshot(
        "feature_layer_snapshot",
        {"candidate": target, "review_decision": req.decision, "approved_update": approved_update},
        prefecture_code=target.get("prefecture_code"),
        metadata={"feature_type": target.get("feature_type", "hospital")},
    )
    input_refs = [make_entity_ref("refresh_candidate", req.candidate_id)]
    output_refs = []
    if approved_update:
        output_refs.append(make_entity_ref("approved_update", approved_update["update_id"]))
    record_audit_event(
        "feature_refresh_reviewed",
        "human",
        req.decision,
        prefecture_code=target.get("prefecture_code"),
        input_refs=input_refs,
        output_refs=output_refs,
        snapshot_id=snapshot["snapshot_id"],
        metadata={"candidate_type": target.get("candidate_type"), "reviewer_comment": req.reviewer_comment},
    )
    upsert_decision_chain(
        "refresh_candidate",
        req.candidate_id,
        successor_refs=output_refs,
        metadata={"prefecture_code": target.get("prefecture_code")},
    )
    if approved_update:
        upsert_decision_chain(
            "approved_update",
            approved_update["update_id"],
            predecessor_refs=[make_entity_ref("refresh_candidate", req.candidate_id)],
            metadata={"prefecture_code": target.get("prefecture_code")},
        )
    return {"status": "ok", "candidate": target, "approved_updates": len(update_items)}

@app.get("/api/healthcare-priorities")
def get_healthcare_priorities(prefecture: str) -> Dict[str, Any]:
    return get_healthcare_priorities_slice(prefecture)


@app.get("/api/healthcare-timeline")
def get_healthcare_timeline(prefecture: str, year: int = 2025) -> Dict[str, Any]:
    return get_healthcare_timeline_slice(prefecture, year)

@app.get("/api/metrics")
def get_metrics(scenario: str = "baseline") -> Dict[str, Any]:
    return {"scenario": scenario, "items": calculate_scenario_metrics(scenario)}


@app.get("/api/reasoning")
def get_reasoning(region_code: str, scenario: str = "baseline") -> Dict[str, Any]:
    row = next((item for item in calculate_scenario_metrics(scenario) if item["region_code"] == region_code), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Region not found")
    comparison = build_scenario_comparison(region_code)
    return {
        "region_code": row["region_code"],
        "region_name": row["region_name"],
        "primary_factors": explain_drivers(row)[:3],
        "uncertainty": row["uncertainty"],
        "risk_distribution": row["risk_distribution"],
        "shock_sensitivity": row["shock_sensitivity"],
        "model_signal": {
            "predicted_annual_decline_rate": row["predicted_annual_decline_rate"],
            "prediction_interval": row["prediction_interval"],
            "population_2035": row["population_2035"],
            "source_years": row["source_years"],
        },
        "comparison": comparison,
    }


@app.post("/api/admin/rebuild-data")
def rebuild_data(req: RebuildRequest) -> Dict[str, Any]:
    script_dir = Path("/app/scripts")
    fetch_script = script_dir / "fetch_public_data.py"
    build_script = script_dir / "build_region_metrics.py"
    if not build_script.exists():
        raise HTTPException(status_code=500, detail="build_region_metrics.py is missing in the backend container.")

    commands = []
    if req.fetch_public_data:
        if not fetch_script.exists():
            raise HTTPException(status_code=500, detail="fetch_public_data.py is missing in the backend container.")
        commands.append([sys.executable, str(fetch_script)])
    commands.append([sys.executable, str(build_script)])

    logs: List[Dict[str, Any]] = []
    try:
        for command in commands:
            result = subprocess.run(command, cwd="/app", capture_output=True, text=True, check=True)
            logs.append({
                "command": " ".join(command),
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            })
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Data rebuild failed.",
                "command": " ".join(exc.cmd),
                "returncode": exc.returncode,
                "stdout": (exc.stdout or "").strip(),
                "stderr": (exc.stderr or "").strip(),
            },
        )

    reload_data_artifacts()
    return {
        "status": "ok",
        "message": "Public data fetched and Bayesian model artifacts rebuilt.",
        "fetch_public_data": req.fetch_public_data,
        "model_name": MODEL_INFO.get("model_name"),
        "train_years": MODEL_INFO.get("train_years"),
        "sample_count": MODEL_INFO.get("sample_count"),
        "logs": logs,
    }


@app.post("/api/summary")
def summarize_region(req: SummaryRequest) -> Dict[str, Any]:
    metrics = calculate_scenario_metrics(req.scenario)
    row = next((item for item in metrics if item["region_code"] == req.region_code), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Region not found")

    comparison = build_scenario_comparison(req.region_code)
    current_label = SCENARIO_LABELS[req.scenario]
    recommended_label = comparison["recommended_scenario_label"]
    robust_label = comparison["robust_recommended_scenario_label"]
    improvement = comparison["improvement_vs_baseline"]
    robust_improvement = comparison["robust_improvement_vs_baseline"]
    top_factors = ", ".join([x["factor"] for x in explain_drivers(row)[:2]])
    top_shocks = ", ".join([x["shock_label"] for x in row["shock_sensitivity"][:2]])

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set on the backend container.")
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="OpenAI SDK is not available in the backend container.")

    prompt = f"""
You are a policy analyst for municipalities. Based on the information below, write a short three-paragraph policy memo.
- Paragraph 1: structural risk and main drivers
- Paragraph 2: model estimate and uncertainty
- Paragraph 3: recommendation based on scenario comparison
- Include at least three numerical values
- Avoid generic statements and be specific
- Explicitly mention the region name and scenario name

Region Name: {row['region_name']}
Displayed Scenario: {current_label}
Expected Risk: {row['total_risk_score']}
p90: {row['risk_distribution']['p90']}
Rank: {row['priority_rank']}
Aging Rate: {row['aging_rate']}
Vacancy Rate: {row['vacancy_rate']}
Depopulation Index: {row['depopulation_index']}
Healthcare Access Risk: {row['medical_access_risk']}
Annual Population Decline Rate: {row['predicted_annual_decline_rate']}
2035 Population: {row['population_2035']}
Prediction Interval Width: {row['prediction_interval']}
Top Factors: {top_factors}
Major Shocks: {top_shocks}
Best by Expected Value: {recommended_label}
Best by p90: {robust_label}
Expected Improvement: {improvement}
p90 Improvement: {robust_improvement}
""".strip()

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "developer",
                    "content": "You are a concise and practical regional policy analyst. Answer in English.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.4,
        )
        text = response.choices[0].message.content if response.choices else ""
        if not text or not str(text).strip():
            raise RuntimeError("OpenAI response was empty.")
        resolved_model = getattr(response, "model", None) or model
        return {
            "summary": str(text).strip(),
            "source": "openai",
            "model": resolved_model,
            "fallback_used": False,
        }
    except Exception as exc:
        detail = f"OpenAI summary generation failed: {type(exc).__name__}: {exc}"
        raise HTTPException(status_code=502, detail=detail)



def get_region_or_404(region_code: str, scenario: str = "baseline") -> Dict[str, Any]:
    if not REGION_METRICS:
        reload_data_artifacts()
    row = next((item for item in calculate_scenario_metrics(scenario) if item["region_code"] == region_code), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Region not found")
    return row


def load_decisions() -> List[Dict[str, Any]]:
    if not DECISIONS_FILE.exists():
        return []
    try:
        return json.loads(DECISIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_decisions(rows: List[Dict[str, Any]]) -> None:
    DECISIONS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_agent_runs() -> List[Dict[str, Any]]:
    if not AGENT_RUNS_FILE.exists():
        return []
    try:
        return json.loads(AGENT_RUNS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_agent_runs(rows: List[Dict[str, Any]]) -> None:
    AGENT_RUNS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")




def load_audit_events() -> List[Dict[str, Any]]:
    return load_optional_json(AUDIT_EVENTS_FILE, []) or []


def save_audit_events(rows: List[Dict[str, Any]]) -> None:
    AUDIT_EVENTS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_audit_snapshots() -> List[Dict[str, Any]]:
    return load_optional_json(AUDIT_SNAPSHOTS_FILE, []) or []


def save_audit_snapshots(rows: List[Dict[str, Any]]) -> None:
    AUDIT_SNAPSHOTS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_decision_chain_links() -> List[Dict[str, Any]]:
    return load_optional_json(DECISION_CHAIN_LINKS_FILE, []) or []


def save_decision_chain_links(rows: List[Dict[str, Any]]) -> None:
    DECISION_CHAIN_LINKS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def make_entity_ref(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def parse_entity_ref(ref: str) -> Dict[str, str]:
    entity_type, entity_id = (ref.split(':', 1) + [''])[:2]
    return {"entity_type": entity_type, "entity_id": entity_id}


def create_audit_snapshot(snapshot_type: str, payload: Dict[str, Any], prefecture_code: Optional[str] = None, year: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    snapshots = load_audit_snapshots()
    snapshot = {
        "snapshot_id": f"snap_{uuid4().hex[:12]}",
        "snapshot_type": snapshot_type,
        "prefecture_code": prefecture_code,
        "year": year,
        "created_at": now_jst_iso(),
        "payload": payload,
        "metadata": metadata or {},
    }
    snapshots.append(snapshot)
    save_audit_snapshots(snapshots)
    return snapshot


def upsert_decision_chain(entity_type: str, entity_id: str, predecessor_refs: Optional[List[str]] = None, successor_refs: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    predecessor_refs = predecessor_refs or []
    successor_refs = successor_refs or []
    rows = load_decision_chain_links()
    row = next((r for r in rows if r.get("entity_type") == entity_type and r.get("entity_id") == entity_id), None)
    if row is None:
        row = {
            "chain_link_id": f"chain_{uuid4().hex[:12]}",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "predecessor_refs": [],
            "successor_refs": [],
            "created_at": now_jst_iso(),
            "metadata": metadata or {},
        }
        rows.append(row)
    row["predecessor_refs"] = sorted(set(row.get("predecessor_refs", []) + predecessor_refs))
    row["successor_refs"] = sorted(set(row.get("successor_refs", []) + successor_refs))
    if metadata:
        row["metadata"] = {**row.get("metadata", {}), **metadata}
    # backfill successor links on predecessors that are explicit entity refs
    for ref in predecessor_refs:
        parsed = parse_entity_ref(ref)
        if not parsed["entity_type"] or not parsed["entity_id"]:
            continue
        pred = next((r for r in rows if r.get("entity_type") == parsed["entity_type"] and r.get("entity_id") == parsed["entity_id"]), None)
        if pred is None:
            pred = {
                "chain_link_id": f"chain_{uuid4().hex[:12]}",
                "entity_type": parsed["entity_type"],
                "entity_id": parsed["entity_id"],
                "predecessor_refs": [],
                "successor_refs": [],
                "created_at": now_jst_iso(),
                "metadata": {},
            }
            rows.append(pred)
        pred["successor_refs"] = sorted(set(pred.get("successor_refs", []) + [make_entity_ref(entity_type, entity_id)]))
    save_decision_chain_links(rows)
    return row


def record_audit_event(event_type: str, actor_type: str, status: str, *, prefecture_code: Optional[str] = None, living_area_id: Optional[str] = None, actor_id: Optional[str] = None, input_refs: Optional[List[str]] = None, output_refs: Optional[List[str]] = None, decision_refs: Optional[List[str]] = None, snapshot_id: Optional[str] = None, model_name: Optional[str] = None, prompt_version: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rows = load_audit_events()
    event = {
        "audit_event_id": f"evt_{uuid4().hex[:12]}",
        "event_type": event_type,
        "prefecture_code": prefecture_code,
        "living_area_id": living_area_id,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "input_refs": input_refs or [],
        "output_refs": output_refs or [],
        "decision_refs": decision_refs or [],
        "snapshot_id": snapshot_id,
        "model_name": model_name,
        "prompt_version": prompt_version,
        "status": status,
        "created_at": now_jst_iso(),
        "metadata": metadata or {},
    }
    rows.append(event)
    save_audit_events(rows)
    return event


def get_audit_chain_payload(entity_type: str, entity_id: str) -> Dict[str, Any]:
    rows = load_decision_chain_links()
    row = next((r for r in rows if r.get("entity_type") == entity_type and r.get("entity_id") == entity_id), None)
    if row is None:
        return {"entity_type": entity_type, "entity_id": entity_id, "chain": None, "related_events": [], "related_snapshots": []}
    refs = set([make_entity_ref(entity_type, entity_id)] + row.get("predecessor_refs", []) + row.get("successor_refs", []))
    events = load_audit_events()
    related_events = []
    snapshot_ids = set()
    for ev in events:
        ev_refs = set(ev.get("input_refs", []) + ev.get("output_refs", []) + ev.get("decision_refs", []))
        if refs & ev_refs:
            related_events.append(ev)
            if ev.get("snapshot_id"):
                snapshot_ids.add(ev["snapshot_id"])
    snapshots = load_audit_snapshots()
    related_snapshots = [s for s in snapshots if s.get("snapshot_id") in snapshot_ids]
    related_events.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    related_snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"entity_type": entity_type, "entity_id": entity_id, "chain": row, "related_events": related_events, "related_snapshots": related_snapshots}


def now_jst_iso() -> str:
    return datetime.now(timezone(timedelta(hours=9))).isoformat()




def build_source_dataset_labels(sources: List[Dict[str, Any]]) -> List[str]:
    labels: List[str] = []
    key_label_map = {
        "ssdse_e_csv": "SSDSE-E-2025",
        "ssdse_b_csv": "SSDSE-B-2025",
        "prefectures_geojson": "prefectures_geojson",
    }
    for src in sources or []:
        if not isinstance(src, dict):
            continue
        label = (
            src.get("name")
            or src.get("title")
            or key_label_map.get(str(src.get("key", "")).strip())
            or Path(str(src.get("path", ""))).name
            or str(src.get("key", "")).strip()
        )
        label = str(label).strip()
        if not label or label.lower() == "unknown":
            continue
        if label not in labels:
            labels.append(label)
    return labels[:5]
def build_scenario_lookup(region_id: str) -> Dict[str, Dict[str, Any]]:
    generated = generate_scenarios(ScenarioGenerateRequest(region_id=region_id))
    return {s["scenario_id"]: s for s in generated["scenarios"]}


def build_scenario_explainer_input(region_id: str, baseline_scenario_id: str, candidate_scenario_id: str) -> Dict[str, Any]:
    scenario_lookup = build_scenario_lookup(region_id)
    baseline = scenario_lookup.get(baseline_scenario_id)
    candidate = scenario_lookup.get(candidate_scenario_id)
    if baseline is None or candidate is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    comparison = compare_scenarios(ScenarioCompareRequest(
        region_id=region_id,
        baseline_scenario_id=baseline_scenario_id,
        candidate_scenario_ids=[candidate_scenario_id],
    ))
    comparison_result = next((x for x in comparison["comparisons"] if x["scenario_id"] == candidate_scenario_id), None)
    if comparison_result is None:
        raise HTTPException(status_code=404, detail="Comparison not found")
    structured = build_structured_explanation(region_id, candidate_scenario_id)
    return {
        "region_id": region_id,
        "region_name": structured["region_name"],
        "baseline": {
            "scenario_id": baseline["scenario_id"],
            "scenario_name": baseline["name"],
            "metrics": baseline["projected_metrics"],
        },
        "candidate": {
            "scenario_id": candidate["scenario_id"],
            "scenario_name": candidate["name"],
            "metrics": candidate["projected_metrics"],
        },
        "diffs": comparison_result["metric_diffs"],
        "recommended": comparison_result["recommended"],
        "risk_factors": structured.get("risk_factors", []),
        "confidence_notes": structured.get("confidence_notes", []),
        "source_datasets": structured.get("source_datasets", []),
        "constraints": {
            "must_not_invent_metrics": True,
            "must_use_only_given_inputs": True,
            "must_state_tradeoffs": True,
        },
    }


def build_deterministic_agent_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    metric_labels = {
        "population_retention": "population_retention",
        "healthcare_access": "healthcare_access",
        "vacancy_risk": "vacancy_risk",
        "fiscal_pressure": "fiscal_pressure",
        "total_risk_score": "total_risk_score",
    }
    lower_is_better = {"vacancy_risk", "fiscal_pressure", "total_risk_score"}
    positive_reasons = {
        "population_retention": "Population retention improves",
        "healthcare_access": "Access to key services improves",
        "vacancy_risk": "Vacant housing risk declines",
        "fiscal_pressure": "Fiscal pressure declines",
        "total_risk_score": "Total risk declines",
    }
    negative_reasons = {
        "population_retention": "Population retention worsens",
        "healthcare_access": "Access to key services worsens",
        "vacancy_risk": "Vacant housing risk rises",
        "fiscal_pressure": "Short- to mid-term fiscal pressure increases",
        "total_risk_score": "Total risk rises",
    }
    improved_metrics = []
    worsened_metrics = []
    for key, delta in payload.get("diffs", {}).items():
        if abs(delta) <= 1e-9:
            continue
        improved = delta < 0 if key in lower_is_better else delta > 0
        target = improved_metrics if improved else worsened_metrics
        target.append({
            "name": metric_labels.get(key, key),
            "delta": float(delta),
            "reason": positive_reasons.get(key, "Related metric improves") if improved else negative_reasons.get(key, "Related metric worsens"),
        })
    candidate_name = payload["candidate"]["scenario_name"]
    recommendation_status = "recommended" if payload.get("recommended") else "not_recommended"
    summary = f"{candidate_name} is {'recommended' if payload.get('recommended') else 'not recommended'} based on the comparison indicators."
    if improved_metrics and worsened_metrics:
        key_tradeoff = f"{improved_metrics[0]['name']}  improves, but attention is required for {worsened_metrics[0]['name']} as a trade-off."
    elif improved_metrics:
        key_tradeoff = f"{improved_metrics[0]['name']} is the main advantage."
    elif worsened_metrics:
        key_tradeoff = f"{worsened_metrics[0]['name']} is the main concern."
    else:
        key_tradeoff = "Differences in the main indicators are limited."
    return {
        "summary": summary,
        "recommendation_status": recommendation_status,
        "improved_metrics": improved_metrics,
        "worsened_metrics": worsened_metrics,
        "key_tradeoff": key_tradeoff,
        "risk_notes": payload.get("risk_factors", []),
        "confidence_note": (payload.get("confidence_notes") or ["The explanation is generated from the provided comparison indicators."])[0],
        "source_datasets": payload.get("source_datasets", []),
    }


def normalize_agent_metric_items(items: Any, fallback_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        items = []
    normalized = []
    fallback_by_name = {str(item.get("name", "")).strip(): item for item in fallback_items}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or raw.get("metric") or raw.get("label") or "").strip()
        reason = str(raw.get("reason") or raw.get("explanation") or raw.get("description") or "").strip()
        delta_value = raw.get("delta", raw.get("impact", raw.get("value", None)))
        try:
            delta = float(delta_value)
        except (TypeError, ValueError):
            delta = None
        fallback = fallback_by_name.get(name)
        if not name and fallback:
            name = str(fallback.get("name", "")).strip()
        if (delta is None or abs(delta) <= 1e-12) and fallback:
            try:
                delta = float(fallback.get("delta", 0.0))
            except (TypeError, ValueError):
                delta = 0.0
        if not reason and fallback:
            reason = str(fallback.get("reason", "")).strip()
        if not name:
            continue
        if delta is None:
            delta = 0.0
        if not reason:
            reason = "No explanation provided"
        normalized.append({
            "name": name,
            "delta": float(delta),
            "reason": reason,
        })
    normalized_names = {item["name"] for item in normalized}
    for fallback in fallback_items:
        if fallback["name"] not in normalized_names:
            normalized.append({
                "name": fallback["name"],
                "delta": float(fallback.get("delta", 0.0)),
                "reason": str(fallback.get("reason", "No explanation provided")),
            })
    normalized.sort(key=lambda item: abs(float(item.get("delta", 0.0))), reverse=True)
    return normalized[:3]


def normalize_agent_output(output: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    fallback = build_deterministic_agent_output(payload)
    normalized = dict(output or {})
    normalized["summary"] = str(normalized.get("summary") or fallback["summary"]).strip()
    normalized["recommendation_status"] = str(normalized.get("recommendation_status") or fallback["recommendation_status"]).strip()
    normalized["key_tradeoff"] = str(normalized.get("key_tradeoff") or fallback["key_tradeoff"]).strip()
    normalized["confidence_note"] = str(normalized.get("confidence_note") or fallback["confidence_note"]).strip()
    risk_notes = normalized.get("risk_notes")
    normalized["risk_notes"] = risk_notes if isinstance(risk_notes, list) and risk_notes else fallback["risk_notes"]
    source_datasets = normalized.get("source_datasets")
    if not isinstance(source_datasets, list) or not source_datasets:
        source_datasets = fallback["source_datasets"]
    source_datasets = [str(x).strip() for x in source_datasets if str(x).strip() and str(x).strip().lower() != "unknown"]
    if not source_datasets:
        source_datasets = build_source_dataset_labels(SOURCE_METADATA.get("sources", []))
    normalized["source_datasets"] = source_datasets[:3] if source_datasets else ["SSDSE-E-2025", "SSDSE-B-2025", "prefectures_geojson"]
    normalized["improved_metrics"] = normalize_agent_metric_items(
        normalized.get("improved_metrics"),
        fallback["improved_metrics"],
    )
    normalized["worsened_metrics"] = normalize_agent_metric_items(
        normalized.get("worsened_metrics"),
        fallback["worsened_metrics"],
    )
    return normalized


def call_scenario_explainer_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        raise RuntimeError("OpenAI is not configured")
    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a constrained explanation agent for regional policy scenario comparison. "
        "Use only the structured input provided to you. Do not invent new metrics, datasets, assumptions, or decisions. "
        "Return valid JSON with keys: summary, recommendation_status, improved_metrics, worsened_metrics, key_tradeoff, risk_notes, confidence_note, source_datasets."
    )
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.1,
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def run_scenario_explainer(payload: Dict[str, Any]) -> Dict[str, Any]:
    agent_runs = load_agent_runs()
    run_id = f"run_{uuid4().hex[:12]}"
    prompt_version = "scenario_explainer_v1"
    retrieved_sources = [
        payload["baseline"]["scenario_id"],
        payload["candidate"]["scenario_id"],
        "comparison_result",
        "structured_explanation_data",
    ]
    status = "success"
    error_message = None
    try:
        output = call_scenario_explainer_llm(payload)
        required = {"summary", "recommendation_status", "improved_metrics", "worsened_metrics", "key_tradeoff", "risk_notes", "confidence_note", "source_datasets"}
        if not required.issubset(set(output.keys())):
            raise ValueError("LLM output missing required keys")
        output = normalize_agent_output(output, payload)
    except Exception as exc:
        output = normalize_agent_output(build_deterministic_agent_output(payload), payload)
        status = "fallback"
        error_message = f"{type(exc).__name__}: {exc}"
    run = {
        "agent_run_id": run_id,
        "agent_name": "scenario_explainer",
        "user_action": "compare_and_explain",
        "input_payload": payload,
        "retrieved_sources": retrieved_sources,
        "output_payload": output,
        "model_name": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "prompt_version": prompt_version,
        "created_at": now_jst_iso(),
        "status": status,
        "error_message": error_message,
    }
    agent_runs.append(run)
    save_agent_runs(agent_runs)
    snapshot = create_audit_snapshot(
        "scenario_compare_snapshot",
        {"input_payload": payload, "output_payload": output},
        prefecture_code=payload.get("region_id"),
        metadata={"agent_run_id": run_id},
    )
    record_audit_event(
        "agent_explanation_generated",
        "agent",
        status,
        prefecture_code=payload.get("region_id"),
        actor_id="scenario_explainer",
        input_refs=[
            make_entity_ref("scenario", payload["baseline"]["scenario_id"]),
            make_entity_ref("scenario", payload["candidate"]["scenario_id"]),
        ],
        output_refs=[make_entity_ref("agent_run", run_id)],
        snapshot_id=snapshot["snapshot_id"],
        model_name=run["model_name"],
        prompt_version=prompt_version,
        metadata={"retrieved_sources": retrieved_sources},
    )
    upsert_decision_chain(
        "agent_run",
        run_id,
        predecessor_refs=[
            make_entity_ref("scenario", payload["baseline"]["scenario_id"]),
            make_entity_ref("scenario", payload["candidate"]["scenario_id"]),
        ],
        metadata={"prefecture_code": payload.get("region_id")},
    )
    return {"agent_run_id": run_id, "agent_name": "scenario_explainer", "status": status, "output": output, "error_message": error_message}


def build_structured_explanation(region_code: str, scenario: str) -> Dict[str, Any]:
    row = get_region_or_404(region_code, scenario)
    comparison = build_scenario_comparison(region_code)
    current = next((x for x in comparison["scenario_comparison"] if x["scenario"] == scenario), None)
    baseline = next((x for x in comparison["scenario_comparison"] if x["scenario"] == "baseline"), None)
    if current is None or baseline is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    metric_pairs = {
        "aging_rate": ("Aging Rate", row.get("aging_rate", 0.0), get_region_or_404(region_code, "baseline").get("aging_rate", 0.0)),
        "vacancy_rate": ("Vacancy Rate", row.get("vacancy_rate", 0.0), get_region_or_404(region_code, "baseline").get("vacancy_rate", 0.0)),
        "depopulation_index": ("Depopulation Index", row.get("depopulation_index", 0.0), get_region_or_404(region_code, "baseline").get("depopulation_index", 0.0)),
        "medical_access_risk": ("Healthcare Access Risk", row.get("medical_access_risk", 0.0), get_region_or_404(region_code, "baseline").get("medical_access_risk", 0.0)),
        "childcare_access_score": ("Family Support Access", row.get("childcare_access_score", 0.0), get_region_or_404(region_code, "baseline").get("childcare_access_score", 0.0)),
    }
    key_drivers = []
    improved = []
    worsened = []
    for d in explain_drivers(row)[:4]:
        label, cur, base = metric_pairs.get(d["key"], (d["factor"], d["value"], d["value"]))
        delta = round(cur - base, 4)
        beneficial = d["key"] == "childcare_access_score"
        improved_flag = delta > 0 if beneficial else delta < 0
        if abs(delta) > 1e-6:
            entry = {
                "metric": d["key"],
                "label": label,
                "direction": "positive" if improved_flag else "negative",
                "impact": d["weighted"],
                "delta_vs_baseline": delta,
                "reason": f"{label} changed by {delta:+.3f} versus baseline"
            }
            key_drivers.append(entry)
            (improved if improved_flag else worsened).append(label)
    if not key_drivers:
        key_drivers = [{"metric": "total_risk_score", "label": "Total Risk", "direction": "neutral", "impact": row["total_risk_score"], "delta_vs_baseline": current["risk_delta_vs_baseline"], "reason": "Difference from baseline is limited"}]

    return {
        "scenario_id": scenario,
        "region_id": region_code,
        "region_name": row["region_name"],
        "scenario_name": SCENARIO_LABELS.get(scenario, scenario),
        "recommended": comparison["recommended_scenario"] == scenario,
        "key_drivers": key_drivers,
        "improved_metrics": improved,
        "worsened_metrics": worsened,
        "supporting_metrics": {
            "total_risk_score": row["total_risk_score"],
            "baseline_risk": baseline["total_risk_score"],
            "p90": row["risk_distribution"]["p90"],
            "population_2035": row["population_2035"],
            "predicted_annual_decline_rate": row["predicted_annual_decline_rate"],
        },
        "risk_factors": [s["shock_label"] for s in row["shock_sensitivity"][:2]],
        "confidence_notes": [
            f"Uncertainty is {row['uncertainty']['overall_label']}; estimated width is {row['uncertainty']['overall_width']:.3f}。",
            f"Expected-value delta is {current['risk_delta_vs_baseline']:+.3f}; p90 delta is {current['p90_delta_vs_baseline']:+.3f}。",
        ],
        "source_datasets": build_source_dataset_labels(SOURCE_METADATA.get("sources", [])),
        "last_updated": MODEL_INFO.get("generated_at", ""),
    }


@app.post("/api/scenarios/generate")
def generate_scenarios(req: ScenarioGenerateRequest) -> Dict[str, Any]:
    scenarios = []
    for key in SCENARIO_LABELS.keys():
        row = get_region_or_404(req.region_id, key)
        scenarios.append({
            "scenario_id": key,
            "name": SCENARIO_LABELS[key],
            "assumptions": {
                "policy_focus": req.policy_focus,
                "budget_level": req.budget_level,
                "constraint_count": len(req.constraints or {}),
            },
            "projected_metrics": {
                "total_risk_score": row["total_risk_score"],
                "population_retention": round(1 - row["predicted_annual_decline_rate"], 4),
                "healthcare_access": round(1 - row["medical_access_risk"], 4),
                "vacancy_risk": row["vacancy_rate"],
                "fiscal_pressure": round(row["uncertainty"]["overall_score"] + row["service_capacity_pressure"], 4),
            },
            "overall_score": round(1 - row["total_risk_score"], 4),
            "priority_rank": row["priority_rank"],
        })
    scenarios.sort(key=lambda x: x["projected_metrics"]["total_risk_score"])
    return {"region_id": req.region_id, "scenarios": scenarios}


@app.post("/api/scenarios/compare")
def compare_scenarios(req: ScenarioCompareRequest) -> Dict[str, Any]:
    generated = generate_scenarios(ScenarioGenerateRequest(region_id=req.region_id))
    by_id = {s["scenario_id"]: s for s in generated["scenarios"]}
    baseline = by_id.get(req.baseline_scenario_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline scenario not found")
    comparisons = []
    for sid in req.candidate_scenario_ids:
        scenario = by_id.get(sid)
        if scenario is None:
            continue
        metric_diffs = {}
        improved_metrics = []
        worsened_metrics = []
        for key, value in scenario["projected_metrics"].items():
            base_value = baseline["projected_metrics"].get(key, 0.0)
            delta = round(value - base_value, 4)
            metric_diffs[key] = delta
            lower_is_better = key in {"total_risk_score", "vacancy_risk", "fiscal_pressure"}
            improved_flag = delta < 0 if lower_is_better else delta > 0
            if abs(delta) > 1e-6:
                (improved_metrics if improved_flag else worsened_metrics).append(key)
        row = get_region_or_404(req.region_id, sid)
        comparisons.append({
            "scenario_id": sid,
            "scenario_name": scenario["name"],
            "rank": scenario["priority_rank"],
            "metric_diffs": metric_diffs,
            "improved_metrics": improved_metrics,
            "worsened_metrics": worsened_metrics,
            "uncertainty": {
                "overall_score_ci_low": round(max(0.0, scenario["overall_score"] - row["uncertainty"]["overall_width"]), 4),
                "overall_score_ci_high": round(min(1.5, scenario["overall_score"] + row["uncertainty"]["overall_width"]), 4),
                "overall_label": row["uncertainty"]["overall_label"],
            },
            "recommended": sid == generated["scenarios"][0]["scenario_id"],
        })
    comparisons.sort(key=lambda x: (not x["recommended"], x["rank"]))
    return {"region_id": req.region_id, "baseline_scenario_id": req.baseline_scenario_id, "comparisons": comparisons}


@app.get("/api/explanations/{scenario_id}")
def get_explanation(scenario_id: str, region_id: str) -> Dict[str, Any]:
    return build_structured_explanation(region_id, scenario_id)


@app.post("/api/agents/explain-scenario")
def explain_scenario_agent(req: ExplainScenarioAgentRequest) -> Dict[str, Any]:
    payload = build_scenario_explainer_input(req.region_id, req.baseline_scenario_id, req.candidate_scenario_id)
    return run_scenario_explainer(payload)


@app.get("/api/agents/runs")
def list_agent_runs_api(region_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    rows = load_agent_runs()
    if region_id:
        rows = [r for r in rows if r.get("input_payload", {}).get("region_id") == region_id]
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"items": rows[:limit]}


@app.post("/api/decisions")
def create_decision(req: DecisionCreateRequest) -> Dict[str, Any]:
    row = get_region_or_404(req.region_id, req.selected_scenario_id)
    decisions = load_decisions()
    decision_id = f"dec_{len(decisions)+1:03d}"
    decision = {
        "decision_id": decision_id,
        "region_id": req.region_id,
        "region_name": row["region_name"],
        "selected_scenario_id": req.selected_scenario_id,
        "selected_scenario_name": SCENARIO_LABELS.get(req.selected_scenario_id, req.selected_scenario_id),
        "status": req.status,
        "reviewer_comment": req.reviewer_comment,
        "rationale_tags": req.rationale_tags,
        "created_at": now_jst_iso(),
    }
    decisions.append(decision)
    save_decisions(decisions)
    latest_agent_run = next((r for r in reversed(load_agent_runs()) if r.get("input_payload", {}).get("region_id") == req.region_id and r.get("input_payload", {}).get("candidate", {}).get("scenario_id") == req.selected_scenario_id), None)
    explanation = build_structured_explanation(req.region_id, req.selected_scenario_id)
    snapshot = create_audit_snapshot(
        "healthcare_summary_snapshot",
        {
            "decision": decision,
            "structured_explanation": explanation,
            "healthcare_summary": get_healthcare_timeline_slice(req.region_id, 2025).get("summary", {}),
        },
        prefecture_code=req.region_id,
        year=2025,
        metadata={"selected_scenario_id": req.selected_scenario_id},
    )
    predecessor_refs = [make_entity_ref("scenario", req.selected_scenario_id)]
    if latest_agent_run:
        predecessor_refs.append(make_entity_ref("agent_run", latest_agent_run["agent_run_id"]))
    record_audit_event(
        "decision_recorded",
        "human",
        req.status,
        prefecture_code=req.region_id,
        input_refs=predecessor_refs,
        output_refs=[make_entity_ref("decision", decision_id)],
        decision_refs=[make_entity_ref("decision", decision_id)],
        snapshot_id=snapshot["snapshot_id"],
        metadata={"reviewer_comment": req.reviewer_comment, "rationale_tags": req.rationale_tags},
    )
    upsert_decision_chain(
        "decision",
        decision_id,
        predecessor_refs=predecessor_refs,
        metadata={"prefecture_code": req.region_id},
    )
    return {
        "decision_id": decision_id,
        "timestamp": decision["created_at"],
        "summary": f"{row['region_name']} {SCENARIO_LABELS.get(req.selected_scenario_id, req.selected_scenario_id)} {req.status} recorded with status ",
        "decision": decision,
    }


@app.get("/api/decisions")
def list_decisions(region_id: Optional[str] = None) -> Dict[str, Any]:
    rows = load_decisions()
    if region_id:
        rows = [r for r in rows if r["region_id"] == region_id]
    rows.sort(key=lambda x: x["created_at"], reverse=True)
    return {"items": rows}


@app.get("/api/audit/events")
def list_audit_events(prefecture: Optional[str] = None, decision_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    rows = load_audit_events()
    if prefecture:
        rows = [r for r in rows if r.get("prefecture_code") == prefecture]
    if decision_id:
        ref = make_entity_ref("decision", decision_id)
        rows = [r for r in rows if ref in (r.get("decision_refs") or []) or ref in (r.get("input_refs") or []) or ref in (r.get("output_refs") or [])]
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"items": rows[:limit]}


@app.get("/api/audit/chain")
def get_audit_chain(entity_type: str, entity_id: str) -> Dict[str, Any]:
    return get_audit_chain_payload(entity_type, entity_id)


@app.get("/api/audit/snapshot")
def get_audit_snapshot(snapshot_id: str) -> Dict[str, Any]:
    snapshots = load_audit_snapshots()
    snap = next((s for s in snapshots if s.get("snapshot_id") == snapshot_id), None)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


@app.post("/api/reports/generate")
def generate_report(req: ReportGenerateRequest) -> Dict[str, Any]:
    decisions = load_decisions()
    decision = next((d for d in decisions if d["decision_id"] == req.decision_id), None)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    comparison = build_scenario_comparison(decision["region_id"])
    selected = next((x for x in comparison["scenario_comparison"] if x["scenario"] == decision["selected_scenario_id"]), None)
    baseline = next((x for x in comparison["scenario_comparison"] if x["scenario"] == "baseline"), None)
    explanation = build_structured_explanation(decision["region_id"], decision["selected_scenario_id"])
    evidence = [k["reason"] for k in explanation["key_drivers"][:3]] + explanation["confidence_notes"][:2]
    comparison_table = [
        {"metric": "total_risk_score", "baseline": baseline["total_risk_score"], "selected": selected["total_risk_score"], "delta": selected["risk_delta_vs_baseline"]},
        {"metric": "p90", "baseline": baseline["risk_distribution"]["p90"], "selected": selected["risk_distribution"]["p90"], "delta": selected["p90_delta_vs_baseline"]},
        {"metric": "priority_rank", "baseline": baseline["priority_rank"], "selected": selected["priority_rank"], "delta": baseline["priority_rank"] - selected["priority_rank"]},
    ]
    report_id = f"rep_{req.decision_id}"
    snapshot = create_audit_snapshot(
        "scenario_compare_snapshot",
        {"comparison_table": comparison_table, "evidence": evidence, "decision": decision},
        prefecture_code=decision.get("region_id"),
        metadata={"report_id": report_id, "audience": req.audience, "format": req.format},
    )
    record_audit_event(
        "report_generated",
        "system",
        "success",
        prefecture_code=decision.get("region_id"),
        input_refs=[make_entity_ref("decision", req.decision_id)],
        output_refs=[make_entity_ref("report", report_id)],
        decision_refs=[make_entity_ref("decision", req.decision_id)],
        snapshot_id=snapshot["snapshot_id"],
        metadata={"audience": req.audience, "format": req.format},
    )
    upsert_decision_chain(
        "report",
        report_id,
        predecessor_refs=[make_entity_ref("decision", req.decision_id)],
        metadata={"prefecture_code": decision.get("region_id")},
    )
    return {
        "report_id": report_id,
        "title": f"{decision['region_name']} Policy Comparison Memo",
        "summary": f"{decision['region_name']} for {decision['selected_scenario_name']} organized around {selected['risk_delta_vs_baseline']:+.3f}; p90 delta is {selected['p90_delta_vs_baseline']:+.3f}。",
        "comparison_table": comparison_table,
        "evidence": evidence,
        "memo": "\n".join([
            f"Target Region: {decision['region_name']}",
            f"Selected Scenario: {decision['selected_scenario_name']}",
            f"Decision Status: {decision['status']}",
            f"Main Drivers: {', '.join(explanation['improved_metrics'][:3] or explanation['worsened_metrics'][:3])}",
            f"Comment: {decision['reviewer_comment'] or 'None'}",
        ]),
        "audit_metadata": {
            "decision_id": req.decision_id,
            "generated_at": now_jst_iso(),
            "audience": req.audience,
            "format": req.format,
        },
    }
