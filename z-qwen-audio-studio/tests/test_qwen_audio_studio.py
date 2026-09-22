import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "qwen_audio_studio.py"
SPEC = importlib.util.spec_from_file_location("qwen_audio_studio", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, status_code, json_value=None, content=b""):
        self.status_code = status_code
        self._json_value = json_value or {}
        self.content = content
        self.text = json.dumps(self._json_value)

    def json(self):
        return self._json_value

    def iter_content(self, chunk_size=65536):
        del chunk_size
        yield self.content


class FakeSession:
    def __init__(self, post_responses=None, get_responses=None):
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.post_calls = 0
        self.get_calls = 0

    def post(self, *args, **kwargs):
        del args, kwargs
        self.post_calls += 1
        return self.post_responses.pop(0)

    def get(self, *args, **kwargs):
        del args, kwargs
        self.get_calls += 1
        return self.get_responses.pop(0)


class RaisingSession:
    def __init__(self, message):
        self.message = message

    def post(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError(self.message)


class QwenAudioStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir_handle = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temp_dir_handle.name)

    def tearDown(self):
        self.temp_dir_handle.cleanup()

    def test_build_payload_uses_next_contract(self):
        payload = MODULE.build_payload(
            prompt='一位女性说：“你好。”',
            references=[],
            output_format="wav",
            sample_rate=48000,
            channels=2,
            volume=50,
            rate=1.0,
            seed=42,
            enable_cbr=False,
            bit_rate=128,
            quality=5,
            enable_aigc_tag=False,
        )

        self.assertEqual(payload["model"], "qwen-audio-3.1-tts-next")
        self.assertEqual(payload["input"]["text_prompt"], '一位女性说：“你好。”')
        self.assertNotIn("voice", payload["input"])
        self.assertNotIn("instruction", payload["input"])
        self.assertNotIn("instructions", payload["input"])
        self.assertEqual(payload["input"]["sample_rate"], 48000)
        self.assertEqual(payload["input"]["channels"], 2)

    def test_rejects_out_of_range_and_unsupported_values(self):
        with self.assertRaisesRegex(MODULE.ConfigError, "3000"):
            MODULE.validate_generation_options("x" * 3001, "wav", 48000, 2, 50, 1.0, 0)
        with self.assertRaisesRegex(MODULE.ConfigError, "sample rate"):
            MODULE.validate_generation_options("ok", "wav", 22050, 2, 50, 1.0, 0)
        with self.assertRaisesRegex(MODULE.ConfigError, "channels"):
            MODULE.validate_generation_options("ok", "wav", 48000, 6, 50, 1.0, 0)
        with self.assertRaisesRegex(MODULE.ConfigError, "volume"):
            MODULE.validate_generation_options("ok", "wav", 48000, 2, 101, 1.0, 0)
        with self.assertRaisesRegex(MODULE.ConfigError, "rate"):
            MODULE.validate_generation_options("ok", "wav", 48000, 2, 50, 2.1, 0)

    def test_environment_check_never_returns_credential_values(self):
        result = MODULE.check_environment(
            {
                "DASHSCOPE_API_KEY": "sk-sensitive-test-value",
                "SFM_WORKSPACE_ID": "workspace-sensitive-test-value",
            },
            which=lambda name: f"/usr/bin/{name}",
            requests_available=True,
        )
        serialized = json.dumps(result)

        self.assertNotIn("sk-sensitive-test-value", serialized)
        self.assertNotIn("workspace-sensitive-test-value", serialized)
        self.assertTrue(result["DASHSCOPE_API_KEY"]["configured"])
        self.assertTrue(result["SFM_WORKSPACE_ID"]["configured"])

    def test_compile_podcast_prompt_preserves_dialogue_and_adds_scene_contract(self):
        result = MODULE.compile_prompt(
            "podcast", "主持人：今天聊 AI。\n嘉宾：好。", 0
        )

        self.assertIn("播客", result)
        self.assertIn("主持人：今天聊 AI。", result)
        self.assertIn("声场", result)

    def test_rejects_reference_number_not_supplied(self):
        with self.assertRaisesRegex(MODULE.ConfigError, "@voice2"):
            MODULE.validate_voice_references("@voice2 说：你好", 1)

    def test_rejects_four_reference_files(self):
        with self.assertRaisesRegex(MODULE.ConfigError, "at most 3"):
            MODULE.validate_reference_paths([Path("a.wav")] * 4)

    def test_rejects_ogg_when_codec_is_not_opus(self):
        path = self.temp_dir / "sample.ogg"
        path.write_bytes(b"fake")
        metadata = {
            "format": {"duration": "1.0", "format_name": "ogg"},
            "streams": [{"codec_name": "vorbis"}],
        }
        with mock.patch.object(MODULE, "run_ffprobe", return_value=metadata):
            with self.assertRaisesRegex(MODULE.ConfigError, "OGG Opus"):
                MODULE.inspect_reference_audio(path)

    def test_encode_reference_uses_data_uri_without_persisting_it(self):
        path = self.temp_dir / "sample.wav"
        path.write_bytes(b"RIFF-test")
        metadata = {
            "format": {"duration": "1.0", "format_name": "wav"},
            "streams": [{"codec_name": "pcm_s16le"}],
        }
        with mock.patch.object(MODULE, "run_ffprobe", return_value=metadata):
            result = MODULE.encode_reference(path)

        self.assertTrue(result["audio_data"].startswith("data:audio/wav;base64,"))

    def test_401_fails_without_retry(self):
        session = FakeSession(
            post_responses=[
                FakeResponse(
                    401, {"code": "InvalidApiKey", "message": "credential rejected"}
                )
            ]
        )

        with self.assertRaisesRegex(MODULE.ApiError, "401"):
            MODULE.post_generation(
                session, "https://example.invalid", "secret", {"model": "x"}
            )

        self.assertEqual(session.post_calls, 1)

    def test_429_retries_then_succeeds(self):
        session = FakeSession(
            post_responses=[
                FakeResponse(429, {"code": "Throttling.RateQuota"}),
                FakeResponse(
                    200,
                    {
                        "request_id": "req-success",
                        "output": {"audio": {"url": "https://audio.invalid/test.wav"}},
                    },
                ),
            ]
        )

        result = MODULE.post_generation(
            session,
            "https://example.invalid",
            "secret",
            {"model": "x"},
            sleeper=lambda _: None,
        )

        self.assertEqual(result["request_id"], "req-success")
        self.assertEqual(session.post_calls, 2)

    def test_200_without_audio_url_fails_with_request_id(self):
        session = FakeSession(
            post_responses=[
                FakeResponse(200, {"request_id": "req-missing-url", "output": {}})
            ]
        )

        with self.assertRaisesRegex(MODULE.ApiError, "req-missing-url"):
            MODULE.post_generation(
                session, "https://example.invalid", "secret", {"model": "x"}
            )

    def test_network_error_redacts_workspace_id(self):
        workspace_id = "workspace-sensitive-test-value"
        session = RaisingSession(
            f"DNS failed for {workspace_id}.cn-beijing.maas.aliyuncs.com"
        )

        with self.assertRaises(MODULE.ApiError) as caught:
            MODULE.post_generation(
                session,
                f"https://{workspace_id}.cn-beijing.maas.aliyuncs.com/test",
                "secret",
                {"model": "x"},
                max_attempts=1,
                sleeper=lambda _: None,
                redact_secrets=[workspace_id],
            )

        self.assertNotIn(workspace_id, str(caught.exception))
        self.assertIn("<redacted>", str(caught.exception))

    def test_redact_removes_secret_workspace_and_audio_data(self):
        value = {
            "message": (
                "Authorization" + ": Bearer " + "secret-key at "
                "https://workspace-sensitive.cn-beijing.maas.aliyuncs.com"
            ),
            "references": [
                {"audio_data": "data:audio/wav;base64,AAAA-sensitive"}
            ],
        }

        redacted = MODULE.redact(
            value, secrets=["secret-key", "workspace-sensitive"]
        )
        serialized = json.dumps(redacted)

        self.assertNotIn("secret-key", serialized)
        self.assertNotIn("workspace-sensitive", serialized)
        self.assertNotIn("AAAA-sensitive", serialized)
        self.assertIn("<redacted audio data>", serialized)

    def test_failed_download_removes_part_file(self):
        destination = self.temp_dir / "audio.wav"
        session = FakeSession(
            get_responses=[FakeResponse(200, content=b"<html>error</html>")]
        )

        def reject_file(_):
            raise MODULE.ValidationError("not audio")

        with self.assertRaisesRegex(MODULE.ValidationError, "not audio"):
            MODULE.download_audio(
                session,
                "https://audio.invalid/test.wav",
                destination,
                validator=reject_file,
                sleeper=lambda _: None,
            )

        self.assertFalse(destination.exists())
        self.assertFalse(destination.with_name("audio.wav.part").exists())

    def test_probe_rejects_non_audio_file(self):
        path = self.temp_dir / "fake.wav"
        path.write_text("html error page", encoding="utf-8")
        completed = mock.Mock(returncode=1, stdout="", stderr="Invalid data")
        with mock.patch.object(MODULE.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(MODULE.ValidationError, "ffprobe"):
                MODULE.probe_audio(path)

    def test_compile_command_writes_prompt_without_credentials(self):
        source = self.temp_dir / "input.md"
        output = self.temp_dir / "prompt.txt"
        source.write_text("主持人：大家好。", encoding="utf-8")

        result = MODULE.main(
            [
                "compile",
                "--mode",
                "podcast",
                "--prompt-file",
                str(source),
                "--output",
                str(output),
            ]
        )

        self.assertEqual(result, 0)
        self.assertIn("播客", output.read_text(encoding="utf-8"))

    def test_doctor_reports_missing_setup_without_values(self):
        stdout = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(
            stdout
        ):
            result = MODULE.main(["doctor"])

        self.assertNotEqual(result, 0)
        self.assertIn("DASHSCOPE_API_KEY", stdout.getvalue())
        self.assertIn("未设置", stdout.getvalue())

    def test_write_report_redacts_credentials_and_audio_data(self):
        report = {
            "endpoint": "https://workspace-sensitive.cn-beijing.maas.aliyuncs.com",
            "authorization": "Bearer secret-key",
            "request": {
                "references": [
                    {"audio_data": "data:audio/wav;base64,AAAA-sensitive"}
                ]
            },
            "request_id": "req-123",
            "validation": {"ffprobe": "pass", "ffmpeg": "pass"},
        }

        json_path, markdown_path = MODULE.write_report(
            self.temp_dir, report, ["secret-key", "workspace-sensitive"]
        )
        combined = json_path.read_text(encoding="utf-8") + markdown_path.read_text(
            encoding="utf-8"
        )

        self.assertNotIn("secret-key", combined)
        self.assertNotIn("workspace-sensitive", combined)
        self.assertNotIn("AAAA-sensitive", combined)
        self.assertIn("req-123", combined)


if __name__ == "__main__":
    unittest.main()
