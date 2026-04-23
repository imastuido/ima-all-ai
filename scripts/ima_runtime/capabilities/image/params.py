from __future__ import annotations

from ima_runtime.shared.rule_resolution import get_valid_attribute_keys
from ima_runtime.shared.types import ModelBinding, TaskSpec


IMAGE_ALLOWED_PARAMS = {
    "n",
    "model",
    "size",
    "resolution",
    "quality",
    "aspect_ratio",
    "mode",
    "prompt_optimizer",
}


def _normalize_backend_param_value(key: str, value: object) -> object:
    if key == "size" and isinstance(value, str):
        return value.replace("×", "x")
    return value


def _normalize_virtual_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).strip().lower()


def _render_allowed_group_combinations(group: dict) -> list[str]:
    combinations: list[str] = []
    ui_fields = list(group.get("ui_fields") or [])
    target_param = group.get("target_param") or group.get("field")
    for rule in group.get("mapping_rules") or []:
        source_values = rule.get("source_values") or {}
        parts = [f"{field}={source_values.get(field)}" for field in ui_fields if field in source_values]
        combinations.append(", ".join(parts) + f" -> {target_param}={rule.get('target_value')}")
    return combinations


def _resolve_virtual_overrides(extra_params: dict | None, model_params: dict) -> dict:
    if not extra_params:
        return {}

    resolved = dict(extra_params)
    virtual_groups = model_params.get("virtual_groups") or []
    virtual_mappings = model_params.get("virtual_mappings") or {}
    grouped_ui_fields: set[str] = set()

    for group in virtual_groups:
        ui_fields = [field for field in (group.get("ui_fields") or []) if field]
        if len(ui_fields) <= 1:
            continue

        present_ui_fields = [field for field in ui_fields if field in resolved]
        if not present_ui_fields:
            continue

        grouped_ui_fields.update(ui_fields)
        target_param = group.get("target_param") or group.get("field") or ui_fields[0]
        if target_param in resolved and target_param not in ui_fields:
            for ui_field in ui_fields:
                resolved.pop(ui_field, None)
            continue

        if len(present_ui_fields) != len(ui_fields):
            from ima_runtime.shared.task_creation import VirtualParamIncompleteError

            raise VirtualParamIncompleteError(
                str(group.get("field") or target_param),
                {field: resolved[field] for field in present_ui_fields},
                [field for field in ui_fields if field not in resolved],
            )

        patch = {field: resolved[field] for field in ui_fields}
        matched_target_value = None
        for rule in group.get("mapping_rules") or []:
            source_values = rule.get("source_values") or {}
            if all(
                _normalize_virtual_value(patch.get(field)) == _normalize_virtual_value(source_values.get(field))
                for field in ui_fields
            ):
                matched_target_value = rule.get("target_value")
                break

        if matched_target_value is None:
            from ima_runtime.shared.task_creation import VirtualParamCombinationError

            raise VirtualParamCombinationError(
                str(group.get("field") or target_param),
                patch,
                _render_allowed_group_combinations(group),
            )

        for ui_field in ui_fields:
            if ui_field != target_param:
                resolved.pop(ui_field, None)
        resolved[target_param] = _normalize_backend_param_value(target_param, matched_target_value)

    for ui_field, mapping in virtual_mappings.items():
        if ui_field in grouped_ui_fields:
            continue
        if ui_field not in resolved:
            continue

        target_param = mapping.get("target_param") or mapping.get("field") or ui_field
        if target_param in resolved and target_param != ui_field:
            resolved.pop(ui_field, None)
            continue

        mapping_rules = mapping.get("mapping_rules") or {}
        mapped_value = mapping_rules.get(str(resolved[ui_field]))
        if mapped_value is None:
            mapped_value = mapping_rules.get(_normalize_virtual_value(resolved[ui_field]))
        if mapped_value is None:
            from ima_runtime.shared.task_creation import VirtualParamMappingError

            raise VirtualParamMappingError(
                ui_field,
                resolved[ui_field],
                list(mapping.get("allowed_ui_values") or []),
            )

        resolved[target_param] = _normalize_backend_param_value(target_param, mapped_value)
        if target_param != ui_field:
            resolved.pop(ui_field, None)

    return resolved


def normalize_image_binding(spec: TaskSpec, model_params: dict) -> tuple[dict, dict]:
    extra_params = dict(spec.extra_params)
    if not extra_params:
        return {}, {}

    form_keys = set(model_params.get("form_fields") or ())
    form_keys.update((model_params.get("form_params") or {}).keys())
    rule_keys = get_valid_attribute_keys(model_params.get("all_credit_rules", []), spec.task_type)
    virtual_ui_keys = set((model_params.get("virtual_mappings") or {}).keys())
    allowed = form_keys | rule_keys | virtual_ui_keys | IMAGE_ALLOWED_PARAMS

    sanitized = {key: value for key, value in extra_params.items() if key in allowed}
    dropped = {key: value for key, value in extra_params.items() if key not in allowed}
    return _resolve_virtual_overrides(sanitized, model_params), dropped


def build_image_model_params(binding: ModelBinding) -> dict:
    metadata = dict(binding.candidate.metadata)
    form_params = dict(metadata.get("form_params") or binding.resolved_params)
    return {
        "model_name": binding.candidate.name,
        "model_id": binding.candidate.model_id,
        "model_id_raw": metadata.get("model_id_raw") or binding.candidate.model_id,
        "model_version": binding.candidate.version_id,
        "attribute_id": binding.attribute_id,
        "credit": binding.credit,
        "form_fields": list(metadata.get("form_fields") or sorted(form_params.keys())),
        "form_params": form_params,
        "rule_attributes": dict(metadata.get("rule_attributes") or {}),
        "all_credit_rules": list(metadata.get("all_credit_rules") or []),
        "virtual_mappings": dict(metadata.get("virtual_mappings") or {}),
        "virtual_groups": list(metadata.get("virtual_groups") or []),
    }
