import unittest

from data_center_reliability_v0_1 import (
    DataCenterObservation,
    DataCenterReliabilityResearch,
)


class TestDataCenterReliabilityResearch(unittest.TestCase):
    def test_normal_observation_has_no_signal(self):
        engine = DataCenterReliabilityResearch()
        result = engine.observe(
            DataCenterObservation(
                timestamp=1,
                rack_id="RACK-01",
                inlet_temp_c=24,
                outlet_temp_c=35,
                power_kw=10,
                ups_load_pct=50,
                ups_battery_pct=90,
                humidity_pct=50,
            )
        )
        self.assertEqual(result, [])

    def test_thermal_signal(self):
        engine = DataCenterReliabilityResearch()
        result = engine.observe(
            DataCenterObservation(
                timestamp=1,
                rack_id="RACK-01",
                inlet_temp_c=31,
                outlet_temp_c=48,
            )
        )
        signals = {item["signal"] for item in result}
        self.assertEqual(
            signals,
            {"elevated_rack_inlet_temperature", "high_rack_thermal_delta"},
        )

    def test_power_change_is_temporal(self):
        engine = DataCenterReliabilityResearch()
        engine.observe(DataCenterObservation(timestamp=1, rack_id="RACK-01", power_kw=10))
        result = engine.observe(DataCenterObservation(timestamp=2, rack_id="RACK-01", power_kw=12))
        self.assertEqual({item["signal"] for item in result}, {"rapid_power_change"})

    def test_low_ups_battery(self):
        engine = DataCenterReliabilityResearch()
        result = engine.observe(DataCenterObservation(timestamp=1, rack_id="RACK-01", ups_battery_pct=20))
        self.assertEqual(result[0]["signal"], "low_ups_battery")


if __name__ == "__main__":
    unittest.main()
