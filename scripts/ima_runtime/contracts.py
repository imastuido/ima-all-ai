"""This module is a compatibility layer for runtime contracts.

Core request/result dataclasses live in `ima_runtime.shared.types`. This module
re-exports those symbols for older import surfaces and defines a few
higher-level contract dataclasses used by tests and tooling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ima_runtime.shared.types import (
    ClarificationRequest,
    ExecutionResult,
    GatewayRequest,
    ModelBinding,
    ModelCandidate,
    RouteDecision,
    TaskSpec,
    WorkflowExecutionResult,
    WorkflowPlanDraft,
    WorkflowStepExecution,
    WorkflowStepDraft,
)


@dataclass(frozen=True)
class ModelSummary:
    name: str
    model_id: str
    raw_model_id: str
    version_id: str
    credit: int
    attr_id: int
    rule_count: int
    form_fields: list[str] = field(default_factory=list)
    virtual_fields: list[str] = field(default_factory=list)
    attribute_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedModel:
    model_id: str
    model_id_raw: str
    model_name: str
    model_version: str
    attribute_id: int
    credit: int
    form_params: dict[str, Any] = field(default_factory=dict)
    rule_attributes: dict[str, Any] = field(default_factory=dict)
    all_credit_rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RuleMatch:
    attribute_id: int
    credit: int
    canonical_params: dict[str, Any] = field(default_factory=dict)
    rule_attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreatePayloadContext:
    task_type: str
    prompt: str
    input_images: list[str] = field(default_factory=list)
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Diagnosis:
    code: int | str | None
    confidence: str
    headline: str
    reasoning: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    model_name: str = ""
    model_id: str = ""
    task_type: str = ""


@dataclass(frozen=True)
class RetryDecision:
    action: str
    new_params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    suggestion: str = ""
    new_attribute_id: int | None = None
    new_credit: int | None = None


@dataclass(frozen=True)
class GenerationResult:
    task_id: str
    url: str
    cover_url: str = ""
    model_id: str = ""
    model_name: str = ""
    credit: int = 0


__all__ = [
    "ModelSummary",
    "ResolvedModel",
    "RuleMatch",
    "CreatePayloadContext",
    "Diagnosis",
    "RetryDecision",
    "GenerationResult",
    "GatewayRequest",
    "RouteDecision",
    "ClarificationRequest",
    "WorkflowStepDraft",
    "WorkflowPlanDraft",
    "WorkflowStepExecution",
    "WorkflowExecutionResult",
    "TaskSpec",
    "ModelCandidate",
    "ModelBinding",
    "ExecutionResult",
]
