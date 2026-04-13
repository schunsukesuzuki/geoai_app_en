# Regional Risk Simulator Implementation Guide

- [1. Purpose of this document](#1-purpose-of-this-document)
- [2. Why a separate implementation guide is useful](#2-why-a-separate-implementation-guide-is-useful)
- [3. System overview](#3-system-overview)
- [4. Directory layout and responsibilities](#4-directory-layout-and-responsibilities)
- [5. Backend guide](#5-backend-guide)
  - [5.1 Entry point](#51-entry-point)
  - [5.2 Main request models](#52-main-request-models)
  - [5.3 Main functions](#53-main-functions)
  - [5.4 Main APIs](#54-main-apis)
- [6. Frontend guide](#6-frontend-guide)
- [7. Data files](#7-data-files)
- [8. Workflow connections](#8-workflow-connections)
- [9. First places to inspect when changing behavior](#9-first-places-to-inspect-when-changing-behavior)

## 1. Purpose of this document

This guide helps a reader understand, in one place:

- where the main code lives
- what the primary classes, functions, and APIs do
- how the data files are connected
- how a user action on the screen flows into backend processing

This is not an auto-generated API reference. It is an implementation-oriented technical guide.

## 2. Why a separate implementation guide is useful

The product is not a simple visualization app. It connects:

- risk scoring
- scenario generation and comparison
- explanation generation
- decision recording
- report generation
- healthcare slice and accessibility layers
- spatial asset registry and optional 3D views

Because of that, a plain endpoint list is not enough. What matters is the design center: an explainable decision workflow.

## 3. System overview

The system uses React + FastAPI + Docker Compose.

Frontend responsibilities:

- initial page load
- region selection
- scenario comparison
- recommendation display
- decision input
- report export
- spatial / 3D panels

Backend responsibilities:

- region metrics loading
- scenario recalculation
- comparison and explanation generation
- constrained agent execution
- decision / audit / report persistence
- healthcare, facility, and timeline data serving
- rebuild script execution

## 4. Directory layout and responsibilities

```text
frontend/
  src/
    App.jsx
    api.js
    components/
backend/
  app/
    main.py
    data/
  scripts/
docs/
```

Interpret the structure this way:

- `frontend/src/App.jsx`
  - orchestrates page-level state
  - acts as the main entry point for API calls
- `frontend/src/api.js`
  - frontend-facing API client
- `frontend/src/components/`
  - units of UI responsibility
- `backend/app/main.py`
  - API definitions, domain logic, and persistence helpers
- `backend/app/data/`
  - demo data, precomputed artifacts, and audit-oriented assets
- `backend/scripts/`
  - public-data fetching and artifact rebuilding scripts

## 5. Backend guide

## 5.1 Entry point

`backend/app/main.py` initializes FastAPI, defines request models, loads the data artifacts, executes scenario logic, and persists decisions, audit events, and reports.

## 5.2 Main request models

Examples include:

- `SummaryRequest`
- `ScenarioGenerateRequest`
- `ScenarioCompareRequest`
- `DecisionCreateRequest`
- `ReportGenerateRequest`
- `ExplainScenarioAgentRequest`
- `FeatureRefreshReviewRequest`

## 5.3 Main functions

Representative functional groups:

- data loading and reload helpers
- scenario metric calculation
- scenario comparison builders
- explanation builders
- decision persistence functions
- report generation helpers
- healthcare slice / accessibility readers
- spatial asset and binding readers

## 5.4 Main APIs

A useful way to read the API layer is by workflow stage rather than by route list.

### A. Initial load and system state

- health endpoint
  - returns API health, OpenAI configuration, and rebuild-script availability
- regions endpoint
  - returns the GeoJSON used for map rendering
- model info endpoint
  - returns model metadata and source metadata
- metrics endpoint
  - returns scenario-adjusted regional metrics

### B. Region detail and explanation

- reasoning endpoint
  - returns main drivers, uncertainty, shock sensitivity, and scenario comparison
- summary endpoint
  - generates a short policy memo
- explanation endpoint
  - returns a structured comparison explanation for the UI
- agent explanation endpoint
  - runs the constrained comparison explainer

### C. Workflow and persistence

- scenario generation / comparison endpoints
- decision create / list endpoints
- report generation endpoint
- audit event and chain endpoints

### D. Spatial and healthcare layers

- facilities endpoint
- living areas endpoint
- accessibility summary endpoint
- healthcare priorities endpoint
- healthcare timeline endpoint
- spatial assets endpoint
- asset binding endpoint
- feature refresh endpoints

## 6. Frontend guide

The frontend centers on `App.jsx`, which coordinates static loading, scenario changes, selected region changes, workflow detail loading, healthcare timeline loading, and spatial layer loading.

Representative components:

- `ScenarioSelect`
- `OverviewCards`
- `RegionHeatGrid`
- `RegionGeoMap`
- `RankingTable`
- `DetailPanel`
- `ScenarioComparisonPanel`
- `RecommendationReasonPanel`
- `DecisionBar`
- `ExportPanel`
- `Spatial3DViewer`

## 7. Data files

Key artifact groups under `backend/app/data/`:

- `regions.geojson`
- `region_metrics.json`
- `model_info.json`
- `facilities/`
- `living_areas/`
- `accessibility/`
- `healthcare_priorities/`
- `healthcare_timeline/`
- `feature_refresh/`
- `spatial_assets.json`
- audit-related JSON files

## 8. Workflow connections

A typical user flow is:

1. choose a prefecture and scenario
2. load current metrics and reasoning
3. generate / compare candidate scenarios
4. inspect explanation and agent output
5. record a decision
6. export a memo or comparison report
7. inspect healthcare slices, timeline state, and spatial assets as supporting context

## 9. First places to inspect when changing behavior

Start here when modifying the product:

- `backend/app/main.py`
- `frontend/src/App.jsx`
- the corresponding component under `frontend/src/components/`
- the artifact file under `backend/app/data/`
- the relevant builder script under `backend/scripts/`
