# Agent guide — Ebay_automation

Scrapes product pages (Argos, Very, CheapFurnitureWarehouse), writes one JSON per
product, then generates eBay listing HTML from those JSON files.

## Layout

| Path | Role |
|---|---|
| `final.py` | **The entrypoint.** Scrape + HTML generation. This is what `ProductScraper.spec` builds. Edit this one. |
| `working.py`, `newlink.py`, `tempCodeRunnerFile.py` | Older/scratch copies of the same scrapers. Not built, not run. |
| `build_exe.py` | Builds `ProductScraper.exe` (Windows only — see below). |
| `url.csv` | Input. One URL per line under a `url` header. |
| `products/` | Output JSON (`OUTPUT_DIR`). |
| `html/` | Output listing HTML (`OUTPUT_HTML_DIR`). |
| `product-template.json` | Required template; the run aborts without it. |

Flow: `main()` → reads `url.csv` → one shared Chrome driver → `scrape_product(url)`
dispatches on hostname (`is_argos` / `is_very` / `is_cheapfurniturewarehouse`) →
per-site scraper → `build_product_from_template` → `products/*.json` →
`generate_html_files()` → `html/`.

If you change a scraper in `final.py`, the sibling copies drift. Either patch them
too or leave them; just don't "fix" one of them and expect the build to change.

---

## Rule: never hardcode a Shopify section id

This caused a live outage and is the single most likely thing to break again.

CheapFurnitureWarehouse is Shopify. Its element ids embed a **section id**:

```
ProductInfo-template--31639337959758__main-product
                      ^^^^^^^^^^^^^^ regenerated on every theme republish
```

The scraper had `template--25585833705806__main-product` pasted in from a browser
"Copy XPath". The store republished its theme (now serving `/t/19/`), the number
changed, and every selector keyed to it silently stopped matching.

**Anything of the form `template--<digits>`, or a long digit run inside an id or
class, is volatile. Match the stable prefix or the theme's class names instead.**

```python
# NO — breaks on the next theme publish
'//*[@id="ProductInfo-template--25585833705806__main-product"]/div/div[1]/div/h1'

# YES — prefix + class, with ordered fallbacks
(By.CSS_SELECTOR, '[id^="ProductInfo-template--"] h1.product--title')
(By.CSS_SELECTOR, 'h1.product--title')
(By.XPATH, '//*[starts-with(@id,"ProductInfo-template--")]/div/div[1]/div/h1')
```

The current stable anchors on that site:

| Field | Selector |
|---|---|
| Title | `[id^="ProductInfo-template--"] h1.product--title` |
| Description | `[id^="ProductInfo-template--"] .product--short-description` |
| Specs table | `//*[contains(@id,"ProductAccordion-specifications_tab") and contains(@id,"__main-product")]/table` |
| Images | `//*[contains(@id,"Media-Thumbnails-template--")]//img`, `[id^="Slide-template--"] img` |

As of the last audit, no hardcoded section ids remain in any `.py` here. Verify with:

```bash
grep -rnE '@id="[^"]*--[0-9]{6,}' *.py
```

### Never swallow a selector failure

The description break went unnoticed for far longer than the title break, because
the title printed a warning and the description sat under a bare `except: pass`.
Worse, the success line still printed `Description: 187 chars` — that was the
*specifications* block appended to an empty description, so the log looked fine.

Every selector that fails must say so on stdout. Don't let one field's output be
counted as another's.

---

## Diagnosing "element not found" on a Shopify page

Don't launch a browser first. Fetch the HTML and read the real ids:

```bash
curl -sL -A "Mozilla/5.0" "<product-url>" -o p.html
grep -oE 'id="ProductInfo[^"]*"' p.html | sort -u
```

Two traps that will waste your time:

- **Dead URLs look like bot-blocking.** A delisted product returns a soft 404 with
  HTTP 200 and no product markup. Check for `<link rel="canonical" href=".../404">`
  or an `<h1>` like "Too slow — that deal's already gone!". The URLs in `url.csv`
  go stale; several already have.
- **Get a known-live URL from the storefront API**, not by guessing:
  ```bash
  curl -sL "https://cheapfurniturewarehouse.co.uk/products.json?limit=3"
  ```
  The site's `sitemap_products_1.xml` is not usable here — it returns only the
  homepage.

---

## Verifying a scraper fix

Run the actual function against a live page rather than trusting the selector by
eye. Selenium + a local Chrome is enough; no chromedriver install needed
(Selenium 4 resolves it).

```python
# harness.py
import sys, importlib.util
spec = importlib.util.spec_from_file_location("m", "final.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

d = m.get_driver(headless=True)
try:
    r = m.scrape_cheapfurniturewarehouse_product(d, "<live-product-url>")
finally:
    d.quit()

print("title :", repr(r["title"]))
print("images:", len(r["image_urls"]))
print("desc  :", len(r["description_html"]),
      "| specs:", "product-specifications" in r["description_html"])
```

Compare against the unpatched version to prove the fix is real:

```bash
git show HEAD:final.py > /tmp/final_orig.py
```

A healthy CheapFurnitureWarehouse result is a non-empty title, ~1400 chars of
description, `specs: True`, and 6–7 images. **An empty title with images still
found is the signature of this bug class** — id-agnostic selectors keep working
while id-pinned ones die, so a partial success is the tell.

---

## Building ProductScraper.exe

**Windows only.** PyInstaller cannot cross-compile; it emits a binary for the OS it
runs on. On macOS or Linux you will produce a non-Windows binary that is useless to
the client — don't ship one and don't claim the rebuild is done. Either use a
Windows machine or a `windows-latest` CI runner.

```bash
python build_exe.py      # -> dist/ProductScraper.exe
```

Then copy `dist/ProductScraper.exe` over `Final/ProductScraper.exe`, keeping
`url.csv` and `product-template.json` beside it. `RunScraper.bat` is the client's
launcher.

**Do not build from `ProductScraper.spec`.** Its `Analysis([...])` holds an absolute
path from the original author's machine (`D:\Study Stuff\Entech\...\final.py`) and
fails anywhere else. `build_exe.py` passes its arguments directly and regenerates
the spec, which is why it works. Fixing that path to a relative one is a
worthwhile cleanup that nobody has done yet.

Editing `final.py` does **not** update the `.exe`. A stale `Final/ProductScraper.exe`
next to a fixed `final.py` is the normal state of this repo after a code fix —
rebuild, or say explicitly that you didn't.

---

## Repo access

The GitHub repo is `Faseeh06/Ebay_automation`. Check push rights before promising a
push:

```bash
gh api repos/Faseeh06/Ebay_automation --jq '.permissions'
```

A secondary account may have read-only access, in which case `git push` fails with
403. Export the commit with `git format-patch -1 --stdout` and hand that over
rather than forking to the wrong account.

The related repo `hawkgeek/ebay-html` may 404 for the same reason — wrong account,
not a missing repo.
