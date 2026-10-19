"""Voice agent + launch-shortcut tests (voice.py, autostart.py, their routes).

No model is loaded and no shortcut is written: the engines and the PowerShell
call are mocked, so this runs offline and leaves the desktop untouched.

    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("REGALIA_UPDATE_CHECK", "0")
DASHBOARD_DIR = Path(__file__).resolve().parent.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import app as dashboard_app  # noqa: E402
import autostart  # noqa: E402
import config  # noqa: E402
import voice  # noqa: E402


class WakeSplitTests(unittest.TestCase):
    def test_wake_word_variants_are_recognized(self):
        for text, command in [
            ("Regalia, what's due this week?", "what's due this week?"),
            ("Hey Regalia what's on my calendar", "what's on my calendar"),
            ("OK so regalia. Open settings.", "Open settings."),
            ("Ragalia, open the inbox", "open the inbox"),       # Whisper misspelling
            ("Re galia show my to-dos", "show my to-dos"),       # split in two
        ]:
            with self.subTest(text=text):
                self.assertEqual(voice.wake_split(text), (True, command))

    def test_bare_wake_word_has_empty_command(self):
        self.assertEqual(voice.wake_split("Regalia."), (True, ""))

    def test_other_speech_is_ignored(self):
        for text in ["", "Thank you.", "We should really go to the gala later",
                     "I was telling my friend that Regalia is neat"]:
            with self.subTest(text=text):
                self.assertFalse(voice.wake_split(text)[0])


class TranscribeTests(unittest.TestCase):
    def test_empty_and_oversized_clips_are_rejected(self):
        with self.assertRaises(voice.VoiceError) as cm:
            voice.transcribe(b"")
        self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(voice.VoiceError) as cm:
            voice.transcribe(b"x" * (voice.MAX_AUDIO_BYTES + 1))
        self.assertEqual(cm.exception.status, 413)

    def test_no_engine_is_a_503_with_guidance(self):
        with mock.patch.object(voice, "_local_available", return_value=False), \
                mock.patch.object(voice, "_openai_key", return_value=""):
            self.assertFalse(voice.status()["ready"])
            with self.assertRaises(voice.VoiceError) as cm:
                voice.transcribe(b"RIFF....")
        self.assertEqual(cm.exception.status, 503)

    def test_local_engine_is_preferred(self):
        with mock.patch.object(voice, "_local_available", return_value=True), \
                mock.patch.object(voice, "_openai_key", return_value="sk-test"), \
                mock.patch.object(voice, "_transcribe_local", return_value="hi") as local, \
                mock.patch.object(voice, "_transcribe_openai") as remote:
            self.assertEqual(voice.transcribe(b"RIFF"), {"text": "hi", "engine": "local"})
        local.assert_called_once()
        remote.assert_not_called()


class VoiceRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = dashboard_app.app.test_client()

    def test_status_route(self):
        r = self.client.get("/api/voice/status")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ready", r.get_json())

    def test_transcribe_route_reports_wake(self):
        with mock.patch.object(voice, "transcribe",
                               return_value={"text": "Regalia, open chat", "engine": "local"}):
            r = self.client.post("/api/voice/transcribe?wake=1", data=b"RIFF",
                                 content_type="audio/wav")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["wake"])
        self.assertEqual(d["command"], "open chat")

    def test_transcribe_route_maps_errors(self):
        r = self.client.post("/api/voice/transcribe", data=b"", content_type="audio/wav")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.get_json())

    def test_voice_settings_are_booleans(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(config, "CONFIG_PATH", Path(tmp) / "c.json"):
            cfg = config.update({"voice_wake": 1, "voice_speak": 0, "whisper_model": " small.en "})
            self.assertIs(cfg["voice_wake"], True)
            self.assertIs(cfg["voice_speak"], False)
            self.assertEqual(cfg["whisper_model"], "small.en")

    def test_page_carries_the_voice_ui(self):
        body = self.client.get("/").get_data(as_text=True)
        for marker in ('id="voice-btn"', 'id="voice-panel"', "function voiceMicClick",
                       'id="stg-launch-login"', 'id="stg-launch-desktop"'):
            self.assertIn(marker, body)


class BootSplashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = dashboard_app.app.test_client()

    def test_voice_warm_never_errors_without_an_engine(self):
        with mock.patch.object(voice, "_local_available", return_value=False), \
                mock.patch.object(voice, "_openai_key", return_value=""):
            r = self.client.post("/api/voice/warm")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["warm"])

    def test_voice_warm_reports_a_failed_load(self):
        with mock.patch.object(voice, "_local_available", return_value=True), \
                mock.patch.object(voice, "warm", side_effect=OSError("offline")):
            d = self.client.post("/api/voice/warm").get_json()
        self.assertFalse(d["warm"])
        self.assertIn("offline", d["error"])

    def test_page_carries_the_loading_screen(self):
        body = self.client.get("/").get_data(as_text=True)
        # Visible from first paint (no `hidden`), removed by its own script block.
        self.assertIn('<div class="boot" id="boot" role="status"', body)
        self.assertIn("(function bootSplash()", body)
        self.assertIn("window.__boot = {", body)
        # The splash's script must be its own block, after everything it calls.
        self.assertGreater(body.index("(function bootSplash()"), body.index("function loadAgents()"))

    def test_desktop_shell_doesnt_import_the_app_up_front(self):
        src = (DASHBOARD_DIR / "desktop.py").read_text(encoding="utf-8")
        self.assertNotIn("\nfrom app import app", src)
        self.assertIn("webview.start(_boot", src)


@unittest.skipUnless(sys.platform == "win32", "launch shortcuts are Windows-only")
class AutostartTests(unittest.TestCase):
    def test_source_run_targets_the_windowless_desktop_shell(self):
        with mock.patch.object(autostart.paths, "is_frozen", return_value=False), \
                mock.patch.object(autostart, "_icon_path", return_value=""):
            t = autostart.launch_target()
        self.assertIn("desktop.py", t["args"])
        self.assertEqual(Path(t["workdir"]), DASHBOARD_DIR)

    def test_enable_writes_through_powershell_and_disable_deletes(self):
        with tempfile.TemporaryDirectory() as tmp:
            startup = Path(tmp)
            with mock.patch.object(autostart, "startup_dir", return_value=startup), \
                    mock.patch.object(autostart, "_icon_path", return_value=""), \
                    mock.patch.object(autostart, "_ps") as ps:
                autostart.set_shortcut("login", True)
                env = ps.call_args.args[1]
                self.assertEqual(env["RG_LINK"], str(startup / "Regalia.lnk"))
                (startup / "Regalia.lnk").write_text("x")
                autostart.set_shortcut("login", False)
            self.assertFalse((startup / "Regalia.lnk").exists())

    def test_route_rejects_non_object_and_reports_state(self):
        client = dashboard_app.app.test_client()
        fake = {"supported": True, "login": False, "desktop": True}
        with mock.patch.object(autostart, "state", return_value=fake), \
                mock.patch.object(autostart, "set_shortcut") as setter:
            self.assertEqual(client.post("/api/system/launch", json=[1]).status_code, 400)
            r = client.post("/api/system/launch", json={"login": True})
        self.assertEqual(r.get_json(), fake)
        setter.assert_called_once_with("login", True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
