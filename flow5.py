import time
import requests
from playwright.sync_api import sync_playwright

PROFILE_ID = 3878

IX_OPEN_URL = "http://127.0.0.1:53200/api/v2/profile-open"

PROMPT = """A cinematic historical scene of an ancient Roman city at sunset,
wide establishing shot, realistic architecture, dramatic lighting,
documentary style, highly detailed."""

def open_ixbrowser_profile():
    r = requests.post(
        IX_OPEN_URL,
        json={
            "profile_id": PROFILE_ID,
            "args": ["--disable-extension-welcome-page"],
            "load_extensions": True,
            "load_profile_info_page": True,
            "cookies_backup": True,
            "cookie": ""
        },
        timeout=30
    )

    print("    HTTP:", r.status_code)
    r.raise_for_status()

    data = r.json()["data"]
    print("[OK] IXBrowser profile opened")
    print("     CDP:", data["debugging_address"])

    return data["debugging_address"]


def get_flow_page(browser):
    pages = browser.contexts[0].pages

    print("[OK] Existing pages:", len(pages))

    for i, p in enumerate(pages):
        print(f"    [{i}] {p.url}")

    for p in pages:
        if "flow.google.com" in p.url:
            return p

    return pages[0]


def is_project_ready(page):
    try:
        start_btn = page.get_by_role(
            "button",
            name="Start generation",
            exact=True
        )

        if start_btn.count() > 0 and start_btn.first.is_visible():
            return True
    except:
        pass

    try:
        editors = page.locator('[contenteditable="true"]')

        for i in range(editors.count()):
            if editors.nth(i).is_visible():
                return True
    except:
        pass

    return False


def inspect_result_ui(page):
    print("\n" + "=" * 70)
    print("GENERATED RESULT UI INSPECTION")
    print("=" * 70)

    print("URL:", page.url)
    print("TITLE:", page.title())

    print("\n--- BUTTONS ---")

    buttons = page.locator("button")

    for i in range(buttons.count()):
        b = buttons.nth(i)

        try:
            if not b.is_visible():
                continue

            text = (b.inner_text() or "").strip()
            aria = b.get_attribute("aria-label")
            title = b.get_attribute("title")

            print(
                f"button[{i}] "
                f"text={text!r} "
                f"aria={aria!r} "
                f"title={title!r}"
            )

        except:
            pass

    print("\n--- LINKS ---")

    links = page.locator("a")

    for i in range(links.count()):
        a = links.nth(i)

        try:
            if not a.is_visible():
                continue

            text = (a.inner_text() or "").strip()
            aria = a.get_attribute("aria-label")
            title = a.get_attribute("title")
            href = a.get_attribute("href")

            print(
                f"link[{i}] "
                f"text={text!r} "
                f"aria={aria!r} "
                f"title={title!r} "
                f"href={href!r}"
            )

        except:
            pass

    print("\n--- ELEMENTS WITH DOWNLOAD-RELATED ATTRIBUTES ---")

    selectors = [
        '[aria-label*="download" i]',
        '[title*="download" i]',
        '[data-testid*="download" i]',
    ]

    found = False

    for selector in selectors:
        try:
            els = page.locator(selector)

            for i in range(els.count()):
                el = els.nth(i)

                try:
                    if not el.is_visible():
                        continue

                    found = True

                    print(
                        selector,
                        "=>",
                        el.evaluate(
                            """el => ({
                                tag: el.tagName,
                                text: el.innerText,
                                aria: el.getAttribute('aria-label'),
                                title: el.getAttribute('title'),
                                testid: el.getAttribute('data-testid')
                            })"""
                        )
                    )

                except:
                    pass

        except:
            pass

    if not found:
        print("No obvious download-related element found.")

    print("=" * 70)


with sync_playwright() as p:

    # ------------------------------------------------------------
    # 1. IXBrowser
    # ------------------------------------------------------------

    print("[1] Opening IXBrowser profile 3878...")

    debugging_address = open_ixbrowser_profile()

    # ------------------------------------------------------------
    # 2. CDP
    # ------------------------------------------------------------

    print("[2] Connecting to IXBrowser Chromium...")

    browser = p.chromium.connect_over_cdp(
        f"http://{debugging_address}"
    )

    print("[OK] Connected to Chromium")

    # ------------------------------------------------------------
    # 3. Flow page
    # ------------------------------------------------------------

    page = get_flow_page(browser)

    # ------------------------------------------------------------
    # 4. Flow home
    # ------------------------------------------------------------

    print("[3] Opening Flow home...")

    page.goto(
        "https://flow.google.com/",
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(3000)

    # ------------------------------------------------------------
    # 5. New project
    # ------------------------------------------------------------

    print("[4] Looking for New project...")

    new_project = page.get_by_role(
        "button",
        name="New project",
        exact=True
    )

    if new_project.count() == 0:

        new_project = page.get_by_text(
            "New project",
            exact=True
        )

    if new_project.count() == 0:
        raise RuntimeError("New project button not found")

    print("[OK] New project found")

    print("[5] Clicking New project...")

    new_project.first.click()

    print("[OK] New project clicked")

    # ------------------------------------------------------------
    # 6. Wait for project UI
    # ------------------------------------------------------------

    print("\n[6] Waiting for Flow project UI...")

    project_ready = False

    for i in range(60):

        if is_project_ready(page):
            project_ready = True
            break

        print(f"[WAIT] Project UI not ready ({i + 1}/60)")
        time.sleep(1)

    if not project_ready:
        raise RuntimeError("Flow project UI did not become ready")

    print("\n" + "=" * 65)
    print("[OK] FLOW PROJECT READY")
    print("URL:", page.url)
    print("TITLE:", page.title())
    print("=" * 65)

    # ------------------------------------------------------------
    # 7. Prompt
    # ------------------------------------------------------------

    print("\n[7] Looking for prompt input...")

    editor = None

    editors = page.locator('[contenteditable="true"]')

    for i in range(editors.count()):
        e = editors.nth(i)

        try:
            if e.is_visible():
                editor = e
                print(f"[OK] Prompt contenteditable found: editable[{i}]")
                break
        except:
            pass

    if editor is None:
        raise RuntimeError("Prompt input not found")

    # ------------------------------------------------------------
    # 8. Fill prompt
    # ------------------------------------------------------------

    print("\n[8] Pasting prompt...")

    print("PROMPT:")
    print(PROMPT)

    try:
        editor.fill(PROMPT)
        print("[OK] Prompt pasted using fill()")

    except Exception as e:

        print("[WARN] fill() failed:", e)

        editor.click()
        page.keyboard.press("CTRL+A")
        page.keyboard.type(PROMPT)

        print("[OK] Prompt pasted using keyboard")

    # ------------------------------------------------------------
    # 9. Start generation
    # ------------------------------------------------------------

    print("\n[9] Looking for Start generation...")

    start_btn = page.get_by_role(
        "button",
        name="Start generation",
        exact=True
    )

    if start_btn.count() == 0:
        raise RuntimeError("Start generation button not found")

    print("[OK] Start generation found")

    # ------------------------------------------------------------
    # 10. Start
    # ------------------------------------------------------------

    print("\n[10] Clicking Start generation...")

    start_btn.first.click()

    print("[OK] Start generation clicked")

    page.screenshot(
        path="generation-started.png",
        full_page=True
    )

    print("\n" + "=" * 65)
    print("IMAGE GENERATION STARTED")
    print("=" * 65)

    # ------------------------------------------------------------
    # 11. Wait for generation
    # ------------------------------------------------------------

    print("\n[11] Waiting for generated image...")

    for i in range(120):

        time.sleep(2)

        print(
            f"[WAIT] Generation/result inspection "
            f"({i + 1}/120)"
        )

        try:
            # Screenshot periodically
            if i % 10 == 0:
                page.screenshot(
                    path=f"generation-{i + 1}.png",
                    full_page=True
                )

            # Look for visible images
            images = page.locator("img")

            visible_images = 0

            for j in range(images.count()):
                try:
                    if images.nth(j).is_visible():
                        visible_images += 1
                except:
                    pass

            # Don't immediately assume every img is the result.
            # We only use this as a signal to inspect the UI.
            if visible_images > 0 and i >= 5:

                print(
                    f"[SIGNAL] Visible images on page: "
                    f"{visible_images}"
                )

                # Give Flow a little time to finish rendering controls.
                page.wait_for_timeout(3000)

                inspect_result_ui(page)

                print("\n[STOP]")
                print("UI inspection complete.")
                print("Browser remains open.")

                while True:
                    time.sleep(10)

        except Exception as e:
            print("[WARN] Inspection error:", e)

    print("[TIMEOUT] Generation wait finished.")
    print("Browser remains open.")

    while True:
        time.sleep(10)
