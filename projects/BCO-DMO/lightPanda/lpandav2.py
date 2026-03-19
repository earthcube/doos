from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Connect to Lightpanda's CDP server (equivalent to puppeteer.connect)
    browser = p.chromium.connect_over_cdp("ws://127.0.0.1:9222")

    # createBrowserContext → new_context()
    context = browser.new_context()
    page = context.new_page()

    # goto with networkidle equivalent
    page.goto("https://www.bco-dmo.org/doi/dataset/10.26008/1912/bco-dmo.990510.1", wait_until="networkidle")

    # evaluate → same concept, returns Python objects directly
    # links = page.evaluate("""() => {
    #     return Array.from(document.querySelectorAll('a')).map(row => {
    #         return row.getAttribute('href');
    #     });
    # }""")

    # print(links)
    results = []
    json_ld_docs = page.evaluate("""() => {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                return Array.from(scripts).map(s => {
                    try { return JSON.parse(s.textContent); }
                    catch { return null; }
                }).filter(Boolean);
            }""")

    results.extend(json_ld_docs)
    print(results)

    page.close()
    context.close()
    browser.close()