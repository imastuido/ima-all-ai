from __future__ import annotations

from ima_runtime.capabilities.image.params import build_image_model_params, normalize_image_binding
from ima_runtime.shared.retry_logic import create_task_with_reflection
from ima_runtime.shared.task_execution import poll_task
from ima_runtime.shared.types import ExecutionResult, ModelBinding, TaskSpec


def execute_image_task(
    base_url: str,
    api_key: str,
    spec: TaskSpec,
    binding: ModelBinding,
    logger=None,
    status_writer=None,
) -> ExecutionResult:
    model_params = build_image_model_params(binding)
    extra_params, _ = normalize_image_binding(spec, model_params)
    task_id = create_task_with_reflection(
        base_url=base_url,
        api_key=api_key,
        task_type=spec.task_type,
        model_params=model_params,
        prompt=spec.prompt,
        input_images=list(spec.input_images),
        extra_params=extra_params or None,
        logger=logger,
        status_writer=status_writer,
    )
    media = poll_task(
        base_url,
        api_key,
        task_id,
        task_type=spec.task_type,
        logger=logger,
        on_progress=(lambda _pct, _elapsed, message: status_writer(message)) if status_writer else None,
    )
    return ExecutionResult(
        task_id=task_id,
        url=media.get("url") or media.get("watermark_url") or media.get("preview_url") or "",
        cover_url=media.get("cover_url") or "",
        model_id=binding.candidate.model_id,
        model_name=binding.candidate.name,
    )
