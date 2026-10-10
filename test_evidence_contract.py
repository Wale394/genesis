import unittest

from evidence_contract import Evidence, EvidenceCategory
from evidence_synthesis import EvidenceSynthesis


class EvidenceContractIntegrationTests(unittest.TestCase):
    def test_contract_evidence_is_synthesized(self):
        evidence = Evidence(
            category=EvidenceCategory.DEVIATION,
            name="motor_temperature_deviation",
            value=8.0,
            source="baseline_engine",
            confidence=0.9,
            metadata={"statement": "Motor temperature is 8°C above baseline."},
        )

        result = EvidenceSynthesis().synthesize(
            feature_record={"robot_id": "R001", "time_step": 1},
            evidence_items=[evidence],
        )

        self.assertEqual(len(result["contract_evidence"]), 1)
        self.assertEqual(result["contract_evidence"][0]["category"], "deviation")
        self.assertEqual(result["contract_evidence"][0]["source"], "baseline_engine")
        self.assertEqual(result["contract_evidence"][0]["confidence"], 0.9)

    def test_invalid_contract_item_is_rejected(self):
        with self.assertRaises(TypeError):
            EvidenceSynthesis().synthesize(
                feature_record={"robot_id": "R001"},
                evidence_items=[{"category": "deviation"}],
            )


if __name__ == "__main__":
    unittest.main()
