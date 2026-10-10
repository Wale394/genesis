import unittest

from evidence_engine import EvidenceEngine
from observation_quality import ObservationQuality, AVAILABLE, DEGRADED, INSUFFICIENT
from test_observation_quality import sample_stream


class ObservationQualityScopeTests(unittest.TestCase):
    def setUp(self):
        self.records = sample_stream()
        self.current = dict(self.records[-1])
        self.history = self.records[:-1]

    def test_battery_degradation_does_not_invalidate_thermal_scope(self):
        self.current["battery_level"] = 120.0
        quality = ObservationQuality().assess(self.current, self.history)

        self.assertEqual(quality["groups"]["battery"]["status"], DEGRADED)
        self.assertEqual(quality["groups"]["thermal"]["status"], AVAILABLE)
        self.assertEqual(quality["field_groups"]["motor_temperature"]["status"], AVAILABLE)
        self.assertEqual(quality["field_groups"]["battery_level"]["status"], DEGRADED)
        self.assertEqual(quality["status"], DEGRADED)
        self.assertFalse(quality["prediction_ready"] is False)

    def test_evidence_items_carry_their_own_quality_scope(self):
        self.current["battery_level"] = 120.0
        quality = ObservationQuality().assess(self.current, self.history)
        evidence = EvidenceEngine().build_evidence_summary(
            self.current,
            risk_result={"probability": 0.20, "prediction": 0},
            observation_quality=quality,
        )
        items = {item["field"]: item for item in evidence["items"]}

        self.assertTrue(items["motor_temperature"]["usable"])
        self.assertEqual(items["motor_temperature"]["quality_status"], AVAILABLE)
        self.assertFalse(items["battery_level"]["usable"])
        self.assertEqual(items["battery_level"]["quality_status"], DEGRADED)

    def test_insufficient_thermal_history_limits_thermal_scope_only(self):
        short_history = []
        record = sample_stream(count=1)[0]
        quality = ObservationQuality().assess(record, short_history)

        self.assertEqual(quality["groups"]["thermal"]["status"], INSUFFICIENT)
        self.assertEqual(quality["field_groups"]["motor_temperature"]["status"], INSUFFICIENT)

    def test_quality_scope_does_not_claim_global_model_readiness(self):
        self.current["battery_level"] = None
        quality = ObservationQuality().assess(self.current, self.history)

        self.assertFalse(quality["prediction_ready"])
        self.assertEqual(quality["field_groups"]["motor_temperature"]["status"], AVAILABLE)
        self.assertEqual(quality["field_groups"]["battery_level"]["status"], INSUFFICIENT)


if __name__ == "__main__":
    unittest.main()
