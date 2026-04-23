from __future__ import annotations

import logging
import mimetypes
import os
from urllib.parse import unquote, urlparse

from ima_runtime.shared.client import request_upload_token, upload_binary
from ima_runtime.shared.config import INPUT_EXACT_COUNT, INPUT_REQUIRED_MIN, TEXT_ONLY_TASK_TYPES

logger = logging.getLogger("ima_skills")


def flatten_input_images_args(raw_groups) -> list[str]:
    """Merge repeated --input-images groups into one flat list."""
    flattened: list[str] = []
    for group in raw_groups or []:
        if isinstance(group, list):
            flattened.extend([str(value) for value in group if str(value).strip()])
        elif group is not None and str(group).strip():
            flattened.append(str(group))
    return flattened


def validate_and_filter_inputs(
    task_type: str,
    raw_inputs: list[str],
    warn_fn=None,
    extra_input_count: int = 0,
) -> list[str]:
    inputs = [value for value in (raw_inputs or []) if str(value).strip()]
    if not inputs:
        minimum = INPUT_REQUIRED_MIN.get(task_type, 0)
        if minimum > extra_input_count:
            raise ValueError(f"{task_type} requires at least {minimum} input image(s).")
        return []

    if task_type in TEXT_ONLY_TASK_TYPES:
        if warn_fn:
            warn_fn(f"⚠️ --input-images is ignored for {task_type}; continuing without media inputs.")
        return []

    exact = INPUT_EXACT_COUNT.get(task_type)
    if exact is not None and len(inputs) != exact:
        raise ValueError(f"{task_type} requires exactly {exact} input image(s); received {len(inputs)}.")

    minimum = INPUT_REQUIRED_MIN.get(task_type, 0)
    if minimum > 0 and len(inputs) + extra_input_count < minimum:
        raise ValueError(f"{task_type} requires at least {minimum} input image(s); received {len(inputs)}.")

    return inputs


def prepare_image_url(source: str, api_key: str) -> str:
    """Upload a local image file to IMA CDN and return its public URL."""
    if source.startswith("https://") or source.startswith("http://"):
        return source

    if source.startswith("file://"):
        parsed = urlparse(source)
        source = unquote(parsed.path)

    if not os.path.isfile(source):
        raise FileNotFoundError(f"Input image not found: {source}")

    content_type = mimetypes.guess_type(source)[0] or "image/jpeg"
    suffix = source.rsplit(".", 1)[-1].lower() if "." in source else "jpeg"

    logger.info("Uploading local image: %s (%s)", source, content_type)
    token_data = request_upload_token(api_key, suffix, content_type)
    upload_url = token_data["ful"]
    download_url = token_data["fdl"]

    with open(source, "rb") as handle:
        image_bytes = handle.read()
    upload_binary(upload_url, image_bytes, content_type)

    logger.info("Upload complete: %s", download_url)
    return download_url
