"""Public Google Drive listing and explicitly selected file downloads."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import gdown


def drive_link(url: str) -> tuple[str, bool]:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or parsed.hostname not in {"drive.google.com", "docs.google.com"}:
        raise ValueError("Use a public Google Drive file or folder link.")
    folder = re.search(r"/folders/([\w-]+)", parsed.path)
    file = re.search(r"/d/([\w-]+)", parsed.path)
    file_id = folder.group(1) if folder else file.group(1) if file else parse_qs(parsed.query).get("id", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
        raise ValueError("The Google Drive link has no valid file ID.")
    return file_id, bool(folder)


def safe_relative_path(name: str, file_id: str) -> Path:
    """Keep folder structure without trusting Drive names as local paths."""
    parts = []
    for raw in name.replace("\\", "/").split("/"):
        if raw in {"", ".", ".."}:
            continue
        part = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw).strip(" .")[:120] or "file"
        if re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part):
            part = "_" + part
        parts.append(part)
    path = Path(*parts) if parts else Path("file")
    identity = re.sub(r"[^A-Za-z0-9_-]", "", file_id)
    return path.with_name(f"{path.stem} [{identity}]{path.suffix}")


def list_public_drive(url: str) -> dict:
    file_id, folder = drive_link(url)
    options = dict(quiet=True, use_cookies=False, skip_download=True, timeout=30)
    if folder:
        files = gdown.download_folder(url=url, **options)
    else:
        item = gdown.download(url=url, **options)
        files = [item] if item else []
    if not files:
        raise ValueError("No downloadable files found. Use a non-empty folder shared with anyone who has the link.")
    entries = []
    for index, item in enumerate(files, 1):
        entries.append({"index": index, "title": item.path, "media_id": item.id,
                        "target": url if not folder else f"https://drive.google.com/file/d/{item.id}/view",
                        "relative_path": str(safe_relative_path(item.path, item.id))})
    return {"title": "Google Drive" if folder else entries[0]["title"], "platform": "Google Drive",
            "target": url, "original_url": url, "media_id": file_id, "is_playlist": folder,
            "playlist_count": len(entries), "playlist_entries": entries, "drive_files": entries,
            "selected_indices": [] if folder else [1], "thumbnail": b""}


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        drive_link(args.url)
        last_percent = -1

        def progress(current, total):
            nonlocal last_percent
            percent = int(current * 100 / total) if total else -1
            if percent != last_percent:
                last_percent = percent
                print(f"[Drive] {percent}% · {current / 1048576:.1f} MiB", flush=True)

        result = gdown.download(url=args.url, output=str(args.output),
                                use_cookies=False, quiet=True, timeout=30, retries=2, progress=progress)
        if not result or not args.output.is_file():
            raise RuntimeError("Google Drive did not return a file.")
        return 0
    except Exception as exc:
        print(f"ERROR: Google Drive: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
