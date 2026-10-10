class RiskEngine:

    def __init__(self, history):
        self.history = history

    def calculate_risk(self, diagnosis, pattern_data, recurrence_data, condition_data):

        score = 0
        evidence = []

        # Recurrence
        if recurrence_data["occurrences"] >= 3:
            score += 3
            evidence.append("Pattern occurred at least 3 times.")

        elif recurrence_data["occurrences"] == 2:
            score += 2
            evidence.append("Pattern occurred more than once.")

        # Severity
        critical_events = pattern_data["severities"].count("CRITICAL")
        warning_events = pattern_data["severities"].count("WARNING")

        if critical_events >= 2:
            score += 3
            evidence.append("Multiple critical events detected.")

        elif critical_events == 1:
            score += 2
            evidence.append("A critical event was detected.")

        elif warning_events >= 2:
            score += 1
            evidence.append("Multiple warning events detected.")

        # Robots affected
        robots_affected = len(pattern_data["robots"])

        if robots_affected >= 3:
            score += 3
            evidence.append("Multiple robots were affected.")

        elif robots_affected == 2:
            score += 2
            evidence.append("Two robots were affected.")

        # Event conditions
        if condition_data["working_events"] > 0:
            score += 1
            evidence.append(
                "The pattern occurred while robots were working."
            )

        # Risk level
        if score >= 7:
            risk_level = "HIGH"

        elif score >= 4:
            risk_level = "MEDIUM"

        else:
            risk_level = "LOW"

        return {
            "diagnosis": diagnosis,
            "score": score,
            "risk_level": risk_level,
            "evidence": evidence
        }