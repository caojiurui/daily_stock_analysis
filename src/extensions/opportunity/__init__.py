# -*- coding: utf-8 -*-
"""Opt-in balanced opportunity engine extension."""

from importlib import import_module
from typing import Any

__all__ = ["OpportunityService"]


def __getattr__(name: str) -> Any:
    if name != "OpportunityService":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(".service", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
