import unittest
from genesis_system.runtime.genesis import Genesis


def record(time_step=None, observation_id=None, sequence_number=None):
    r = {
        "robot_id": "R-ID",
        "manufacturer": "TEST",
        "robot_type": "AMR",
        "motor_temperature": 30,
        "ambient_temperature": 25,
        "battery_level": 80,
        "battery_voltage": 48,
        "battery_current": 5,
        "battery_temperature": 30,
        "power_consumption": 100,
        "workload": 20,
        "robot_state": "idle",
    }
    if time_step is not None: r["time_step"] = time_step
    meta = {}
    if observation_id is not None: meta["observation_id"] = observation_id
    if sequence_number is not None: meta["sequence_number"] = sequence_number
    if meta: r["source_metadata"] = meta
    return r

class ObservationIdentityReplayTests(unittest.TestCase):
    def test_duplicate_observation_id_is_rejected(self):
        g = Genesis()
        g.investigate(record(observation_id="obs-1"))
        with self.assertRaises(ValueError):
            g.investigate(record(observation_id="obs-1"))
        self.assertEqual(len(g._records_by_robot["R-ID"]), 1)

    def test_sequence_number_must_increase(self):
        g = Genesis()
        g.investigate(record(sequence_number=10))
        with self.assertRaises(ValueError):
            g.investigate(record(sequence_number=10))
        with self.assertRaises(ValueError):
            g.investigate(record(sequence_number=9))
        self.assertEqual(len(g._records_by_robot["R-ID"]), 1)

    def test_identical_payload_without_identity_is_not_deduplicated(self):
        g = Genesis()
        g.investigate(record())
        g.investigate(record())
        self.assertEqual(len(g._records_by_robot["R-ID"]), 2)

if __name__ == "__main__": unittest.main()
