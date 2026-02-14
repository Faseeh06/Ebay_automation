"""
Build script to create a standalone .exe file from final.py
Run this script to create an executable that works without Python installed
"""

import PyInstaller.__main__
import os
import sys

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
final_py_path = os.path.join(script_dir, "final.py")
icon_path = None  # You can add an icon file path here if you have one

# PyInstaller arguments
args = [
    final_py_path,
    '--name=ProductScraper',  # Name of the executable
    '--onefile',  # Create a single executable file
    '--console',  # Show console window (CMD) - IMPORTANT for seeing progress
    '--clean',  # Clean PyInstaller cache
    '--noconfirm',  # Overwrite output directory without asking
    '--add-data=url.csv;.',  # Include url.csv file (Windows format)
    '--add-data=product-template.json;.',  # Include product-template.json file (Windows format)
    '--hidden-import=selenium',
    '--hidden-import=selenium.webdriver',
    '--hidden-import=selenium.webdriver.chrome',
    '--hidden-import=selenium.webdriver.chrome.options',
    '--hidden-import=selenium.webdriver.chrome.service',
    '--hidden-import=selenium.webdriver.common.by',
    '--hidden-import=selenium.webdriver.support.ui',
    '--hidden-import=selenium.webdriver.support.expected_conditions',
    '--hidden-import=webdriver_manager',
    '--hidden-import=webdriver_manager.chrome',
    '--hidden-import=lxml',
    '--hidden-import=lxml.html',
    '--collect-all=selenium',
    '--collect-all=webdriver_manager',
]

# Add icon if it exists
if icon_path and os.path.exists(icon_path):
    args.append(f'--icon={icon_path}')

print("=" * 60)
print("Building ProductScraper.exe...")
print("=" * 60)
print("\nThis will create a standalone executable that:")
print("- Works without Python installed")
print("- Shows CMD window for output (so you can see progress)")
print("- Includes all dependencies")
print("- Does BOTH scraping AND HTML generation automatically")
print("\nBuilding...\n")

try:
    PyInstaller.__main__.run(args)
    print("\n" + "=" * 60)
    print("Build completed successfully!")
    print("=" * 60)
    print(f"\nExecutable location: {os.path.join(script_dir, 'dist', 'ProductScraper.exe')}")
    print("\nYou can now distribute ProductScraper.exe to clients.")
    print("Make sure to include url.csv and product-template.json in the same folder.")
    print("\nThe executable will:")
    print("  1. Scrape products from URLs in url.csv")
    print("  2. Generate HTML files automatically")
    print("  3. Show progress in CMD window")
except Exception as e:
    print(f"\nError building executable: {e}")
    print("\nMake sure PyInstaller is installed:")
    print("  pip install pyinstaller")
    sys.exit(1)
