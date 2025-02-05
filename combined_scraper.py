#!/usr/bin/env python3
import os
import sys
import time
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright

def get_sitemap_urls(main_url):
    """
    Try to get sitemap URLs from the site's robots.txt. If none are found, try /sitemap.xml.
    """
    parsed = urlparse(main_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(base, "/robots.txt")
    sitemap_urls = []
    print(f"Fetching robots.txt from {robots_url} ...")
    try:
        resp = requests.get(robots_url, timeout=10)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    sitemap_urls.append(sitemap_url)
                    print(f"Found sitemap in robots.txt: {sitemap_url}")
        else:
            print(f"robots.txt not found (HTTP {resp.status_code}).")
    except Exception as e:
        print(f"Error fetching robots.txt: {e}")

    # If no sitemap was discovered in robots.txt, try the default /sitemap.xml.
    if not sitemap_urls:
        possible = urljoin(base, "/sitemap.xml")
        print(f"Trying default sitemap at {possible} ...")
        try:
            resp = requests.get(possible, timeout=10)
            if resp.status_code == 200:
                sitemap_urls.append(possible)
                print(f"Found sitemap: {possible}")
            else:
                print(f"No sitemap found at {possible} (HTTP {resp.status_code}).")
        except Exception as e:
            print(f"Error fetching sitemap.xml: {e}")

    return sitemap_urls

def parse_sitemap(sitemap_url):
    """
    Download and parse the sitemap (or sitemap index) and return a list of page URLs.
    """
    urls = []
    try:
        print(f"Downloading sitemap: {sitemap_url}")
        resp = requests.get(sitemap_url, timeout=10)
        if resp.status_code != 200:
            print(f"Error fetching sitemap {sitemap_url}: HTTP {resp.status_code}")
            return urls

        content = resp.content
        # Handle gzip-compressed sitemaps if needed.
        if sitemap_url.endswith('.gz'):
            import gzip
            content = gzip.decompress(content)

        root = ET.fromstring(content)
        tag = root.tag.lower()
        if tag.endswith("sitemapindex"):
            # This sitemap is an index of other sitemaps.
            for sitemap in root.findall("{*}sitemap"):
                loc = sitemap.find("{*}loc")
                if loc is not None and loc.text:
                    child_sitemap = loc.text.strip()
                    print(f"Found child sitemap: {child_sitemap}")
                    urls.extend(parse_sitemap(child_sitemap))
        elif tag.endswith("urlset"):
            # Standard sitemap listing page URLs.
            for url in root.findall("{*}url"):
                loc = url.find("{*}loc")
                if loc is not None and loc.text:
                    page_url = loc.text.strip()
                    urls.append(page_url)
        else:
            print("Unknown XML format in sitemap.")
    except Exception as e:
        print(f"Error parsing sitemap {sitemap_url}: {e}")

    return urls

def get_file_path(url, output_folder):
    """
    Convert a URL into a file name and return the full path under output_folder.
    All files are saved in the same folder. The file name is derived by combining the domain
    (with dots replaced by underscores) and the URL path (with slashes replaced by underscores).
    
    Examples:
      - https://example.com/         -> example_com_index.html
      - https://example.com/about    -> example_com_about.html
      - https://example.com/blog/     -> example_com_blog_index.html
    """
    parsed = urlparse(url)
    # Replace dots in the domain with underscores
    domain = parsed.netloc.replace('.', '_')
    
    path = parsed.path
    if not path or path.endswith('/'):
        path = path + "index.html"
    else:
        if not os.path.splitext(path)[1]:
            path = path + ".html"
    # Remove any leading slash and replace remaining slashes with underscores.
    path = path.lstrip('/').replace('/', '_')
    # Combine domain and path to form a file name.
    file_name = f"{domain}_{path}"
    return os.path.join(output_folder, file_name)

def save_page_with_inlining(browser, url, output_folder):
    """
    Opens the given URL in a Playwright page, inlines external resources (CSS and images),
    and then saves the resulting self-contained HTML to disk.
    """
    print(f"\nProcessing page: {url}")
    page = browser.new_page()
    try:
        page.goto(url, wait_until="networkidle")
        # Inline external CSS and images via an async IIFE.
        inline_script = """
        (async () => {
            // Inline external CSS files.
            const links = Array.from(document.querySelectorAll('link[rel="stylesheet"]'));
            for (const link of links) {
                try {
                    const response = await fetch(link.href);
                    const cssText = await response.text();
                    const style = document.createElement('style');
                    style.textContent = cssText;
                    link.parentNode.insertBefore(style, link);
                    link.remove();
                } catch (err) {
                    console.error('Error inlining stylesheet:', link.href, err);
                }
            }
        
            // Inline images by converting them to data URLs.
            const images = Array.from(document.querySelectorAll('img'));
            for (const img of images) {
                if (img.src && !img.src.startsWith('data:')) {
                    try {
                        const response = await fetch(img.src);
                        const blob = await response.blob();
                        const reader = new FileReader();
                        await new Promise(resolve => {
                            reader.onloadend = resolve;
                            reader.readAsDataURL(blob);
                        });
                        img.src = reader.result;
                    } catch (err) {
                        console.error('Error inlining image:', img.src, err);
                    }
                }
            }
        })();
        """
        print("Inlining external resources …")
        page.evaluate(inline_script)
        # Give a moment for inlining to finish.
        time.sleep(1)
        content = page.content()
        file_path = get_file_path(url, output_folder)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved page to {file_path}")
    except Exception as e:
        print(f"Error processing {url}: {e}")
    finally:
        page.close()

def main():
    print("Welcome to the Combined Sitemap and Self-contained Page Scraper!")
    main_url = input("Enter the main URL of the website to scrape (e.g., https://example.com): ").strip()
    if not main_url:
        print("No URL provided. Exiting.")
        return

    # Optional: Ask for maximum number of pages to scrape.
    max_pages_input = input("Enter maximum number of pages to scrape (default 100): ").strip()
    try:
        max_pages = int(max_pages_input) if max_pages_input else 100
    except ValueError:
        print("Invalid input for maximum pages. Using default value of 100.")
        max_pages = 100

    # Create a folder for the website using its domain (dots replaced with underscores).
    parsed_main = urlparse(main_url)
    domain_folder = parsed_main.netloc.replace('.', '_')
    output_folder = os.path.join("downloaded_site", domain_folder)
    os.makedirs(output_folder, exist_ok=True)
    print(f"All files will be saved in: {output_folder}")

    # Discover sitemap URLs.
    sitemap_urls = get_sitemap_urls(main_url)
    if not sitemap_urls:
        print("No sitemap found for the given URL. Exiting.")
        return

    # Parse all discovered sitemaps.
    all_page_urls = []
    for sitemap in sitemap_urls:
        print(f"\nProcessing sitemap: {sitemap}")
        page_urls = parse_sitemap(sitemap)
        print(f"Found {len(page_urls)} page URLs in sitemap {sitemap}")
        all_page_urls.extend(page_urls)

    # Remove duplicate URLs while preserving order.
    unique_page_urls = list(dict.fromkeys(all_page_urls))
    total_found = len(unique_page_urls)
    print(f"\nTotal unique pages found: {total_found}")

    # Limit the pages to scrape if needed.
    if total_found > max_pages:
        print(f"Limiting pages to the first {max_pages} of {total_found} found.")
        unique_page_urls = unique_page_urls[:max_pages]

    # Use Playwright to open each page, inline its resources, and save it.
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for url in unique_page_urls:
            save_page_with_inlining(browser, url, output_folder)
        browser.close()

    print("\nScraping complete!")

if __name__ == "__main__":
    main()
