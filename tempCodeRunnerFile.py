from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# ─── SETUP ────────────────────────────────────────────────────────────

options = webdriver.ChromeOptions()
options.add_argument("--headless")   # no window
options.add_argument("--disable-gpu")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

url = "https://cheapfurniturewarehouse.co.uk/collections/furniture-clearance/products/minky-wing-12m-heated-clothes-airer-with-cover"
driver.get(url)

time.sleep(3)  # let JS load


# ─── SCRAPE TEXT DATA ─────────────────────────────────────────────────

try:
    title = driver.find_element(
        By.XPATH, '//*[@id="ProductInfo-template--25585833705806__main-product"]/div/div[1]/div/h1'
    ).text
except Exception as e:
    title = None

try:
    second_text = driver.find_element(
        By.XPATH, '//*[@id="ProductInfo-template--25585833705806__main-product"]/div/div[3]'
    ).text
except Exception as e:
    second_text = None

print("\n--- PRODUCT INFO ---")
print("Title:", title)
print("Info:", second_text)


# ─── SCRAPE ALL IMAGES ─────────────────────────────────────────────────

imgs = []
thumbs = driver.find_elements(
    By.XPATH,
    '//*[@id="Media-Thumbnails-template--25585833705806__main-product-56240683090254"]//img'
)

for img in thumbs:
    src = img.get_attribute("src")
    if src and src not in imgs:
        imgs.append(src)

# Also try main featured image if exists
try:
    main_img = driver.find_element(
        By.CSS_SELECTOR, "#Slide-template--25585833705806__main-product-0 img"
    ).get_attribute("src")
    if main_img not in imgs:
        imgs.append(main_img)
except:
    pass


print("\n--- IMAGES ---")
for i, url in enumerate(imgs):
    print(f"{i+1}. {url}")

driver.quit()
