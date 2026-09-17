import time
import os
import requests
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

PROFILE_ID = 3878

PROMPT = """
A cinematic historical scene of an ancient Roman city at sunset,
wide establishing shot, realistic architecture, dramatic lighting,
documentary style, highly detailed.
""".strip()

IX_API = "http://127.0.0.1:53200/api/v2/profile-open"


# ============================================================
# IXBROWSER
# ============================================================

def open_ixbrowser_profile():

    print(f"[1] Opening IXBrowser profile {PROFILE_ID}...")

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

    print(f"    HTTP: {response.status_code}")

    response.raise_for_status()

    data = response.json()

    profile_data = data.get("data", {})

    debugging_address = profile_data.get(
        "debugging_address"
    )

    if not debugging_address:

        raise RuntimeError(
            "IXBrowser debugging_address missing:\n"
            + str(data)
        )

    print("[OK] IXBrowser profile opened")
    print(
        f"     CDP: {debugging_address}"
    )

    return debugging_address


# ============================================================
# NEW PROJECT
# ============================================================

def find_new_project(page):

    # Exact text
    try:

        locator = page.get_by_text(
            "New project",
            exact=True
        )

        for i in range(locator.count()):

            element = locator.nth(i)

            if element.is_visible():

                return element

    except Exception:
        pass


    # Button role
    try:

        locator = page.get_by_role(
            "button",
            name="New project",
            exact=True
        )

        for i in range(locator.count()):

            element = locator.nth(i)

            if element.is_visible():

                return element

    except Exception:
        pass


    # Generic button
    try:

        buttons = page.locator("button")

        for i in range(buttons.count()):

            element = buttons.nth(i)

            if not element.is_visible():
                continue

            text = (
                element.inner_text()
                .strip()
                .lower()
            )

            if "new project" in text:

                return element

    except Exception:
        pass


    return None


# ============================================================
# PROJECT UI DETECTION
# ============================================================

def is_project_screen(page):

    """
    Do NOT depend only on URL.

    Flow project screen contains UI elements
    such as:
        - Start generation
        - Add ingredients
        - Agent
        - contenteditable prompt
    """

    # --------------------------------------------------------
    # Start generation
    # --------------------------------------------------------

    try:

        locator = page.get_by_role(
            "button",
            name="Start generation",
            exact=True
        )

        if locator.count() > 0:

            for i in range(locator.count()):

                if locator.nth(i).is_visible():

                    return True

    except Exception:
        pass


    # --------------------------------------------------------
    # Contenteditable
    # --------------------------------------------------------

    try:

        locator = page.locator(
            '[contenteditable="true"]'
        )

        for i in range(locator.count()):

            if locator.nth(i).is_visible():

                return True

    except Exception:
        pass


    # --------------------------------------------------------
    # Add ingredients
    # --------------------------------------------------------

    try:

        locator = page.get_by_role(
            "button",
            name="Add ingredients to the prompt box",
            exact=True
        )

        if locator.count() > 0:

            for i in range(locator.count()):

                if locator.nth(i).is_visible():

                    return True

    except Exception:
        pass


    return False


# ============================================================
# FIND PROMPT
# ============================================================

def find_prompt(page):

    # Contenteditable
    try:

        locator = page.locator(
            '[contenteditable="true"]'
        )

        for i in range(locator.count()):

            element = locator.nth(i)

            if element.is_visible():

                print(
                    f"[OK] Prompt contenteditable "
                    f"found: editable[{i}]"
                )

                return element

    except Exception:
        pass


    # Textarea fallback
    try:

        locator = page.locator(
            "textarea"
        )

        for i in range(locator.count()):

            element = locator.nth(i)

            if element.is_visible():

                print(
                    f"[OK] Prompt textarea "
                    f"found: textarea[{i}]"
                )

                return element

    except Exception:
        pass


    return None


# ============================================================
# START GENERATION
# ============================================================

def find_start_generation(page):

    try:

        locator = page.get_by_role(
            "button",
            name="Start generation",
            exact=True
        )

        for i in range(locator.count()):

            element = locator.nth(i)

            if element.is_visible():

                return element

    except Exception:
        pass


    try:

        locator = page.locator(
            'button[aria-label="Start generation"]'
        )

        for i in range(locator.count()):

            element = locator.nth(i)

            if element.is_visible():

                return element

    except Exception:
        pass


    return None


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # OPEN IXBROWSER
    # ========================================================

    debugging_address = (
        open_ixbrowser_profile()
    )


    with sync_playwright() as p:

        # ====================================================
        # CONNECT
        # ====================================================

        print(
            "[2] Connecting to IXBrowser Chromium..."
        )

        browser = p.chromium.connect_over_cdp(
            f"http://{debugging_address}"
        )

        print(
            "[OK] Connected to Chromium"
        )


        contexts = browser.contexts

        if not contexts:

            raise RuntimeError(
                "No browser context found."
            )


        context = contexts[0]

        pages = context.pages

        print(
            f"[OK] Existing pages: "
            f"{len(pages)}"
        )


        # ====================================================
        # SELECT FLOW PAGE
        # ====================================================

        page = None

        for candidate in pages:

            try:

                if (
                    "flow.google.com"
                    in candidate.url
                ):

                    page = candidate

                    break

            except Exception:
                pass


        if page is None:

            page = (
                pages[0]
                if pages
                else context.new_page()
            )


        # ====================================================
        # OPEN FLOW
        # ====================================================

        print(
            "[3] Opening Flow home..."
        )

        page.goto(
            "https://flow.google.com/",
            wait_until="domcontentloaded",
            timeout=60000
        )

        print(
            "[OK] Flow home opened"
        )

        time.sleep(4)


        # ====================================================
        # NEW PROJECT
        # ====================================================

        print(
            "[4] Looking for New project..."
        )

        new_project = None

        for attempt in range(30):

            new_project = (
                find_new_project(page)
            )

            if new_project:

                break

            print(
                f"[WAIT] New project "
                f"not found "
                f"({attempt + 1}/30)"
            )

            time.sleep(1)


        if not new_project:

            raise RuntimeError(
                "New project button not found."
            )


        print(
            "[OK] New project found"
        )


        # ====================================================
        # CLICK NEW PROJECT
        # ====================================================

        print(
            "[5] Clicking New project..."
        )

        new_project.click()

        print(
            "[OK] New project clicked"
        )


        # ====================================================
        # WAIT FOR PROJECT UI
        # ====================================================

        print()
        print(
            "[6] Waiting for Flow project UI..."
        )


        project_ready = False


        for attempt in range(60):

            try:

                # Check current page UI

                if is_project_screen(page):

                    project_ready = True

                    break


            except Exception:
                pass


            # ------------------------------------------------
            # Also inspect any newly opened page
            # ------------------------------------------------

            for candidate in context.pages:

                try:

                    if candidate == page:
                        continue

                    if (
                        "flow.google.com"
                        not in candidate.url
                    ):
                        continue

                    if is_project_screen(candidate):

                        print(
                            "[OK] Project UI found "
                            "on another page."
                        )

                        page = candidate

                        project_ready = True

                        break

                except Exception:
                    pass


            if project_ready:

                break


            print(
                f"[WAIT] Project UI not ready "
                f"({attempt + 1}/60)"
            )

            time.sleep(1)


        # ====================================================
        # PROJECT READY
        # ====================================================

        if not project_ready:

            print()
            print(
                "[ERROR] Project UI was not detected."
            )

            print(
                "Current URL:",
                page.url
            )

            print(
                "Open pages:"
            )

            for i, candidate in enumerate(
                context.pages
            ):

                try:

                    print(
                        f"[{i}] {candidate.url}"
                    )

                except Exception:
                    pass


            raise RuntimeError(
                "Flow project UI did not appear."
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

        try:

            print(
                "TITLE:",
                page.title()
            )

        except Exception:
            pass

        print(
            "=" * 65
        )


        # ====================================================
        # FIND PROMPT
        # ====================================================

        print()
        print(
            "[7] Looking for prompt input..."
        )


        prompt_input = None


        for attempt in range(30):

            prompt_input = (
                find_prompt(page)
            )

            if prompt_input:

                break


            print(
                f"[WAIT] Prompt input not ready "
                f"({attempt + 1}/30)"
            )

            time.sleep(1)


        if not prompt_input:

            raise RuntimeError(
                "Prompt input not found."
            )


        # ====================================================
        # PASTE PROMPT
        # ====================================================

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


        prompt_input.click()

        time.sleep(0.5)


        # ----------------------------------------------------
        # Try fill
        # ----------------------------------------------------

        filled = False


        try:

            prompt_input.fill(
                PROMPT
            )

            filled = True

            print(
                "[OK] Prompt pasted using fill()"
            )

        except Exception as e:

            print(
                "[INFO] fill() failed."
            )

            print(
                e
            )


        # ----------------------------------------------------
        # Keyboard fallback
        # ----------------------------------------------------

        if not filled:

            try:

                prompt_input.click()

                prompt_input.press(
                    "CTRL+A"
                )

                prompt_input.press_sequentially(
                    PROMPT,
                    delay=0.01
                )

                filled = True

                print(
                    "[OK] Prompt entered "
                    "using keyboard."
                )

            except Exception as e:

                print(
                    "[ERROR] Keyboard input failed."
                )

                print(
                    e
                )


        if not filled:

            raise RuntimeError(
                "Could not paste prompt."
            )


        # ====================================================
        # WAIT FOR START BUTTON
        # ====================================================

        print()
        print(
            "[9] Looking for Start generation..."
        )


        start_button = None


        for attempt in range(30):

            start_button = (
                find_start_generation(
                    page
                )
            )

            if start_button:

                break


            print(
                f"[WAIT] Start generation "
                f"not ready "
                f"({attempt + 1}/30)"
            )

            time.sleep(1)


        if not start_button:

            raise RuntimeError(
                "Start generation button "
                "not found."
            )


        print(
            "[OK] Start generation found"
        )


        # ====================================================
        # CLICK GENERATION
        # ====================================================

        print()
        print(
            "[10] Clicking Start generation..."
        )


        start_button.click()


        print(
            "[OK] Start generation clicked"
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


        # ====================================================
        # SCREENSHOT
        # ====================================================

        try:

            screenshot_path = os.path.abspath(
                "generation-started.png"
            )

            page.screenshot(
                path=screenshot_path,
                full_page=True
            )

            print(
                "[OK] Screenshot saved:"
            )

            print(
                screenshot_path
            )

        except Exception as e:

            print(
                "[WARN] Screenshot failed:"
            )

            print(
                e
            )


        # ====================================================
        # KEEP OPEN
        # ====================================================

        print()
        print(
            "[LIVE] Flow is running."
        )

        print(
            "[LIVE] Browser remains open."
        )

        print(
            "[INFO] Press CTRL+C to stop."
        )


        try:

            while True:

                time.sleep(2)

        except KeyboardInterrupt:

            print(
                "\n[EXIT] Stopped by user."
            )


        try:

            browser.close()

        except Exception:
            pass


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
