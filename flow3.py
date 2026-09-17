import sys
import time
import requests
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

IX_API = "http://127.0.0.1:53200/api/v2"

PROFILE_ID = 3878

FLOW_HOME = "https://flow.google.com/"

TEST_PROMPT = (
    "A cinematic historical scene of an ancient Roman city "
    "at sunset, wide establishing shot, realistic architecture, "
    "dramatic lighting, documentary style, highly detailed."
)


# ============================================================
# IXBROWSER
# ============================================================

def open_ixbrowser_profile(profile_id):

    print(f"[1] Opening IXBrowser profile {profile_id}...")

    payload = {
        "profile_id": profile_id,
        "args": [
            "--disable-extension-welcome-page"
        ],
        "load_extensions": True,
        "load_profile_info_page": False,
        "cookies_backup": True,
        "cookie": ""
    }

    response = requests.post(
        f"{IX_API}/profile-open",
        json=payload,
        timeout=60
    )

    print(f"    HTTP: {response.status_code}")

    data = response.json()

    if data.get("error", {}).get("code") != 0:
        raise RuntimeError(
            f"IXBrowser error: {data.get('error')}"
        )

    browser_data = data["data"]

    print("[OK] IXBrowser profile opened")
    print(
        f"     CDP: "
        f"{browser_data.get('debugging_address')}"
    )

    return browser_data


# ============================================================
# PAGE INSPECTION
# ============================================================

def inspect_page(page):

    print("\n========== PAGE INSPECTION ==========")

    print("URL   :", page.url)
    print("TITLE :", page.title())

    print("\nTEXTAREAS:")

    textareas = page.locator("textarea")

    for i in range(textareas.count()):

        try:

            el = textareas.nth(i)

            print(
                f"  textarea[{i}] "
                f"visible={el.is_visible()} "
                f"placeholder="
                f"{el.get_attribute('placeholder')!r}"
            )

        except Exception:
            pass

    print("\nCONTENTEDITABLE:")

    editables = page.locator(
        '[contenteditable="true"]'
    )

    for i in range(editables.count()):

        try:

            el = editables.nth(i)

            if el.is_visible():

                print(
                    f"  editable[{i}] "
                    f"aria-label="
                    f"{el.get_attribute('aria-label')!r}"
                )

        except Exception:
            pass

    print("\nBUTTONS:")

    buttons = page.locator("button")

    for i in range(buttons.count()):

        try:

            button = buttons.nth(i)

            if not button.is_visible():
                continue

            text = (
                button.inner_text(
                    timeout=500
                ).strip()
            )

            aria = button.get_attribute(
                "aria-label"
            )

            if text or aria:

                print(
                    f"  button[{i}] "
                    f"text={text!r} "
                    f"aria={aria!r}"
                )

        except Exception:
            pass

    print("====================================\n")


# ============================================================
# FIND PROMPT
# ============================================================

def find_prompt(page):

    print("[5] Finding prompt input...")

    # --------------------------------------------------------
    # textarea
    # --------------------------------------------------------

    textareas = page.locator("textarea")

    for i in range(textareas.count()):

        try:

            el = textareas.nth(i)

            if el.is_visible():

                print(
                    f"[OK] Prompt textarea found: "
                    f"textarea[{i}]"
                )

                return el

        except Exception:
            pass

    # --------------------------------------------------------
    # contenteditable
    # --------------------------------------------------------

    editables = page.locator(
        '[contenteditable="true"]'
    )

    for i in range(editables.count()):

        try:

            el = editables.nth(i)

            if el.is_visible():

                print(
                    f"[OK] Contenteditable found: "
                    f"editable[{i}]"
                )

                return el

        except Exception:
            pass

    return None


# ============================================================
# FIND START GENERATION
# ============================================================

def find_start_generation(page):

    print(
        "[7] Finding Start generation button..."
    )

    # Exact accessible name
    try:

        button = page.get_by_role(
            "button",
            name="Start generation",
            exact=True
        )

        if button.count() > 0:

            for i in range(button.count()):

                el = button.nth(i)

                if el.is_visible():

                    print(
                        "[OK] Start generation "
                        "button found."
                    )

                    return el

    except Exception:
        pass

    # Fallback: aria-label
    buttons = page.locator("button")

    for i in range(buttons.count()):

        try:

            button = buttons.nth(i)

            if not button.is_visible():
                continue

            aria = (
                button.get_attribute(
                    "aria-label"
                ) or ""
            ).lower()

            if aria == "start generation":

                print(
                    "[OK] Start generation "
                    "button found by aria-label."
                )

                return button

        except Exception:
            pass

    return None


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        # ====================================================
        # 1. IXBrowser
        # ====================================================

        browser_data = open_ixbrowser_profile(
            PROFILE_ID
        )

        debugging_address = browser_data[
            "debugging_address"
        ]

        # ====================================================
        # 2. Playwright CDP
        # ====================================================

        print(
            "[2] Connecting to IXBrowser Chromium..."
        )

        with sync_playwright() as p:

            browser = p.chromium.connect_over_cdp(
                f"http://{debugging_address}"
            )

            print(
                "[OK] Connected to Chromium"
            )

            if not browser.contexts:

                raise RuntimeError(
                    "No browser context found."
                )

            context = browser.contexts[0]

            # =================================================
            # 3. Page
            # =================================================

            pages = context.pages

            print(
                f"[OK] Existing pages: {len(pages)}"
            )

            if pages:

                page = pages[0]

            else:

                page = context.new_page()

            # =================================================
            # 4. Flow Home
            # =================================================

            print(
                "[3] Opening Flow home..."
            )

            page.goto(
                FLOW_HOME,
                wait_until="domcontentloaded",
                timeout=120000
            )

            print(
                "[OK] Flow home opened"
            )

            page.wait_for_timeout(10000)

            # =================================================
            # 5. New Project
            # =================================================

            print(
                "[4] Looking for New project..."
            )

            new_project = page.get_by_text(
                "New project",
                exact=True
            )

            if (
                new_project.count() == 0
                or not new_project.first.is_visible()
            ):

                print(
                    "[ERROR] New project not found."
                )

                inspect_page(page)

                page.screenshot(
                    path="debug-new-project.png",
                    full_page=True
                )

                raise RuntimeError(
                    "New project button not found."
                )

            print(
                "[OK] New project found"
            )

            new_project.first.click()

            print(
                "[OK] New project clicked"
            )

            # =================================================
            # 6. Wait for project
            # =================================================

            print(
                "[INFO] Waiting for project..."
            )

            page.wait_for_timeout(5000)

            print(
                "[OK] Project URL:",
                page.url
            )

            # =================================================
            # Inspect before prompt
            # =================================================

            inspect_page(page)

            # =================================================
            # 7. Find prompt
            # =================================================

            prompt = find_prompt(page)

            if not prompt:

                print(
                    "[ERROR] Prompt input not found."
                )

                page.screenshot(
                    path="debug-prompt.png",
                    full_page=True
                )

                print(
                    "[DEBUG] Saved debug-prompt.png"
                )

                while True:
                    time.sleep(5)

            # =================================================
            # 8. Fill prompt
            # =================================================

            print(
                "[6] Filling prompt..."
            )

            prompt.click()

            prompt.fill(
                TEST_PROMPT
            )

            print(
                "[OK] Prompt filled:"
            )

            print(
                TEST_PROMPT
            )

            page.wait_for_timeout(1500)

            # =================================================
            # 9. Find generation button
            # =================================================

            start_button = find_start_generation(
                page
            )

            if not start_button:

                print(
                    "[ERROR] Start generation "
                    "button not found."
                )

                inspect_page(page)

                page.screenshot(
                    path="debug-start-generation.png",
                    full_page=True
                )

                print(
                    "[DEBUG] Saved "
                    "debug-start-generation.png"
                )

                while True:
                    time.sleep(5)

            # =================================================
            # 10. Click
            # =================================================

            print(
                "[8] Clicking Start generation..."
            )

            start_button.click()

            print(
                "[OK] Start generation clicked"
            )

            # =================================================
            # 11. Wait
            # =================================================

            print()
            print(
                "======================================"
            )
            print(
                " GENERATION STARTED"
            )
            print(
                "======================================"
            )

            print(
                "Waiting 30 seconds for generation..."
            )

            for i in range(30):

                time.sleep(1)

                if i % 5 == 0:

                    print(
                        f"[WAIT] {i}s"
                    )

            # =================================================
            # 12. Screenshot after generation
            # =================================================

            page.screenshot(
                path="after-generation-start.png",
                full_page=True
            )

            print(
                "[OK] Saved:"
                " after-generation-start.png"
            )

            print()
            print(
                "Generation test completed."
            )

            print(
                "Browser remains open."
            )

            # =================================================
            # Keep alive
            # =================================================

            while True:

                time.sleep(5)

                try:

                    print(
                        f"[LIVE] {page.title()} | "
                        f"{page.url}"
                    )

                except Exception:

                    print(
                        "[ERROR] Browser connection lost."
                    )

                    break

    except KeyboardInterrupt:

        print(
            "\n[EXIT] Stopped by user."
        )

    except Exception as e:

        print()
        print(
            "[ERROR]",
            type(e).__name__
        )

        print(
            str(e)
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
