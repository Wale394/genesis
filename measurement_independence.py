
from dataclasses import dataclass
from enum import Enum

class Relationship(str, Enum):
    DISTINCT = "DISTINCT"
    SAME = "SAME"
    UNKNOWN = "UNKNOWN"

class Infrastructure(str, Enum):
    SEPARATE = "SEPARATE"
    SHARED = "SHARED"
    UNKNOWN = "UNKNOWN"

class Assessment(str, Enum):
    CORROBORATING = "CORROBORATING"
    COMMON_MODE_RISK = "COMMON_MODE_RISK"
    CONTEXTUAL_DIFFERENCE = "CONTEXTUAL_DIFFERENCE"
    INSUFFICIENT_INDEPENDENCE = "INSUFFICIENT_INDEPENDENCE"

@dataclass(frozen=True)
class MeasurementEvidence:
    evidence_id: str
    physical_signal: str
    source: str
    relationship: Relationship
    infrastructure: Infrastructure
    valid: bool = True
    current: bool = True
    location: str | None = None

def assess_pair(a, b):
    if not a.valid or not b.valid or not a.current or not b.current:
        return Assessment.INSUFFICIENT_INDEPENDENCE
    if a.location is not None and b.location is not None and a.location != b.location:
        return Assessment.CONTEXTUAL_DIFFERENCE
    if a.relationship == Relationship.UNKNOWN or b.relationship == Relationship.UNKNOWN:
        return Assessment.INSUFFICIENT_INDEPENDENCE
    if a.infrastructure == Infrastructure.UNKNOWN or b.infrastructure == Infrastructure.UNKNOWN:
        return Assessment.INSUFFICIENT_INDEPENDENCE
    if a.relationship == Relationship.SAME:
        return (Assessment.COMMON_MODE_RISK
                if a.infrastructure == Infrastructure.SHARED
                else Assessment.INSUFFICIENT_INDEPENDENCE)
    if a.relationship == Relationship.DISTINCT and b.relationship == Relationship.DISTINCT:
        return (Assessment.COMMON_MODE_RISK
                if a.infrastructure == Infrastructure.SHARED
                else Assessment.CORROBORATING)
    return Assessment.INSUFFICIENT_INDEPENDENCE
