"""Capture bottom-sheets and product form."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/tmp/frontend-shots")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.on("pageerror", lambda err: print(f"[pageerror]", err))
        page.goto("http://localhost:5173/", wait_until="networkidle", timeout=30000)
        page.wait_for_selector("button.card", timeout=15000)
        page.wait_for_timeout(1500)

        # Product action sheet
        page.locator("button.card").first.click()
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / "06-product-action-sheet.png"))

        # Close
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # New product FAB
        page.locator('button[aria-label="Neues Produkt anlegen"]').click()
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / "07-new-product-sheet.png"))

        # Fill out a product to demonstrate live margin calc
        page.fill('input[placeholder*="Bananen"]', "Demo Produkt")
        page.fill('input[placeholder*="z.B. 1kg"]', "500ml")
        page.fill('#f-cost', "1,20")
        page.fill('#f-sell', "2,49")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "08-product-form-margin.png"))

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # Warenbestand + Aktuelle Bewegungen tab
        page.click("text=Warenbestand")
        page.wait_for_timeout(700)
        page.click("text=Aktuelle Bewegungen")
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / "09-inventory-movements.png"))

        # Scanner manual entry
        page.click("text=Scanner")
        page.wait_for_timeout(500)
        page.locator("button.btn-secondary >> nth=1").click()  # keyboard icon
        page.wait_for_timeout(400)
        page.fill('input#barcode-input', '4015001000008')  # Bananen
        page.click('button[type="submit"]')
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "10-scanner-found.png"))

        # Try a miss
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.locator("button.btn-secondary >> nth=1").click()
        page.wait_for_timeout(300)
        page.fill('input#barcode-input', '9999999999999')
        page.click('button[type="submit"]')
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "11-scanner-miss-new-product.png"))

        browser.close()
    for f in sorted(OUT.glob("*.png")):
        print(f.name, f.stat().st_size)

if __name__ == "__main__":
    main()