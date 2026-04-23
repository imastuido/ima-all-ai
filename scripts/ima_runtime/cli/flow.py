"""The main CLI orchestration path for the current public runtime.

This module owns argument validation, request assembly, capability dispatch,
workflow plan/confirm flow, and user-facing CLI output. Read this before
exploring gateway seams when you need to understand what the CLI does today.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time

from ima_runtime.cli.presenter import print_model_summary
from ima_runtime.capabilities.audio.executor import execute_audio_task
from ima_runtime.capabilities.audio.models import build_audio_model_binding
from ima_runtime.capabilities.audio.routes import build_audio_task_spec
from ima_runtime.capabilities.image.executor import execute_image_task
from ima_runtime.capabilities.image.models import build_image_model_binding
from ima_runtime.capabilities.image.routes import build_image_task_spec
from ima_runtime.capabilities.video.executor import execute_video_task
from ima_runtime.capabilities.video.models import build_video_model_binding
from ima_runtime.capabilities.video.routes import build_video_task_spec
from ima_runtime.capabilities.workflow.coordinator import build_confirmable_plan
from ima_runtime.capabilities.workflow.confirmation import (
    append_execution_history,
    build_confirmable_plan_payload,
    list_saved_workflows,
    load_reviewed_plan,
    persist_confirmable_plan,
    plan_from_payload,
    request_from_dict,
)
from ima_runtime.capabilities.workflow.executor import execute_confirmed_workflow
from ima_runtime.shared.config import VIDEO_TASK_TYPES
from ima_runtime.shared.model_selection import resolve_model_params_for_task as _resolve_model_params_for_task
from ima_runtime.shared.model_recommendation import (
    choose_runtime_default_model_id,
    recommend_model_ids,
)
from ima_runtime.shared.task_creation import (
    VirtualParamCombinationError,
    VirtualParamIncompleteError,
    VirtualParamMappingError,
    VirtualParamResolutionError,
)
from ima_runtime.shared.types import (
    ClarificationRequest,
    ExecutionResult,
    GatewayRequest,
    MediaSource,
    TaskSpec,
    WorkflowExecutionResult,
    WorkflowPlanDraft,
    WorkflowStepDraft,
)


CAPABILITY_ORDER = ("image", "video", "audio")


def _status_writer(status_stream):
    return lambda message: print(message, file=status_stream, flush=True)


def _print_virtual_param_error(exc: VirtualParamResolutionError) -> None:
    if isinstance(exc, VirtualParamIncompleteError):
        provided = ", ".join(f"{key}={value}" for key, value in exc.provided_values.items()) or "<none>"
        missing = ", ".join(exc.missing_ui_fields) or "<none>"
        print(
            f"❌ `{exc.field}` 需要一组完整的 UI 参数组合。\n"
            f"   已提供：{provided}\n"
            f"   缺少：{missing}",
            file=sys.stderr,
        )
        return
    if isinstance(exc, VirtualParamCombinationError):
        provided = ", ".join(f"{key}={value}" for key, value in exc.provided_values.items()) or "<none>"
        combinations = " | ".join(exc.allowed_combinations[:3]) if exc.allowed_combinations else "<none>"
        print(
            f"❌ `{exc.field}` 当前组合无效。\n"
            f"   已提供：{provided}\n"
            f"   允许组合示例：{combinations}",
            file=sys.stderr,
        )
        return
    valid_options = ", ".join(exc.allowed_ui_values)
    print(
        f"❌ `{exc.field}` 当前值无效：{exc.value}\n"
        f"   可用选项：{valid_options}",
        file=sys.stderr,
    )


def _build_video_intent_hints(task_type: str) -> dict[str, str]:
    hints = {"task_type": task_type}
    if task_type == "first_last_frame_to_video":
        hints["video_mode"] = "first_last_frame"
    elif task_type == "reference_image_to_video":
        hints["video_mode"] = "reference"
    return hints


def _build_audio_intent_hints(task_type: str) -> dict[str, str]:
    if task_type == "text_to_music":
        return {"audio_mode": "music"}
    if task_type == "text_to_speech":
        return {"audio_mode": "speech"}
    return {}


def _is_preformatted_retry_failure(exc: RuntimeError) -> bool:
    return str(exc).startswith("Task failed after ")


def _infer_capability_from_task_type(task_type: str) -> str:
    if task_type.endswith("_video"):
        return "video"
    if "image" in task_type:
        return "image"
    return "audio"


def _build_single_target_request(
    task_type: str,
    prompt: str,
    resolved_inputs: list[str],
    reference_media: tuple[MediaSource, ...],
    extra: dict,
) -> GatewayRequest:
    capability = _infer_capability_from_task_type(task_type)
    intent_hints: dict[str, str] = {}
    if capability == "video":
        intent_hints = _build_video_intent_hints(task_type)
    elif capability == "audio":
        intent_hints = _build_audio_intent_hints(task_type)

    return GatewayRequest(
        prompt=prompt,
        media_targets=(capability,),
        input_images=tuple(resolved_inputs),
        reference_media=reference_media,
        intent_hints=intent_hints,
        extra_params=extra,
    )


def _parse_json_object(raw_value: str | None, flag_name: str) -> dict:
    if not raw_value:
        return {}
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid {flag_name} JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"{flag_name} must be a JSON object")
    return decoded


def _parse_workflow_models(raw_value: str | None) -> dict[str, str]:
    decoded = _parse_json_object(raw_value, "--workflow-models")
    if not decoded:
        return {}

    invalid_keys = sorted(set(decoded) - set(CAPABILITY_ORDER))
    if invalid_keys:
        raise RuntimeError(
            "--workflow-models only supports capability keys: image, video, audio "
            f"(invalid: {', '.join(invalid_keys)})"
        )

    workflow_models: dict[str, str] = {}
    for capability, model_id in decoded.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise RuntimeError(f"--workflow-models[{capability}] must be a non-empty string model_id")
        workflow_models[str(capability)] = model_id.strip()
    return workflow_models


def _parse_reuse_outputs(raw_values: list[str] | None) -> dict[str, str]:
    reused: dict[str, str] = {}
    for raw_value in raw_values or []:
        if "=" not in raw_value:
            raise RuntimeError("--reuse-output must use the form step_id=url")
        step_id, url = raw_value.split("=", 1)
        step_id = step_id.strip()
        url = url.strip()
        if not step_id or not url:
            raise RuntimeError("--reuse-output must use the form step_id=url")
        reused[step_id] = url
    return reused


def _build_workflow_preview_specs(
    plan: WorkflowPlanDraft,
    request: GatewayRequest,
) -> list[tuple[WorkflowStepDraft, TaskSpec]]:
    preview_specs: list[tuple[WorkflowStepDraft, TaskSpec]] = []
    synthetic_outputs: dict[str, str] = {}

    for step in plan.steps:
        input_images = request.input_images
        if step.capability == "video":
            dependency_images = tuple(
                synthetic_outputs[dependency]
                for dependency in step.depends_on
                if dependency in synthetic_outputs
            )
            if dependency_images:
                input_images = dependency_images
            elif not input_images:
                input_images = ("workflow-image-output",)
        elif step.capability == "audio":
            input_images = ()

        step_request = GatewayRequest(
            prompt=request.prompt,
            media_targets=(step.capability,),
            input_images=input_images,
            intent_hints=request.intent_hints,
            extra_params=request.extra_params,
        )
        spec = _build_capability_task_spec(step.capability, step_request)
        preview_specs.append((step, spec))

        if step.capability == "image":
            synthetic_outputs[step.step_id] = "workflow-image-output"
        elif step.capability == "video":
            synthetic_outputs[step.step_id] = "workflow-video-output"

    return preview_specs


def _build_workflow_suggested_commands(
    *,
    plan_file: str | None,
    plan_hash: str,
    missing_requirements: list[str],
    model_requirements: dict[str, dict],
) -> list[str]:
    commands: list[str] = []
    if any("IMA_API_KEY" in requirement for requirement in missing_requirements):
        commands.append("export IMA_API_KEY=ima_xxx")

    for requirement in model_requirements.values():
        if not requirement.get("model_id"):
            commands.append(
                "python3 scripts/ima_create.py "
                f"--api-key \"$IMA_API_KEY\" --task-type {requirement['task_type']} --list-models --output-json"
            )

    if plan_file:
        commands.append(
            "python3 scripts/ima_create.py "
            f"--plan-file {plan_file} --confirm-plan-hash {plan_hash} --confirm-workflow --output-json"
        )
    else:
        commands.append(
            "Re-run with --plan-file ./ima-workflow-plan.json to save a confirmable workflow artifact."
        )

    return commands


def _resolve_workflow_credit_preview(
    *,
    task_type: str,
    model_id: str,
    base: str,
    api_key: str,
    language: str,
    get_product_list_fn,
    find_model_version_fn,
    extract_model_params_fn,
    logger,
) -> dict | None:
    try:
        tree = get_product_list_fn(base, api_key, task_type, language=language)
        node = find_model_version_fn(tree, model_id, None)
        if not node:
            return None
        model_params = extract_model_params_fn(node)
    except Exception as exc:
        logger.error(
            "Workflow credit preview failed: task_type=%s, model_id=%s, error=%s",
            task_type,
            model_id,
            exc,
        )
        return None

    return {
        "model_id": model_params["model_id"],
        "model_name": model_params["model_name"],
        "credit": model_params["credit"],
        "attribute_id": model_params["attribute_id"],
    }


def _build_workflow_plan_payload(
    *,
    plan: WorkflowPlanDraft,
    request: GatewayRequest,
    workflow_models: dict[str, str],
    user_id: str,
    api_key_present: bool,
    base: str,
    api_key: str | None,
    language: str,
    get_preferred_model_id_fn,
    get_product_list_fn,
    list_all_models_fn,
    find_model_version_fn,
    extract_model_params_fn,
    logger,
    plan_file: str | None,
) -> dict:
    preview_specs = _build_workflow_preview_specs(plan, request)
    steps_payload = []
    model_requirements: dict[str, dict] = {}
    missing_requirements: list[str] = []
    credit_preview_steps: dict[str, dict] = {}
    total_credit = 0

    if not api_key_present:
        missing_requirements.append("IMA_API_KEY is required to execute the workflow.")

    for step, spec in preview_specs:
        steps_payload.append(
            {
                "step_id": step.step_id,
                "capability": step.capability,
                "task_type": spec.task_type,
                "goal": step.goal,
                "depends_on": list(step.depends_on),
            }
        )

        model_id = workflow_models.get(step.capability)
        source = "workflow_models" if model_id else ""
        recommended_model_ids: list[str] = []
        if not model_id:
            model_id = get_preferred_model_id_fn(user_id, spec.task_type)
            source = "saved_preference" if model_id else "missing"
        if not model_id and api_key:
            try:
                tree = get_product_list_fn(base, api_key, spec.task_type, language=language)
                available_models = list_all_models_fn(tree, spec.task_type)
                model_id = choose_runtime_default_model_id(spec.task_type, available_models)
                if model_id:
                    source = "runtime_single_candidate"
                else:
                    recommended_model_ids = recommend_model_ids(spec.task_type, available_models)
            except Exception as exc:
                logger.error(
                    "Workflow model recommendation failed: step_id=%s, task_type=%s, error=%s",
                    step.step_id,
                    spec.task_type,
                    exc,
                )
        if not model_id:
            recommendation_suffix = ""
            if recommended_model_ids:
                recommendation_suffix = " Recommended model_ids: " + ", ".join(recommended_model_ids) + "."
            missing_requirements.append(
                f"Workflow step {step.step_id} ({spec.task_type}) needs a model_id via --workflow-models or saved preference."
                + recommendation_suffix
            )

        model_requirements[step.step_id] = {
            "capability": step.capability,
            "task_type": spec.task_type,
            "model_id": model_id or None,
            "source": source,
            "recommended_model_ids": recommended_model_ids,
        }

        if model_id and api_key:
            preview = _resolve_workflow_credit_preview(
                task_type=spec.task_type,
                model_id=model_id,
                base=base,
                api_key=api_key,
                language=language,
                get_product_list_fn=get_product_list_fn,
                find_model_version_fn=find_model_version_fn,
                extract_model_params_fn=extract_model_params_fn,
                logger=logger,
            )
            if preview is not None:
                credit_preview_steps[step.step_id] = preview
                total_credit += int(preview["credit"])

    payload = build_confirmable_plan_payload(
        plan=plan,
        request=request,
        steps_payload=steps_payload,
        model_requirements=model_requirements,
        missing_requirements=missing_requirements,
        credit_preview={
            "steps": credit_preview_steps,
            "total_credit": total_credit,
        },
        suggested_commands=[],
    )
    payload["suggested_commands"] = _build_workflow_suggested_commands(
        plan_file=plan_file,
        plan_hash=payload["plan_hash"],
        missing_requirements=missing_requirements,
        model_requirements=model_requirements,
    )
    return payload

def _serialize_workflow_result(result: WorkflowExecutionResult) -> dict:
    return {
        "mode": "workflow_execution",
        "summary": result.summary,
        "steps": [
            {
                "step_id": step.step_id,
                "capability": step.capability,
                "task_type": step.task_type,
                "task_id": step.task_id,
                "url": step.url,
                "cover_url": step.cover_url,
                "model_id": step.model_id,
                "model_name": step.model_name,
                "depends_on": list(step.depends_on),
            }
            for step in result.steps
        ],
    }


def _print_workflow_plan(plan: WorkflowPlanDraft, stream) -> None:
    print("\n🧭 Workflow plan:", file=stream)
    print(f"   Summary: {plan.summary}", file=stream)
    for step in plan.steps:
        depends_on = ", ".join(step.depends_on) if step.depends_on else "none"
        print(
            f"   - {step.step_id}: {step.capability} | depends_on={depends_on}",
            file=stream,
        )


def _print_clarification(clarification: ClarificationRequest) -> None:
    print(f"❌ {clarification.question}", file=sys.stderr)
    if clarification.options:
        print("   选项：" + " / ".join(clarification.options), file=sys.stderr)


def _coalesce_prompt(args) -> str:
    positional_prompt = " ".join(
        str(part).strip() for part in (getattr(args, "prompt_text", None) or []) if str(part).strip()
    ).strip()
    if args.prompt and positional_prompt:
        raise RuntimeError("Use either --prompt or a positional beginner prompt, not both.")
    return args.prompt or positional_prompt


def _is_beginner_mode(args, media_targets: tuple[str, ...], reference_media: tuple[MediaSource, ...]) -> bool:
    return bool(args.prompt) and not args.task_type and not media_targets and not args.confirm_workflow and not reference_media


def _default_beginner_task_type(raw_inputs: list[str]) -> str:
    return "image_to_image" if raw_inputs else "text_to_image"


def _build_reference_media(
    *,
    raw_reference_videos: list[str],
    raw_reference_audios: list[str],
) -> tuple[MediaSource, ...]:
    items: list[MediaSource] = []
    items.extend(MediaSource(kind="video", source=value, role="reference") for value in raw_reference_videos)
    items.extend(MediaSource(kind="audio", source=value, role="reference") for value in raw_reference_audios)
    return tuple(items)


def _print_workflow_list(workflows: list[dict], stream) -> None:
    if not workflows:
        print("🗂️ No saved workflows found.", file=stream)
        return
    print("🗂️ Saved workflows:", file=stream)
    print(f"{'Plan ID':<18} {'Status':<10} {'Progress':<8} Summary", file=stream)
    print("─" * 80, file=stream)
    for workflow in workflows:
        print(
            f"{workflow['plan_id']:<18} {workflow['status']:<10} {workflow['progress']:<8} {workflow['summary']}",
            file=stream,
        )


def _resolve_task_inputs(
    raw_inputs: list[str],
    api_key: str,
    prepare_image_url_fn,
    logger,
    status_stream,
) -> list[str]:
    resolved_inputs: list[str] = []
    for source in raw_inputs:
        if source.startswith("https://") or source.startswith("http://"):
            resolved_inputs.append(source)
            continue

        print(
            f"📤 Uploading local image: {os.path.basename(source)}",
            file=status_stream,
            flush=True,
        )
        try:
            cdn_url = prepare_image_url_fn(source, api_key)
            resolved_inputs.append(cdn_url)
            print(f"   ✅ Uploaded → {cdn_url}", file=status_stream, flush=True)
        except Exception as exc:
            logger.error("Image upload failed: %s — %s", source, exc)
            print(f"❌ Failed to upload image {source}: {exc}", file=sys.stderr)
            sys.exit(1)

    return resolved_inputs


def _build_capability_task_spec(capability: str, request: GatewayRequest) -> TaskSpec:
    if capability == "video":
        routed = build_video_task_spec(request)
    elif capability == "image":
        routed = build_image_task_spec(request)
    else:
        routed = build_audio_task_spec(request)

    if isinstance(routed, ClarificationRequest):
        raise RuntimeError(json.dumps({"question": routed.question, "options": list(routed.options)}, ensure_ascii=False))
    return routed


def _rebuild_task_spec(spec: TaskSpec, extra_params: dict) -> TaskSpec:
    return TaskSpec(
        capability=spec.capability,
        task_type=spec.task_type,
        prompt=spec.prompt,
        input_images=spec.input_images,
        reference_media=spec.reference_media,
        extra_params=extra_params,
    )


def _execute_capability_task(
    *,
    capability: str,
    base: str,
    api_key: str,
    spec: TaskSpec,
    model_params: dict,
    json_output_mode: bool,
    status_stream,
    extract_error_info_fn,
    build_contextual_diagnosis_fn,
    format_user_failure_message_fn,
    logger,
) -> ExecutionResult:
    if capability == "video":
        binding = build_video_model_binding(model_params)
        executor = execute_video_task
    elif capability == "image":
        binding = build_image_model_binding(model_params)
        executor = execute_image_task
    else:
        binding = build_audio_model_binding(model_params)
        executor = execute_audio_task

    print("\n🚀 Creating task…", file=status_stream, flush=True)
    try:
        execution_context = (
            contextlib.redirect_stdout(status_stream)
            if json_output_mode
            else contextlib.nullcontext()
        )
        with execution_context:
            result = executor(
                base,
                api_key,
                spec,
                binding,
                logger=logger,
                status_writer=_status_writer(status_stream),
            )
    except VirtualParamResolutionError as exc:
        _print_virtual_param_error(exc)
        sys.exit(1)
    except RuntimeError as exc:
        logger.error("%s execution failed: %s", capability.capitalize(), str(exc))
        if _is_preformatted_retry_failure(exc):
            print("\n❌ " + str(exc), file=sys.stderr)
            sys.exit(1)
        error_info = extract_error_info_fn(exc)
        diagnosis = build_contextual_diagnosis_fn(
            error_info=error_info,
            task_type=spec.task_type,
            model_params=model_params,
            current_params=dict(spec.extra_params) if spec.extra_params else {},
            input_images=list(spec.input_images),
            credit_rules=model_params.get("all_credit_rules", []),
        )
        logger.error(
            "%s execution contextual diagnosis: %s",
            capability.capitalize(),
            json.dumps(diagnosis, ensure_ascii=False),
        )
        print(
            "\n❌ " + format_user_failure_message_fn(diagnosis=diagnosis, attempts_used=1, max_attempts=1),
            file=sys.stderr,
        )
        sys.exit(1)
    except TimeoutError as exc:
        logger.error("%s execution failed: %s", capability.capitalize(), str(exc))
        error_info = extract_error_info_fn(exc)
        diagnosis = build_contextual_diagnosis_fn(
            error_info=error_info,
            task_type=spec.task_type,
            model_params=model_params,
            current_params=dict(spec.extra_params) if spec.extra_params else {},
            input_images=list(spec.input_images),
            credit_rules=model_params.get("all_credit_rules", []),
        )
        logger.error(
            "%s execution contextual diagnosis: %s",
            capability.capitalize(),
            json.dumps(diagnosis, ensure_ascii=False),
        )
        print(
            "\n❌ " + format_user_failure_message_fn(diagnosis=diagnosis, attempts_used=1, max_attempts=1),
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"✅ Task created: {result.task_id}", file=status_stream, flush=True)
    return result


def _run_single_task_mode(
    *,
    args,
    beginner_mode: bool,
    logger,
    base: str,
    api_key: str,
    raw_extra: dict,
    raw_inputs: list[str],
    resolved_inputs: list[str],
    reference_media: tuple[MediaSource, ...],
    json_output_mode: bool,
    status_stream,
    start_time: float,
    normalize_model_id_fn,
    get_product_list_fn,
    list_all_models_fn,
    get_preferred_model_id_fn,
    find_model_version_fn,
    extract_model_params_fn,
    sanitize_extra_params_fn,
    extract_error_info_fn,
    build_contextual_diagnosis_fn,
    format_user_failure_message_fn,
    save_pref_fn,
    print_model_summary_fn,
    prepare_image_url_fn,
) -> int:
    request = _build_single_target_request(args.task_type, args.prompt, raw_inputs, reference_media, raw_extra)
    capability = request.media_targets[0]
    try:
        spec = _build_capability_task_spec(capability, request)
    except RuntimeError as exc:
        clarification = json.loads(str(exc))
        _print_clarification(
            ClarificationRequest(
                reason="capability clarification required",
                question=clarification["question"],
                options=tuple(clarification["options"]),
            )
        )
        sys.exit(1)

    has_multimodal_reference = any(item.kind in {"video", "audio"} for item in spec.reference_media)
    try:
        model_params = _resolve_model_params_for_task(
            task_type=spec.task_type,
            explicit_model_id=args.model_id,
            version_id=args.version_id,
            base=base,
            api_key=api_key,
            language=args.language,
            user_id=args.user_id,
            status_stream=status_stream,
            json_output_mode=json_output_mode,
            normalize_model_id_fn=normalize_model_id_fn,
            get_product_list_fn=get_product_list_fn,
            list_all_models_fn=list_all_models_fn,
            get_preferred_model_id_fn=get_preferred_model_id_fn,
            find_model_version_fn=find_model_version_fn,
            extract_model_params_fn=extract_model_params_fn,
            sanitize_extra_params_fn=sanitize_extra_params_fn,
            print_model_summary_fn=print_model_summary_fn,
            logger=logger,
            allow_recommended_default=beginner_mode,
            allow_saved_preference=not has_multimodal_reference,
            model_selection_context=(
                "Requests that include reference video/audio need an explicit compatible model choice from the live catalog."
                if has_multimodal_reference and not args.model_id
                else None
            ),
            raw_extra=raw_extra,
            reference_media=spec.reference_media,
        )
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        extra, dropped_extra = sanitize_extra_params_fn(raw_extra, model_params, spec.task_type)
    except VirtualParamResolutionError as exc:
        _print_virtual_param_error(exc)
        sys.exit(1)
    if dropped_extra:
        dropped_keys = ", ".join(sorted(dropped_extra.keys()))
        print(
            f"⚠️ Ignored unsupported extra params for this model: {dropped_keys}",
            file=status_stream,
            flush=True,
        )
    is_seedance_extended = capability == "video" and (
        model_params.get("model_id") in {"ima-pro", "ima-pro-fast"}
        and spec.task_type in {"image_to_video", "first_last_frame_to_video", "reference_image_to_video"}
    )

    execution_inputs = resolved_inputs
    if is_seedance_extended:
        execution_inputs = raw_inputs
    else:
        execution_inputs = _resolve_task_inputs(
            raw_inputs=raw_inputs,
            api_key=api_key,
            prepare_image_url_fn=prepare_image_url_fn,
            logger=logger,
            status_stream=status_stream,
        )
    spec = _rebuild_task_spec(spec, extra)
    if execution_inputs != list(spec.input_images):
        spec = TaskSpec(
            capability=spec.capability,
            task_type=spec.task_type,
            prompt=spec.prompt,
            input_images=tuple(execution_inputs),
            reference_media=spec.reference_media,
            extra_params=spec.extra_params,
        )

    result = _execute_capability_task(
        capability=capability,
        base=base,
        api_key=api_key,
        spec=spec,
        model_params=model_params,
        json_output_mode=json_output_mode,
        status_stream=status_stream,
        extract_error_info_fn=extract_error_info_fn,
        build_contextual_diagnosis_fn=build_contextual_diagnosis_fn,
        format_user_failure_message_fn=format_user_failure_message_fn,
        logger=logger,
    )

    if args.remember_model:
        save_pref_fn(args.user_id, spec.task_type, model_params)
        print(
            "💾 Saved model preference (--remember-model enabled).",
            file=status_stream,
            flush=True,
        )

    print("\n✅ Generation complete!", file=status_stream)
    print(f"   URL:   {result.url}", file=status_stream)
    if result.cover_url:
        print(f"   Cover: {result.cover_url}", file=status_stream)

    if json_output_mode:
        output = {
            "task_id": result.task_id,
            "url": result.url,
            "cover_url": result.cover_url,
            "model_id": result.model_id,
            "model_name": result.model_name,
            "credit": model_params["credit"],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    total_time = int(time.time() - start_time)
    logger.info("Script completed: total_time=%ss, task_id=%s", total_time, result.task_id)
    return 0


def _run_workflow_mode(
    *,
    args,
    logger,
    base: str,
    api_key: str | None,
    media_targets: tuple[str, ...],
    raw_extra: dict,
    resolved_inputs: list[str],
    workflow_models: dict[str, str],
    reused_outputs: dict[str, str],
    json_output_mode: bool,
    status_stream,
    start_time: float,
    normalize_model_id_fn,
    get_product_list_fn,
    list_all_models_fn,
    get_preferred_model_id_fn,
    find_model_version_fn,
    extract_model_params_fn,
    sanitize_extra_params_fn,
    extract_error_info_fn,
    build_contextual_diagnosis_fn,
    format_user_failure_message_fn,
    save_pref_fn,
    print_model_summary_fn,
) -> int:
    request: GatewayRequest
    plan: WorkflowPlanDraft
    plan_payload: dict

    if args.confirm_workflow:
        if args.media_targets or args.prompt or resolved_inputs or args.audio_mode or raw_extra:
            print(
                "❌ Confirmed workflow execution loads request state from --plan-file. "
                "Do not pass prompt/media-targets/input-images/audio-mode/extra flags together with --confirm-workflow.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            plan_payload = load_reviewed_plan(args.plan_file, args.confirm_plan_hash)
        except RuntimeError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            sys.exit(1)
        request = request_from_dict(plan_payload.get("request") or {})
        plan = plan_from_payload(plan_payload)

        persisted_workflow_models: dict[str, str] = {}
        for requirement in (plan_payload.get("model_requirements") or {}).values():
            capability = str(requirement.get("capability") or "")
            model_id = requirement.get("model_id")
            if capability and isinstance(model_id, str) and model_id.strip():
                persisted_workflow_models[capability] = model_id.strip()
        if workflow_models:
            for capability, model_id in workflow_models.items():
                persisted_model_id = persisted_workflow_models.get(capability)
                if persisted_model_id != model_id:
                    print(
                        "❌ confirm-workflow cannot override reviewed plan model requirements. "
                        "Re-run workflow planning with the new workflow-models first.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        workflow_models = persisted_workflow_models

        unresolved = [
            requirement["task_type"]
            for requirement in (plan_payload.get("model_requirements") or {}).values()
            if not requirement.get("model_id")
        ]
        if unresolved:
            print(
                "❌ Reviewed plan still has unresolved model requirements. "
                "Re-run workflow planning with explicit workflow-models before confirmation: "
                + ", ".join(unresolved),
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"🧭 Loaded reviewed workflow plan {plan_payload.get('plan_id')} ({plan_payload.get('plan_hash')}).",
            file=status_stream,
            flush=True,
        )
    else:
        request = GatewayRequest(
            prompt=args.prompt,
            media_targets=media_targets,
            input_images=tuple(resolved_inputs),
            intent_hints={"audio_mode": args.audio_mode} if args.audio_mode else {},
            extra_params=raw_extra,
        )
        plan_or_clarification = build_confirmable_plan(request)
        if isinstance(plan_or_clarification, ClarificationRequest):
            _print_clarification(plan_or_clarification)
            sys.exit(1)

        plan = plan_or_clarification
        plan_payload = _build_workflow_plan_payload(
            plan=plan,
            request=request,
            workflow_models=workflow_models,
            user_id=args.user_id,
            api_key_present=bool(api_key),
            base=base,
            api_key=api_key,
            language=args.language,
            get_preferred_model_id_fn=get_preferred_model_id_fn,
            get_product_list_fn=get_product_list_fn,
            list_all_models_fn=list_all_models_fn,
            find_model_version_fn=find_model_version_fn,
            extract_model_params_fn=extract_model_params_fn,
            logger=logger,
            plan_file=args.plan_file,
        )
        print("🧭 Workflow plan ready.", file=status_stream, flush=True)
        _print_workflow_plan(plan, status_stream)
        plan_payload, artifact_path = persist_confirmable_plan(plan_payload, args.plan_file)
        print(f"💾 Workflow artifact saved: {artifact_path}", file=status_stream, flush=True)
        if args.plan_file:
            print(f"💾 Workflow plan saved: {args.plan_file}", file=status_stream, flush=True)

        if not args.confirm_workflow:
            if json_output_mode:
                print(json.dumps(plan_payload, ensure_ascii=False, indent=2))
            total_time = int(time.time() - start_time)
            logger.info("Workflow plan completed: total_time=%ss, steps=%s", total_time, len(plan.steps))
            return 0

    def _run_workflow_step(step_request: GatewayRequest) -> tuple[str, ExecutionResult]:
        capability = step_request.media_targets[0]
        try:
            spec = _build_capability_task_spec(capability, step_request)
        except RuntimeError as exc:
            clarification = json.loads(str(exc))
            _print_clarification(
                ClarificationRequest(
                    reason="workflow capability clarification required",
                    question=clarification["question"],
                    options=tuple(clarification["options"]),
                )
            )
            sys.exit(1)

        explicit_model_id = workflow_models.get(capability)
        try:
            model_params = _resolve_model_params_for_task(
                task_type=spec.task_type,
                explicit_model_id=explicit_model_id,
                version_id=None,
                base=base,
                api_key=api_key,
                language=args.language,
                user_id=args.user_id,
                status_stream=status_stream,
                json_output_mode=json_output_mode,
                normalize_model_id_fn=normalize_model_id_fn,
                get_product_list_fn=get_product_list_fn,
                list_all_models_fn=list_all_models_fn,
                get_preferred_model_id_fn=get_preferred_model_id_fn,
                find_model_version_fn=find_model_version_fn,
                extract_model_params_fn=extract_model_params_fn,
                sanitize_extra_params_fn=sanitize_extra_params_fn,
                print_model_summary_fn=print_model_summary_fn,
                logger=logger,
                raw_extra=raw_extra,
                reference_media=spec.reference_media,
            )
        except RuntimeError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            sys.exit(1)

        try:
            extra, dropped_extra = sanitize_extra_params_fn(raw_extra, model_params, spec.task_type)
        except VirtualParamResolutionError as exc:
            _print_virtual_param_error(exc)
            sys.exit(1)
        if dropped_extra:
            dropped_keys = ", ".join(sorted(dropped_extra.keys()))
            print(
                f"⚠️ Ignored unsupported extra params for this model: {dropped_keys}",
                file=status_stream,
                flush=True,
            )
        spec = _rebuild_task_spec(spec, extra)

        result = _execute_capability_task(
            capability=capability,
            base=base,
            api_key=api_key,
            spec=spec,
            model_params=model_params,
            json_output_mode=json_output_mode,
            status_stream=status_stream,
            extract_error_info_fn=extract_error_info_fn,
            build_contextual_diagnosis_fn=build_contextual_diagnosis_fn,
            format_user_failure_message_fn=format_user_failure_message_fn,
            logger=logger,
        )

        if args.remember_model:
            save_pref_fn(args.user_id, spec.task_type, model_params)
            print(
                f"💾 Saved model preference for workflow step {spec.task_type}.",
                file=status_stream,
                flush=True,
            )

        return spec.task_type, result

    if args.resume_from_step:
        print(f"\n🔁 Resuming workflow from step {args.resume_from_step}.", file=status_stream, flush=True)
    print("\n✅ Confirmed workflow execution.", file=status_stream, flush=True)
    try:
        workflow_result = execute_confirmed_workflow(
            plan=plan,
            request=request,
            registry={capability: _run_workflow_step for capability in CAPABILITY_ORDER if capability in request.media_targets},
            resume_from_step=args.resume_from_step,
            reused_outputs=reused_outputs,
        )
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n✅ Workflow execution complete!", file=status_stream)
    for step in workflow_result.steps:
        print(f"   {step.step_id}: {step.url}", file=status_stream)

    if json_output_mode:
        execution_payload = _serialize_workflow_result(workflow_result)
        execution_payload["plan_id"] = plan_payload.get("plan_id")
        execution_payload["plan_hash"] = plan_payload.get("plan_hash")
        execution_payload["artifact_path"] = plan_payload.get("artifact_path")
        print(json.dumps(execution_payload, ensure_ascii=False, indent=2))

    artifact_path = append_execution_history(
        plan_payload,
        workflow_result,
        resume_from_step=args.resume_from_step,
        plan_file=args.plan_file,
    )
    print(f"📝 Workflow history updated: {artifact_path}", file=status_stream, flush=True)

    total_time = int(time.time() - start_time)
    logger.info("Workflow execution completed: total_time=%ss, steps=%s", total_time, len(workflow_result.steps))
    return 0


def run_cli(
    args,
    logger,
    load_bootstrap_api_key_fn,
    bootstrap_api_key_if_needed_fn,
    normalize_model_id_fn,
    get_product_list_fn,
    list_all_models_fn,
    get_preferred_model_id_fn,
    find_model_version_fn,
    extract_model_params_fn,
    sanitize_extra_params_fn,
    flatten_input_images_args_fn,
    validate_and_filter_inputs_fn,
    prepare_image_url_fn,
    create_task_with_reflection_fn,
    poll_task_fn,
    extract_error_info_fn,
    build_contextual_diagnosis_fn,
    format_user_failure_message_fn,
    save_pref_fn,
    print_model_summary_fn=print_model_summary,
) -> int:
    del create_task_with_reflection_fn, poll_task_fn

    base = args.base_url
    api_key = args.api_key or os.getenv("IMA_API_KEY") or load_bootstrap_api_key_fn()
    json_output_mode = bool(args.output_json)
    status_stream = sys.stderr if json_output_mode else sys.stdout
    raw_inputs = flatten_input_images_args_fn(args.input_images)
    raw_reference_video_groups = getattr(args, "reference_videos", [])
    raw_reference_audio_groups = getattr(args, "reference_audios", [])
    raw_reference_videos = flatten_input_images_args_fn(raw_reference_video_groups) if raw_reference_video_groups else []
    raw_reference_audios = flatten_input_images_args_fn(raw_reference_audio_groups) if raw_reference_audio_groups else []
    reference_media = _build_reference_media(
        raw_reference_videos=raw_reference_videos,
        raw_reference_audios=raw_reference_audios,
    )

    try:
        args.prompt = _coalesce_prompt(args)
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    media_targets = tuple(args.media_targets or [])
    beginner_mode = _is_beginner_mode(args, media_targets, reference_media)
    if beginner_mode:
        args.task_type = _default_beginner_task_type(raw_inputs)
        print(f"✨ 新手模式：默认使用 {args.task_type}。", file=status_stream, flush=True)
    if not args.task_type and not media_targets and reference_media:
        args.task_type = "reference_image_to_video"
        print("ℹ️  Auto-inferred task_type: reference_image_to_video (reference video/audio detected)", file=status_stream, flush=True)

    if args.task_type and args.model_id:
        args.model_id = normalize_model_id_fn(args.model_id) or args.model_id

    if getattr(args, "list_workflows", False):
        if args.task_type or media_targets or args.prompt or args.list_models or args.confirm_workflow:
            print("❌ --list-workflows cannot be combined with generation or confirmation flags.", file=sys.stderr)
            sys.exit(1)
        workflows = list_saved_workflows()
        if json_output_mode:
            print(json.dumps({"mode": "workflow_list", "workflows": workflows}, ensure_ascii=False, indent=2))
        else:
            _print_workflow_list(workflows, status_stream)
        return 0

    if args.task_type and media_targets:
        print("❌ Use either --task-type or --media-targets, not both.", file=sys.stderr)
        sys.exit(1)
    if reference_media and args.confirm_workflow:
        print("❌ --reference-videos/--reference-audios cannot be used with --confirm-workflow.", file=sys.stderr)
        sys.exit(1)
    if reference_media and args.task_type and args.task_type != "reference_image_to_video":
        print("❌ --reference-videos/--reference-audios only support task_type=reference_image_to_video.", file=sys.stderr)
        sys.exit(1)
    if not args.confirm_workflow and not args.task_type and not media_targets:
        print("❌ One of --task-type or --media-targets is required.", file=sys.stderr)
        sys.exit(1)
    if args.list_models and not args.task_type:
        print("❌ --list-models requires --task-type.", file=sys.stderr)
        sys.exit(1)
    if media_targets and len(media_targets) < 2:
        print("❌ --media-targets requires at least two targets. Use --task-type for single-task mode.", file=sys.stderr)
        sys.exit(1)
    if args.confirm_workflow and not media_targets:
        if not args.plan_file:
            print("❌ --confirm-workflow requires --plan-file.", file=sys.stderr)
            sys.exit(1)
    if args.confirm_workflow and not args.confirm_plan_hash:
        print("❌ --confirm-workflow requires --confirm-plan-hash.", file=sys.stderr)
        sys.exit(1)
    if args.resume_from_step and not args.confirm_workflow:
        print("❌ --resume-from-step requires --confirm-workflow.", file=sys.stderr)
        sys.exit(1)
    if args.reuse_output and not args.confirm_workflow:
        print("❌ --reuse-output requires --confirm-workflow.", file=sys.stderr)
        sys.exit(1)

    try:
        workflow_models = _parse_workflow_models(args.workflow_models)
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        reused_outputs = _parse_reuse_outputs(args.reuse_output)
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        raw_extra = _parse_json_object(args.extra_params, "--extra-params")
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)
    if args.size:
        raw_extra["size"] = args.size

    if not args.confirm_workflow and not args.prompt and not args.list_models:
        print("❌ --prompt is required", file=sys.stderr)
        sys.exit(1)

    start_time = time.time()
    masked_key = "***"
    if api_key:
        masked_key = f"{api_key[:10]}..." if len(api_key) > 10 else "***"
    logger.info(
        "Script started: task_type=%s, media_targets=%s, model_id=%s, api_key=%s",
        args.task_type,
        media_targets,
        args.model_id or "auto",
        masked_key,
    )

    if args.list_models:
        print(f"🔍 Querying product list: category={args.task_type}", file=status_stream, flush=True)
        try:
            tree = get_product_list_fn(base, api_key, args.task_type, language=args.language)
        except Exception as exc:
            logger.error("Product list failed: %s", str(exc))
            print(f"❌ Product list failed: {exc}", file=sys.stderr)
            sys.exit(1)

        models = list_all_models_fn(tree, args.task_type)
        if json_output_mode:
            print(json.dumps(models, ensure_ascii=False, indent=2))
            sys.exit(0)

        print(f"\nAvailable models for '{args.task_type}':")
        print(f"{'Name':<28} {'model_id':<34} {'version_id':<44} {'pts':>4}  attr_id  rules")
        print("─" * 128)
        for model in models:
            print(
                f"{model['name']:<28} {model['model_id']:<34} {model['version_id']:<44} "
                f"{model['credit']:>4}  {model['attr_id']:<7} {model['rule_count']}"
            )
        sys.exit(0)

    requires_api_key = bool(args.task_type or args.list_models or args.confirm_workflow)
    requires_api_key = requires_api_key or any(
        not value.startswith("https://") and not value.startswith("http://")
        for value in raw_inputs
    )
    requires_api_key = requires_api_key or any(
        not item.source.startswith("https://") and not item.source.startswith("http://")
        for item in reference_media
    )
    if requires_api_key and not api_key:
        api_key = bootstrap_api_key_if_needed_fn(status_stream=sys.stderr)
    if requires_api_key and not api_key:
        print("❌ API key is required. Pass --api-key or set IMA_API_KEY.", file=sys.stderr)
        print("   Or run: python3 scripts/ima_create.py --bootstrap", file=sys.stderr)
        print('   Example: export IMA_API_KEY="ima_xxx"', file=sys.stderr)
        print("   Get a key: https://www.imaclaw.ai/imaclaw/apikey", file=sys.stderr)
        sys.exit(1)

    if args.task_type:
        try:
            validation_kwargs = {"warn_fn": _status_writer(status_stream)}
            if reference_media:
                validation_kwargs["extra_input_count"] = len(reference_media)
            raw_inputs = validate_and_filter_inputs_fn(
                args.task_type,
                raw_inputs,
                **validation_kwargs,
            )
        except ValueError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        raw_inputs = [value for value in raw_inputs if str(value).strip()]

    resolved_inputs: list[str] = []
    if not args.task_type:
        resolved_inputs = _resolve_task_inputs(
            raw_inputs=raw_inputs,
            api_key=api_key,
            prepare_image_url_fn=prepare_image_url_fn,
            logger=logger,
            status_stream=status_stream,
        )

    if args.task_type:
        return _run_single_task_mode(
            args=args,
            beginner_mode=beginner_mode,
            logger=logger,
            base=base,
            api_key=api_key,
            raw_extra=raw_extra,
            raw_inputs=raw_inputs,
            resolved_inputs=resolved_inputs,
            reference_media=reference_media,
            json_output_mode=json_output_mode,
            status_stream=status_stream,
            start_time=start_time,
            normalize_model_id_fn=normalize_model_id_fn,
            get_product_list_fn=get_product_list_fn,
            list_all_models_fn=list_all_models_fn,
            get_preferred_model_id_fn=get_preferred_model_id_fn,
            find_model_version_fn=find_model_version_fn,
            extract_model_params_fn=extract_model_params_fn,
            sanitize_extra_params_fn=sanitize_extra_params_fn,
            extract_error_info_fn=extract_error_info_fn,
            build_contextual_diagnosis_fn=build_contextual_diagnosis_fn,
            format_user_failure_message_fn=format_user_failure_message_fn,
            save_pref_fn=save_pref_fn,
            print_model_summary_fn=print_model_summary_fn,
            prepare_image_url_fn=prepare_image_url_fn,
        )

    return _run_workflow_mode(
        args=args,
        logger=logger,
        base=base,
        api_key=api_key,
        media_targets=media_targets,
        raw_extra=raw_extra,
        resolved_inputs=resolved_inputs,
        workflow_models=workflow_models,
        reused_outputs=reused_outputs,
        json_output_mode=json_output_mode,
        status_stream=status_stream,
        start_time=start_time,
        normalize_model_id_fn=normalize_model_id_fn,
        get_product_list_fn=get_product_list_fn,
        list_all_models_fn=list_all_models_fn,
        get_preferred_model_id_fn=get_preferred_model_id_fn,
        find_model_version_fn=find_model_version_fn,
        extract_model_params_fn=extract_model_params_fn,
        sanitize_extra_params_fn=sanitize_extra_params_fn,
        extract_error_info_fn=extract_error_info_fn,
        build_contextual_diagnosis_fn=build_contextual_diagnosis_fn,
        format_user_failure_message_fn=format_user_failure_message_fn,
        save_pref_fn=save_pref_fn,
        print_model_summary_fn=print_model_summary_fn,
    )
