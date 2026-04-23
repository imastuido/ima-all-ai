# Audio Scenarios

## Supported Outcomes

| User need | Task type |
| --- | --- |
| generate music / BGM / song | `text_to_music` |
| generate narration / voiceover / TTS | `text_to_speech` |

## Typical Requests

- "做一段品牌 BGM" -> `text_to_music`
- "把这段文案读出来" -> `text_to_speech`

## Clarify-First Case

If the user only says "做音频" or "加点声音" without saying music vs speech, return clarification first.
