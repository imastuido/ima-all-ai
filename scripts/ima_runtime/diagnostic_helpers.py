from __future__ import annotations

import re


def _normalize_compare_value(value) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).strip().upper()


def _parse_min_pixels(text: str) -> int | None:
    match = re.search(
        r"(?:at\s+least\s+(\d+)\s+pixels|pixels?\s+should\s+be\s+at\s+least\s+(\d+))",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return int(match.group(1) or match.group(2))


def _parse_size_dims(value) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"(\d{2,5})\s*[xX×]\s*(\d{2,5})", value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _format_rule_attributes(rule: dict, task_type: str, max_items: int = 4) -> str:
    attrs = rule.get("attributes") or {}
    parts: list[str] = []
    for key, value in attrs.items():
        if task_type != "text_to_speech" and key == "default" and value == "enabled":
            continue
        parts.append(f"{key}={value}")
    if not parts:
        return "<default rule>"
    return ", ".join(parts[:max_items])


def _best_rule_mismatch(credit_rules: list, merged_params: dict, task_type: str) -> dict | None:
    if not credit_rules:
        return None

    best: dict | None = None
    normalized_params = {
        str(key).strip().lower(): _normalize_compare_value(value)
        for key, value in merged_params.items()
    }

    for rule in credit_rules:
        attrs = rule.get("attributes") or {}
        if not attrs:
            continue

        missing: list[str] = []
        conflicts: list[tuple[str, str, str]] = []
        matched = 0

        for key, expected in attrs.items():
            if task_type != "text_to_speech" and key == "default" and expected == "enabled":
                continue
            normalized_key = str(key).strip().lower()
            expected_norm = _normalize_compare_value(expected)
            actual_norm = normalized_params.get(normalized_key)
            if actual_norm is None:
                missing.append(str(key))
            elif actual_norm == expected_norm:
                matched += 1
            else:
                actual_raw = merged_params.get(key, merged_params.get(normalized_key, ""))
                conflicts.append((str(key), str(actual_raw), str(expected)))

        score = matched * 3 - len(missing) * 2 - len(conflicts) * 3
        candidate = {
            "rule": rule,
            "missing": missing,
            "conflicts": conflicts,
            "matched": matched,
            "score": score,
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate

    return best

