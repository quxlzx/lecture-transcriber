# lecture-transcriber

Turn long YouTube lecture videos into two artifacts, in seconds:

1. **`yt_transcribe.py`** — the full transcript as a timestamped Markdown file
2. **`yt_screenshots.py`** — one screenshot every N seconds (default 30) as a zip, perfect for slide-based lectures

No speech-to-text needed: the transcriber pulls YouTube's own caption track
(manual preferred, auto-generated fallback), so a **2-hour lecture takes ~3
seconds** and ~150 KB of Markdown.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# screenshots also need ffmpeg on PATH:
#   apt install ffmpeg   /   brew install ffmpeg
```

## Usage

```bash
# Transcript → Markdown (title header + [HH:MM:SS] paragraphs)
python yt_transcribe.py "https://youtu.be/VIDEO_ID"
python yt_transcribe.py VIDEO_ID -o notes.md --lang en,ko

# Slide screenshots → zip (frame_HHMMSS.jpg every 30s + README)
python yt_screenshots.py "https://youtu.be/VIDEO_ID"
python yt_screenshots.py VIDEO_ID --every 60 --height 480   # smaller zip
```

Both print a one-line JSON summary (`title`, `language`, `frames`, `out`, …)
so they're easy to script.

## How it works

| Step | Transcript | Screenshots |
|---|---|---|
| Fetch | `youtube-transcript-api` caption track (no video download) | `yt-dlp` video-only stream, 720p cap, no audio |
| Build | groups segments into paragraphs, breaking at >2s pauses | `ffmpeg` grabs one frame every N seconds |
| Output | `out/<id>.md` | `out/<id>_screenshots.zip` |

A 1-hour lecture: transcript ≈ 3 s, screenshots ≈ 1 minute wall-clock
(~120 frames, ~15 MB zip).

## Notes

- If a video has captions disabled, the transcriber exits with `NO_CAPTIONS`
  — there is no audio fallback; run your own ASR if you need one.
- Language preference order: `en,ko,ja,zh-Hans,zh-Hant,es,fr,de`, then
  whatever exists. Override with `--lang`.
- YouTube may rate-limit heavy batch use; space requests out.
- Respect your institution's policies on downloading lecture content — these
  tools are for personal study.

## License

MIT — see [LICENSE](LICENSE).
