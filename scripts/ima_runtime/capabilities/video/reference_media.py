from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import tempfile
from pathlib import Path

from ima_runtime.shared.client import request_upload_token, upload_binary
from ima_runtime.shared.network_safety import RemoteNetworkSafetyError, open_safe_public_stream
from ima_runtime.shared.rule_resolution import normalize_model_id
from ima_runtime.shared.types import MediaSource, TaskSpec


SEEDANCE_MODEL_IDS = {"ima-pro", "ima-pro-fast"}
SEEDANCE_MEDIA_TASK_TYPES = {"image_to_video", "first_last_frame_to_video", "reference_image_to_video"}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
AUDIO_EXTENSIONS = {".mp3", ".wav"}

IMAGE_MAX_BYTES = 30 * 1024 * 1024
VIDEO_MAX_BYTES = 50 * 1024 * 1024
AUDIO_MAX_BYTES = 15 * 1024 * 1024
REQUEST_MAX_BYTES = 64 * 1024 * 1024

VIDEO_MIN_DURATION = 2.0
VIDEO_MAX_DURATION = 15.0
AUDIO_MIN_DURATION = 2.0
AUDIO_MAX_DURATION = 15.0
VIDEO_MIN_DIMENSION = 300
VIDEO_MAX_DIMENSION = 6000
IMAGE_MIN_DIMENSION = 300
IMAGE_MAX_DIMENSION = 6000
MIN_ASPECT_RATIO = 0.4
MAX_ASPECT_RATIO = 2.5
VIDEO_MIN_PIXELS = 409600
VIDEO_MAX_PIXELS = 92740800
VIDEO_MIN_FPS = 24.0
VIDEO_MAX_FPS = 60.0


class SeedanceMediaValidationError(RuntimeError):
    """Raised when Seedance media inputs fail strict preflight validation."""


def is_seedance_extended_task(model_id: str | None, task_type: str) -> bool:
    normalized = normalize_model_id(model_id) or model_id
    return bool(normalized in SEEDANCE_MODEL_IDS and task_type in SEEDANCE_MEDIA_TASK_TYPES)


def has_multimodal_reference_media(spec: TaskSpec) -> bool:
    return bool(spec.task_type == "reference_image_to_video" and any(item.kind in {"video", "audio"} for item in spec.reference_media))


def collect_seedance_media_sources(spec: TaskSpec) -> tuple[MediaSource, ...]:
    sources: list[MediaSource] = []
    if spec.task_type == "first_last_frame_to_video":
        for index, source in enumerate(spec.input_images):
            role = "first_frame" if index == 0 else "last_frame"
            sources.append(MediaSource(kind="image", source=source, role=role))
    else:
        sources.extend(MediaSource(kind="image", source=source, role="input") for source in spec.input_images)
    sources.extend(spec.reference_media)
    return tuple(sources)


def _is_remote_url(source: str) -> bool:
    return source.startswith("https://") or source.startswith("http://")


def _format_bytes(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def _guess_content_type(path: str, kind: str) -> tuple[str, str]:
    ext = Path(path).suffix.lstrip(".").lower()
    mime = mimetypes.guess_type(path)[0]
    if not ext:
        ext = {"image": "jpeg", "video": "mp4", "audio": "mp3"}[kind]
    if not mime:
        mime = {
            "image": "image/jpeg",
            "video": "video/mp4",
            "audio": "audio/mpeg",
        }[kind]
    return ext, mime


def _run_ffprobe_json_entries(file_path: str, *, entries: str, stream_selector: str | None = None) -> dict:
    cmd = ["ffprobe", "-v", "error"]
    if stream_selector:
        cmd.extend(["-select_streams", stream_selector])
    cmd.extend(["-show_entries", entries, "-of", "json", file_path])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout or "{}")


def _get_image_dimensions(file_path: str) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(file_path) as image:
            return image.size
    except ImportError:
        data = _run_ffprobe_json_entries(file_path, entries="stream=width,height", stream_selector="v:0")
        streams = data.get("streams") or []
        if not streams:
            return (0, 0)
        stream = streams[0]
        return int(stream.get("width") or 0), int(stream.get("height") or 0)


def _get_video_metadata(file_path: str) -> dict:
    format_data = _run_ffprobe_json_entries(file_path, entries="format=duration")
    stream_data = _run_ffprobe_json_entries(file_path, entries="stream=width,height,r_frame_rate", stream_selector="v:0")
    duration = float(((format_data.get("format") or {}).get("duration")) or 0.0)
    streams = stream_data.get("streams") or [{}]
    stream = streams[0] if streams else {}
    frame_rate = str(stream.get("r_frame_rate") or "0/1")
    fps = 0.0
    if "/" in frame_rate:
        numerator, denominator = frame_rate.split("/", 1)
        denominator_value = float(denominator or 0)
        fps = float(numerator or 0) / denominator_value if denominator_value else 0.0
    elif frame_rate:
        fps = float(frame_rate)
    return {
        "duration": duration,
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "fps": fps,
    }


def _get_audio_duration(file_path: str) -> float:
    data = _run_ffprobe_json_entries(file_path, entries="format=duration")
    return float(((data.get("format") or {}).get("duration")) or 0.0)


def _extract_video_cover_frame(file_path: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        output_path = temp_file.name
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", file_path, "-frames:v", "1", "-q:v", "2", output_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise RuntimeError(result.stderr.strip() or "ffmpeg cover extraction failed")
    return output_path


def _download_remote_media_to_temp(url: str, *, max_bytes: int, suffix: str = "") -> tuple[str, int]:
    try:
        with open_safe_public_stream(url, timeout=60) as response:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                total = 0
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        temp_file.close()
                        os.unlink(temp_file.name)
                        raise SeedanceMediaValidationError(
                            f"❌ 参考资源大小超限：{url}，当前值 > {_format_bytes(max_bytes)}，请压缩后重试。"
                        )
                    temp_file.write(chunk)
                return temp_file.name, total
    except RemoteNetworkSafetyError as exc:
        raise SeedanceMediaValidationError(f"❌ 参考资源地址不安全：{exc}") from exc


def _upload_local_media(path: str, api_key: str, kind: str) -> str:
    suffix, content_type = _guess_content_type(path, kind)
    file_type = {"image": "picture", "video": "video", "audio": "audio"}[kind]
    token = request_upload_token(api_key, suffix, content_type, file_type=file_type)
    with open(path, "rb") as handle:
        content = handle.read()
    upload_binary(token["ful"], content, content_type)
    return token["fdl"]


def _validate_seedance_media(probed_assets: list[dict], task_type: str) -> None:
    if not probed_assets:
        raise SeedanceMediaValidationError("❌ Seedance 视频任务至少需要 1 个素材输入。")

    issues: list[str] = []
    images = [item for item in probed_assets if item["kind"] == "image"]
    videos = [item for item in probed_assets if item["kind"] == "video"]
    audios = [item for item in probed_assets if item["kind"] == "audio"]

    if task_type in {"image_to_video", "first_last_frame_to_video"} and (videos or audios):
        issues.append("只有 reference_image_to_video 支持参考视频或参考音频。")
    if task_type == "image_to_video" and len(images) < 1:
        issues.append("image_to_video 至少需要 1 张输入图片。")
    if task_type == "first_last_frame_to_video" and len(images) != 2:
        issues.append(f"first_last_frame_to_video 需要且仅需要 2 张图片，当前为 {len(images)} 张。")
    if task_type == "reference_image_to_video" and not (images or videos or audios):
        issues.append("reference_image_to_video 至少需要 1 个图片、视频或音频参考输入。")

    if len(images) > 9:
        issues.append(f"参考图片数量超限，当前值: {len(images)}，允许范围: 0~9。")
    if len(videos) > 3:
        issues.append(f"参考视频数量超限，当前值: {len(videos)}，允许范围: 0~3。")
    if len(audios) > 3:
        issues.append(f"参考音频数量超限，当前值: {len(audios)}，允许范围: 0~3。")

    total_size = sum(int(item.get("size_bytes") or 0) for item in probed_assets)
    if total_size > REQUEST_MAX_BYTES:
        issues.append(
            f"全部参考资源总大小超限，当前值: {_format_bytes(total_size)}，允许范围: ≤ {_format_bytes(REQUEST_MAX_BYTES)}。"
        )

    total_video_duration = sum(float(item.get("duration") or 0.0) for item in videos)
    if total_video_duration > VIDEO_MAX_DURATION:
        issues.append(f"参考视频总时长超限，当前值: {total_video_duration:.2f}s，允许范围: ≤ {VIDEO_MAX_DURATION:.0f}s。")

    total_audio_duration = sum(float(item.get("duration") or 0.0) for item in audios)
    if total_audio_duration > AUDIO_MAX_DURATION:
        issues.append(f"参考音频总时长超限，当前值: {total_audio_duration:.2f}s，允许范围: ≤ {AUDIO_MAX_DURATION:.0f}s。")

    for item in images:
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        if int(item.get("size_bytes") or 0) >= IMAGE_MAX_BYTES:
            issues.append(f"图片大小超限: {item['source']}，允许范围: < {_format_bytes(IMAGE_MAX_BYTES)}。")
        if width < IMAGE_MIN_DIMENSION or width > IMAGE_MAX_DIMENSION:
            issues.append(f"图片宽度超限: {item['source']}，当前值: {width}，允许范围: {IMAGE_MIN_DIMENSION}~{IMAGE_MAX_DIMENSION}px。")
        if height < IMAGE_MIN_DIMENSION or height > IMAGE_MAX_DIMENSION:
            issues.append(f"图片高度超限: {item['source']}，当前值: {height}，允许范围: {IMAGE_MIN_DIMENSION}~{IMAGE_MAX_DIMENSION}px。")
        if width > 0 and height > 0:
            ratio = width / height
            if ratio < MIN_ASPECT_RATIO or ratio > MAX_ASPECT_RATIO:
                issues.append(f"图片宽高比超限: {item['source']}，当前值: {ratio:.4f}，允许范围: {MIN_ASPECT_RATIO}~{MAX_ASPECT_RATIO}。")

    for item in videos:
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        duration = float(item.get("duration") or 0.0)
        fps = float(item.get("fps") or 0.0)
        pixels = width * height
        if int(item.get("size_bytes") or 0) > VIDEO_MAX_BYTES:
            issues.append(f"视频大小超限: {item['source']}，允许范围: ≤ {_format_bytes(VIDEO_MAX_BYTES)}。")
        if duration < VIDEO_MIN_DURATION or duration > VIDEO_MAX_DURATION:
            issues.append(f"视频时长超限: {item['source']}，当前值: {duration:.2f}s，允许范围: {VIDEO_MIN_DURATION}~{VIDEO_MAX_DURATION}s。")
        if width < VIDEO_MIN_DIMENSION or width > VIDEO_MAX_DIMENSION:
            issues.append(f"视频宽度超限: {item['source']}，当前值: {width}，允许范围: {VIDEO_MIN_DIMENSION}~{VIDEO_MAX_DIMENSION}px。")
        if height < VIDEO_MIN_DIMENSION or height > VIDEO_MAX_DIMENSION:
            issues.append(f"视频高度超限: {item['source']}，当前值: {height}，允许范围: {VIDEO_MIN_DIMENSION}~{VIDEO_MAX_DIMENSION}px。")
        if width > 0 and height > 0:
            ratio = width / height
            if ratio < MIN_ASPECT_RATIO or ratio > MAX_ASPECT_RATIO:
                issues.append(f"视频宽高比超限: {item['source']}，当前值: {ratio:.4f}，允许范围: {MIN_ASPECT_RATIO}~{MAX_ASPECT_RATIO}。")
        if pixels and (pixels < VIDEO_MIN_PIXELS or pixels > VIDEO_MAX_PIXELS):
            issues.append(f"视频像素数超限: {item['source']}，当前值: {pixels}，允许范围: {VIDEO_MIN_PIXELS}~{VIDEO_MAX_PIXELS}。")
        if fps and (fps < VIDEO_MIN_FPS or fps > VIDEO_MAX_FPS):
            issues.append(f"视频帧率超限: {item['source']}，当前值: {fps:.3f}，允许范围: {VIDEO_MIN_FPS}~{VIDEO_MAX_FPS}。")

    for item in audios:
        duration = float(item.get("duration") or 0.0)
        if int(item.get("size_bytes") or 0) > AUDIO_MAX_BYTES:
            issues.append(f"音频大小超限: {item['source']}，允许范围: ≤ {_format_bytes(AUDIO_MAX_BYTES)}。")
        if duration < AUDIO_MIN_DURATION or duration > AUDIO_MAX_DURATION:
            issues.append(f"音频时长超限: {item['source']}，当前值: {duration:.2f}s，允许范围: {AUDIO_MIN_DURATION}~{AUDIO_MAX_DURATION}s。")

    if issues:
        raise SeedanceMediaValidationError(
            "❌ Seedance 素材未通过预校验，请修正后重试：\n" + "\n".join(f"- {item}" for item in issues)
        )


def prepare_seedance_media_bundle(spec: TaskSpec, api_key: str) -> dict:
    sources = collect_seedance_media_sources(spec)
    probed_assets: list[dict] = []
    temp_paths: list[str] = []
    try:
        for item in sources:
            if _is_remote_url(item.source):
                max_bytes = {
                    "image": IMAGE_MAX_BYTES,
                    "video": VIDEO_MAX_BYTES,
                    "audio": AUDIO_MAX_BYTES,
                }[item.kind]
                suffix = Path(item.source).suffix
                temp_path, size_bytes = _download_remote_media_to_temp(item.source, max_bytes=max_bytes, suffix=suffix)
                temp_paths.append(temp_path)
                local_probe_path = temp_path
                final_url = item.source
            else:
                if not os.path.isfile(item.source):
                    raise SeedanceMediaValidationError(f"❌ 本地素材不存在: {item.source}")
                local_probe_path = item.source
                size_bytes = os.path.getsize(item.source)
                final_url = _upload_local_media(item.source, api_key, item.kind)

            metadata = {
                "kind": item.kind,
                "source": item.source,
                "role": item.role,
                "url": final_url,
                "size_bytes": size_bytes,
            }
            if item.kind == "image":
                width, height = _get_image_dimensions(local_probe_path)
                metadata.update({"width": width, "height": height})
            elif item.kind == "video":
                metadata.update(_get_video_metadata(local_probe_path))
                cover_path = _extract_video_cover_frame(local_probe_path)
                try:
                    metadata["cover"] = _upload_local_media(cover_path, api_key, "image")
                finally:
                    if os.path.exists(cover_path):
                        os.unlink(cover_path)
            elif item.kind == "audio":
                metadata["duration"] = _get_audio_duration(local_probe_path)
            probed_assets.append(metadata)

        _validate_seedance_media(probed_assets, spec.task_type)

        src_image = tuple(
            {"url": item["url"], "width": int(item.get("width") or 0), "height": int(item.get("height") or 0)}
            for item in probed_assets
            if item["kind"] == "image"
        )
        src_video = tuple(
            {
                "url": item["url"],
                "duration": int(float(item.get("duration") or 0)),
                "width": int(item.get("width") or 0),
                "height": int(item.get("height") or 0),
                "cover": item.get("cover") or "",
            }
            for item in probed_assets
            if item["kind"] == "video"
        )
        src_audio = tuple(
            {
                "url": item["url"],
                "duration": int(float(item.get("duration") or 0)),
            }
            for item in probed_assets
            if item["kind"] == "audio"
        )
        return {
            "input_urls": tuple(item["url"] for item in probed_assets),
            "src_image": src_image,
            "src_video": src_video,
            "src_audio": src_audio,
        }
    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def prepare_reference_media_bundle(spec: TaskSpec, api_key: str) -> dict:
    return prepare_seedance_media_bundle(spec, api_key)


__all__ = [
    "SeedanceMediaValidationError",
    "has_multimodal_reference_media",
    "collect_seedance_media_sources",
    "is_seedance_extended_task",
    "prepare_reference_media_bundle",
    "prepare_seedance_media_bundle",
]
