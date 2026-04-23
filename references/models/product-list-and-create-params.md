> Legacy redirect: This file is retained for compatibility. Canonical docs now live under `references/gateway/*`, `references/shared/*`, and `capabilities/*`.

# Product List And Create Params

## Why This Exists

Weak models often stop after choosing a `model_id`.
That is not enough for a reliable create call.

The real create contract depends on the selected product-list leaf and the rule/default resolution derived from it.

## Product List Leaf Fields

For a type=3 leaf returned by `/open/v1/product/list`, the important fields are:

| Product-list field | Meaning in runtime | Used in create task |
| --- | --- | --- |
| `id` | version leaf ID | `parameters[0].model_version` |
| `model_id` | backend model code | `parameters[0].model_id` |
| `name` | user-facing model name | `parameters[0].model_name` |
| `form_config[]` | default UI/runtime parameters | base of inner `parameters` |
| `credit_rules[]` | allowed attribute profiles | selects `attribute_id`, `credit`, canonical rule params |

## Credit Rule Semantics

`credit_rules` is not just metadata. It is the pricing and attribute-selection rule set for the selected product leaf.

Interpretation:

- `credit_rules[i].points`
  the billable points for that matched rule
- `credit_rules[i].attribute_id`
  the backend attribute profile id that must be sent when that rule is selected
- `credit_rules[i].attributes`
  the rule-matching condition set

Meaning:

1. Rule matching determines both points and `attribute_id`.
2. The selected `attribute_id` is not cosmetic. It is a required create-time identifier.
3. If the chosen parameters imply a different rule, both points and `attribute_id` should change with that rule.

## What `--list-models` Tells You

### Plain Table

`--list-models` currently exposes:

- `name`
- `model_id`
- `raw_model_id`
- `version_id`
- first-rule `pts`
- first-rule `attr_id`
- `rule_count`

### JSON Discovery Mode

`--list-models --output-json` additionally exposes:

- `raw_model_id`
- `form_fields`
- `virtual_fields`
- `virtual_ui_fields`
- `virtual_mappings`
- `attribute_keys`

Use JSON discovery mode when the agent needs to know whether a model surface likely supports user-requested params.

Meaning:

- `virtual_fields`
  the product leaf fields marked `is_ui_virtual=true`
- `virtual_ui_fields`
  the user-facing input fields exposed via `ui_params`
- `virtual_mappings`
  the discovery view of how user-facing virtual values map to backend target params and target values

## Multiple Leaves With The Same `model_id`

Weak models often treat `model_id` as if it uniquely identifies one runtime product leaf.
That is not always true.

Current runtime reality:

- multiple leaves can share the same `model_id`
- `version_id` is the leaf-level identifier exposed by the product list
- the same `model_id` family can still require different downstream handling based on the selected leaf

Practical implications:

1. `model_id` identifies the model family, not always a unique product-list leaf.
2. `version_id` is the precise leaf selector when you need one specific variant.
3. Without `--version-id`, runtime currently returns the last matching leaf for the requested `model_id`.
4. If repeated rows share the same `model_id`, do not assume they are interchangeable.

Examples:

- `pixverse` may appear multiple times with different `version_id` values such as `Pixverse V5.5`, `Pixverse V5`, `Pixverse V4.5`
- these leaves share the same family code but still differ in effective runtime behavior

## What `--list-models` Does Not Tell You

It is still a discovery surface, not the final create payload.

It does not fully expose:

- the entire `form_config`
- the entire `credit_rules` matrix
- the final selected rule after user overrides are merged
- the final inner `parameters` payload sent to create
- whether multiple rows with the same `model_id` will later need an explicit `--version-id` for reproducibility

## Resolution Flow

Current runtime logic resolves create fields in this order:

1. Find the matching product-list leaf by exact `model_id`, optionally pinned by `version_id`.
2. Build `form_params` from `form_config`.
3. Resolve virtual form fields when `is_ui_virtual=true` using `ui_params + value_mapping`.
4. Select the initial credit rule from `credit_rules` using resolved form defaults.
5. Merge user overrides and re-select the best matching credit rule for the effective parameter set.
6. Build the final create payload using leaf fields + selected rule + merged params.

When multiple leaves share the same `model_id`, step 1 is where the ambiguity is resolved.
That is why `version_id` matters even before rule selection begins.

The rule-selection consequence is:

- initial default params choose the initial `attribute_id` and points
- user overrides may move the request onto a different rule
- final create payload must use the final selected rule's `attribute_id` and points

## Payload Mapping

| Resolved value | Create payload target |
| --- | --- |
| chosen `task_type` | top-level `task_type` |
| local/remote inputs | top-level `src_img_url` and inner `input_images` |
| selected leaf `model_id` | `parameters[0].model_id` |
| selected leaf `name` | `parameters[0].model_name` |
| selected leaf `id` | `parameters[0].model_version` |
| selected rule `attribute_id` | `parameters[0].attribute_id` and inner `cast.attribute_id` |
| selected rule `points` | `parameters[0].credit` and inner `cast.points` |
| merged effective params | `parameters[0].parameters` |

`raw_model_id` is a discovery/debug field from runtime discovery.
It helps you see the backend value as exposed by the product list, but it is not a separate CLI flag.

## Parameter Merge Priority

The current create path merges parameters in this order:

1. `form_params`
2. `rule_attributes`
3. canonical values from the matched rule
4. user `--extra-params` for non-rule keys

This is why user input may be normalized to backend rule values such as `1080P` or `1K`.

## Special Cases

### Virtual Parameters

If a form field is marked `is_ui_virtual=true`, the user-facing control and the backend payload field are not necessarily the same thing.

Interpretation:

- `ui_params[].field`
  user-facing field shown to the operator/user
- `value_mapping.source_values`
  the UI-side values used for matching
- `value_mapping.target_param`
  the backend payload field when present
- `mapping_rules[].target_value`
  the backend value actually sent after mapping

Agent/operator rule:

1. If the user gives a UI-facing virtual value, do not pass it directly as the final backend parameter.
2. Resolve it through `value_mapping` first.
3. Send the mapped backend field/value pair, not the UI field/value pair.
4. Apply the same mapping semantics to both default values and user overrides.

Field selection rule:

- use `value_mapping.target_param` when present
- otherwise fall back to the virtual field's own `field`

Current implementation already resolves virtual defaults from `ui_params + value_mapping`.
Agent-side parameter interpretation for user overrides must follow the same semantics.

#### Example: `quality` UI -> `mode` backend

Example shape:

- virtual field: `field=mode`
- UI field: `ui_params.field=quality`
- `quality=720p` -> `mode=std`
- `quality=1080p` -> `mode=pro`

Correct interpretation:

- user chooses `quality=1080p`
- backend should receive `mode=pro`
- do not send `quality=1080p` as if it were the final create parameter
- do not rewrite it as `quality=pro`; the final backend field is still `mode`

This is why weak models must distinguish:

- display/UI field
- mapped backend field
- mapped backend value

#### Conflict Rule: UI field vs backend field

If both are present:

- UI field example: `quality=1080p`
- backend field example: `mode=std`

Then the backend field wins.

Rules:

1. Treat the explicit backend field as authoritative.
2. Ignore the conflicting UI field for final payload construction.
3. Prefer logging or warning about the conflict rather than silently merging inconsistent values.

#### Invalid UI Value Rule

If a UI-facing value cannot be mapped through `value_mapping.mapping_rules`, do not guess the backend field or value.

Expected behavior:

1. stop before create
2. return a user-friendly clarification
3. show only valid UI choices
4. do not expose backend enum values as the suggested user input

Example:

- invalid UI input: `quality=4k`
- valid user-facing options: `720p`, `1080p`
- do not ask the user to choose `std` or `pro`

### Default Rule: `attributes.default=enabled`

`default=enabled` should be treated as the default fallback rule marker.

Rule-selection semantics:

1. Try to match more specific rules first.
2. If no specific rule matches, fall back to the default rule.
3. When the default rule is selected, use that rule's `attribute_id` and `points`.
4. Use `default=enabled` only for default rule selection, points, and `attribute_id`.
5. Do not emit `default=enabled` as a business parameter in the final create payload unless a model-specific contract explicitly requires it.

Do not let the existence of `default=enabled` erase the distinction between:

- a specific matched rule
- a default fallback rule

### TTS note

For `text_to_speech`, `credit_rules.attributes.default=enabled` is not merely descriptive.
It remains part of the valid runtime attribute surface and must not be dropped from TTS attribute-key handling.
That does not change the default rule principle above: its primary role is still rule selection and attribute/points resolution.

### Pixverse `model`

Some Pixverse variants require an extra inner `model` parameter even though the main `model_id` is still `pixverse`.

Current runtime behavior:

- preserve `model` from `form_config` when present
- allow explicit override via `--extra-params`
- auto-infer `model` from `model_name` as a fallback for Pixverse

This is a concrete example of why `model_id` alone may be insufficient context for understanding the final create payload.

### Default Rule + Virtual Mapping Interaction

The most error-prone case is when:

- `form_config` contains virtual UI fields
- user-visible values map to backend values
- `credit_rules` includes a default rule and/or multiple concrete rules

In that case, the safe order is:

1. resolve virtual UI fields to backend field/value pairs
2. evaluate concrete `credit_rules.attributes`
3. if none match, fall back to the default rule
4. use the selected rule's `attribute_id` and points in the final payload
5. do not leak default-rule markers into the payload unless the runtime contract explicitly requires it

## Weak-Model Checklist

Before treating a model choice as final:

1. run `--list-models --output-json`
2. confirm `attribute_keys` can cover the user's requested params
3. if the same `model_id` appears multiple times, inspect `version_id` before assuming the leaves are equivalent
4. for `is_ui_virtual=true`, distinguish UI-facing fields from backend payload fields
5. remember that `version_id`, `attribute_id`, points, and rule-compatible values are resolved after leaf selection
6. if you hit `6009` or `6010`, suspect rule mismatch before suspecting prompt quality

## Debugging Clues

- `4008`: points profile too expensive for the selected rule
- `6009`: missing rule attributes
- `6010`: selected params do not match the resolved `attribute_id`
- minimum pixel errors: selected size violates model constraints

See `../operations/api-contract-and-errors.md` for retry behavior and failure messaging.
