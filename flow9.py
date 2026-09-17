import re
import time
import requests

from pathlib import Path
from datetime import datetime

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


# ============================================================
# PROMPT
# ============================================================

PROMPT = (
    "A cinematic realistic scene of a futuristic city at sunset, "
    "dramatic golden lighting, highly detailed architecture, "
    "photorealistic, cinematic composition"
)


# ============================================================
# TIMING
# ============================================================

PROJECT_TIMEOUT = 90

GENERATION_TIMEOUT = 300

# Generation stop hone ke baad Flow ko results settle karne ka time
POST_GENERATION_WAIT = 20

# Hover/menu timings
HOVER_WAIT = 1.5
MENU_WAIT = 1.0
SUBMENU_TIMEOUT = 10


# ============================================================
# LOG
# ============================================================

def log(message=""):
    print(message, flush=True)


# ============================================================
# IXBROWSER
# ============================================================

def open_ixbrowser_profile():

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

    log("[DEBUG] IXBrowser API response:")
    log(str(data))

    # --------------------------------------------------------
    # Correct IXBrowser success check
    # --------------------------------------------------------

    error = data.get("error", {})

    if error.get("code") != 0:
        raise RuntimeError(
            f"IXBrowser failed: {error}"
        )

    debugging_address = (
        data
        .get("data", {})
        .get("debugging_address")
    )

    if not debugging_address:
        raise RuntimeError(
            "debugging_address not found in IXBrowser response"
        )

    log("[OK] IXBrowser profile opened")
    log(f"CDP: {debugging_address}")

    return debugging_address


# ============================================================
# PAGE
# ============================================================

def get_flow_page(context):

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

    # Otherwise use existing page
    if pages:
        return pages[0]

    return context.new_page()


# ============================================================
# PROJECT WAIT
# ============================================================

def wait_for_project(page):

    log("[6] Waiting for FLOW project UI...")

    for i in range(PROJECT_TIMEOUT):

        # ----------------------------------------------------
        # URL
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
        # Editable prompt
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

    editable = page.locator(
        '[contenteditable="true"]'
    )

    for i in range(editable.count()):

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
# GENERATION
# ============================================================

def start_generation(page):

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


def stop_button_visible(page):

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


def wait_generation(page):

    log("[11] Waiting for generation to finish...")

    start_time = time.time()

    last_report = -1

    while True:

        elapsed = int(
            time.time() - start_time
        )

        if elapsed >= GENERATION_TIMEOUT:

            raise TimeoutError(
                "Generation timeout reached."
            )

        if stop_button_visible(page):

            ten_second_block = elapsed // 10

            if ten_second_block != last_report:

                last_report = ten_second_block

                log(
                    f"[WAIT] Generation running... "
                    f"{elapsed}s"
                )

            time.sleep(1)

            continue

        log(
            "[SIGNAL] Stop button disappeared."
        )

        break

    log(
        f"[12] Waiting additional "
        f"{POST_GENERATION_WAIT}s "
        "for result tiles..."
    )

    time.sleep(
        POST_GENERATION_WAIT
    )


# ============================================================
# IMAGE DETECTION
# ============================================================

def get_large_visible_images(page):

    images = page.locator("img")

    found = []

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

            # Ignore icons
            if width < 150:
                continue

            if height < 100:
                continue

            src = None

            try:
                src = img.get_attribute("src")
            except Exception:
                pass

            found.append({
                "locator": img,
                "index": i,
                "box": box,
                "src": src,
                "width": width,
                "height": height,
            })

        except Exception:
            continue

    return found


def deduplicate_images(images):

    """
    Same Flow image can appear in DOM more than once.
    Example from your output:

        Image 1 = 394x222
        Image 2 = 192x108

    Both had identical src.

    Keep only the largest occurrence.
    """

    by_src = {}

    no_src = []

    for item in images:

        src = item["src"]

        if not src:
            no_src.append(item)
            continue

        if src not in by_src:

            by_src[src] = item

            continue

        old = by_src[src]

        old_area = (
            old["width"] *
            old["height"]
        )

        new_area = (
            item["width"] *
            item["height"]
        )

        if new_area > old_area:
            by_src[src] = item

    result = list(by_src.values())

    # Images without src are retained
    result.extend(no_src)

    return result


def print_images(images):

    log("")
    log(
        "================================================"
    )
    log("GENERATED IMAGE CANDIDATES")
    log(
        "================================================"
    )

    for i, item in enumerate(images, start=1):

        box = item["box"]

        log(
            f"[IMAGE {i}] "
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
# IMAGE RIGHT CLICK
# ============================================================

def right_click_image(page, image, number):

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
        "Moving mouse to image center..."
    )

    log(
        f"    X={round(center_x)} "
        f"Y={round(center_y)}"
    )

    # Move to image center
    page.mouse.move(
        center_x,
        center_y,
        steps=20
    )

    time.sleep(HOVER_WAIT)

    log(
        f"[IMAGE {number}] "
        "Right-clicking image center..."
    )

    page.mouse.click(
        center_x,
        center_y,
        button="right"
    )

    time.sleep(MENU_WAIT)


# ============================================================
# FIND FLOW DOWNLOAD MENU ITEM
# ============================================================

def find_download_menu_item(page):

    """
    Finds the image-specific Flow menu item.

    We specifically inspect role=menuitem rather than
    page-wide buttons so project-level More isn't selected.
    """

    menuitems = page.get_by_role(
        "menuitem"
    )

    candidates = []

    for i in range(menuitems.count()):

        try:

            item = menuitems.nth(i)

            if not item.is_visible():
                continue

            text = item.inner_text().strip()

            # Normalize whitespace
            normalized = " ".join(
                text.split()
            )

            # Expected:
            # download Download
            if (
                normalized.lower() == "download"
                or
                normalized.lower().endswith(
                    " download"
                )
            ):

                candidates.append(item)

        except Exception:
            continue

    if candidates:
        return candidates[0]

    return None


# ============================================================
# HOVER DOWNLOAD
# ============================================================

def hover_download_menu_item(page):

    log(
        "[DOWNLOAD] Looking for Download menu item..."
    )

    deadline = (
        time.time() +
        SUBMENU_TIMEOUT
    )

    download_item = None

    while time.time() < deadline:

        download_item = (
            find_download_menu_item(page)
        )

        if download_item is not None:
            break

        time.sleep(0.25)

    if download_item is None:

        raise RuntimeError(
            "Flow Download menuitem not found."
        )

    log(
        "[DOWNLOAD] Download menu item found."
    )

    box = download_item.bounding_box()

    log(
        f"[DOWNLOAD] Menu item box: {box}"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # User specifically said Download par HOVER karna hai.
    # No click here.
    # --------------------------------------------------------

    download_item.hover(
        force=True
    )

    log(
        "[DOWNLOAD] Hovered Download..."
    )

    time.sleep(1.5)

    return download_item


# ============================================================
# FIND 1K DOWNLOAD OPTION
# ============================================================

def find_1k_option(page):

    """
    Search submenu for:

        Download 1K
        1K

    Also supports icon text + visible label.
    """

    # --------------------------------------------------------
    # First inspect menuitems
    # --------------------------------------------------------

    menuitems = page.get_by_role(
        "menuitem"
    )

    for i in range(menuitems.count()):

        try:

            item = menuitems.nth(i)

            if not item.is_visible():
                continue

            text = item.inner_text().strip()

            normalized = " ".join(
                text.split()
            )

            lower = normalized.lower()

            if (
                "1k" in lower
                or
                "1 k" in lower
            ):

                return item

        except Exception:
            pass

    # --------------------------------------------------------
    # Search visible text
    # --------------------------------------------------------

    selectors = [
        r"Download\s*1K",
        r"1K",
        r"1\s*K",
    ]

    for pattern in selectors:

        try:

            locator = page.get_by_text(
                re.compile(
                    pattern,
                    re.IGNORECASE
                )
            )

            for i in range(locator.count()):

                try:

                    item = locator.nth(i)

                    if not item.is_visible():
                        continue

                    return item

                except Exception:
                    pass

        except Exception:
            pass

    return None


# ============================================================
# WAIT FOR 1K
# ============================================================

def wait_for_1k_option(page):

    log(
        "[DOWNLOAD] Waiting for 1K submenu..."
    )

    deadline = (
        time.time() +
        SUBMENU_TIMEOUT
    )

    while time.time() < deadline:

        option = find_1k_option(page)

        if option is not None:

            try:

                text = option.inner_text().strip()

            except Exception:

                text = "1K"

            log(
                f"[DOWNLOAD] Found 1K option: "
                f"{text!r}"
            )

            try:
                log(
                    f"[DOWNLOAD] Box: "
                    f"{option.bounding_box()}"
                )
            except Exception:
                pass

            return option

        time.sleep(0.25)

    return None


# ============================================================
# SAVE DOWNLOAD
# ============================================================

def make_download_path(
    image_number,
    suggested_name
):

    # --------------------------------------------------------
    # Use extension from browser suggested filename
    # --------------------------------------------------------

    extension = ".png"

    if suggested_name:

        lower = suggested_name.lower()

        for ext in [
            ".png",
            ".jpg",
            ".jpeg",
            ".webp"
        ]:

            if lower.endswith(ext):

                extension = ext
                break

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"flow_image_"
        f"{image_number}_"
        f"{timestamp}"
        f"{extension}"
    )

    return DOWNLOAD_DIR / filename


# ============================================================
# DOWNLOAD ONE IMAGE
# ============================================================

def download_one_image(
    page,
    image,
    image_number
):

    log("")
    log(
        "================================================"
    )
    log(
        f"DOWNLOADING IMAGE {image_number}"
    )
    log(
        "================================================"
    )

    # --------------------------------------------------------
    # Open image-specific menu
    # --------------------------------------------------------

    right_click_image(
        page,
        image,
        image_number
    )

    # --------------------------------------------------------
    # Screenshot menu
    # --------------------------------------------------------

    menu_screenshot = (
        SCREENSHOT_DIR /
        f"image_{image_number}_download_menu.png"
    )

    page.screenshot(
        path=str(menu_screenshot),
        full_page=False
    )

    log(
        f"[DOWNLOAD] Menu screenshot: "
        f"{menu_screenshot}"
    )

    # --------------------------------------------------------
    # Hover Download
    # --------------------------------------------------------

    hover_download_menu_item(
        page
    )

    # --------------------------------------------------------
    # Screenshot submenu
    # --------------------------------------------------------

    submenu_screenshot = (
        SCREENSHOT_DIR /
        f"image_{image_number}_download_submenu.png"
    )

    page.screenshot(
        path=str(submenu_screenshot),
        full_page=False
    )

    log(
        f"[DOWNLOAD] Submenu screenshot: "
        f"{submenu_screenshot}"
    )

    # --------------------------------------------------------
    # Find 1K
    # --------------------------------------------------------

    option = wait_for_1k_option(
        page
    )

    if option is None:

        # Dump visible menuitems for debugging
        log("")
        log(
            "[DOWNLOAD] 1K option NOT FOUND."
        )

        log(
            "[DOWNLOAD] Current visible menuitems:"
        )

        menuitems = page.get_by_role(
            "menuitem"
        )

        for i in range(menuitems.count()):

            try:

                item = menuitems.nth(i)

                if not item.is_visible():
                    continue

                log(
                    f"    {i}: "
                    f"{item.inner_text()!r}"
                )

            except Exception:
                pass

        raise RuntimeError(
            "Download submenu opened, "
            "but Download 1K / 1K was not found."
        )

    # --------------------------------------------------------
    # Screenshot before actual click
    # --------------------------------------------------------

    before_download = (
        SCREENSHOT_DIR /
        f"image_{image_number}_before_1k_click.png"
    )

    page.screenshot(
        path=str(before_download),
        full_page=False
    )

    log(
        f"[DOWNLOAD] Before 1K click screenshot: "
        f"{before_download}"
    )

    # --------------------------------------------------------
    # ACTUAL DOWNLOAD
    #
    # Playwright waits for browser download event.
    # --------------------------------------------------------

    log(
        "[DOWNLOAD] Clicking 1K..."
    )

    try:

        with page.expect_download(
            timeout=30000
        ) as download_info:

            option.click(
                force=True
            )

        download = download_info.value

    except Exception as e:

        log(
            f"[DOWNLOAD] expect_download failed: "
            f"{e}"
        )

        # Save screenshot for diagnosis
        error_path = (
            SCREENSHOT_DIR /
            f"image_{image_number}_download_error.png"
        )

        page.screenshot(
            path=str(error_path),
            full_page=False
        )

        raise

    # --------------------------------------------------------
    # Save file
    # --------------------------------------------------------

    suggested_name = (
        download.suggested_filename
    )

    output_path = make_download_path(
        image_number,
        suggested_name
    )

    download.save_as(
        str(output_path)
    )

    log("")
    log(
        "[OK] IMAGE DOWNLOADED"
    )

    log(
        f"    Suggested name: "
        f"{suggested_name}"
    )

    log(
        f"    Saved to: "
        f"{output_path}"
    )

    # --------------------------------------------------------
    # Verify file
    # --------------------------------------------------------

    if output_path.exists():

        size = output_path.stat().st_size

        log(
            f"    File size: "
            f"{size:,} bytes"
        )

        if size == 0:

            raise RuntimeError(
                "Downloaded file exists but is 0 bytes."
            )

    else:

        raise RuntimeError(
            "Download event happened but "
            "saved file was not found."
        )

    log(
        "================================================"
    )
    log("")

    # Small pause before next image
    time.sleep(1)

    return output_path


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # 1. IXBrowser
    # --------------------------------------------------------

    debugging_address = (
        open_ixbrowser_profile()
    )

    # --------------------------------------------------------
    # Playwright
    # --------------------------------------------------------

    with sync_playwright() as p:

        log(
            "[2] Connecting to IXBrowser via CDP..."
        )

        browser = p.chromium.connect_over_cdp(
            f"http://{debugging_address}"
        )

        log("[OK] Connected")

        if not browser.contexts:

            raise RuntimeError(
                "No browser context found."
            )

        context = browser.contexts[0]

        # ----------------------------------------------------
        # Page
        # ----------------------------------------------------

        page = get_flow_page(
            context
        )

        log(
            f"[OK] Using page: {page.url}"
        )

        # ----------------------------------------------------
        # 3. Flow
        # ----------------------------------------------------

        log(
            "[3] Opening Flow home..."
        )

        try:

            page.goto(
                FLOW_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

        except Exception as e:

            log(
                f"[INFO] page.goto: {e}"
            )

        time.sleep(5)

        # ----------------------------------------------------
        # 4. New project
        # ----------------------------------------------------

        log(
            "[4] Looking for New project..."
        )

        new_project = None

        # Exact text
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

        # Button fallback
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
                "New project not found."
            )

        log(
            "[OK] New project found"
        )

        # ----------------------------------------------------
        # 5. Click
        # ----------------------------------------------------

        log(
            "[5] Clicking New project..."
        )

        new_project.click()

        # ----------------------------------------------------
        # 6. Project
        # ----------------------------------------------------

        if not wait_for_project(page):

            raise RuntimeError(
                "FLOW project UI did not appear."
            )

        # ----------------------------------------------------
        # 7 + 8. Prompt
        # ----------------------------------------------------

        fill_prompt(page)

        # ----------------------------------------------------
        # 9 + 10. Generate
        # ----------------------------------------------------

        start_generation(page)

        # ----------------------------------------------------
        # 11 + 12. Wait
        # ----------------------------------------------------

        wait_generation(page)

        # ----------------------------------------------------
        # 13. Find images
        # ----------------------------------------------------

        log(
            "[13] Looking for generated images..."
        )

        raw_images = get_large_visible_images(
            page
        )

        log(
            f"[INFO] Raw image candidates: "
            f"{len(raw_images)}"
        )

        print_images(
            raw_images
        )

        # ----------------------------------------------------
        # Deduplicate
        # ----------------------------------------------------

        images = deduplicate_images(
            raw_images
        )

        log(
            f"[OK] Unique generated images: "
            f"{len(images)}"
        )

        print_images(
            images
        )

        if not images:

            error_path = (
                SCREENSHOT_DIR /
                "NO_GENERATED_IMAGES.png"
            )

            page.screenshot(
                path=str(error_path),
                full_page=False
            )

            raise RuntimeError(
                "No generated images found."
            )

        # ----------------------------------------------------
        # Download ALL unique images
        # ----------------------------------------------------

        downloaded = []

        for number, image in enumerate(
            images,
            start=1
        ):

            try:

                output = download_one_image(
                    page,
                    image,
                    number
                )

                downloaded.append(
                    output
                )

            except Exception as e:

                log("")
                log(
                    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                )

                log(
                    f"[ERROR] Image {number} "
                    f"download failed:"
                )

                log(
                    str(e)
                )

                log(
                    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                )

                # Continue with next image
                # instead of killing whole run.
                try:
                    page.keyboard.press(
                        "Escape"
                    )
                except Exception:
                    pass

                time.sleep(1)

        # ----------------------------------------------------
        # Final report
        # ----------------------------------------------------

        log("")
        log(
            "================================================"
        )
        log("FINAL DOWNLOAD REPORT")
        log(
            "================================================"
        )

        log(
            f"Detected unique images: "
            f"{len(images)}"
        )

        log(
            f"Successfully downloaded: "
            f"{len(downloaded)}"
        )

        for i, path in enumerate(
            downloaded,
            start=1
        ):

            log(
                f"[FILE {i}] {path}"
            )

        log(
            "================================================"
        )

        log("")
        log(
            f"Downloads folder:"
        )

        log(
            str(DOWNLOAD_DIR)
        )

        log("")
        log(
            "Browser intentionally remains OPEN."
        )

        log(
            "Press Ctrl+C when you want to stop."
        )

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

        print(
            "[FATAL ERROR]"
        )

        print(
            str(e)
        )

        print(
            "================================================"
        )

        raise
