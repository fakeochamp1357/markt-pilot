"""Test: offline create → online → sync."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.on("console", lambda msg: print(f"[{msg.type}]", msg.text[:300]))

    def on_request(req):
        if "/api/products" in req.url and req.method == "POST":
            print(f"[req] POST {req.url}")
            print(f"[req-body] {req.post_data}")
    def on_response(r):
        if "/api/products" in r.url and r.request.method == "POST":
            print(f"[resp] {r.status} {r.url}")
    page.on("request", on_request)
    page.on("response", on_response)
    page.on("pageerror", lambda err: print("[err]", err))
    page.goto("http://localhost:5173/", wait_until="networkidle")
    page.wait_for_selector("button.card")
    page.wait_for_timeout(1500)
    context.set_offline(True)
    page.wait_for_timeout(1500)
    page.locator('button[aria-label="Neues Produkt anlegen"]').click()
    page.wait_for_timeout(500)
    page.fill('input#f-name', 'Sync Test Produkt')
    page.fill('#f-cost', '2,00')
    page.fill('#f-sell', '4,99')
    page.locator('button[type="submit"]:has-text("Anlegen")').click()
    page.wait_for_timeout(2000)

    page.click("text=Mehr")
    page.wait_for_timeout(1500)
    page.screenshot(path="/tmp/sync-before.png")

    # Back online — outbox should sync automatically
    print("--- back online ---")
    context.set_offline(False)
    page.wait_for_timeout(8000)  # wait for polling tick
    page.screenshot(path="/tmp/sync-after.png")

    # Check the IndexedDB outbox is now empty
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
  return all.length;
}
""")
    print("--- outbox size after sync:", outbox_count)

    # Verify backend now has the product
    import urllib.request, json
    products = json.loads(urllib.request.urlopen("http://localhost:8000/api/products?q=Sync%20Test").read())
    print("--- backend has:", [p['name'] for p in products['items']])

    browser.close()