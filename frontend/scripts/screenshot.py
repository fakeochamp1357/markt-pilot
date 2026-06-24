"""Quick visual smoke-test: open Preisliste, capture screenshots."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/tmp/frontend-shots")
OUT.mkdir(exist_ok=True)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # iPhone 13-ish viewport
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.on("console", lambda msg: print(f"[console:{msg.type}]", msg.text))
        page.on("pageerror", lambda err: print(f"[pageerror]", err))
        page.goto("http://localhost:5173/", wait_until="networkidle", timeout=30000)
        # Wait until products render (at least one product card visible)
        try:
            page.wait_for_selector("text=Produkt", timeout=15000)
        except Exception as e:
            print(f"[warn] product text not found: {e}")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "01-preisliste.png"), full_page=False)

        page.click("text=Warenbestand")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "02-inventory.png"), full_page=False)

        page.click("text=Kategorien")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "03-categories.png"), full_page=False)

        page.click("text=Scanner")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "04-scanner.png"), full_page=False)

        page.click("text=Mehr")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "05-more.png"), full_page=False)

        # Open a product bottom-sheet
        page.click("text=Preisliste")
        page.wait_for_timeout(1000)
        try:
            page.locator("button.card").first.click()
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / "06-product-action-sheet.png"))
        except Exception as e:
            print(f"[warn] action sheet failed: {e}")

        # Open new product sheet
        page.locator('button[aria-label="Neues Produkt anlegen"]').click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "07-new-product-sheet.png"))

        browser.close()
    for f in sorted(OUT.glob("*.png")):
        print(f.name, f.stat().st_size)

if __name__ == "__main__":
    main()