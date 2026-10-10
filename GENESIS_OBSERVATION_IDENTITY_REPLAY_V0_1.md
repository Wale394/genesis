# GENESIS Observation Identity & Replay Guard v0.1

## Purpose
Stress-test whether Genesis can distinguish a legitimate repeated observation from a replayed source observation.

## Weakness found
A source record without a source timestamp could be ingested twice and assigned two ingestion-order time steps. Payload equality alone cannot safely identify a replay because two legitimate consecutive observations may have identical values.

## Contract
- `source_metadata.observation_id`: optional stable source observation identity.
- `source_metadata.sequence_number`: optional monotonic source sequence.
- Duplicate observation IDs are rejected.
- Sequence numbers must strictly increase per asset stream.
- Failed replay attempts are transactionally rolled back.
- If neither identity nor sequence is provided, Genesis does not invent identity; freshness remains an explicit unknown in the security assessment.
- Payload equality alone is never used as a deduplication rule.

## Engineering lesson
Ingestion order is not proof of source freshness. Observation identity and temporal ordering are separate properties.

## Validation
Focused: 3 passed.
Full regression: 510 passed, 11 subtests passed.
