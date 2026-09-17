import os
import time
import requests
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

PROFILE_ID = 3878

IX_API = "http://127.0.0.1:53200/api/v2/profile-open"

FLOW_URL = "https://flow.google.com/"

BASE_DIR = Path(r"C:\Users\Uswa\Desktop\flow")

DOWNLOAD_DIR = BASE_DIR / "downloads"
SCREENSHOT_DIR = BASE_DIR / "screenshots"

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# Prompt
# ------------------------------------------------------------

PROMPT = (
    "A cinematic realistic scene of a futuristic city at sunset, "
    "dramatic golden lighting, detailed architecture, "
    "photorealistic, high quality"
)


# ------------------------------------------------------------
# Timeouts
# ------------------------------------------------------------

PROJECT_TIMEOUT = 90
GENERATION_TIMEOUT = 300

# Agent kabhi multiple images banata hai.
# Generation complete hone ke baad extra settling time.
POST_GENERATION_WAIT = 20


# ============================================================
# LOGGING
# ============================================================

def log(message=""):
    print(message, flush=True)


# ============================================================
# IXBROWSER
# ============================================================

def open_ixbrowser_profile():
    """
    Open IXBrowser profile through Local API.

    IMPORTANT:
    IXBrowser success response looks like:

    {
        "error": {
            "code": 0,
            "message": "success"
        },
        "data": {
            "debugging_address": "127.0.0.1:xxxxx"
        }
    }

    So success is checked using error.code == 0.
    """

    log(f"[1] Opening IXBrowser profile {PROFILE_ID}...")

    payload = {
        "profile_id": PROFILE_ID,
        "args": [
            "--disable-extension-welcome-page"
        ],
        "load_extensions": True,
        "load_profile_info_page": True,
        "cookies_backup": True,
        "cookie": ""
    }

    response = requests.post(
        IX_API,
        json=payload,
        timeout=30
    )

    log(f"HTTP: {response.status_code}")

    response.raise_for_status()

    data = response.json()

    # Debug response
    log("[DEBUG] IXBrowser API response:")
    log(str(data))

    # --------------------------------------------------------
    # Correct IXBrowser success check
    # --------------------------------------------------------

    error = data.get("error", {})

    error_code = error.get("code")

    if error_code != 0:
        raise RuntimeError(
            f"IXBrowser failed: {error}"
        )

    # --------------------------------------------------------
    # Get CDP address
    # --------------------------------------------------------

    api_data = data.get("data", {})

    debugging_address = api_data.get(
        "debugging_address"
    )

    if not debugging_address:
        raise RuntimeError(
            "IXBrowser response mein "
            "debugging_address nahi mila.\n"
            f"Response: {data}"
        )

    log("[OK] IXBrowser profile opened")
    log(f"CDP: {debugging_address}")

    return debugging_address


# ============================================================
# PAGE HELPERS
# ============================================================

def get_or_create_flow_page(context):
    """
    Reuse existing Flow page if present.
    Otherwise reuse first page / create new page.
    """

    pages = context.pages

    log(f"[OK] Existing pages: {len(pages)}")

    for i, pg in enumerate(pages):
        try:
            log(f"    [{i}] {pg.url}")
        except Exception:
            pass

    # Prefer existing Flow page
    for pg in pages:
        try:
            if "flow.google.com" in pg.url:
                return pg
        except Exception:
            pass

    if pages:
        return pages[0]

    return context.new_page()


def visible_count(locator):
    count = 0

    try:
        total = locator.count()

        for i in range(total):
            try:
                if locator.nth(i).is_visible():
                    count += 1
            except Exception:
                pass

    except Exception:
        pass

    return count


# ============================================================
# PROJECT DETECTION
# ============================================================

def wait_for_project(page):
    log("[6] Waiting for FLOW project UI...")

    for i in range(PROJECT_TIMEOUT):

        # ----------------------------------------------------
        # URL check
        # ----------------------------------------------------

        try:
            if "/project/" in page.url:
                log("[OK] FLOW PROJECT URL DETECTED")
                log(f"URL: {page.url}")

                try:
                    log(f"TITLE: {page.title()}")
                except Exception:
                    pass

                return True

        except Exception:
            pass

        # ----------------------------------------------------
        # Contenteditable check
        # ----------------------------------------------------

        try:
            editable = page.locator(
                '[contenteditable="true"]'
            )

            for j in range(editable.count()):

                try:
                    el = editable.nth(j)

                    if el.is_visible():
                        log(
                            "[OK] FLOW PROJECT UI DETECTED"
                        )

                        log(f"URL: {page.url}")

                        try:
                            log(
                                f"TITLE: {page.title()}"
                            )
                        except Exception:
                            pass

                        return True

                except Exception:
                    pass

        except Exception:
            pass

        if i % 5 == 0:
            log(
                f"[WAIT] Project UI "
                f"({i + 1}/{PROJECT_TIMEOUT})"
            )

        time.sleep(1)

    return False


# ============================================================
# PROMPT
# ============================================================

def find_prompt(page):
    """
    Find visible editable prompt.
    """

    editable = page.locator(
        '[contenteditable="true"]'
    )

    total = editable.count()

    for i in range(total):

        try:
            el = editable.nth(i)

            if not el.is_visible():
                continue

            if not el.is_editable():
                continue

            return el

        except Exception:
            pass

    return None


def fill_prompt(page):
    log("[7] Looking for prompt contenteditable...")

    prompt = find_prompt(page)

    if prompt is None:
        raise RuntimeError(
            "Prompt contenteditable not found"
        )

    log("[OK] Prompt contenteditable found")

    log("[8] Filling prompt...")

    prompt.fill(PROMPT)

    time.sleep(1)

    log("[OK] Prompt filled")


# ============================================================
# START GENERATION
# ============================================================

def click_start_generation(page):
    log("[9] Looking for Start generation...")

    button = page.get_by_role(
        "button",
        name="Start generation"
    )

    button.wait_for(
        state="visible",
        timeout=30000
    )

    log("[OK] Start generation found")

    button.click()

    log("[10] Start generation clicked")


# ============================================================
# GENERATION WAIT
# ============================================================

def is_stop_visible(page):
    """
    Returns True while Flow shows Stop.
    """

    try:
        stop = page.get_by_role(
            "button",
            name="Stop"
        )

        for i in range(stop.count()):

            try:
                if stop.nth(i).is_visible():
                    return True
            except Exception:
                pass

    except Exception:
        pass

    return False


def wait_for_generation(page):
    log("[11] Waiting for generation to finish...")

    start_time = time.time()
    last_log_second = -1

    while True:

        elapsed = int(
            time.time() - start_time
        )

        if elapsed >= GENERATION_TIMEOUT:
            raise TimeoutError(
                f"Generation did not finish within "
                f"{GENERATION_TIMEOUT} seconds."
            )

        if is_stop_visible(page):

            # Print every 10 sec
            if elapsed // 10 != last_log_second:
                last_log_second = elapsed // 10

                log(
                    f"[WAIT] Generation running... "
                    f"{elapsed}s"
                )

            time.sleep(1)

            continue

        # ----------------------------------------------------
        # Stop disappeared
        # ----------------------------------------------------

        log(
            "[SIGNAL] Stop button disappeared."
        )

        break

    # --------------------------------------------------------
    # Give Flow time to finish rendering tiles
    # --------------------------------------------------------

    log(
        f"[12] Waiting additional "
        f"{POST_GENERATION_WAIT}s "
        f"for result tiles..."
    )

    time.sleep(
        POST_GENERATION_WAIT
    )


# ============================================================
# IMAGE DETECTION
# ============================================================

def get_large_visible_images(page):
    """
    Find visible <img> elements that are large enough
    to plausibly be generated image tiles.

    Tiny UI icons are ignored.
    """

    images = page.locator("img")

    results = []

    total = images.count()

    for i in range(total):

        try:
            img = images.nth(i)

            if not img.is_visible():
                continue

            box = img.bounding_box()

            if not box:
                continue

            width = box["width"]
            height = box["height"]

            # Ignore icons / tiny images
            if width < 150:
                continue

            if height < 100:
                continue

            src = None

            try:
                src = img.get_attribute("src")
            except Exception:
                pass

            results.append({
                "locator": img,
                "index": i,
                "box": box,
                "src": src,
            })

        except Exception:
            continue

    return results


def print_images(images):
    log("")
    log(
        "================================================"
    )
    log("VISIBLE LARGE IMAGES")
    log(
        "================================================"
    )

    if not images:
        log("No large visible images found.")

    for number, item in enumerate(images, start=1):

        box = item["box"]

        log(
            f"[IMAGE {number}] "
            f"x={round(box['x'])} "
            f"y={round(box['y'])} "
            f"w={round(box['width'])} "
            f"h={round(box['height'])}"
        )

        log(
            f"    src={item['src']}"
        )

    log(
        "================================================"
    )
    log("")


# ============================================================
# HOVER + RIGHT CLICK TEST
# ============================================================

def right_click_image(page, image, number):
    """
    Exact requested behavior:

        cursor -> image center
        cursor hover
        right click

    We use actual mouse coordinates rather than searching
    for the hidden three-dot button.
    """

    box = image["box"]

    center_x = (
        box["x"] +
        box["width"] / 2
    )

    center_y = (
        box["y"] +
        box["height"] / 2
    )

    log("")
    log(
        f"[IMAGE {number}] "
        f"Moving mouse to image center..."
    )

    log(
        f"    X={round(center_x)} "
        f"Y={round(center_y)}"
    )

    # --------------------------------------------------------
    # Move naturally
    # --------------------------------------------------------

    page.mouse.move(
        center_x,
        center_y,
        steps=20
    )

    # Give Flow hover state time to appear.
    time.sleep(2)

    # --------------------------------------------------------
    # Screenshot BEFORE right click
    # --------------------------------------------------------

    before_path = (
        SCREENSHOT_DIR /
        f"image_{number}_before_right_click.png"
    )

    page.screenshot(
        path=str(before_path),
        full_page=False
    )

    log(
        f"[IMAGE {number}] "
        f"Hover screenshot saved:"
    )

    log(
        f"    {before_path}"
    )

    # --------------------------------------------------------
    # Actual right click
    # --------------------------------------------------------

    log(
        f"[IMAGE {number}] "
        f"Right-clicking image center..."
    )

    page.mouse.click(
        center_x,
        center_y,
        button="right"
    )

    # Give menu time to open.
    time.sleep(1.5)

    # --------------------------------------------------------
    # Screenshot AFTER right click
    # --------------------------------------------------------

    after_path = (
        SCREENSHOT_DIR /
        f"image_{number}_after_right_click.png"
    )

    page.screenshot(
        path=str(after_path),
        full_page=False
    )

    log(
        f"[IMAGE {number}] "
        f"Right-click screenshot saved:"
    )

    log(
        f"    {after_path}"
    )


# ============================================================
# MENU INSPECTION
# ============================================================

def inspect_visible_menu(page):
    """
    Print all visible menu-related elements.

    This is the important diagnostic step before we automate
    Download -> Download 1K.
    """

    log("")
    log(
        "================================================"
    )
    log("MENU INSPECTION")
    log(
        "================================================"
    )

    # --------------------------------------------------------
    # 1. role=menuitem
    # --------------------------------------------------------

    try:

        menuitems = page.get_by_role(
            "menuitem"
        )

        count = menuitems.count()

        log(
            f"[ROLE=menuitem] count={count}"
        )

        for i in range(count):

            try:

                item = menuitems.nth(i)

                if not item.is_visible():
                    continue

                text = ""

                try:
                    text = item.inner_text().strip()
                except Exception:
                    pass

                aria = item.get_attribute(
                    "aria-label"
                )

                title = item.get_attribute(
                    "title"
                )

                box = item.bounding_box()

                log(
                    f"[MENUITEM {i}] "
                    f"text={text!r}"
                )

                log(
                    f"    aria={aria!r}"
                )

                log(
                    f"    title={title!r}"
                )

                log(
                    f"    box={box}"
                )

            except Exception as e:
                log(
                    f"[MENUITEM {i}] "
                    f"error={e}"
                )

    except Exception as e:
        log(
            f"[ROLE=menuitem] ERROR: {e}"
        )

    # --------------------------------------------------------
    # 2. role=menu
    # --------------------------------------------------------

    try:

        menus = page.locator(
            '[role="menu"]'
        )

        count = menus.count()

        log(
            f"[ROLE=menu] count={count}"
        )

        for i in range(count):

            try:

                menu = menus.nth(i)

                if not menu.is_visible():
                    continue

                text = ""

                try:
                    text = menu.inner_text().strip()
                except Exception:
                    pass

                box = menu.bounding_box()

                log("")
                log(
                    f"[MENU {i}]"
                )

                log(
                    f"    text={text!r}"
                )

                log(
                    f"    box={box}"
                )

            except Exception:
                pass

    except Exception as e:
        log(
            f"[ROLE=menu] ERROR: {e}"
        )

    # --------------------------------------------------------
    # 3. Download text
    # --------------------------------------------------------

    try:

        download = page.get_by_text(
            "Download",
            exact=False
        )

        count = download.count()

        log(
            f"[TEXT Download] count={count}"
        )

        for i in range(count):

            try:

                item = download.nth(i)

                if not item.is_visible():
                    continue

                text = item.inner_text().strip()

                aria = item.get_attribute(
                    "aria-label"
                )

                title = item.get_attribute(
                    "title"
                )

                box = item.bounding_box()

                log("")
                log(
                    f"[DOWNLOAD {i}]"
                )

                log(
                    f"    text={text!r}"
                )

                log(
                    f"    aria={aria!r}"
                )

                log(
                    f"    title={title!r}"
                )

                log(
                    f"    box={box}"
                )

            except Exception:
                pass

    except Exception as e:
        log(
            f"[DOWNLOAD TEXT] ERROR: {e}"
        )

    # --------------------------------------------------------
    # 4. Search 1K / 2K
    # --------------------------------------------------------

    for search_text in [
        "1K",
        "2K",
        "Download 1K",
        "Download 2K"
    ]:

        try:

            locator = page.get_by_text(
                search_text,
                exact=False
            )

            count = locator.count()

            if count == 0:
                continue

            log(
                f"[TEXT {search_text!r}] "
                f"count={count}"
            )

            for i in range(count):

                try:

                    item = locator.nth(i)

                    if not item.is_visible():
                        continue

                    text = item.inner_text().strip()

                    aria = item.get_attribute(
                        "aria-label"
                    )

                    title = item.get_attribute(
                        "title"
                    )

                    box = item.bounding_box()

                    log(
                        f"[{search_text} {i}] "
                        f"text={text!r} "
                        f"aria={aria!r} "
                        f"title={title!r} "
                        f"box={box}"
                    )

                except Exception:
                    pass

        except Exception:
            pass

    log(
        "================================================"
    )
    log("END MENU INSPECTION")
    log(
        "================================================"
    )
    log("")


# ============================================================
# ALL VISIBLE BUTTONS
# ============================================================

def inspect_visible_buttons(page):
    """
    Diagnostic output.
    """

    log("")
    log(
        "================================================"
    )
    log("VISIBLE BUTTONS")
    log(
        "================================================"
    )

    try:

        buttons = page.locator(
            "button"
        )

        total = buttons.count()

        for i in range(total):

            try:

                button = buttons.nth(i)

                if not button.is_visible():
                    continue

                text = ""

                try:
                    text = button.inner_text().strip()
                except Exception:
                    pass

                aria = button.get_attribute(
                    "aria-label"
                )

                title = button.get_attribute(
                    "title"
                )

                box = button.bounding_box()

                log(
                    f"[BUTTON {i}] "
                    f"text={text!r} "
                    f"aria={aria!r} "
                    f"title={title!r} "
                    f"box={box}"
                )

            except Exception:
                pass

    except Exception as e:
        log(
            f"[BUTTON INSPECTION ERROR] {e}"
        )

    log(
        "================================================"
    )
    log("")


# ============================================================
# ESCAPE CONTEXT MENU
# ============================================================

def close_context_menu(page):
    """
    Press Escape so the browser is left in a clean state.
    """

    try:
        page.keyboard.press("Escape")
        time.sleep(0.5)
    except Exception:
        pass


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # STEP 1
    # --------------------------------------------------------

    debugging_address = (
        open_ixbrowser_profile()
    )

    # --------------------------------------------------------
    # STEP 2
    # --------------------------------------------------------

    log(
        "[2] Connecting to IXBrowser via CDP..."
    )

    with sync_playwright() as p:

        browser = p.chromium.connect_over_cdp(
            f"http://{debugging_address}"
        )

        log("[OK] Connected")

        # ----------------------------------------------------
        # Browser context
        # ----------------------------------------------------

        contexts = browser.contexts

        if not contexts:
            raise RuntimeError(
                "No Playwright browser context found."
            )

        context = contexts[0]

        # ----------------------------------------------------
        # Page
        # ----------------------------------------------------

        page = get_or_create_flow_page(
            context
        )

        log(
            f"[OK] Using page: {page.url}"
        )

        # ----------------------------------------------------
        # STEP 3
        # ----------------------------------------------------

        log("[3] Opening Flow home...")

        try:
            page.goto(
                FLOW_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )
        except Exception as e:
            log(
                f"[INFO] page.goto result: {e}"
            )

        time.sleep(5)

        # ----------------------------------------------------
        # STEP 4
        # ----------------------------------------------------

        log("[4] Looking for New project...")

        new_project = None

        # First exact text
        try:

            candidate = page.get_by_text(
                "New project",
                exact=True
            )

            candidate.wait_for(
                state="visible",
                timeout=15000
            )

            new_project = candidate

        except Exception:
            pass

        # Fallback role=button
        if new_project is None:

            try:

                candidate = page.get_by_role(
                    "button",
                    name="New project"
                )

                candidate.wait_for(
                    state="visible",
                    timeout=15000
                )

                new_project = candidate

            except Exception:
                pass

        if new_project is None:
            raise RuntimeError(
                "New project button/text not found."
            )

        log("[OK] New project found")

        # ----------------------------------------------------
        # STEP 5
        # ----------------------------------------------------

        log("[5] Clicking New project...")

        new_project.click()

        # ----------------------------------------------------
        # STEP 6
        # ----------------------------------------------------

        if not wait_for_project(page):
            raise RuntimeError(
                "FLOW project UI did not appear."
            )

        # ----------------------------------------------------
        # STEP 7 + 8
        # ----------------------------------------------------

        fill_prompt(page)

        # ----------------------------------------------------
        # STEP 9 + 10
        # ----------------------------------------------------

        click_start_generation(page)

        # ----------------------------------------------------
        # STEP 11 + 12
        # ----------------------------------------------------

        wait_for_generation(page)

        # ----------------------------------------------------
        # STEP 13
        # ----------------------------------------------------

        log(
            "[13] Looking for generated images..."
        )

        images = get_large_visible_images(
            page
        )

        print_images(images)

        if not images:

            no_image_path = (
                SCREENSHOT_DIR /
                "NO_GENERATED_IMAGE.png"
            )

            page.screenshot(
                path=str(no_image_path),
                full_page=False
            )

            log(
                f"[ERROR] No generated image found."
            )

            log(
                f"Screenshot: {no_image_path}"
            )

            raise RuntimeError(
                "No large visible generated image found."
            )

        log(
            f"[OK] Found {len(images)} "
            f"large visible image(s)."
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # For this test we use FIRST generated image only.
        #
        # Once right-click behavior is confirmed,
        # we will loop through ALL generated images.
        # ----------------------------------------------------

        first_image = images[0]

        log(
            "[14] Starting RIGHT-CLICK test "
            "on first image..."
        )

        right_click_image(
            page,
            first_image,
            1
        )

        # ----------------------------------------------------
        # STEP 15
        # ----------------------------------------------------

        inspect_visible_menu(
            page
        )

        # ----------------------------------------------------
        # STEP 16
        # ----------------------------------------------------

        inspect_visible_buttons(
            page
        )

        # ----------------------------------------------------
        # Close menu
        # ----------------------------------------------------

        close_context_menu(
            page
        )

        # ----------------------------------------------------
        # DONE
        # ----------------------------------------------------

        log("")
        log(
            "================================================"
        )
        log("RIGHT-CLICK TEST FINISHED")
        log(
            "================================================"
        )

        log("")
        log(
            "Browser intentionally LEFT OPEN."
        )

        log("")
        log(
            "Check these screenshots:"
        )

        log(
            str(
                SCREENSHOT_DIR /
                "image_1_before_right_click.png"
            )
        )

        log(
            str(
                SCREENSHOT_DIR /
                "image_1_after_right_click.png"
            )
        )

        log("")
        log(
            "Paste the COMPLETE terminal output."
        )

        log(
            "Do not close the IXBrowser/Flow window."
        )

        log("")

        # ----------------------------------------------------
        # Keep browser alive
        # ----------------------------------------------------

        while True:
            time.sleep(5)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print("")
        print(
            "[STOP] Script stopped by user."
        )

    except Exception as e:

        print("")
        print(
            "================================================"
        )
        print("[ERROR]")
        print(str(e))
        print(
            "================================================"
        )

        raise
