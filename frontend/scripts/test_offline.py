"""Offline-mode test: turn off network → list still loads → create product → queued in outbox."""
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
        # Load online first to populate cache
        page.goto("http://localhost:5173/", wait_until="networkidle", timeout=30000)
        page.wait_for_selector("button.card", timeout=15000)
        page.wait_for_timeout(1500)

        # Now go offline — block any future requests so we can simulate
        context.set_offline(True)
        # We don't reload (no SW in dev). The cached list is already in React state.
        # Give the UI a moment to register the offline event.
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT / "12-offline-list.png"))

        # Open new product
        page.locator('button[aria-label="Neues Produkt anlegen"]').click()
        page.wait_for_timeout(700)
        page.fill('input#f-name', 'Offline Test')
        page.fill('#f-cost', '1,00')
        page.fill('#f-sell', '2,50')
        page.screenshot(path=str(OUT / "13-offline-new-product-form.png"))
        page.locator('button[type="submit"]:has-text("Anlegen")').click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "14-offline-product-queued.png"))

        # Check Mehr → outbox counter
        page.click("text=Mehr")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "15-mehr-offline-outbox.png"))

        browser.close()
    for f in sorted(OUT.glob("*.png")):
        print(f.name, f.stat().st_size)

if __name__ == "__main__":
    main()