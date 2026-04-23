from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

from ima_runtime.shared.model_recommendation import (
    choose_runtime_default_model_id,
    recommend_model_ids,
)
from ima_runtime.shared.types import MediaSource


logger = logging.getLogger("ima_skills")


def _candidate_model_id(candidate: dict) -> str:
    return str((candidate.get("model_params") or {}).get("model_id") or candidate["summary"].get("model_id") or "")


def _load_candidate_model_params(
    *,
    tree: list,
    candidate: dict,
    version_id: str | None,
    find_model_version_fn,
    extract_model_params_fn,
    logger,
) -> dict:
    selected_model_id = str(candidate["summary"].get("model_id") or "")
    candidate_version_id = candidate["summary"].get("version_id")
    node = find_model_version_fn(tree, selected_model_id, version_id or candidate_version_id)
    if not node:
        logger.error("Model not found: model_id=%s", selected_model_id)
        raise RuntimeError(f"model_id='{selected_model_id}' not found in the live catalog.")
    try:
        return extract_model_params_fn(node)
    except RuntimeError as exc:
        logger.error("Param extraction failed for model_id=%s: %s", selected_model_id, str(exc))
        raise RuntimeError(str(exc)) from exc


def resolve_model_candidates(
    *,
    tree: list,
    task_type: str,
    explicit_model_id: str | None,
    raw_extra: dict,
    reference_media: tuple[MediaSource, ...],
    list_all_models_fn: Callable[[list, str | None], list[dict]],
    sanitize_extra_params_fn=None,
) -> tuple[list[dict], dict[str, str], list[dict]]:
    candidate_rows = list_all_models_fn(tree, task_type)
    compatible_candidates: list[dict] = []
    rejection_reasons: dict[str, str] = {}
    has_multimodal_reference = any(item.kind in {"video", "audio"} for item in reference_media)
    model_constraint_universe: set[str] = set()

    def _supported_constraint_keys(row: dict) -> set[str]:
        supported = set(row.get("form_fields") or [])
        supported.update(row.get("attribute_keys") or [])
        supported.update(row.get("virtual_ui_fields") or [])
        if "audio" in supported:
            supported.add("generate_audio")
        return supported

    for row in candidate_rows:
        model_constraint_universe.update(_supported_constraint_keys(row))

    enforced_constraint_keys = {key for key in raw_extra.keys() if key in model_constraint_universe}

    for row in candidate_rows:
        candidate_model_id = str(row.get("model_id") or "").strip()
        if explicit_model_id and candidate_model_id != explicit_model_id:
            continue

        if not enforced_constraint_keys and not has_multimodal_reference:
            compatible_candidates.append(
                {
                    "summary": row,
                    "model_params": None,
                }
            )
            continue

        if has_multimodal_reference and task_type != "reference_image_to_video":
            rejection_reasons[candidate_model_id] = "reference video/audio only applies to reference_image_to_video"
            continue

        supported_constraint_keys = _supported_constraint_keys(row)
        unsupported_constraint_keys = sorted(enforced_constraint_keys - supported_constraint_keys)
        if unsupported_constraint_keys:
            rejection_reasons[candidate_model_id] = (
                "unsupported explicit constraint keys: " + ", ".join(unsupported_constraint_keys)
            )
            continue

        compatible_candidates.append(
            {
                "summary": row,
                "model_params": None,
            }
        )

    return compatible_candidates, rejection_reasons, candidate_rows


def resolve_model_params_for_task(
    *,
    task_type: str,
    explicit_model_id: str | None,
    version_id: str | None,
    base: str,
    api_key: str,
    language: str,
    user_id: str,
    status_stream,
    json_output_mode: bool,
    normalize_model_id_fn,
    get_product_list_fn,
    list_all_models_fn,
    get_preferred_model_id_fn,
    find_model_version_fn,
    extract_model_params_fn,
    sanitize_extra_params_fn=None,
    print_model_summary_fn,
    allow_recommended_default: bool = False,
    allow_saved_preference: bool = True,
    model_selection_context: str | None = None,
    raw_extra: dict | None = None,
    reference_media: tuple[MediaSource, ...] = (),
    logger=logger,
) -> dict:
    print(f"🔍 Querying product list: category={task_type}", file=status_stream, flush=True)
    try:
        tree = get_product_list_fn(base, api_key, task_type, language=language)
    except Exception as exc:  # pragma: no cover - exercised through CLI behavior tests
        logger.error("Product list failed: %s", str(exc))
        raise RuntimeError(f"Product list failed for task_type='{task_type}': {exc}") from exc

    explicit_model_id = normalize_model_id_fn(explicit_model_id) if explicit_model_id else None
    compatible_candidates, rejection_reasons, available_models = resolve_model_candidates(
        tree=tree,
        task_type=task_type,
        explicit_model_id=explicit_model_id,
        raw_extra=raw_extra or {},
        reference_media=reference_media,
        list_all_models_fn=list_all_models_fn,
    )

    if raw_extra and sanitize_extra_params_fn:
        from ima_runtime.shared.task_creation import VirtualParamResolutionError

        filtered_candidates: list[dict] = []
        for candidate in compatible_candidates:
            candidate_model_id = _candidate_model_id(candidate)
            try:
                model_params = _load_candidate_model_params(
                    tree=tree,
                    candidate=candidate,
                    version_id=version_id,
                    find_model_version_fn=find_model_version_fn,
                    extract_model_params_fn=extract_model_params_fn,
                    logger=logger,
                )
                sanitize_extra_params_fn(raw_extra, model_params, task_type)
            except (RuntimeError, VirtualParamResolutionError) as exc:
                rejection_reasons[candidate_model_id] = str(exc)
                continue
            filtered_candidates.append(
                {
                    "summary": candidate["summary"],
                    "model_params": model_params,
                }
            )
        compatible_candidates = filtered_candidates

    if explicit_model_id and not available_models:
        node = find_model_version_fn(tree, explicit_model_id, version_id)
        if not node:
            logger.error("Model not found: model_id=%s, task_type=%s", explicit_model_id, task_type)
            raise RuntimeError(f"model_id='{explicit_model_id}' not found for task_type='{task_type}'.")
        try:
            model_params = extract_model_params_fn(node)
        except RuntimeError as exc:
            logger.error("Param extraction failed: %s", str(exc))
            raise RuntimeError(str(exc)) from exc
        if json_output_mode:
            with contextlib.redirect_stdout(status_stream):
                print_model_summary_fn(model_params)
        else:
            print_model_summary_fn(model_params)
        return model_params

    if (
        any(item.kind in {"video", "audio"} for item in reference_media)
        and not explicit_model_id
        and len({str(model.get("model_id") or "") for model in available_models if model.get("model_id")}) > 1
    ):
        recommended_model_ids = recommend_model_ids(task_type, available_models)
        recommendation_hint = ""
        if recommended_model_ids:
            recommendation_hint = " Compatible model_ids: " + ", ".join(recommended_model_ids) + "."
        context_hint = f" {model_selection_context}" if model_selection_context else ""
        raise RuntimeError(
            f"--model-id is required for task_type='{task_type}' because multiple live-catalog models remain."
            + context_hint
            + recommendation_hint
            + " Run with --list-models or provide --model-id."
        )

    compatible_model_ids = [
        str((item.get("model_params") or {}).get("model_id") or item["summary"].get("model_id") or "")
        for item in compatible_candidates
    ]

    available_model_ids = [f"  {model['model_id']}" for model in available_models]
    if explicit_model_id and explicit_model_id not in {str(model.get("model_id") or "") for model in available_models}:
        logger.error("Model not found: model_id=%s, task_type=%s", explicit_model_id, task_type)
        raise RuntimeError(
            f"model_id='{explicit_model_id}' not found for task_type='{task_type}'.\n"
            "Available model_ids:\n" + "\n".join(available_model_ids)
        )

    if explicit_model_id and not compatible_candidates:
        reason = rejection_reasons.get(explicit_model_id) or "model is incompatible with the explicit request constraints"
        raise RuntimeError(
            f"model_id='{explicit_model_id}' is incompatible with task_type='{task_type}'. Reason: {reason}."
        )

    selected_candidate: dict | None = None
    if allow_saved_preference:
        preferred_model_id = get_preferred_model_id_fn(user_id, task_type)
        preferred_model_id = normalize_model_id_fn(preferred_model_id) if preferred_model_id else None
        if preferred_model_id:
            selected_candidate = next(
                (item for item in compatible_candidates if _candidate_model_id(item) == preferred_model_id),
                None,
            )
            if selected_candidate is not None:
                print(f"💡 Using your preferred model: {preferred_model_id}", file=status_stream, flush=True)

    if selected_candidate is None:
        selected_model_id = choose_runtime_default_model_id(
            task_type,
            [item["summary"] for item in compatible_candidates],
        )
        if selected_model_id:
            selected_candidate = next(
                (item for item in compatible_candidates if _candidate_model_id(item) == selected_model_id),
                None,
            )
            if selected_candidate is not None:
                message = (
                    f"💡 Using the only runtime-listed compatible model: {selected_model_id}"
                    if (raw_extra or reference_media)
                    else f"💡 Using the only runtime-listed model: {selected_model_id}"
                )
                print(message, file=status_stream, flush=True)

    if selected_candidate is None:
        recommended_model_ids = recommend_model_ids(
            task_type,
            [item["summary"] for item in compatible_candidates],
        )
        if allow_recommended_default and recommended_model_ids:
            selected_candidate = next(
                (item for item in compatible_candidates if _candidate_model_id(item) == recommended_model_ids[0]),
                None,
            )
            if selected_candidate is not None:
                message = (
                    f"💡 Using recommended compatible model: {recommended_model_ids[0]}"
                    if (raw_extra or reference_media)
                    else f"💡 Using recommended model: {recommended_model_ids[0]}"
                )
                print(message, file=status_stream, flush=True)
        else:
            recommendation_hint = ""
            if recommended_model_ids:
                label = "Compatible model_ids" if (raw_extra or reference_media) else "Recommended model_ids"
                recommendation_hint = f" {label}: " + ", ".join(recommended_model_ids) + "."
            context_hint = f" {model_selection_context}" if model_selection_context else ""
            if compatible_model_ids:
                raise RuntimeError(
                    f"--model-id is required for task_type='{task_type}' because multiple compatible models remain."
                    + context_hint
                    + recommendation_hint
                    + " Run with --list-models or provide --model-id."
                )
            raise RuntimeError(
                (
                    f"No live-catalog models are compatible with task_type='{task_type}' and the explicit request constraints."
                    + context_hint
                    + recommendation_hint
                )
            )

    model_params = selected_candidate["model_params"]
    if model_params is None:
        selected_model_id = str(selected_candidate["summary"].get("model_id") or "")
        try:
            model_params = _load_candidate_model_params(
                tree=tree,
                candidate=selected_candidate,
                version_id=version_id,
                find_model_version_fn=find_model_version_fn,
                extract_model_params_fn=extract_model_params_fn,
                logger=logger,
            )
        except RuntimeError as exc:
            raise RuntimeError(
                f"model_id='{selected_model_id}' not found for task_type='{task_type}'.\n"
                "Available model_ids:\n" + "\n".join(available_model_ids)
            ) from exc

    if json_output_mode:
        with contextlib.redirect_stdout(status_stream):
            print_model_summary_fn(model_params)
    else:
        print_model_summary_fn(model_params)

    return model_params


__all__ = [
    "resolve_model_candidates",
    "resolve_model_params_for_task",
]
