import asyncio
from playwright.async_api import async_playwright
import sys
import os
from pathlib import Path

async def take_screenshot(target_id):
    os.makedirs("screenshots", exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        if target_id == "mp-api":
            page = await browser.new_page()
            try:
                # Tomar screenshot de la API o del portal
                await page.goto("https://api2.mercadopublico.cl/v2/compra-agil?estado=publicada&tamano_pagina=10", timeout=15000)
                await asyncio.sleep(2)
                await page.screenshot(path="screenshots/mercadopublico_api.png", full_page=False)
            except Exception as e:
                print(f"Error mp-api: {e}")
                
        elif target_id == "linkedin-feed":
            # Usar la sesión guardada
            state_path = Path("../Linkedin-AG/linkedin_state.json")
            if state_path.exists():
                context = await browser.new_context(storage_state=str(state_path))
            else:
                context = await browser.new_context()
                
            page = await context.new_page()
            try:
                await page.goto("https://www.linkedin.com/feed/", timeout=20000)
                await asyncio.sleep(5)
                await page.screenshot(path="screenshots/linkedin_feed.png", full_page=False)
            except Exception as e:
                print(f"Error linkedin: {e}")

        await browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
        asyncio.run(take_screenshot(target))
