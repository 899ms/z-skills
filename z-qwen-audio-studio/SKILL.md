---
name: z-qwen-audio-studio
description: Use when creating complete generated audio with qwen-audio-3.1-tts-next, including podcasts, radio drama, advertisements, multiple speakers, reference voices, ambience, sound effects, or background music. Trigger on 全景音频、双人播客、广播剧、环境声、动作音效、参考音频 and TTS Next requests. Exclude qwen-audio-3.1-tts-flash system-voice TTS.
---

# Qwen Audio Next Studio

Use Alibaba Cloud `qwen-audio-3.1-tts-next` to generate a complete audio scene from a prompt and up to three reference recordings.

## First use

Read [references/setup.md](references/setup.md), then run:

```bash
python3 scripts/qwen_audio_studio.py doctor
```

Continue only when every check reports `已设置`. The command never displays credential values.

## Workflow

1. Identify the mode: `narration`, `advertisement`, `podcast`, `drama`, or `auto`.
2. Preserve the user's exact dialogue and requested sound events. Read [references/prompt-patterns.md](references/prompt-patterns.md) when the request needs prompt construction.
3. For reference recordings, bind files in order to `@voice1`, `@voice2`, and `@voice3`. Each file must be WAV, MP3, or OGG Opus, at most 30 seconds and 10 MB.
4. Compile and inspect the prompt before a paid generation:

```bash
python3 scripts/qwen_audio_studio.py compile \
  --mode podcast \
  --prompt-file input.md \
  --reference-count 0 \
  --output compiled-prompt.txt
```

5. Generate into an explicit output directory:

```bash
python3 scripts/qwen_audio_studio.py generate \
  --mode podcast \
  --prompt-file input.md \
  --format wav \
  --sample-rate 48000 \
  --channels 2 \
  --output-name episode \
  --output-dir output/qwen-audio-next
```

Add one `--reference-audio path/to/reference.wav` argument per reference recording.

6. Accept completion only when the command exits 0 and the output directory contains the audio, compiled prompt, `generation-report.json`, and `generation-report.md`. The script verifies the file with both ffprobe and a full ffmpeg decode.

## Failure handling

- 400: correct prompt length, reference numbering, file constraints, or output parameters.
- 401: verify the Beijing-region API Key.
- 403: verify model access and Workspace permissions.
- 404 with `Model not exist`: verify the model is enabled in the Beijing region.
- 429 or 5xx: the script performs bounded retries; retain the request ID if all attempts fail.
- A failed download or decode is incomplete work. Keep the report, remove any `.part` file, and report the exact failure.

For the request schema and limits, read [references/api-contract.md](references/api-contract.md).

## Security

Read credentials only from `DASHSCOPE_API_KEY` and `SFM_WORKSPACE_ID`. Never place real values in commands, source files, examples, reports, screenshots, commits, or chat replies. Do not publish generated audio or reports with the Skill.
