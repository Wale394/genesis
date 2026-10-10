"""Compatibility shim: canonical implementation lives in genesis_system.adapters.robot_adapter."""
from importlib import import_module as _import_module
_impl = _import_module("genesis_system.adapters.robot_adapter")
globals().update({k: v for k, v in vars(_impl).items() if k not in {"__name__", "__package__", "__loader__", "__spec__"}})
