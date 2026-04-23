> Legacy redirect: This file is retained for compatibility. Canonical docs now live under `references/gateway/*`, `references/shared/*`, and `capabilities/*`.

# Model ID And Defaults

## Non-Negotiable

Use exact `model_id`, not friendly names.
Runtime product list is source of truth.

## Responsibility Split

- Runtime product list is authoritative for available `model_id`, `version_id`, credits, and form fields.
- Agent or operator chooses the candidate `model_id` from that runtime list.
- The CLI only auto-fills `model_id` from saved preference memory; otherwise `--model-id` is required.

## Lookup Hints (Docs Only)

These are convenience hints for humans, not static authority and not guaranteed parser aliases.

| Friendly intent | Typical model_id |
| --- | --- |
| GPT Image 2 | `gpt-image-2` |
| Nano Banana 2 | `gemini-3.1-flash-image` |
| Nano Banana Pro | `gemini-3-pro-image` |
| SeeDream 4.5 | `doubao-seedream-4.5` |
| Seedance 2.0 | `ima-pro` |
| Seedance 2.0 Fast | `ima-pro-fast` |
| DouBao BGM | `GenBGM` |
| DouBao Song | `GenSong` |
| TTS default | `seed-tts-2.0` |

## Parser Alias Support (Current)

Only a very small alias set is normalized by the script today:

- `Seedance 2.0` -> `ima-pro`
- `Seedance 2.0-Fast` -> `ima-pro-fast`
- `Seedance 2.0 Fast` -> `ima-pro-fast`

All other friendly names should be resolved manually to exact runtime `model_id`.

## Runtime Discovery Commands

```bash
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_image --list-models
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_video --list-models
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_music --list-models
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_speech --list-models
```

`--list-models` prints `model_id`, `version_id`, and points so you can rank candidates by availability and cost.
Use `--list-models --output-json` when you also need `rule_count`, `form_fields`, `virtual_fields`, or `attribute_keys`.

## Same `model_id`, Multiple Leaves

One `model_id` does not always mean one unique runtime leaf.

Important cases:

- the same `model_id` can appear multiple times with different `version_id`
- the same `model_id` can map to different product leaves that still need different downstream handling
- `pixverse` is the clearest example: multiple leaves share `model_id=pixverse` but differ by `version_id` and effective inner `model`

Rules:

1. Treat `model_id` as the primary family identifier, not always the final unique leaf identity.
2. If multiple leaves share the same `model_id`, `version_id` is the stable tie-breaker when you need a specific one.
3. Without `--version-id`, runtime currently picks the last matching leaf from the live product list.
4. If your use case depends on a specific generation variant, pin `--version-id` instead of assuming the family `model_id` is enough.

## Default Model Strategy

Current CLI behavior when caller does not pass `--model-id`:

1. reuse saved preference for the current `user_id` + `task_type` if one exists
2. if the current runtime exposes only one unique `model_id` family for that `task_type`, use it automatically
3. otherwise stop and require an explicit `--model-id`, but print 1-3 recommended model ids

Current recommendation note:

- recommendations still come from the live runtime list, not a static model registry
- for Seedance family video tasks, `Seedance 2.0 Fast` is ranked ahead of subscription-gated `Seedance 2.0` when no subscription state signal is available

Recommended agent behavior:

1. run `--list-models` for the target `task_type`
2. recommend 1-3 candidates that fit the user's quality/speed/cost intent
3. pass the exact chosen `model_id` explicitly
4. if multiple leaves share that `model_id`, decide whether the run should also pin `--version-id`

## Missing Model Behavior

Current CLI behavior when requested model is not found:

1. print an error for the requested `model_id`
2. print the full available `model_id` list for that `task_type`
3. exit non-zero

Recommended agent fallback:

1. re-run `--list-models` for the same `task_type`
2. surface top 3 compatible candidates
3. preserve user intent (quality/speed/cost/accessibility) in recommendation order

## Stale Preference Behavior

Saved preference only stores `model_id`, not a permanently valid promise that the runtime still exposes that leaf.

Implications:

- a remembered `model_id` may disappear from the live runtime list
- a remembered `model_id` family may still exist, but with different leaves or changed points/profile

Recommended agent behavior when a remembered model is stale:

1. treat the stale preference as a hint, not a guarantee
2. rerun `--list-models` for the same `task_type`
3. prefer a current runtime-listed replacement that matches the old intent (quality/speed/cost)
4. tell the user that the remembered model was unavailable in the current runtime

## Version Pinning

- Use `--version-id` only when you need a specific version leaf from the runtime tree.
- Without `--version-id`, the script uses the matched model leaf selected from the current product list.
- For how `version_id`, `attribute_id`, and rule-derived params feed create, see `product-list-and-create-params.md`.

When to pin `--version-id`:

- multiple leaves share the same `model_id`
- a workflow depends on a known leaf-specific behavior
- you need reproducibility across runs while the live product list may reorder or evolve

When not to pin:

- you only care about the current best/default live leaf for that `model_id`
- you explicitly want runtime drift to follow the latest available leaf

## Preference Rules

- Persist preference only when user explicitly asks to remember a model.
- CLI write-back is explicit via `--remember-model`.
- No implicit write-back after successful generation.
- If preference conflicts with explicit request, explicit request wins for this run.
- If preference and current runtime disagree, current runtime availability wins and the old preference must be treated as stale.

## Anti-Patterns

- Hardcoding full model tables as immutable truth.
- Using image model IDs for video task types (or vice versa).
- Treating lookup hints as accepted CLI aliases.
- Assuming one `model_id` always maps to one unique runtime leaf.
- Treating remembered `model_id` as valid without checking the live product list first.
- Storing preference silently without user consent.
