from __future__ import annotations

from ima_runtime.capabilities.audio.routes import build_audio_task_spec
from ima_runtime.capabilities.video.routes import build_video_task_spec
from ima_runtime.capabilities.workflow.confirmation import to_confirmable_plan
from ima_runtime.gateway.planner import build_workflow_plan
from ima_runtime.shared.types import ClarificationRequest, GatewayRequest, WorkflowPlanDraft


def _validate_step_routes(
    request: GatewayRequest,
    plan: WorkflowPlanDraft,
) -> ClarificationRequest | None:
    simulated_inputs = request.input_images

    for step in plan.steps:
        if step.capability == "video":
            probe_inputs = simulated_inputs
            if not probe_inputs and any(previous.capability == "image" for previous in plan.steps if previous.step_id in step.depends_on):
                probe_inputs = ("workflow-image-output",)

            routed = build_video_task_spec(
                GatewayRequest(
                    prompt=request.prompt,
                    media_targets=("video",),
                    input_images=probe_inputs,
                    intent_hints=request.intent_hints,
                    extra_params=request.extra_params,
                )
            )
            if isinstance(routed, ClarificationRequest):
                return routed
            simulated_inputs = routed.input_images
        elif step.capability == "audio":
            routed = build_audio_task_spec(
                GatewayRequest(
                    prompt=request.prompt,
                    media_targets=("audio",),
                    intent_hints=request.intent_hints,
                    extra_params=request.extra_params,
                )
            )
            if isinstance(routed, ClarificationRequest):
                return routed

    return None


def build_confirmable_plan(request: GatewayRequest) -> WorkflowPlanDraft | ClarificationRequest:
    plan = build_workflow_plan(request)
    if isinstance(plan, ClarificationRequest):
        return plan
    clarification = _validate_step_routes(request, plan)
    if clarification is not None:
        return clarification
    return to_confirmable_plan(plan)


__all__ = ["build_confirmable_plan"]
