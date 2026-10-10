"""Domain-neutral fleet/site registry for Genesis integrations and demos."""

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from asset_contract import AssetProfile, FleetSnapshot, NormalizedObservation


class AssetFleetRegistry:
    """Track heterogeneous physical assets without coupling Genesis to one industry."""

    def __init__(self) -> None:
        self._assets: Dict[str, AssetProfile] = {}
        self._observations: Dict[str, List[NormalizedObservation]] = defaultdict(list)

    def register(self, asset: AssetProfile) -> None:
        existing = self._assets.get(asset.asset_id)
        if existing is not None and existing != asset:
            raise ValueError(f"Asset {asset.asset_id!r} is already registered with different identity.")
        self._assets[asset.asset_id] = asset

    def ingest(self, observation: NormalizedObservation) -> None:
        self.register(observation.asset)
        self._observations[observation.asset.asset_id].append(observation)

    def get_asset(self, asset_id: str) -> Optional[AssetProfile]:
        return self._assets.get(asset_id)

    def observations(self, asset_id: str) -> List[NormalizedObservation]:
        return list(self._observations.get(asset_id, []))

    def peer_group(self, asset: AssetProfile) -> List[AssetProfile]:
        return [
            candidate
            for candidate in self._assets.values()
            if candidate.asset_id != asset.asset_id
            and candidate.domain == asset.domain
            and candidate.asset_type == asset.asset_type
        ]

    def snapshot(self) -> FleetSnapshot:
        observations = [item for values in self._observations.values() for item in values]
        return FleetSnapshot(assets=list(self._assets.values()), observations=observations)

    def summary(self) -> Dict[str, object]:
        counts: Dict[str, int] = defaultdict(int)
        for asset in self._assets.values():
            counts[asset.domain] += 1
        return {
            "asset_count": len(self._assets),
            "domain_count": len(counts),
            "assets_by_domain": dict(sorted(counts.items())),
            "sites": sorted({asset.site_id for asset in self._assets.values()}),
        }
