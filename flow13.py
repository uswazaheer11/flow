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
# VIDEO PROMPT
# ============================================================

VIDEO_PROMPT = (
    "The camera slowly moves forward through the futuristic city. "
    "Buildings and lights move naturally with realistic cinematic motion, "
    "subtle atmospheric movement, dramatic golden sunset lighting, "
    "photorealistic cinematic camera movement, highly detailed, "
    "smooth natural motion."
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
# VIDEO TIMING
# ============================================================

VIDEO_UI_TIMEOUT = 30

VIDEO_GENERATION_TIMEOUT = 600

VIDEO_POST_GENERATION_WAIT = 20

VIDEO_UPLOAD_WAIT = 5

VIDEO_MINIMUM_WAIT = 180

VIDEO_RESULT_EXTRA_TIMEOUT = 420


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
# ============================================================
# VIDEO SECTION - NEW CODE
# ============================================================
# ============================================================


# ============================================================
# PRINT CURRENT VIDEO-RELATED UI
# ============================================================

def print_video_ui(page):

    log("")
    log(
        "================================================"
    )
    log(
        "VIDEO UI INSPECTION"
    )
    log(
        "================================================"
    )

    # --------------------------------------------------------
    # Buttons
    # --------------------------------------------------------

    buttons = page.get_by_role("button")

    log(
        f"[VIDEO DEBUG] Buttons found: {buttons.count()}"
    )

    for i in range(buttons.count()):

        try:

            button = buttons.nth(i)

            if not button.is_visible():
                continue

            text = ""

            aria = ""

            try:
                text = button.inner_text().strip()
            except Exception:
                pass

            try:
                aria = (
                    button.get_attribute("aria-label")
                    or ""
                )
            except Exception:
                pass

            normalized = " ".join(
                text.split()
            )

            if (
                normalized
                or
                aria
            ):

                log(
                    f"[BUTTON {i}] "
                    f"text={normalized!r} "
                    f"aria={aria!r}"
                )

        except Exception:
            pass

    # --------------------------------------------------------
    # Visible text around Video / Ingredients / Add Image
    # --------------------------------------------------------

    important_patterns = [
        r"^Video$",
        r"^Image$",
        r"Ingredients",
        r"Add Image",
        r"Upload",
        r"Generate Image",
        r"Start generation",
    ]

    for pattern in important_patterns:

        try:

            locator = page.get_by_text(
                re.compile(
                    pattern,
                    re.IGNORECASE
                )
            )

            for i in range(locator.count()):

                try:

                    el = locator.nth(i)

                    if not el.is_visible():
                        continue

                    log(
                        f"[VIDEO TEXT] "
                        f"pattern={pattern!r} "
                        f"text={el.inner_text().strip()!r}"
                    )

                except Exception:
                    pass

        except Exception:
            pass

    log(
        "================================================"
    )
    log("")


# ============================================================
# FIND VIDEO MODEL SELECTOR
# ============================================================

def find_video_model_selector(page):

    """
    Google Flow normally has a model/generation selector
    around the prompt box.

    We search visible buttons using text / aria-label.
    """

    buttons = page.get_by_role(
        "button"
    )

    candidates = []

    for i in range(buttons.count()):

        try:

            button = buttons.nth(i)

            if not button.is_visible():
                continue

            text = ""

            aria = ""

            try:
                text = button.inner_text().strip()
            except Exception:
                pass

            try:
                aria = (
                    button.get_attribute(
                        "aria-label"
                    )
                    or ""
                )
            except Exception:
                pass

            combined = (
                f"{text} {aria}"
            ).lower()

            # Current Flow model names commonly contain
            # Nano / Veo / model information.
            if (
                "nano" in combined
                or
                "veo" in combined
                or
                "model" in combined
            ):

                candidates.append(button)

        except Exception:
            pass

    if candidates:

        # Prefer the smallest/most compact visible
        # candidate around prompt controls.
        for button in candidates:

            try:

                box = button.bounding_box()

                if not box:
                    continue

                if box["y"] > 400:

                    return button

            except Exception:
                pass

        return candidates[-1]

    return None


# ============================================================
# CLICK VIDEO MODEL SELECTOR
# ============================================================

def open_video_settings(page):

    log(
        "[VIDEO 1] Looking for Flow model selector..."
    )

    selector = find_video_model_selector(
        page
    )

    if selector is None:

        log(
            "[VIDEO] Model selector not found."
        )

        print_video_ui(page)

        debug_path = (
            SCREENSHOT_DIR /
            "video_model_selector_not_found.png"
        )

        page.screenshot(
            path=str(debug_path),
            full_page=False
        )

        raise RuntimeError(
            "Video model selector not found."
        )

    log(
        "[VIDEO] Model selector found."
    )

    try:

        log(
            f"[VIDEO] Selector text: "
            f"{selector.inner_text().strip()!r}"
        )

    except Exception:
        pass

    try:

        log(
            f"[VIDEO] Selector aria: "
            f"{selector.get_attribute('aria-label')!r}"
        )

    except Exception:
        pass

    selector.click()

    time.sleep(1)

    log(
        "[VIDEO] Model selector clicked."
    )


# ============================================================
# CLICK VIDEO
# ============================================================

def click_video_option(page):

    log(
        "[VIDEO 2] Looking for Video option..."
    )

    deadline = (
        time.time() +
        VIDEO_UI_TIMEOUT
    )

    while time.time() < deadline:

        # ----------------------------------------------------
        # Exact text Video
        # ----------------------------------------------------

        try:

            locator = page.get_by_text(
                "Video",
                exact=True
            )

            for i in range(locator.count()):

                try:

                    item = locator.nth(i)

                    if not item.is_visible():
                        continue

                    log(
                        "[VIDEO] Video option found."
                    )

                    item.click(
                        force=True
                    )

                    time.sleep(1)

                    log(
                        "[VIDEO] Video option clicked."
                    )

                    return True

                except Exception:
                    pass

        except Exception:
            pass

        # ----------------------------------------------------
        # Role menuitem fallback
        # ----------------------------------------------------

        try:

            menuitems = page.get_by_role(
                "menuitem"
            )

            for i in range(menuitems.count()):

                try:

                    item = menuitems.nth(i)

                    if not item.is_visible():
                        continue

                    text = " ".join(
                        item.inner_text().split()
                    )

                    if text.lower() == "video":

                        log(
                            "[VIDEO] Video menuitem found."
                        )

                        item.click(
                            force=True
                        )

                        time.sleep(1)

                        return True

                except Exception:
                    pass

        except Exception:
            pass

        time.sleep(0.25)

    print_video_ui(page)

    raise RuntimeError(
        "Video option was not found."
    )


# ============================================================
# CLICK INGREDIENTS
# ============================================================

def click_ingredients_option(page):

    log(
        "[VIDEO 3] Looking for Ingredients option..."
    )

    deadline = (
        time.time() +
        VIDEO_UI_TIMEOUT
    )

    while time.time() < deadline:

        # ----------------------------------------------------
        # Exact/partial text
        # ----------------------------------------------------

        try:

            locator = page.get_by_text(
                re.compile(
                    r"^Ingredients$",
                    re.IGNORECASE
                )
            )

            for i in range(locator.count()):

                try:

                    item = locator.nth(i)

                    if not item.is_visible():
                        continue

                    log(
                        "[VIDEO] Ingredients option found."
                    )

                    item.click(
                        force=True
                    )

                    time.sleep(1)

                    log(
                        "[VIDEO] Ingredients selected."
                    )

                    return True

                except Exception:
                    pass

        except Exception:
            pass

        # ----------------------------------------------------
        # Menuitem fallback
        # ----------------------------------------------------

        try:

            menuitems = page.get_by_role(
                "menuitem"
            )

            for i in range(menuitems.count()):

                try:

                    item = menuitems.nth(i)

                    if not item.is_visible():
                        continue

                    text = " ".join(
                        item.inner_text().split()
                    )

                    if text.lower() == "ingredients":

                        item.click(
                            force=True
                        )

                        time.sleep(1)

                        return True

                except Exception:
                    pass

        except Exception:
            pass

        time.sleep(0.25)

    print_video_ui(page)

    raise RuntimeError(
        "Ingredients option was not found."
    )


# ============================================================
# FIND ADD IMAGE CONTROL
# ============================================================

def find_add_image_control(page):

    # --------------------------------------------------------
    # First try exact visible text
    # --------------------------------------------------------

    try:

        locator = page.get_by_text(
            re.compile(
                r"^Add Image$",
                re.IGNORECASE
            )
        )

        for i in range(locator.count()):

            try:

                item = locator.nth(i)

                if item.is_visible():

                    return item

            except Exception:
                pass

    except Exception:
        pass

    # --------------------------------------------------------
    # Buttons
    # --------------------------------------------------------

    buttons = page.get_by_role(
        "button"
    )

    for i in range(buttons.count()):

        try:

            button = buttons.nth(i)

            if not button.is_visible():
                continue

            text = ""

            aria = ""

            try:
                text = button.inner_text().strip()
            except Exception:
                pass

            try:
                aria = (
                    button.get_attribute(
                        "aria-label"
                    )
                    or ""
                )
            except Exception:
                pass

            combined = (
                f"{text} {aria}"
            ).lower()

            if "add image" in combined:

                return button

        except Exception:
            pass

    return None


# ============================================================
# UPLOAD IMAGE THROUGH ADD IMAGE
# ============================================================

def upload_video_ingredient(
    page,
    image_path
):

    log(
        "[VIDEO 4] Adding downloaded image as ingredient..."
    )

    image_path = Path(
        image_path
    ).resolve()

    if not image_path.exists():

        raise FileNotFoundError(
            f"Video ingredient image not found: "
            f"{image_path}"
        )

    log(
        f"[VIDEO] Ingredient file:"
    )

    log(
        f"        {image_path}"
    )

    # --------------------------------------------------------
    # First inspect current UI
    # --------------------------------------------------------

    add_image = find_add_image_control(
        page
    )

    if add_image is None:

        log(
            "[VIDEO] Add Image control not found."
        )

        print_video_ui(page)

        debug_path = (
            SCREENSHOT_DIR /
            "video_add_image_not_found.png"
        )

        page.screenshot(
            path=str(debug_path),
            full_page=False
        )

        raise RuntimeError(
            "Add Image control not found."
        )

    log(
        "[VIDEO] Add Image control found."
    )

    # --------------------------------------------------------
    # Try direct file chooser
    # --------------------------------------------------------

    try:

        log(
            "[VIDEO] Trying direct file chooser..."
        )

        with page.expect_file_chooser(
            timeout=5000
        ) as chooser_info:

            add_image.click(
                force=True
            )

        chooser = chooser_info.value

        chooser.set_files(
            str(image_path)
        )

        log(
            "[OK] Image sent to file chooser."
        )

        time.sleep(
            VIDEO_UPLOAD_WAIT
        )

        return True

    except Exception as direct_error:

        log(
            "[VIDEO] Direct file chooser did not open."
        )

        log(
            f"[VIDEO] Reason: {direct_error}"
        )

    # --------------------------------------------------------
    # Fallback:
    # click Add Image and inspect popup
    # --------------------------------------------------------

    try:

        add_image.click(
            force=True
        )

    except Exception:

        raise RuntimeError(
            "Could not click Add Image."
        )

    time.sleep(1)

    log(
        "[VIDEO] Add Image menu opened."
    )

    # Screenshot
    popup_path = (
        SCREENSHOT_DIR /
        "video_add_image_menu.png"
    )

    page.screenshot(
        path=str(popup_path),
        full_page=False
    )

    log(
        f"[VIDEO] Add Image menu screenshot: "
        f"{popup_path}"
    )

    # --------------------------------------------------------
    # Find Upload / Upload Image / Media
    # --------------------------------------------------------

    upload_patterns = [
        r"^Upload$",
        r"^Upload Image$",
        r"^Media$",
    ]

    upload_control = None

    for pattern in upload_patterns:

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

                    upload_control = item

                    break

                except Exception:
                    pass

        except Exception:
            pass

        if upload_control is not None:
            break

    if upload_control is None:

        log(
            "[VIDEO] Upload option not found."
        )

        print_video_ui(page)

        raise RuntimeError(
            "Upload option under Add Image not found."
        )

    log(
        "[VIDEO] Upload option found."
    )

    # --------------------------------------------------------
    # Click Upload while capturing chooser
    # --------------------------------------------------------

    try:

        with page.expect_file_chooser(
            timeout=10000
        ) as chooser_info:

            upload_control.click(
                force=True
            )

        chooser = chooser_info.value

        chooser.set_files(
            str(image_path)
        )

    except Exception as e:

        raise RuntimeError(
            f"File chooser upload failed: {e}"
        )

    log(
        "[OK] Ingredient image uploaded."
    )

    time.sleep(
        VIDEO_UPLOAD_WAIT
    )

    return True


# ============================================================
# VIDEO PROMPT
# ============================================================

def fill_video_prompt(page):

    log(
        "[VIDEO 5] Looking for prompt box..."
    )

    prompt = find_prompt(
        page
    )

    if prompt is None:

        raise RuntimeError(
            "Video prompt contenteditable not found."
        )

    log(
        "[VIDEO] Video prompt box found."
    )

    prompt.fill(
        VIDEO_PROMPT
    )

    time.sleep(1)

    log(
        "[OK] Video prompt filled."
    )


# ============================================================
# VIDEO GENERATE BUTTON
# ============================================================

def find_video_generate_button(page):

    names = [
        "Generate Image",
        "Start generation",
        "Generate",
    ]

    for name in names:

        try:

            locator = page.get_by_role(
                "button",
                name=name,
                exact=True
            )

            for i in range(locator.count()):

                try:

                    button = locator.nth(i)

                    if button.is_visible():

                        return button

                except Exception:
                    pass

        except Exception:
            pass

    # --------------------------------------------------------
    # Regex fallback
    # --------------------------------------------------------

    try:

        buttons = page.get_by_role(
            "button"
        )

        for i in range(buttons.count()):

            try:

                button = buttons.nth(i)

                if not button.is_visible():
                    continue

                text = (
                    button.inner_text()
                    .strip()
                    .lower()
                )

                if (
                    "generate image" in text
                    or
                    text == "generate"
                    or
                    "start generation" in text
                ):

                    return button

            except Exception:
                pass

    except Exception:
        pass

    return None


def start_video_generation(page):

    log(
        "[VIDEO 6] Looking for video Generate button..."
    )

    button = find_video_generate_button(
        page
    )

    if button is None:

        log(
            "[VIDEO] Generate button not found."
        )

        print_video_ui(page)

        debug_path = (
            SCREENSHOT_DIR /
            "video_generate_button_not_found.png"
        )

        page.screenshot(
            path=str(debug_path),
            full_page=False
        )

        raise RuntimeError(
            "Video Generate button not found."
        )

    try:

        log(
            f"[VIDEO] Generate button text: "
            f"{button.inner_text().strip()!r}"
        )

    except Exception:
        pass

    button.click(
        force=True
    )

    log(
        "[OK] Video generation clicked."
    )


# ============================================================
# VIDEO GENERATION WAIT
# ============================================================

def wait_video_generation(page):

    log(
        "[VIDEO 7] Waiting for video generation..."
    )

    start_time = time.time()

    last_report = -1

    while True:

        elapsed = int(
            time.time() -
            start_time
        )

        if elapsed >= VIDEO_GENERATION_TIMEOUT:

            raise TimeoutError(
                "Video generation timeout reached."
            )

        if stop_button_visible(page):

            ten_second_block = (
                elapsed // 10
            )

            if (
                ten_second_block !=
                last_report
            ):

                last_report = (
                    ten_second_block
                )

                log(
                    f"[WAIT] Video generation "
                    f"running... {elapsed}s"
                )

            time.sleep(1)

            continue

        log(
            "[SIGNAL] Video Stop button disappeared."
        )

        break

    log(
        f"[VIDEO 8] Waiting additional "
        f"{VIDEO_POST_GENERATION_WAIT}s "
        "for video result..."
    )

    time.sleep(
        VIDEO_POST_GENERATION_WAIT
    )


# ============================================================
# VIDEO DETECTION
# ============================================================

def get_visible_videos(page):

    videos = page.locator(
        "video"
    )

    found = []

    for i in range(
        videos.count()
    ):

        try:

            video = videos.nth(i)

            if not video.is_visible():
                continue

            box = video.bounding_box()

            if not box:
                continue

            width = box["width"]
            height = box["height"]

            if width < 150:
                continue

            if height < 80:
                continue

            src = None

            try:
                src = video.get_attribute(
                    "src"
                )
            except Exception:
                pass

            poster = None

            try:
                poster = video.get_attribute(
                    "poster"
                )
            except Exception:
                pass

            found.append({
                "locator": video,
                "index": i,
                "box": box,
                "src": src,
                "poster": poster,
                "width": width,
                "height": height,
            })

        except Exception:
            continue

    return found


# ============================================================
# VIDEO DETECTION - ALSO SEARCH SOURCE
# ============================================================

def get_video_candidates(page):

    found = []

    # --------------------------------------------------------
    # Actual video elements
    # --------------------------------------------------------

    found.extend(
        get_visible_videos(page)
    )

    # --------------------------------------------------------
    # Source elements
    # --------------------------------------------------------

    try:

        sources = page.locator(
            "video source"
        )

        for i in range(
            sources.count()
        ):

            try:

                source = sources.nth(i)

                src = source.get_attribute(
                    "src"
                )

                if not src:
                    continue

                parent = source.locator(
                    ".."
                )

                box = parent.bounding_box()

                if not box:
                    continue

                found.append({
                    "locator": parent,
                    "index": i,
                    "box": box,
                    "src": src,
                    "poster": None,
                    "width": box["width"],
                    "height": box["height"],
                })

            except Exception:
                pass

    except Exception:
        pass

    return found


def deduplicate_videos(videos):

    by_src = {}

    no_src = []

    for item in videos:

        src = item.get(
            "src"
        )

        if not src:

            no_src.append(
                item
            )

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

    result = list(
        by_src.values()
    )

    result.extend(
        no_src
    )

    return result


def print_videos(videos):

    log("")
    log(
        "================================================"
    )
    log(
        "GENERATED VIDEO CANDIDATES"
    )
    log(
        "================================================"
    )

    for i, item in enumerate(
        videos,
        start=1
    ):

        box = item["box"]

        log(
            f"[VIDEO {i}] "
            f"x={round(box['x'])} "
            f"y={round(box['y'])} "
            f"w={round(box['width'])} "
            f"h={round(box['height'])}"
        )

        log(
            f"    src={item.get('src')}"
        )

        log(
            f"    poster={item.get('poster')}"
        )

    log(
        "================================================"
    )
    log("")


# ============================================================
# WAIT FOR GENERATED VIDEO
# ============================================================

def wait_for_generated_videos(page):

    log(
        "[VIDEO 9] Looking for generated videos..."
    )

    deadline = (
        time.time() +
        VIDEO_UI_TIMEOUT
    )

    while time.time() < deadline:

        raw_videos = get_video_candidates(
            page
        )

        videos = deduplicate_videos(
            raw_videos
        )

        if videos:

            log(
                f"[OK] Generated video candidates: "
                f"{len(videos)}"
            )

            print_videos(
                videos
            )

            return videos

        time.sleep(1)

    debug_path = (
        SCREENSHOT_DIR /
        "NO_GENERATED_VIDEOS.png"
    )

    page.screenshot(
        path=str(debug_path),
        full_page=False
    )

    log(
        f"[VIDEO] No video element detected."
    )

    log(
        f"[VIDEO] Screenshot: {debug_path}"
    )

    # --------------------------------------------------------
    # Debug DOM
    # --------------------------------------------------------

    try:

        html = page.locator(
            "body"
        ).inner_text()

        debug_text = (
            SCREENSHOT_DIR /
            "video_no_result_text.txt"
        )

        debug_text.write_text(
            html,
            encoding="utf-8"
        )

        log(
            f"[VIDEO] Page text saved: "
            f"{debug_text}"
        )

    except Exception:
        pass

    raise RuntimeError(
        "Video generation completed, "
        "but no generated video element was detected."
    )


# ============================================================
# DOWNLOAD GENERATED VIDEO
# ============================================================

def find_video_download_menu_item(page):

    menuitems = page.get_by_role(
        "menuitem"
    )

    for i in range(
        menuitems.count()
    ):

        try:

            item = menuitems.nth(i)

            if not item.is_visible():
                continue

            text = " ".join(
                item.inner_text().split()
            )

            if text.lower() == "download":

                return item

        except Exception:
            pass

    return None


def find_video_download_option(page):

    """
    Video Flow download submenu can contain
    multiple file/resolution choices.

    We first look for MP4/video options.
    """

    menuitems = page.get_by_role(
        "menuitem"
    )

    candidates = []

    for i in range(
        menuitems.count()
    ):

        try:

            item = menuitems.nth(i)

            if not item.is_visible():
                continue

            text = " ".join(
                item.inner_text().split()
            )

            lower = text.lower()

            if (
                "mp4" in lower
                or
                "video" in lower
                or
                "720" in lower
                or
                "1080" in lower
                or
                "360" in lower
            ):

                candidates.append(
                    item
                )

        except Exception:
            pass

    if candidates:

        return candidates[0]

    return None


# ============================================================
# DOWNLOAD ONE VIDEO
# ============================================================

def download_one_video(
    page,
    video,
    video_number
):

    log("")
    log(
        "================================================"
    )
    log(
        f"DOWNLOADING VIDEO {video_number}"
    )
    log(
        "================================================"
    )

    box = video["box"]

    center_x = (
        box["x"] +
        box["width"] / 2
    )

    center_y = (
        box["y"] +
        box["height"] / 2
    )

    log(
        f"[VIDEO DOWNLOAD] "
        f"Moving to video center "
        f"X={round(center_x)} "
        f"Y={round(center_y)}"
    )

    page.mouse.move(
        center_x,
        center_y,
        steps=20
    )

    time.sleep(
        HOVER_WAIT
    )

    log(
        "[VIDEO DOWNLOAD] Right-clicking video..."
    )

    page.mouse.click(
        center_x,
        center_y,
        button="right"
    )

    time.sleep(
        MENU_WAIT
    )

    menu_path = (
        SCREENSHOT_DIR /
        f"video_{video_number}_download_menu.png"
    )

    page.screenshot(
        path=str(menu_path),
        full_page=False
    )

    log(
        f"[VIDEO DOWNLOAD] Menu screenshot: "
        f"{menu_path}"
    )

    # --------------------------------------------------------
    # Download menu
    # --------------------------------------------------------

    download_item = None

    deadline = (
        time.time() +
        SUBMENU_TIMEOUT
    )

    while time.time() < deadline:

        download_item = (
            find_video_download_menu_item(
                page
            )
        )

        if download_item is not None:
            break

        time.sleep(
            0.25
        )

    if download_item is None:

        raise RuntimeError(
            "Video Download menuitem not found."
        )

    log(
        "[VIDEO DOWNLOAD] Download menu found."
    )

    # --------------------------------------------------------
    # Hover Download
    # --------------------------------------------------------

    download_item.hover(
        force=True
    )

    log(
        "[VIDEO DOWNLOAD] Hovered Download."
    )

    time.sleep(
        1.5
    )

    submenu_path = (
        SCREENSHOT_DIR /
        f"video_{video_number}_download_submenu.png"
    )

    page.screenshot(
        path=str(submenu_path),
        full_page=False
    )

    log(
        f"[VIDEO DOWNLOAD] Submenu screenshot: "
        f"{submenu_path}"
    )

    # --------------------------------------------------------
    # Find video option
    # --------------------------------------------------------

    option = find_video_download_option(
        page
    )

    if option is None:

        log(
            "[VIDEO DOWNLOAD] Video download option "
            "not found."
        )

        log(
            "[VIDEO DOWNLOAD] Visible menuitems:"
        )

        menuitems = page.get_by_role(
            "menuitem"
        )

        for i in range(
            menuitems.count()
        ):

            try:

                item = menuitems.nth(i)

                if not item.is_visible():
                    continue

                log(
                    f"    [{i}] "
                    f"{item.inner_text()!r}"
                )

            except Exception:
                pass

        raise RuntimeError(
            "Video download submenu option not found."
        )

    log(
        f"[VIDEO DOWNLOAD] Selected option: "
        f"{option.inner_text().strip()!r}"
    )

    # --------------------------------------------------------
    # Download event
    # --------------------------------------------------------

    with page.expect_download(
        timeout=30000
    ) as download_info:

        option.click(
            force=True
        )

    download = download_info.value

    suggested_name = (
        download.suggested_filename
    )

    extension = ".mp4"

    if suggested_name:

        lower = suggested_name.lower()

        for ext in [
            ".mp4",
            ".mov",
            ".webm",
            ".avi"
        ]:

            if lower.endswith(ext):

                extension = ext

                break

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        DOWNLOAD_DIR /
        f"flow_video_"
        f"{video_number}_"
        f"{timestamp}"
        f"{extension}"
    )

    download.save_as(
        str(output_path)
    )

    log("")
    log(
        "[OK] VIDEO DOWNLOADED"
    )

    log(
        f"    Suggested name: "
        f"{suggested_name}"
    )

    log(
        f"    Saved to: "
        f"{output_path}"
    )

    if not output_path.exists():

        raise RuntimeError(
            "Video download event occurred "
            "but file was not found."
        )

    size = output_path.stat().st_size

    log(
        f"    File size: "
        f"{size:,} bytes"
    )

    if size == 0:

        raise RuntimeError(
            "Video file is 0 bytes."
        )

    log(
        "================================================"
    )

    return output_path




# ============================================================
# ============================================================
# ANIMATE PIPELINE - NEW
# ============================================================
# ============================================================


def find_animate_menu_item(page):

    log(
        "[ANIMATE] Looking for Animate menu item..."
    )

    menuitems = page.get_by_role(
        "menuitem"
    )

    deadline = (
        time.time() +
        SUBMENU_TIMEOUT
    )

    while time.time() < deadline:

        for i in range(menuitems.count()):

            try:

                item = menuitems.nth(i)

                if not item.is_visible():
                    continue

                text = " ".join(
                    item.inner_text().split()
                )

                normalized = text.lower()

                log(
                    f"[ANIMATE DEBUG] "
                    f"menuitem={text!r}"
                )

                if normalized == "animate":
                    return item

                if normalized.endswith(
                    " animate"
                ):
                    return item

            except Exception:
                pass

        time.sleep(0.25)

    return None


def get_current_generated_image_for_animate(page):

    log(
        "[ANIMATE] Re-finding generated Flow image..."
    )

    images = get_large_visible_images(
        page
    )

    if not images:

        raise RuntimeError(
            "No generated Flow image found "
            "for Animate."
        )

    # --------------------------------------------------------
    # Largest visible image is preferred.
    # This matches the already-confirmed Flow DOM where
    # duplicate <img> elements can exist for the same output.
    # --------------------------------------------------------

    images = deduplicate_images(
        images
    )

    images.sort(
        key=lambda item: (
            item["width"] *
            item["height"]
        ),
        reverse=True
    )

    image = images[0]

    log(
        "[ANIMATE] Generated image selected:"
    )

    log(
        f"    width={round(image['width'])}"
    )

    log(
        f"    height={round(image['height'])}"
    )

    log(
        f"    src={image['src']}"
    )

    return image


def open_animate_from_image(
    page,
    image
):

    log("")
    log(
        "================================================"
    )
    log(
        "OPENING FLOW ANIMATE"
    )
    log(
        "================================================"
    )

    # --------------------------------------------------------
    # Use the original generated Flow image.
    #
    # IMPORTANT:
    # We are NOT uploading the downloaded JPEG.
    # --------------------------------------------------------

    box = image["box"]

    center_x = (
        box["x"] +
        box["width"] / 2
    )

    center_y = (
        box["y"] +
        box["height"] / 2
    )

    log(
        f"[ANIMATE] Image center:"
    )

    log(
        f"    X={round(center_x)}"
    )

    log(
        f"    Y={round(center_y)}"
    )

    # --------------------------------------------------------
    # Move to generated image
    # --------------------------------------------------------

    page.mouse.move(
        center_x,
        center_y,
        steps=20
    )

    time.sleep(
        HOVER_WAIT
    )

    # --------------------------------------------------------
    # Right click generated image
    # --------------------------------------------------------

    log(
        "[ANIMATE] Right-clicking generated image..."
    )

    page.mouse.click(
        center_x,
        center_y,
        button="right"
    )

    time.sleep(
        MENU_WAIT
    )

    # --------------------------------------------------------
    # Debug screenshot
    # --------------------------------------------------------

    menu_path = (
        SCREENSHOT_DIR /
        "animate_image_menu.png"
    )

    page.screenshot(
        path=str(menu_path),
        full_page=False
    )

    log(
        f"[ANIMATE] Menu screenshot:"
    )

    log(
        f"    {menu_path}"
    )

    # --------------------------------------------------------
    # Find Animate
    # --------------------------------------------------------

    animate_item = (
        find_animate_menu_item(
            page
        )
    )

    if animate_item is None:

        log(
            "[ANIMATE] Animate menu item NOT FOUND."
        )

        log(
            "[ANIMATE DEBUG] Visible menuitems:"
        )

        menuitems = page.get_by_role(
            "menuitem"
        )

        for i in range(
            menuitems.count()
        ):

            try:

                item = menuitems.nth(i)

                if not item.is_visible():
                    continue

                log(
                    f"    [{i}] "
                    f"{item.inner_text()!r}"
                )

            except Exception:
                pass

        error_path = (
            SCREENSHOT_DIR /
            "ANIMATE_MENU_NOT_FOUND.png"
        )

        page.screenshot(
            path=str(error_path),
            full_page=False
        )

        raise RuntimeError(
            "Animate menu item not found."
        )

    log(
        "[OK] Animate menu item found."
    )

    log(
        f"[ANIMATE] Text:"
        f" {animate_item.inner_text()!r}"
    )

    # --------------------------------------------------------
    # Click Animate
    # --------------------------------------------------------

    animate_item.click(
        force=True
    )

    log(
        "[OK] Animate clicked."
    )

    time.sleep(
        2
    )

    after_path = (
        SCREENSHOT_DIR /
        "after_animate_click.png"
    )

    page.screenshot(
        path=str(after_path),
        full_page=False
    )

    log(
        f"[ANIMATE] After Animate screenshot:"
    )

    log(
        f"    {after_path}"
    )


def find_animate_prompt(page):

    log(
        "[ANIMATE] Looking for motion prompt..."
    )

    deadline = (
        time.time() +
        VIDEO_UI_TIMEOUT
    )

    while time.time() < deadline:

        prompt = find_prompt(
            page
        )

        if prompt is not None:

            log(
                "[OK] Animate motion prompt found."
            )

            return prompt

        time.sleep(
            0.5
        )

    debug_path = (
        SCREENSHOT_DIR /
        "ANIMATE_PROMPT_NOT_FOUND.png"
    )

    page.screenshot(
        path=str(debug_path),
        full_page=False
    )

    print_video_ui(
        page
    )

    raise RuntimeError(
        "Animate motion prompt not found."
    )


def fill_animate_prompt(page):

    log(
        "[ANIMATE] Filling motion prompt..."
    )

    prompt = find_animate_prompt(
        page
    )

    prompt.fill(
        VIDEO_PROMPT
    )

    time.sleep(
        1
    )

    log(
        "[OK] Animate motion prompt filled."
    )


def start_animate_generation(page):

    log(
        "[ANIMATE] Looking for Start generation..."
    )

    button = page.get_by_role(
        "button",
        name="Start generation"
    )

    button.wait_for(
        state="visible",
        timeout=30000
    )

    log(
        "[OK] Animate Start generation found."
    )

    button.click(
        force=True
    )

    log(
        "[OK] Animate video generation started."
    )


def wait_animate_generation(page):

    log(
        "[ANIMATE] Waiting for video generation..."
    )

    start_time = time.time()

    last_report = -1

    while True:

        elapsed = int(
            time.time() -
            start_time
        )

        if elapsed >= VIDEO_GENERATION_TIMEOUT:

            raise TimeoutError(
                "Animate video generation timeout reached."
            )

        if stop_button_visible(page):

            ten_second_block = (
                elapsed // 10
            )

            if (
                ten_second_block !=
                last_report
            ):

                last_report = (
                    ten_second_block
                )

                log(
                    f"[WAIT] Animate video generation "
                    f"running... {elapsed}s"
                )

            time.sleep(
                1
            )

            continue

        log(
            "[SIGNAL] Animate Stop button disappeared."
        )

        break

    # --------------------------------------------------------
    # MANDATORY 3-MINUTE WAIT
    #
    # Even if Flow finishes before 180 seconds,
    # we MUST wait until 180 seconds have passed
    # from the moment video generation started.
    # --------------------------------------------------------

    elapsed = int(
        time.time() -
        start_time
    )

    remaining = (
        VIDEO_MINIMUM_WAIT -
        elapsed
    )

    if remaining > 0:

        log(
            f"[ANIMATE] Generation signal finished "
            f"after {elapsed}s."
        )

        log(
            f"[ANIMATE] MANDATORY minimum wait: "
            f"{remaining}s remaining."
        )

        while remaining > 0:

            sleep_for = min(
                5,
                remaining
            )

            time.sleep(
                sleep_for
            )

            elapsed = int(
                time.time() -
                start_time
            )

            remaining = (
                VIDEO_MINIMUM_WAIT -
                elapsed
            )

            log(
                f"[ANIMATE] Mandatory wait progress: "
                f"{elapsed}/{VIDEO_MINIMUM_WAIT}s"
            )

    log(
        "[ANIMATE] Mandatory 3-minute wait completed."
    )

    # --------------------------------------------------------
    # Additional Flow result settling time
    # --------------------------------------------------------

    log(
        f"[ANIMATE] Waiting additional "
        f"{VIDEO_POST_GENERATION_WAIT}s "
        f"for result tile..."
    )

    time.sleep(
        VIDEO_POST_GENERATION_WAIT
    )

def get_video_elements_for_animate(page):

    found = []

    # --------------------------------------------------------
    # FIRST:
    # Try normal <video> elements.
    # --------------------------------------------------------

    videos = page.locator(
        "video"
    )

    for i in range(
        videos.count()
    ):

        try:

            video = videos.nth(i)

            if not video.is_visible():
                continue

            box = video.bounding_box()

            if not box:
                continue

            if box["width"] < 150:
                continue

            if box["height"] < 80:
                continue

            src = (
                video.get_attribute(
                    "src"
                )
            )

            poster = (
                video.get_attribute(
                    "poster"
                )
            )

            found.append({
                "locator": video,
                "index": i,
                "box": box,
                "src": src,
                "poster": poster,
                "width": box["width"],
                "height": box["height"],
                "video_editor_button": False,
            })

        except Exception:
            pass

    if found:
        return found

    # --------------------------------------------------------
    # SECOND:
    # Flow may expose the generated video as:
    #
    # aria="Open video in editor"
    #
    # This is what your actual Flow UI showed.
    # --------------------------------------------------------

    try:

        buttons = page.locator(
            'button[aria-label*="Open video in editor" i]'
        )

        for i in range(
            buttons.count()
        ):

            try:

                button = buttons.nth(i)

                if not button.is_visible():
                    continue

                button_box = (
                    button.bounding_box()
                )

                if not button_box:
                    continue

                # ------------------------------------------------
                # Walk up through parent containers.
                #
                # We do NOT want the small button itself.
                # We want the actual video tile around it so
                # right-click opens Flow's media menu.
                # ------------------------------------------------

                best_box = None
                best_locator = button

                parent = button

                for level in range(7):

                    try:

                        parent = parent.locator(
                            "xpath=.."
                        )

                        if not parent.is_visible():
                            continue

                        parent_box = (
                            parent.bounding_box()
                        )

                        if not parent_box:
                            continue

                        width = (
                            parent_box["width"]
                        )

                        height = (
                            parent_box["height"]
                        )

                        # ----------------------------------------
                        # Typical Flow media tile is much larger
                        # than the Open-in-editor button.
                        # ----------------------------------------

                        if (
                            width >= 250
                            and
                            height >= 150
                            and
                            width <= 1200
                            and
                            height <= 900
                        ):

                            if best_box is None:

                                best_box = (
                                    parent_box
                                )

                                best_locator = (
                                    parent
                                )

                            else:

                                old_area = (
                                    best_box["width"] *
                                    best_box["height"]
                                )

                                new_area = (
                                    width *
                                    height
                                )

                                # Prefer the larger media
                                # container, but not the page.
                                if new_area > old_area:

                                    best_box = (
                                        parent_box
                                    )

                                    best_locator = (
                                        parent
                                    )

                    except Exception:
                        continue

                if best_box is None:

                    best_box = (
                        button_box
                    )

                log(
                    "[OK] Flow video editor tile detected."
                )

                log(
                    f"    Button box: "
                    f"{button_box}"
                )

                log(
                    f"    Video tile box: "
                    f"{best_box}"
                )

                found.append({
                    "locator": best_locator,
                    "button": button,
                    "index": i,
                    "box": best_box,
                    "src": None,
                    "poster": None,
                    "width": best_box["width"],
                    "height": best_box["height"],
                    "video_editor_button": True,
                })

            except Exception:
                pass

    except Exception:
        pass

    return found


def wait_for_animate_video(page):

    log(
        "[ANIMATE] Looking for generated video..."
    )

    deadline = (
        time.time() +
        VIDEO_RESULT_EXTRA_TIMEOUT
    )

    last_report = -1

    while time.time() < deadline:

        # --------------------------------------------------------
        # Direct <video> OR Flow video-editor tile
        # --------------------------------------------------------

        videos = (
            get_video_elements_for_animate(
                page
            )
        )

        if videos:

            log(
                f"[OK] Generated video result detected: "
                f"{len(videos)}"
            )

            for i, video in enumerate(
                videos,
                start=1
            ):

                box = video.get(
                    "box"
                )

                log(
                    f"[VIDEO {i}] "
                    f"x={round(box['x'])} "
                    f"y={round(box['y'])} "
                    f"w={round(box['width'])} "
                    f"h={round(box['height'])}"
                )

                if video.get(
                    "video_editor_button",
                    False
                ):

                    log(
                        "[VIDEO] Detected through "
                        "'Open video in editor' tile."
                    )

            print_videos(
                videos
            )

            return videos

        elapsed = int(
            (
                VIDEO_RESULT_EXTRA_TIMEOUT
                -
                max(
                    0,
                    deadline - time.time()
                )
            )
        )

        ten_second_block = (
            elapsed // 10
        )

        if (
            ten_second_block !=
            last_report
        ):

            last_report = (
                ten_second_block
            )

            log(
                f"[WAIT] Waiting for Flow video tile... "
                f"{elapsed}s"
            )

        time.sleep(
            5
        )

    # --------------------------------------------------------
    # Debug screenshot
    # --------------------------------------------------------

    error_path = (
        SCREENSHOT_DIR /
        "ANIMATE_VIDEO_NOT_FOUND.png"
    )

    page.screenshot(
        path=str(error_path),
        full_page=False
    )

    log(
        "[ANIMATE] Generated video tile "
        "was not detected."
    )

    log(
        f"[ANIMATE] Screenshot: {error_path}"
    )

    # --------------------------------------------------------
    # Dump buttons because Flow may expose the generated
    # asset through a tile/player wrapper.
    # --------------------------------------------------------

    print_video_ui(
        page
    )

    # --------------------------------------------------------
    # Also inspect video-related DOM
    # --------------------------------------------------------

    try:

        html = page.locator(
            "body"
        ).inner_text()

        text_path = (
            SCREENSHOT_DIR /
            "ANIMATE_VIDEO_NOT_FOUND.txt"
        )

        text_path.write_text(
            html,
            encoding="utf-8"
        )

        log(
            "[ANIMATE] Page text saved:"
        )

        log(
            f"    {text_path}"
        )

    except Exception:
        pass

    raise RuntimeError(
        "Animate generation completed, "
        "but generated video tile was not detected."
    )


def find_animate_video_download_item(page):

    menuitems = page.get_by_role(
        "menuitem"
    )

    candidates = []

    for i in range(
        menuitems.count()
    ):

        try:

            item = menuitems.nth(i)

            if not item.is_visible():
                continue

            text = " ".join(
                item.inner_text().split()
            )

            normalized = text.lower()

            log(
                f"[ANIMATE DEBUG] menuitem={text!r}"
            )

            if (
                normalized == "download"
                or
                normalized.endswith(" download")
            ):

                candidates.append(
                    item
                )

        except Exception:
            pass

    if candidates:

        log(
            "[OK] Animate video Download menu found."
        )

        return candidates[0]

    return None



def find_animate_video_quality_option(page):

    menuitems = page.get_by_role(
        "menuitem"
    )

    candidates = []

    for i in range(
        menuitems.count()
    ):

        try:

            item = menuitems.nth(i)

            if not item.is_visible():
                continue

            text = " ".join(
                item.inner_text().split()
            )

            lower = text.lower()

            if lower == "download":
                continue

            # ------------------------------------------------
            # Prefer explicit video/resolution options.
            # ------------------------------------------------

            score = 0

            if "1080" in lower:
                score += 100

            if "720" in lower:
                score += 90

            if "360" in lower:
                score += 80

            if "mp4" in lower:
                score += 70

            if "original" in lower:
                score += 60

            if "video" in lower:
                score += 50

            if score > 0:

                candidates.append(
                    (
                        score,
                        item,
                        text
                    )
                )

        except Exception:
            pass

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    log(
        "[ANIMATE DOWNLOAD] "
        "Video quality options:"
    )

    for score, item, text in candidates:

        log(
            f"    score={score} "
            f"text={text!r}"
        )

    return candidates[0][1]


def download_animate_video(
    page,
    video,
    number=1
):

    log("")
    log(
        "================================================"
    )
    log(
        f"DOWNLOADING ANIMATED VIDEO {number}"
    )
    log(
        "================================================"
    )

    box = video["box"]

    center_x = (
        box["x"] +
        box["width"] / 2
    )

    center_y = (
        box["y"] +
        box["height"] / 2
    )

    log(
        f"[ANIMATE DOWNLOAD] "
        f"Moving to video center..."
    )

    log(
        f"    X={round(center_x)}"
    )

    log(
        f"    Y={round(center_y)}"
    )

    page.mouse.move(
        center_x,
        center_y,
        steps=20
    )

    time.sleep(
        HOVER_WAIT
    )

    log(
        "[ANIMATE DOWNLOAD] "
        "Right-clicking video..."
    )

    page.mouse.click(
        center_x,
        center_y,
        button="right"
    )

    time.sleep(
        MENU_WAIT
    )

    menu_path = (
        SCREENSHOT_DIR /
        f"animate_video_{number}_menu.png"
    )

    page.screenshot(
        path=str(menu_path),
        full_page=False
    )

    log(
        f"[ANIMATE DOWNLOAD] "
        f"Menu screenshot: {menu_path}"
    )

    # --------------------------------------------------------
    # Find Download
    # --------------------------------------------------------

    download_item = None

    deadline = (
        time.time() +
        SUBMENU_TIMEOUT
    )

    while time.time() < deadline:

        download_item = (
            find_animate_video_download_item(
                page
            )
        )

        if download_item is not None:
            break

        time.sleep(
            0.25
        )

    if download_item is None:

        raise RuntimeError(
            "Animate video Download menuitem not found."
        )

    log(
        "[OK] Video Download menu found."
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Hover Download, don't click it.
    # --------------------------------------------------------

    download_item.hover(
        force=True
    )

    log(
        "[ANIMATE DOWNLOAD] "
        "Hovered Download."
    )

    time.sleep(
        1.5
    )

    submenu_path = (
        SCREENSHOT_DIR /
        f"animate_video_{number}_submenu.png"
    )

    page.screenshot(
        path=str(submenu_path),
        full_page=False
    )

    log(
        f"[ANIMATE DOWNLOAD] "
        f"Submenu screenshot: {submenu_path}"
    )

    # --------------------------------------------------------
    # Find quality
    # --------------------------------------------------------

    option = (
        find_animate_video_quality_option(
            page
        )
    )

    if option is None:

        log(
            "[ANIMATE DOWNLOAD] "
            "Video quality option not found."
        )

        log(
            "[ANIMATE DOWNLOAD] "
            "Visible menuitems:"
        )

        menuitems = page.get_by_role(
            "menuitem"
        )

        for i in range(
            menuitems.count()
        ):

            try:

                item = menuitems.nth(i)

                if not item.is_visible():
                    continue

                log(
                    f"    [{i}] "
                    f"{item.inner_text()!r}"
                )

            except Exception:
                pass

        raise RuntimeError(
            "Animated video download option not found."
        )

    log(
        "[ANIMATE DOWNLOAD] "
        f"Selected: {option.inner_text().strip()!r}"
    )

    # --------------------------------------------------------
    # Actual browser download
    # --------------------------------------------------------

    with page.expect_download(
        timeout=30000
    ) as download_info:

        option.click(
            force=True
        )

    download = download_info.value

    suggested_name = (
        download.suggested_filename
    )

    extension = ".mp4"

    if suggested_name:

        lower = suggested_name.lower()

        for ext in [
            ".mp4",
            ".mov",
            ".webm",
            ".avi"
        ]:

            if lower.endswith(ext):

                extension = ext
                break

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        DOWNLOAD_DIR /
        f"flow_animated_video_"
        f"{number}_"
        f"{timestamp}"
        f"{extension}"
    )

    download.save_as(
        str(output_path)
    )

    log("")
    log(
        "[OK] ANIMATED VIDEO DOWNLOADED"
    )

    log(
        f"    Suggested name: "
        f"{suggested_name}"
    )

    log(
        f"    Saved to: "
        f"{output_path}"
    )

    if not output_path.exists():

        raise RuntimeError(
            "Animated video download event occurred "
            "but file was not found."
        )

    size = output_path.stat().st_size

    log(
        f"    File size: "
        f"{size:,} bytes"
    )

    if size == 0:

        raise RuntimeError(
            "Animated video file is 0 bytes."
        )

    log(
        "================================================"
    )

    return output_path


def run_animate_video_pipeline(page):

    log("")
    log(
        "################################################"
    )
    log(
        "# IMAGE -> ANIMATE -> VIDEO PIPELINE"
    )
    log(
        "################################################"
    )
    log("")

    # --------------------------------------------------------
    # IMPORTANT:
    # Find the image already generated by Flow.
    #
    # Do NOT use downloaded_images.
    # Do NOT upload JPEG again.
    # --------------------------------------------------------

    image = (
        get_current_generated_image_for_animate(
            page
        )
    )

    # --------------------------------------------------------
    # Open image's right-click menu
    # --------------------------------------------------------

    open_animate_from_image(
        page,
        image
    )

    # --------------------------------------------------------
    # Animate opens motion-generation UI
    # --------------------------------------------------------

    fill_animate_prompt(
        page
    )

    # --------------------------------------------------------
    # Start animation
    # --------------------------------------------------------

    start_animate_generation(
        page
    )

    # --------------------------------------------------------
    # Wait
    # --------------------------------------------------------

    wait_animate_generation(
        page
    )

    # --------------------------------------------------------
    # Detect video
    # --------------------------------------------------------

    videos = (
        wait_for_animate_video(
            page
        )
    )

    log(
        f"[ANIMATE] Videos detected: "
        f"{len(videos)}"
    )

    # --------------------------------------------------------
    # Download every detected video
    # --------------------------------------------------------

    downloaded_videos = []

    for number, video in enumerate(
        videos,
        start=1
    ):

        try:

            output = (
                download_animate_video(
                    page,
                    video,
                    number
                )
            )

            downloaded_videos.append(
                output
            )

        except Exception as e:

            log("")
            log(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

            log(
                f"[ERROR] Animated video {number} "
                f"download failed:"
            )

            log(
                str(e)
            )

            log(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

            try:

                page.keyboard.press(
                    "Escape"
                )

            except Exception:
                pass

    # --------------------------------------------------------
    # Final Animate report
    # --------------------------------------------------------

    log("")
    log(
        "================================================"
    )
    log(
        "FINAL ANIMATE VIDEO REPORT"
    )
    log(
        "================================================"
    )

    log(
        f"Detected videos: "
        f"{len(videos)}"
    )

    log(
        f"Downloaded videos: "
        f"{len(downloaded_videos)}"
    )

    for i, path in enumerate(
        downloaded_videos,
        start=1
    ):

        log(
            f"[ANIMATED VIDEO {i}] "
            f"{path}"
        )

    log(
        "================================================"
    )

    return downloaded_videos

def run_video_pipeline( 
    page, 
    downloaded_images 
): 

    # ========================================================
    # NEW ROUTE:
    # Use Flow's native Animate action on the generated image.
    #
    # Everything below this return is your OLD VIDEO CODE
    # and remains untouched.
    # ========================================================

    return run_animate_video_pipeline(page)

    log("")
    log(
        "################################################"
    )

# ============================================================
# RUN VIDEO PIPELINE
# ============================================================



def run_video_pipeline(
    page,
    downloaded_images
):

    return run_animate_video_pipeline(page)

    log("")
    log(
        "################################################"
    )
    log(
        "# STARTING IMAGE -> VIDEO PIPELINE"
    )
    log(
        "################################################"
    )
    log("")

    if not downloaded_images:

        raise RuntimeError(
            "No downloaded images available "
            "for video generation."
        )

    # --------------------------------------------------------
    # For first test use first successfully downloaded image.
    # Old image generation/download remains untouched.
    # --------------------------------------------------------

    ingredient_image = (
        downloaded_images[0]
    )

    log(
        f"[VIDEO] Using downloaded image:"
    )

    log(
        f"        {ingredient_image}"
    )

    # --------------------------------------------------------
    # Open model selector
    # --------------------------------------------------------

    open_video_settings(
        page
    )

    # --------------------------------------------------------
    # Select Video
    # --------------------------------------------------------

    click_video_option(
        page
    )

    # --------------------------------------------------------
    # Select Ingredients
    # --------------------------------------------------------

    click_ingredients_option(
        page
    )

    # --------------------------------------------------------
    # Add downloaded image
    # --------------------------------------------------------

    upload_video_ingredient(
        page,
        ingredient_image
    )

    # --------------------------------------------------------
    # Fill motion prompt
    # --------------------------------------------------------

    fill_video_prompt(
        page
    )

    # --------------------------------------------------------
    # Generate video
    # --------------------------------------------------------

    start_video_generation(
        page
    )

    # --------------------------------------------------------
    # Wait
    # --------------------------------------------------------

    wait_video_generation(
        page
    )

    # --------------------------------------------------------
    # Detect result
    # --------------------------------------------------------

    videos = wait_for_generated_videos(
        page
    )

    log(
        f"[VIDEO] Detected videos: "
        f"{len(videos)}"
    )

    # --------------------------------------------------------
    # Download videos
    # --------------------------------------------------------

    downloaded_videos = []

    for number, video in enumerate(
        videos,
        start=1
    ):

        try:

            output = download_one_video(
                page,
                video,
                number
            )

            downloaded_videos.append(
                output
            )

        except Exception as e:

            log("")
            log(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

            log(
                f"[ERROR] Video {number} "
                f"download failed:"
            )

            log(
                str(e)
            )

            log(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

            try:

                page.keyboard.press(
                    "Escape"
                )

            except Exception:
                pass

    # --------------------------------------------------------
    # Video final report
    # --------------------------------------------------------

    log("")
    log(
        "================================================"
    )
    log(
        "FINAL VIDEO REPORT"
    )
    log(
        "================================================"
    )

    log(
        f"Detected videos: "
        f"{len(videos)}"
    )

    log(
        f"Successfully downloaded videos: "
        f"{len(downloaded_videos)}"
    )

    for i, path in enumerate(
        downloaded_videos,
        start=1
    ):

        log(
            f"[VIDEO FILE {i}] "
            f"{path}"
        )

    log(
        "================================================"
    )

    return downloaded_videos


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

        # ====================================================
        # NEW:
        # IMAGE -> VIDEO
        # ====================================================

        if downloaded:

            try:

                downloaded_videos = (
                    run_video_pipeline(
                        page,
                        downloaded
                    )
                )

            except Exception as e:

                log("")
                log(
                    "################################################"
                )

                log(
                    "[VIDEO PIPELINE ERROR]"
                )

                log(
                    str(e)
                )

                log(
                    "################################################"
                )

                # Video failure does NOT destroy
                # the successful image workflow.

                try:

                    video_error_path = (
                        SCREENSHOT_DIR /
                        "VIDEO_PIPELINE_ERROR.png"
                    )

                    page.screenshot(
                        path=str(
                            video_error_path
                        ),
                        full_page=False
                    )

                    log(
                        f"[VIDEO] Error screenshot: "
                        f"{video_error_path}"
                    )

                except Exception:
                    pass

                downloaded_videos = []

        else:

            log(
                "[VIDEO] Skipped because "
                "no image was downloaded."
            )

            downloaded_videos = []

        # ----------------------------------------------------
        # Final combined report
        # ----------------------------------------------------

        log("")
        log(
            "================================================"
        )
        log(
            "FINAL COMPLETE REPORT"
        )
        log(
            "================================================"
        )

        log(
            f"Images detected: "
            f"{len(images)}"
        )

        log(
            f"Images downloaded: "
            f"{len(downloaded)}"
        )

        log(
            f"Videos downloaded: "
            f"{len(downloaded_videos)}"
        )

        for i, path in enumerate(
            downloaded_videos,
            start=1
        ):

            log(
                f"[VIDEO FILE {i}] "
                f"{path}"
            )

        log(
            "================================================"
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
