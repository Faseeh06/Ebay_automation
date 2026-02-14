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

# Handle PyInstaller bundle (when running as .exe)
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    # PyInstaller sets _MEIPASS to the temp folder where data files are extracted
    if hasattr(sys, '_MEIPASS'):
        # Data files are in the temp folder, but user files should be next to .exe
        BASE_DIR = Path(sys.executable).parent
        # Template might be in temp folder or next to exe - try both
        TEMPLATE_PATH_TEMP = Path(sys._MEIPASS) / "product-template.json"
        TEMPLATE_PATH = BASE_DIR / "product-template.json"
        # Use temp folder template if it exists, otherwise use exe folder
        if TEMPLATE_PATH_TEMP.exists():
            TEMPLATE_PATH = TEMPLATE_PATH_TEMP
    else:
        BASE_DIR = Path(sys.executable).parent
        TEMPLATE_PATH = BASE_DIR / "product-template.json"
else:
    # Running as script
    BASE_DIR = Path(__file__).resolve().parent
    TEMPLATE_PATH = BASE_DIR / "product-template.json"

# User files are always in the executable's directory (or script's directory)
URL_CSV_PATH = BASE_DIR / "url.csv"
OUTPUT_DIR = BASE_DIR / "products"
OUTPUT_HTML_DIR = BASE_DIR / "html"

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
    # Additional stability options
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")  # Suppress Chrome logs
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

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
    """Scrape product data from Very.co.uk (logic aligned with argos_cluade.py)"""
    print(f"\n🔍 Scraping Very.co.uk: {url}")
    wait = WebDriverWait(driver, 25)
    data = {"url": url}
    result = {"url": url, "title": "", "image_urls": [], "description_html": ""}

    try:
        driver.get(url)

        # Wait for the main product container (same as argos_cluade.py)
        wait.until(EC.presence_of_element_located((By.ID, "product-detail")))
        time.sleep(4)  # Extra buffer — description grid renders after initial load (argos_cluade.py)

        # ── Title ──────────────────────────────────────────────────────────────
        try:
            title_el = driver.find_element(
                By.CSS_SELECTOR, "#product-detail > h1 > span[class*='Title']"
            )
            data["title"] = title_el.text.strip()
            result["title"] = data["title"]
            print(f"  ✅ Title: {data['title']}")
        except Exception:
            try:
                title_el = driver.find_element(By.CSS_SELECTOR, "#product-detail h1")
                data["title"] = title_el.text.strip()
                result["title"] = data["title"]
                print(f"  ✅ Title (fallback): {data['title']}")
            except Exception:
                try:
                    # Fallback: any visible h1 on page (Very sometimes loads structure late)
                    title_el = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h1")))
                    data["title"] = title_el.text.strip()
                    result["title"] = data["title"]
                    print(f"  ✅ Title (h1): {data['title']}")
                except Exception:
                    try:
                        # Fallback: page title often has product name on Very
                        page_title = driver.execute_script("return document.title || '';")
                        if page_title and "very" not in page_title.lower() and len(page_title) > 3:
                            # Strip common suffixes like " | Very.co.uk"
                            data["title"] = page_title.split("|")[0].strip()
                            result["title"] = data["title"]
                            print(f"  ✅ Title (from page title): {data['title']}")
                        else:
                            data["title"] = ""
                            result["title"] = ""
                            print(f"  ⚠️  Title: not found")
                    except Exception:
                        data["title"] = ""
                        result["title"] = ""
                        print(f"  ⚠️  Title: not found")

        # ── Images from Splide carousel ────────────────────────────────────────
        image_urls = []
        try:
            # Try to wait for carousel, but don't fail if it doesn't appear
            try:
                wait.until(EC.presence_of_element_located((By.ID, "splide01-list")))
            except:
                # Try alternative selectors
                time.sleep(2)  # Give more time
            
            # Try multiple selectors for images
            slides = []
            try:
                slides = driver.find_elements(By.CSS_SELECTOR, "#splide01-list li img")
            except:
                pass
            
            if not slides:
                # Fallback: try other image containers
                try:
                    slides = driver.find_elements(By.CSS_SELECTOR, ".product-images img, [class*='image'] img")
                except:
                    pass
            
            seen = set()
            for img in slides:
                try:
                    src = (
                        img.get_attribute("src")
                        or img.get_attribute("data-src")
                        or img.get_attribute("data-splide-lazy")
                    )
                    if src and src not in seen:
                        seen.add(src)
                        image_urls.append(src)
                except:
                    continue
            
            result["image_urls"] = image_urls
            if image_urls:
                print(f"  ✅ Images found: {len(image_urls)}")
            else:
                print("  ⚠️  Images: not found")
        except Exception as img_error:
            print(f"  ⚠️  Images: error - {img_error}")
            result["image_urls"] = []

        # ── Product Description (logic from working.py) ─────────────────────────────
        description = None
        description_html = ""

        def _is_recommendations_blob(html):
            """Avoid keeping recommendations widget markup instead of description."""
            if not html:
                return False
            return "recs2_pdp_1" in html or "data-stateid=\"recs2" in html

        # Strategy 0: Very's product description body (correct content: Size & Fit, Details, etc.)
        try:
            desc_el = driver.find_element(
                By.CSS_SELECTOR,
                '[data-testid="product_description_body"]'
            )
            description = desc_el.text.strip()
            description_html = desc_el.get_attribute("outerHTML") or driver.execute_script("return arguments[0].innerHTML;", desc_el)
            if _is_recommendations_blob(description_html):
                description, description_html = None, ""
        except Exception:
            pass

        # Strategy 1: Exact XPath confirmed from browser DevTools (may grab recommendations if layout changed)
        if not description:
            try:
                desc_el = driver.find_element(
                    By.XPATH,
                    '//*[@id="product-page-container"]/div[1]/div[3]/div[1]/div/div/div'
                )
                description = desc_el.text.strip()
                description_html = desc_el.get_attribute("outerHTML") or driver.execute_script("return arguments[0].innerHTML;", desc_el)
                if _is_recommendations_blob(description_html):
                    description, description_html = None, ""
            except Exception:
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
                if _is_recommendations_blob(description_html):
                    description, description_html = None, ""
            except Exception:
                pass

        # Strategy 3: Find by h2 "Product description" heading → grab sibling content (parent section)
        if not description:
            try:
                desc_heading = driver.find_element(
                    By.XPATH,
                    "//h2[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'product description')]"
                )
                section = desc_heading.find_element(By.XPATH, "./..")
                description = section.text.strip()
                description_html = section.get_attribute("outerHTML") or driver.execute_script("return arguments[0].innerHTML;", section)
            except Exception:
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
            except Exception:
                pass

        # Convert text to HTML if we have text but no HTML
        if description and not description_html:
            description_html = f"<div class=\"product-description-content-text\"><p>{description.replace(chr(10), '</p><p>')}</p></div>"
        elif not description and description_html:
            try:
                if 'desc_el' in locals():
                    description = driver.execute_script("return arguments[0].textContent || arguments[0].innerText;", desc_el)
            except Exception:
                pass

        if description or description_html:
            print(f"  ✅ Description: {len(description or description_html)} chars")
        else:
            print("  ⚠️  Description: not found")

        result["description_html"] = description_html or ""
        
        return result

    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        print(f"  ❌ Error ({error_type}): {error_msg}")
        
        # Check if this is a Chrome crash or driver issue
        if "chrome" in error_msg.lower() or "chromedriver" in error_msg.lower() or "session" in error_msg.lower():
            print("  ⚠️  Chrome driver may have crashed. Attempting recovery...")
        
        # Try to extract any data we might have gotten before the error
        try:
            # Check if driver is still responsive
            if driver:
                try:
                    # Test if driver is still alive
                    _ = driver.current_url
                    current_url = driver.current_url
                    if "very.co.uk" in current_url:
                        # Try to get title if page loaded
                        try:
                            title_el = driver.find_element(By.CSS_SELECTOR, "#product-detail h1, h1")
                            result["title"] = title_el.text.strip() if title_el else ""
                            if result["title"]:
                                print(f"  ✅ Recovered title: {result['title']}")
                        except:
                            pass
                        
                        # Try to get images if available
                        try:
                            slides = driver.find_elements(By.CSS_SELECTOR, "#splide01-list li img, img")
                            temp_images = []
                            for img in slides[:10]:  # Limit to avoid too many
                                try:
                                    src = img.get_attribute("src") or img.get_attribute("data-src")
                                    if src and src not in temp_images:
                                        temp_images.append(src)
                                except:
                                    continue
                            if temp_images:
                                result["image_urls"] = temp_images
                                print(f"  ✅ Recovered {len(temp_images)} images")
                        except:
                            pass
                except Exception as driver_check_error:
                    # Driver is not responsive
                    print(f"  ⚠️  Driver not responsive: {driver_check_error}")
                    pass
        except Exception as recovery_error:
            print(f"  ⚠️  Recovery attempt failed: {recovery_error}")
            pass
        
        # Return partial results if we have any, otherwise return empty
        if not result.get("title") and not result.get("image_urls"):
            result = {
                "title": "",
                "image_urls": [],
                "description_html": "",
            }
        
        return result


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
            description_html = desc_el.get_attribute("outerHTML") or driver.execute_script("return arguments[0].innerHTML;", desc_el)
            if not description_html:
                desc_text = desc_el.text.strip()
                if desc_text:
                    description_html = f"<div class=\"product-description-content-text\"><p>{desc_text.replace(chr(10), '</p><p>')}</p></div>"
        except Exception as e:
            pass

        # ── Specifications table (ProductAccordion-specifications_tab_.../table) ──
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
            except Exception as very_error:
                print(f"  ❌ Fatal error scraping Very.co.uk: {very_error}")
                result.update({
                    "title": "",
                    "image_urls": [],
                    "description_html": "",
                })
            finally:
                try:
                    driver.quit()
                except:
                    pass
        else:
            try:
                scraped = scrape_very_product(driver, url)
                result.update(scraped)
            except Exception as very_error:
                print(f"  ❌ Fatal error scraping Very.co.uk: {very_error}")
                result.update({
                    "title": "",
                    "image_urls": [],
                    "description_html": "",
                })

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
    # Try multiple possible locations
    possible_paths = [
        TEMPLATE_PATH,
        BASE_DIR / "product-template.json",
    ]
    
    # If running as executable, also check temp folder
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        possible_paths.insert(0, Path(sys._MEIPASS) / "product-template.json")
    
    for template_path in possible_paths:
        if template_path.exists():
            print(f"📄 Loading template from: {template_path}")
            with template_path.open(encoding="utf-8") as f:
                return json.load(f)
    
    # If none found, provide helpful error message
    error_msg = f"Template JSON not found. Checked:\n"
    for path in possible_paths:
        error_msg += f"  - {path}\n"
    error_msg += f"\nPlease ensure product-template.json is in the same folder as the executable."
    raise FileNotFoundError(error_msg)


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


# ─── HTML GENERATION ──────────────────────────────────────────────────────────

def load_json_file(json_file):
    """Load product data from JSON file"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File '{json_file}' not found!")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{json_file}': {e}")
        return None


def generate_images_html(images):
    """Generate image gallery HTML"""
    if len(images) == 0:
        return "", ""

    sentinel_html = f'<img src="{images[0]}" alt="" class="main-sentinel" />'
    
    images_html = ""
    for i, img_url in enumerate(images, 1):
        checked = ' checked' if i == 1 else ''
        images_html += f"""
                                <!-- IMAGE {i} -->
                                <div class="image">
                                    <input id="thumbnail-control-{i}" type="radio" name="thumbnails" class="thumbnails-control"{checked} />
                                    <label for="thumbnail-control-{i}" id="thumbnail-{i}" class="thumbnail">
                                        <img src="{img_url}" alt="Thumb {i}" />
                                    </label>
                                    <input id="image-control-{i}" type="checkbox" class="main-control">
                                    <label for="image-control-{i}" id="image-{i}" class="main transition">
                                        <img src="{img_url}" alt="Main Image {i}" />
                                    </label>
                                </div>
"""
    
    return sentinel_html, images_html


def generate_gallery_css(num_images):
    """Generate dynamic CSS for image positioning"""
    if num_images == 0:
        return "", "", 200, 200

    desktop_css = "            /* Desktop Positioning */\n"
    desktop_step = 120
    max_per_row_desktop = 5
    
    for i in range(num_images):
        row = i // max_per_row_desktop
        col = i % max_per_row_desktop
        left_pos = col * desktop_step
        bottom_pos = -150 - (row * 100)
        desktop_css += f"            .image:nth-of-type({i+1}) .thumbnail {{ left: {left_pos}px; bottom: {bottom_pos}px; }}\n"

    desktop_rows = (num_images - 1) // max_per_row_desktop
    desktop_margin_bottom = 200 + (desktop_rows * 100)

    mobile_css = "            /* Mobile Positioning */\n"
    mobile_step = 90
    max_per_row_mobile = 4
    
    for i in range(num_images):
        row = i // max_per_row_mobile
        col = i % max_per_row_mobile
        left_pos = col * mobile_step
        bottom_pos = -150 - (row * 90)
        mobile_css += f"            .image:nth-of-type({i+1}) .thumbnail {{ left: {left_pos}px; bottom: {bottom_pos}px; }}\n"
        
    mobile_rows = (num_images - 1) // max_per_row_mobile
    mobile_margin_bottom = 260 + (mobile_rows * 90)
    
    return desktop_css, desktop_margin_bottom, mobile_css, mobile_margin_bottom


def generate_condition_html(condition):
    """Generate condition box HTML"""
    details_html = ""
    for detail in condition['details']:
        details_html += f"                                    <li>{detail}</li>\n"
    return condition['title'], details_html


def generate_description_html(desc):
    """Return main description HTML only (scraped)."""
    return desc.get('main_text', '')


def generate_delivery_html(delivery):
    """Generate delivery section HTML"""
    items_html = ""
    for item in delivery['items']:
        label_html = f"<span class=\"delivery-label\">{item['label']}</span> " if item['label'] else ""
        items_html += f"                                            <div class=\"delivery-item\">{label_html}{item['value']}</div>\n"
    return items_html


def generate_returns_html(returns):
    """Generate returns section HTML"""
    details_html = ""
    for detail in returns['details']:
        details_html += f"                                        <li>{detail}</li>\n"
    return returns['title'], details_html


def generate_html_from_data(data):
    """Generate complete HTML from product data"""
    sentinel_img, images_html = generate_images_html(data['images'])
    condition_title, condition_details = generate_condition_html(data['condition'])
    desc_html = generate_description_html(data['description'])
    delivery_html = generate_delivery_html(data['delivery'])
    returns_title, returns_details = generate_returns_html(data['returns'])
    
    desktop_css, desktop_margin_bottom, mobile_css, mobile_margin_bottom = generate_gallery_css(len(data['images']))
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
<title>{data['page_title']}</title>

    <style>
        html, body {{ margin: 0; padding: 0; font-family: "Trebuchet MS", "Lucida Grande", sans-serif; background: #fff; color: #333; font-size: 14px; line-height: 1.5; -webkit-font-smoothing: antialiased; }}
        * {{ box-sizing: border-box; }}
        img {{ max-width: 100%; height: auto; display: block; }}
        a {{ color: #333; text-decoration: none; transition: all 0.2s ease; }}
        a:hover {{ color: {data['brand_color']}; }}
        p {{ margin: 0 0 15px; }}
        ul {{ list-style: none; padding: 0; margin: 0; }}
        h1, h2, h3 {{ font-weight: 700; color: {data['brand_color']}; margin-top: 0; margin-bottom: 15px; }}
        .container {{ padding-right: 15px; padding-left: 15px; margin-right: auto; margin-left: auto; max-width: 1200px; }}
        .row {{ margin-right: -15px; margin-left: -15px; display: flex; flex-wrap: wrap; }}
        .col-xs-12, .col-md-8, .col-md-4, .col-lg-8, .col-lg-6 {{ position: relative; width: 100%; padding-right: 15px; padding-left: 15px; }}
        .section {{ padding: 20px 0; }}
        .clearfix::after {{ content: ""; display: table; clear: both; }}
        @media (min-width: 768px) {{
            .col-md-8 {{ flex: 0 0 66.66667%; max-width: 66.66667%; }}
            .col-md-4 {{ flex: 0 0 33.33333%; max-width: 33.33333%; padding-right: 15px; }}
            .hidden-md-down {{ display: block !important; }}
            .hidden-lg-up {{ display: none !important; }}
        }}
        @media (max-width: 767px) {{
            .hidden-md-down {{ display: none !important; }}
            .col-md-4 {{ padding-right: 15px; }}
        }}
        #header {{ border-bottom: 1px solid #e0e0e0; padding-bottom: 15px; margin-bottom: 20px; }}
        .logo-box {{ display: flex; align-items: center; justify-content: flex-start; padding-left: 20px; }}
        .logo-box img {{ height: 60px; width: auto; }}
        .title {{ font-size: 28px; line-height: 1.3; font-weight: 400; color: #333; margin-bottom: 25px; text-transform: uppercase; margin-top: 10px; padding-left: 15px; }}
        .images {{ position: relative; margin-bottom: 200px; max-width: 450px; margin-left: auto; margin-right: auto; }}
        .main-sentinel {{ width: 100%; visibility: hidden; }}
        .image {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; }}
        .thumbnails-control, .main-control {{ display: none; }}
        .thumbnail {{ position: absolute; bottom: -150px; width: 80px; height: 80px; border-radius: 50%; background: #fff; cursor: pointer; border: 2px solid #eee; overflow: hidden; z-index: 5; display: flex; align-items: center; justify-content: center; }}
        .thumbnail img {{ width: 100%; height: 100%; object-fit: contain; padding: 5px; border-radius: 50%; }}
        .thumbnail:hover {{ border-color: {data['brand_color']}; }}
        .thumbnails-control:checked + .thumbnail {{ border-color: {data['brand_color']}; opacity: 1; }}
        .main {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #fff; opacity: 0; z-index: 1; transition: opacity 0.3s; display: flex; align-items: center; justify-content: center; }}
        .main img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
        .thumbnails-control:checked ~ .main {{ opacity: 1; z-index: 2; }}
        @media (min-width: 768px) {{
            .images {{ max-width: 600px; margin-left: 0; margin-right: 0; margin-bottom: {desktop_margin_bottom}px; }}
{desktop_css}
        }}
        @media (max-width: 500px) {{
            .images {{ margin-bottom: {mobile_margin_bottom}px; }}
{mobile_css}
        }}
        .condition {{ border: 2px solid #ddd; padding: 20px; margin-bottom: 25px; background: #fff; margin-top: 20px; }}
        .condition h2 {{ font-size: 18px; margin-bottom: 15px; color: #333; font-weight: 600; }}
        .condition ul li {{ font-size: 14px; margin-bottom: 10px; padding-left: 20px; position: relative; color: #555; }}
        .condition ul li::before {{ content: "•"; position: absolute; left: 0; color: #333; font-weight: bold; }}
        .condition ul li strong {{ color: #333; }}
        .accordion-content ul {{ list-style: disc; padding-left: 20px; margin: 0 0 15px 0; }}
        .accordion-content ul li {{ margin-bottom: 6px; padding-left: 4px; }}
        .accordion-content h2, .accordion-content h3, .accordion-content strong {{ color: {data['brand_color']}; font-weight: 600; }}
        .accordion-content .product-specifications {{ margin-top: 20px; margin-bottom: 20px; }}
        .accordion-content .product-specifications h3 {{ margin-bottom: 12px; font-size: 16px; }}
        .accordion-content .product-specifications table {{ width: 100%; border-collapse: collapse; font-size: 14px; color: #333; }}
        .accordion-content .product-specifications table th {{ text-align: left; padding: 10px 12px; border: 1px solid #ddd; background: #f5f5f5; font-weight: 600; color: #333; width: 35%; }}
        .accordion-content .product-specifications table td {{ padding: 10px 12px; border: 1px solid #ddd; background: #fff; }}
        .accordion-content .product-specifications table tr:nth-child(even) td {{ background: #fafafa; }}
        .accordion-content .product-specifications table tr:hover td {{ background: #f8f8f8; }}
        .buttons .btn {{ display: block; width: 100%; padding: 16px 0; text-align: center; border: 2px solid {data['brand_color']}; color: {data['brand_color']}; border-radius: 50px; font-weight: bold; margin-bottom: 15px; background: #fff; font-size: 16px; }}
        .buttons .btn:hover {{ background: {data['brand_color']}; color: #fff; }}
        .accordion-area {{ margin-top: 40px; max-width: 100%; margin-left: auto; margin-right: auto; }}
        .accordion-box {{ background: #ffffff; border: 1px solid #d3d3d3; border-radius: 8px; margin-bottom: 30px; overflow: hidden; }}
        .accordion-box summary {{ padding: 18px 25px; cursor: pointer; list-style: none; font-size: 16px; font-weight: 400; color: #333; background: #ffffff; display: flex; justify-content: space-between; align-items: center; }}
        .accordion-box summary::-webkit-details-marker {{ display: none; }}
        .accordion-box summary:hover {{ background-color: #fafafa; color: {data['brand_color']}; }}
        .accordion-box summary .toggle-icon {{ width: 20px; height: 20px; transition: transform 0.3s ease; stroke: #333; }}
        .accordion-box details[open] summary .toggle-icon {{ transform: rotate(180deg); stroke: {data['brand_color']}; }}
        .accordion-box details[open] summary {{ border-bottom: 1px solid #eee; color: {data['brand_color']}; font-weight: bold; }}
        .accordion-content {{ padding: 25px; font-size: 14px; color: #333; line-height: 1.6; }}
        .delivery-section {{ display: flex; justify-content: space-between; align-items: flex-start; }}
        .delivery-info {{ flex: 1; }}
        .delivery-subtitle {{ color: {data['brand_color']}; font-weight: 600; font-size: 14px; margin-bottom: 15px; }}
        .delivery-item {{ margin-bottom: 12px; font-size: 14px; color: #333; line-height: 1.5; }}
        .delivery-label {{ font-weight: 600; }}
        .delivery-icons {{ display: flex; gap: 15px; align-items: center; margin-left: 20px; }}
        .delivery-icon {{ width: 70px; height: 70px; fill: #999; }}
        @media (max-width: 600px) {{
            .delivery-section {{ flex-direction: column; }}
            .delivery-icons {{ margin-left: 0; margin-top: 20px; width: 100%; justify-content: flex-start; }}
            .delivery-icon {{ width: 50px; height: 50px; }}
        }}
        #footer {{ background-color: #ececec; padding: 40px 20px; margin-top: 50px; }}
        #footer h3 {{ font-size: 16px; font-weight: 600; color: #333; margin: 0 0 20px 0; }}
        #footer a {{ color: #333; text-decoration: none; font-size: 14px; font-weight: 400; }}
        #footer a:hover {{ color: {data['brand_color']}; text-decoration: underline; }}
    </style>
</head>
<body>
<div id="page">
    <header id="header" class="section">
        <div class="container">
            <div class="row">
                <div class="col-xs-12 col-lg-6">
                    <a target="_blank" href="#" title="Cheap Furniture Warehouse" class="logo">
                        <div class="logo-box">
                            <img src="{data['logo_url']}" alt="Cheap Furniture Warehouse" />
                        </div>
                    </a>
                </div>
            </div>
        </div>
        
    </header>
    <div id="main">
        <section class="container">
            <div class="row">
                <div class="col-xs-12">
                    <div class="row">
                        <div class="col-xs-12">
                            <h1 class="title">{data['product_title']} </h1>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-xs-12 col-md-8">
                            <div class="images">
                                {sentinel_img}
{images_html}
                            </div>
                        </div>
                        <div class="col-xs-12 col-md-4">
                            <div class="condition">
                                <h2>{condition_title}</h2>
                                <ul>
{condition_details}
                                </ul>
                            </div>
                            <div class="buttons clearfix">
                                <a class="btn" href="#" onclick="window.parent.postMessage({{action: 'CONTACT_SELLER'}}, '*'); return false;">Contact</a>
                                <a target="_blank" class="btn" href="{data.get('shop_url', 'https://www.ebay.co.uk/str/cfurniturewarehousebradford')}">Visit our eBay shop</a>
                            </div>
                        </div>
                    </div>
                    <div class="accordion-area">
                        <div class="accordion-box">
                            <details open>
                                <summary>
                                    <span style="font-size: 16px;">Description</span>
                                    <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="6 9 12 15 18 9"></polyline>
                                    </svg>
                                </summary>
                                <div class="accordion-content">
                                    {desc_html}
                                </div>
                            </details>
                        </div>
                        <div class="accordion-box">
                            <details>
                                <summary>
                                    <span style="font-size: 16px;">Delivery</span>
                                    <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="6 9 12 15 18 9"></polyline>
                                    </svg>
                                </summary>
                                <div class="accordion-content">
                                    <div class="delivery-section">
                                        <div class="delivery-info">
                                            <div class="delivery-subtitle">Delivery Information</div>
{delivery_html}
                                        </div>
                                    </div>
                                </div>
                            </details>
                        </div>
                        <div class="accordion-box">
                            <details>
                                <summary>
                                    <span style="font-size: 16px;">Returns</span>
                                    <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="6 9 12 15 18 9"></polyline>
                                    </svg>
                                </summary>
                                <div class="accordion-content">
                                    <p>We offer <strong>{returns_title}</strong>.</p>
                                    <ul>
{returns_details}
                                    </ul>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </div>
</div>
</body>
</html>"""
    
    return html


def generate_html_files():
    """Generate HTML files from all JSON files in products folder"""
    print("\n" + "=" * 60)
    print("🚀 Generating HTML Files")
    print("=" * 60)
    
    if not OUTPUT_DIR.exists() or not OUTPUT_DIR.is_dir():
        print(f"❌ Error: 'products' folder not found at: {OUTPUT_DIR}")
        return False
    
    json_files = sorted(OUTPUT_DIR.glob("*.json"))
    if not json_files:
        print(f"❌ Error: No JSON files found in: {OUTPUT_DIR}")
        return False
    
    print(f"📂 Found {len(json_files)} JSON file(s) in 'products' folder.\n")
    
    success_count = 0
    fail_count = 0
    
    for json_file in json_files:
        print(f"📂 Loading: {json_file.name}")
        data = load_json_file(json_file)
        if data is None:
            fail_count += 1
            continue
        
        try:
            html = generate_html_from_data(data)
        except Exception as e:
            print(f"❌ Error during generation for '{json_file.name}': {e}")
            fail_count += 1
            continue
        
        output_filename = json_file.stem + "-generated.html"
        OUTPUT_HTML_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_HTML_DIR / output_filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✅ Created: html/{output_filename}\n")
            success_count += 1
        except Exception as e:
            print(f"❌ Error saving file '{output_filename}': {e}\n")
            fail_count += 1
    
    print("=" * 60)
    print(f"✅ Successfully generated: {success_count} HTML file(s) in 'html' folder")
    if fail_count:
        print(f"⚠️  Failed: {fail_count} file(s)")
    print("=" * 60)
    
    return success_count > 0


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    if not URL_CSV_PATH.exists():
        print(f"CSV file not found at {URL_CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    urls = read_urls_from_csv(URL_CSV_PATH)
    if not urls:
        print("No URLs found in url.csv", file=sys.stderr)
        sys.exit(1)

    # Load template first (needed to build product JSON files from scraped data)
    # We check this early so we don't waste time scraping if template is missing
    print("📄 Loading product template (required for building product JSON files)...")
    try:
        template = load_template()
        print("✅ Template loaded successfully\n")
    except Exception as e:
        print(f"\n❌ Failed to load product-template.json")
        print(f"Error: {e}")
        print(f"\nDebugging info:")
        print(f"  Current working directory: {Path.cwd()}")
        print(f"  BASE_DIR: {BASE_DIR}")
        print(f"  Looking for template in: {TEMPLATE_PATH}")
        if getattr(sys, 'frozen', False):
            print(f"  Executable location: {sys.executable}")
            if hasattr(sys, '_MEIPASS'):
                print(f"  Temp folder (_MEIPASS): {sys._MEIPASS}")
        print(f"\n💡 Solution: Place product-template.json in the same folder as:")
        if getattr(sys, 'frozen', False):
            print(f"   → {Path(sys.executable).parent}")
        else:
            print(f"   → {BASE_DIR}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Determine which sites are being scraped
    has_very_urls = any(is_very(url) for url in urls)
    has_argos_urls = any(is_argos(url) for url in urls)
    has_cfw_urls = any(is_cheapfurniturewarehouse(url) for url in urls)
    
    sites = []
    if has_argos_urls:
        sites.append("Argos")
    if has_very_urls:
        sites.append("Very.co.uk")
    if has_cfw_urls:
        sites.append("CheapFurnitureWarehouse")
    
    sites_str = " + ".join(sites) if sites else "Multiple Sites"
    print(f"🚀 Starting Combined Scraper ({sites_str})...")
    print(f"   URLs to scrape: {len(urls)}\n")

    results: List[Dict[str, Any]] = []
    
    # Use a single driver for all sites that need Selenium (more efficient)
    driver = None

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

    print(
        f"\n✅ Scraping completed! Wrote {len(results)} product JSON file(s) to {OUTPUT_DIR}"
    )
    
    # Step 2: Generate HTML files from the scraped JSON files
    if len(results) > 0:
        print("\n")
        html_success = generate_html_files()
        if html_success:
            print("\n✅ All tasks completed successfully!")
        else:
            print("\n⚠️  Scraping completed but HTML generation had issues.")
    else:
        print("\n⚠️  No products scraped, skipping HTML generation.")


if __name__ == "__main__":
    main()
