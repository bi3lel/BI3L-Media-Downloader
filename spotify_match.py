"""Conservative matching of Spotify metadata to public audio candidates."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalized(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )).split())


def versions(title: str) -> set[str]:
    words = set(normalized(title).split())
    return words & {"live", "remix", "remastered", "remaster", "cover", "karaoke", "instrumental", "acoustic", "sped", "slowed", "nightcore", "clean", "explicit", "edit"}


def rank_candidates(track: dict, candidates: list[dict]) -> list[dict]:
    title = normalized(str(track.get("title") or ""))
    artists = [normalized(a) for a in re.split(r",|;", str(track.get("artists") or "")) if normalized(a)]
    duration = float(track.get("duration") or 0)
    ranked = []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        video_id = str(item.get("id") or "")
        if not re.fullmatch(r"[\w-]{11}", video_id) or video_id in seen:
            continue
        seen.add(video_id)
        candidate_title = normalized(str(item.get("title") or ""))
        channel = normalized(str(item.get("channel") or item.get("uploader") or ""))
        haystack = f" {candidate_title} {channel} "
        artist_match = bool(artists) and all(f" {artist} " in haystack for artist in artists)
        artist_channel = re.sub(r"\s*(topic|vevo)$", "", channel).strip()
        official_artist = bool(artists) and (artist_channel in artists or normalized(str(item.get("artist") or "")) in artists)
        # Remove attribution and presentation labels, not version qualifiers.
        clean = candidate_title
        for artist in artists:
            clean = re.sub(rf"\b{re.escape(artist)}\b", " ", clean)
        clean = re.sub(r"\b(official|audio|video|lyrics|lyric|visualizer|hd|hq|4k)\b", " ", clean)
        clean = " ".join(clean.split())
        title_score = SequenceMatcher(None, title, clean).ratio() if title else 0
        actual_duration = float(item.get("duration") or 0)
        duration_match = duration > 0 and actual_duration > 0 and abs(duration - actual_duration) <= max(3, duration * 0.015)
        version_match = versions(str(track.get("title") or "")) == versions(str(item.get("title") or ""))
        album = normalized(str(track.get("album") or ""))
        candidate_album = normalized(str(item.get("album") or ""))
        album_match = not album or not candidate_album or album == candidate_album
        score = title_score * 50 + artist_match * 30 + duration_match * 20
        confident = title_score >= 0.94 and artist_match and official_artist and duration_match and version_match and album_match
        ranked.append({**item, "target": f"https://www.youtube.com/watch?v={video_id}",
                       "score": score, "confident": confident})
    return sorted(ranked, key=lambda item: (item["confident"], item["score"]), reverse=True)


def automatic_candidate(ranked: list[dict]) -> dict | None:
    if not ranked or not ranked[0]["confident"]:
        return None
    # Equally convincing sources/versions require a human choice.
    if len(ranked) > 1 and ranked[1]["score"] >= ranked[0]["score"] - 5:
        return None
    return ranked[0]
