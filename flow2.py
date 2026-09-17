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

# New Project ke liye possible text/labels
NEW_PROJECT_TEXTS = [
    "New project",
    "New Project",
]


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

    browser = data["data"]

    print("[OK] IXBrowser profile opened")
    print(f"     PID: {browser.get('pid')}")
    print(f"     CDP: {browser.get('debugging_address')}")

    return browser


# ============================================================
# PAGE DEBUG
# ============================================================

def inspect_page(page):

    print("\n========== CURRENT PAGE ==========")
    print("URL   :", page.url)
    print("TITLE :", page.title())

    print("\nVISIBLE BUTTONS:")

    buttons = page.locator("button")

    for i in range(buttons.count()):

        try:
            button = buttons.nth(i)

            if not button.is_visible():
                continue

            text = button.inner_text(timeout=500).strip()
            aria = button.get_attribute("aria-label")
            title = button.get_attribute("title")

            if text or aria or title:
                print(
                    f"  [{i}] "
                    f"text={text!r} "
                    f"aria={aria!r} "
                    f"title={title!r}"
                )

        except Exception:
            pass

    print("=================================\n")


# ============================================================
# FIND NEW PROJECT
# ============================================================

def find_new_project(page):

    print("[5] Looking for 'New project'...")

    # --------------------------------------------------------
    # Method 1: exact accessible button
    # --------------------------------------------------------

    for text in NEW_PROJECT_TEXTS:

        try:
            locator = page.get_by_role(
                "button",
                name=text,
                exact=True
            )

            if locator.count() > 0:

                for i in range(locator.count()):

                    element = locator.nth(i)

                    if element.is_visible():
                        print(
                            f"[OK] Found button: {text}"
                        )
                        return element

        except Exception:
            pass

    # --------------------------------------------------------
    # Method 2: text locator
    # --------------------------------------------------------

    for text in NEW_PROJECT_TEXTS:

        try:
            locator = page.get_by_text(
                text,
                exact=True
            )

            if locator.count() > 0:

                for i in range(locator.count()):

                    element = locator.nth(i)

                    if element.is_visible():
                        print(
                            f"[OK] Found text: {text}"
                        )
                        return element

        except Exception:
            pass

    # --------------------------------------------------------
    # Method 3: buttons containing "new project"
    # --------------------------------------------------------

    buttons = page.locator("button")

    for i in range(buttons.count()):

        try:

            button = buttons.nth(i)

            if not button.is_visible():
                continue

            text = (
                button.inner_text(timeout=500)
                .strip()
                .lower()
            )

            aria = (
                button.get_attribute("aria-label")
                or ""
            ).lower()

            title = (
                button.get_attribute("title")
                or ""
            ).lower()

            combined = f"{text} {aria} {title}"

            if "new project" in combined:
                print(
                    "[OK] Found New Project button "
                    "through DOM inspection"
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

        # ----------------------------------------------------
        # Open IXBrowser
        # ----------------------------------------------------

        browser_data = open_ixbrowser_profile(
            PROFILE_ID
        )

        debugging_address = browser_data[
            "debugging_address"
        ]

        # ----------------------------------------------------
        # Connect using CDP
        # ----------------------------------------------------

        print("[2] Connecting to IXBrowser Chromium...")

        with sync_playwright() as p:

            browser = p.chromium.connect_over_cdp(
                f"http://{debugging_address}"
            )

            print("[OK] Connected to Chromium")

            if not browser.contexts:
                raise RuntimeError(
                    "No browser context found."
                )

            context = browser.contexts[0]

            # ------------------------------------------------
            # Use existing page or create one
            # ------------------------------------------------

            pages = context.pages

            print(
                f"[OK] Existing pages: {len(pages)}"
            )

            if pages:
                page = pages[0]
            else:
                page = context.new_page()

            # ------------------------------------------------
            # Open Flow HOME
            # ------------------------------------------------

            print("[3] Opening Flow home...")

            page.goto(
                FLOW_HOME,
                wait_until="domcontentloaded",
                timeout=120000
            )

            print("[OK] Flow navigation completed")

            # ------------------------------------------------
            # Wait for React/UI
            # ------------------------------------------------

            print("[4] Waiting for Flow UI...")

            page.wait_for_timeout(10000)

            print(
                "[OK] Current URL:",
                page.url
            )

            print(
                "[OK] Current title:",
                page.title()
            )

            # ------------------------------------------------
            # IMPORTANT:
            # If Flow redirects directly into an existing
            # project, go back to Flow home once.
            # ------------------------------------------------

            if "/project/" in page.url:

                print(
                    "[INFO] Flow redirected directly "
                    "to an existing project."
                )

                print(
                    "[INFO] Going back to Flow home..."
                )

                page.goto(
                    FLOW_HOME,
                    wait_until="domcontentloaded",
                    timeout=120000
                )

                page.wait_for_timeout(10000)

            # ------------------------------------------------
            # Inspect screen
            # ------------------------------------------------

            inspect_page(page)

            # ------------------------------------------------
            # Find New Project
            # ------------------------------------------------

            new_project = find_new_project(page)

            if not new_project:

                print(
                    "[ERROR] 'New project' button not found."
                )

                page.screenshot(
                    path="flow-home-debug.png",
                    full_page=True
                )

                print(
                    "[DEBUG] Screenshot saved:"
                    " flow-home-debug.png"
                )

                print(
                    "\nLeave browser open for inspection."
                )

                while True:
                    time.sleep(5)

            # ------------------------------------------------
            # Click New Project
            # ------------------------------------------------

            print("[6] Clicking New Project...")

            new_project.click()

            print(
                "[OK] New Project clicked"
            )

            # ------------------------------------------------
            # Wait for next page/state
            # ------------------------------------------------

            print(
                "[7] Waiting for new project screen..."
            )

            page.wait_for_timeout(5000)

            print()
            print(
                "========== AFTER NEW PROJECT =========="
            )
            print(
                "URL   :", page.url
            )
            print(
                "TITLE :", page.title()
            )
            print(
                "======================================="
            )

            # ------------------------------------------------
            # Save screenshot
            # ------------------------------------------------

            page.screenshot(
                path="after-new-project.png",
                full_page=True
            )

            print(
                "[OK] Screenshot saved:"
                " after-new-project.png"
            )

            # ------------------------------------------------
            # Inspect new screen
            # ------------------------------------------------

            inspect_page(page)

            print()
            print(
                "======================================"
            )
            print(
                " NEW PROJECT TEST COMPLETED"
            )
            print(
                "======================================"
            )

            print(
                "\nBrowser ko open rakha gaya hai."
            )
            print(
                "Ctrl+C press karke stop kar sakte hain."
            )

            # ------------------------------------------------
            # Keep browser alive
            # ------------------------------------------------

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
            "\n[EXIT] Test stopped."
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
