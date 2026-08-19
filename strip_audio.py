from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _ffmpeg_path() -> str:
    bundled = Path.home() / ".ytDownloader" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled.is_file():
        return str(bundled)
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        executable = shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
        if executable:
            return executable
        raise RuntimeError("FFmpeg was not found.")


def strip_audio(source: Path, workspace: Path | None = None) -> int:
    if not source.is_file():
        return 2
    try:
        ffmpeg = _ffmpeg_path()
    except RuntimeError:
        return 2
    workspace = workspace or source.parent
    workspace.mkdir(parents=True, exist_ok=True)
    original = workspace / f"{source.stem}.original{source.suffix}"
    temporary = workspace / f"{source.stem}.silent{source.suffix}"
    try:
        os.replace(source, original)
    except OSError:
        return 2
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(original),
        "-map",
        "0:v:0",
        "-c:v",
        "copy",
        "-an",
        "-map_metadata",
        "0",
        str(temporary),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            creationflags=creation_flags,
        )
    except OSError:
        try:
            os.replace(original, source)
        except OSError:
            pass
        return 2
    if completed.returncode == 0 and temporary.is_file():
        os.replace(temporary, source)
        try:
            original.unlink()
        except FileNotFoundError:
            pass
        return 0
    try:
        temporary.unlink()
    except FileNotFoundError:
        pass
    # A post-processing error should not destroy an otherwise complete video.
    try:
        os.replace(original, source)
    except OSError:
        pass
    return completed.returncode or 1


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(2)
    workspace = Path(sys.argv[2]) if len(sys.argv) == 3 else None
    raise SystemExit(strip_audio(Path(sys.argv[1]), workspace))
