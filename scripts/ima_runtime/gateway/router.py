"""Request classification seam for normalized gateway requests.

This module is useful for routing tests and architectural boundaries, but it is
not the main CLI execution path for the current public runtime.
"""

from __future__ import annotations

from ima_runtime.gateway.planner import build_workflow_plan, normalize_media_targets
from ima_runtime.shared.types import ClarificationRequest, GatewayRequest, RouteDecision, WorkflowPlanDraft


def route_request(request: GatewayRequest) -> RouteDecision | WorkflowPlanDraft | ClarificationRequest:
    targets = normalize_media_targets(request)
    if isinstance(targets, ClarificationRequest):
        return targets
    if len(targets) > 1:
        return build_workflow_plan(request)
    return RouteDecision(capability=targets[0], reason="single media target")
