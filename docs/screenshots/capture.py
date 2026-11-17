"""Take the README's screenshots from the running stack, so they can be retaken after any change.

  make screenshots

runs this inside the Playwright image (browsers included) on the stack's network:

  docker run --rm --network "${COMPOSE_PROJECT_NAME:-sql-megasamples}_default" -v "$PWD/docs/screenshots:/out" \\
      mcr.microsoft.com/playwright/python:v1.65.2-noble@sha256:38dd67fc654b56b3cba611e4c8eb71cd33750e1cd29eea2a5dc00b484817a75f sh -c \\
      "pip install -q --break-system-packages playwright==1.65.2 && python3 /out/capture.py"

Three pictures: the console index tall enough to show the connection help, the consoles and the
first rows of the database table; CloudBeaver with the MySQL read-only connection opened down to
sakila's `film` table on its Data tab; DbGate on the same table with its connection list scrolled
back to the top. The consoles are driven through their own markup (CloudBeaver's tree-node
controls, DbGate's connection list), which is why the selectors here are specific to the pinned
image versions. Every screenshot is 1440 px wide at 1x; nothing in them is staged.
"""
import re, time

from playwright.sync_api import sync_playwright

OUT = "/out"

with sync_playwright() as p:
    browser = p.chromium.launch()

    # the console index
    ctx = browser.new_context(viewport={"width": 1440, "height": 1500}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto("http://landing/", wait_until="networkidle")
    time.sleep(1)
    page.screenshot(path=f"{OUT}/landing.png")
    ctx.close()

    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)

    # CloudBeaver: MySQL (read-only) > Databases > sakila > Tables > film, Data tab
    page = ctx.new_page()
    page.goto("http://cloudbeaver:8978/", wait_until="networkidle")
    time.sleep(5)

    def expand(text, wait=6):
        node = page.locator('[data-tree-node-control="true"]').filter(has=page.get_by_text(text, exact=True)).first
        node.locator('[title="Expand"]').first.click()
        time.sleep(wait)

    expand("MySQL (read-only)", 8)
    expand("Databases")
    expand("sakila")
    expand("Tables")
    film = page.locator('[data-tree-node-control="true"]').filter(has=page.get_by_text("film", exact=True))
    # A full catalogue virtualizes rows below the navigation viewport.
    for attempt in range(12):
        if film.count():
            break
        page.locator('[data-tree-node-control="true"]').last.hover()
        page.mouse.wheel(0, 350)
        page.wait_for_timeout(350)
    film.first.dblclick()
    time.sleep(10)
    tab = page.get_by_role("tab", name="Data").first
    if tab.count():
        tab.click()
        time.sleep(5)
    page.screenshot(path=f"{OUT}/cloudbeaver.png")

    # DbGate: MySQL (read-only) > sakila > film, the connection list scrolled back to the top
    page = ctx.new_page()
    page.goto("http://dbgate:3000/", wait_until="load")
    time.sleep(10)
    # A fresh browser profile receives DbGate's optional analytics prompt.
    # Keep screenshot capture private and wait until the connection list is usable.
    decline = page.get_by_test_id("UsageAnalyticsConsentModal_declineButton")
    if decline.is_visible():
        decline.click()
        decline.wait_for(state="hidden")
    page.locator('[data-testid="ConnectionList_container"] div.main', has_text="MySQL (read-only)").first.click()
    time.sleep(8)
    page.locator("div.main", has_text=re.compile(r"^\s*sakila\b")).first.click()
    time.sleep(8)
    page.locator("div.main", has_text=re.compile(r"^\s*film\b")).first.click()
    time.sleep(8)
    page.evaluate("""() => { let e = document.querySelector('[data-testid="ConnectionList_container"]');
                             while (e) { e.scrollTop = 0; e = e.parentElement; } }""")
    time.sleep(1)
    page.screenshot(path=f"{OUT}/dbgate.png")
    browser.close()
