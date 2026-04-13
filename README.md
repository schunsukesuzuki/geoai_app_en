# Regional Risk Simulator

## Overview

This repository contains a React + FastAPI + Docker Compose prototype for regional-risk analysis and policy workflow support.

The goal is not to provide a simple prefecture-level risk dashboard. The product is designed as an end-to-end decision workflow that connects:

- forecasting
- scenario comparison
- explanation
- approval
- report export
- constrained-agent execution
- spatial / GeoAI-style layers

In other words, the prototype is built as a decision interface for municipal, infrastructure, and regional-policy use cases.

## Why this app exists

In regional and infrastructure policy, the hard problem is not only analysis. The real problem is deciding, under limited budget, labor, and time, what should be maintained, what should receive reinvestment, and what should be treated as a shrinkage candidate, in a form that can be explained and audited.

This prototype answers that problem through a workflow-oriented structure:

`forecast -> compare scenarios -> explain rationale -> approve -> export -> refresh over time`

## Differentiation

### 1. Decision workflow instead of a single model
The application carries scenario generation, comparison, recommendation, approval, and export through both the UI and API layers.

### 2. Constrained agent instead of a free-form copilot
The LLM is used as a bounded explanation unit with explicit fallback behavior and auditable outputs.

### 3. Minimal GeoAI / Digital Twin structure
Instead of jumping directly to a flashy 3D viewer, the system layers:

- 2D entities
- healthcare living-area slices
- accessibility summaries
- spatial-asset registry and bindings
- optional 3D / reality-asset views

## Main capabilities

### Baseline regional risk scoring
The app can rebuild prefecture-level risk metrics from public data and estimate the annual population decline rate and projected 2035 population.

### Scenario workflow
Scenario candidates are compared not only by a single score, but by trade-offs such as population retention, healthcare access, vacancy risk, fiscal pressure, and total risk.

### Policy memo generation
`scenario_explainer` is implemented as a bounded explanation unit rather than a free-form chat surface.

### Healthcare slices and accessibility
Healthcare areas are represented as spatial slices that preserve prefecture shells while decomposing healthcare accessibility into more actionable geographic units.

### Timeline state management
Healthcare slices are also treated as year-indexed state so the app can represent maintain / reinvest / shrink-candidate transitions over time.

### Spatial asset registry
2D entities and 3D / reality assets are separated and bound through a registry so they can evolve independently.

## Repository structure

```text
backend/
  app/
    data/
    main.py
  scripts/
frontend/
docs/
README.md
```

## Run locally

```bash
docker compose up --build
```

Frontend: `http://localhost:5173`
Backend API: `http://localhost:8000`

## Environment variables

Create `.env` from `.env.example` and set the values you need.

- `OPENAI_API_KEY`
- `OPENAI_MODEL`

If the key is missing, the app still runs with fallback behavior for memo generation.

## Data notes

This publishable package removes unnecessary runtime artifacts and excludes sensitive or environment-specific files. Some rebuild scripts expect public datasets to be fetched again when needed.

## Documentation

See `docs/implementation_guide_regional_risk_simulator_api_enhanced.md` for an implementation-oriented guide to the main classes, functions, APIs, data files, and workflow connections.
