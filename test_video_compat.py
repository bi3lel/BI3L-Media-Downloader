import subprocess
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from strip_audio import _ffmpeg_path
from video_compat import make_editor_mp4


class ConversionSafetyTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("video_compat.available_encoder", return_value="libx264")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_failures_preserve_original_and_remove_partial_output(self):
        for failure in (OSError("Cannot start FFmpeg"), subprocess.CompletedProcess([], 1, stderr="Encoder failed")):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "video.mp4"
                source.write_bytes(b"original download")

                def run(command, **kwargs):
                    Path(command[-1]).write_bytes(b"partial conversion")
                    if isinstance(failure, Exception):
                        raise failure
                    return failure

                with patch("video_compat._ffmpeg_path", return_value="ffmpeg"), patch("video_compat.subprocess.run", side_effect=run):
                    self.assertNotEqual(make_editor_mp4(source), 0)
                self.assertEqual(source.read_bytes(), b"original download")
                self.assertEqual(list(Path(directory).iterdir()), [source])

    def test_failed_replace_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "video.mp4"
            source.write_bytes(b"original download")

            def run(command, **kwargs):
                Path(command[-1]).write_bytes(b"converted video")
                return subprocess.CompletedProcess(command, 0, stderr="")

            with patch("video_compat._ffmpeg_path", return_value="ffmpeg"), patch("video_compat.subprocess.run", side_effect=run), patch("video_compat.os.replace", side_effect=OSError("File busy")):
                self.assertNotEqual(make_editor_mp4(source), 0)
            self.assertEqual(source.read_bytes(), b"original download")
            self.assertEqual(list(Path(directory).iterdir()), [source])


class FFmpegConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ffmpeg = _ffmpeg_path()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

    def run_ffmpeg(self, *args):
        return subprocess.run([self.ffmpeg, "-hide_banner", "-nostdin", "-y", *args], capture_output=True, text=True, check=True)

    def test_vp9_opus_mp4_becomes_h264_aac_and_decodes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Vídeo & test [1].mp4"
            self.run_ffmpeg("-f", "lavfi", "-i", "testsrc2=size=96x64:rate=30:duration=1", "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libvpx-vp9", "-c:a", "libopus", str(source))
            with patch("video_compat._ffmpeg_path", return_value=self.ffmpeg):
                self.assertEqual(make_editor_mp4(source), 0)
            decoded = self.run_ffmpeg("-i", str(source), "-f", "null", "-")
            self.assertIn("Video: h264 (High)", decoded.stderr)
            self.assertIn("yuv420p", decoded.stderr)
            self.assertRegex(decoded.stderr, r"Audio: aac \(LC\).*48000 Hz, stereo")
            self.assertEqual(list(Path(directory).iterdir()), [source])

    def test_10bit_video_and_silent_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "silent.mp4"
            self.run_ffmpeg("-f", "lavfi", "-i", "testsrc2=size=96x64:rate=24:duration=1", "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p10le", "-c:a", "aac", str(source))
            with patch("video_compat._ffmpeg_path", return_value=self.ffmpeg):
                self.assertEqual(make_editor_mp4(source, silent=True), 0)
                # Optional audio mapping must also accept video-only downloads.
                self.assertEqual(make_editor_mp4(source), 0)
            decoded = self.run_ffmpeg("-i", str(source), "-f", "null", "-")
            self.assertIn("Video: h264 (High)", decoded.stderr)
            self.assertIn("yuv420p", decoded.stderr)
            self.assertNotIn("Audio:", decoded.stderr)

    def test_variable_frame_rate_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "variable.mp4"
            self.run_ffmpeg("-f", "lavfi", "-i", "testsrc2=size=96x64:rate=30:duration=1", "-vf", r"select=not(eq(mod(n\,5)\,1))", "-fps_mode", "vfr", "-c:v", "libx264", str(source))

            def intervals():
                decoded = self.run_ffmpeg("-i", str(source), "-vf", "showinfo", "-f", "null", "-")
                times = [float(value) for value in re.findall(r"pts_time:([0-9.]+)", decoded.stderr)]
                self.assertGreater(len(times), 10)
                return {round(b - a, 4) for a, b in zip(times, times[1:])}

            self.assertGreater(len(intervals()), 1)
            with patch("video_compat._ffmpeg_path", return_value=self.ffmpeg):
                self.assertEqual(make_editor_mp4(source), 0)
            self.assertEqual(len(intervals()), 1)

    def test_av1_mp4_is_converted_even_with_mp4_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "av1.mp4"
            self.run_ffmpeg("-f", "lavfi", "-i", "testsrc2=size=96x64:rate=24:duration=0.5", "-c:v", "libaom-av1", "-cpu-used", "8", str(source))
            with patch("video_compat._ffmpeg_path", return_value=self.ffmpeg):
                self.assertEqual(make_editor_mp4(source), 0)
            decoded = self.run_ffmpeg("-i", str(source), "-f", "null", "-")
            self.assertIn("Video: h264 (High)", decoded.stderr)


if __name__ == "__main__":
    unittest.main()
