from __future__ import annotations

from ima_runtime.shared.types import GatewayRequest, TaskSpec


def build_image_task_spec(request: GatewayRequest) -> TaskSpec:
    task_type = "image_to_image" if request.input_images else "text_to_image"
    return TaskSpec(
        capability="image",
        task_type=task_type,
        prompt=request.prompt,
        input_images=request.input_images,
        extra_params=request.extra_params,
    )
