import copy
import csv
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse

import requests
from lxml import html

# Optional Selenium support for sites that block plain HTTP clients (e.g. very.co.uk)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    webdriver = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).resolve().parent
URL_CSV_PATH = BASE_DIR / "url.csv"
TEMPLATE_PATH = BASE_DIR / "product-template.json"
OUTPUT_DIR = BASE_DIR / "products"


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("http://") or url.startswith("https://"):
        return url

    # Handle bare domain URLs
    if url.startswith("argos.co.uk"):
        return "https://" + url
    if url.startswith("very.co.uk"):
        return "https://www." + url

    return url


def fetch_page(url: str) -> html.HtmlElement:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return html.fromstring(resp.text)


def fetch_page_with_selenium(url: str) -> html.HtmlElement:
    """
    Load a page using a real browser (Selenium) and return an lxml document.
    Used for sites like very.co.uk that block plain HTTP clients with 403.
    """
    if webdriver is None:
        raise RuntimeError(
            "Selenium is not installed. Install it with 'pip install selenium' "
            "and ensure you have a compatible Chrome/Edge driver."
        )

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)

        # For Very, wait until the product title is present (best-effort)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="product-detail"]/h1'))
            )
        except Exception:
            # If it times out, still try to use whatever HTML we have
            pass

        page_html = driver.page_source
        return html.fromstring(page_html)
    finally:
        driver.quit()


def is_argos(url: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return "argos.co.uk" in hostname


def is_very(url: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return "very.co.uk" in hostname


def extract_argos_data(doc: html.HtmlElement) -> Dict[str, Any]:
    """
    Use the provided Argos XPaths to pull out title, images and description.
    """
    # Title
    title_nodes = doc.xpath(
        '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[2]/section/section[1]/div[2]/h1/span'
    )
    title = title_nodes[0].text_content().strip() if title_nodes else ""

    # Images container UL, then all img/src under it
    image_list_nodes = doc.xpath(
        '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[1]/section/section/div/div/div/div[2]/div[2]/div/div[2]/ul'
    )
    image_urls: List[str] = []
    if image_list_nodes:
        img_nodes = image_list_nodes[0].xpath(".//img")
        for img in img_nodes:
            src = img.get("src") or img.get("data-src") or img.get("data-main-image-url")
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            image_urls.append(src)

    # Description HTML
    desc_nodes = doc.xpath('//*[@id="pdp-description"]/div')
    description_html = ""
    if desc_nodes:
        description_html = html.tostring(
            desc_nodes[0], encoding="unicode", with_tail=False
        )

    return {
        "title": title,
        "image_urls": image_urls,
        "description_html": description_html,
    }


def extract_very_data(doc: html.HtmlElement) -> Dict[str, Any]:
    """
    Use the provided XPaths for Very.co.uk (second site).
    """
    # Title: //*[@id="product-detail"]/h1
    title_nodes = doc.xpath('//*[@id="product-detail"]/h1')
    title = title_nodes[0].text_content().strip() if title_nodes else ""

    # Images: container //*[@id="splide02-list"], then all imgs beneath
    image_list_nodes = doc.xpath('//*[@id="splide02-list"]')
    image_urls: List[str] = []
    if image_list_nodes:
        img_nodes = image_list_nodes[0].xpath(".//img")
        for img in img_nodes:
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            # Handle relative URLs
            if src.startswith("/"):
                src = "https://www.very.co.uk" + src
            image_urls.append(src)

    # Description: //*[@id="product-page-container"]/div[1]/div[3]/div[1]/div/div
    desc_nodes = doc.xpath(
        '//*[@id="product-page-container"]/div[1]/div[3]/div[1]/div/div'
    )
    description_html = ""
    if desc_nodes:
        description_html = html.tostring(
            desc_nodes[0], encoding="unicode", with_tail=False
        )

    return {
        "title": title,
        "image_urls": image_urls,
        "description_html": description_html,
    }


def extract_product_data(url: str, doc: html.HtmlElement) -> Dict[str, Any]:
    """
    Dispatch to the correct extractor based on which site the URL is from.
    """
    if is_argos(url):
        return extract_argos_data(doc)
    if is_very(url):
        return extract_very_data(doc)

    # Fallback: currently we only support Argos and Very.
    raise ValueError(f"Unsupported site for URL: {url}")


def read_urls_from_csv(path: Path) -> List[str]:
    urls: List[str] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_url = (row.get("url") or "").strip()
            if not raw_url:
                continue
            urls.append(normalize_url(raw_url))
    return urls


def load_template() -> Dict[str, Any]:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template JSON not found at {TEMPLATE_PATH}")
    with TEMPLATE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def build_product_from_template(
    template: Dict[str, Any], scraped: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Take the full template structure and only replace:
    - product_title
    - page_title
    - images
    - description.main_text (and remove key_features, specifications, note)
    """
    result = copy.deepcopy(template)
    title = scraped.get("title", "") or ""
    images = scraped.get("image_urls", []) or []
    description_html = scraped.get("description_html", "") or ""

    result["product_title"] = title
    result["page_title"] = title
    result["images"] = images

    if isinstance(result.get("description"), dict):
        # Replace main_text with scraped content
        result["description"]["main_text"] = description_html
        # Remove the template placeholder fields we don't want
        result["description"].pop("key_features", None)
        result["description"].pop("specifications", None)
        result["description"].pop("note", None)

    return result


def main() -> None:
    if not URL_CSV_PATH.exists():
        print(f"CSV file not found at {URL_CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    urls = read_urls_from_csv(URL_CSV_PATH)
    if not urls:
        print("No URLs found in url.csv", file=sys.stderr)
        sys.exit(1)

    try:
        template = load_template()
    except Exception as e:
        print(f"Failed to load product-template.json: {e}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []

    for idx, url in enumerate(urls, start=1):
        print(f"Scraping {url} ...")
        try:
            # Use Selenium for Very (to avoid 403), plain requests for Argos.
            if is_very(url):
                doc = fetch_page_with_selenium(url)
            else:
                doc = fetch_page(url)

            scraped = extract_product_data(url, doc)
            scraped["url"] = url
            results.append(scraped)

            product_json = build_product_from_template(template, scraped)
            out_file = OUTPUT_DIR / f"product_{idx}.json"
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(product_json, f, ensure_ascii=False, indent=4)
            print(f"  -> wrote {out_file.name}")
        except Exception as e:
            print(f"Failed to scrape {url}: {e}", file=sys.stderr)

    # Optional: keep CSV summary for quick debugging
    out_path = BASE_DIR / "argos_products.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["url", "title", "image_urls", "description_html"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "image_urls": "|".join(r.get("image_urls", [])),
                    "description_html": r.get("description_html", ""),
                }
            )

    print(
        f"Done. Wrote {len(results)} product JSON file(s) to {OUTPUT_DIR} "
        f"and CSV summary to {out_path}"
    )


if __name__ == "__main__":
    main()

