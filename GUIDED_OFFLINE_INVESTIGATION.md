# KORDEX Guided Offline Investigation

This interactive workflow helps an engineer inspect a recorded telemetry file, explicitly map source fields to supported KORDEX signals, review a proposed mapping, and optionally run an offline investigation. It does not connect to a robot or send commands.

## Run

```powershell
python kordex_guided_investigation.py --input path\to\telemetry.csv
```

Supported formats: CSV, JSON, JSONL, and NDJSON. The wizard displays field names, missing counts, sample values, and conservative name-based suggestions; collects an asset label, timestamp field and unit, signal mappings, and source units; blocks label/outcome-like fields from inference; saves a mapping JSON; displays the proposed mapping; and asks before running an investigation. Declining leaves the config available for later use.

## Review requirements

- Suggestions are not proof of sensor meaning.
- Confirm timestamp semantics and units from source documentation.
- Input is user-provided recorded data; KORDEX does not authenticate the physical source.
- An observed anomaly is not proof of physical failure or validated failure prediction.
- Label/class/fault/outcome-like fields are blocked from inference to reduce target leakage.

By default, the mapping is saved to `kordex-guided-output/<input-stem>.kordex-mapping.json`. Existing configs are not overwritten unless `--overwrite-config` is supplied. Use `--config-out` to choose another path.
