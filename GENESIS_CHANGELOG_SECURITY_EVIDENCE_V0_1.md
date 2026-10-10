# Genesis Security + Evidence Contract v0.1

This checkpoint includes the verified Security v0.1 work plus the first Evidence Contract integration.

## Included
- Observation security model and runtime security checks.
- Shared `Evidence` / `EvidenceCategory` contract.
- Root compatibility shim: `evidence_contract.py`.
- `EvidenceSynthesis` accepts optional `evidence_items` without breaking existing callers.
- Contract evidence is exposed under `contract_evidence` and included in synthesis.
- Two regression/integration tests for the contract.

## Verification
- `python -m pytest -q`
- Result: **407 passed, 11 subtests passed**.

## Important compatibility rule
The existing EvidenceSynthesis representation remains intact. The new contract is an additive input path, so existing Genesis evidence producers and callers continue to work.
