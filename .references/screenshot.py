"""Take mobile-viewport screenshots of the running MarktPilot app for verification."""
import sys
from playwright.sync_api import sync_playwright

VIEWPORTS = [
    ("home", "http://localhost:5173/", "Preisliste"),
    ("inventory", "http://localhost:5173/inventory", "Warenbestand"),
    ("categories", "http://localhost:5173/categories", "Kategorien"),
    ("scanner", "http://localhost:5173/scanner", "Scanner"),
    ("more", "http://localhost:5173/more", "Mehr"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
        locale="de-DE",
        is_mobile=True,
        has_touch=True,
    )
    page = ctx.new_page()
    page.set_default_timeout(15000)
    for slug, url, label in VIEWPORTS:
        try:
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(2000)
            path = f"/workspace/markt-pilot/.references/screenshot-{slug}.png"
            page.screenshot(path=path, full_page=True)
            print(f"  {label:14s} -> {path}")
        except Exception as e:
            print(f"  {label:14s} FAIL: {e}", file=sys.stderr)
    browser.close()
print("done")
