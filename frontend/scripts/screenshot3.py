"""Final round: scanner flows and offline simulation."""
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

        # Scanner manual entry — hit
        page.click("text=Scanner")
        page.wait_for_timeout(500)
        page.locator('button[aria-label=""]').filter(has=page.locator('svg')).nth(2).click()
        page.wait_for_timeout(400)
        # Use the manual input form (visible)
        page.fill('input#barcode-input', '4015001000008')
        page.locator('button[type="submit"]:has-text("Suchen")').click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "10-scanner-found.png"))

        # Miss → new product sheet
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        # Open manual entry again
        page.locator('button:has(svg.lucide-keyboard)').click()
        page.wait_for_timeout(400)
        page.fill('input#barcode-input', '9999999999999')
        page.locator('button[type="submit"]:has-text("Suchen")').click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "11-scanner-miss-new-product.png"))

        browser.close()
    for f in sorted(OUT.glob("*.png")):
        print(f.name, f.stat().st_size)

if __name__ == "__main__":
    main()