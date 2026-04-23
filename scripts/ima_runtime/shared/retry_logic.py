from __future__ import annotations

import json
import logging
from typing import Any, Callable

from ima_runtime.shared.config import VIDEO_RECORDS_URL
from ima_runtime.shared.errors import (
    build_contextual_diagnosis,
    extract_error_info,
    format_user_failure_message,
)
from ima_runtime.shared.rule_resolution import (
    get_param_degradation_strategy_with_rules,
    select_credit_rule_by_params,
)
from ima_runtime.shared.task_execution import create_task

logger = logging.getLogger("ima_skills")


def reflect_on_failure(
    error_info: dict,
    attempt: int,
    current_params: dict,
    credit_rules: list,
    model_params: dict,
    logger=logger,
) -> dict:
    code = error_info.get("code")
    error_type = error_info.get("type", "")

    logger.info("🔍 Reflection Attempt %s: analyzing error code=%s, type=%s", attempt, code, error_type)

    if code == 500:
        logger.info("Strategy: Degrade parameters due to 500 error")
        for key in ["size", "resolution", "duration", "quality"]:
            if key in current_params:
                current_val = current_params[key]
                fallbacks = get_param_degradation_strategy_with_rules(key, current_val, credit_rules)
                if fallbacks:
                    new_val = fallbacks[0]
                    new_params = current_params.copy()
                    new_params[key] = new_val
                    logger.info("  → Degrading %s: %s → %s", key, current_val, new_val)
                    return {
                        "action": "retry",
                        "new_params": new_params,
                        "reason": f"500 error with {key}='{current_val}', degrading to '{new_val}'",
                    }
        return {
            "action": "give_up",
            "suggestion": (
                f"Model '{model_params['model_name']}' returned 500 Internal Server Error. "
                "This may indicate a backend issue or unsupported parameter combination. "
                "Try a different model or contact IMA support."
            ),
        }

    if code == 6009:
        logger.info("Strategy: Add missing parameters from credit_rules (6009)")
        if credit_rules and len(credit_rules) > 0:
            min_rule = min(credit_rules, key=lambda rule: rule.get("points", 9999))
            rule_attrs = min_rule.get("attributes", {})
            if rule_attrs:
                new_params = current_params.copy()
                added = []
                for key, value in rule_attrs.items():
                    if key not in new_params:
                        new_params[key] = value
                        added.append(f"{key}={value}")
                if added:
                    logger.info("  → Adding missing params: %s", ", ".join(added))
                    return {
                        "action": "retry",
                        "new_params": new_params,
                        "reason": f"6009 error: added missing parameters {', '.join(added)} from credit_rules",
                    }
        return {
            "action": "give_up",
            "suggestion": (
                f"No matching credit rule found for parameters: {current_params}. "
                f"Model '{model_params['model_name']}' may not support this parameter combination. "
                "Try using default parameters or a different model."
            ),
        }

    if code == 6010:
        logger.info("Strategy: Reselect credit_rule based on current params (6010)")
        if credit_rules:
            selected = select_credit_rule_by_params(credit_rules, current_params)
            if selected:
                new_attr_id = selected.get("attribute_id")
                new_points = selected.get("points")
                rule_attrs = selected.get("attributes", {})
                new_params = current_params.copy()
                new_params.update(rule_attrs)
                logger.info(
                    "  → Reselected rule: attribute_id=%s, points=%s, attrs=%s",
                    new_attr_id,
                    new_points,
                    rule_attrs,
                )
                return {
                    "action": "retry",
                    "new_params": new_params,
                    "reason": f"6010 error: reselected credit_rule (attribute_id={new_attr_id}, {new_points} pts)",
                    "new_attribute_id": new_attr_id,
                    "new_credit": new_points,
                }
        return {
            "action": "give_up",
            "suggestion": (
                f"Parameter mismatch (error 6010) for model '{model_params['model_name']}'. "
                "Could not find compatible credit_rule. Try refreshing the model list or using default parameters."
            ),
        }

    if code == "timeout":
        return {
            "action": "give_up",
            "suggestion": (
                f"Task generation timed out for model '{model_params['model_name']}'. "
                "The task may still be processing in the background without explicit backend errors. "
                f"Please check your creation record at {VIDEO_RECORDS_URL}. "
                "If this model is consistently slow, consider using a faster model."
            ),
        }

    return {
        "action": "give_up",
        "suggestion": (
            f"Unexpected error (code={code}): {error_info.get('message')}. "
            f"If this persists, please report to IMA support with error code {code}."
        ),
    }


def create_task_with_reflection(
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
    max_attempts: int = 3,
    create_task_fn: Callable[..., str] | None = None,
    extract_error_info_fn: Callable[[Exception], dict] | None = None,
    build_contextual_diagnosis_fn: Callable[..., dict] | None = None,
    format_user_failure_message_fn: Callable[..., str] | None = None,
    logger=logger,
    status_writer=None,
) -> str:
    create_task_fn = create_task_fn or create_task
    extract_error_info_fn = extract_error_info_fn or extract_error_info
    build_contextual_diagnosis_fn = build_contextual_diagnosis_fn or build_contextual_diagnosis
    format_user_failure_message_fn = format_user_failure_message_fn or format_user_failure_message
    working_model_params = dict(model_params)
    current_params = extra_params.copy() if extra_params else {}
    attempt_log = []
    credit_rules = working_model_params.get("all_credit_rules", [])
    last_reflection: dict[str, Any] | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("%s", "=" * 60)
            logger.info("Attempt %s/%s: Creating task with params=%s", attempt, max_attempts, current_params)
            logger.info("%s", "=" * 60)

            if attempt > 1 and last_reflection and "new_attribute_id" in last_reflection:
                working_model_params["attribute_id"] = last_reflection["new_attribute_id"]
                working_model_params["credit"] = last_reflection["new_credit"]
                logger.info(
                    "  Using reflected attribute_id=%s, credit=%s pts",
                    last_reflection["new_attribute_id"],
                    last_reflection["new_credit"],
                )

            task_id = create_task_fn(
                base_url=base_url,
                api_key=api_key,
                task_type=task_type,
                model_params=working_model_params,
                prompt=prompt,
                input_images=input_images,
                extra_params=current_params,
                src_image=src_image,
                src_video=src_video,
                src_audio=src_audio,
                status_writer=status_writer,
            )

            if attempt > 1:
                logger.info("✅ Task created successfully after %s attempts (auto-recovery)", attempt)

            attempt_log.append(
                {
                    "attempt": attempt,
                    "result": "success",
                    "params": current_params.copy(),
                }
            )
            return task_id

        except Exception as exc:
            error_info = extract_error_info_fn(exc)
            attempt_log.append(
                {
                    "attempt": attempt,
                    "result": "failed",
                    "params": current_params.copy(),
                    "error": error_info,
                }
            )
            logger.error("❌ Attempt %s failed: %s - %s", attempt, error_info["type"], error_info["message"])

            if attempt < max_attempts:
                reflection = reflect_on_failure(
                    error_info=error_info,
                    attempt=attempt,
                    current_params=current_params,
                    credit_rules=credit_rules,
                    model_params=working_model_params,
                    logger=logger,
                )
                last_reflection = reflection

                if reflection["action"] == "retry":
                    current_params = reflection["new_params"]
                    logger.info("🔄 Reflection decision: %s", reflection["reason"])
                    logger.info("   Retrying with new params: %s", current_params)
                    continue

                logger.error("💡 Reflection suggests giving up: %s", reflection.get("suggestion"))
                diagnosis = build_contextual_diagnosis_fn(
                    error_info=error_info,
                    task_type=task_type,
                    model_params=working_model_params,
                    current_params=current_params,
                    input_images=input_images,
                    credit_rules=credit_rules,
                )
                logger.error("Contextual diagnosis (early give-up): %s", json.dumps(diagnosis, ensure_ascii=False))
                raise RuntimeError(
                    format_user_failure_message_fn(
                        diagnosis=diagnosis,
                        attempts_used=attempt,
                        max_attempts=max_attempts,
                    )
                ) from exc

            logger.error("❌ All %s attempts failed", max_attempts)
            last_error = attempt_log[-1]["error"]
            diagnosis = build_contextual_diagnosis_fn(
                error_info=last_error,
                task_type=task_type,
                model_params=working_model_params,
                current_params=current_params,
                input_images=input_images,
                credit_rules=credit_rules,
            )
            logger.error("Contextual diagnosis (max attempts): %s", json.dumps(diagnosis, ensure_ascii=False))
            logger.error("Attempt log (debug only): %s", json.dumps(attempt_log, ensure_ascii=False))
            raise RuntimeError(
                format_user_failure_message_fn(
                    diagnosis=diagnosis,
                    attempts_used=max_attempts,
                    max_attempts=max_attempts,
                )
            ) from exc


__all__ = [
    "reflect_on_failure",
    "create_task_with_reflection",
]
