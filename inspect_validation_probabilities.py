"""Compatibility shim: canonical implementation lives in offline.validation.inspect_validation_probabilities."""
from importlib import import_module as _import_module
_impl = _import_module("offline.validation.inspect_validation_probabilities")
globals().update({k: v for k, v in vars(_impl).items() if k not in {"__name__", "__package__", "__loader__", "__spec__"}})
