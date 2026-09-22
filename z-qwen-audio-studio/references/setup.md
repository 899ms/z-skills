# Setup

Prepare these items before using the Skill.

## 1. Enable the model

Use Alibaba Cloud Model Studio in the China (Beijing) region and confirm that `qwen-audio-3.1-tts-next` is available to the target workspace.

Official API documentation: <https://help.aliyun.com/zh/model-studio/audio-generation-api>

## 2. Create a Beijing-region API Key

Create or copy an API Key that can access the target workspace and model:

<https://help.aliyun.com/zh/model-studio/get-api-key>

API Keys are region-specific. Use the Beijing-region key for this Skill.

## 3. Get the Workspace ID

Open Model Studio in the target region. The current Workspace ID is available from the workspace menu in the upper-right corner:

<https://help.aliyun.com/zh/model-studio/obtain-the-app-id-and-workspace-id>

The value commonly starts with `llm-`. Treat it as configuration data and keep it out of published files and reports.

## 4. Install local dependencies

- Python 3.9 or newer
- Python package `requests`
- `ffmpeg` and `ffprobe`

```bash
python3 -m pip install requests
```

Install ffmpeg with the package manager for the operating system, then confirm:

```bash
ffmpeg -version
ffprobe -version
```

## 5. Set credentials for the current terminal

Use placeholders in documentation and replace them only in the private terminal session:

```bash
export DASHSCOPE_API_KEY="your-api-key"
export SFM_WORKSPACE_ID="your-workspace-id"
```

Avoid committing a `.env` file. For unattended execution, use the operating system's secret manager or the deployment platform's encrypted secret store.

## 6. Run the environment check

From the Skill directory:

```bash
python3 scripts/qwen_audio_studio.py doctor
```

Every line must report `已设置`. The doctor command checks presence only and never prints either value.

## Common errors

| Error | Check |
|---|---|
| 401 | API Key value and Beijing-region selection |
| 403 | Workspace membership and model permission |
| 404 / Model not exist | Model ID, Beijing region, and account availability |
| ffmpeg or ffprobe missing | Install ffmpeg and reopen the terminal |
