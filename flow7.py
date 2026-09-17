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

MAX_GENERATION_SECONDS = 300

# Important for cases where Flow creates 2 images.
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

def visible(locator):

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

    for page in pages:

        if "flow.google.com" in page.url:
            return page

    return pages[0]


# ============================================================
# NEW PROJECT
# ============================================================

def click_new_project(page):

    candidates = [

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

    for locator in candidates:

        try:

            if visible(locator):

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

        start = page.get_by_role(
            "button",
            name="Start generation",
            exact=True
        )

        if visible(start):
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

def stop_visible(page):

    try:

        stop = page.get_by_role(
            "button",
            name="Stop",
            exact=True
        )

        return visible(stop)

    except Exception:
        return False


def wait_generation_finished(page):

    print()
    print("[11] Waiting for generation to finish...")

    started = time.time()
    last_message = 0

    while True:

        elapsed = int(
            time.time() - started
        )

        if elapsed >= MAX_GENERATION_SECONDS:

            print(
                "[TIMEOUT] Generation exceeded "
                f"{MAX_GENERATION_SECONDS}s"
            )

            return False

        if stop_visible(page):

            if elapsed - last_message >= 10:

                print(
                    f"[WAIT] Generation running "
                    f"({elapsed}s)"
                )

                last_message = elapsed

            time.sleep(2)

            continue

        print()
        print(
            f"[OK] Generation finished after "
            f"{elapsed}s"
        )

        print(
            f"[WAIT] Extra "
            f"{EXTRA_RESULT_WAIT_SECONDS}s "
            "for all result tiles to render..."
        )

        time.sleep(
            EXTRA_RESULT_WAIT_SECONDS
        )

        return True


# ============================================================
# IMAGE DETECTION
# ============================================================

def get_visible_images(page):

    results = []

    images = page.locator("img")

    for i in range(images.count()):

        try:

            img = images.nth(i)

            if not img.is_visible():
                continue

            box = img.bounding_box()

            if not box:
                continue

            width = box["width"]
            height = box["height"]

            # Ignore tiny UI icons.
            if width < 150 or height < 100:
                continue

            src = img.get_attribute("src")

            alt = img.get_attribute("alt")

            results.append({
                "locator": img,
                "index": i,
                "width": width,
                "height": height,
                "src": src,
                "alt": alt
            })

        except Exception:
            pass

    return results


# ============================================================
# FIND MORE BUTTON FOR IMAGE
# ============================================================

def find_more_button_for_image(page, img):

    """
    The screenshot shows:

        generated image
              ↓
        hover image
              ↓
        More / ⋮
              ↓
        Download

    We first hover the image, then look for a visible
    More button near the image.
    """

    try:

        img.hover(
            position={
                "x": 10,
                "y": 10
            }
        )

    except Exception:

        try:
            img.hover()
        except Exception:
            pass

    page.wait_for_timeout(1000)

    # Most reliable if Flow exposes accessible name.
    names = [
        "More",
        "More options"
    ]

    for name in names:

        try:

            button = page.get_by_role(
                "button",
                name=name,
                exact=True
            )

            if visible(button):

                return button.first

        except Exception:
            pass

    # Fallback: buttons whose aria-label/title contains more.
    selectors = [
        'button[aria-label*="more" i]',
        '[role="button"][aria-label*="more" i]',
        'button[title*="more" i]',
        '[role="button"][title*="more" i]'
    ]

    for selector in selectors:

        try:

            buttons = page.locator(selector)

            for i in range(buttons.count()):

                button = buttons.nth(i)

                if not button.is_visible():
                    continue

                return button

        except Exception:
            pass

    return None


# ============================================================
# DOWNLOAD MENU
# ============================================================

def find_download_menu_item(page):

    # Screenshot shows exact visible "Download".
    exact_candidates = [

        page.get_by_text(
            "Download",
            exact=True
        ),

        page.get_by_role(
            "menuitem",
            name="Download",
            exact=True
        ),

        page.get_by_role(
            "button",
            name="Download",
            exact=True
        )
    ]

    for locator in exact_candidates:

        try:

            if visible(locator):

                return locator.first

        except Exception:
            pass

    return None


# ============================================================
# DOWNLOAD ONE IMAGE
# ============================================================

def download_image(page, img, number):

    print()
    print(
        f"[IMAGE {number}] Preparing download..."
    )

    # Hover generated image
    try:

        img.hover()

    except Exception:

        print(
            f"[WARN] Could not hover image {number}"
        )

        return None

    page.wait_for_timeout(1000)

    # Find More button
    more = find_more_button_for_image(
        page,
        img
    )

    if more is None:

        print(
            f"[WARN] More button not found "
            f"for image {number}"
        )

        return None

    print(
        f"[OK] More button found "
        f"for image {number}"
    )

    try:

        more.click()

    except Exception as error:

        print(
            "[WARN] Could not click More:",
            error
        )

        return None

    page.wait_for_timeout(700)

    # Find Download menu item
    download_item = (
        find_download_menu_item(page)
    )

    if download_item is None:

        print(
            "[WARN] Download menu item not found"
        )

        # Screenshot for debugging
        page.screenshot(
            path=str(
                SCREENSHOT_DIR /
                f"download-menu-{number}.png"
            ),
            full_page=True
        )

        return None

    print(
        "[OK] Download menu item found"
    )

    # Capture browser download
    try:

        with page.expect_download(
            timeout=20000
        ) as download_info:

            download_item.click()

        download = (
            download_info.value
        )

        filename = (
            download.suggested_filename
            or f"flow_image_{number}.png"
        )

        target = (
            DOWNLOAD_DIR /
            filename
        )

        # Avoid overwriting.
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
                f"[OK] IMAGE {number} DOWNLOADED"
            )

            print(
                "     File:",
                target
            )

            print(
                "     Size:",
                target.stat().st_size,
                "bytes"
            )

            return target

    except PlaywrightTimeoutError:

        print(
            "[WARN] Download click did not "
            "produce browser download."
        )

    except Exception as error:

        print(
            "[WARN] Download failed:",
            repr(error)
        )

    return None


# ============================================================
# DOWNLOAD ALL GENERATED IMAGES
# ============================================================

def download_all_images(page):

    print()
    print(
        "[14] Searching for generated images..."
    )

    images = get_visible_images(page)

    print(
        f"[INFO] Large visible images found: "
        f"{len(images)}"
    )

    if not images:

        return []

    downloaded = []

    # Avoid processing the same source twice.
    seen_src = set()

    number = 0

    for item in images:

        src = item.get("src")

        if src and src in seen_src:
            continue

        if src:
            seen_src.add(src)

        number += 1

        print()
        print(
            f"--- RESULT IMAGE {number} ---"
        )

        print(
            "Size:",
            round(item["width"]),
            "x",
            round(item["height"])
        )

        result = download_image(
            page,
            item["locator"],
            number
        )

        if result:

            downloaded.append(result)

        # Close menu if still open.
        try:

            page.keyboard.press(
                "Escape"
            )

        except Exception:
            pass

        page.wait_for_timeout(500)

    return downloaded


# ============================================================
# MAIN
# ============================================================

def main():

    with sync_playwright() as p:

        # ----------------------------------------------------
        # 1
        # ----------------------------------------------------

        print(
            f"[1] Opening IXBrowser profile "
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

        page = get_flow_page(
            browser
        )

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

        page.wait_for_timeout(
            3000
        )

        # ----------------------------------------------------
        # 5
        # ----------------------------------------------------

        print(
            "[4] Looking for New project..."
        )

        if not click_new_project(
            page
        ):

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
        print(
            "=" * 65
        )

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

        print(
            "=" * 65
        )

        # ----------------------------------------------------
        # 7
        # ----------------------------------------------------

        print()
        print(
            "[7] Looking for prompt input..."
        )

        editor = find_prompt(
            page
        )

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

        if not visible(
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
        print(
            "=" * 65
        )

        print(
            "IMAGE GENERATION STARTED"
        )

        print(
            "=" * 65
        )

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
                "[LIVE] Browser remains open."
            )

            while True:
                time.sleep(10)

        # ----------------------------------------------------
        # 12
        # ----------------------------------------------------

        print()
        print(
            "[12] Generation finished."
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
            "[13] Waiting before download..."
        )

        # Additional safety wait for Agent / second image.
        time.sleep(
            5
        )

        # ----------------------------------------------------
        # 14
        # ----------------------------------------------------

        downloaded = (
            download_all_images(
                page
            )
        )

        # ----------------------------------------------------
        # FINAL
        # ----------------------------------------------------

        print()
        print(
            "=" * 70
        )

        print(
            "FINAL RESULT"
        )

        print(
            "=" * 70
        )

        print(
            "Images downloaded:",
            len(downloaded)
        )

        for file in downloaded:

            print(
                " ->",
                file
            )

        if not downloaded:

            print()
            print(
                "[WARN] No image was downloaded."
            )

            print(
                "Check screenshots folder:"
            )

            print(
                SCREENSHOT_DIR
            )

        else:

            print()
            print(
                "[OK] Download stage completed."
            )

            print(
                "Download folder:",
                DOWNLOAD_DIR
            )

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
