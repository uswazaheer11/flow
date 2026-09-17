import time
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# CONFIG
# ============================================================

PROFILE_ID = 3878

IX_OPEN_URL = "http://127.0.0.1:53200/api/v2/profile-open"

FLOW_URL = "https://flow.google.com/"

PROMPT = """A cinematic historical scene of an ancient Roman city at sunset,
wide establishing shot, realistic architecture, dramatic lighting,
documentary style, highly detailed."""

BASE_DIR = Path(__file__).resolve().parent

DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

SCREENSHOT_DIR = BASE_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Generation wait
MAX_GENERATION_SECONDS = 300

# Extra time after generation finishes.
# Useful when Flow/Agent produces 2 images.
EXTRA_RESULT_WAIT_SECONDS = 20


# ============================================================
# IXBROWSER
# ============================================================

def open_ixbrowser_profile():

    response = requests.post(
        IX_OPEN_URL,
        json={
            "profile_id": PROFILE_ID,
            "args": [
                "--disable-extension-welcome-page"
            ],
            "load_extensions": True,
            "load_profile_info_page": True,
            "cookies_backup": True,
            "cookie": ""
        },
        timeout=30
    )

    print("    HTTP:", response.status_code)

    response.raise_for_status()

    data = response.json()["data"]

    print("[OK] IXBrowser profile opened")
    print("     CDP:", data["debugging_address"])

    return data["debugging_address"]


# ============================================================
# HELPERS
# ============================================================

def is_visible(locator):

    try:

        if locator.count() == 0:
            return False

        return locator.first.is_visible()

    except Exception:
        return False


def get_flow_page(browser):

    context = browser.contexts[0]

    pages = context.pages

    print("[OK] Existing pages:", len(pages))

    for i, page in enumerate(pages):
        print(f"    [{i}] {page.url}")

    # Prefer existing Flow page
    for page in pages:

        if "flow.google.com" in page.url:
            return page

    return pages[0]


# ============================================================
# NEW PROJECT
# ============================================================

def click_new_project(page):

    selectors = [

        page.get_by_role(
            "button",
            name="New project",
            exact=True
        ),

        page.get_by_text(
            "New project",
            exact=True
        )
    ]

    for locator in selectors:

        try:

            if is_visible(locator):

                print("[OK] New project found")

                locator.first.click()

                print("[OK] New project clicked")

                return True

        except Exception:
            pass

    return False


# ============================================================
# PROJECT READY
# ============================================================

def project_ready(page):

    try:

        start_button = page.get_by_role(
            "button",
            name="Start generation",
            exact=True
        )

        if is_visible(start_button):
            return True

    except Exception:
        pass

    try:

        editors = page.locator(
            '[contenteditable="true"]'
        )

        for i in range(editors.count()):

            if editors.nth(i).is_visible():
                return True

    except Exception:
        pass

    return False


# ============================================================
# PROMPT
# ============================================================

def find_prompt(page):

    # First try contenteditable
    editors = page.locator(
        '[contenteditable="true"]'
    )

    for i in range(editors.count()):

        try:

            element = editors.nth(i)

            if element.is_visible():

                print(
                    f"[OK] Prompt contenteditable found: "
                    f"editable[{i}]"
                )

                return element

        except Exception:
            pass

    # Fallback textarea
    textareas = page.locator("textarea")

    for i in range(textareas.count()):

        try:

            element = textareas.nth(i)

            if element.is_visible():

                print(
                    f"[OK] Prompt textarea found: "
                    f"textarea[{i}]"
                )

                return element

        except Exception:
            pass

    return None


# ============================================================
# GENERATION STATE
# ============================================================

def stop_button_visible(page):

    try:

        stop = page.get_by_role(
            "button",
            name="Stop",
            exact=True
        )

        return is_visible(stop)

    except Exception:
        return False


def wait_generation_finished(page):

    print()
    print("[11] Waiting for Flow generation to finish...")
    print(
        f"     Maximum wait: "
        f"{MAX_GENERATION_SECONDS}s"
    )

    started = time.time()

    last_report = 0

    while True:

        elapsed = int(time.time() - started)

        if elapsed >= MAX_GENERATION_SECONDS:

            print(
                "[TIMEOUT] Generation exceeded "
                f"{MAX_GENERATION_SECONDS}s"
            )

            return False

        # Stop button means generation is still active.
        if stop_button_visible(page):

            if elapsed - last_report >= 10:

                print(
                    f"[WAIT] Generation still running "
                    f"({elapsed}s)"
                )

                last_report = elapsed

            time.sleep(2)

            continue

        # Stop may temporarily disappear while UI is rendering.
        print(
            f"[SIGNAL] Stop button is no longer visible "
            f"after {elapsed}s"
        )

        # Important:
        # Give Flow extra time for all generated results
        # and Agent output to render.
        print(
            f"[WAIT] Extra {EXTRA_RESULT_WAIT_SECONDS}s "
            "for result rendering..."
        )

        time.sleep(EXTRA_RESULT_WAIT_SECONDS)

        return True


# ============================================================
# RESULT INSPECTION
# ============================================================

def inspect_media(page):

    print()
    print("--- VISIBLE MEDIA ---")

    image_count = 0
    video_count = 0

    try:

        images = page.locator("img")

        for i in range(images.count()):

            element = images.nth(i)

            try:

                if not element.is_visible():
                    continue

                image_count += 1

                data = element.evaluate(
                    """
                    el => ({
                        src: el.currentSrc || el.src || "",
                        alt: el.getAttribute("alt"),
                        title: el.getAttribute("title"),
                        className: el.className
                    })
                    """
                )

                print(
                    f"img[{i}] => {data}"
                )

            except Exception:
                pass

    except Exception:
        pass

    try:

        videos = page.locator("video")

        for i in range(videos.count()):

            element = videos.nth(i)

            try:

                if not element.is_visible():
                    continue

                video_count += 1

                data = element.evaluate(
                    """
                    el => ({
                        src: el.currentSrc || el.src || "",
                        poster: el.getAttribute("poster"),
                        className: el.className
                    })
                    """
                )

                print(
                    f"video[{i}] => {data}"
                )

            except Exception:
                pass

    except Exception:
        pass

    print()
    print(
        f"[MEDIA] Visible images: {image_count}"
    )

    print(
        f"[MEDIA] Visible videos: {video_count}"
    )

    return image_count, video_count


# ============================================================
# BUTTON INSPECTION
# ============================================================

def inspect_buttons(page):

    print()
    print("=" * 75)
    print("BUTTON INSPECTION")
    print("=" * 75)

    buttons = page.locator("button")

    results = []

    for i in range(buttons.count()):

        button = buttons.nth(i)

        try:

            if not button.is_visible():
                continue

            text = (
                button.inner_text() or ""
            ).strip()

            aria = button.get_attribute(
                "aria-label"
            )

            title = button.get_attribute(
                "title"
            )

            testid = button.get_attribute(
                "data-testid"
            )

            info = {
                "index": i,
                "text": text,
                "aria": aria,
                "title": title,
                "testid": testid
            }

            results.append(
                (button, info)
            )

            print(
                f"button[{i}] "
                f"text={text!r} "
                f"aria={aria!r} "
                f"title={title!r} "
                f"testid={testid!r}"
            )

        except Exception:
            pass

    return results


# ============================================================
# DOWNLOAD CANDIDATE SEARCH
# ============================================================

def find_download_candidates(page):

    print()
    print(
        "--- SEARCHING FOR DOWNLOAD CONTROLS ---"
    )

    selectors = [

        '[aria-label*="download" i]',

        '[title*="download" i]',

        '[data-testid*="download" i]',

        'button:has-text("Download")',

        '[role="button"]:has-text("Download")',

        'a[download]',

        'a[href*="download" i]'
    ]

    candidates = []

    seen = set()

    for selector in selectors:

        try:

            elements = page.locator(selector)

            for i in range(elements.count()):

                element = elements.nth(i)

                try:

                    if not element.is_visible():
                        continue

                    info = element.evaluate(
                        """
                        el => ({
                            tag: el.tagName,
                            text: (el.innerText || "").trim(),
                            aria: el.getAttribute("aria-label"),
                            title: el.getAttribute("title"),
                            testid: el.getAttribute("data-testid"),
                            href: el.getAttribute("href"),
                            download: el.getAttribute("download"),
                            className: el.className
                        })
                        """
                    )

                    key = str(info)

                    if key in seen:
                        continue

                    seen.add(key)

                    candidates.append(
                        (element, info)
                    )

                    print(
                        "[FOUND]",
                        info
                    )

                except Exception:
                    pass

        except Exception:
            pass

    print(
        f"[INFO] Download candidates: "
        f"{len(candidates)}"
    )

    return candidates


# ============================================================
# EXPAND RESULT
# ============================================================

def click_expand(page):

    print()
    print("[13] Looking for Expand...")

    for attempt in range(60):

        try:

            expand = page.get_by_role(
                "button",
                name="Expand",
                exact=True
            )

            if is_visible(expand):

                print(
                    "[OK] Expand button found"
                )

                expand.first.click()

                print(
                    "[OK] Expand clicked"
                )

                page.wait_for_timeout(3000)

                return True

        except Exception:
            pass

        time.sleep(1)

    print(
        "[WARN] Expand button not found"
    )

    return False


# ============================================================
# DOWNLOAD
# ============================================================

def save_download(page, candidates):

    if not candidates:

        print(
            "[WARN] No download candidate found."
        )

        return None

    print()
    print(
        "[14] Trying download controls..."
    )

    for index, (element, info) in enumerate(
        candidates
    ):

        print()
        print(
            f"[TRY {index + 1}] {info}"
        )

        try:

            with page.expect_download(
                timeout=15000
            ) as download_info:

                element.click()

            download = download_info.value

            filename = (
                download.suggested_filename
                or "flow_generated"
            )

            target = (
                DOWNLOAD_DIR /
                filename
            )

            # Prevent overwrite
            if target.exists():

                stem = target.stem
                suffix = target.suffix

                counter = 2

                while True:

                    new_target = (
                        DOWNLOAD_DIR /
                        f"{stem}_{counter}{suffix}"
                    )

                    if not new_target.exists():

                        target = new_target
                        break

                    counter += 1

            download.save_as(
                str(target)
            )

            if (
                target.exists()
                and target.stat().st_size > 0
            ):

                print()
                print(
                    "=" * 65
                )

                print(
                    "[OK] DOWNLOAD SUCCESS"
                )

                print(
                    "[OK] File:",
                    target
                )

                print(
                    "[OK] Size:",
                    target.stat().st_size,
                    "bytes"
                )

                print(
                    "=" * 65
                )

                return target

        except PlaywrightTimeoutError:

            print(
                "[INFO] Click did not trigger "
                "a browser download."
            )

        except Exception as error:

            print(
                "[WARN] Download attempt failed:",
                repr(error)
            )

    return None


# ============================================================
# MAIN
# ============================================================

def main():

    with sync_playwright() as p:

        # ----------------------------------------------------
        # 1
        # ----------------------------------------------------

        print(
            "[1] Opening IXBrowser profile "
            f"{PROFILE_ID}..."
        )

        debugging_address = (
            open_ixbrowser_profile()
        )

        # ----------------------------------------------------
        # 2
        # ----------------------------------------------------

        print(
            "[2] Connecting to IXBrowser Chromium..."
        )

        browser = p.chromium.connect_over_cdp(
            f"http://{debugging_address}"
        )

        print(
            "[OK] Connected to Chromium"
        )

        # ----------------------------------------------------
        # 3
        # ----------------------------------------------------

        page = get_flow_page(browser)

        # ----------------------------------------------------
        # 4
        # ----------------------------------------------------

        print(
            "[3] Opening Flow home..."
        )

        page.goto(
            FLOW_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        # ----------------------------------------------------
        # 5
        # ----------------------------------------------------

        print(
            "[4] Looking for New project..."
        )

        if not click_new_project(page):

            raise RuntimeError(
                "New project button not found"
            )

        # ----------------------------------------------------
        # 6
        # ----------------------------------------------------

        print()
        print(
            "[5] Waiting for Flow project UI..."
        )

        ready = False

        for i in range(60):

            if project_ready(page):

                ready = True
                break

            print(
                f"[WAIT] Project UI not ready "
                f"({i + 1}/60)"
            )

            time.sleep(1)

        if not ready:

            raise RuntimeError(
                "Flow project UI did not become ready"
            )

        print()
        print("=" * 65)

        print(
            "[OK] FLOW PROJECT READY"
        )

        print(
            "URL:",
            page.url
        )

        print(
            "TITLE:",
            page.title()
        )

        print("=" * 65)

        # ----------------------------------------------------
        # 7
        # ----------------------------------------------------

        print()
        print(
            "[7] Looking for prompt input..."
        )

        editor = find_prompt(page)

        if editor is None:

            raise RuntimeError(
                "Prompt input not found"
            )

        # ----------------------------------------------------
        # 8
        # ----------------------------------------------------

        print()
        print(
            "[8] Pasting prompt..."
        )

        print(
            "PROMPT:"
        )

        print(
            PROMPT
        )

        try:

            editor.fill(
                PROMPT
            )

            print(
                "[OK] Prompt pasted using fill()"
            )

        except Exception as error:

            print(
                "[WARN] fill() failed:",
                error
            )

            editor.click()

            page.keyboard.press(
                "CTRL+A"
            )

            page.keyboard.type(
                PROMPT
            )

            print(
                "[OK] Prompt pasted using keyboard"
            )

        # ----------------------------------------------------
        # 9
        # ----------------------------------------------------

        print()
        print(
            "[9] Looking for Start generation..."
        )

        start_button = page.get_by_role(
            "button",
            name="Start generation",
            exact=True
        )

        if not is_visible(
            start_button
        ):

            raise RuntimeError(
                "Start generation button not found"
            )

        print(
            "[OK] Start generation found"
        )

        # ----------------------------------------------------
        # 10
        # ----------------------------------------------------

        print()
        print(
            "[10] Clicking Start generation..."
        )

        start_button.first.click()

        print(
            "[OK] Start generation clicked"
        )

        page.screenshot(
            path=str(
                SCREENSHOT_DIR /
                "generation-started.png"
            ),
            full_page=True
        )

        print()
        print("=" * 65)

        print(
            "IMAGE GENERATION STARTED"
        )

        print("=" * 65)

        # ----------------------------------------------------
        # 11
        # ----------------------------------------------------

        finished = (
            wait_generation_finished(
                page
            )
        )

        if not finished:

            page.screenshot(
                path=str(
                    SCREENSHOT_DIR /
                    "generation-timeout.png"
                ),
                full_page=True
            )

            print(
                "[INFO] Browser remains open."
            )

            while True:
                time.sleep(10)

        # ----------------------------------------------------
        # 12
        # ----------------------------------------------------

        print()
        print(
            "[12] Inspecting generated media..."
        )

        images, videos = (
            inspect_media(page)
        )

        page.screenshot(
            path=str(
                SCREENSHOT_DIR /
                "generation-finished.png"
            ),
            full_page=True
        )

        # ----------------------------------------------------
        # 13
        # ----------------------------------------------------

        print()
        print(
            "[13] Checking result controls..."
        )

        inspect_buttons(page)

        # ----------------------------------------------------
        # 14
        # ----------------------------------------------------

        expanded = click_expand(page)

        if expanded:

            print()
            print(
                "[OK] Expanded result opened."
            )

            page.screenshot(
                path=str(
                    SCREENSHOT_DIR /
                    "expanded-result.png"
                ),
                full_page=True
            )

            # Allow action toolbar to render.
            time.sleep(3)

        # ----------------------------------------------------
        # 15
        # ----------------------------------------------------

        print()
        print(
            "[15] Inspecting download controls..."
        )

        inspect_buttons(page)

        candidates = (
            find_download_candidates(page)
        )

        # ----------------------------------------------------
        # 16
        # ----------------------------------------------------

        downloaded = save_download(
            page,
            candidates
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        print()
        print("=" * 70)

        if downloaded:

            print(
                "FINAL RESULT: DOWNLOAD SUCCESS"
            )

            print(
                "FILE:",
                downloaded
            )

        else:

            print(
                "FINAL RESULT: DOWNLOAD CONTROL "
                "NOT AUTOMATICALLY CAPTURED"
            )

            print()
            print(
                "Screenshots:"
            )

            print(
                SCREENSHOT_DIR /
                "generation-finished.png"
            )

            print(
                SCREENSHOT_DIR /
                "expanded-result.png"
            )

            print()
            print(
                "The browser will stay open."
            )

        print("=" * 70)

        # ----------------------------------------------------
        # KEEP BROWSER OPEN
        # ----------------------------------------------------

        print()
        print(
            "[LIVE] Browser remains open."
        )

        print(
            "[INFO] Press CTRL+C to stop."
        )

        while True:

            time.sleep(10)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
