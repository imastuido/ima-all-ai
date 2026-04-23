from __future__ import annotations

from ima_runtime.shared.rule_resolution import normalize_model_id

_SUBSCRIPTION_GATED_MODEL_IDS = {
    "ima-pro",
}


def _canonical_model_id(model: dict) -> str | None:
    raw_model_id = model.get("model_id")
    if not isinstance(raw_model_id, str) or not raw_model_id.strip():
        return None
    return normalize_model_id(raw_model_id) or raw_model_id.strip()


def _unique_model_ids(task_type: str, models: list[dict]) -> list[str]:
    del task_type
    unique_ids: list[str] = []
    seen: set[str] = set()
    for model in models:
        canonical = _canonical_model_id(model)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        unique_ids.append(canonical)
    return unique_ids


def recommend_model_ids(task_type: str, models: list[dict], limit: int = 3) -> list[str]:
    del task_type

    def sort_key(model: dict) -> tuple[int, int, str, str]:
        canonical = _canonical_model_id(model) or ""
        subscription_bucket = 1 if canonical in _SUBSCRIPTION_GATED_MODEL_IDS else 0
        credit = int(model.get("credit") or 0)
        name = str(model.get("name") or "")
        return (
            subscription_bucket,
            credit,
            name,
        )

    ranked = sorted(models, key=sort_key)
    recommended: list[str] = []
    seen: set[str] = set()
    for model in ranked:
        canonical = _canonical_model_id(model)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        recommended.append(canonical)
        if len(recommended) >= limit:
            break
    return recommended


def choose_runtime_default_model_id(task_type: str, models: list[dict]) -> str | None:
    unique_ids = _unique_model_ids(task_type, models)
    if len(unique_ids) == 1:
        return unique_ids[0]
    return None


__all__ = [
    "choose_runtime_default_model_id",
    "recommend_model_ids",
]
