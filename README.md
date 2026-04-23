# IMA All-in-One AI Creator

One installed skill for image, video, music, TTS, and confirmed multi-step workflow execution.

## Quick Start

You only need three things:

1. `python3`
2. `requests` + `keyring`
3. `IMA_API_KEY`

Fastest setup:

```bash
python3 scripts/ima_create.py --bootstrap
```

Manual setup:

```bash
pip install -r requirements.txt
```

Set your API key:

```bash
export IMA_API_KEY="ima_xxx"
```

If you do not have a key yet, get one from:

- `https://www.imaclaw.ai/imaclaw/apikey`

Bootstrap behavior:

- `--bootstrap` installs missing public dependencies such as `requests` and `keyring`
- bootstrap saves your `IMA_API_KEY` into the system keyring
- `~/.openclaw/memory/ima_bootstrap.json` now stores only keyring metadata, not the plaintext key
- `IMA_API_KEY` environment variable still overrides the saved bootstrap key
- `IMA_API_KEY` is required for API calls, but it is not required before installation
- normal commands will auto-enter interactive bootstrap when the key is missing and the session is interactive
- normal commands will auto-install missing public Python dependencies before entering the main runtime

## Packaging

To build a runtime-only release pack:

```bash
bash scripts/build_pack.sh
```

This creates:

- `pack/<slug>/`

Pack contents:

- root release files such as `README.md`, `SKILL.md`, `clawhub.json`, and `requirements.txt`
- runtime code under `scripts/`
- skill references under `references/`
- capability docs under `capabilities/`

Pack exclusions:

- `tests/`
- `tooling/`
- local caches such as `__pycache__/`, `.pytest_cache/`, `.venv/`, `.idea/`

## First Successful Command

Fastest beginner path:

```bash
python3 scripts/ima_create.py "a clean product hero shot"
```

This zero-config mode defaults to image generation and auto-picks the top recommended runtime model when you have not saved a preference yet.

Start with model discovery:

```bash
python3 scripts/ima_create.py \
  --task-type text_to_image \
  --list-models --output-json
```

Then run one image task with a real runtime-listed `model_id`:

```bash
python3 scripts/ima_create.py \
  --task-type text_to_image \
  --model-id gpt-image-2 \
  --prompt "a clean product hero shot" \
  --extra-params '{"quality":"high","output_format":"png","aspect_ratio":"16:9"}' \
  --output-json
```

One-line form:

```bash
python3 scripts/ima_create.py --task-type text_to_image --model-id gpt-image-2 --prompt "a clean product hero shot" --extra-params '{"quality":"high","output_format":"png"}' --output-json
```

## Seedance Reference Media

For `ima-pro` / `ima-pro-fast`, `reference_image_to_video` now supports:

- reference images
- reference videos
- reference audio

Example:

```bash
python3 scripts/ima_create.py \
  --api-key "$IMA_API_KEY" \
  --model-id ima-pro-fast \
  --prompt "match the narration mood" \
  --reference-videos ./ref.mov \
  --reference-audios ./voice.mp3 \
  --output-json
```

Important:

- this expanded media path is only enabled for `ima-pro` and `ima-pro-fast`
- `image_to_video`, `first_last_frame_to_video`, and `reference_image_to_video` now require compliance verification before task creation for those two models
- local or remote reference video/audio probing depends on `ffprobe`
- video cover extraction depends on `ffmpeg`
- remote reference media must use public `http(s)` URLs; localhost, private/reserved IPs, local hostnames, and redirect chains into those targets are rejected before probing

## First Workflow Plan

Plan a workflow before spending credits:

```bash
python3 scripts/ima_create.py \
  --media-targets image video \
  --prompt "launch campaign bundle" \
  --plan-file ./ima-workflow-plan.json \
  --output-json
```

One-line form:

```bash
python3 scripts/ima_create.py --media-targets image video --prompt "launch campaign bundle" --plan-file ./ima-workflow-plan.json --output-json
```

What you get:

- a reviewed workflow plan
- `plan_id`
- `plan_hash`
- `credit_preview`
- `missing_requirements`
- `suggested_commands`

`plan_hash` now binds the full confirmable workflow object, including:

- request
- ordered steps
- model requirements
- missing requirements
- credit preview

## Confirm And Run A Workflow

After reviewing the saved plan:

```bash
python3 scripts/ima_create.py \
  --plan-file ./ima-workflow-plan.json \
  --confirm-plan-hash <plan_hash_from_plan_output> \
  --confirm-workflow \
  --output-json
```

This is human-in-the-loop by design:

- plan first
- inspect the exact plan object
- confirm the exact `plan_hash`
- then execute

Important:

- if you want to change `workflow-models`, do it during planning and generate a new plan
- confirm-run does not allow overriding reviewed model bindings

## Resume A Failed Workflow

If an earlier step already succeeded, reuse it:

```bash
python3 scripts/ima_create.py \
  --plan-file ./ima-workflow-plan.json \
  --confirm-plan-hash <plan_hash_from_plan_output> \
  --confirm-workflow \
  --resume-from-step video-2 \
  --reuse-output image-1=https://example.com/generated-image.jpg \
  --workflow-models '{"video":"<runtime-video-model-id>"}' \
  --output-json
```

## Workflow Persistence And History

Workflow planning and execution use two file concepts:

- the canonical workflow artifact
- the optional review file passed by `--plan-file`

Planning behavior:

- every reviewed workflow plan is always written to a canonical artifact path
- default artifact directory: `~/.openclaw/memory/ima_workflows/`
- override the artifact directory with `IMA_WORKFLOW_STORE_DIR`
- artifact filename format: `<plan_id>.json`
- if `--plan-file` points to a different path, the same reviewed payload is also copied there

Execution behavior:

- `--confirm-workflow` always reloads request state from `--plan-file`
- confirm-run refuses prompt/media/input override flags because the reviewed plan is the source of truth
- each confirmed run appends one entry to `execution_history`
- resume runs record `resume_from_step` plus the executed step outputs in that history entry

History location rule:

- `execution_history` is always appended to `artifact_path`
- if your `--plan-file` is the same as `artifact_path`, that file is updated in place
- if your `--plan-file` is only a copied review file, the canonical history still lives under `artifact_path`

Operational habit:

- keep the `artifact_path` returned by plan mode
- use the same reviewed `--plan-file` and `--confirm-plan-hash` for confirmation
- inspect `execution_history` in the canonical artifact when debugging retries or resume flows

List saved workflow plans and their latest known status:

```bash
python3 scripts/ima_create.py --list-workflows --output-json
```

## Reading The Output

- `stdout`
  strict machine-readable JSON when `--output-json` is enabled
- `stderr`
  human progress, warnings, and review prompts

Single-task output includes:

- `task_id`
- `url`
- `model_id`

Workflow plan output includes:

- `plan_id`
- `plan_hash`
- `credit_preview`
- `can_execute_now`
- `missing_requirements`
- `suggested_commands`

Workflow execution output includes:

- `plan_id`
- `plan_hash`
- `artifact_path`
- per-step results

## Common First-Run Issues

Error-code quick reference:

- [`references/shared/error-code-action-guide.md`](references/shared/error-code-action-guide.md)

### Missing API Key

Symptom:

- `API key is required. Pass --api-key or set IMA_API_KEY.`

Fix:

```bash
export IMA_API_KEY="ima_xxx"
```

Key URL:

- `https://www.imaclaw.ai/imaclaw/apikey`

### Don’t Know Which Model To Use

Run discovery first:

```bash
python3 scripts/ima_create.py --task-type text_to_video --list-models --output-json
```

### Workflow Asks For Music Or Speech

If your workflow includes audio, specify:

```bash
--audio-mode music
```

or:

```bash
--audio-mode speech
```

### Confirmed Workflow Refuses To Run

Check:

- `--plan-file` points to the reviewed plan file
- `--confirm-plan-hash` exactly matches the plan output
- required model ids are already present in the reviewed plan or available via saved preferences at planning time
- if you need different workflow models, re-run planning first

Friendly failure messages now distinguish two cases:

- `工作流计划已被修改，无法执行` means the plan file contents changed after planning
- `工作流计划确认码不匹配` means the `--confirm-plan-hash` argument does not match the current plan file

## Operational Notes

- preferences are stored in `~/.openclaw/memory/ima_prefs.json`
- workflow artifacts and execution history are stored in `~/.openclaw/memory/ima_workflows/`
- logs are stored in `~/.openclaw/logs/ima_skills/`
- local image paths are uploaded before task creation
- workflow execution is sequential orchestration, not one backend batch task
