from __future__ import annotations

from typing import TypeAlias

from ima_runtime.shared.types import WorkflowPlanDraft, WorkflowStepDraft


ConfirmablePlan: TypeAlias = WorkflowPlanDraft
ConfirmableStep: TypeAlias = WorkflowStepDraft

__all__ = ["ConfirmablePlan", "ConfirmableStep"]
