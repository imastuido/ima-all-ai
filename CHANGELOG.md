# Changelog

All notable changes to this project will be documented in this file.

The format is intentionally lightweight. New changes should be added under `Unreleased`
until the next version is cut.

## [Unreleased]

### Added

- Added Seedance-only reference-media support so `reference_image_to_video` can accept reference video and reference audio alongside reference images.
- Added Seedance-only strict media validation and mandatory compliance verification for `image_to_video`, `first_last_frame_to_video`, and `reference_image_to_video`.
- Added top-level create-payload support for `src_image`, `src_video`, and `src_audio` while preserving the legacy generic path.
## [1.4.6]

- Added beginner positional-prompt mode so `python3 scripts/ima_create.py "a cute puppy"` defaults to image generation.
- Added `--list-workflows` to inspect saved workflow plans and latest local execution status.
- Added semantic validation for confirmable workflow plans so duplicate step ids,
  unknown dependencies, empty plans, and out-of-order capability chains fail fast.
- Added confirmation-time revalidation when loading a reviewed workflow payload.
- Added workflow persistence documentation covering `artifact_path`,
  `execution_history`, `IMA_WORKFLOW_STORE_DIR`, and `--plan-file` behavior.
- Added live-list model recommendation behavior:
  auto-select the only runtime-listed model family for a task type, and surface
  recommended model ids when multiple families are available.
- Added bootstrap support via `python3 scripts/ima_create.py --bootstrap`, with
  automatic public dependency installation and secure API key persistence through
  the system keyring.

### Changed

- Forwarded the runtime logger through image, video, and audio executors into shared
  task creation and polling helpers.
- Video recommendation ranking now prefers `Seedance 2.0 Fast` ahead of
  subscription-gated `Seedance 2.0` when no subscription-state signal is available.
- Normal commands now auto-enter interactive bootstrap for missing API keys when
  the session is interactive, and prefer the bootstrap credential store when the
  environment variable is absent.
- Public skill metadata and packaging docs now describe keyring-backed bootstrap
  storage instead of plaintext credential persistence.
- Workflow listings now sort unexecuted plans by `created_at` when no execution
  history exists.

## [1.4.5]

### Notes

- Baseline published release before `CHANGELOG.md` was introduced.
- Version metadata for this release is recorded in `SKILL.md`, `_meta.json`,
  `clawhub.json`, and `scripts/ima_create.py`.
