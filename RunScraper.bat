@echo off
title Product Scraper
color 0A
echo ========================================
echo    Product Scraper - Starting...
echo ========================================
echo.
echo Reading URLs from url.csv...
echo Output will be saved to 'products' folder
echo.
echo ========================================
echo.

ProductScraper.exe

echo.
echo ========================================
echo    Scraping Completed!
echo ========================================
echo.
echo Check the 'products' folder for results
echo.
pause
