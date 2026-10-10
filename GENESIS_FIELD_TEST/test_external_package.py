"""Smoke test runnable with only files inside this distribution folder."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parent


class PackagedFieldTestTests(unittest.TestCase):
    def test_recorded_example_runs_through_packaged_genesis(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "field-session.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE / "genesis_field_agent.py"),
                    "--config", str(PACKAGE / "config.example.json"),
                    "--input", str(PACKAGE / "examples" / "recorded_diagnostics_example.json"),
                    "--output", str(output),
                ],
                cwd=PACKAGE,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            session = json.loads(output.read_text(encoding="utf-8"))
            rendered = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE / "investigation_report.py"),
                    "--input", str(output),
                ],
                cwd=PACKAGE,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(session["session"]["robot"]["robot_id"], "FIELD-R001")
        self.assertEqual(len(session["observations"]), 10)
        self.assertEqual(len(session["genesis_results"]), 10)
        final_result = session["genesis_results"][-1]["result"]
        self.assertEqual(final_result["robot"]["robot_id"], "FIELD-R001")
        self.assertEqual(final_result["capability_discovery"]["robot_identity"]["robot_id"], "FIELD-R001")
        self.assertEqual(final_result["capability_discovery"]["observation_count"], 10)
        synthesis = final_result["evidence_synthesis"]
        self.assertTrue(synthesis["observations"])
        self.assertTrue(synthesis["pattern_evidence"])
        self.assertTrue(synthesis["engineering_evidence"])
        self.assertFalse(final_result["ml_inference"].get("prediction_available", False))
        self.assertIsNone(final_result["ml_inference"].get("probability"))

        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertIn("GENESIS INVESTIGATION REPORT", rendered.stdout)
        self.assertIn("FIELD-R001", rendered.stdout)


if __name__ == "__main__":
    unittest.main()

