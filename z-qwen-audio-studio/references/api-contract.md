# Qwen Audio Next API contract

Authoritative documentation: [Alibaba Cloud audio generation API](https://help.aliyun.com/zh/model-studio/audio-generation-api).

## Endpoint

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer
```

Use the Beijing-region API Key and Workspace ID from environment variables. Never copy either value into this file, `SKILL.md`, scripts, reports, or examples.

## Request

- Model: `qwen-audio-3.1-tts-next`
- Required: `input.text_prompt`
- Optional references: at most three `audio_url` or `audio_data` entries
- Output: `wav`, `mp3`, or `pcm`
- Sample rates: 8000, 16000, 24000, 44100, 48000
- Channels: 1 or 2
- Rate: 0.5–2.0
- Volume: 0–100

Next uses `text_prompt` and `references`. System-voice fields such as `voice` and Flash instruction fields are outside this contract.

## Response

Download `output.audio.url` immediately; the URL is valid for 24 hours. Retain `request_id`, `output.audio.duration`, and non-sensitive generation parameters in the report.

## Error policy

| Status | Action |
|---|---|
| 400 | Fix prompt, reference, format, or parameter validation; do not retry |
| 401 | Check the API Key; do not retry |
| 403 | Check model access and workspace permissions; do not retry |
| 404 | Check model ID, region, and account availability; do not retry |
| 429 | Retry with bounded exponential backoff |
| 5xx | Retry with bounded exponential backoff; retain the request ID |
