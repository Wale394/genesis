from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceCategory(str, Enum):
    OBSERVATION = "observation"
    BASELINE = "baseline"
    DEVIATION = "deviation"
    TEMPORAL = "temporal"
    CONTEXT = "context"
    PATTERN = "pattern"
    CROSS_SIGNAL = "cross_signal"
    HISTORICAL = "historical"
    FLEET = "fleet"
    QUALITY = "quality"
    SECURITY = "security"
    ML_INFERENCE = "ml_inference"


@dataclass
class Evidence:
    category: EvidenceCategory
    name: str
    value: Any
    source: str
    confidence: Optional[float] = None
    timestamp: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Evidence name cannot be empty.")
        if not self.source:
            raise ValueError("Evidence source cannot be empty.")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Evidence confidence must be between 0.0 and 1.0.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "name": self.name,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "context": self.context,
            "metadata": self.metadata,
            "limitations": self.limitations,
        }
