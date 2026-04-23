from __future__ import annotations

from ima_runtime.shared.catalog import list_all_models
from ima_runtime.shared.types import ModelBinding, ModelCandidate, TaskSpec


def build_video_model_candidates(product_tree: list, spec: TaskSpec) -> tuple[ModelCandidate, ...]:
    rows = list_all_models(product_tree, task_type=spec.task_type)
    return tuple(
        ModelCandidate(
            name=row["name"],
            model_id=row["model_id"],
            version_id=row["version_id"],
            metadata={"rule_count": row["rule_count"], "form_fields": row["form_fields"]},
        )
        for row in rows
    )


def build_video_model_binding(model_params: dict) -> ModelBinding:
    form_params = dict(model_params.get("form_params") or {})
    metadata = {
        "rule_count": len(model_params.get("all_credit_rules") or []),
        "form_fields": list(model_params.get("form_fields") or sorted(form_params.keys())),
        "model_id_raw": model_params.get("model_id_raw") or model_params.get("model_id", ""),
        "form_params": form_params,
        "rule_attributes": dict(model_params.get("rule_attributes") or {}),
        "all_credit_rules": list(model_params.get("all_credit_rules") or []),
        "virtual_mappings": dict(model_params.get("virtual_mappings") or {}),
        "virtual_groups": list(model_params.get("virtual_groups") or []),
    }
    return ModelBinding(
        candidate=ModelCandidate(
            name=model_params["model_name"],
            model_id=model_params["model_id"],
            version_id=model_params["model_version"],
            metadata=metadata,
        ),
        attribute_id=model_params["attribute_id"],
        credit=model_params["credit"],
        resolved_params=form_params,
    )
