# Error Code Action Guide

This table maps common business error codes to the user-facing action we expect the skill to recommend.

## Core Action Table

| Code | Meaning | User Action |
| --- | --- | --- |
| `401` | API key invalid or unauthorized | Get or regenerate a key at `https://www.imaclaw.ai/imaclaw/apikey`, then retry |
| `4008` | Points / credits are not enough | Go to `https://www.imaclaw.ai/imaclaw/subscription` to top up or upgrade, or switch to a lower-cost model |
| `4014` | Subscription tier required | Go to `https://www.imaclaw.ai/imaclaw/subscription` and upgrade the account tier |
| `500` | Backend rejected current parameter complexity | Retry with simpler parameters or a faster / lower-cost model |
| `6009` | No matching credit rule | Remove custom overrides or add the missing rule-compatible parameters |
| `6010` | Attribute mismatch with current rule | Retry after reselecting the compatible rule / attribute combination |

## Timeout And Non-Code Cases

| Condition | Meaning | User Action |
| --- | --- | --- |
| `timeout` | Polling exceeded the configured wait window | Retry with simpler params and check the creation record or dashboard |
| transport error without business code | Network / HTTP layer failed before a business result | Retry, verify connectivity, and only escalate after repeated failures |

## Product Rule

The skill should not just expose the code. It should translate the code into:

1. what happened
2. why it likely happened
3. what exact action the user should take next

For `4008`, `4014`, and `401`, the next action should always include the correct destination URL.
