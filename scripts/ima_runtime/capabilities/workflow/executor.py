from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ima_runtime.shared.types import (
    ExecutionResult,
    GatewayRequest,
    WorkflowExecutionResult,
    WorkflowPlanDraft,
    WorkflowStepDraft,
    WorkflowStepExecution,
)


def _build_step_request(
    step: WorkflowStepDraft,
    root_request: GatewayRequest,
    prior_steps: tuple[WorkflowStepExecution, ...],
) -> GatewayRequest:
    input_images = root_request.input_images
    if step.capability == "video" and prior_steps:
        previous_url = prior_steps[-1].url
        input_images = (previous_url,) if previous_url else ()
    if step.capability == "audio":
        input_images = ()

    return GatewayRequest(
        prompt=root_request.prompt,
        media_targets=(step.capability,),
        input_images=input_images,
        intent_hints=root_request.intent_hints,
        extra_params=root_request.extra_params,
    )


def execute_confirmed_workflow(
    plan: WorkflowPlanDraft,
    request: GatewayRequest,
    registry: dict[str, Callable[[GatewayRequest], ExecutionResult | tuple[str, ExecutionResult]]],
    resume_from_step: str | None = None,
    reused_outputs: dict[str, str] | None = None,
) -> WorkflowExecutionResult:
    reused_outputs = dict(reused_outputs or {})
    completed: list[WorkflowStepExecution] = []
    steps_to_run = plan.steps

    if resume_from_step:
        resume_index = next((index for index, step in enumerate(plan.steps) if step.step_id == resume_from_step), None)
        if resume_index is None:
            raise ValueError(f"Unknown workflow step_id for resume: {resume_from_step}")

        for step in plan.steps[:resume_index]:
            reused_url = reused_outputs.get(step.step_id)
            if not reused_url:
                raise ValueError(
                    f"Missing reused output for prior step '{step.step_id}'. "
                    "Provide --reuse-output step_id=url for each skipped step."
                )
            completed.append(
                WorkflowStepExecution(
                    step_id=step.step_id,
                    capability=step.capability,
                    task_id=f"reused:{step.step_id}",
                    url=reused_url,
                    depends_on=step.depends_on,
                )
            )

        steps_to_run = plan.steps[resume_index:]

    for step in steps_to_run:
        step_request = _build_step_request(step, request, tuple(completed))
        outcome = registry[step.capability](step_request)
        task_type = ""
        if isinstance(outcome, tuple):
            task_type, result = cast(tuple[str, ExecutionResult], outcome)
        else:
            result = cast(ExecutionResult, outcome)
        completed.append(
            WorkflowStepExecution(
                step_id=step.step_id,
                capability=step.capability,
                task_id=result.task_id,
                url=result.url,
                task_type=task_type,
                cover_url=result.cover_url,
                model_id=result.model_id,
                model_name=result.model_name,
                depends_on=step.depends_on,
            )
        )

    return WorkflowExecutionResult(summary=plan.summary, steps=tuple(completed))


__all__ = ["execute_confirmed_workflow"]
