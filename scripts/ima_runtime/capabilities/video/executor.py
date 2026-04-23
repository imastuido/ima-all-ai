from __future__ import annotations

from ima_runtime.capabilities.video.compliance import verify_seedance_media_compliance
from ima_runtime.capabilities.video.params import build_video_model_params, normalize_video_binding
from ima_runtime.capabilities.video.reference_media import (
    has_multimodal_reference_media,
    is_seedance_extended_task,
    prepare_reference_media_bundle,
    prepare_seedance_media_bundle,
)
from ima_runtime.shared.config import POLL_CONFIG
from ima_runtime.shared.retry_logic import create_task_with_reflection
from ima_runtime.shared.task_execution import poll_task
from ima_runtime.shared.types import ExecutionResult, ModelBinding, TaskSpec


def execute_video_task(
    base_url: str,
    api_key: str,
    spec: TaskSpec,
    binding: ModelBinding,
    logger=None,
    status_writer=None,
) -> ExecutionResult:
    model_params = build_video_model_params(binding)
    extra_params, _ = normalize_video_binding(spec, model_params)
    cfg = POLL_CONFIG.get(spec.task_type, {"interval": 5, "max_wait": 300})
    prepared_media = {"input_urls": tuple(spec.input_images), "src_image": (), "src_video": (), "src_audio": ()}
    if is_seedance_extended_task(model_params.get("model_id"), spec.task_type):
        prepared_media = prepare_seedance_media_bundle(spec, api_key)
        verify_seedance_media_compliance(base_url, api_key, prepared_media["input_urls"])
    elif has_multimodal_reference_media(spec):
        prepared_media = prepare_reference_media_bundle(spec, api_key)
    task_id = create_task_with_reflection(
        base_url=base_url,
        api_key=api_key,
        task_type=spec.task_type,
        model_params=model_params,
        prompt=spec.prompt,
        input_images=list(prepared_media["input_urls"]),
        extra_params=extra_params or None,
        src_image=list(prepared_media["src_image"]),
        src_video=list(prepared_media["src_video"]),
        src_audio=list(prepared_media["src_audio"]),
        logger=logger,
        status_writer=status_writer,
    )
    media = poll_task(
        base_url,
        api_key,
        task_id,
        task_type=spec.task_type,
        estimated_max=cfg["max_wait"] // 2,
        poll_interval=cfg["interval"],
        max_wait=cfg["max_wait"],
        on_progress=(lambda _pct, _elapsed, message: status_writer(message)) if status_writer else None,
        logger=logger,
    )
    return ExecutionResult(
        task_id=task_id,
        url=media.get("url") or media.get("preview_url") or "",
        cover_url=media.get("cover_url") or "",
        model_id=binding.candidate.model_id,
        model_name=binding.candidate.name,
    )
