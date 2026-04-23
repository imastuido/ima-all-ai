from __future__ import annotations

import re

from ima_runtime.rule_values import (
    get_param_degradation_strategy as _get_param_degradation_strategy,
    get_param_degradation_strategy_with_rules as _get_param_degradation_strategy_with_rules,
)
from ima_runtime.shared.config import MODEL_ID_ALIASES


def normalize_model_id(model_id: str | None) -> str | None:
    """Normalize known aliases; return original model_id when no alias applies."""
    if not model_id:
        return None
    normalized_key = re.sub(r"\s+", " ", model_id.strip().lower())
    return MODEL_ID_ALIASES.get(normalized_key, model_id.strip())


def to_user_facing_model_name(model_name: str | None, model_id: str | None) -> str:
    """Return user-facing Seedance branding when model_id belongs to Seedance family."""
    canonical = normalize_model_id(model_id)
    if canonical == "ima-pro":
        return "Seedance 2.0 (IMA Video Pro)"
    if canonical == "ima-pro-fast":
        return "Seedance 2.0 Fast (IMA Video Pro Fast)"
    return model_name or "IMA Model"


def resolve_virtual_param(field: dict) -> dict:
    """
    Handle virtual form fields (is_ui_virtual=True).

    Frontend logic (useAgentModeData.ts):
      1. Create sub-forms from ui_params (each has a default value)
      2. Build patch: {ui_param.field: ui_param.value} for each sub-param
      3. Find matching value_mapping rule where source_values == patch
      4. Use target_value as the actual API parameter value

    If is_ui_virtual is not exposed by Open API, fall through to default value.
    """
    field_name = field.get("field")
    ui_params = field.get("ui_params") or []
    value_mapping = field.get("value_mapping") or {}
    mapping_rules = value_mapping.get("mapping_rules") or []
    default_value = field.get("value")

    if not field_name:
        return {}

    if ui_params and mapping_rules:
        patch = {}
        for ui in ui_params:
            ui_field = ui.get("field") or ui.get("id", "")
            patch[ui_field] = ui.get("value")

        for rule in mapping_rules:
            source = rule.get("source_values") or {}
            if all(patch.get(k) == v for k, v in source.items()):
                return {field_name: rule.get("target_value")}

    if default_value is not None:
        return {field_name: default_value}
    return {}


def select_credit_rule_by_params(credit_rules: list, user_params: dict) -> dict | None:
    """
    Select the best credit_rule matching user parameters.

    Strategy:
    1. Try exact match: all rule attributes match user params
    2. Try best partial match
    3. Fallback to first rule
    """
    if not credit_rules:
        return None

    default_rule = next(
        (
            rule
            for rule in credit_rules
            if (rule.get("attributes") or {}).get("default") == "enabled"
        ),
        None,
    )

    if not user_params:
        return default_rule or credit_rules[0]

    def normalize_value(value):
        if isinstance(value, bool):
            return str(value).lower()
        return str(value).strip().upper()

    normalized_user = {
        key.lower().strip(): normalize_value(value)
        for key, value in user_params.items()
    }

    for rule in credit_rules:
        attrs = rule.get("attributes", {})
        if not attrs:
            continue
        if attrs.get("default") == "enabled":
            continue

        normalized_attrs = {
            key.lower().strip(): normalize_value(value)
            for key, value in attrs.items()
        }
        if all(normalized_user.get(key) == value for key, value in normalized_attrs.items()):
            return rule

    best_match = None
    best_match_count = 0
    for rule in credit_rules:
        attrs = rule.get("attributes", {})
        if not attrs:
            continue
        if attrs.get("default") == "enabled":
            continue

        normalized_attrs = {
            key.lower().strip(): normalize_value(value)
            for key, value in attrs.items()
        }
        match_count = sum(
            1
            for key, value in normalized_attrs.items()
            if normalized_user.get(key) == value
        )
        if match_count > best_match_count:
            best_match_count = match_count
            best_match = rule

    if best_match:
        return best_match

    return default_rule or credit_rules[0]


def get_valid_attribute_keys(credit_rules: list, task_type: str | None = None) -> set:
    """Extract valid attribute keys from runtime credit rules."""
    valid_keys = set()
    for rule in credit_rules:
        attrs = rule.get("attributes", {})
        for key, value in attrs.items():
            if task_type == "text_to_speech":
                valid_keys.add(key)
            elif not (key == "default" and value == "enabled"):
                valid_keys.add(key)
    return valid_keys


def get_param_degradation_strategy(param_key: str, current_value: str) -> list:
    return _get_param_degradation_strategy(param_key, current_value)


def get_param_degradation_strategy_with_rules(
    param_key: str,
    current_value: str,
    credit_rules: list | None,
) -> list:
    return _get_param_degradation_strategy_with_rules(param_key, current_value, credit_rules)


__all__ = [
    "normalize_model_id",
    "to_user_facing_model_name",
    "resolve_virtual_param",
    "select_credit_rule_by_params",
    "get_valid_attribute_keys",
    "get_param_degradation_strategy",
    "get_param_degradation_strategy_with_rules",
]
