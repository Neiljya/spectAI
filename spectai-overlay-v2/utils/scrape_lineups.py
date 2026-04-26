import asyncio
import json
import os
import re
import httpx
from pathlib import Path
from playwright.async_api import async_playwright, Page

BASE_URL   = "https://lineupsvalorant.com"
OUT_JSON   = "lineups_data.json"
IMG_DIR    = Path("assets/lineups")
IMG_DIR.mkdir(parents=True, exist_ok=True)

MAPS = ["Ascent", "Bind", "Breeze", "Fracture", "Haven", "Icebox", "Lotus", "Pearl", "Split", "Sunset"]
AGENTS = ["Brimstone", "Viper", "Omen", "Astra", "Harbor", "Clove", "Sova", "Fade", "Gekko", "Killjoy", "Cypher", "Deadlock"]

async def download_image(url: str, path: Path):
    if path.exists(): return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, follow_redirects=True)
            if r.status_code == 200:
                path.write_bytes(r.content)
    except Exception as e:
        print(f"  [img] failed {url}: {e}")

async def extract_card(card, map_name: str, agent: str) -> dict | None:
    """Updated to match the provided HTML structure."""
    
    # 1. Extract ID from data-id attribute
    lineup_id = await card.get_attribute("data-id") or ""

    # 2. Extract Title
    title_el = await card.query_selector(".lineup-box-title")
    title = (await title_el.inner_text()).strip() if title_el else ""

    # 3. Extract Thumbnail URL (looking for the b-cdn source)
    img_el = await card.query_selector(".lineup-box-image")
    img_url = await img_el.get_attribute("src") if img_el else ""

    # 4. Extract From/To Locations (from the <a> tags inside .lineup-box-position)
    # The HTML shows: From <a href="?start=X">...</a> to <a href="?end=Y">...</a>
    from_loc = ""
    to_loc = ""
    links = await card.query_selector_all(".lineup-box-position a")
    for link in links:
        href = await link.get_attribute("href") or ""
        text = (await link.inner_text()).strip()
        if "start=" in href:
            from_loc = text
        elif "end=" in href:
            to_loc = text

    # 5. Extract Ability (from the alt text of the ability icon)
    abil_el = await card.query_selector(".lineup-box-abilities img")
    ability = (await abil_el.get_attribute("alt")) if abil_el else ""

    if not title and not img_url:
        return None

    # Download image
    local_img = ""
    if img_url and lineup_id:
        fname = IMG_DIR / f"{lineup_id}.webp"
        await download_image(img_url, fname)
        local_img = str(fname)

    return {
        "id": lineup_id,
        "map": map_name,
        "agent": agent,
        "ability": ability,
        "title": title,
        "from": from_loc,
        "to": to_loc,
        "img_url": img_url,
        "img_local": local_img,
    }

async def scrape_map_agent(page: Page, map_name: str, agent: str) -> list[dict]:
    url = f"{BASE_URL}/?map={map_name}&agent={agent}"
    lineups = []

    try:
        await page.goto(url, wait_until="networkidle", timeout=20_000)
        # The site uses an async search() function; wait for the grid to populate
        await page.wait_for_selector(".lineup-box", timeout=5000)
    except Exception:
        return lineups

    cards = await page.query_selector_all(".lineup-box")
    for card in cards:
        lineup = await extract_card(card, map_name, agent)
        if lineup:
            lineups.append(lineup)

    return lineups

async def main():
    all_lineups = []
    seen_ids = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        # Setting a standard user agent helps avoid bot detection
        ctx = await browser.new_context(user_agent="Mozilla/5.0...")
        page = await ctx.new_page()

        for map_name in MAPS:
            for agent in AGENTS:
                print(f"Scraping {map_name} / {agent}...", end=" ", flush=True)
                lineups = await scrape_map_agent(page, map_name, agent)
                
                new_count = 0
                for lu in lineups:
                    if lu["id"] not in seen_ids:
                        seen_ids.add(lu["id"])
                        all_lineups.append(lu)
                        new_count += 1
                print(f"found {new_count} new.")
                await asyncio.sleep(0.5)

        await browser.close()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_lineups, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())