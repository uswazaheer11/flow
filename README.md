# Google Flow Automation

Python browser automation for Google Flow using an authenticated IXBrowser profile, Playwright, and CDP.

## Current Goal

```text
IXBrowser profile → Google Flow → image generation → image download → native Animate → video generation → 720p / Original size video download
```

Long-term: multiple IXBrowser profiles → job queue → Tauri 2 desktop app → real-time status.

## Status

Working: IXBrowser opening, CDP connection, Flow navigation, image generation/detection/download, 1K selection, native Animate, video generation start, video result detection.

Needs verification/fixing: video download helper, exact 720p selection, queue-aware handling, complete single-profile E2E.

## Configuration

```python
PROFILE_ID = 3878
IX_API = "http://127.0.0.1:53200/api/v2/profile-open"
FLOW_URL = "https://flow.google.com/"
BASE_DIR = Path(r"C:\Users\Uswa\Desktop\flow")
```

## Image Pipeline

```text
PROMPT → Flow Generate → image tiles → deduplicate → right click → Download → 1K → local JPEG
```

Working image code must not be removed.

## Video Pipeline

```text
generated image → Animate → VIDEO_PROMPT → Generate → queued/generating → video tile → Download → 720p / Original size → local video
```

## Queue Handling

Flow can report that a video has been scheduled and is waiting in the queue due to high demand. This is pending, not completed. `Stop disappeared` does not mean `video ready`.

## Video Download Options

```text
270p — Animated GIF
720p — Original size
1080p — Upscale
4K — Upscale
```

Select 720p explicitly.

## Timing

```python
VIDEO_MINIMUM_WAIT = 180
VIDEO_RESULT_EXTRA_TIMEOUT = 420
```

## Diagnostics

Preserve `ANIMATE_VIDEO_NOT_FOUND.png` and `ANIMATE_VIDEO_NOT_FOUND.txt` on video detection failure.

## Known Bug

A real run reached a video tile but failed because `find_animate_video_download_item` was not defined. The helper must find the visible Flow menuitem named Download.

## Roadmap

1. Single-profile E2E stability
2. Retries/state machine/structured logs/recovery
3. Multiple IXBrowser profiles and worker queue
4. Tauri 2 real-time desktop UI

## Project Memory

Read `ai/memory/project_state.md` before continuing work.
