import unittest

from observation_security import (
    DEGRADED, TRUSTED, UNTRUSTED, UNKNOWN, ObservationSecurity,
)


class ObservationSecurityTests(unittest.TestCase):
    def setUp(self):
        self.security = ObservationSecurity()
        self.record = {"robot_id": "R001", "time_step": 2}

    def test_missing_metadata_is_explicitly_degraded(self):
        result = self.security.assess(self.record, source_time_step=2, previous_time_step=1)
        self.assertEqual(result["status"], DEGRADED)
        self.assertEqual(result["authentication"], UNKNOWN)
        self.assertEqual(result["integrity"], UNKNOWN)
        self.assertEqual(result["freshness"], TRUSTED)

    def test_explicitly_verified_source_can_be_trusted(self):
        result = self.security.assess(
            self.record,
            source_metadata={
                "source_id": "robot:R001",
                "source_type": "robot",
                "authentication": "verified",
                "integrity": "verified",
                "authorization": "verified",
            },
            source_time_step=2,
            previous_time_step=1,
        )
        self.assertEqual(result["status"], TRUSTED)

    def test_non_monotonic_source_is_untrusted(self):
        result = self.security.assess(
            self.record,
            source_metadata={"authentication": "verified", "integrity": "verified", "authorization": "verified"},
            source_time_step=2,
            previous_time_step=2,
        )
        self.assertEqual(result["status"], UNTRUSTED)
        self.assertEqual(result["freshness"], UNTRUSTED)

    def test_security_does_not_claim_crypto_without_explicit_metadata(self):
        result = self.security.assess(self.record, source_time_step=2, previous_time_step=1)
        self.assertIn("cryptographically verified", " ".join(result["limitations"]))


if __name__ == "__main__":
    unittest.main()
