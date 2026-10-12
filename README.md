# GENESIS — Engineering Reliability Platform

**One engineering project. One reliability-intelligence system.**

Genesis is the project and repository. **KORDEX** is the reliability-intelligence system within it, built to help engineers investigate unusual behavior in robots and other physical systems.

KORDEX is an early-stage system exploring how telemetry, historical observations, evidence quality, and operating context can help engineers investigate unusual behavior in robotic and other physical systems. The repository also contains the broader Genesis engineering foundation, research, offline workflows, and project-level interface. Internal Python modules retain the `genesis_system` namespace for compatibility.

> **Project status:** research prototype. This repository is shared for technical review and discussion. It is not a validated safety-critical or predictive-maintenance product.

## Why it exists

Robot operators often need to distinguish an unusual measurement from a real asset problem. KORDEX is being developed to make that investigation more explicit: what was observed, what evidence supports the observation, what is missing, and what remains unknown.

## What the current prototype includes

- A local browser-based operator interface for KORDEX, the reliability-intelligence system within Genesis.
- Python processing for submitted or recorded telemetry, including pattern and observation-quality assessments.
- Evidence summaries and lineage links that describe traceable relationships without claiming causation.
- Investigation records, recommendations, and explicit limitations/unknowns.
- Adapters and experiments for exploring telemetry from different sources.

The default interface scenario uses synthetic telemetry processed by the Python engine. The interface is local and read-only with respect to physical robots: it does not establish a live connection to a robot, and recommendations are not commands to control a physical system. The ROS 2 adapter in this prototype is a payload adapter/demo, not a live ROS connection.

## What it does **not** prove

- A detected pattern does not prove a mechanical fault or establish its cause.
- The prototype has not established validated failure-prediction accuracy on representative field data.
- Submitted data is not automatically sensor-authenticated; provenance depends on what the source actually provides.
- Session memory and decision records are not a durable, signed, tamper-proof audit system.
- It must not be used as the sole basis for safety-critical maintenance or operational decisions. Human review is required.

## Run the local interface

Requirements: Python 3.11+ recommended. The core interface is designed to run with the Python standard library; tests use `pytest`, and some offline research scripts require additional packages and datasets that are intentionally not bundled in this public preview.

From the repository root:

```bash
python -m genesis_interface.server
```

Then open <http://127.0.0.1:8765>. The server binds to loopback by default. Do not expose it to a network without appropriate authentication, authorization, and deployment hardening.

To run the tests that do not require separately supplied research datasets, install pytest and run selected tests, for example:

```bash
python -m pip install pytest
python -m pytest -q test_observation_quality.py test_telemetry_pattern_engine.py test_genesis_interface.py
```

This is an example of a focused test selection, not a claim that the complete suite has been run against this public package. Some research tests expect excluded datasets or optional analysis dependencies.

## Guided offline investigation

For the shortest path from an unfamiliar telemetry file to a reviewed mapping and report, use the interactive workflow:

```powershell
python kordex_guided_investigation.py --input "/path/to/your-telemetry.csv"
```

The wizard inspects CSV, JSON, JSONL, or NDJSON fields, shows samples and missing-value counts, asks you to confirm the timestamp and source units, saves a mapping for review, and asks before running the offline investigation. It does not connect to a robot. Name-based suggestions are hints only; verify signal meaning and units against source documentation. See [`GUIDED_OFFLINE_INVESTIGATION.md`](GUIDED_OFFLINE_INVESTIGATION.md).

## Try KORDEX with your own recorded telemetry

You can test KORDEX without owning a robot or installing ROS 2. The custom telemetry importer accepts recorded CSV, JSON, JSON Lines, and NDJSON files. It uses an explicit mapping file so you can tell KORDEX which source fields represent supported signals and which units they use.

If you are not sure which fields your file contains, inspect it before writing a mapping:

```powershell
python inspect_telemetry.py --input examples/custom_robot_telemetry.csv
```

To create a **draft** mapping template from conservative field-name suggestions:

```powershell
python inspect_telemetry.py --input examples/custom_robot_telemetry.csv --template-out mapping-draft.json
```

The inspector shows sample values, missing counts, possible timestamp fields, and suggested signal names. It does not infer sensor units or run inference. Review the generated template and verify the meaning and units against the data source before using it. See [`TELEMETRY_FILE_INSPECTION.md`](TELEMETRY_FILE_INSPECTION.md).

Start with the included synthetic CSV example:

```bash
python custom_telemetry_import.py --input examples/custom_robot_telemetry.csv --config custom-telemetry-mapping.example.json --output-dir custom-telemetry-output
```

Or use the JSON example:

```bash
python custom_telemetry_import.py --input examples/custom_robot_telemetry.json --config custom-telemetry-json-mapping.example.json --output-dir custom-telemetry-json-output
```

To investigate your own data, copy the appropriate example mapping file, edit the robot identity, timestamp field and unit, and signal mappings, then run:

```bash
python custom_telemetry_import.py --input "/path/to/your-telemetry.csv" --config "/path/to/your-mapping.json" --output-dir my-investigation
```

See [`CUSTOM_TELEMETRY_IMPORT.md`](CUSTOM_TELEMETRY_IMPORT.md) for supported signals and units, input requirements, mapping examples, and troubleshooting. The importer writes a session JSON, a structured investigation report, and a readable text report. Unmapped fields are listed and excluded from inference; unsupported mappings and invalid units fail explicitly. Reports also include a descriptive offline data review with mapped-signal completeness, value ranges, and timestamp intervals. It does not apply engineering thresholds or diagnose failures; see [`KORDEX_OFFLINE_REPORT_REVIEW.md`](KORDEX_OFFLINE_REPORT_REVIEW.md).

**Important:** this is offline recorded-data analysis. KORDEX cannot independently authenticate the source or confirm that declared units are correct. A detected pattern is not proof of physical failure, and this workflow is not a validated failure-prediction accuracy claim. Do not use it as the sole basis for safety-critical decisions.

## Try the offline field-test package

Want to evaluate the included diagnostic-message workflow without connecting a robot? Start with [`GENESIS_FIELD_TEST/README.md`](GENESIS_FIELD_TEST/README.md). From the repository root, run:

```bash
python GENESIS_FIELD_TEST/run_example.py
```

This processes the included **synthetic** diagnostic messages offline and writes a structured session plus a readable investigation report under `GENESIS_FIELD_TEST/demo-output/`. The example demonstrates the current pipeline; its state labels and recommendations are not calibrated to a real robot and are not validated diagnoses.

## Architecture at a glance

1. **Input and context** — telemetry observations and available operating context.
2. **Quality and pattern analysis** — checks data readiness and identifies unusual behavior.
3. **Evidence synthesis** — records supporting observations, missing links, and limitations.
4. **Decision and investigation output** — communicates the engine assessment and a recommendation for human review.

See `GENESIS_ARCHITECTURE_V0_1.md`, `GENESIS_COMPONENT_MAP.md`, `GENESIS_SECURITY_MODEL_V0_1.md`, and `genesis_interface/README.md` for deeper technical detail.

## Roadmap

- Improve operator-facing investigation explanations.
- Validate the pipeline against appropriately licensed, documented recorded datasets.
- Measure false positives, false negatives, and performance under operating-context changes.
- Improve provenance, repeatability, and evidence traceability.
- Explore integrations only after interface boundaries and safety requirements are clearly defined.

## Data and privacy

Raw datasets, large observation-level exports, local caches, and generated session artifacts are intentionally excluded from this public preview. If you contribute or reproduce an experiment, document the dataset source, license, labels, preprocessing, and limitations. Never upload private robot telemetry or credentials without authorization.

## License and contributions

No open-source license has been applied yet. Until a license is added, no permission is granted to reuse, modify, or redistribute this code beyond rights provided by applicable law. Please contact the project owner before reusing it.

This repository is currently published for review and feedback; please open an issue before proposing substantial changes.
