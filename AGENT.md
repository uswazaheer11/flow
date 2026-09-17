# AGENT.md

## Project

Google Flow browser automation using Python, Playwright, IXBrowser, and Chrome DevTools Protocol (CDP).

Repository: `uswazaheer11/flow`
Main script: `flow12.py`

## Goal

Build a reliable pipeline:

IXBrowser authenticated profile → Google Flow → image generation → local image download → native Animate → video generation/queue → 720p video download → later Tauri 2 real-time UI → eventually multiple profiles.

Current priority: stabilize one profile before scaling.

## Hard Rules

1. Never remove working image-generation/download code unless explicitly requested.
2. Prefer surgical fixes over rewriting the whole script.
3. Preserve old code when modifying `flow12.py`.
4. Do not replace Flow native Animate with a generic upload/model workflow unless explicitly requested.
5. Do not claim a fix is verified unless it was actually executed.
6. Prefer visible text, ARIA roles, bounding boxes, and fallbacks over fragile generated CSS classes.
7. Preserve screenshots/text diagnostics when automation fails.
8. Check duplicate function definitions because Python uses the last definition.

## Current Configuration

```python
PROFILE_ID = 3878
IX_API = "http://127.0.0.1:53200/api/v2/profile-open"
FLOW_URL = "https://flow.google.com/"
BASE_DIR = Path(r"C:\Users\Uswa\Desktop\flow")
DOWNLOAD_DIR = BASE_DIR / "downloads"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
```

Current video timing:

```python
VIDEO_MINIMUM_WAIT = 180
VIDEO_RESULT_EXTRA_TIMEOUT = 420
```

## Protected Image Workflow

Preserve these working functions:

`get_large_visible_images`, `deduplicate_images`, `print_images`, `right_click_image`, `find_download_menu_item`, `hover_download_menu_item`, `find_1k_option`, `wait_for_1k_option`, `make_download_path`, `download_one_image`.

Working flow: image → right click → Download → hover Download → 1K / Original size → expect_download → local JPEG.

## Video Workflow

Preferred path:

generated Flow image → right click → Animate → VIDEO_PROMPT → Generate → queue/generation → result tile → Download → 720p / Original size.

Flow may report that the video is scheduled and waiting in the queue due to high demand. That is pending, not completion. `Stop` disappearing is not proof that the video is ready.

## Video Download

Required quality: **720p — Original size**. Do not silently fall back to 1080p or 4K.

## Known Bug

A real run detected a video but failed with `name 'find_animate_video_download_item' is not defined`. The helper must locate a visible Flow menuitem named Download.

## Diagnostics

On video detection failure preserve `ANIMATE_VIDEO_NOT_FOUND.png` and `ANIMATE_VIDEO_NOT_FOUND.txt`.

## Testing

Test one profile first: open IXBrowser → CDP → Flow → images → image downloads → Animate → video queue → video tile → Download → 720p → local video.

Only then scale to multiple profiles.
