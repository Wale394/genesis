# Genesis Command Center V0.4 — Multi-workspace interface

## What's new

The single long dashboard is now organized into dedicated workspaces:

- **Overview** — current state, observation quality, session count, assessment, recommendation, recent events.
- **Fleet & Assets** — the currently configured R004 controlled test asset and explicit scope limitations.
- **Telemetry** — latest measurements and selectable observation history.
- **Evidence Explorer** — engine-returned observations, engineering/pattern evidence, contradictions, missing evidence, limitations, and raw JSON.
- **Investigations** — investigation status and the controlled follow-up observation input.
- **Reliability Memory** — clearly marks that a memory browse endpoint is not yet connected.
- **Incidents** — clearly marks that a dedicated incident-list endpoint is not yet connected.
- **Audit Trail** — events and observation trace for the current interface session.

## Run

From the `GenesisLabcl` project root:

```bash
python -m genesis_interface.server
```

Open <http://127.0.0.1:8765>.

## Architecture and honesty boundaries

The UI continues to call the local interface API, which calls the real Genesis runtime. Switching workspaces does not reset the session. Synthetic scenario telemetry is used for the controlled demonstration; it is not a live robot or industrial connection.

Memory and incident workspaces do not fabricate records. They explain that dedicated read APIs must be connected before those sections can display records.

## Verification

- Interface tests: 8 passed.
- Full regression: 573 passed, 11 subtests passed.
