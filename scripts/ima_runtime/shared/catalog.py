from __future__ import annotations

import logging

from ima_runtime.shared.client import get_product_list_data
from ima_runtime.shared.rule_resolution import (
    get_valid_attribute_keys,
    normalize_model_id,
    resolve_virtual_param,
    select_credit_rule_by_params,
)

logger = logging.getLogger("ima_skills")


def _build_virtual_mappings(form_config: list[dict]) -> dict[str, dict]:
    mappings: dict[str, dict] = {}
    for field in form_config or []:
        if not field.get("is_ui_virtual"):
            continue

        value_mapping = field.get("value_mapping") or {}
        target_param = value_mapping.get("target_param") or field.get("field")
        rules = value_mapping.get("mapping_rules") or []

        for ui in field.get("ui_params") or []:
            ui_field = ui.get("field")
            if not ui_field:
                continue

            ui_rules: dict[str, object] = {}
            for rule in rules:
                source_values = rule.get("source_values") or {}
                if ui_field in source_values:
                    ui_rules[str(source_values[ui_field])] = rule.get("target_value")

            mappings[ui_field] = {
                "field": field.get("field"),
                "target_param": target_param,
                "allowed_ui_values": [
                    option.get("value")
                    for option in (ui.get("options") or [])
                    if option.get("value") is not None
                ],
                "mapping_rules": ui_rules,
            }

    return mappings


def _build_virtual_groups(form_config: list[dict]) -> list[dict]:
    groups: list[dict] = []
    for field in form_config or []:
        if not field.get("is_ui_virtual"):
            continue

        ui_params = field.get("ui_params") or []
        ui_fields = [ui.get("field") for ui in ui_params if ui.get("field")]
        if not ui_fields:
            continue

        value_mapping = field.get("value_mapping") or {}
        groups.append(
            {
                "field": field.get("field"),
                "target_param": value_mapping.get("target_param") or field.get("field"),
                "ui_fields": ui_fields,
                "allowed_ui_values": {
                    ui.get("field"): [
                        option.get("value")
                        for option in (ui.get("options") or [])
                        if option.get("value") is not None
                    ]
                    for ui in ui_params
                    if ui.get("field")
                },
                "mapping_rules": list(value_mapping.get("mapping_rules") or []),
            }
        )
    return groups


def _build_virtual_discovery(form_config: list[dict]) -> tuple[list[str], dict[str, dict]]:
    mappings = _build_virtual_mappings(form_config)
    return sorted(mappings.keys()), {
        key: {
            "target_param": value["target_param"],
            "allowed_ui_values": value["allowed_ui_values"],
            "mapping_rules": value["mapping_rules"],
        }
        for key, value in mappings.items()
    }


def _collect_form_fields(form_config: list[dict]) -> list[str]:
    return sorted(
        {
            field.get("field")
            for field in form_config
            if field.get("field")
        }
    )


def get_product_list(
    base_url: str,
    api_key: str,
    category: str,
    app: str = "ima",
    platform: str = "web",
    language: str = "en",
) -> list:
    logger.info("Query product list: category=%s, app=%s, platform=%s", category, app, platform)
    products = get_product_list_data(
        base_url=base_url,
        api_key=api_key,
        category=category,
        app=app,
        platform=platform,
        language=language,
    )
    logger.info("Product list retrieved successfully: %s groups found", len(products))
    return products


def find_model_version(
    product_tree: list,
    target_model_id: str,
    target_version_id: str | None = None,
) -> dict | None:
    """
    Walk the V2 tree and find a type=3 leaf node matching target_model_id.
    If target_version_id is given, match exactly; otherwise return the last
    matching version, which is usually the newest.
    """
    candidates = []
    canonical_target_model_id = normalize_model_id(target_model_id) or target_model_id

    def walk(nodes: list) -> None:
        for node in nodes:
            if node.get("type") == "3":
                model_id = node.get("model_id", "")
                normalized_model_id = normalize_model_id(model_id) or model_id
                version_id = node.get("id", "")
                if normalized_model_id == canonical_target_model_id:
                    if target_version_id is None or version_id == target_version_id:
                        candidates.append(node)
            children = node.get("children") or []
            walk(children)

    walk(product_tree)

    if not candidates:
        logger.error(
            "Model not found: model_id=%s, version_id=%s",
            canonical_target_model_id,
            target_version_id,
        )
        return None

    selected = candidates[-1]
    logger.info(
        "Model found: %s (model_id=%s, version_id=%s)",
        selected.get("name"),
        canonical_target_model_id,
        selected.get("id"),
    )
    return selected


def list_all_models(product_tree: list, task_type: str | None = None) -> list[dict]:
    """Flatten tree to model summaries for discovery and agent-side routing."""
    result = []

    def walk(nodes: list) -> None:
        for node in nodes:
            if node.get("type") == "3":
                first_rule = (node.get("credit_rules") or [{}])[0]
                default_credit = first_rule.get("points", 0)
                default_attr_id = first_rule.get("attribute_id", 0)
                if node.get("credit_rules"):
                    try:
                        default_params = extract_model_params(node)
                    except RuntimeError:
                        default_params = None
                    else:
                        default_credit = default_params["credit"]
                        default_attr_id = default_params["attribute_id"]
                raw_model_id = node.get("model_id", "")
                canonical_model_id = normalize_model_id(raw_model_id) or raw_model_id
                form_config = node.get("form_config") or []
                form_fields = _collect_form_fields(form_config)
                virtual_fields = sorted(
                    {
                        field.get("field")
                        for field in form_config
                        if field.get("field") and field.get("is_ui_virtual")
                    }
                )
                virtual_ui_fields, virtual_mappings = _build_virtual_discovery(form_config)
                attribute_keys = sorted(
                    get_valid_attribute_keys(node.get("credit_rules") or [], task_type)
                )
                result.append(
                    {
                        "name": node.get("name", ""),
                        "model_id": canonical_model_id,
                        "raw_model_id": raw_model_id,
                        "version_id": node.get("id", ""),
                        "credit": default_credit,
                        "attr_id": default_attr_id,
                        "rule_count": len(node.get("credit_rules") or []),
                        "form_fields": form_fields,
                        "virtual_fields": virtual_fields,
                        "virtual_ui_fields": virtual_ui_fields,
                        "virtual_mappings": virtual_mappings,
                        "virtual_groups": _build_virtual_groups(form_config),
                        "attribute_keys": attribute_keys,
                    }
                )
            walk(node.get("children") or [])

    walk(product_tree)
    return result


def extract_model_params(node: dict) -> dict:
    """Extract create-task fields from a selected product-list leaf node."""
    credit_rules = node.get("credit_rules") or []
    if not credit_rules:
        raise RuntimeError(
            f"No credit_rules found for model '{node.get('model_id')}' "
            f"version '{node.get('id')}'. Cannot determine attribute_id or credit."
        )

    form_config = node.get("form_config") or []
    form_fields = _collect_form_fields(form_config)
    form_params: dict = {}
    for field in form_config:
        field_name = field.get("field")
        if not field_name:
            continue
        if field.get("is_ui_virtual", False):
            form_params.update(resolve_virtual_param(field))
        else:
            field_value = field.get("value")
            if field_value is not None:
                form_params[field_name] = field_value

    def normalize_value(value):
        if isinstance(value, bool):
            return str(value).lower()
        return str(value).strip().upper()

    normalized_form = {
        key.lower().strip(): normalize_value(value)
        for key, value in form_params.items()
    }

    selected_rule = select_credit_rule_by_params(credit_rules, form_params)
    logger.info(
        "Matched credit_rule by form_params: attribute_id=%s, attrs=%s",
        selected_rule.get("attribute_id"),
        selected_rule.get("attributes", {}),
    )

    attribute_id = selected_rule.get("attribute_id", 0)
    credit = selected_rule.get("points", 0)
    if attribute_id == 0:
        raise RuntimeError(
            f"attribute_id is 0 for model '{node.get('model_id')}'. "
            "This will cause 'Invalid product attribute' error."
        )

    rule_attributes = {
        key: value
        for key, value in (selected_rule.get("attributes") or {}).items()
        if not (key == "default" and value == "enabled")
    }
    raw_model_id = node.get("model_id", "")
    canonical_model_id = normalize_model_id(raw_model_id) or raw_model_id
    logger.info(
        "Params extracted: model=%s, raw_model=%s, attribute_id=%s, credit=%s, rule_attrs=%s fields",
        canonical_model_id,
        raw_model_id,
        attribute_id,
        credit,
        len(rule_attributes),
    )

    return {
        "attribute_id": attribute_id,
        "credit": credit,
        "model_id": canonical_model_id,
        "model_id_raw": raw_model_id,
        "model_name": node.get("name", ""),
        "model_version": node.get("id", ""),
        "form_fields": form_fields,
        "form_params": form_params,
        "rule_attributes": rule_attributes,
        "all_credit_rules": credit_rules,
        "virtual_mappings": _build_virtual_mappings(form_config),
        "virtual_groups": _build_virtual_groups(form_config),
    }
