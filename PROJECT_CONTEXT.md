# Genesis / KORDEX Project Context

This file describes the Genesis project charter exposed through the local Command Center at `/api/project-context`. The machine-readable source of truth is `project_context.json`.

- **Genesis** is the overall project and repository.
- **KORDEX** is the reliability-intelligence system implemented within Genesis.
- The current focus is robotics and heterogeneous autonomous fleets.
- The project is at prototype and engineering-validation stage, not production-ready.
- Current architecture and future roadmap are deliberately distinguished.
- Project-level goals guide human development and product navigation. They are not robot telemetry, evidence, diagnosis, or runtime decision inputs.

The Python package retains the `genesis_system` namespace for compatibility; that internal package name does not change the product/system identity. When updating the project direction, update `project_context.json` and this document together. Keep future capabilities marked as planned until implementation and validation support a status change.
