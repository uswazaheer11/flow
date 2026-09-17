# Project State Memory

## Repository

`uswazaheer11/flow`

Main script: `flow12.py`

Stack: Python, Playwright Sync API, IXBrowser, CDP, Google Flow, future Tauri 2.

## Long-Term Goal

multiple authenticated IXBrowser profiles → Flow image generation → local image downloads → native Animate → queued video generation → local 720p video downloads → real-time Tauri 2 UI.

Current priority: one profile, one script, stable E2E first.

## Current Configuration

```text
PROFILE_ID = 3878
IX_API = http://127.0.0.1:53200/api/v2/profile-open
FLOW_URL = https://flow.google.com/
BASE_DIR = C:\Users\Uswa\Desktop\flow
DOWNLOAD_DIR = C:\Users\Uswa\Desktop\flow\downloads
SCREENSHOT_DIR = C:\Users\Uswa\Desktop\flow\screenshots
```

## Completed

- IXBrowser opening works.
- Playwright CDP attachment works.
- Flow opens successfully.
- Image generation/detection/filtering works.
- Native image download and 1K selection work.
- Two images were successfully downloaded in a real run.
- Native Animate opens.
- Animate prompt can be filled.
- Video generation can be started.
- Video result detection can work; a real run reached `Generated video result detected: 1` and exposed a direct video source.

## Protected Image Functions

`get_large_visible_images`, `deduplicate_images`, `print_images`, `right_click_image`, `find_download_menu_item`, `hover_download_menu_item`, `find_1k_option`, `wait_for_1k_option`, `make_download_path`, `download_one_image`.

## Current Problems

### Missing video download helper

Observed runtime error: `name 'find_animate_video_download_item' is not defined`.

### 720p verification

Required: `720p — Original size`.

### Queue handling

Flow can show: `Your video has been scheduled and is waiting in the queue due to high demand.` This is pending. `Stop disappeared` is not proof of readiness.

## Timing

```python
VIDEO_MINIMUM_WAIT = 180
VIDEO_RESULT_EXTRA_TIMEOUT = 420
```

## Diagnostics

Keep `ANIMATE_VIDEO_NOT_FOUND.png` and `ANIMATE_VIDEO_NOT_FOUND.txt`.

## Duplicate Definition Warning

`run_video_pipeline()` has appeared more than once. Python uses the final definition.

## Next Work

1. Ensure `find_animate_video_download_item()` exists.
2. Ensure `download_animate_video()` selects 720p / Original size.
3. Make queue state explicit.
4. Run single-profile full E2E.
5. Verify a local video file.
6. Record the result here.
7. Only then start multi-profile/Tauri work.

## User Code-Change Requirement

Preserve old code. Do not remove image code. Prefer additions/surgical replacements. If a full file is requested, preserve the complete source and apply only requested changes. Never claim 100% working without a real test.

## Current State

```text
IXBrowser opening       DONE
CDP attachment          DONE
Flow opening            DONE
Image generation        DONE
Image detection         DONE
Image download          DONE
Native Animate           DONE
Video start             DONE
Video result detection  DONE
Video download helper   FIX/VERIFY
720p download           VERIFY
Queue handling          HARDEN
Single-profile E2E      NEXT
Multi-profile           LATER
Tauri 2                 LATER
```
