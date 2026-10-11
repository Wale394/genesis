# Inspect a telemetry file before mapping it

Use `inspect_telemetry.py` to understand an engineer-provided recorded CSV, JSON, JSONL, or NDJSON file before creating the KORDEX mapping configuration.

```powershell
python inspect_telemetry.py --input "C:\path\to\robot.csv"
```

To write a draft mapping file:

```powershell
python inspect_telemetry.py --input "C:\path\to\robot.csv" --template-out mapping-draft.json
```

The inspector prints the record count, field names, missing counts, observed value types, a few sample values, possible timestamp fields, and conservative name-based signal suggestions. It does **not** run inference, connect to a robot, or infer sensor units. Treat the output as a helper, not as an authoritative interpretation of a vendor's telemetry.

The generated JSON is deliberately a draft. Replace `CHOOSE_TIMESTAMP_UNIT` with `s`, `ms`, `us`, or `ns`, replace each `CHOOSE_SOURCE_UNIT` with a supported unit, and verify each field's meaning and the robot identity before using it with `custom_telemetry_import.py`. Label-like fields such as `failure`, `fault`, `outcome`, or `ground_truth` are never suggested as inference inputs.

```powershell
python custom_telemetry_import.py --input "C:\path\to\robot.csv" --config mapping-draft.json --output-dir my-investigation
```

Recorded files are user-provided and are not authenticated by KORDEX. Observed patterns are not proof of physical failure or validated failure prediction.
