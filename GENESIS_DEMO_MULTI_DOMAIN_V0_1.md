# Genesis Multi-Domain Fleet Demo v0.1

## Purpose

Demonstrate that Genesis can accept heterogeneous physical assets through domain-specific adapters while keeping a shared reliability reasoning layer.

## Demonstrated domains

- Robotics: AMR, robotic arm, mobile robot
- Energy infrastructure: transformer, generator
- Industrial equipment: compressor, CNC machine

The demo intentionally uses controlled deterministic telemetry. It demonstrates the architecture and reasoning boundary, not production field connectivity or real-world failure prediction.

## Architecture

```text
Domain-specific telemetry
        |
        v
+---------------------------+
| Domain Adapter Registry   |
+-------------+-------------+
              |
              v
      NormalizedObservation
              |
              v
       Fleet Registry
              |
              v
       Genesis Evidence
              |
              v
       Evidence Review
              |
              v
      Reliability State
              |
              v
        Investigation
```

## Why this matters

Genesis is not required to understand every vendor protocol or asset type inside its core. An adapter translates domain-specific telemetry into a common observation envelope:

- asset identity
- domain
- asset type
- manufacturer/model
- site
- timestamp
- signals
- source/provenance
- quality

A future integration can therefore add a new industry at the adapter boundary rather than rewriting the reasoning engine.

## Demo fleet

The deterministic scenario contains nine assets across three domains and four sites. The registry also exposes same-type peer groups where applicable.

## Run

```bash
python demo_multi_industry.py
```

Focused tests:

```bash
pytest -q test_multi_industry_demo.py
```

Full regression:

```bash
pytest -q
```

## Safe demo claim

> Genesis demonstrates a domain-flexible reliability reasoning architecture in which heterogeneous physical-system telemetry can enter through adapters and be evaluated through shared evidence and reliability contracts.

## Claims we should not make

- That the adapters are production connectors.
- That the controlled scenarios prove real-world failure prediction.
- That the current system can connect to arbitrary robots or industrial systems without integration work.
- That a demo reliability state is equivalent to a validated field diagnosis.
