# CLAUDE.md

## Working Context

This project automates Google Flow through an already-authenticated IXBrowser profile using Python + Playwright + CDP.

Primary file: `flow12.py`

## Non-Negotiable Rules

- Do not delete working image code.
- Do not shorten the source by replacing it with an example.
- Prefer targeted patches.
- Preserve existing helpers unless explicitly asked to remove them.
- Native Flow Animate is the preferred video path.
- Do not claim testing that did not happen.
- Check duplicate function definitions before editing.
- Keep diagnostics on failures.

## Architecture

```text
IXBrowser → local API → debugging_address → Playwright CDP → Google Flow → image generation → image download → native Animate → video queue/generation → video tile → 720p / Original size download
```

## Protected Image Functions

`get_large_visible_images`, `deduplicate_images`, `print_images`, `right_click_image`, `find_download_menu_item`, `hover_download_menu_item`, `find_1k_option`, `wait_for_1k_option`, `make_download_path`, `download_one_image`.

Do not touch these while fixing video issues unless explicitly necessary.

## Video State

Treat `queued`, `generating`, `ready`, `downloading`, `completed`, and `failed` separately.

Queue text such as `waiting in the queue`, `scheduled`, or `due to high demand` means pending.

## Video Download

Target `720p — Original size`. Never silently select 1080p/4K.

## Known Missing Helper

Previous run: `name 'find_animate_video_download_item' is not defined`.

Restore/add the helper before `download_animate_video()` uses it. It should inspect visible menuitems and return Download.

## Duplicate Definitions

`flow12.py` has had duplicate `run_video_pipeline()` definitions. Python executes the last definition. Inspect all definitions before changing behavior.

## Debugging

On failure: screenshot → body text dump → roles/ARIA → bounding boxes → overlays/menus → queue/approval/error text → fallback selector → retry.

## Tauri Direction

Eventually expose events: `profile_opening`, `flow_open`, `image_generating`, `image_downloaded`, `animate_opening`, `video_queued`, `video_generating`, `video_ready`, `video_downloading`, `completed`, `failed`.
