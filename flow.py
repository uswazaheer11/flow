import sys
import time
import requests
from playwright.sync_api import sync_playwright


API = "http://127.0.0.1:53200/api/v2"

# CHANGE THIS
PROFILE_ID = 3878

FLOW_URL = "https://flow.google.com"

TEST_PROMPT = """
A cinematic historical scene of an ancient Roman city at sunset,
wide establishing shot, realistic architecture, dramatic lighting,
documentary style, highly detailed.
""".strip()


def open_ixbrowser_profile(profile_id: int):
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

    r = requests.post(
        f"{API}/profile-open",
        json=payload,
        timeout=60
    )

    print(f"    HTTP: {r.status_code}")

    data = r.json()

    if data.get("error", {}).get("code") != 0:
        raise RuntimeError(data.get("error"))

    return data["data"]


def inspect_flow(page):
    print("\n========== FLOW UI INSPECTION ==========")

    print("\nTEXTAREAS:")
    for i in range(page.locator("textarea").count()):
        el = page.locator("textarea").nth(i)

        try:
            print(
                f"  textarea[{i}] "
                f"placeholder={el.get_attribute('placeholder')!r}"
            )
        except Exception:
            pass

    print("\nINPUTS:")
    for i in range(page.locator("input").count()):
        el = page.locator("input").nth(i)

        try:
            print(
                f"  input[{i}] "
                f"type={el.get_attribute('type')!r} "
                f"placeholder={el.get_attribute('placeholder')!r}"
            )
        except Exception:
            pass

    print("\nBUTTONS:")
    for i in range(page.locator("button").count()):
        el = page.locator("button").nth(i)

        try:
            text = el.inner_text(timeout=1000).strip()
            aria = el.get_attribute("aria-label")

            if text or aria:
                print(
                    f"  button[{i}] "
                    f"text={text!r} "
                    f"aria-label={aria!r}"
                )
        except Exception:
            pass

    print("========================================\n")


def find_prompt_input(page):
    """
    Try several generic strategies instead of depending
    on one fragile Flow CSS class.
    """

    # 1. Textarea
    textareas = page.locator("textarea")

    for i in range(textareas.count()):
        el = textareas.nth(i)

        try:
            if el.is_visible():
                return el
        except Exception:
            pass

    # 2. Contenteditable
    editables = page.locator('[contenteditable="true"]')

    for i in range(editables.count()):
        el = editables.nth(i)

        try:
            if el.is_visible():
                return el
        except Exception:
            pass

    # 3. Inputs
    inputs = page.locator("input")

    for i in range(inputs.count()):
        el = inputs.nth(i)

        try:
            if el.is_visible():
                return el
        except Exception:
            pass

    return None


def find_submit_button(page):
    """
    Look for a visible button using accessible text/labels.
    """

    candidates = [
        "Generate",
        "Create",
        "Submit",
        "Send"
    ]

    for name in candidates:

        locator = page.get_by_role(
            "button",
            name=name,
            exact=True
        )

        try:
            if locator.count() > 0 and locator.first.is_visible():
                return locator.first
        except Exception:
            pass

    # Try aria-label / title containing common terms.
    buttons = page.locator("button")

    for i in range(buttons.count()):
        button = buttons.nth(i)

        try:
            if not button.is_visible():
                continue

            aria = (
                button.get_attribute("aria-label") or ""
            ).lower()

            title = (
                button.get_attribute("title") or ""
            ).lower()

            text = (
                button.inner_text(timeout=500) or ""
            ).lower()

            combined = f"{aria} {title} {text}"

            if any(
                word in combined
                for word in [
                    "generate",
                    "create",
                    "submit",
                    "send"
                ]
            ):
                return button

        except Exception:
            pass

    return None


def main():

    try:

        browser_data = open_ixbrowser_profile(
            PROFILE_ID
        )

        debugging_address = browser_data[
            "debugging_address"
        ]

        print("[OK] IXBrowser profile opened")
        print(
            f"[OK] CDP: {debugging_address}"
        )

        with sync_playwright() as p:

            print("[2] Connecting to IXBrowser...")

            browser = p.chromium.connect_over_cdp(
                f"http://{debugging_address}"
            )

            print("[OK] Connected")

            if not browser.contexts:
                raise RuntimeError(
                    "No browser context found."
                )

            context = browser.contexts[0]

            pages = context.pages

            if pages:
                page = pages[0]
            else:
                page = context.new_page()

            print("[3] Opening Flow...")

            page.goto(
                FLOW_URL,
                wait_until="domcontentloaded",
                timeout=120000
            )

            print("[OK] Flow opened")

            print("[4] Waiting for Flow UI...")

            page.wait_for_timeout(8000)

            print(
                f"[OK] URL: {page.url}"
            )

            print(
                f"[OK] TITLE: {page.title()}"
            )

            # Inspect current UI first.
            inspect_flow(page)

            print("[5] Finding prompt input...")

            prompt_input = find_prompt_input(page)

            if not prompt_input:

                print(
                    "[ERROR] Prompt input was not found."
                )

                print(
                    "Take a screenshot / inspect the UI "
                    "before adding automation."
                )

                page.screenshot(
                    path="flow-debug.png",
                    full_page=True
                )

                print(
                    "[DEBUG] Saved flow-debug.png"
                )

                while True:
                    time.sleep(5)

            print("[OK] Prompt input found")

            print("[6] Filling prompt...")

            prompt_input.click()

            # Handle textarea/contenteditable/input differently.
            tag = prompt_input.evaluate(
                "(el) => el.tagName"
            )

            if tag == "TEXTAREA" or tag == "INPUT":
                prompt_input.fill(TEST_PROMPT)
            else:
                prompt_input.fill(TEST_PROMPT)

            print("[OK] Prompt pasted")

            page.wait_for_timeout(1000)

            print("[7] Finding Generate button...")

            submit_button = find_submit_button(page)

            if not submit_button:

                print(
                    "[ERROR] Generate/Submit button "
                    "was not found."
                )

                inspect_flow(page)

                page.screenshot(
                    path="flow-before-submit.png",
                    full_page=True
                )

                print(
                    "[DEBUG] Saved flow-before-submit.png"
                )

                while True:
                    time.sleep(5)

            print("[OK] Submit button found")

            print("[8] Clicking Generate...")

            submit_button.click()

            print("[OK] Generate clicked")

            print()
            print("======================================")
            print(" FLOW GENERATION STARTED")
            print("======================================")
            print()
            print(
                "Prompt:",
                TEST_PROMPT
            )
            print()
            print(
                "The browser will remain open."
            )
            print(
                "Press Ctrl+C to stop."
            )

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

        print("\n[EXIT] Stopped.")

    except Exception as e:

        print("\n[ERROR]")
        print(type(e).__name__)
        print(str(e))

        sys.exit(1)


if __name__ == "__main__":
    main()
