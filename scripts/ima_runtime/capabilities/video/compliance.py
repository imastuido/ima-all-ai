from __future__ import annotations

import requests


class SeedanceComplianceError(RuntimeError):
    """Raised when Seedance media compliance verification fails."""


def _verify_single_asset(base_url: str, api_key: str, asset_url: str) -> dict:
    response = requests.post(
        f"{base_url}/open/v1/assets/verify",
        json={"url": asset_url},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "x-app-source": "ima_skills",
            "x_app_language": "en",
        },
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()
    code = payload.get("code")
    if code not in (0, 200):
        raise SeedanceComplianceError(
            f"素材合规校验接口失败: code={code}, message={payload.get('message') or 'unknown'}"
        )
    return (payload.get("data") or {}).get("result") or {}


def verify_seedance_media_compliance(base_url: str, api_key: str, input_urls: tuple[str, ...] | list[str]) -> None:
    for asset_url in input_urls:
        result = _verify_single_asset(base_url, api_key, asset_url)
        status = str(result.get("status") or "").strip().lower()
        if status in {"active", "success"}:
            continue
        error_info = result.get("error") or {}
        raise SeedanceComplianceError(
            f"素材合规校验未通过: {asset_url} | status={status or '<empty>'} | "
            f"code={error_info.get('code') or ''} | message={error_info.get('message') or 'unknown'}"
        )


__all__ = [
    "SeedanceComplianceError",
    "verify_seedance_media_compliance",
]
