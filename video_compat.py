"""Convert downloaded MP4 streams to an editor-friendly encoding."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from functools import lru_cache

from strip_audio import _ffmpeg_path


ENCODERS = {
    "h264_nvenc": ["-preset", "p4", "-rc", "vbr", "-cq", "19", "-b:v", "0"],
    "h264_qsv": ["-preset", "veryfast", "-global_quality", "19"],
    "h264_amf": ["-quality", "speed", "-rc", "cqp", "-qp_i", "18", "-qp_p", "20"],
    "libx264": ["-preset", "veryfast", "-crf", "18"],
}


@lru_cache(maxsize=4)
def available_encoder(ffmpeg: str) -> str:
    """An advertised encoder may lack a GPU/driver. Test a real encode."""
    for encoder in ("h264_nvenc", "h264_qsv", "h264_amf"):
        try:
            result = subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
                 "-f", "lavfi", "-i", "color=size=640x360:rate=30",
                 "-frames:v", "2", "-c:v", encoder, *ENCODERS[encoder],
                 "-profile:v", "high", "-pix_fmt", "yuv420p", "-f", "null", "-"],
                capture_output=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                return encoder
        except (OSError, subprocess.TimeoutExpired):
            continue
    return "libx264"


def make_editor_mp4(source: Path, *, silent: bool = False) -> int:
    """Replace only after successful conversion; keep the download on failure."""
    source = source.resolve()
    temporary: Path | None = None
    try:
        if not source.is_file():
            raise OSError(f"Video not found: {source}")
        ffmpeg = _ffmpeg_path()
        encoder = available_encoder(ffmpeg)
        # Same directory guarantees atomic replacement, even if the download
        # workspace and destination are on different drives.
        handle, name = tempfile.mkstemp(prefix=".bi3l-convert-", suffix=".mp4", dir=source.parent)
        os.close(handle)
        temporary = Path(name)
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-i", str(source), "-map", "0:v:0",
            "-c:v", encoder, *ENCODERS[encoder],
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-fps_mode", "cfr", "-tag:v", "avc1",
        ]
        if silent:
            command += ["-an"]
        else:
            command += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
        command += ["-map_metadata", "0", "-movflags", "+faststart", str(temporary)]
        print(f"[EditorMP4] Converting video for editing ({encoder})...", flush=True)
        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        # Hardware can pass a small probe but fail on this resolution or run
        # out of encoder sessions. Retry from the untouched original on CPU.
        if completed.returncode and encoder != "libx264":
            print("[EditorMP4] Hardware encode failed; retrying on CPU...", flush=True)
            start = command.index("-c:v")
            end = command.index("-profile:v")
            command[start:end] = ["-c:v", "libx264", *ENCODERS["libx264"]]
            completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       text=True, encoding="utf-8", errors="replace",
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or "FFmpeg conversion failed")
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("FFmpeg produced an empty video")
        os.replace(temporary, source)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: MP4 conversion failed; original download kept. {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    raise SystemExit(make_editor_mp4(args.source, silent=args.silent))
