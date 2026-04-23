# IMA All AI References

The docs now mirror the runtime architecture:

- `references/gateway/*`
  Entry rules for request classification, routing, and workflow confirmation.
- `references/shared/*`
  Cross-capability policy for model selection, failures, security, and network behavior.
- `capabilities/*`
  Domain-owned contract docs for image, video, audio, and workflow.

`SKILL.md` is intentionally short. It is the public gateway, not the full operating manual.

## Migration State

- Image, video, and audio are now all wired through their capability-owned execution paths in current production CLI flow.
- The public CLI supports single-task execution plus confirmed workflow plan/run flows.
- Workflow execution still runs one capability step at a time in dependency order; it is orchestration, not one backend batch task.

## Read Order

1. `gateway/entry-and-routing.md`
2. `gateway/workflow-confirmation.md`
3. `shared/model-selection-policy.md`
4. `shared/error-policy.md`
5. `shared/error-code-action-guide.md`
6. `shared/security-and-network.md`
7. capability docs under `../capabilities/*/CAPABILITY.md`

## Layout Rules

- Gateway docs explain how requests enter the system.
- Shared docs explain policy that applies to every capability.
- Capability docs explain domain-specific scenarios, routing, model binding, and parameter rules.
- Capability docs may describe staged seams as well as active production paths; do not assume every package is already the live CLI executor.
- Keep deep detail in the owning capability instead of repeating it in `SKILL.md`.

## Capability Map

- `../capabilities/image/`
  `text_to_image` and `image_to_image`
- `../capabilities/video/`
  `text_to_video`, `image_to_video`, `first_last_frame_to_video`, `reference_image_to_video`
- `../capabilities/audio/`
  `text_to_music` and `text_to_speech`
- `../capabilities/workflow/`
  Multi-target planning, dependency ordering, and confirmation

## Maintenance Notes

- Update gateway docs when `GatewayRequest`, router behavior, or clarification boundaries change.
- Update shared docs when policy changes across multiple capabilities.
- Update capability docs when the owning `scripts/ima_runtime/capabilities/*` package changes.
- `tooling/validate-doc-structure.sh` enforces structure, legacy redirect markers, and version alignment only.
