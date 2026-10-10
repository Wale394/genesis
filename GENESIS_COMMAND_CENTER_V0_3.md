# Genesis Command Center V0.3 — Evidence Explorer

## Purpose

V0.3 makes the actual Genesis result inspectable. It does not add new reliability logic or calculate conclusions in the browser.

## Changes

- The controller retains up to 100 recent engine results in the session snapshot.
- The observation history is selectable. Selecting a step renders that exact result's state and telemetry.
- Evidence Explorer reads `evidence_synthesis` returned by Genesis and displays observation evidence, engineering/pattern/temporal/quality/security evidence, contradictions, missing evidence, and limitations.
- A raw JSON inspector exposes the complete selected engine result for debugging and engineering review.
- Reset clears both the current state and the retained session history.
- The frontend escapes displayed strings before rendering them as HTML.

## Run

From the project root:

```bash
python -m genesis_interface.server
```

Open `http://127.0.0.1:8765`.

Run the controlled scenario, then select any observation-history step to inspect the exact result at that point.

## Verification

- Interface tests: 6 passed.
- Full suite: 571 passed, 11 subtests passed.
- Browser JavaScript syntax check: passed.

## Boundaries / limitations

- The bundled R004 scenario uses synthetic telemetry, but each observation is processed by the real `Genesis.investigate()` facade and decision pipeline.
- This version is a local single-session interface, not a production multi-user server.
- History is in-memory and is cleared on reset or server restart.
- Evidence categories are shown as Genesis returned them; the UI does not independently certify their correctness or independence.
- External robot/energy connectors and live physical telemetry are not included in this milestone.
