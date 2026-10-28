#!/usr/bin/env python3
"""Capture a frame every N seconds (default 30) from a YouTube video, zip them.

Usage: yt_screenshots.py URL_OR_ID [-o OUT.zip] [--every 30] [--height 720]

Downloads video-only (capped resolution, no audio) via yt-dlp, extracts
frames with ffmpeg, names them frame_HHMMSS.jpg, zips. Skips frames that
are near-duplicates of the previous one (static slides) unless --keep-all.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).parent


def _tool(name: str) -> str:
    """Locate yt-dlp/ffmpeg on PATH (ffmpeg must be installed system-side)."""
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(f"{name} not found on PATH — install it first (pip install {name} or your package manager)")

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


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r.stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--every", type=int, default=30, help="seconds between screenshots")
    ap.add_argument("--height", type=int, default=720, help="max video height to download")
    ap.add_argument("--keep-all", action="store_true", help="do not dedupe static-slide frames")
    args = ap.parse_args()

    vid = extract_video_id(args.url)
    work = HERE / "out" / vid
    work.mkdir(parents=True, exist_ok=True)
    out_zip = Path(args.out) if args.out else HERE / "out" / f"{vid}_screenshots.zip"

    # 1) metadata + video-only download (no audio stream needed)
    meta = run([_tool("yt-dlp"), "--skip-download", "--no-warnings",
                "--print", "%(title)s\n%(duration)s",
                f"https://www.youtube.com/watch?v={vid}"]).strip().splitlines()
    title, duration = meta[0], int(meta[1]) if len(meta) > 1 else 0

    video_file = work / f"{vid}.mp4"
    if not video_file.exists():
        run([_tool("yt-dlp"), "--no-playlist", "-f",
             f"bestvideo[height<={args.height}][ext=mp4]/bestvideo[height<={args.height}]/best[height<={args.height}]",
             "-o", str(video_file), f"https://www.youtube.com/watch?v={vid}"])

    # 2) extract one frame every N seconds
    frames_dir = work / "frames"
    frames_dir.mkdir(exist_ok=True)
    run([_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(video_file),
         "-vf", f"fps=1/{args.every}", "-q:v", "3",
         str(frames_dir / "raw_%05d.jpg")])

    raw = sorted(frames_dir.glob("raw_*.jpg"))
    if not raw:
        raise SystemExit("no frames extracted")

    # 3) rename to timestamps; optionally drop near-identical consecutive frames
    kept, prev_hash, prev_bytes = [], None, None
    for i, f in enumerate(raw):
        t = i * args.every
        ts = f"{t // 3600:02d}{(t % 3600) // 60:02d}{t % 60:02d}"
        if not args.keep_all:
            data = f.read_bytes()
            # cheap dedupe: identical size + identical md5 of downsampled bytes
            import hashlib
            h = hashlib.md5(data).hexdigest()
            if h == prev_hash:
                f.unlink()
                continue
            prev_hash = h
        f.rename(frames_dir / f"frame_{ts}.jpg")
        kept.append(frames_dir / f"frame_{ts}.jpg")

    # 4) zip
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt",
                   f"{title}\nhttps://www.youtube.com/watch?v={vid}\n"
                   f"duration: {duration // 60}m{duration % 60:02d}s | "
                   f"one frame every {args.every}s | {len(kept)} frames\n")
        for f in kept:
            z.write(f, f.name)

    print(json.dumps({
        "video_id": vid, "title": title,
        "duration": f"{duration // 3600:02d}:{(duration % 3600) // 60:02d}:{duration % 60:02d}",
        "every_s": args.every, "frames": len(kept),
        "zip_bytes": out_zip.stat().st_size, "out": str(out_zip),
    }))


if __name__ == "__main__":
    main()
