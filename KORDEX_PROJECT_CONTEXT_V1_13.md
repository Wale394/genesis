# KORDEX Project Context v1.13

## Delivered
- Added `project_context.json` as a versioned, machine-readable source for mission, current focus, engineering principles, current architecture, future roadmap, long-term vision, and explicit limitations.
- Added `GET /api/project-context` for read-only access by the Command Center and future project-aware tools.
- Added the **Goals & Architecture** workspace, which loads the charter from the API and clearly distinguishes current focus from planned/future capabilities.
- Updated the architecture and README documentation to explain the project-context boundary.
- Added focused API/contract checks in `test_project_context.py`.

## Trust boundary
Project context is strategic reference knowledge. It is not injected into per-robot reliability inference, is not telemetry/evidence, and cannot establish an asset's condition. Roadmap entries remain planned until implementation and validation justify a status change.

## Focused verification
- `python -m py_compile genesis_interface/server.py test_project_context.py` — passed.
- `node --check genesis_interface/ui/app.js` — passed.
- `python -m pytest -q test_project_context.py` — 2 passed.

The full test suite was not rerun; this update was checked with focused tests only.
