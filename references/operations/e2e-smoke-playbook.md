> Legacy redirect: This file is retained for compatibility. Canonical docs now live under `references/gateway/*`, `references/shared/*`, and `capabilities/*`.

# E2E Smoke Playbook

Use this checklist before release or after major refactor.

## Preconditions

- `IMA_API_KEY` is set and valid, or bootstrap has saved a valid key in the system keyring
- network can reach IMA endpoints
- `python3`, `requests`, and `keyring` available

Fast path:

```bash
bash tooling/live-smoke.sh
```

This script discovers a current runtime model for each default stage and runs the four live smoke checks end to end.
It also runs the workflow plan smoke by default.
Use positional task types if you want a narrower gate, for example:

```bash
bash tooling/live-smoke.sh text_to_image text_to_video
```

## 0) Repo Gate

```bash
bash tooling/ci-check.sh
```

Expected:

- doc structure/version checks pass
- syntax checks pass
- tests pass

Note:

- This gate does not prove semantic accuracy of the docs.
- It also does not prove live API availability.

## Runtime Model Selection Rule

Before each live smoke stage below:

1. run `--list-models` for that `task_type`
2. choose a current runtime-listed model with a reasonable points profile
3. substitute that exact `model_id` into the smoke command

Use `--list-models --output-json` when you need to inspect `rule_count`, `form_fields`, or `attribute_keys` before choosing the model.

Known model IDs such as `doubao-seedream-4.5`, `wan2.6-t2v`, `GenBGM`, and `seed-tts-2.0` are only examples, not guaranteed live truth.
For point-in-time verified runs, see `live-smoke-history.md`.

## 1) Image Smoke

```bash
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_image --list-models

python3 scripts/ima_create.py \
  --api-key "$IMA_API_KEY" \
  --task-type text_to_image \
  --model-id <runtime-image-model-id> \
  --prompt "minimal smoke image" \
  --output-json
```

Check:

- returns `task_id`
- returns non-empty `url`
- output `model_id` matches the selected runtime model

## 2) Video Smoke

```bash
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_video --list-models

python3 scripts/ima_create.py \
  --api-key "$IMA_API_KEY" \
  --task-type text_to_video \
  --model-id <runtime-video-model-id> \
  --prompt "minimal smoke video" \
  --extra-params '{"duration":5,"resolution":"720P"}' \
  --output-json
```

Check:

- task completes within configured polling window
- failure path includes actionable diagnosis if timeout/error occurs
- when debugging failures, confirm the response-body API `code`; do not use HTTP status alone as the business error code

## 3) Music Smoke

```bash
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_music --list-models

python3 scripts/ima_create.py \
  --api-key "$IMA_API_KEY" \
  --task-type text_to_music \
  --model-id <runtime-music-model-id> \
  --prompt "minimal smoke bgm" \
  --output-json
```

Check:

- URL is returned
- no input-image related errors

## 4) TTS Smoke

```bash
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_speech --list-models

python3 scripts/ima_create.py \
  --api-key "$IMA_API_KEY" \
  --task-type text_to_speech \
  --model-id <runtime-tts-model-id> \
  --prompt "this is a smoke test" \
  --output-json
```

Check:

- URL is returned
- duration/metadata present when available

## 5) Guardrail Smoke (No Real API Required)

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Specifically ensure these pass:

- interface recognition
- parameter sanitization
- upload recognition (`file://`)
- reflection retry paths (`500`, `6009`, `6010`, exhausted retries)

## 6) Workflow Surface Smoke

```bash
python3 scripts/ima_create.py \
  --media-targets image video \
  --prompt "workflow smoke plan" \
  --output-json
```

Check:

- returns `mode=workflow_plan`
- returns ordered steps
- does not create any generation task in plan-only mode

Run confirmed workflow mode when you have valid runtime models or remembered preferences:

```bash
IMA_ENABLE_WORKFLOW_CONFIRM_SMOKE=1 bash tooling/live-smoke.sh
```

Check:

- returns `mode=workflow_execution`
- image step completes before video step starts
- video step uses the generated image output as its upstream input when applicable

## 7) Release Decision

Ship only if:

- repo gate and all six smoke stages pass
- no regression in task routing or error diagnosis clarity
