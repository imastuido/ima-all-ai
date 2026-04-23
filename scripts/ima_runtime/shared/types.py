from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


MediaKind = Literal["image", "video", "audio"]


@dataclass(frozen=True)
class MediaSource:
    kind: MediaKind
    source: str
    role: Literal["input", "reference", "first_frame", "last_frame"] = "reference"


@dataclass(frozen=True)
class GatewayRequest:
    prompt: str
    media_targets: tuple[MediaKind, ...]
    input_images: tuple[str, ...] = ()
    reference_media: tuple[MediaSource, ...] = ()
    intent_hints: Mapping[str, Any] = field(default_factory=dict)
    extra_params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteDecision:
    capability: MediaKind
    reason: str


@dataclass(frozen=True)
class ClarificationRequest:
    reason: str
    question: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowStepDraft:
    step_id: str
    capability: MediaKind
    goal: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowPlanDraft:
    summary: str
    steps: tuple[WorkflowStepDraft, ...]


@dataclass(frozen=True)
class WorkflowStepExecution:
    step_id: str
    capability: MediaKind
    task_id: str
    url: str
    task_type: str = ""
    cover_url: str = ""
    model_id: str = ""
    model_name: str = ""
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowExecutionResult:
    summary: str
    steps: tuple[WorkflowStepExecution, ...]


@dataclass(frozen=True)
class TaskSpec:
    capability: MediaKind
    task_type: str
    prompt: str
    input_images: tuple[str, ...] = ()
    reference_media: tuple[MediaSource, ...] = ()
    extra_params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelCandidate:
    name: str
    model_id: str
    version_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelBinding:
    candidate: ModelCandidate
    attribute_id: int
    credit: int
    resolved_params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    url: str
    cover_url: str = ""
    model_id: str = ""
    model_name: str = ""
