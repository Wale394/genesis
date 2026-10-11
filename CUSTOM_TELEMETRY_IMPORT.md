# KORDEX custom recorded telemetry import

This offline workflow lets an engineer investigate their own recorded `.csv`, `.json`, `.jsonl`, or `.ndjson` telemetry without editing Python source. A JSON mapping file declares how source fields map to KORDEX's supported telemetry contract.

## Try the included CSV example

From the GenesisLabcl project root:

```powershell
python custom_telemetry_import.py --input examples/custom_robot_telemetry.csv --config custom-telemetry-mapping.example.json --output-dir custom-telemetry-output
```

## Try the included JSON example

```powershell
python custom_telemetry_import.py --input examples/custom_robot_telemetry.json --config custom-telemetry-json-mapping.example.json --output-dir custom-telemetry-json-output
```

Both examples are synthetic. They demonstrate the format, not real robot telemetry or validated failure prediction.

## Inspect a file before creating its mapping

If you do not know the column names or structure in your file, inspect it first:

```powershell
python inspect_telemetry.py --input "C:\path\to\your-telemetry.csv"
```

To create a draft mapping file from conservative field-name suggestions:

```powershell
python inspect_telemetry.py --input "C:\path\to\your-telemetry.csv" --template-out mapping-draft.json
```

The template is deliberately incomplete: confirm the timestamp unit and every signal unit, and verify the meaning of each field from the source documentation. The inspector does not run inference or authenticate the sensor source. See [`TELEMETRY_FILE_INSPECTION.md`](TELEMETRY_FILE_INSPECTION.md) for details.

## Use your own data

Copy the relevant example mapping config and edit the robot identity, timestamp field/unit, and signal mappings to match your data. Then run:

```powershell
python custom_telemetry_import.py --input "C:\path\to\your-telemetry.csv" --config "C:\path\to\your-mapping.json" --output-dir my-investigation
```

## Input formats

- CSV: first row must contain field names.
- JSON: a list of record objects, a single record object, or an object containing an `observations` list. For another nested list, set optional `records_path` in the config (a dot-separated object path).
- JSON Lines: one JSON object per non-empty line (`.jsonl` or `.ndjson`).
- The timestamp field must be numeric. Declare its unit as `s`, `ms`, `us`, or `ns`. Records must be chronological with strictly increasing timestamps.

## Mapping config

- `robot.robot_id` is required. `manufacturer` and `robot_type` are optional.
- Optional `robot.robot_id_field` can override the static ID per record.
- `timestamp.field` and `timestamp.unit` are required.
- `signals` is a list of `{ "field": "source_name", "target": "KORDEX_FIELD", "unit": "SOURCE_UNIT" }` entries.
- Supported targets: `motor_temperature`, `ambient_temperature`, `battery_level`, `battery_voltage`, `battery_current`, `battery_temperature`, `power_consumption`, `voltage_drop`, `workload`, `robot_state`.
- JSON source fields may use dot paths, such as `sensors.motor.temperature`.
- Temperature source units `C`, `F`, and `K` are converted to canonical Celsius. Battery level accepts `%` or `fraction`; voltage accepts `V` or `mV`; current accepts `A` or `mA`; power accepts `W` or `kW`; workload accepts `unitless`. State accepts known values such as `working`, `running`, `active`, `idle`, and `standby`.
- Unsupported columns are listed by name and excluded. Unknown units and unsupported target fields fail explicitly. Label-like source fields (`label`, `target`, `ground_truth`, failure/fault labels, etc.) are blocked from being mapped into inference to reduce target leakage.

## Outputs

The output folder contains `field-session.json`, `investigation-report.json`, and `investigation-report.txt`. The reports preserve the declared mapping, source filename, time range, and unsupported source field names.

## Trust boundaries

- This is recorded data; the workflow does not connect to or control a robot.
- KORDEX cannot independently authenticate that a file came from the named robot or that its units match the sensors.
- Only configured signals enter inference. Unmapped columns are listed by name and excluded.
- A detected pattern is not proof of a physical failure. This workflow is not a validated failure-prediction accuracy claim.
- The importer is intentionally strict about numeric values and timestamps. Correct the mapping or source file rather than silently filling missing timestamps or guessing units.
