> Legacy redirect: This file is retained for compatibility. Canonical docs now live under `references/gateway/*`, `references/shared/*`, and `capabilities/*`.

# Security And Network

## Credentials

- `IMA_API_KEY` is required for runtime API calls.
- It is not required before installation because bootstrap can configure it later.
- Never print full keys in logs or user output.
- Prefer environment variable injection over hardcoding.
- Bootstrap persists the key in the system keyring.
- `~/.openclaw/memory/ima_bootstrap.json` stores keyring metadata only.
- Environment `IMA_API_KEY` should override the persisted bootstrap key.

## Network Endpoints

- `https://api.imastudio.com` for product/task APIs and Seedance asset verification.
- `https://imapi.liveme.com` for local image/video/audio upload token and upload flow on supported task paths.

## Remote Reference Media Boundary

- remote reference media probing is restricted to public `http(s)` URLs
- localhost, private/reserved IPs, and local/private hostnames are blocked before any request is sent
- redirects are resolved one hop at a time and blocked if a redirect target crosses into those network ranges

## Data Flow Boundary

| Data | Stored where | Retention |
| --- | --- | --- |
| bootstrap keyring metadata | `~/.openclaw/memory/ima_bootstrap.json` | until user deletes |
| model preferences | `~/.openclaw/memory/ima_prefs.json` | until user deletes |
| runtime logs | `~/.openclaw/logs/ima_skills/` | rotating files + best-effort cleanup after 7 days |
| generated media URL | returned to caller | external resource policy applies |

## Current Logging Reality

- Local file logs rotate under `~/.openclaw/logs/ima_skills/`.
- Old log files are cleaned up on startup on a best-effort basis.
- Console logging defaults to `WARNING` unless `IMA_CONSOLE_LOG_LEVEL` is set.
- Current upload/failure logs may include local absolute paths; treat shared logs as sensitive artifacts.

## Safe Logging Rules

Allowed:

- masked API key prefix (e.g., first 8-10 chars + `...`)
- task_id, model_id, sanitized params

Forbidden:

- full API key
- raw credential headers
- signed upload URLs in shared channels

Current caveat:

- The implementation may still emit local absolute paths during upload and upload failure handling, so redact paths before sharing logs externally.

## Troubleshooting Hygiene

- Use test/scoped keys in demos.
- Do not paste full request payload with credentials into shared channels.
- If sharing logs, redact key-like strings and signed upload URLs.
