from __future__ import annotations

import hashlib
import time
import uuid

import requests

from ima_runtime.shared.config import APP_ID, APP_KEY, IMA_IM_BASE


def make_headers(api_key: str, language: str = "en") -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "x-app-source": "ima_skills",
        "x_app_language": language,
    }


def _gen_sign() -> tuple[str, str, str]:
    nonce = uuid.uuid4().hex[:21]
    timestamp = str(int(time.time()))
    raw = f"{APP_ID}|{APP_KEY}|{timestamp}|{nonce}"
    sign = hashlib.sha1(raw.encode()).hexdigest().upper()
    return sign, timestamp, nonce


def request_upload_token(
    api_key: str,
    suffix: str,
    content_type: str,
    file_type: str = "picture",
) -> dict:
    sign, timestamp, nonce = _gen_sign()
    response = requests.get(
        f"{IMA_IM_BASE}/api/rest/oss/getuploadtoken",
        params={
            "appUid": api_key,
            "appId": APP_ID,
            "appKey": APP_KEY,
            "cmimToken": api_key,
            "sign": sign,
            "timestamp": timestamp,
            "nonce": nonce,
            "fService": "privite",
            "fType": file_type,
            "fSuffix": suffix,
            "fContentType": content_type,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["data"]


def upload_binary(upload_url: str, content: bytes, content_type: str) -> None:
    response = requests.put(
        upload_url,
        data=content,
        headers={"Content-Type": content_type},
        timeout=60,
    )
    response.raise_for_status()


def get_product_list_data(
    base_url: str,
    api_key: str,
    category: str,
    app: str = "ima",
    platform: str = "web",
    language: str = "en",
) -> list:
    response = requests.get(
        f"{base_url}/open/v1/product/list",
        params={"app": app, "platform": platform, "category": category},
        headers=make_headers(api_key, language),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    code = data.get("code")
    if code not in (0, 200):
        raise RuntimeError(f"Product list API error: code={code}, msg={data.get('message')}")
    return data.get("data") or []


def create_task_request(base_url: str, api_key: str, payload: dict) -> dict:
    response = requests.post(
        f"{base_url}/open/v1/tasks/create",
        json=payload,
        headers=make_headers(api_key),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_task_detail(base_url: str, api_key: str, task_id: str) -> dict:
    response = requests.post(
        f"{base_url}/open/v1/tasks/detail",
        json={"task_id": task_id},
        headers=make_headers(api_key),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
