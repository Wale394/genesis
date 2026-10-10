import unittest

from genesis_system.runtime.genesis import Genesis


def record(time_step, temperature=30):
    return {
        "robot_id": "R-TX",
        "manufacturer": "TEST",
        "robot_type": "AMR",
        "time_step": time_step,
        "motor_temperature": temperature,
        "ambient_temperature": 25,
        "battery_level": 80,
        "battery_voltage": 48,
        "battery_current": 5,
        "battery_temperature": 30,
        "power_consumption": 100,
        "workload": 20,
        "robot_state": "idle",
    }


class GenesisIngestionTransactionTests(unittest.TestCase):
    def test_failed_batch_does_not_commit_earlier_observations(self):
        genesis = Genesis()

        with self.assertRaises(ValueError):
            genesis.investigate([
                record(1),
                record(2),
                record(3, temperature="BAD"),
            ])

        self.assertEqual(genesis._records_by_robot.get("R-TX", []), [])
        self.assertNotIn("R-TX", genesis._states_by_robot)
        self.assertNotIn("R-TX", genesis._last_time_by_robot)
        self.assertNotIn("R-TX", genesis._timestamp_mode_by_robot)
        self.assertEqual(genesis._sampling_time_steps_by_robot.get("R-TX", []), [])
        self.assertEqual(genesis._capability_records_by_robot.get("R-TX", []), [])
        self.assertEqual(genesis._history.records, [])
        self.assertEqual(genesis._history.incidents, [])
        self.assertEqual(genesis._incident_manager.next_incident_number, 1)

    def test_failed_batch_preserves_preexisting_state(self):
        genesis = Genesis()
        genesis.investigate(record(1))
        before_records = list(genesis._records_by_robot["R-TX"])
        before_state = genesis._states_by_robot["R-TX"]
        before_next_id = genesis._incident_manager.next_incident_number

        with self.assertRaises(ValueError):
            genesis.investigate([
                record(2),
                record(3, temperature="BAD"),
            ])

        self.assertEqual(genesis._records_by_robot["R-TX"], before_records)
        self.assertEqual(genesis._states_by_robot["R-TX"], before_state)
        self.assertEqual(genesis._last_time_by_robot["R-TX"], 1)
        self.assertEqual(genesis._incident_manager.next_incident_number, before_next_id)
        self.assertEqual(genesis._history.records, [])

    def test_successful_batch_commits_all_observations(self):
        genesis = Genesis()
        result = genesis.investigate([record(1), record(2), record(3)])

        self.assertEqual(result["processing"]["observation_count"], 3)
        self.assertEqual(
            [r["time_step"] for r in genesis._records_by_robot["R-TX"]],
            [1, 2, 3],
        )
        self.assertEqual(genesis._last_time_by_robot["R-TX"], 3)


if __name__ == "__main__":
    unittest.main()
