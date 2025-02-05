# Combined Sitemap & Self-contained Page Scraper

This Python project scrapes an entire website by discovering its sitemap, downloading all the pages, and saving them as self-contained HTML files. Each saved HTML file inlines external CSS and image resources so that it renders similarly to the original page, similar to how [SingleFile](https://github.com/gildas-lormeau/SingleFile) works.

## Features

- **Sitemap Discovery:**  
  Automatically discovers sitemap URLs from the website's `robots.txt` or uses the default `/sitemap.xml`.

- **Sitemap Parsing:**  
  Supports parsing standard sitemaps and sitemap indexes.

- **Resource Inlining:**  
  Uses Playwright to open each page, then inlines external CSS and images so the HTML is self-contained.

- **Preserves URL Structure:**  
  Saves the scraped pages in a directory structure that mirrors the website's URL paths.

## Prerequisites

- **Python 3.7+**
- **Pip**

Install the required Python packages:

```bash
pip install requests playwright
