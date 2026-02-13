#!/usr/bin/env python3
"""
eBay Listing Generator
Generates HTML listings from ALL JSON product files in the products/ folder
"""

import json
import sys
from pathlib import Path


def load_json(json_file):
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


def generate_images(images):
    """Generate image gallery HTML"""
    if len(images) == 0:
        return "", "" # No images

    # Use whatever images are provided
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
        return "", "", 200, 200 # Defaults

    # --- DESKTOP ---
    # Max width 600px. Thumbnail width 80px. Spacing 120px centers 5 items perfectly.
    # 5 items per row.
    desktop_css = "            /* Desktop Positioning */\n"
    desktop_step = 120
    max_per_row_desktop = 5
    
    for i in range(num_images):
        row = i // max_per_row_desktop
        col = i % max_per_row_desktop
        
        left_pos = col * desktop_step
        # Base bottom is -150px. Each new row pushes down by 100px?
        # Thumbnails are 80px tall. Padding 20px. 
        # Let's say step down by 90px (same as mobile) or 100px.
        bottom_pos = -150 - (row * 100)
        
        desktop_css += f"            .image:nth-of-type({i+1}) .thumbnail {{ left: {left_pos}px; bottom: {bottom_pos}px; }}\n"

    # Calculate Desktop margin offset
    # 1 row (0) -> 200px margin (standard)
    # 2 rows (1) -> 200 + 100 = 300px
    desktop_rows = (num_images - 1) // max_per_row_desktop
    desktop_margin_bottom = 200 + (desktop_rows * 100)


    # --- MOBILE ---
    # Max width ~350px. 4 items per row. Spacing 90px.
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
    mobile_margin_bottom = 260 + (mobile_rows * 90) # Standard was 260 for mobile in original CSS
    
    return desktop_css, desktop_margin_bottom, mobile_css, mobile_margin_bottom


def generate_condition(condition):
    """Generate condition box HTML"""
    details_html = ""
    for detail in condition['details']:
        details_html += f"                                    <li>{detail}</li>\n"
    
    return condition['title'], details_html


def generate_description(desc):
    """Return main description HTML only (scraped)."""
    return desc.get('main_text', '')


def generate_delivery(delivery):
    """Generate delivery section HTML"""
    items_html = ""
    for item in delivery['items']:
        label_html = f"<span class=\"delivery-label\">{item['label']}</span> " if item['label'] else ""
        items_html += f"                                            <div class=\"delivery-item\">{label_html}{item['value']}</div>\n"
    
    return items_html


def generate_returns(returns):
    """Generate returns section HTML"""
    details_html = ""
    for detail in returns['details']:
        details_html += f"                                        <li>{detail}</li>\n"
    
    return returns['title'], details_html


def generate_html(data):
    """Generate complete HTML from product data"""
    
    # Generate sections
    sentinel_img, images_html = generate_images(data['images'])
    condition_title, condition_details = generate_condition(data['condition'])
    desc_html = generate_description(data['description'])
    delivery_html = generate_delivery(data['delivery'])
    returns_title, returns_details = generate_returns(data['returns'])
    
    # Generate dynamic CSS for images
    desktop_css, desktop_margin_bottom, mobile_css, mobile_margin_bottom = generate_gallery_css(len(data['images']))
    
    # Complete HTML template
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
<title>{data['page_title']}</title>

    <style>
        /* =========================================================
           1. RESET & FONTS
           ========================================================= */
        html, body {{ margin: 0; padding: 0; font-family: "Trebuchet MS", "Lucida Grande", sans-serif; background: #fff; color: #333; font-size: 14px; line-height: 1.5; -webkit-font-smoothing: antialiased; }}
        * {{ box-sizing: border-box; }}
        img {{ max-width: 100%; height: auto; display: block; }}
        a {{ color: #333; text-decoration: none; transition: all 0.2s ease; }}
        
        /* BRAND COLOR HOVER */
        a:hover {{ color: {data['brand_color']}; }}

        p {{ margin: 0 0 15px; }}
        ul {{ list-style: none; padding: 0; margin: 0; }}
        
        /* HEADINGS - BRAND COLOR */
        h1, h2, h3 {{ font-weight: 700; color: {data['brand_color']}; margin-top: 0; margin-bottom: 15px; }} 

        /* =========================================================
           2. LAYOUT GRID
           ========================================================= */
        .container {{ padding-right: 15px; padding-left: 15px; margin-right: auto; margin-left: auto; max-width: 1200px; }}
        .row {{ margin-right: -15px; margin-left: -15px; display: flex; flex-wrap: wrap; }}
        .col-xs-12, .col-md-8, .col-md-4, .col-lg-8, .col-lg-6 {{ position: relative; width: 100%; padding-right: 15px; padding-left: 15px; }}
        .section {{ padding: 20px 0; }}
        .clearfix::after {{ content: ""; display: table; clear: both; }}

        @media (min-width: 768px) {{
            .col-md-8 {{ flex: 0 0 66.66667%; max-width: 66.66667%; }}
            .col-md-4 {{ 
                flex: 0 0 33.33333%; 
                max-width: 33.33333%; 
                padding-right: 15px; 
            }}
            .hidden-md-down {{ display: block !important; }}
            .hidden-lg-up {{ display: none !important; }}
        }}
        @media (max-width: 767px) {{
            .hidden-md-down {{ display: none !important; }}
            .col-md-4 {{ padding-right: 15px; }}
        }}

        /* =========================================================
           3. HEADER
           ========================================================= */
        #header {{
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}

        .logo-box {{
            display: flex; 
            align-items: center; 
            justify-content: flex-start; 
            padding-left: 20px; 
        }}
        
        .logo-box img {{
            height: 60px;
            width: auto;
        }}
        
        /* =========================================================
           4. PRODUCT TITLE
           ========================================================= */
        .title {{ 
            font-size: 28px; 
            line-height: 1.3; 
            font-weight: 400; 
            color: #333; 
            margin-bottom: 25px; 
            text-transform: uppercase; 
            margin-top: 10px; 
            padding-left: 15px; 
        }}

        /* =========================================================
           5. GALLERY
           ========================================================= */
        .images {{ 
            position: relative; 
            margin-bottom: 200px; 
            max-width: 450px; 
            margin-left: auto; margin-right: auto; 
        }} 
        
        .main-sentinel {{ width: 100%; visibility: hidden; }} 
        
        .image {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; }}
        .thumbnails-control, .main-control {{ display: none; }}

        .thumbnail {{ 
            position: absolute; 
            bottom: -150px; 
            width: 80px; height: 80px; border-radius: 50%; 
            background: #fff; cursor: pointer; border: 2px solid #eee;
            overflow: hidden; z-index: 5;
            display: flex; align-items: center; justify-content: center;
        }}
        
        .thumbnail img {{ 
            width: 100%; height: 100%; 
            object-fit: contain; 
            padding: 5px; 
            border-radius: 50%;
        }}
        
        .thumbnail:hover {{ border-color: {data['brand_color']}; }}
        .thumbnails-control:checked + .thumbnail {{ border-color: {data['brand_color']}; opacity: 1; }}

        .main {{ 
            position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
            background: #fff; opacity: 0; z-index: 1; transition: opacity 0.3s; 
            display: flex; align-items: center; justify-content: center;
        }}
        .main img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
        .thumbnails-control:checked ~ .main {{ opacity: 1; z-index: 2; }}

        @media (min-width: 768px) {{
            .images {{
                max-width: 600px; 
                margin-left: 0;  
                margin-right: 0;
                margin-bottom: {desktop_margin_bottom}px;
            }}
{desktop_css}
        }}
        
        @media (max-width: 500px) {{
            .images {{ margin-bottom: {mobile_margin_bottom}px; }}

{mobile_css}
        }}
        
        /* =========================================================
           6. RIGHT SIDEBAR
           ========================================================= */
        .condition {{ border: 2px solid #ddd; padding: 20px; margin-bottom: 25px; background: #fff; margin-top: 20px; }}
        .condition h2 {{ font-size: 18px; margin-bottom: 15px; color: #333; font-weight: 600; }}
        .condition ul li {{ font-size: 14px; margin-bottom: 10px; padding-left: 20px; position: relative; color: #555; }}
        .condition ul li::before {{ content: "•"; position: absolute; left: 0; color: #333; font-weight: bold; }}
        .condition ul li strong {{ color: #333; }}

        .buttons .btn {{
            display: block; 
            width: 100%; 
            padding: 16px 0; 
            text-align: center;
            border: 2px solid {data['brand_color']}; 
            color: {data['brand_color']}; 
            border-radius: 50px; 
            font-weight: bold; 
            margin-bottom: 15px; 
            background: #fff; 
            font-size: 16px; 
        }}
        .buttons .btn:hover {{ background: {data['brand_color']}; color: #fff; }}

        /* =========================================================
           7. ACCORDION SECTIONS
           ========================================================= */
        .accordion-area {{ 
            margin-top: 40px; 
            max-width: 100%; 
            margin-left: auto; 
            margin-right: auto;
        }}

        .accordion-box {{
            background: #ffffff;
            border: 1px solid #d3d3d3;
            border-radius: 8px;
            margin-bottom: 30px;
            overflow: hidden;
        }}

        .accordion-box summary {{
            padding: 18px 25px;
            cursor: pointer;
            list-style: none;
            font-size: 16px;
            font-weight: 400;
            color: #333;
            background: #ffffff;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
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

        /* =========================================================
           8. FOOTER
           ========================================================= */
        #footer {{ background-color: #ececec; padding: 40px 20px;  margin-top: 50px; }}
        #footer h3 {{ font-size: 16px; font-weight: 600; color: #333; margin: 0 0 20px 0; }}
        #footer a {{ color: #333; text-decoration: none; font-size: 14px; font-weight: 400; }}
        #footer a:hover {{ color: {data['brand_color']}; text-decoration: underline; }}
    </style>
</head>
<body>

<div id="page">

    <!-- HEADER SECTION -->
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

    <!-- MAIN PRODUCT SECTION -->
    <div id="main">
        <section class="container">
            <div class="row">
                <div class="col-xs-12">
                    
                    <!-- PRODUCT TITLE -->
                    <div class="row">
                        <div class="col-xs-12">
                            <h1 class="title">{data['product_title']} </h1>
                        </div>
                    </div>

                    <div class="row">
                        <!-- IMAGE GALLERY -->
                        <div class="col-xs-12 col-md-8">
                            <div class="images">
                                <!-- Sentinel -->
                                {sentinel_img}
{images_html}
                            </div>
                        </div>

                        <!-- RIGHT SIDEBAR -->
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

                    <!-- ACCORDION SECTION -->
                    <div class="accordion-area">
                        <!-- Description Box -->
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
                        <!-- Delivery Box -->
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
{delivery_html}                                        </div>
                                    </div>
                                </div>
                            </details>
                        </div>
                        <!-- Returns Box -->
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
{returns_details}                                    </ul>
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


def main():
    print("🚀 eBay Listing Generator (Batch Mode)")
    print("==========================================")

    base_dir = Path(__file__).resolve().parent
    products_dir = base_dir / "products"

    if not products_dir.exists() or not products_dir.is_dir():
        print(f"❌ Error: 'products' folder not found at: {products_dir}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    json_files = sorted(products_dir.glob("*.json"))
    if not json_files:
        print(f"❌ Error: No JSON files found in: {products_dir}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    print(f"📂 Found {len(json_files)} JSON file(s) in 'products' folder.\n")

    success_count = 0
    fail_count = 0

    for json_file in json_files:
        print(f"📂 Loading: {json_file.name}")
        data = load_json(json_file)
        if data is None:
            fail_count += 1
            continue

        # Generate HTML for this product
        try:
            html = generate_html(data)
        except Exception as e:
            print(f"❌ Error during generation for '{json_file.name}': {e}")
            fail_count += 1
            continue

        # Save output next to the JSON
        output_filename = json_file.stem + "-generated.html"
        output_path = json_file.parent / output_filename

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✅ Created: {output_filename}\n")
            success_count += 1
        except Exception as e:
            print(f"❌ Error saving file '{output_filename}': {e}\n")
            fail_count += 1

    print("==========================================")
    print(f"✅ Successfully generated: {success_count} file(s)")
    if fail_count:
        print(f"⚠️  Failed: {fail_count} file(s)")
    print("Done.")
    # Always pause at the end so user can see the result if double-clicked
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
