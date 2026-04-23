from __future__ import annotations

import re


def _extract_rule_values(credit_rules: list, param_key: str) -> list[str]:
    values: list[str] = []
    if not credit_rules:
        return values
    for rule in credit_rules:
        attrs = rule.get("attributes") or {}
        if param_key in attrs:
            value = str(attrs[param_key]).strip()
            if value:
                values.append(value)
    return values


def _parse_size_dims(value) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"(\d{2,5})\s*[xX×]\s*(\d{2,5})", value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _value_score(param_key: str, raw_value: str) -> float:
    key = param_key.lower()
    text = str(raw_value).strip()
    upper = text.upper()

    if key == "quality":
        quality_map = {
            "LOW": 1,
            "STANDARD": 2,
            "MEDIUM": 2,
            "HIGH": 3,
            "ULTRA": 4,
            "标清": 1,
            "高清": 3,
        }
        return float(quality_map.get(upper, 0))

    if key in {"resolution", "duration"}:
        match = re.search(r"(\d+)", upper)
        if match:
            return float(int(match.group(1)))
        return 0.0

    if key == "size":
        dims = _parse_size_dims(text)
        if dims:
            return float(dims[0] * dims[1])
        match = re.search(r"(\d+(?:\.\d+)?)\s*K", upper)
        if match:
            return float(match.group(1)) * 1000
        match = re.search(r"(\d+)\s*PX", upper)
        if match:
            return float(match.group(1))
        return 0.0

    match = re.search(r"(\d+(?:\.\d+)?)", upper)
    if match:
        return float(match.group(1))
    return 0.0


def _dedupe_preserve(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip().upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(value)
    return out


def get_param_degradation_strategy_with_rules(
    param_key: str,
    current_value: str,
    credit_rules: list | None,
) -> list:
    """
    Prefer runtime rule values for degradation.
    Falls back to static maps only when runtime offers no candidates.
    """
    key = param_key.lower()
    current = str(current_value).strip()
    runtime_values = _dedupe_preserve(_extract_rule_values(credit_rules or [], param_key))

    if runtime_values:
        values = _dedupe_preserve(runtime_values + [current])
        values_sorted = sorted(values, key=lambda value: _value_score(key, value), reverse=True)
        current_norm = current.upper()
        index = next(
            (i for i, value in enumerate(values_sorted) if value.strip().upper() == current_norm),
            None,
        )
        if index is not None:
            return values_sorted[index + 1 :]
        current_score = _value_score(key, current)
        return [value for value in values_sorted if _value_score(key, value) < current_score]

    if key == "size":
        size_map = {
            "4k": ["2k", "1k", "512px"],
            "2k": ["1k", "512px"],
            "1k": ["512px"],
            "512px": [],
        }
        return size_map.get(current.lower(), [])

    if key == "resolution":
        resolution_map = {
            "1080p": ["720p", "480p"],
            "720p": ["480p"],
            "480p": [],
        }
        return resolution_map.get(current.lower(), [])

    if key == "duration":
        duration_map = {
            "10s": ["5s"],
            "5s": [],
        }
        return duration_map.get(current.lower(), [])

    if key == "quality":
        quality_map = {
            "高清": ["标清"],
            "high": ["standard", "low"],
            "standard": ["low"],
            "low": [],
        }
        return quality_map.get(current.lower(), [])

    return []


def get_param_degradation_strategy(param_key: str, current_value: str) -> list:
    """
    Get degradation sequence for a parameter when error occurs.

    Returns list of fallback values to try, from high-quality to low-quality.
    Empty list means no degradation available.
    """
    return get_param_degradation_strategy_with_rules(param_key, current_value, credit_rules=None)

