# GENESIS Semantic Boundary Stress Test v0.1

## Purpose
Stress-test the boundary between domain-specific telemetry and Genesis canonical signals.

## Weakness under test
A normalized numeric value can look valid even when its physical meaning, source field, unit, or transformation is missing or wrong.

Example failure:
- source field `motor_load`
- numeric value `72`
- adapter labels it `motor_temperature`
- downstream reasoning sees a plausible temperature value without knowing the semantic mismatch.

## Guard contract
A signal is `VERIFIED` only when its semantic provenance establishes:
- canonical field mapping
- source field
- physical quantity compatible with the canonical signal
- unit where required
- normalization transform

Missing or conflicting semantics must not be treated as verified physical evidence.

## Current result
3 focused tests pass.

## Deliberate scope
This is an architectural experiment, not yet a core integration. Before integration it should be tested across:
- robotics adapters
- energy infrastructure adapters
- industrial equipment adapters
- unit conversion
- renamed vendor fields
- multiple source fields mapping to one canonical field
- schema/version changes
- ambiguous or unknown units

## Engineering lesson
A normalized number is not sufficient evidence of physical meaning. Genesis must preserve semantic provenance across the adapter boundary.
