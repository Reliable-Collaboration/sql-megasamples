"""Submit a statement through CloudBeaver's SQL editor in a task-owned browser."""

import sys

from playwright.sync_api import sync_playwright


def query(browser, url):
    context = browser.new_context()
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    connection = page.get_by_text("PostgreSQL (read-only)", exact=True).first
    connection.click(timeout=45_000)
    page.locator('[title="Open SQL Editor"], [aria-label="Open SQL Editor"]').first.click(timeout=15_000)
    editor = page.locator(".cm-content[contenteditable=true], .monaco-editor textarea").first
    editor.click(timeout=15_000)
    page.keyboard.insert_text("SELECT 17077 AS dl077_editor")
    page.keyboard.press("Control+Enter")
    page.get_by_text("17077", exact=True).first.wait_for(timeout=20_000)
    print("CloudBeaver SQL editor returned 17077", flush=True)
    return context


if __name__ == "__main__":
    address, sessions = sys.argv[1:]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--disable-dev-shm-usage"])
        contexts = [query(browser, address) for _ in range(int(sessions))]
        browser.close()
