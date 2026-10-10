"""Small adapter boundary for heterogeneous physical-system telemetry."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from asset_contract import AssetProfile, NormalizedObservation


class DomainAdapter(ABC):
    """Translate a domain-specific payload into Genesis' common observation envelope."""

    domain: str = "generic"

    @abstractmethod
    def normalize(self, payload: Dict[str, Any]) -> NormalizedObservation:
        raise NotImplementedError


class GenericDomainAdapter(DomainAdapter):
    """Reference adapter for domains whose payload already exposes clear signals."""

    def normalize(self, payload: Dict[str, Any]) -> NormalizedObservation:
        asset = AssetProfile(
            asset_id=str(payload["asset_id"]),
            domain=str(payload.get("domain", self.domain)),
            asset_type=str(payload.get("asset_type", "unknown")),
            manufacturer=str(payload.get("manufacturer", "UNKNOWN")),
            model=str(payload.get("model", "UNKNOWN")),
            site_id=str(payload.get("site_id", "UNKNOWN")),
            metadata=dict(payload.get("asset_metadata", {})),
        )
        return NormalizedObservation(
            asset=asset,
            timestamp=payload.get("timestamp"),
            signals=dict(payload["signals"]),
            source=str(payload.get("source", "unknown")),
            provenance=dict(payload.get("provenance", {})),
            quality=str(payload.get("quality", "AVAILABLE")),
        )


class RoboticsAdapter(GenericDomainAdapter):
    domain = "robotics"


class EnergyInfrastructureAdapter(GenericDomainAdapter):
    domain = "energy_infrastructure"


class IndustrialEquipmentAdapter(GenericDomainAdapter):
    domain = "industrial_equipment"


class WarehouseInfrastructureAdapter(GenericDomainAdapter):
    domain = "warehouse_infrastructure"


class DomainAdapterRegistry:
    """Register domain adapters without changing Genesis core reasoning."""

    def __init__(self) -> None:
        self._adapters = {}

    def register(self, domain: str, adapter: DomainAdapter) -> None:
        if not domain:
            raise ValueError("Domain cannot be empty.")
        if not isinstance(adapter, DomainAdapter):
            raise TypeError("adapter must implement DomainAdapter.")
        if domain in self._adapters:
            raise ValueError(f"Adapter for domain {domain!r} is already registered.")
        self._adapters[domain] = adapter

    def get(self, domain: str) -> DomainAdapter:
        try:
            return self._adapters[domain]
        except KeyError as exc:
            raise KeyError(f"No adapter registered for domain {domain!r}.") from exc

    def domains(self):
        return tuple(sorted(self._adapters))
