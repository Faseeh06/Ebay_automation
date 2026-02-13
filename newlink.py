from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# ─── SETUP ────────────────────────────────────────────────────────────

options = webdriver.ChromeOptions()
options.add_argument("--headless")   # run without opening a window
options.add_argument("--disable-gpu")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

url = "https://cheapfurniturewarehouse.co.uk/collections/furniture-clearance/products/minky-wing-12m-heated-clothes-airer-with-cover"
driver.get(url)

time.sleep(2)  # wait a bit for page to load JS

# ─── SCRAPE TEXT DATA ─────────────────────────────────────────────────

try:
    title = driver.find_element(
        By.XPATH, '//*[@id="ProductInfo-template--25585833705806__main-product"]/div/div[1]/div/h1'
    ).text
except:
    title = None

try:
    second_text = driver.find_element(
        By.XPATH, '//*[@id="ProductInfo-template--25585833705806__main-product"]/div/div[3]'
    ).text
except:
    second_text = None

print("\n--- PRODUCT INFO ---")
print("Title:", title)
print("Info:", second_text)

# ─── SCRAPE ALL IMAGES ─────────────────────────────────────────────────

imgs = []

# Get all thumbnails by using 'contains' on dynamic IDs
thumbs = driver.find_elements(
    By.XPATH, '//div[contains(@id,"Media-Thumbnails-template")]//img'
)

for img in thumbs:
    src = img.get_attribute("src")
    if src and src not in imgs:
        imgs.append(src)

# Also try main featured image(s) in the slider
main_imgs = driver.find_elements(
    By.XPATH, '//div[contains(@id,"Slide-template")]//img'
)
for img in main_imgs:
    src = img.get_attribute("src")
    if src and src not in imgs:
        imgs.append(src)

print("\n--- IMAGES ---")
for i, url in enumerate(imgs):
    print(f"{i+1}. {url}")

driver.quit()
