#!/usr/bin/env python3
"""
IMA AI Creation Script — ima_create.py
Version: 1.4.6

This module is the public CLI entrypoint. It stays thin and forwards the real
runtime orchestration to the canonical `ima_runtime.cli` package.

Reliable task creation via IMA Open API.
Flow: product list → virtual param resolution → task create → poll status.

- --input-images: accepts HTTPS URLs or local file paths (local files auto-uploaded to IMA CDN).
- --api-key is optional when IMA_API_KEY is already present in the environment.
- Task types: text_to_image | image_to_image | text_to_video | image_to_video |
  first_last_frame_to_video | reference_image_to_video | text_to_music | text_to_speech

Usage:
  python3 scripts/ima_create.py "a cute puppy"

  # Explicit single-task mode
  python3 scripts/ima_create.py --api-key ima_xxx --task-type text_to_image \
    --model-id doubao-seedream-4.5 --prompt "a cute puppy"

Logs: ~/.openclaw/logs/ima_skills/ima_create_YYYYMMDD.log
"""

import sys

from ima_runtime.bootstrap import (
    ensure_runtime_dependency as _ensure_runtime_dependency,
    load_bootstrap_api_key as _load_bootstrap_api_key,
    run_bootstrap as _run_bootstrap,
    bootstrap_api_key_if_needed as _bootstrap_api_key_if_needed,
)
from ima_runtime.cli.parser import build_parser as _build_parser_impl

try:
    from ima_logger import setup_logger, cleanup_old_logs
except ImportError:
    setup_logger = None
    cleanup_old_logs = None

if setup_logger:
    try:
        logger = setup_logger("ima_skills")
        cleanup_old_logs(days=7)
    except Exception:
        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-5s | %(funcName)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logger = logging.getLogger("ima_skills")
else:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-5s | %(funcName)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("ima_skills")

_extract_model_params_impl = None
_find_model_version_impl = None
_get_product_list_impl = None
_list_all_models_impl = None
_print_model_summary_impl = None
_run_cli_impl = None
_build_contextual_diagnosis_impl = None
_extract_error_info_impl = None
_format_user_failure_message_impl = None
_flatten_input_images_args_impl = None
_prepare_image_url_impl = None
_validate_and_filter_inputs_impl = None
_get_preferred_model_id_impl = None
_save_pref_impl = None
_create_task_with_reflection_impl = None
_poll_task_impl = None
_sanitize_extra_params_impl = None
_normalize_model_id_impl = None


def _initialize_runtime_imports() -> None:
    global _extract_model_params_impl
    global _find_model_version_impl
    global _get_product_list_impl
    global _list_all_models_impl
    global _print_model_summary_impl
    global _run_cli_impl
    global _build_contextual_diagnosis_impl
    global _extract_error_info_impl
    global _format_user_failure_message_impl
    global _flatten_input_images_args_impl
    global _prepare_image_url_impl
    global _validate_and_filter_inputs_impl
    global _get_preferred_model_id_impl
    global _save_pref_impl
    global _create_task_with_reflection_impl
    global _poll_task_impl
    global _sanitize_extra_params_impl
    global _normalize_model_id_impl

    if _run_cli_impl is None:
        from ima_runtime.cli import run_cli as _runtime_run_cli

        _run_cli_impl = _runtime_run_cli
    if _print_model_summary_impl is None:
        from ima_runtime.cli import print_model_summary as _runtime_print_model_summary

        _print_model_summary_impl = _runtime_print_model_summary

    if _extract_model_params_impl is None:
        from ima_runtime.shared.catalog import extract_model_params as _runtime_extract_model_params

        _extract_model_params_impl = _runtime_extract_model_params
    if _find_model_version_impl is None:
        from ima_runtime.shared.catalog import find_model_version as _runtime_find_model_version

        _find_model_version_impl = _runtime_find_model_version
    if _get_product_list_impl is None:
        from ima_runtime.shared.catalog import get_product_list as _runtime_get_product_list

        _get_product_list_impl = _runtime_get_product_list
    if _list_all_models_impl is None:
        from ima_runtime.shared.catalog import list_all_models as _runtime_list_all_models

        _list_all_models_impl = _runtime_list_all_models

    if _build_contextual_diagnosis_impl is None:
        from ima_runtime.shared.errors import build_contextual_diagnosis as _runtime_build_contextual_diagnosis

        _build_contextual_diagnosis_impl = _runtime_build_contextual_diagnosis
    if _extract_error_info_impl is None:
        from ima_runtime.shared.errors import extract_error_info as _runtime_extract_error_info

        _extract_error_info_impl = _runtime_extract_error_info
    if _format_user_failure_message_impl is None:
        from ima_runtime.shared.errors import format_user_failure_message as _runtime_format_user_failure_message

        _format_user_failure_message_impl = _runtime_format_user_failure_message

    if _flatten_input_images_args_impl is None:
        from ima_runtime.shared.inputs import flatten_input_images_args as _runtime_flatten_input_images_args

        _flatten_input_images_args_impl = _runtime_flatten_input_images_args
    if _prepare_image_url_impl is None:
        from ima_runtime.shared.inputs import prepare_image_url as _runtime_prepare_image_url

        _prepare_image_url_impl = _runtime_prepare_image_url
    if _validate_and_filter_inputs_impl is None:
        from ima_runtime.shared.inputs import validate_and_filter_inputs as _runtime_validate_and_filter_inputs

        _validate_and_filter_inputs_impl = _runtime_validate_and_filter_inputs

    if _get_preferred_model_id_impl is None:
        from ima_runtime.shared.prefs import get_preferred_model_id as _runtime_get_preferred_model_id

        _get_preferred_model_id_impl = _runtime_get_preferred_model_id
    if _save_pref_impl is None:
        from ima_runtime.shared.prefs import save_pref as _runtime_save_pref

        _save_pref_impl = _runtime_save_pref

    if _create_task_with_reflection_impl is None:
        from ima_runtime.shared.retry_logic import create_task_with_reflection as _runtime_create_task_with_reflection

        _create_task_with_reflection_impl = _runtime_create_task_with_reflection

    if _poll_task_impl is None:
        from ima_runtime.shared.task_execution import poll_task as _runtime_poll_task

        _poll_task_impl = _runtime_poll_task

    if _sanitize_extra_params_impl is None:
        from ima_runtime.shared.task_creation import sanitize_extra_params as _runtime_sanitize_extra_params

        _sanitize_extra_params_impl = _runtime_sanitize_extra_params

    if _normalize_model_id_impl is None:
        from ima_runtime.shared.rule_resolution import normalize_model_id as _runtime_normalize_model_id

        _normalize_model_id_impl = _runtime_normalize_model_id


def build_parser():
    return _build_parser_impl()


def _parse_bootstrap_request(argv: list[str]):
    return build_parser().parse_known_args(argv)[0]


def main():
    args = _parse_bootstrap_request(sys.argv[1:])
    if getattr(args, "bootstrap", False):
        return _run_bootstrap(explicit_api_key=args.api_key)

    _ensure_runtime_dependency()
    _initialize_runtime_imports()

    return _run_cli_impl(
        args=build_parser().parse_args(),
        logger=logger,
        load_bootstrap_api_key_fn=_load_bootstrap_api_key,
        bootstrap_api_key_if_needed_fn=_bootstrap_api_key_if_needed,
        normalize_model_id_fn=_normalize_model_id_impl,
        get_product_list_fn=_get_product_list_impl,
        list_all_models_fn=_list_all_models_impl,
        get_preferred_model_id_fn=_get_preferred_model_id_impl,
        find_model_version_fn=_find_model_version_impl,
        extract_model_params_fn=_extract_model_params_impl,
        sanitize_extra_params_fn=_sanitize_extra_params_impl,
        flatten_input_images_args_fn=_flatten_input_images_args_impl,
        validate_and_filter_inputs_fn=_validate_and_filter_inputs_impl,
        prepare_image_url_fn=_prepare_image_url_impl,
        create_task_with_reflection_fn=_create_task_with_reflection_impl,
        poll_task_fn=_poll_task_impl,
        extract_error_info_fn=_extract_error_info_impl,
        build_contextual_diagnosis_fn=_build_contextual_diagnosis_impl,
        format_user_failure_message_fn=_format_user_failure_message_impl,
        save_pref_fn=_save_pref_impl,
        print_model_summary_fn=_print_model_summary_impl,
    )


if __name__ == "__main__":
    sys.exit(main())
