# GENESIS Temporal Semantics Guard v0.1

## Purpose
Prevent Genesis from combining source timestamps with ingestion-order fallback values as if they were the same clock.

## Problem Found
The runtime used `time_step` for both source-supplied timestamps and synthetic ingestion-order fallback. In mixed streams this could cause false ordering failures or, worse, misleading temporal comparisons.

Examples discovered:

- missing timestamp → later source timestamp could be rejected against a synthetic step
- source timestamp → missing timestamp → later source timestamp could collide with the synthetic step

## Fix
Genesis now tracks timestamp basis per robot stream:

- `SOURCE` — observations provide source timestamps
- `INGESTION_ORDER` — observations rely on fallback ordering

A stream cannot silently switch between the two modes. Mixed timestamp basis is rejected with an explicit error.

Sampling analysis continues to use only source timestamps. It does not treat fallback ordering as elapsed time.

## Engineering Principle

> Never combine values from different time bases as if they were measurements on the same clock.

A future dual-time contract may support both source time and ingestion sequence explicitly. This release intentionally does not invent that broader abstraction.

## Validation

Focused telemetry sampling tests: 18 passed.

Full Genesis regression: 442 tests passed.
