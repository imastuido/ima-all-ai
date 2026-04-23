from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from ima_runtime.shared.config import PREFS_PATH
from ima_runtime.shared.rule_resolution import normalize_model_id


def load_prefs() -> dict:
    try:
        with open(PREFS_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_pref(user_id: str, task_type: str, model_params: dict) -> None:
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    prefs = load_prefs()
    key = f"user_{user_id}"
    canonical_model_id = normalize_model_id(model_params.get("model_id")) or model_params.get("model_id")
    prefs.setdefault(key, {})[task_type] = {
        "model_id": canonical_model_id,
        "model_name": model_params["model_name"],
        "credit": model_params["credit"],
        "last_used": datetime.now(timezone.utc).isoformat(),
    }
    with open(PREFS_PATH, "w", encoding="utf-8") as handle:
        json.dump(prefs, handle, ensure_ascii=False, indent=2)


def get_preferred_model_id(user_id: str, task_type: str) -> str | None:
    prefs = load_prefs()
    entry = (prefs.get(f"user_{user_id}") or {}).get(task_type)
    if not entry:
        return None
    return normalize_model_id(entry.get("model_id"))
