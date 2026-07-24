"""Playwright-based BCO-DMO website search (deprecated; prefer ERDDAP search)."""

import sys
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from defs.common import log, write_json

BASE_URL = "https://www.bco-dmo.org"
SEARCH_URL = f"{BASE_URL}/search/dataset"


def extract_dataset_links(page):
    """
    Return dataset href attributes visible in the current DOM.

    Matches both /dataset/<id> and /doi/dataset/... patterns so the
    caller receives every format BCO-DMO uses for landing pages.
    """
    return page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href]'))
            .map(a => a.getAttribute('href'))
            .filter(href => href &&
                (/\\/dataset\\/\\d/.test(href) || href.includes('/doi/dataset/')));
    }""")


def scrape_search_results(keyword: str, *, headless: bool = True) -> list[str]:
    """
    Walk paginated BCO-DMO search results and return unique landing page URLs.

    Args:
        keyword: Search term to query
        headless: Run browser without a visible window

    Returns:
        list[str]: Absolute, deduplicated dataset landing page URLs
    """
    seen = set()
    ordered = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent="BCO-DMO-Scanner/1.0")
        page = context.new_page()

        page_num = 0

        while True:
            params = urlencode({"query": f"~'{keyword}", "page": page_num})
            url = f"{SEARCH_URL}?{params}"
            log(f"Scanning page {page_num}: {url}")

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                log(f"Error loading page {page_num}: {e}")
                break

            links = extract_dataset_links(page)

            new_links = []
            for href in links:
                abs_url = BASE_URL + href if href.startswith("/") else href
                if abs_url not in seen:
                    seen.add(abs_url)
                    new_links.append(abs_url)

            if not new_links:
                log(f"No new results on page {page_num} — search complete.")
                break

            ordered.extend(new_links)
            log(f"  +{len(new_links)} datasets (running total: {len(ordered)})")
            page_num += 1

        page.close()
        context.close()
        browser.close()

    return ordered


def run_scan_datasets(
    keyword: str,
    *,
    output: Path,
    urls_output: Path | None = None,
    headless: bool = True,
    print_urls: bool = False,
) -> dict:
    """
    Search the BCO-DMO website and write results to disk.

    Args:
        keyword: Search term
        output: Path for the primary JSON result file
        urls_output: Optional path for a plain-text URL list (one per line)
        headless: Run Playwright without a visible browser window
        print_urls: Echo URLs to stdout after writing files

    Returns:
        dict: Result payload written to ``output``
    """
    log(f"Searching BCO-DMO datasets for: '{keyword}'")

    urls = scrape_search_results(keyword, headless=headless)

    result = {
        "keyword": keyword,
        "count": len(urls),
        "datasets": urls,
    }

    write_json(output, result)
    log(f"\nDone. {len(urls)} datasets written to {output}")

    if urls_output is not None:
        urls_output.parent.mkdir(parents=True, exist_ok=True)
        urls_output.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
        log(f"URL list written to {urls_output}")

    if print_urls:
        for url in urls:
            print(url)

    return result