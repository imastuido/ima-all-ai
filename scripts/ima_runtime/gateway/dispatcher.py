"""This module is a generic dispatch helper for gateway-shaped decisions and task specs.

The current public CLI usually calls capability modules directly through
`ima_runtime.cli_flow`, so this module mainly exists as a small reusable seam.
"""

from __future__ import annotations

from typing import Callable

from ima_runtime.shared.types import RouteDecision, TaskSpec


def dispatch_task_spec(spec: TaskSpec, registry: dict[str, Callable[[TaskSpec], object]]) -> object:
    return registry[spec.capability](spec)


def dispatch_route(decision: RouteDecision, registry: dict[str, Callable[[RouteDecision], object]]) -> object:
    return registry[decision.capability](decision)
