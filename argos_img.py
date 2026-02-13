from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import random

# Product URLs
product_urls = [
    "https://www.argos.co.uk/product/5795743",
    "https://www.argos.co.uk/product/7483125"
]


def get_stealth_driver(headless=True):
    """Create Chrome driver with strong anti-bot bypass features"""
    options = Options()
    
    # Basic stealth options
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic user agent (Windows Chrome)
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_argument(f"user-agent={user_agent}")
    
    # Window and display settings
    if headless:
        options.add_argument("--headless=new")
    else:
        # Maximize window so user can see what's happening
        options.add_argument("--start-maximized")
    
    # Language and locale
    options.add_argument("--lang=en-GB")
    options.add_argument("--accept-lang=en-GB,en;q=0.9")
    
    # Additional stealth arguments
    if headless:
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins-discovery")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    
    # Remove automation indicators
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # Performance and stealth
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    
    # Create driver
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    # Execute stealth JavaScript to hide webdriver property
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-GB', 'en']
            });
            
            // Chrome runtime
            window.chrome = {
                runtime: {}
            };
            
            // Override toString methods
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter(parameter);
            };
        """
    })
    
    # Additional CDP commands for stealth
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {
        "userAgent": user_agent,
        "acceptLanguage": "en-GB,en;q=0.9",
        "platform": "Win32"
    })
    
    return driver


# Create driver with stealth features (headless=False to see what's happening)
driver = get_stealth_driver(headless=False)

for url in product_urls:
    print(f"\n{'='*60}")
    print(f"Fetching images from: {url}")
    print('='*60)
    
    # Random delay before navigation (human-like behavior)
    delay = random.uniform(1.5, 3.5)
    time.sleep(delay)
    
    driver.get(url)
    
    # Wait for page to load with random delay
    time.sleep(random.uniform(3, 6))
    
    # Scroll a bit to trigger lazy loading (human-like behavior)
    driver.execute_script("window.scrollTo(0, 300);")
    time.sleep(random.uniform(1, 2))
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(random.uniform(1, 2))

    # XPath Method: Navigate slider and extract all images + videos
    print("\n--- XPath Method: Navigate slider to unlock all images and videos ---")
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
        
        print("Navigating through slider to load all images and videos...")
        
        seen_urls = set()
        seen_video_urls = set()
        
        # Function to collect all images and videos from container
        def collect_media(container, label=""):
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
                # Try different video URL attributes
                video_src = (
                    video.get_attribute("src") or 
                    video.get_attribute("data-src") or 
                    video.get_attribute("data-video-url") or
                    video.get_attribute("data-video")
                )
                
                # Also check for video source tags
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
        img_count, vid_count = collect_media(slider_container, "initial")
        print(f"  Initial: {img_count} images, {vid_count} videos")
        
        # Navigate through slider
        try:
            next_button = driver.find_element(By.XPATH, next_button_xpath)
            max_clicks = 30  # Increased limit
            click_count = 0
            consecutive_no_new = 0
            
            while click_count < max_clicks:
                # Check if button is enabled/clickable
                try:
                    if not next_button.is_enabled() or not next_button.is_displayed():
                        print(f"  Button not clickable after {click_count} clicks")
                        break
                except:
                    print(f"  Button disappeared after {click_count} clicks")
                    break
                
                # Click the next button
                driver.execute_script("arguments[0].click();", next_button)
                click_count += 1
                
                # Wait for content to load
                time.sleep(random.uniform(1.0, 2.0))
                
                # Re-find slider container (may have updated)
                try:
                    slider_container = driver.find_element(
                        By.XPATH,
                        '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[1]/section/section/div/div/div/div[2]/div[1]/div[1]/div[1]'
                    )
                except:
                    print(f"  Slider container not found after click {click_count}")
                    break
                
                # Collect new media
                img_count, vid_count = collect_media(slider_container, f"click {click_count}")
                
                if img_count == 0 and vid_count == 0:
                    consecutive_no_new += 1
                    if consecutive_no_new >= 2:
                        print(f"  No new media found after {consecutive_no_new} consecutive clicks, stopping")
                        break
                else:
                    consecutive_no_new = 0
                    print(f"  Click {click_count}: Found {img_count} new image(s), {vid_count} new video(s)")
                
                # Try to find next button again (may have changed state)
                try:
                    next_button = driver.find_element(By.XPATH, next_button_xpath)
                except:
                    print(f"  Next button not found after {click_count} clicks")
                    break
                    
        except Exception as btn_error:
            print(f"  Could not navigate slider: {btn_error}")
            print("  Proceeding with media found so far...")
        
        # Final comprehensive collection - get ALL media from entire slider container
        print("\nFinal collection: Gathering all images and videos from slider...")
        try:
            slider_container = driver.find_element(
                By.XPATH,
                '//*[@id="content"]/main/div[2]/div[2]/div[1]/section[1]/section/section/div/div/div/div[2]/div[1]/div[1]/div[1]'
            )
            
            # Use JavaScript to find ALL images and videos in the DOM (including hidden)
            all_media_js = """
            var container = arguments[0];
            var results = {images: [], videos: []};
            
            // Find all images
            var imgs = container.querySelectorAll('img, picture img');
            imgs.forEach(function(img) {
                var src = img.src || img.getAttribute('data-src') || img.getAttribute('data-main-image-url') || img.getAttribute('data-lazy-src');
                if (src && src.includes('media.4rgos.it')) {
                    results.images.push(src);
                }
            });
            
            // Find all videos
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
            print(f"  Error in final collection: {e}")
        
        # Remove duplicates and print results
        unique_image_urls = list(dict.fromkeys(image_urls))
        unique_video_urls = list(dict.fromkeys(video_urls))
        
        print(f"\n✅ Total unique images found: {len(unique_image_urls)}")
        for idx, url in enumerate(unique_image_urls, 1):
            print(f"  Image {idx}. {url}")
        
        print(f"\n✅ Total unique videos found: {len(unique_video_urls)}")
        for idx, url in enumerate(unique_video_urls, 1):
            print(f"  Video {idx}. {url}")
        
        if not unique_image_urls and not unique_video_urls:
            print("  ❌ No media found")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Random delay between URLs (human-like behavior)
    if url != product_urls[-1]:  # Don't delay after last URL
        delay = random.uniform(2, 5)
        print(f"\nWaiting {delay:.1f}s before next URL...")
        time.sleep(delay)

driver.quit()
print("\n✅ Scraping completed!")
