"""Compatibility shim: canonical implementation lives in genesis_system.core.data_availability."""
from importlib import import_module as _import_module
_impl = _import_module("genesis_system.core.data_availability")
globals().update({k: v for k, v in vars(_impl).items() if k not in {"__name__", "__package__", "__loader__", "__spec__"}})
