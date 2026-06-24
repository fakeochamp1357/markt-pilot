"""Debug offline flow."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    page.on("console", lambda msg: print(f"[{msg.type}]", msg.text))
    page.on("pageerror", lambda err: print("[err]", err))
    page.goto("http://localhost:5173/", wait_until="networkidle", timeout=30000)
    page.wait_for_selector("button.card", timeout=15000)
    page.wait_for_timeout(2000)

    print("--- going offline ---")
    context.set_offline(True)
    page.wait_for_timeout(2500)

    print("--- opening FAB ---")
    page.locator('button[aria-label="Neues Produkt anlegen"]').click()
    page.wait_for_timeout(500)
    page.fill('input#f-name', 'Offline Test')
    page.fill('#f-cost', '1,00')
    page.fill('#f-sell', '2,50')
    print("--- clicking Anlegen ---")
    page.locator('button[type="submit"]:has-text("Anlegen")').click()
    page.wait_for_timeout(2500)

    # Inspect IndexedDB directly
    outbox_count = page.evaluate("""
async () => {
  const db = await new Promise((resolve, reject) => {
    const req = indexedDB.open('markt-pilot');
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  const tx = db.transaction('outbox', 'readonly');
  const store = tx.objectStore('outbox');
  const all = await new Promise((resolve) => {
    const r = store.getAll();
    r.onsuccess = () => resolve(r.result);
  });
  return { count: all.length, items: all.map(e => ({status: e.status, kind: e.op.kind})) };
}
""")
    print("--- IndexedDB outbox state:", outbox_count)

    page.click("text=Mehr")
    page.wait_for_timeout(2500)
    # Grab the visible counter text
    rows = page.locator("text=Offene Änderungen").all()
    print("--- visible counter rows:", len(rows))

    browser.close()