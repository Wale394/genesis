# Genesis / KORDEX merge notes

## Identity
- Repository and overall engineering project: **Genesis**
- Reliability-intelligence system: **KORDEX**
- The existing `genesis_system` Python namespace is retained for compatibility.

## Integration changes in this merge pass
- Added a read-only `GET /api/project-context` endpoint backed by the root `project_context.json`.
- Updated the machine-readable and human-readable project context so Genesis is the project and KORDEX is the system.
- Updated the root README to establish the Genesis project identity while retaining KORDEX product/system language.
- Added `ROS2TelemetryAdapter.adapt_packet()` to bridge the existing ROS-like payload adapter into the shared `TelemetryPacket` contract. The adapter remains payload-only and does not create a live ROS connection.
- Updated the local server banner and health response to identify the Genesis project and KORDEX system separately.

## Verification
Full test suite: **666 passed, 1 skipped, 11 subtests passed**.
This is software test verification only; it does not establish predictive-maintenance performance or validate live robot integration.

## GitHub rename follow-up
The included Git history still points to the existing remote `https://github.com/Wale394/kordex.git`. Rename the repository on GitHub first, then update the local remote:

```powershell
git remote set-url origin https://github.com/Wale394/genesis.git
git remote -v
git fetch origin
```

The repository rename and push have not been performed by this archive-generation step.
