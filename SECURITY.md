# Security Disclosure: ima-all-ai

## Purpose

This document explains endpoint usage, credential flow, and local data behavior for `ima-all-ai`.

## Network Endpoints

| Domain | Used For | Trigger |
|---|---|---|
| `api.imastudio.com` | Product list, task create, task detail polling, asset verify | All requests; asset verify only for Seedance compliance-gated media runs |
| `imapi.liveme.com` | Upload-token request + binary upload for local media inputs | Local image/video/audio inputs on supported task paths |
| `*.aliyuncs.com` / `*.esxscloud.com` | Presigned binary upload + media CDN delivery | Returned by upload-token API |

For remote media URLs (`http(s)://...`), the script passes URLs directly and does not need upload-token calls, but Seedance reference-video/audio probing may still fetch those URLs temporarily for metadata extraction.
That probing path now only allows public `http(s)` targets and rejects localhost, private/reserved IPs, local hostnames, and redirect chains that enter those network ranges.

## Credential Flow

| Credential | Where Sent | Why |
|---|---|---|
| `IMA_API_KEY` | `api.imastudio.com` | Open API auth (`Authorization: Bearer ...`) |
| `IMA_API_KEY` | `imapi.liveme.com` | Upload-token auth for local image/video/audio uploads |

No API key is sent to presigned upload hosts (`aliyuncs/esxscloud`) during binary upload.

## Input Safety Guards

The script validates task/image compatibility before task creation:

- `text_to_image`, `text_to_video`, `text_to_music`, `text_to_speech`: no input images
- `image_to_image`, `image_to_video`: at least 1 image
- `reference_image_to_video`: at least 1 reference asset (`image`, `video`, or `audio`)
- `first_last_frame_to_video`: exactly 2 images

## Upload Signing Constants

`APP_ID` and `APP_KEY` in script source are upload-signing constants (not repository secrets).

## Local Data

| Path | Content | Retention |
|---|---|---|
| `~/.openclaw/memory/ima_prefs.json` | Per-user model preference cache | Until manually removed |
| `~/.openclaw/logs/ima_skills/` | Operational logs | Auto-cleaned by script after 7 days |

No API key is written into repository files.
