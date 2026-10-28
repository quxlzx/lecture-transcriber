#!/usr/bin/env python3
"""Fetch a full YouTube transcript and write it as a timestamped Markdown file.

Usage: yt_transcribe.py URL_OR_ID [-o OUT.md] [--lang en,...]

Prefers manual captions, falls back to auto-generated. Groups segments into
readable paragraphs, breaking on >2s silence gaps. Exits non-zero with a
clear message when captions are unavailable (caller can fall back to ASR).
"""
import argparse
import json
import re
import sys
from pathlib import Path

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(s: str) -> str:
    s = s.strip()
    if VIDEO_ID_RE.match(s):
        return s
    m = re.search(
        r"(?:youtube\.com/(?:watch\?v=|embed/|live/|shorts/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})",
        s,
    )
    if m:
        return m.group(1)
    raise SystemExit(f"could not extract a video id from: {s!r}")


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _tool(name: str) -> str:
    """Locate yt-dlp/ffmpeg: PATH first, then a sibling .venv/bin, then give up."""
    import shutil

    found = shutil.which(name)
    if found:
        return found
    local = Path(__file__).parent / ".venv" / "bin" / name
    if local.exists():
        return str(local)
    raise SystemExit(f"{name} not found on PATH — install it (pip install {name}) or add it to PATH")


def metadata(video_id: str) -> dict:
    """Best-effort metadata via yt-dlp (skip download). Never fatal."""
    try:
        import subprocess

        out = subprocess.run(
            [_tool("yt-dlp"),
             "--skip-download", "--no-warnings", "--print",
             "%(title)s\n%(channel)s\n%(duration_string)s\n%(upload_date)s",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=60,
        )
        lines = out.stdout.strip().splitlines()
        if len(lines) >= 3:
            return {"title": lines[0], "channel": lines[1],
                    "duration": lines[2], "upload_date": lines[3] if len(lines) > 3 else ""}
    except Exception:
        pass
    return {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--lang", default="en,ko,ja,zh-Hans,zh-Hant,es,fr,de")
    args = ap.parse_args()

    video_id = extract_video_id(args.url)

    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    langs = [l.strip() for l in args.lang.split(",") if l.strip()]

    try:
        tl = api.list(video_id)
    except Exception as e:
        raise SystemExit(f"transcript listing failed for {video_id}: {e}")

    transcript = None
    tried = set()
    for want in langs:
        try:
            transcript = tl.find_transcript([want] + [l for l in langs if l != want])
            break
        except Exception:
            tried.add(want)
    if transcript is None:
        # last resort: whatever is available
        try:
            transcript = next(iter(tl))
        except StopIteration:
            raise SystemExit(
                f"NO_CAPTIONS: {video_id} has no captions at all "
                f"(tried: {', '.join(langs)}). Needs audio transcription instead."
            )

    fetched = transcript.fetch()
    segs = [(s.start, s.text) for s in fetched]
    if not segs:
        raise SystemExit(f"NO_CAPTIONS: transcript for {video_id} came back empty.")

    lang = transcript.language_code
    generated = transcript.is_generated

    # group into paragraphs: break on >2s gap or when paragraph >= ~45 words
    paragraphs, cur, cur_start, words = [], [], 0.0, 0
    for start, text in segs:
        if cur and (start - prev_end > 2.0 or words >= 45):
            paragraphs.append((cur_start, " ".join(cur)))
            cur, words = [], 0
        if not cur:
            cur_start = start
        cur.append(text.strip())
        words += len(text.split())
        prev_end = start
    if cur:
        paragraphs.append((cur_start, " ".join(cur)))

    meta = metadata(video_id)
    title = meta.get("title") or video_id
    out_path = Path(args.out) if args.out else Path(__file__).parent / "out" / f"{video_id}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dur = meta.get("duration", "")
    if not dur and segs:
        dur = fmt_ts(segs[-1][0])
    lines = [
        f"# {title}",
        "",
        f"- **Video:** https://www.youtube.com/watch?v={video_id}",
        f"- **Channel:** {meta.get('channel', '?')}",
        f"- **Duration:** {dur}",
        f"- **Captions:** {'auto-generated' if generated else 'manual'} ({lang})",
        f"- **Transcript paragraphs:** {len(paragraphs)}",
        "",
        "---",
        "",
    ]
    for start, text in paragraphs:
        lines.append(f"**[{fmt_ts(start)}]** {text}")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "video_id": video_id, "title": title, "language": lang,
        "generated": generated, "paragraphs": len(paragraphs),
        "chars": out_path.stat().st_size, "out": str(out_path),
    }))


if __name__ == "__main__":
    main()
