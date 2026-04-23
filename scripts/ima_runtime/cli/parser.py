"""Argument parser for the canonical CLI package."""

from __future__ import annotations

import argparse

from ima_runtime.shared.config import DEFAULT_BASE_URL, POLL_CONFIG


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="IMA AI Creation Script — reliable task creation via Open API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Beginner mode: prompt only, default to image generation
  python3 scripts/ima_create.py "a cute puppy"

  # Bootstrap dependencies and local API key storage
  python3 scripts/ima_create.py --bootstrap

  # Text to image (GPT Image 2 — current recommended default)
  python3 scripts/ima_create.py \\
    --api-key ima_xxx --task-type text_to_image \\
    --model-id gpt-image-2 --prompt "a cute puppy"

  # Text to image with GPT Image 2 quality/output override
  python3 scripts/ima_create.py \\
    --api-key ima_xxx --task-type text_to_image \\
    --model-id gpt-image-2 --prompt "city skyline" \\
    --extra-params '{"quality":"high","output_format":"png","aspect_ratio":"16:9"}'

  # Text to video (Wan 2.6 — most popular default)
  python3 scripts/ima_create.py \\
    --api-key ima_xxx --task-type text_to_video \\
    --model-id wan2.6-t2v --prompt "a puppy running on grass, cinematic"

  # Image to video (Wan 2.6)
  python3 scripts/ima_create.py \\
    --api-key ima_xxx --task-type image_to_video \\
    --model-id wan2.6-i2v --prompt "camera slowly zooms in" \\
    --input-images https://example.com/photo.jpg

  # Seedance reference-image-to-video with video/audio references
  python3 scripts/ima_create.py \\
    --api-key ima_xxx --model-id ima-pro-fast \\
    --prompt "match the narration mood" \\
    --reference-videos https://example.com/ref.mov \\
    --reference-audios https://example.com/ref.mp3

  # Text to music (Suno sonic-v5)
  python3 scripts/ima_create.py \\
    --api-key ima_xxx --task-type text_to_music \\
    --model-id sonic --prompt "upbeat lo-fi hip hop, 90 BPM"

  # Text to speech (TTS) — use model_id from --list-models for category text_to_speech
  python3 scripts/ima_create.py \\
    --api-key ima_xxx --task-type text_to_speech \\
    --model-id <from list-models> --prompt "Text to be spoken"

  # List all models for a category
  python3 scripts/ima_create.py \\
    --api-key ima_xxx --task-type text_to_video --list-models

  # Plan a confirmed workflow bundle
  python3 scripts/ima_create.py \\
    --media-targets image video \\
    --prompt "launch campaign bundle" \\
    --plan-file ./ima-workflow-plan.json --output-json

  # Run a confirmed workflow bundle with explicit per-capability models
  python3 scripts/ima_create.py \\
    --media-targets image video \\
    --prompt "launch campaign bundle" \\
    --workflow-models '{"image":"gemini-3.1-flash-image","video":"wan2.6-i2v"}' \\
    --plan-file ./ima-workflow-plan.json --output-json

  # Confirm the reviewed workflow plan
  python3 scripts/ima_create.py \\
    --plan-file ./ima-workflow-plan.json \\
    --confirm-plan-hash <from reviewed plan output> \\
    --confirm-workflow --output-json

  # List saved workflow plans and latest execution status
  python3 scripts/ima_create.py --list-workflows --output-json

  # Resume a failed workflow from the video step
  python3 scripts/ima_create.py \\
    --plan-file ./ima-workflow-plan.json \\
    --confirm-plan-hash <from plan output> \\
    --confirm-workflow --resume-from-step video-2 \\
    --reuse-output image-1=https://example.com/generated-image.jpg \\
    --workflow-models '{"video":"wan2.6-i2v"}' --output-json
""",
    )

    parser.add_argument(
        "--api-key",
        help="IMA Open API key (starts with ima_). Falls back to IMA_API_KEY when omitted.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Install runtime dependencies if needed and configure a locally persisted IMA API key.",
    )
    parser.add_argument(
        "prompt_text",
        nargs="*",
        help="Beginner shortcut prompt. When present without --task-type/--media-targets, defaults to image generation.",
    )
    parser.add_argument("--task-type", choices=list(POLL_CONFIG.keys()), help="Task type to create")
    parser.add_argument("--model-id", help="Model ID from product list (e.g. gpt-image-2)")
    parser.add_argument("--version-id", help="Specific version ID — overrides auto-select of latest")
    parser.add_argument("--prompt", help="Generation prompt (required unless --list-models)")
    parser.add_argument(
        "--input-images",
        nargs="*",
        action="append",
        default=[],
        help=(
            "Input image URLs or local file paths (for image_to_image, image_to_video, etc.). "
            "Can be repeated multiple times; values are merged. "
            "Local files are automatically uploaded using the API key."
        ),
    )
    parser.add_argument(
        "--reference-videos",
        nargs="*",
        action="append",
        default=[],
        help="Reference video URLs or local file paths for Seedance reference_image_to_video runs. Can be repeated.",
    )
    parser.add_argument(
        "--reference-audios",
        nargs="*",
        action="append",
        default=[],
        help="Reference audio URLs or local file paths for Seedance reference_image_to_video runs. Can be repeated.",
    )
    parser.add_argument("--size", help="Override size parameter (e.g. 4k, 2k, 1024x1024)")
    parser.add_argument("--extra-params", help='JSON string of extra inner parameters, e.g. \'{"n":2}\'')
    parser.add_argument("--language", default="en", help="Language for product labels (en/zh)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--user-id", default="default", help="User ID for preference memory")
    parser.add_argument(
        "--media-targets",
        nargs="+",
        choices=("image", "video", "audio"),
        help="Workflow media targets for plan/confirm/run mode (e.g. image video audio)",
    )
    parser.add_argument(
        "--audio-mode",
        choices=("music", "speech"),
        help="Audio routing hint for workflow or capability mode when audio intent matters",
    )
    parser.add_argument(
        "--workflow-models",
        help='JSON object mapping capability to model_id, e.g. \'{"image":"img-model","video":"vid-model"}\'',
    )
    parser.add_argument(
        "--plan-file",
        help="Path to save a workflow plan or load a reviewed workflow plan for confirmation/resume",
    )
    parser.add_argument(
        "--confirm-plan-hash",
        help="Plan hash from the reviewed workflow plan. Required for confirm-workflow when using --plan-file.",
    )
    parser.add_argument(
        "--confirm-workflow",
        action="store_true",
        help="Execute a reviewed workflow plan from --plan-file after verifying --confirm-plan-hash",
    )
    parser.add_argument(
        "--resume-from-step",
        help="Resume a confirmed workflow from this step_id. Requires --confirm-workflow and --plan-file.",
    )
    parser.add_argument(
        "--reuse-output",
        action="append",
        default=[],
        help="Reuse output from a completed step when resuming, in the form step_id=url. Can be repeated.",
    )
    parser.add_argument(
        "--remember-model",
        action="store_true",
        help="Persist selected model to local preference memory for this user/task_type",
    )
    parser.add_argument("--list-models", action="store_true", help="List all available models for --task-type and exit")
    parser.add_argument(
        "--list-workflows",
        action="store_true",
        help="List saved workflow plans and their latest known execution status from local workflow storage.",
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Output strict machine-readable JSON to stdout; human progress goes to stderr.",
    )
    return parser
