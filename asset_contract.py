"""Domain-neutral asset and observation contracts for Genesis integrations."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class AssetProfile:
    """Identity and context shared by physical assets across industries."""

    asset_id: str
    domain: str
    asset_type: str
    manufacturer: str = "UNKNOWN"
    model: str = "UNKNOWN"
    site_id: str = "UNKNOWN"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (("asset_id", self.asset_id), ("domain", self.domain), ("asset_type", self.asset_type)):
            if not value:
                raise ValueError(f"{name} cannot be empty.")


@dataclass(frozen=True)
class NormalizedObservation:
    """Common observation envelope produced by any domain adapter."""

    asset: AssetProfile
    timestamp: Any
    signals: Dict[str, Any]
    source: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    quality: str = "AVAILABLE"

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("Observation source cannot be empty.")
        if not self.signals:
            raise ValueError("Observation must contain at least one signal.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": {
                "asset_id": self.asset.asset_id,
                "domain": self.asset.domain,
                "asset_type": self.asset.asset_type,
                "manufacturer": self.asset.manufacturer,
                "model": self.asset.model,
                "site_id": self.asset.site_id,
                "metadata": dict(self.asset.metadata),
            },
            "timestamp": self.timestamp,
            "signals": dict(self.signals),
            "source": self.source,
            "provenance": dict(self.provenance),
            "quality": self.quality,
        }


@dataclass(frozen=True)
class FleetSnapshot:
    """Point-in-time inventory view used by demo and integration layers."""

    assets: List[AssetProfile]
    observations: List[NormalizedObservation]

    @property
    def asset_count(self) -> int:
        return len(self.assets)

    @property
    def domains(self) -> List[str]:
        return sorted({asset.domain for asset in self.assets})

    def by_domain(self, domain: str) -> List[AssetProfile]:
        return [asset for asset in self.assets if asset.domain == domain]
