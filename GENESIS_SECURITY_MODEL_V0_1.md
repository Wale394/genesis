# Genesis Security Model v0.1

## Purpose

Genesis must distinguish **what an observation says** from **how much the system can currently trust the observation source**.

This version establishes a conservative trust/provenance boundary without pretending that the research prototype has production authentication or cryptographic integrity.

## Security properties

Genesis v0.1 tracks these properties separately:

- **Source identity** — which source claims to have produced the observation.
- **Authentication** — whether the source identity has been verified.
- **Authorization** — whether the source is permitted to submit data.
- **Integrity** — whether the observation has been protected from tampering.
- **Freshness** — whether the observation is newer than the previous observation for the same robot.
- **Provenance** — how the observation entered Genesis.

Unknown security properties remain `UNKNOWN`; Genesis never upgrades them to trusted merely because a field exists.

## Trust states

- `TRUSTED`: all relevant security properties are explicitly trusted and freshness is valid.
- `DEGRADED`: the observation may still be used for analysis, but one or more security properties are unknown or limited.
- `UNTRUSTED`: a security property has explicitly failed or freshness has failed.

The current trust assessment is **descriptive only**. It does not silently change model features, reliability thresholds, state transitions, or recommendations.

## Current architecture

```text
Source
  |
  v
Ingestion / Normalization
  |
  +--> Observation Quality
  |
  +--> Observation Security
  |       |
  |       +-- identity
  |       +-- authentication
  |       +-- authorization
  |       +-- integrity
  |       +-- freshness
  |       +-- provenance
  |
  v
Analysis
  |
  v
Evidence Synthesis
  |
  v
Decision / Incident
```

## Threats covered by the first implementation

1. Missing or ambiguous source provenance.
2. Unauthenticated source claims.
3. Explicitly failed authentication/integrity/authorization.
4. Non-monotonic source time steps / basic replay ordering.
5. Confusing observation quality with source trust.

## Not implemented yet

- cryptographic signatures
- device certificates
- mutual TLS
- production identity provider
- role-based access control
- encrypted durable storage
- secure transport configuration
- persistent security audit log
- distributed replay protection
- key rotation

These are planned production boundaries, not capabilities claimed by the current prototype.

## Design rule

> **Never turn an unknown security property into a trusted claim.**

Security metadata must remain separate from behavioral evidence. Evidence synthesis may report trust limitations, but trust status does not by itself prove a failure or clear a failure.
