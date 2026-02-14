"""
Combined Product Scraper for Argos and Very.co.uk
Reads URLs from url.csv and saves individual product JSON files like argos_scraper.py
"""

import copy
import csv
import json
import sys
import time
import random
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse

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


def is_cheapfurniturewarehouse(url: str) -> bool:
    """Check if URL is from cheapfurniturewarehouse.co.uk"""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return "cheapfurniturewarehouse.co.uk" in hostname


# ─── ARGOS SCRAPER ────────────────────────────────────────────────────────────

def scrape_argos_product(driver, url: str) -> Dict[str, Any]:
    """Scrape product data from Argos using Selenium with slider navigation"""
    print(f"\n🔍 Scraping Argos: {url}")
    wait = WebDriverWait(driver, 20)
    result = {"url": url, "title": "", "image_urls": [], "description_html": ""}

    try:
        driver.get(url)
        
        # Wait for page to load
        wait.until(EC.presence_of_element_located((By.ID, "content")))
        time.sleep(2)  # Extra buffer for JS-rendered content

        # ── Title ──────────────────────────────────────────────────────────────
        try:
            title_el = driver.find_element(
                By.XPATH,
                '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[2]/section/section[1]/div[2]/h1/span'
            )
            result["title"] = title_el.text.strip()
            print(f"  ✅ Title: {result['title']}")
        except Exception as e:
            print(f"  ⚠️  Title: not found ({e})")
            result["title"] = ""

        # ── Images and Videos from Slider ────────────────────────────────────────
        image_urls = []
        video_urls = []
        
        try:
            # Find the slider container
            slider_container = driver.find_element(
                By.XPATH,
                '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[1]/section/section/div/div/div/div[2]/div[1]/div[1]/div[1]'
            )
            
            # Find the next button to navigate through slider
            next_button_xpath = '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[1]/section/section/div/div/div/div[2]/div[1]/div[1]/div[2]/button[2]'
            
            seen_urls = set()
            seen_video_urls = set()
            
            # Function to collect all images and videos from container
            def collect_media(container):
                collected_images = 0
                collected_videos = 0
                
                # Collect all images (including hidden ones)
                all_images = container.find_elements(By.XPATH, './/picture/img | .//img')
                for img in all_images:
                    src = img.get_attribute("src") or img.get_attribute("data-src") or img.get_attribute("data-main-image-url") or img.get_attribute("data-lazy-src")
                    if src:
                        if src.startswith("//"):
                            src = "https:" + src
                        if src not in seen_urls and "media.4rgos.it" in src:
                            image_urls.append(src)
                            seen_urls.add(src)
                            collected_images += 1
                
                # Collect all video sources
                video_elements = container.find_elements(By.XPATH, './/video | .//source | .//*[@data-video-url]')
                for video in video_elements:
                    video_src = (
                        video.get_attribute("src") or 
                        video.get_attribute("data-src") or 
                        video.get_attribute("data-video-url") or
                        video.get_attribute("data-video")
                    )
                    
                    if not video_src and video.tag_name == "source":
                        video_src = video.get_attribute("src")
                    
                    if video_src:
                        if video_src.startswith("//"):
                            video_src = "https:" + video_src
                        if video_src not in seen_video_urls:
                            video_urls.append(video_src)
                            seen_video_urls.add(video_src)
                            collected_videos += 1
                
                return collected_images, collected_videos
            
            # Initial collection
            img_count, vid_count = collect_media(slider_container)
            print(f"  Initial: {img_count} images, {vid_count} videos")
            
            # Navigate through slider
            try:
                next_button = driver.find_element(By.XPATH, next_button_xpath)
                max_clicks = 30
                click_count = 0
                consecutive_no_new = 0
                
                while click_count < max_clicks:
                    try:
                        if not next_button.is_enabled() or not next_button.is_displayed():
                            break
                    except:
                        break
                    
                    # Click the next button
                    driver.execute_script("arguments[0].click();", next_button)
                    click_count += 1
                    
                    # Wait for content to load
                    time.sleep(random.uniform(1.0, 2.0))
                    
                    # Re-find slider container
                    try:
                        slider_container = driver.find_element(
                            By.XPATH,
                            '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[1]/section/section/div/div/div/div[2]/div[1]/div[1]/div[1]'
                        )
                    except:
                        break
                    
                    # Collect new media
                    img_count, vid_count = collect_media(slider_container)
                    
                    if img_count == 0 and vid_count == 0:
                        consecutive_no_new += 1
                        if consecutive_no_new >= 2:
                            break
                    else:
                        consecutive_no_new = 0
                    
                    # Try to find next button again
                    try:
                        next_button = driver.find_element(By.XPATH, next_button_xpath)
                    except:
                        break
                        
            except Exception as btn_error:
                print(f"  ⚠️  Could not navigate slider: {btn_error}")
            
            # Final comprehensive collection using JavaScript
            try:
                slider_container = driver.find_element(
                    By.XPATH,
                    '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[1]/section/section/div/div/div/div[2]/div[1]/div[1]/div[1]'
                )
                
                # Use JavaScript to find ALL images and videos
                all_media_js = """
                var container = arguments[0];
                var results = {images: [], videos: []};
                
                var imgs = container.querySelectorAll('img, picture img');
                imgs.forEach(function(img) {
                    var src = img.src || img.getAttribute('data-src') || img.getAttribute('data-main-image-url') || img.getAttribute('data-lazy-src');
                    if (src && src.includes('media.4rgos.it')) {
                        results.images.push(src);
                    }
                });
                
                var videos = container.querySelectorAll('video, source[src*="media.4rgos.it"], [data-video-url], [data-video]');
                videos.forEach(function(video) {
                    var src = video.src || video.getAttribute('data-video-url') || video.getAttribute('data-video');
                    if (src) {
                        results.videos.push(src);
                    }
                });
                
                return results;
                """
                
                media_results = driver.execute_script(all_media_js, slider_container)
                
                for img_url in media_results.get('images', []):
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    if img_url not in seen_urls:
                        image_urls.append(img_url)
                        seen_urls.add(img_url)
                
                for vid_url in media_results.get('videos', []):
                    if vid_url.startswith("//"):
                        vid_url = "https:" + vid_url
                    if vid_url not in seen_video_urls:
                        video_urls.append(vid_url)
                        seen_video_urls.add(vid_url)
                        
            except Exception as e:
                print(f"  ⚠️  Error in final collection: {e}")
            
            # Combine images and videos (videos can be added to image_urls if needed, or kept separate)
            result["image_urls"] = list(dict.fromkeys(image_urls))  # Remove duplicates, preserve order
            if video_urls:
                # Optionally add videos to image_urls or keep separate
                result["video_urls"] = list(dict.fromkeys(video_urls))
            
            print(f"  ✅ Images: {len(result['image_urls'])}")
            if video_urls:
                print(f"  ✅ Videos: {len(video_urls)}")
                
        except Exception as e:
            print(f"  ⚠️  Images/Videos: error - {e}")
            result["image_urls"] = []

        # ── Description HTML ────────────────────────────────────────────────────
        try:
            desc_el = driver.find_element(By.XPATH, '//*[@id="pdp-description"]/div')
            result["description_html"] = desc_el.get_attribute("outerHTML")
            print(f"  ✅ Description: {len(result['description_html'])} chars")
        except Exception as e:
            print(f"  ⚠️  Description: not found ({e})")
            result["description_html"] = ""

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()

    return result


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

        # ── Product Description (using logic from argos_cluade.py) ────────────────
        description = None
        description_html = ""

        # Strategy 1: Exact XPath confirmed from browser DevTools
        try:
            desc_el = driver.find_element(
                By.XPATH,
                '//*[@id="product-page-container"]/div[1]/div[3]/div[1]/div/div/div'
            )
            description = desc_el.text.strip()
            # Try to get HTML first
            description_html = desc_el.get_attribute("outerHTML") or driver.execute_script("return arguments[0].innerHTML;", desc_el)
        except:
            pass

        # Strategy 2: CSS equivalent with extra nested div (confirmed selector)
        if not description:
            try:
                desc_el = driver.find_element(
                    By.CSS_SELECTOR,
                    "#product-page-container div[class*='grid-container'] > div:nth-child(3) > div:nth-child(1) > div > div > div"
                )
                description = desc_el.text.strip()
                description_html = desc_el.get_attribute("outerHTML") or driver.execute_script("return arguments[0].innerHTML;", desc_el)
            except:
                pass

        # Strategy 3: Find by h2 "Product description" heading → grab sibling content
        if not description:
            try:
                desc_heading = driver.find_element(
                    By.XPATH,
                    "//h2[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'product description')]"
                )
                section = desc_heading.find_element(By.XPATH, "./..")
                description = section.text.strip()
                description_html = section.get_attribute("outerHTML") or driver.execute_script("return arguments[0].innerHTML;", section)
            except:
                pass

        # Strategy 4: Fallback — grab all bullet points from product-detail
        if not description:
            try:
                detail_section = driver.find_element(By.ID, "product-detail")
                bullets = detail_section.find_elements(By.CSS_SELECTOR, "ul li")
                if bullets:
                    description = "\n".join([b.text.strip() for b in bullets if b.text.strip()])
                    if description:
                        description_html = f"<div class=\"product-description-content-text\"><ul>{''.join([f'<li>{b.text.strip()}</li>' for b in bullets if b.text.strip()])}</ul></div>"
            except:
                pass

        # Convert text to HTML if we have text but no HTML
        if description and not description_html:
            description_html = f"<div class=\"product-description-content-text\"><p>{description.replace(chr(10), '</p><p>')}</p></div>"
        elif not description and description_html:
            # If we have HTML but no text, extract text from HTML
            try:
                if 'desc_el' in locals():
                    description = driver.execute_script("return arguments[0].textContent || arguments[0].innerText;", desc_el)
            except:
                pass

        if description or description_html:
            print(f"  ✅ Description: {len(description or description_html)} chars")
        else:
            print("  ⚠️  Description: not found")

        return {
            "title": data.get("title", ""),
            "image_urls": image_urls,
            "description_html": description_html or "",
        }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {
            "title": "",
            "image_urls": [],
            "description_html": "",
        }


# ─── CHEAPFURNITUREWAREHOUSE.CO.UK SCRAPER ────────────────────────────────────────

def scrape_cheapfurniturewarehouse_product(driver, url: str) -> Dict[str, Any]:
    """Scrape product data from cheapfurniturewarehouse.co.uk"""
    print(f"\n🔍 Scraping CheapFurnitureWarehouse: {url}")
    wait = WebDriverWait(driver, 20)
    result = {"url": url, "title": "", "image_urls": [], "description_html": ""}

    try:
        driver.get(url)
        
        # Wait for page to load
        time.sleep(3)  # Wait for JS to render

        # ── Title ──────────────────────────────────────────────────────────────
        try:
            title_el = driver.find_element(
                By.XPATH,
                '//*[@id="ProductInfo-template--25585833705806__main-product"]/div/div[1]/div/h1'
            )
            result["title"] = title_el.text.strip()
            print(f"  ✅ Title: {result['title']}")
        except Exception as e:
            print(f"  ⚠️  Title: not found ({e})")
            result["title"] = ""

        # ── Description ────────────────────────────────────────────────────────
        description_html = ""
        try:
            desc_el = driver.find_element(
                By.XPATH,
                '//*[@id="ProductInfo-template--25585833705806__main-product"]/div/div[3]'
            )
            # Get HTML content
            description_html = desc_el.get_attribute("outerHTML") or driver.execute_script("return arguments[0].innerHTML;", desc_el)
            if not description_html:
                # Fallback to text
                desc_text = desc_el.text.strip()
                if desc_text:
                    description_html = f"<div class=\"product-description-content-text\"><p>{desc_text.replace(chr(10), '</p><p>')}</p></div>"
        except Exception as e:
            pass

        # ── Specifications table (ProductAccordion-specifications_tab_.../table) ──
        # Try to expand the specifications accordion first (table may be in collapsed section)
        try:
            specs_accordion = driver.find_element(
                By.XPATH,
                '//*[contains(@id,"ProductAccordion-specifications_tab") and contains(@id,"template--25585833705806__main-product")]'
            )
            driver.execute_script("arguments[0].click();", specs_accordion)
            time.sleep(1)
        except Exception:
            pass
        try:
            specs_table = driver.find_element(
                By.XPATH,
                '//*[contains(@id,"ProductAccordion-specifications_tab") and contains(@id,"template--25585833705806__main-product")]/table'
            )
            specs_html = specs_table.get_attribute("outerHTML")
            if specs_html:
                description_html = (description_html or "") + '<div class="product-specifications"><h3>Specifications</h3>' + specs_html + '</div>'
                print(f"  ✅ Specifications table: added")
        except Exception:
            try:
                specs_table = driver.find_element(
                    By.CSS_SELECTOR,
                    '[id*="ProductAccordion-specifications_tab"][id*="main-product"] table'
                )
                specs_html = specs_table.get_attribute("outerHTML")
                if specs_html:
                    description_html = (description_html or "") + '<div class="product-specifications"><h3>Specifications</h3>' + specs_html + '</div>'
                    print(f"  ✅ Specifications table: added")
            except Exception:
                pass

        if description_html:
            result["description_html"] = description_html
            print(f"  ✅ Description: {len(description_html)} chars")
        else:
            result["description_html"] = ""
            print(f"  ⚠️  Description: not found")

        # ── Images ────────────────────────────────────────────────────────────
        image_urls = []
        seen_urls = set()
        
        try:
            # Get all thumbnails by using 'contains' on dynamic IDs
            thumbs = driver.find_elements(
                By.XPATH, '//div[contains(@id,"Media-Thumbnails-template")]//img'
            )
            
            for img in thumbs:
                src = img.get_attribute("src")
                if src:
                    if src.startswith("//"):
                        src = "https:" + src
                    # Clean URL by removing query parameters
                    clean_src = src.split("?")[0]
                    if clean_src not in seen_urls:
                        image_urls.append(clean_src)
                        seen_urls.add(clean_src)
            
            # Also try main featured image(s) in the slider
            main_imgs = driver.find_elements(
                By.XPATH, '//div[contains(@id,"Slide-template")]//img'
            )
            
            for img in main_imgs:
                src = img.get_attribute("src")
                if src:
                    if src.startswith("//"):
                        src = "https:" + src
                    # Clean URL by removing query parameters
                    clean_src = src.split("?")[0]
                    if clean_src not in seen_urls:
                        image_urls.append(clean_src)
                        seen_urls.add(clean_src)
            
            result["image_urls"] = image_urls
            print(f"  ✅ Images found: {len(image_urls)}")
        except Exception as e:
            print(f"  ⚠️  Images: error - {e}")
            result["image_urls"] = []

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()

    return result


# ─── MAIN SCRAPING LOGIC ──────────────────────────────────────────────────────

def scrape_product(url: str, driver=None) -> Dict[str, Any]:
    """Scrape product from URL, auto-detecting site"""
    url = normalize_url(url)
    result = {"url": url, "title": "", "image_urls": [], "description_html": ""}

    if is_argos(url):
        if driver is None:
            driver = get_driver(headless=True)
            try:
                scraped = scrape_argos_product(driver, url)
                result.update(scraped)
            finally:
                driver.quit()
        else:
            scraped = scrape_argos_product(driver, url)
            result.update(scraped)

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

    elif is_cheapfurniturewarehouse(url):
        if driver is None:
            driver = get_driver(headless=True)
            try:
                scraped = scrape_cheapfurniturewarehouse_product(driver, url)
                result.update(scraped)
            finally:
                driver.quit()
        else:
            scraped = scrape_cheapfurniturewarehouse_product(driver, url)
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

    print("🚀 Starting Combined Scraper...")
    print(f"   URLs to scrape: {len(urls)}\n")

    results: List[Dict[str, Any]] = []
    
    # Use a single driver for all sites that need Selenium (more efficient)
    driver = None
    has_very_urls = any(is_very(url) for url in urls)
    has_argos_urls = any(is_argos(url) for url in urls)
    has_cfw_urls = any(is_cheapfurniturewarehouse(url) for url in urls)

    try:
        # Initialize driver if we have URLs that need Selenium
        if has_argos_urls or has_very_urls or has_cfw_urls:
            driver = get_driver(headless=True)

        # Process all URLs in order
        for idx, url in enumerate(urls, start=1):
            print(f"Scraping {url} ...")
            try:
                # Use driver for both Argos and Very.co.uk
                result = scrape_product(url, driver=driver)
                
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
                elif is_argos(url):
                    time.sleep(random.uniform(2, 4))  # Longer delay for Argos due to slider navigation
                elif is_cheapfurniturewarehouse(url):
                    time.sleep(random.uniform(2, 3))
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