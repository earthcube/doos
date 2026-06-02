#!/usr/bin/env python3
"""
Scan BCO-DMO dataset search results for a keyword and collect landing page URLs.

Uses Playwright to render the JS-heavy search page and walks pagination until
no new results appear. Output is a JSON file plus one URL per line on stdout.

Usage:
    python scan_datasets.py --keyword depth --output depth_urls.json
    python scan_datasets.py --keyword depth | head -20
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

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


def scrape_search_results(keyword, headless=True):
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
            print(f"Scanning page {page_num}: {url}", file=sys.stderr)

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                print(f"Error loading page {page_num}: {e}", file=sys.stderr)
                break

            links = extract_dataset_links(page)

            new_links = []
            for href in links:
                abs_url = BASE_URL + href if href.startswith("/") else href
                if abs_url not in seen:
                    seen.add(abs_url)
                    new_links.append(abs_url)

            if not new_links:
                print(
                    f"No new results on page {page_num} — search complete.",
                    file=sys.stderr,
                )
                break

            ordered.extend(new_links)
            print(
                f"  +{len(new_links)} datasets (running total: {len(ordered)})",
                file=sys.stderr,
            )
            page_num += 1

        page.close()
        context.close()
        browser.close()

    return ordered


def main():
    parser = argparse.ArgumentParser(
        description="Collect BCO-DMO dataset landing page URLs matching a keyword"
    )
    parser.add_argument(
        "--keyword", default="depth", help="Search keyword (default: depth)"
    )
    parser.add_argument(
        "--output", default="scan_results.json", help="Output JSON file path"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window while scanning",
    )

    args = parser.parse_args()

    print(f"Searching BCO-DMO datasets for: '{args.keyword}'", file=sys.stderr)

    try:
        urls = scrape_search_results(args.keyword, headless=not args.no_headless)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = {
        "keyword": args.keyword,
        "count": len(urls),
        "datasets": urls,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(
        f"\nDone. {len(urls)} datasets written to {output_path}",
        file=sys.stderr,
    )

    for url in urls:
        print(url)


if __name__ == "__main__":
    main()
