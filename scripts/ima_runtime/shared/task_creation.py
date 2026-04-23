from __future__ import annotations

import re

from ima_runtime.capabilities.audio.params import normalize_audio_binding
from ima_runtime.capabilities.image.params import normalize_image_binding
from ima_runtime.capabilities.video.params import normalize_video_binding
from ima_runtime.shared.rule_resolution import (
    get_valid_attribute_keys,
    select_credit_rule_by_params,
)
from ima_runtime.shared.types import TaskSpec


IMAGE_TASK_TYPES = {"text_to_image", "image_to_image"}
VIDEO_TASK_TYPES = {
    "text_to_video",
    "image_to_video",
    "first_last_frame_to_video",
    "reference_image_to_video",
}
AUDIO_TASK_TYPES = {"text_to_music", "text_to_speech"}


class VirtualParamResolutionError(ValueError):
    """Base error for virtual UI parameter resolution failures."""


class VirtualParamMappingError(VirtualParamResolutionError):
    def __init__(self, field: str, value: object, allowed_ui_values: list[str]) -> None:
        self.field = field
        self.value = value
        self.allowed_ui_values = allowed_ui_values
        joined = ", ".join(allowed_ui_values) if allowed_ui_values else "<none>"
        super().__init__(
            f"Unsupported value for virtual field '{field}': {value}. "
            f"Valid options: {joined}"
        )


class VirtualParamIncompleteError(VirtualParamResolutionError):
    def __init__(
        self,
        field: str,
        provided_values: dict[str, object],
        missing_ui_fields: list[str],
    ) -> None:
        self.field = field
        self.provided_values = provided_values
        self.missing_ui_fields = missing_ui_fields
        provided = ", ".join(f"{key}={value}" for key, value in provided_values.items()) or "<none>"
        missing = ", ".join(missing_ui_fields) or "<none>"
        super().__init__(
            f"Incomplete virtual field group '{field}': provided {provided}; missing {missing}."
        )


class VirtualParamCombinationError(VirtualParamResolutionError):
    def __init__(
        self,
        field: str,
        provided_values: dict[str, object],
        allowed_combinations: list[str],
    ) -> None:
        self.field = field
        self.provided_values = provided_values
        self.allowed_combinations = allowed_combinations
        provided = ", ".join(f"{key}={value}" for key, value in provided_values.items()) or "<none>"
        combos = "; ".join(allowed_combinations) if allowed_combinations else "<none>"
        super().__init__(
            f"Unsupported virtual field combination for '{field}': {provided}. "
            f"Allowed combinations: {combos}"
        )


def _normalize_backend_param_value(key: str, value: object) -> object:
    if key == "size" and isinstance(value, str):
        return value.replace("×", "x")
    return value


def _resolve_virtual_overrides(extra_params: dict | None, model_params: dict) -> dict:
    if not extra_params:
        return {}

    resolved = dict(extra_params)
    virtual_mappings = model_params.get("virtual_mappings") or {}

    for ui_field, mapping in virtual_mappings.items():
        if ui_field not in resolved:
            continue

        target_param = mapping.get("target_param") or mapping.get("field") or ui_field
        if target_param in resolved and target_param != ui_field:
            resolved.pop(ui_field, None)
            continue

        mapping_rules = mapping.get("mapping_rules") or {}
        mapped_value = mapping_rules.get(str(resolved[ui_field]))
        if mapped_value is None:
            mapped_value = mapping_rules.get(str(resolved[ui_field]).strip().lower())
        if mapped_value is None:
            raise VirtualParamMappingError(
                ui_field,
                resolved[ui_field],
                list(mapping.get("allowed_ui_values") or []),
            )

        resolved[target_param] = _normalize_backend_param_value(target_param, mapped_value)
        if target_param != ui_field:
            resolved.pop(ui_field, None)

    return resolved


def sanitize_extra_params(extra_params: dict, model_params: dict, task_type: str) -> tuple[dict, dict]:
    spec = TaskSpec(capability="video", task_type=task_type, prompt="", extra_params=extra_params or {})

    if task_type in VIDEO_TASK_TYPES:
        return normalize_video_binding(spec, model_params)
    if task_type in IMAGE_TASK_TYPES:
        return normalize_image_binding(
            TaskSpec(capability="image", task_type=task_type, prompt="", extra_params=extra_params or {}),
            model_params,
        )
    if task_type in AUDIO_TASK_TYPES:
        return normalize_audio_binding(
            TaskSpec(capability="audio", task_type=task_type, prompt="", extra_params=extra_params or {}),
            model_params,
        )

    if not extra_params:
        return {}, {}

    form_keys = set(model_params.get("form_fields") or ())
    form_keys.update((model_params.get("form_params") or {}).keys())
    rule_keys = get_valid_attribute_keys(model_params.get("all_credit_rules", []), task_type)
    virtual_ui_keys = set((model_params.get("virtual_mappings") or {}).keys())
    always_allow = {
        "n",
        "model",
        "size",
        "resolution",
        "duration",
        "quality",
        "aspect_ratio",
        "voice_id",
        "voice_type",
        "speed",
        "pitch",
        "volume",
        "lyrics",
        "genre",
        "mood",
        "sound",
        "mode",
        "generate_audio",
        "prompt_optimizer",
        "fast_pretreatment",
    }
    allowed = form_keys | rule_keys | virtual_ui_keys | always_allow

    sanitized: dict = {}
    dropped: dict = {}
    for key, value in extra_params.items():
        if key in allowed:
            sanitized[key] = value
        else:
            dropped[key] = value

    return _resolve_virtual_overrides(sanitized, model_params), dropped


def build_create_payload(
    task_type: str,
    model_params: dict,
    prompt: str,
    input_images: list[str] | None = None,
    extra_params: dict | None = None,
    src_image: list[dict] | None = None,
    src_video: list[dict] | None = None,
    src_audio: list[dict] | None = None,
) -> tuple[dict, int, int, dict]:
    if input_images is None:
        input_images = []

    resolved_extra_params = _resolve_virtual_overrides(extra_params, model_params)

    all_rules = model_params.get("all_credit_rules", [])
    normalized_rule_params: dict = {}

    if all_rules:
        merged_params = {**model_params["form_params"], **resolved_extra_params}
        valid_keys = get_valid_attribute_keys(all_rules, task_type)
        candidate_params = {key: value for key, value in merged_params.items() if key in valid_keys}

        if candidate_params:
            selected_rule = select_credit_rule_by_params(all_rules, candidate_params)
            if selected_rule:
                attribute_id = selected_rule.get("attribute_id", model_params["attribute_id"])
                credit = selected_rule.get("points", model_params["credit"])
                rule_attrs = selected_rule.get("attributes", {})
                for key in valid_keys:
                    if key in rule_attrs:
                        normalized_rule_params[key] = rule_attrs[key]
            else:
                attribute_id = model_params["attribute_id"]
                credit = model_params["credit"]
        else:
            attribute_id = model_params["attribute_id"]
            credit = model_params["credit"]
    else:
        attribute_id = model_params["attribute_id"]
        credit = model_params["credit"]

    inner: dict = {}
    inner.update(model_params["form_params"])

    rule_attrs = {
        key: value
        for key, value in (model_params.get("rule_attributes") or {}).items()
        if not (key == "default" and value == "enabled")
    }
    if rule_attrs:
        inner.update(rule_attrs)

    if normalized_rule_params:
        inner.update(
            {
                key: value
                for key, value in normalized_rule_params.items()
                if not (key == "default" and value == "enabled")
            }
        )

    if resolved_extra_params:
        for key, value in resolved_extra_params.items():
            if key not in normalized_rule_params:
                inner[key] = value

    inner["prompt"] = prompt
    inner["n"] = int(inner.get("n", 1))
    inner["input_images"] = input_images
    inner["cast"] = {"points": credit, "attribute_id": attribute_id}

    if "model" in model_params.get("form_params", {}):
        inner["model"] = model_params["form_params"]["model"]
    if resolved_extra_params and "model" in resolved_extra_params:
        inner["model"] = resolved_extra_params["model"]

    if model_params.get("model_id") == "pixverse" and "model" not in inner:
        model_name = model_params.get("model_name", "")
        version_match = re.search(r"V(\d+(?:\.\d+)?)", model_name, re.IGNORECASE)
        if version_match:
            inner["model"] = f"v{version_match.group(1)}"

    inner.pop("default", None)

    payload = {
        "task_type": task_type,
        "enable_multi_model": False,
        "src_img_url": [item["url"] for item in (src_image or []) if item.get("url")] if src_image else input_images,
        "parameters": [
            {
                "attribute_id": attribute_id,
                "model_id": model_params.get("model_id_raw") or model_params["model_id"],
                "model_name": model_params["model_name"],
                "model_version": model_params["model_version"],
                "app": "ima",
                "platform": "web",
                "category": task_type,
                "credit": credit,
                "parameters": inner,
            }
        ],
    }
    if src_image:
        payload["src_image"] = src_image
    if src_video:
        payload["src_video"] = src_video
    if src_audio:
        payload["src_audio"] = src_audio

    return payload, attribute_id, credit, normalized_rule_params


__all__ = [
    "VirtualParamResolutionError",
    "VirtualParamMappingError",
    "VirtualParamIncompleteError",
    "VirtualParamCombinationError",
    "sanitize_extra_params",
    "build_create_payload",
]
