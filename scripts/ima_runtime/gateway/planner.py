from __future__ import annotations

from ima_runtime.shared.types import (
    ClarificationRequest,
    GatewayRequest,
    MediaKind,
    WorkflowPlanDraft,
    WorkflowStepDraft,
)


SUPPORTED_MEDIA_TARGETS: tuple[MediaKind, ...] = ("image", "video", "audio")


def normalize_media_targets(request: GatewayRequest) -> tuple[MediaKind, ...] | ClarificationRequest:
    deduplicated = tuple(dict.fromkeys(request.media_targets))
    if not deduplicated:
        return ClarificationRequest(
            reason="no media target",
            question="你这次要生成图片、视频还是音频？",
            options=("图片", "视频", "音频"),
        )

    invalid_targets = tuple(target for target in deduplicated if target not in SUPPORTED_MEDIA_TARGETS)
    if invalid_targets:
        invalid_summary = ", ".join(str(target) for target in invalid_targets)
        return ClarificationRequest(
            reason="unsupported media target",
            question=f"暂不支持这些类型: {invalid_summary}。请改为图片、视频或音频。",
            options=("图片", "视频", "音频"),
        )

    return tuple(target for target in SUPPORTED_MEDIA_TARGETS if target in deduplicated)


def build_workflow_plan(request: GatewayRequest) -> WorkflowPlanDraft | ClarificationRequest:
    ordered = normalize_media_targets(request)
    if isinstance(ordered, ClarificationRequest):
        return ordered

    steps = []
    for index, capability in enumerate(ordered, start=1):
        depends_on = () if index == 1 else (steps[-1].step_id,)
        steps.append(
            WorkflowStepDraft(
                step_id=f"{capability}-{index}",
                capability=capability,
                goal=f"Produce the {capability} output for: {request.prompt}",
                depends_on=depends_on,
            )
        )
    return WorkflowPlanDraft(summary=" -> ".join(ordered), steps=tuple(steps))
