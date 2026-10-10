# Genesis System-Wide Adversarial Audit v0.1

## Scope

This audit treats Genesis as a reliability reasoning system rather than a collection of isolated unit tests. It targets ingestion, temporal semantics, observation quality, measurement validity, provenance/security, context, evidence independence, memory, investigation, state transitions, incident lifecycle, recommendations, and cross-domain boundaries.

## Result

The latest uploaded Genesis archive started with **564 passed, 11 subtests**.

After the confirmed memory serialization fix:

- Targeted adversarial/regression slice: **79 passed**
- Full regression: **565 passed, 11 subtests**

## Confirmed bug fixed

### Investigation-memory round-trip failure

Investigation outcomes were stored with an `investigation` schema while `ReliabilityMemory.load_entry()` assumed every serialized entry contained `identity.incident_id`.

A valid investigation memory entry therefore failed to deserialize.

### Fix

Memory entries now carry an explicit `entry_type`:

- `incident`
- `investigation`

The loader validates each schema according to its type and retains backward compatibility with older incident entries that have no `entry_type` field.

## Architectural findings intentionally preserved

These are not silently treated as fixed because doing so without a complete contract would create false confidence:

1. Historical incident matching is still advisory and does not universally enforce the newer context-compatibility contract. The context-compatibility evaluator exists and is conservative, but all historical-memory consumers must eventually use it as a gate before historical evidence can support a current claim.
2. Historical retrieval exposes both a `CONFLICTING` parent status and the constituent validated/refuted findings. Consumers must respect the parent conflict state rather than treating `validated_findings` as unconditional support.
3. The system has several trust/quality judges (semantics, measurement validity, observation quality, temporal validity, security, provenance, independence, context) but they are not yet unified behind one universal evidence-eligibility gate.
4. Recovery semantics remain domain-specific. Sensor recovery must not be interpreted as proof of asset recovery; the current robotics lifecycle requires an explicit recovery transition before closure.
5. The semantic-boundary, measurement-validity, disagreement, independence, and context-shift experiments remain conservative architectural stress tests rather than claims of universal physical correctness.

## Engineering principle

A test failure is only an architectural change when the architecture itself cannot express the required invariant. Otherwise, fix the implementation defect and preserve the existing contract.

## Source of truth

The regression results in this document were run against the packaged checkout used to create this release. User-local regression results remain authoritative for their local environment.
