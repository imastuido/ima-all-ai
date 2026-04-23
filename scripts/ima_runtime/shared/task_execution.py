from __future__ import annotations

import time

from ima_runtime.shared.client import create_task_request, get_task_detail
from ima_runtime.shared.config import VIDEO_RECORDS_URL, VIDEO_TASK_TYPES
from ima_runtime.shared.task_creation import build_create_payload


def create_task(
    base_url: str,
    api_key: str,
    task_type: str,
    model_params: dict,
    prompt: str,
    input_images: list[str] | None = None,
    extra_params: dict | None = None,
    src_image: list[dict] | None = None,
    src_video: list[dict] | None = None,
    src_audio: list[dict] | None = None,
    logger=None,
    status_writer=None,
) -> str:
    payload, attribute_id, credit, normalized_rule_params = build_create_payload(
        task_type=task_type,
        model_params=model_params,
        prompt=prompt,
        input_images=input_images,
        extra_params=extra_params,
        src_image=src_image,
        src_video=src_video,
        src_audio=src_audio,
    )

    if normalized_rule_params:
        if status_writer:
            status_writer(f"   📝 Normalized params from rule: {normalized_rule_params}")
    if (
        model_params.get("model_id") == "pixverse"
        and payload["parameters"][0]["parameters"].get("model")
        and "model" not in (model_params.get("form_params") or {})
        and not (extra_params and "model" in extra_params)
    ):
        inferred_model = payload["parameters"][0]["parameters"]["model"]
        if status_writer:
            status_writer(
                f"🔧 Auto-inferred Pixverse model parameter: model=\"{inferred_model}\" "
                f"(from model_name=\"{model_params.get('model_name', '')}\")"
            )

    if logger:
        logger.info(
            "Create task: model=%s, task_type=%s, credit=%s, attribute_id=%s",
            model_params["model_name"],
            task_type,
            credit,
            attribute_id,
        )

    data = create_task_request(base_url=base_url, api_key=api_key, payload=payload)
    code = data.get("code")
    if code not in (0, 200):
        if logger:
            logger.error(
                "Task create failed: code=%s, msg=%s, attribute_id=%s, credit=%s",
                code,
                data.get("message"),
                attribute_id,
                credit,
            )
        raise RuntimeError(
            f"Create task failed — code={code} "
            f"message={data.get('message')}"
        )

    task_id = (data.get("data") or {}).get("id")
    if not task_id:
        if logger:
            logger.error("Task create failed: no task_id in response")
        raise RuntimeError(f"No task_id in response: {data}")

    if logger:
        logger.info("Task created: task_id=%s", task_id)
    return task_id


def poll_task(
    base_url: str,
    api_key: str,
    task_id: str,
    task_type: str | None = None,
    estimated_max: int = 120,
    poll_interval: int = 5,
    max_wait: int = 600,
    on_progress=None,
    logger=None,
) -> dict:
    start = time.time()

    if logger:
        logger.info("Poll task started: task_id=%s, max_wait=%ss", task_id, max_wait)

    last_progress_report = 0
    progress_interval = 15 if poll_interval <= 5 else 30

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            if logger:
                logger.error("Task timeout: task_id=%s, elapsed=%ss, max_wait=%s", task_id, int(elapsed), max_wait)
            if task_type in VIDEO_TASK_TYPES:
                raise TimeoutError(
                    f"Task {task_id} timed out after {max_wait}s without explicit backend errors. "
                    f"Please check your creation record at {VIDEO_RECORDS_URL}."
                )
            raise TimeoutError(
                f"Task {task_id} timed out after {max_wait}s. "
                "Check the IMA dashboard for status."
            )

        data = get_task_detail(base_url=base_url, api_key=api_key, task_id=task_id)
        code = data.get("code")
        if code not in (0, 200):
            raise RuntimeError(f"Poll error — code={code} msg={data.get('message')}")

        task = data.get("data") or {}
        medias = task.get("medias") or []

        def resource_status(media: dict) -> int:
            value = media.get("resource_status")
            return 0 if (value is None or value == "") else int(value)

        for media in medias:
            status = resource_status(media)
            if status == 2:
                err = media.get("error_msg") or media.get("remark") or "unknown"
                if logger:
                    logger.error("Task failed: task_id=%s, resource_status=2, error=%s", task_id, err)
                raise RuntimeError(f"Generation failed (resource_status=2): {err}")
            if status == 3:
                if logger:
                    logger.error("Task deleted: task_id=%s", task_id)
                raise RuntimeError("Task was deleted")

        if medias and all(resource_status(media) == 1 for media in medias):
            for media in medias:
                if (media.get("status") or "").strip().lower() == "failed":
                    err = media.get("error_msg") or media.get("remark") or "unknown"
                    if logger:
                        logger.error("Task failed: task_id=%s, status=failed, error=%s", task_id, err)
                    raise RuntimeError(f"Generation failed: {err}")
            first_media = medias[0]
            result_url = (
                first_media.get("url")
                or first_media.get("watermark_url")
                or first_media.get("preview_url")
            )
            if result_url:
                if logger:
                    logger.info(
                        "Task completed: task_id=%s, elapsed=%ss, url=%s",
                        task_id,
                        int(time.time() - start),
                        result_url[:80],
                    )
                return first_media

        if elapsed - last_progress_report >= progress_interval:
            pct = min(95, int(elapsed / estimated_max * 100))
            msg = f"⏳ {int(elapsed)}s elapsed … {pct}%"
            if elapsed > estimated_max:
                msg += "  (taking longer than expected, please wait…)"
            if on_progress:
                on_progress(pct, int(elapsed), msg)
            last_progress_report = elapsed

        time.sleep(poll_interval)


__all__ = [
    "create_task",
    "poll_task",
]
