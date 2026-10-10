
from measurement_independence import *

def ev(i, signal, source, rel, infra, valid=True, current=True, location=None):
    return MeasurementEvidence(i, signal, source, rel, infra, valid, current, location)

def test_01_distinct_separate_corroborate():
    assert assess_pair(ev("A","temperature","sa",Relationship.DISTINCT,Infrastructure.SEPARATE),
                        ev("B","vibration","sb",Relationship.DISTINCT,Infrastructure.SEPARATE)) == Assessment.CORROBORATING

def test_02_distinct_shared_common_mode():
    assert assess_pair(ev("A","temperature","sa",Relationship.DISTINCT,Infrastructure.SHARED),
                        ev("B","vibration","sb",Relationship.DISTINCT,Infrastructure.SHARED)) == Assessment.COMMON_MODE_RISK

def test_03_same_shared_common_mode():
    assert assess_pair(ev("A","temperature","sa",Relationship.SAME,Infrastructure.SHARED),
                        ev("B","temperature","sb",Relationship.SAME,Infrastructure.SHARED)) == Assessment.COMMON_MODE_RISK

def test_04_same_separate_not_independent():
    assert assess_pair(ev("A","temperature","sa",Relationship.SAME,Infrastructure.SEPARATE),
                        ev("B","temperature","sb",Relationship.SAME,Infrastructure.SEPARATE)) == Assessment.INSUFFICIENT_INDEPENDENCE

def test_05_unknown_relationship_not_independent():
    assert assess_pair(ev("A","temperature","sa",Relationship.UNKNOWN,Infrastructure.SEPARATE),
                        ev("B","vibration","sb",Relationship.DISTINCT,Infrastructure.SEPARATE)) == Assessment.INSUFFICIENT_INDEPENDENCE

def test_06_unknown_infrastructure_not_independent():
    assert assess_pair(ev("A","temperature","sa",Relationship.DISTINCT,Infrastructure.UNKNOWN),
                        ev("B","vibration","sb",Relationship.DISTINCT,Infrastructure.SEPARATE)) == Assessment.INSUFFICIENT_INDEPENDENCE

def test_07_invalid_measurement_cannot_corrobate():
    assert assess_pair(ev("A","temperature","sa",Relationship.DISTINCT,Infrastructure.SEPARATE,valid=False),
                        ev("B","vibration","sb",Relationship.DISTINCT,Infrastructure.SEPARATE)) == Assessment.INSUFFICIENT_INDEPENDENCE

def test_08_stale_measurement_cannot_corrobate():
    assert assess_pair(ev("A","temperature","sa",Relationship.DISTINCT,Infrastructure.SEPARATE,current=False),
                        ev("B","vibration","sb",Relationship.DISTINCT,Infrastructure.SEPARATE)) == Assessment.INSUFFICIENT_INDEPENDENCE

def test_09_different_locations_are_contextual():
    assert assess_pair(ev("A","temperature","sa",Relationship.DISTINCT,Infrastructure.SEPARATE,location="bearing"),
                        ev("B","temperature","sb",Relationship.DISTINCT,Infrastructure.SEPARATE,location="housing")) == Assessment.CONTEXTUAL_DIFFERENCE

def test_10_shared_controller_common_mode():
    assert assess_pair(ev("A","temperature","sa",Relationship.DISTINCT,Infrastructure.SHARED),
                        ev("B","current","sb",Relationship.DISTINCT,Infrastructure.SHARED)) == Assessment.COMMON_MODE_RISK

def test_11_unknown_dependency_not_independent():
    assert assess_pair(ev("A","thermal","ca",Relationship.DISTINCT,Infrastructure.UNKNOWN),
                        ev("B","electrical","cb",Relationship.DISTINCT,Infrastructure.UNKNOWN)) == Assessment.INSUFFICIENT_INDEPENDENCE

def test_12_usable_distinct_separate_evidence_corroborates():
    assert assess_pair(ev("A","temperature","sa",Relationship.DISTINCT,Infrastructure.SEPARATE),
                        ev("B","vibration","sb",Relationship.DISTINCT,Infrastructure.SEPARATE)) == Assessment.CORROBORATING
