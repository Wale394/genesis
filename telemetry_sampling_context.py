"""Compatibility shim: canonical implementation lives in genesis_system.core.telemetry_sampling_context."""
from importlib import import_module as _import_module
_impl = _import_module("genesis_system.core.telemetry_sampling_context")
globals().update({k: v for k, v in vars(_impl).items() if k not in {"__name__", "__package__", "__loader__", "__spec__"}})
