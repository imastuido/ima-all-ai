# Security And Network

This policy applies to every capability and to the gateway shell.

## Credentials

- `IMA_API_KEY` is required for runtime API calls
- it is not required before installation because bootstrap can configure it later
- never print the full key in logs or user-visible output
- prefer environment injection over hardcoded keys
- bootstrap persists the key in the system keyring
- `~/.openclaw/memory/ima_bootstrap.json` stores keyring metadata only
- environment `IMA_API_KEY` should override the persisted bootstrap key

## Network Endpoints

- `https://api.imastudio.com`
  Product list, task create, task detail, asset verify
- `https://imapi.liveme.com`
  Upload token and local media upload path for image/video/audio inputs on supported task paths

## Remote Media Guardrails

- remote reference media probing only accepts public `http(s)` URLs
- localhost, private/reserved IP literals, and local/private hostnames are rejected before the fetch starts
- redirect chains are followed manually and are rejected immediately if any hop points into a blocked network target

## Local Data Boundaries

| Data | Location |
| --- | --- |
| bootstrap keyring metadata | `~/.openclaw/memory/ima_bootstrap.json` |
| model preferences | `~/.openclaw/memory/ima_prefs.json` |
| runtime logs | `~/.openclaw/logs/ima_skills/` |
| generated URLs | returned to the caller |

## Safe Logging

Allowed:

- masked key prefixes
- `task_id`
- `model_id`
- sanitized params

Do not share:

- full API keys
- raw auth headers
- signed upload URLs
- unredacted local absolute paths from upload logs

## Upload Boundary

- local paths are uploaded before task creation
- remote `http://` and `https://` inputs are passed through as URLs
- text-only tasks should not receive uploaded media inputs

## Sharing Hygiene

When sharing logs outside the local machine, redact:

- credential-like strings
- signed URLs
- local filesystem paths
