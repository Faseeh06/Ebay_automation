"""
Very.co.uk Product Scraper
Scrapes: title, price, images, product info block
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import json
import time
import csv
import os

# ─── CONFIG ───────────────────────────────────────────────────────────────────

URLS = [
    "https://www.very.co.uk/the-very-collection-boys-2-pack-swim-shorts-multi/1601201388.prd",
    "https://www.very.co.uk/the-very-collection-boys-cargo-swim-shorts-blue/1601213067.prd",
    "https://www.very.co.uk/the-very-collection-compact-knitted-mini-skirt-co-ord-burgundy-red/1601196456.prd",
]

OUTPUT_JSON = "very_products.json"
OUTPUT_CSV  = "very_products.csv"

# ─── DRIVER SETUP ─────────────────────────────────────────────────────────────

def get_driver(headless=True):
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


# ─── SCRAPE ONE PRODUCT ────────────────────────────────────────────────────────

def scrape_product(driver, url):
    print(f"\n🔍 Scraping: {url}")
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
        except Exception as e:
            # Fallback: any h1 in product-detail
            try:
                data["title"] = driver.find_element(
                    By.CSS_SELECTOR, "#product-detail h1"
                ).text.strip()
            except:
                data["title"] = None
            print(f"  ⚠️  Title fallback: {data['title']}")

        # ── Price ──────────────────────────────────────────────────────────────
        try:
            price_el = driver.find_element(
                By.CSS_SELECTOR, "[class*='Price'], [class*='price'], .price"
            )
            data["price"] = price_el.text.strip()
            print(f"  ✅ Price: {data['price']}")
        except:
            data["price"] = None
            print("  ⚠️  Price: not found")

        # ── Info Block (div:nth-child(3) section) ──────────────────────────────
        try:
            info_el = driver.find_element(
                By.CSS_SELECTOR,
                "#product-page-container div[class*='grid-container'] > div:nth-child(3) > div:nth-child(1) > div > div"
            )
            data["info_block"] = info_el.text.strip()
            print(f"  ✅ Info block: {len(data['info_block'])} chars")
        except:
            data["info_block"] = None
            print("  ⚠️  Info block: not found")

        # ── Images from Splide carousel ────────────────────────────────────────
        try:
            wait.until(EC.presence_of_element_located((By.ID, "splide01-list")))
            slides = driver.find_elements(By.CSS_SELECTOR, "#splide01-list li img")
            images = []
            seen = set()
            for img in slides:
                src = (
                    img.get_attribute("src")
                    or img.get_attribute("data-src")
                    or img.get_attribute("data-splide-lazy")
                )
                alt = img.get_attribute("alt") or ""
                if src and src not in seen:
                    seen.add(src)
                    images.append({"src": src, "alt": alt})
            data["images"] = images
            print(f"  ✅ Images found: {len(images)}")
        except:
            data["images"] = []
            print("  ⚠️  Images: carousel not found")

        # ── Product ID from URL ────────────────────────────────────────────────
        try:
            data["product_id"] = url.split("/")[-1].replace(".prd", "")
        except:
            data["product_id"] = None

        data["status"] = "success"

    except Exception as e:
        data["status"] = "error"
        data["error"] = str(e)
        print(f"  ❌ Error: {e}")

    return data


# ─── SAVE RESULTS ─────────────────────────────────────────────────────────────

def save_json(results, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 JSON saved → {path}")


def save_csv(results, path):
    if not results:
        return
    fieldnames = ["product_id", "title", "price", "info_block", "url", "status"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            # Flatten images to a count for CSV
            r_flat = {**r, "images": len(r.get("images", []))}
            writer.writerow(r_flat)
    print(f"💾 CSV saved  → {path}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("🚀 Starting Very.co.uk scraper...")
    print(f"   URLs to scrape: {len(URLS)}\n")

    driver = get_driver(headless=True)
    results = []

    try:
        for url in URLS:
            product = scrape_product(driver, url)
            results.append(product)
            time.sleep(2)  # Polite delay between requests
    finally:
        driver.quit()
        print("\n🛑 Browser closed.")

    save_json(results, OUTPUT_JSON)
    save_csv(results, OUTPUT_CSV)

    # Print summary
    print("\n── Summary ──────────────────────────────")
    for r in results:
        status = "✅" if r["status"] == "success" else "❌"
        print(f"  {status} [{r.get('product_id')}] {r.get('title', 'N/A')}")
    print("─────────────────────────────────────────")


if __name__ == "__main__":
    main()