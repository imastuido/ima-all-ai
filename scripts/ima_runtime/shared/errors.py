from __future__ import annotations

import math
import re

import requests

from ima_runtime.diagnostic_helpers import (
    _best_rule_mismatch,
    _format_rule_attributes,
    _parse_min_pixels,
    _parse_size_dims,
)
from ima_runtime.shared.config import POLL_CONFIG, VIDEO_RECORDS_URL, VIDEO_TASK_TYPES
from ima_runtime.shared.rule_resolution import (
    get_param_degradation_strategy,
    to_user_facing_model_name,
)


def extract_error_info(exception: Exception) -> dict:
    error_str = str(exception)

    if isinstance(exception, requests.HTTPError):
        try:
            response_data = exception.response.json()
            api_code = response_data.get("code")
            api_msg = response_data.get("message", "")
            if api_code not in (None, ""):
                return {
                    "code": api_code,
                    "message": api_msg or error_str,
                    "type": f"api_{api_code}",
                    "raw_response": response_data,
                }
            return {
                "code": "unknown",
                "message": api_msg or error_str,
                "type": "unknown",
                "raw_response": response_data,
            }
        except Exception:
            return {
                "code": "unknown",
                "message": error_str,
                "type": "unknown",
            }

    code_match = re.search(r"code[=:]?\s*(\d+)", error_str, re.IGNORECASE)
    if code_match:
        code = int(code_match.group(1))
        return {
            "code": code,
            "message": error_str,
            "type": f"api_{code}",
        }

    if isinstance(exception, TimeoutError):
        return {
            "code": "timeout",
            "message": error_str,
            "type": "timeout",
        }

    return {
        "code": "unknown",
        "message": error_str,
        "type": "unknown",
    }


def build_contextual_diagnosis(
    error_info: dict,
    task_type: str,
    model_params: dict,
    current_params: dict | None,
    input_images: list[str] | None,
    credit_rules: list | None,
) -> dict:
    code = error_info.get("code")
    raw_message = str(error_info.get("message") or "")
    msg_lower = raw_message.lower()

    merged_params = dict(model_params.get("form_params") or {})
    merged_params.update(current_params or {})
    media_inputs = input_images or []
    model_name = model_params.get("model_name") or "unknown_model"
    model_id = model_params.get("model_id") or "unknown_model_id"

    diagnosis = {
        "code": code,
        "confidence": "medium",
        "headline": "Model task failed with current configuration",
        "reasoning": [],
        "actions": [],
        "model_name": model_name,
        "model_id": model_id,
        "task_type": task_type,
    }

    input_required = {
        "image_to_image",
        "image_to_video",
        "first_last_frame_to_video",
        "reference_image_to_video",
    }
    if task_type in input_required and not media_inputs:
        diagnosis["confidence"] = "high"
        diagnosis["headline"] = "Missing required reference media for this task type"
        diagnosis["reasoning"].append(
            f"{task_type} requires input media, but input_images is empty."
        )
        diagnosis["actions"].append("Provide at least one URL/path via --input-images.")
        if task_type == "first_last_frame_to_video":
            diagnosis["actions"].append("Provide at least 2 frames: first and last.")
        return diagnosis

    if task_type == "first_last_frame_to_video" and 0 < len(media_inputs) < 2:
        diagnosis["confidence"] = "high"
        diagnosis["headline"] = "Insufficient frames for first_last_frame_to_video"
        diagnosis["reasoning"].append(
            f"Received {len(media_inputs)} media item(s); this mode typically needs first+last frames."
        )
        diagnosis["actions"].append("Pass two frame URLs in --input-images.")
        return diagnosis

    if code == 401 or "unauthorized" in msg_lower:
        diagnosis["confidence"] = "high"
        diagnosis["headline"] = "API key is invalid or unauthorized"
        diagnosis["actions"].append("Regenerate API key: https://www.imaclaw.ai/imaclaw/apikey")
        diagnosis["actions"].append("Retry with the new key in --api-key.")
        return diagnosis

    if code == 4014 or "requires a subscription" in msg_lower:
        diagnosis["confidence"] = "high"
        diagnosis["headline"] = "This model requires an active subscription tier"
        diagnosis["reasoning"].append(
            f"Model {model_name} ({model_id}) is gated behind a subscription requirement."
        )
        diagnosis["actions"].append("Upgrade your plan: https://www.imaclaw.ai/imaclaw/subscription")
        diagnosis["actions"].append("Then retry the same request with the upgraded account.")
        return diagnosis

    if code == 4008 or "insufficient points" in msg_lower:
        diagnosis["confidence"] = "high"
        diagnosis["headline"] = "Account points are not enough for this model request"
        diagnosis["reasoning"].append(
            f"Model {model_name} ({model_id}) charges by attribute/profile."
        )
        diagnosis["actions"].append("Top up credits: https://www.imaclaw.ai/imaclaw/subscription")
        diagnosis["actions"].append("Or switch to a lower-cost model/parameter profile.")
        return diagnosis

    min_pixels = _parse_min_pixels(raw_message)
    requested_dims = _parse_size_dims(str(merged_params.get("size") or ""))
    fallback_dims = _parse_size_dims(raw_message)
    dims = requested_dims or fallback_dims
    if min_pixels is not None and dims is not None:
        requested_pixels = dims[0] * dims[1]
        if requested_pixels < min_pixels:
            diagnosis["confidence"] = "high"
            diagnosis["headline"] = "Output size is below this model's minimum pixel requirement"
            diagnosis["reasoning"].append(
                f"Requested size {dims[0]}x{dims[1]} ({requested_pixels} px) is below required {min_pixels} px."
            )
            target = int(math.ceil(math.sqrt(min_pixels)))
            diagnosis["actions"].append(f"Increase --size to at least around {target}x{target}.")
            diagnosis["actions"].append("Then retry with the same model.")
            return diagnosis

    credit_rules = credit_rules or []
    rule_mismatch = _best_rule_mismatch(credit_rules, merged_params, task_type)
    if (
        code in (6009, 6010)
        or "invalid product attribute" in msg_lower
        or "no matching" in msg_lower
        or "attribute" in msg_lower
    ):
        diagnosis["headline"] = "Current parameter combination does not fit this model rule set"
        diagnosis["confidence"] = "high" if code in (6009, 6010) else "medium"
        diagnosis["reasoning"].append(
            f"Model {model_name} uses attribute-based rules; current overrides conflict with matched rule."
        )
        if rule_mismatch:
            if rule_mismatch["missing"]:
                diagnosis["reasoning"].append(
                    "Missing parameters for best-matching rule: "
                    + ", ".join(rule_mismatch["missing"][:4])
                )
            if rule_mismatch["conflicts"]:
                compact = ", ".join(
                    f"{key}={got} (expected {expected})"
                    for key, got, expected in rule_mismatch["conflicts"][:3]
                )
                diagnosis["reasoning"].append(f"Conflicting values: {compact}")
            diagnosis["actions"].append(
                "Use a rule-compatible profile: "
                + _format_rule_attributes(rule_mismatch["rule"], task_type)
            )
        diagnosis["actions"].append("Remove custom --extra-params and retry with defaults.")
        return diagnosis

    if code == "timeout" or "timed out" in msg_lower:
        diagnosis["confidence"] = "medium"
        diagnosis["headline"] = "Task exceeded polling timeout for current model settings"
        max_wait = (POLL_CONFIG.get(task_type) or {}).get("max_wait")
        if max_wait:
            diagnosis["reasoning"].append(f"Polling waited {max_wait}s without a ready result.")
        diagnosis["actions"].append("Retry with lower complexity (size/resolution/duration).")
        diagnosis["actions"].append("Use --list-models and choose a faster model variant.")
        if task_type in VIDEO_TASK_TYPES:
            diagnosis["actions"].append(f"Check your creation record: {VIDEO_RECORDS_URL}")
        else:
            diagnosis["actions"].append("Check task status in dashboard: https://imagent.bot")
        return diagnosis

    if code == 500 or "internal server error" in msg_lower:
        diagnosis["confidence"] = "medium"
        diagnosis["headline"] = "Backend rejected current parameter complexity"
        for key in ("size", "resolution", "duration", "quality"):
            if key in merged_params:
                fallback = get_param_degradation_strategy(key, str(merged_params[key]))
                if fallback:
                    diagnosis["actions"].append(
                        f"Try {key}={fallback[0]} (current {merged_params[key]})."
                    )
                    break
        diagnosis["actions"].append("Retry after simplifying parameters.")
        return diagnosis

    diagnosis["reasoning"].append(
        f"Model context: {to_user_facing_model_name(model_name, model_id)}, "
        f"task={task_type}, media_count={len(media_inputs)}."
    )
    if merged_params:
        focus_keys = ["size", "resolution", "duration", "quality", "mode"]
        hints = [f"{key}={merged_params[key]}" for key in focus_keys if key in merged_params]
        if hints:
            diagnosis["reasoning"].append("Active key parameters: " + ", ".join(hints))
    diagnosis["actions"].append("Retry with defaults (remove --extra-params).")
    diagnosis["actions"].append("Use --list-models to verify model and supported settings.")
    return diagnosis


def format_user_failure_message(
    diagnosis: dict,
    attempts_used: int,
    max_attempts: int,
) -> str:
    display_model = to_user_facing_model_name(
        diagnosis.get("model_name"),
        diagnosis.get("model_id"),
    )
    lines = [
        f"Task failed after {attempts_used}/{max_attempts} attempt(s).",
        f"Model: {display_model} | Task: {diagnosis.get('task_type')}",
        f"Likely cause ({diagnosis.get('confidence', 'medium')} confidence): {diagnosis.get('headline')}",
    ]

    reasoning = diagnosis.get("reasoning") or []
    if reasoning:
        lines.append("Why this diagnosis:")
        for item in reasoning[:3]:
            lines.append(f"- {item}")

    actions = diagnosis.get("actions") or []
    if actions:
        lines.append("What to do next:")
        for index, action in enumerate(actions[:4], 1):
            lines.append(f"{index}. {action}")

    code = diagnosis.get("code")
    if code not in (None, "", "unknown"):
        lines.append(f"Reference code: {code}")
    lines.append("Technical details were recorded in local logs.")
    return "\n".join(lines)
