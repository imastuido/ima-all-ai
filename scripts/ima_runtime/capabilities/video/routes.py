from __future__ import annotations

from ima_runtime.shared.config import VIDEO_TASK_TYPES
from ima_runtime.shared.types import ClarificationRequest, GatewayRequest, TaskSpec


def build_video_task_spec(request: GatewayRequest) -> TaskSpec | ClarificationRequest:
    explicit_task_type = request.intent_hints.get("task_type")
    if explicit_task_type in VIDEO_TASK_TYPES:
        return TaskSpec(
            capability="video",
            task_type=explicit_task_type,
            prompt=request.prompt,
            input_images=request.input_images,
            reference_media=request.reference_media,
            extra_params=dict(request.extra_params),
        )

    mode = request.intent_hints.get("video_mode")
    extra_params = dict(request.extra_params)

    if mode == "first_last_frame":
        return TaskSpec(
            capability="video",
            task_type="first_last_frame_to_video",
            prompt=request.prompt,
            input_images=request.input_images,
            reference_media=request.reference_media,
            extra_params=extra_params,
        )
    if mode == "reference":
        return TaskSpec(
            capability="video",
            task_type="reference_image_to_video",
            prompt=request.prompt,
            input_images=request.input_images,
            reference_media=request.reference_media,
            extra_params=extra_params,
        )
    if request.input_images and len(request.input_images) == 1:
        return TaskSpec(
            capability="video",
            task_type="image_to_video",
            prompt=request.prompt,
            input_images=request.input_images,
            reference_media=request.reference_media,
            extra_params=extra_params,
        )
    if request.input_images and len(request.input_images) >= 2:
        return ClarificationRequest(
            reason="video image roles ambiguous",
            question="这两张图分别是什么角色？是首帧/尾帧，还是参考图，还是只动其中一张？",
            options=("首帧/尾帧", "参考图", "只动其中一张"),
        )
    return TaskSpec(
        capability="video",
        task_type="text_to_video",
        prompt=request.prompt,
        reference_media=request.reference_media,
        extra_params=extra_params,
    )
