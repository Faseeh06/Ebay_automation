"""
Combined Product Scraper for Argos and Very.co.uk
Reads URLs from url.csv and saves individual product JSON files like argos_scraper.py
"""

import copy
import csv
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse

import requests
from lxml import html
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# ─── CONFIG ───────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
URL_CSV_PATH = BASE_DIR / "url.csv"
TEMPLATE_PATH = BASE_DIR / "product-template.json"
OUTPUT_DIR = BASE_DIR / "products"

# ─── DRIVER SETUP ─────────────────────────────────────────────────────────────

def get_driver(headless=True):
    """Create and configure Chrome WebDriver"""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Try webdriver-manager first, fall back to system chromedriver
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    except Exception:
        driver = webdriver.Chrome(options=options)

    return driver


# ─── URL HELPERS ──────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Normalize URL format"""
    url = url.strip()
    if not url:
        return url

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("http://") or url.startswith("https://"):
        return url

    # Handle bare domain URLs
    if url.startswith("argos.co.uk"):
        return "https://www." + url
    if url.startswith("very.co.uk"):
        return "https://www." + url

    return url


def is_argos(url: str) -> bool:
    """Check if URL is from Argos"""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return "argos.co.uk" in hostname


def is_very(url: str) -> bool:
    """Check if URL is from Very.co.uk"""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return "very.co.uk" in hostname


# ─── ARGOS SCRAPER ────────────────────────────────────────────────────────────

def fetch_page(url: str) -> html.HtmlElement:
    """Fetch page using requests (for Argos)"""
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


def extract_argos_data(doc: html.HtmlElement) -> Dict[str, Any]:
    """Extract product data from Argos page"""
    # Title
    title_nodes = doc.xpath(
        '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[2]/section/section[1]/div[2]/h1/span'
    )
    title = title_nodes[0].text_content().strip() if title_nodes else ""

    # Extract all images directly using the specific XPath
    img_nodes = doc.xpath(
        '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[1]/section/section/div/div/div/div[2]/div[1]/div[1]/div[1]/div[1]/div/picture/img'
    )
    image_urls: List[str] = []
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


# ─── VERY.CO.UK SCRAPER ───────────────────────────────────────────────────────

def scrape_very_product(driver, url: str) -> Dict[str, Any]:
    """Scrape product data from Very.co.uk"""
    print(f"\n🔍 Scraping Very.co.uk: {url}")
    wait = WebDriverWait(driver, 20)
    data = {"url": url}

    try:
        driver.get(url)

        # Wait for the main product container to appear
        wait.until(EC.presence_of_element_located((By.ID, "product-detail")))
        time.sleep(2)  # Extra buffer for JS-rendered content

        # ── Title ──────────────────────────────────────────────────────────────
        try:
            title_el = driver.find_element(
                By.CSS_SELECTOR, "#product-detail > h1 > span[class*='Title']"
            )
            data["title"] = title_el.text.strip()
            print(f"  ✅ Title: {data['title']}")
        except Exception:
            # Fallback: any h1 in product-detail
            try:
                data["title"] = driver.find_element(
                    By.CSS_SELECTOR, "#product-detail h1"
                ).text.strip()
            except:
                data["title"] = ""
            print(f"  ⚠️  Title fallback: {data['title']}")

        # ── Images from Splide carousel ────────────────────────────────────────
        image_urls = []
        try:
            wait.until(EC.presence_of_element_located((By.ID, "splide01-list")))
            slides = driver.find_elements(By.CSS_SELECTOR, "#splide01-list li img")
            seen = set()
            for img in slides:
                src = (
                    img.get_attribute("src")
                    or img.get_attribute("data-src")
                    or img.get_attribute("data-splide-lazy")
                )
                if src and src not in seen:
                    seen.add(src)
                    image_urls.append(src)
            print(f"  ✅ Images found: {len(image_urls)}")
        except:
            print("  ⚠️  Images: carousel not found")

        # ── Info Block (description) ────────────────────────────────────────────
        description_html = ""
        try:
            info_el = driver.find_element(
                By.CSS_SELECTOR,
                "#product-page-container div[class*='grid-container'] > div:nth-child(3) > div:nth-child(1) > div > div"
            )
            info_text = info_el.text.strip()
            # Convert plain text to HTML paragraph
            if info_text:
                description_html = f"<div class=\"product-description-content-text\"><p>{info_text.replace(chr(10), '</p><p>')}</p></div>"
            print(f"  ✅ Description: {len(description_html)} chars")
        except:
            print("  ⚠️  Description: not found")

        return {
            "title": data.get("title", ""),
            "image_urls": image_urls,
            "description_html": description_html,
        }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {
            "title": "",
            "image_urls": [],
            "description_html": "",
        }


# ─── MAIN SCRAPING LOGIC ──────────────────────────────────────────────────────

def scrape_product(url: str, driver=None) -> Dict[str, Any]:
    """Scrape product from URL, auto-detecting site"""
    url = normalize_url(url)
    result = {"url": url, "title": "", "image_urls": [], "description_html": ""}

    if is_argos(url):
        print(f"\n🔍 Scraping Argos: {url}")
        try:
            doc = fetch_page(url)
            scraped = extract_argos_data(doc)
            result.update(scraped)
            print(f"  ✅ Title: {result['title']}")
            print(f"  ✅ Images: {len(result['image_urls'])}")
            print(f"  ✅ Description: {len(result['description_html'])} chars")
        except Exception as e:
            print(f"  ❌ Error scraping Argos: {e}")
            result["error"] = str(e)

    elif is_very(url):
        if driver is None:
            driver = get_driver(headless=True)
            try:
                scraped = scrape_very_product(driver, url)
                result.update(scraped)
            finally:
                driver.quit()
        else:
            scraped = scrape_very_product(driver, url)
            result.update(scraped)

    else:
        print(f"  ⚠️  Unsupported site: {url}")
        result["error"] = "Unsupported site"

    return result


# ─── CSV READING ──────────────────────────────────────────────────────────────

def read_urls_from_csv(path: Path) -> List[str]:
    """Read URLs from CSV file"""
    urls: List[str] = []
    if not path.exists():
        print(f"CSV file not found at {path}")
        return urls

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_url = (row.get("url") or "").strip()
            if not raw_url:
                continue
            urls.append(normalize_url(raw_url))

    return urls


# ─── TEMPLATE HANDLING ────────────────────────────────────────────────────────

def load_template() -> Dict[str, Any]:
    """Load the product template JSON"""
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


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
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

    print("🚀 Starting Combined Scraper (Argos + Very.co.uk)...")
    print(f"   URLs to scrape: {len(urls)}\n")

    results: List[Dict[str, Any]] = []
    
    # Use a single driver for Very.co.uk URLs (more efficient)
    driver = None
    has_very_urls = any(is_very(url) for url in urls)

    try:
        # Initialize driver if we have Very.co.uk URLs
        if has_very_urls:
            driver = get_driver(headless=True)

        # Process all URLs in order
        for idx, url in enumerate(urls, start=1):
            print(f"Scraping {url} ...")
            try:
                # Use driver for Very.co.uk, None for Argos
                if is_very(url):
                    result = scrape_product(url, driver=driver)
                else:
                    result = scrape_product(url)
                
                result["url"] = url
                results.append(result)

                product_json = build_product_from_template(template, result)
                out_file = OUTPUT_DIR / f"product_{idx}.json"
                with out_file.open("w", encoding="utf-8") as f:
                    json.dump(product_json, f, ensure_ascii=False, indent=4)
                print(f"  -> wrote {out_file.name}")
                
                # Polite delay between requests
                if is_very(url):
                    time.sleep(2)
                else:
                    time.sleep(1)
            except Exception as e:
                print(f"Failed to scrape {url}: {e}", file=sys.stderr)

    finally:
        if driver:
            driver.quit()
            print("\n🛑 Browser closed.")

    # Save CSV summary for quick debugging (same format as argos_scraper.py)
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
        f"\nDone. Wrote {len(results)} product JSON file(s) to {OUTPUT_DIR} "
        f"and CSV summary to {out_path}"
    )


if __name__ == "__main__":
    main()
