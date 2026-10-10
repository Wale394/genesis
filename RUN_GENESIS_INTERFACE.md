# Genesis Command Center v0.1

This is the first real interface layer for Genesis. It is intentionally thin:
all reliability evaluation remains in the existing `Genesis` engine.

## Run locally

From the Genesis repository root:

```bash
PYTHONPATH=. python -m genesis_interface.server
```

Open:

`http://127.0.0.1:8765`

## What is real

- The Command Center calls the real `Genesis.investigate()` API.
- Scenario observations are passed through the actual normalizer, pipeline,
  evidence synthesis, reliability state, and recommendation path.
- Reset creates a fresh real Genesis engine.
- The UI does not calculate reliability state itself.

## What is simulated

The built-in Command Center scenario is synthetic telemetry. It is an
engineering experiment for observing Genesis behavior, not a claim about a
real robot failure.

## Architecture

```text
Browser UI
    |
    v
Genesis interface server
    |
    v
GenesisController
    |
    v
Genesis.investigate()
    |
    v
Existing Genesis reasoning pipeline
```
